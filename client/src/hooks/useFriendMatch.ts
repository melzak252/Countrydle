import { useCallback, useEffect, useRef, useState } from 'react';
import { friendError, friendMatchApi, friendRequestId, friendStatus, uncertainFriendRequest } from '../services/friendMatchApi';
import type { FriendAction, FriendActionPayloads, FriendActionType, FriendInvite, FriendSnapshot } from '../types/friendMatch';

export function useFriendMatch(code: string | undefined, fallbackError: string, staleError: string) {
  const [snapshot, setSnapshot] = useState<FriendSnapshot | null>(null);
  const [invite, setInvite] = useState<FriendInvite | null>(null);
  const [loading, setLoading] = useState(Boolean(code));
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [retryable, setRetryable] = useState(false);
  const [connection, setConnection] = useState<'connecting' | 'connected' | 'recovering'>('connecting');
  const current = useRef<FriendSnapshot | null>(null);
  const pending = useRef<FriendAction | null>(null);
  const inFlight = useRef(false);
  const [reload, setReload] = useState(0);
  const messages = useRef({ fallbackError, staleError });
  messages.current = { fallbackError, staleError };

  const accept = useCallback((next: FriendSnapshot) => {
    const previous = current.current;
    if (previous?.id === next.id && previous.version > next.version) return;
    // AI evidence does not change gameplay version. An earlier HTTP response must
    // not erase a completion already delivered by the socket.
    if (previous?.id === next.id) {
      const ranks = { pending: 0, running: 1, completed: 2, failed: 2 };
      const previousGuidance = new Map(previous.guidance.map(item => [item.question_id, item]));
      const guidance = next.guidance.map(item => {
        const old = previousGuidance.get(item.question_id);
        return old && ranks[old.status] > ranks[item.status] ? old : item;
      });
      next = { ...next, guidance };
      // If version and key fields are identical, avoid re-triggering component re-renders
      if (
        previous.version === next.version &&
        previous.phase === next.phase &&
        previous.status === next.status &&
        previous.active_player_id === next.active_player_id &&
        previous.pending_question_id === next.pending_question_id &&
        previous.history.length === next.history.length &&
        previous.guidance.length === next.guidance.length &&
        previous.players.every((p, i) => {
          const np = next.players[i];
          return np && p.ready === np.ready && p.connected === np.connected && p.question_count === np.question_count && p.guess_count === np.guess_count;
        }) &&
        JSON.stringify(previous.guidance) === JSON.stringify(next.guidance)
      ) {
        return;
      }
    }
    current.current = next;
    setSnapshot(next);
  }, []);

  useEffect(() => {
    let alive = true;
    current.current = null;
    pending.current = null;
    inFlight.current = false;
    // Keep resets together with the asynchronous room lookup, including Strict Mode cleanup.
    void (async () => {
      setSnapshot(null); setInvite(null); setError(''); setRetryable(false); setBusy(false);
      setLoading(Boolean(code));
      if (!code) return;
      try {
        const preview = await friendMatchApi.invite(code);
        if (!alive) return;
        setInvite(preview);
        try {
          const resumed = await friendMatchApi.snapshot(preview.id);
          if (alive) accept(resumed);
        } catch (cause) {
          if (friendStatus(cause) !== 403) throw cause;
        }
      } catch (cause) {
        if (alive) setError(friendError(cause, messages.current.fallbackError));
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => { alive = false; };
  }, [code, reload, accept]);

  const roomId = snapshot?.id;
  useEffect(() => {
    if (!roomId) return;
    let alive = true;
    let socket: WebSocket | null = null;
    let timer: number | undefined;
    let failures = 0;
    let syncing = false;
    const refresh = async () => {
      if (syncing) return;
      syncing = true;
      try {
        const next = await friendMatchApi.snapshot(roomId);
        if (alive) accept(next);
      } catch (cause) {
        if (alive) {
          setConnection('recovering');
          setError(friendError(cause, messages.current.fallbackError));
        }
      } finally { syncing = false; }
    };
    const connect = () => {
      if (!alive) return;
      setConnection(failures ? 'recovering' : 'connecting');
      try {
        socket = new WebSocket(friendMatchApi.socketUrl(roomId));
      } catch {
        schedule(); return;
      }
      socket.onopen = () => {
        if (!alive) return;
        failures = 0; setConnection('connected');
        void refresh();
      };
      socket.onmessage = event => {
        if (!alive) return;
        try {
          const next: FriendSnapshot = JSON.parse(event.data);
          if (next.id === roomId && Array.isArray(next.players) && Array.isArray(next.guidance)) accept(next);
        } catch { void refresh(); }
      };
      socket.onerror = () => { socket?.close(); };
      socket.onclose = () => { if (alive) schedule(); };
    };
    const schedule = () => {
      setConnection('recovering');
      clearTimeout(timer);
      timer = window.setTimeout(connect, Math.min(15000, 500 * 2 ** Math.min(failures++, 5)));
    };
    const wake = () => {
      if (document.visibilityState === 'hidden') return;
      void refresh();
      if (!socket || socket.readyState === WebSocket.CLOSED) { clearTimeout(timer); connect(); }
    };
    connect();
    // HTTP recovery also covers environments where WebSocket upgrades are blocked.
    const poll = setInterval(() => { if (document.visibilityState !== 'hidden') void refresh(); }, 10000);
    window.addEventListener('online', wake);
    document.addEventListener('visibilitychange', wake);
    return () => {
      alive = false; clearTimeout(timer); clearInterval(poll); socket?.close();
      window.removeEventListener('online', wake);
      document.removeEventListener('visibilitychange', wake);
    };
  }, [roomId, accept]);

  const sendPending = useCallback(async (): Promise<boolean> => {
    const action = pending.current;
    const room = current.current;
    if (!action || !room || inFlight.current) return false;
    inFlight.current = true; setBusy(true); setError('');
    try {
      const next = await friendMatchApi.action(room.id, action);
      if (current.current?.id !== room.id) return false;
      accept(next); pending.current = null; setRetryable(false);
      return true;
    } catch (cause) {
      if (current.current?.id !== room.id) return false;
      const uncertain = uncertainFriendRequest(cause);
      if (!uncertain) pending.current = null;
      setRetryable(uncertain);
      setError(friendStatus(cause) === 409 ? messages.current.staleError : friendError(cause, messages.current.fallbackError));
      try {
        const refreshed = await friendMatchApi.snapshot(room.id);
        if (current.current?.id === room.id) accept(refreshed);
      } catch { /* Original command error remains visible. */ }
      return false;
    } finally {
      if (current.current?.id === room.id) { inFlight.current = false; setBusy(false); }
    }
  }, [accept]);

  const act = useCallback(async <K extends FriendActionType>(type: K, payload: FriendActionPayloads[K]): Promise<boolean> => {
    if (!current.current || pending.current || inFlight.current) return false;
    pending.current = { action_id: friendRequestId(), expected_version: current.current.version, type, payload } as FriendAction;
    return sendPending();
  }, [sendPending]);

  const refresh = useCallback(async () => {
    const room = current.current;
    if (!room) { setReload(value => value + 1); return; }
    try {
      const next = await friendMatchApi.snapshot(room.id);
      if (current.current?.id === room.id) { accept(next); setError(''); }
    } catch (cause) {
      if (current.current?.id === room.id) setError(friendError(cause, messages.current.fallbackError));
    }
  }, [accept]);

  return { snapshot, invite, loading, error, busy, retryable, connection, accept, act, retry: sendPending, refresh };
}
