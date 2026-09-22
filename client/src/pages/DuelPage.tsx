import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  Clock3,
  Eye,
  EyeOff,
  Users,
  HelpCircle,
  Zap,
  Dices,
  Clock,
  ChevronDown,
  ChevronUp,
  X,
  MessageSquare,
  Trophy,
} from 'lucide-react';
import { useFriendMatch } from '../hooks/useFriendMatch';
import { useAuthStore } from '../stores/authStore';
import { friendError, friendMatchApi, friendRequestId, uncertainFriendRequest } from '../services/friendMatchApi';
import type { FriendEntity, FriendMode, FriendSnapshot } from '../types/friendMatch';
import GuessInput from '../components/GuessInput';
import QuestionInput from '../components/QuestionInput';
import FriendDuelMap from '../components/friendDuel/FriendDuelMap';
import DuelHistory from '../components/friendDuel/DuelHistory';
import FriendQuestionModal from '../components/friendDuel/FriendQuestionModal';
import { duelButton, duelCopy, duelModes, duelPrimary } from '../components/friendDuel/copy';
import type { DuelCopy } from '../components/friendDuel/copy';

function normalizeEntityName(value: string) {
  return value.trim().toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/ł/g, 'l');
}

function Countdown({ deadline, copy }: { deadline: string; copy: DuelCopy }) {
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 500);
    return () => window.clearInterval(timer);
  }, []);
  const seconds = Math.max(0, Math.ceil((Date.parse(deadline) - now) / 1000));
  const isUrgent = seconds <= 10;

  return (
    <div
      className={`flex items-center gap-1.5 px-2.5 text-xs font-mono font-semibold ${
        isUrgent
          ? 'bg-amber-950/60 text-amber-200 animate-pulse'
          : 'text-sand-100'
      }`}
    >
      <Clock3 size={13} className={isUrgent ? 'text-amber-400' : 'text-zinc-400'} aria-hidden="true" />
      <span className="sr-only">{copy.deadline}</span>
      <span role="timer" className="tabular-nums">
        {seconds > 0 ? `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}` : copy.expired}
      </span>
    </div>
  );
}

function InviteLink({ code, copy }: { code: string; copy: DuelCopy }) {
  const [notice, setNotice] = useState('');
  const link = `${window.location.origin}/duel/${encodeURIComponent(code)}`;

  return (
    <section className="rounded-sm border border-white/15 bg-obsidian-900/90 p-4 shadow-xl backdrop-blur-md max-w-sm" aria-label={copy.invite}>
      <h2 className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.16em] text-sand-100">
        <Users size={14} className="text-emerald-400" />
        <span>{copy.invite}</span>
      </h2>
      <label className="sr-only" htmlFor="duel-invite-link">{copy.invite}</label>
      <input
        id="duel-invite-link"
        className="w-full my-2.5 rounded-sm border border-white/15 bg-obsidian-950 px-3 py-1.5 font-mono text-xs text-sand-100 select-all"
        value={link}
        readOnly
        onFocus={event => event.target.select()}
      />
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className="rounded-sm bg-emerald-400 hover:bg-emerald-300 px-3 py-1.5 font-mono text-[10px] font-bold uppercase tracking-wider text-obsidian-950 transition-colors cursor-pointer"
          onClick={() => {
            if (!navigator.clipboard) { setNotice(copy.copyFailed); return; }
            void navigator.clipboard.writeText(link).then(() => setNotice(copy.copied)).catch(() => setNotice(copy.copyFailed));
          }}
        >
          {copy.copy}
        </button>
        {typeof navigator.share === 'function' && (
          <button
            type="button"
            className="rounded-sm border border-white/15 bg-white/5 hover:bg-white/10 px-3 py-1.5 font-mono text-[10px] uppercase tracking-wider text-sand-100 transition-colors cursor-pointer"
            onClick={() => {
              void navigator.share({ title: copy.title, url: link }).catch(cause => {
                if (!(cause instanceof DOMException && cause.name === 'AbortError')) setNotice(copy.copyFailed);
              });
            }}
          >
            {copy.share}
          </button>
        )}
      </div>
      {notice && <p role="status" className="mt-2 text-xs text-emerald-300 font-medium">{notice}</p>}
      <p className="mt-2.5 text-[11px] leading-relaxed text-zinc-400">{copy.guest}</p>
    </section>
  );
}

function ResultsModal({
  snapshot,
  copy,
  busy,
  rematch,
  onClose,
}: {
  snapshot: FriendSnapshot;
  copy: DuelCopy;
  busy: boolean;
  rematch: () => void;
  onClose: () => void;
}) {
  const self = snapshot.players.find(player => player.id === snapshot.you);
  const opponent = snapshot.players.find(player => player.id !== snapshot.you);
  const outcome = snapshot.result === 'draw'
    ? copy.draw
    : snapshot.winner_id
    ? snapshot.winner_id === snapshot.you
      ? copy.won
      : copy.lost
    : snapshot.result === 'interrupted'
    ? copy.interrupted
    : copy.cancelled;

  const isWinner = snapshot.winner_id === snapshot.you;

  return (
    <div
      role="dialog"
      aria-modal="true"
      onClick={onClose}
      className="fixed inset-0 z-[1200] flex items-center justify-center p-4 bg-black/70 backdrop-blur-md animate-in fade-in duration-150 cursor-pointer"
    >
      <div
        className="relative w-full max-w-lg max-h-[90vh] overflow-y-auto rounded-sm border border-white/20 bg-obsidian-950/95 p-5 sm:p-6 shadow-2xl cursor-default"
        onClick={e => e.stopPropagation()}
      >
        <button
          type="button"
          onClick={onClose}
          className="absolute right-4 top-4 rounded-sm border border-white/10 bg-white/5 p-1.5 text-zinc-400 hover:bg-white/10 hover:text-sand-100 transition-colors cursor-pointer"
          title="Inspect Map"
          aria-label="Close modal and explore map"
        >
          <X size={15} />
        </button>

        <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-zinc-400">{copy.results}</p>
        <h2 className={`mt-1.5 text-2xl font-bold sm:text-3xl ${isWinner ? 'text-emerald-300' : 'text-sand-100'}`}>
          {outcome}
        </h2>

        <h3 className="mb-2 mt-5 font-mono text-[10px] uppercase tracking-[0.16em] text-zinc-400">{copy.reveals}</h3>
        <ul className="space-y-2 rounded-sm border border-white/10 bg-black/30 p-3">
          {snapshot.reveals?.map(reveal => {
            const playerName = snapshot.players.find(p => p.id === reveal.player_id)?.name || 'Player';
            const isYou = reveal.player_id === snapshot.you;
            return (
              <li key={reveal.player_id} className="flex flex-wrap items-center justify-between gap-2 text-sm">
                <span className={`text-xs font-medium ${isYou ? 'text-emerald-400 font-mono' : 'text-blue-400 font-mono'}`}>
                  {playerName} {isYou ? `(${copy.you})` : ''}
                </span>
                <strong className="text-sand-100">{reveal.entity.name}</strong>
              </li>
            );
          })}
        </ul>

        {snapshot.session_score && (
          <p className="mt-3 font-mono text-xs text-zinc-400">
            {copy.wins}:{' '}
            {snapshot.session_score
              .map(score => `${snapshot.players.find(p => p.id === score.player_id)?.name || '—'}: ${score.wins}`)
              .join(' · ')}
            {snapshot.draw_count !== undefined && ` · ${copy.draws}: ${snapshot.draw_count}`}
          </p>
        )}

        <div className="mt-5 flex flex-wrap items-center gap-3">
          {snapshot.rematch_code ? (
            <Link className="rounded-sm bg-emerald-400 hover:bg-emerald-300 px-4 py-2 font-mono text-xs font-bold uppercase tracking-wider text-obsidian-950 transition-colors" to={`/duel/${encodeURIComponent(snapshot.rematch_code)}`}>
              {copy.rematchOpen}
            </Link>
          ) : snapshot.players.length < 2 ? null : self?.rematch_ready ? (
            <p role="status" className="text-sm font-medium text-emerald-300 font-mono">{copy.rematchWaiting}</p>
          ) : (
            <>
              {opponent?.rematch_ready && <p className="w-full text-sm font-medium text-emerald-300 font-mono">{copy.rematchReceived}</p>}
              <button type="button" className="rounded-sm bg-emerald-400 hover:bg-emerald-300 px-4 py-2 font-mono text-xs font-bold uppercase tracking-wider text-obsidian-950 transition-colors cursor-pointer" disabled={busy} onClick={rematch}>
                {copy.rematch}
              </button>
            </>
          )}
          <Link className="rounded-sm border border-white/15 bg-white/5 hover:bg-white/10 px-4 py-2 font-mono text-xs uppercase tracking-wider text-sand-100 transition-colors" to="/friends">{copy.newDuel}</Link>

          <button
            type="button"
            className="flex items-center gap-1.5 px-4 py-2 font-mono text-xs uppercase tracking-wider text-zinc-300 hover:text-white rounded-sm border border-white/10 hover:bg-white/5 transition-colors cursor-pointer ml-auto"
            onClick={onClose}
          >
            <Eye size={13} />
            <span>Explore Map</span>
          </button>
        </div>
      </div>
    </div>
  );
}

function DuelRoom({ code }: { code?: string }) {
  const { i18n, t } = useTranslation();
  const copy = duelCopy(i18n.resolvedLanguage || i18n.language);
  const navigate = useNavigate();

  const { user, isAuthenticated, isLoading: authLoading } = useAuthStore();
  const accountName = isAuthenticated && user?.username ? user.username : '';
  const [guestName, setGuestName] = useState(() => localStorage.getItem('duel_guest_name') || '');
  const name = accountName || guestName;

  const room = useFriendMatch(code, copy.error, copy.stale);
  const { snapshot } = room;

  const [mode, setMode] = useState<FriendMode>(() => {
    const requested = new URLSearchParams(window.location.search).get('mode');
    return duelModes.find(item => item === requested) || 'countrydle';
  });

  const [entryBusy, setEntryBusy] = useState(false);
  const [entryError, setEntryError] = useState('');
  const [entryUncertain, setEntryUncertain] = useState(false);
  const entryRequest = useRef<{ name: string; mode: FriendMode; request_id: string } | null>(null);
  const entryInFlight = useRef(false);
  const [modeDropdownOpen, setModeDropdownOpen] = useState(false);
  const modeDropdownRef = useRef<HTMLDivElement>(null);
  const [entities, setEntities] = useState<FriendEntity[]>([]);
  const [entitiesError, setEntitiesError] = useState('');
  const [entityReload, setEntityReload] = useState(0);
  const [entitiesLoading, setEntitiesLoading] = useState(false);
  const [showSecret, setShowSecret] = useState(false);
  const [activeActionTab, setActiveActionTab] = useState<'question' | 'guess'>('question');

  // Desktop HUD & Chat state
  const [isHistoryOpen, setIsHistoryOpen] = useState(true);
  const [isResultDismissed, setIsResultDismissed] = useState(false);
  const [rulesOpen, setRulesOpen] = useState(false);

  const answerPanel = useRef<HTMLDivElement>(null);
  const activeMode = snapshot?.mode;
  const viewMode = activeMode || room.invite?.mode || mode;

  useEffect(() => {
    if (!activeMode) return;
    let alive = true;
    void (async () => {
      setEntitiesLoading(true);
      setEntitiesError('');
      try {
        const list = await friendMatchApi.entities(activeMode);
        if (alive) setEntities(list);
      } catch (cause) {
        if (alive) setEntitiesError(friendError(cause, copy.error));
      } finally {
        if (alive) setEntitiesLoading(false);
      }
    })();
    return () => { alive = false; };
  }, [activeMode, entityReload, copy.error]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (modeDropdownRef.current && !modeDropdownRef.current.contains(event.target as Node)) {
        setModeDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const enter = async () => {
    if (authLoading || entryInFlight.current || (!entryRequest.current && !name.trim())) return;
    entryInFlight.current = true;
    setEntryBusy(true);
    setEntryError('');
    const request = entryRequest.current ?? { name: name.trim(), mode, request_id: friendRequestId() };
    entryRequest.current = request;
    try {
      const joined = code
        ? await friendMatchApi.join(code, { name: request.name, request_id: request.request_id })
        : await friendMatchApi.create(request);
      entryRequest.current = null;
      setEntryUncertain(false);
      room.accept(joined);
      if (!code) navigate(`/duel/${encodeURIComponent(joined.invite_code)}`);
    } catch (cause) {
      const uncertain = uncertainFriendRequest(cause);
      if (!uncertain) entryRequest.current = null;
      setEntryUncertain(uncertain);
      setEntryError(friendError(cause, copy.error));
      if (code && !uncertain) void room.refresh();
    } finally {
      entryInFlight.current = false;
      setEntryBusy(false);
    }
  };

  const busy = room.busy || room.retryable;
  const self = snapshot?.players.find(p => p.id === snapshot.you);
  const opponent = snapshot?.players.find(p => p.id !== snapshot.you);

  const myTurn = snapshot?.status === 'active' && snapshot.active_player_id === snapshot.you;
  const pendingQuestion = snapshot?.history.find(item => item.id === snapshot.pending_question_id);
  const mustAnswer = snapshot?.status === 'active' && snapshot.phase === 'answering' && pendingQuestion?.subject_id === snapshot.you;
  const advice = snapshot?.guidance.find(item => item.question_id === snapshot.pending_question_id);
  const finished = snapshot?.status === 'finished';
  const revealedOpponent = finished ? snapshot.reveals?.find(item => item.player_id !== snapshot.you)?.entity.name : undefined;
  const canGuess = myTurn && (snapshot?.phase === 'thinking' || snapshot?.phase === 'reply');
  const isMyQuestionTurn = Boolean(
    snapshot?.status === 'active' &&
    snapshot?.phase === 'thinking' &&
    snapshot?.active_player_id === snapshot?.you
  );

  // Reactive timer for question turn gradient border
  const [turnNow, setTurnNow] = useState(Date.now);
  useEffect(() => {
    if (!snapshot?.deadline || !isMyQuestionTurn) return;
    const interval = window.setInterval(() => setTurnNow(Date.now()), 250);
    return () => clearInterval(interval);
  }, [snapshot?.deadline, isMyQuestionTurn]);

  const turnSecondsLeft = snapshot?.deadline
    ? Math.max(0, Math.ceil((Date.parse(snapshot.deadline) - turnNow) / 1000))
    : 120;

  const turnBorderPhase: 'red' | 'yellow' | 'green' =
    turnSecondsLeft <= 10 ? 'red' : turnSecondsLeft <= 30 ? 'yellow' : 'green';
  const topGradient =
    turnBorderPhase === 'red'
      ? 'from-rose-500/35 via-rose-600/12 to-transparent'
      : turnBorderPhase === 'yellow'
      ? 'from-amber-400/30 via-amber-500/10 to-transparent'
      : 'from-emerald-400/25 via-emerald-500/08 to-transparent';

  const bottomGradient = topGradient;
  const leftGradient = topGradient;
  const rightGradient = topGradient;

  const borderGlow =
    turnBorderPhase === 'red'
      ? 'shadow-[inset_0_0_50px_rgba(244,63,94,0.45),inset_0_0_15px_rgba(239,68,68,0.5)] animate-pulse'
      : turnBorderPhase === 'yellow'
      ? 'shadow-[inset_0_0_40px_rgba(245,158,11,0.35),inset_0_0_12px_rgba(251,191,36,0.4)]'
      : 'shadow-[inset_0_0_35px_rgba(16,185,129,0.3),inset_0_0_10px_rgba(52,211,153,0.35)]';
  // Auto-switch action tab if reply phase requires guessing
  useEffect(() => {
    if (snapshot?.phase === 'reply') {
      setActiveActionTab('guess');
    }
  }, [snapshot?.phase]);

  // SCENARIO A: Lobby Entry (no snapshot yet) -> Clean centered card layout
  if (!snapshot) {
    return (
      <div className="relative h-[calc(100vh-3.5rem)] w-full overflow-hidden bg-obsidian-950 font-sans select-none">
        {/* Full-Canvas Background Map (previews selected mode!) */}
        <div className="absolute inset-0 z-0 h-full w-full">
          <FriendDuelMap
            mode={viewMode}
            matchKey={`entry-preview-${viewMode}`}
            finished={false}
            className="h-full w-full rounded-none border-0 shadow-none"
            isLobby={true}
          />
        </div>

        {/* Top Status HUD Bar */}
        <div className="pointer-events-none absolute left-1/2 top-3 z-[1000] -translate-x-1/2 px-2">
          <div className="pointer-events-auto flex h-8 items-stretch divide-x divide-white/10 rounded-sm border border-white/15 bg-obsidian-900/85 shadow-lg backdrop-blur-md overflow-hidden text-xs font-mono">
            <div className="flex items-center gap-2 px-3 text-[10px] uppercase tracking-[0.16em] text-zinc-400">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
              <span>{copy[`play_${viewMode}`]}</span>
              <span className="font-semibold text-sand-100">Multiplayer</span>
            </div>
            <button
              type="button"
              onClick={() => setRulesOpen(true)}
              className="flex items-center gap-1.5 px-2.5 text-zinc-400 hover:text-sand-100 hover:bg-white/5 transition-colors text-[10px] uppercase tracking-[0.16em] cursor-pointer whitespace-nowrap"
              title={copy.rulesTitle}
            >
              <HelpCircle size={13} className="text-emerald-400" />
              <span>Rules</span>
            </button>
          </div>
        </div>
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-[1200] flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-in fade-in duration-150"
        >
          <div className="relative z-10 w-full max-w-md rounded-sm border border-white/20 bg-obsidian-950/95 p-6 shadow-2xl space-y-4">
            <div>
              <p className="mb-1 font-mono text-[10px] uppercase tracking-[0.16em] text-emerald-400">
                {copy.multiplayer}
              </p>
              <h2 className="text-xl font-bold text-sand-100">
                {code ? copy.join : copy.create}
              </h2>
              <p className="mt-1 text-xs leading-relaxed text-zinc-400">{copy.subtitle}</p>
            </div>

            {room.invite && (
              <div className="rounded-sm border border-emerald-500/30 bg-emerald-950/20 p-2.5 font-mono text-xs text-emerald-300">
                <span className="font-semibold text-zinc-300">Players: </span>
                {room.invite.players.map(p => p.name).join(' / ')}
              </div>
            )}

            {code && !room.invite ? (
              <button type="button" className={duelButton} onClick={() => { void room.refresh(); }}>
                {copy.refresh}
              </button>
            ) : code && room.invite && (room.invite.full || room.invite.status !== 'lobby') ? (
              <div className="space-y-4">
                <div className="rounded-sm border border-amber-500/40 bg-amber-950/20 p-3 text-xs text-amber-200">
                  <p className="font-semibold text-amber-300 mb-1">
                    {room.invite.status === 'finished' ? copy.ended : copy.full}
                  </p>
                </div>
                <Link to="/friends" className={`${duelPrimary} block w-full text-center rounded-sm`}>
                  {copy.newDuel}
                </Link>
              </div>
            ) : (
              <form
                className="space-y-4"
                onSubmit={event => {
                  event.preventDefault();
                  void enter();
                }}
              >
                <div>
                  <label className="mb-1.5 block font-mono text-[10px] uppercase tracking-[0.16em] text-zinc-300" htmlFor="duel-name">
                    {accountName ? t('auth.username') : copy.name}
                  </label>
                  <input
                    id="duel-name"
                    className="w-full rounded-sm border border-white/15 bg-obsidian-950 px-3 py-2 text-sm text-sand-100 placeholder:text-zinc-600 focus:border-emerald-500/70 focus:outline-none"
                    autoComplete="nickname"
                    value={name}
                    maxLength={40}
                    required
                    readOnly={Boolean(accountName)}
                    disabled={authLoading || entryBusy || entryUncertain}
                    onChange={event => setGuestName(event.target.value)}
                  />
                </div>

                {!code && (
                  <div className="relative" ref={modeDropdownRef}>
                    <label className="mb-1.5 block font-mono text-[10px] uppercase tracking-[0.16em] text-zinc-300" htmlFor="duel-mode-btn">
                      {copy.mode}
                    </label>
                    <button
                      id="duel-mode-btn"
                      type="button"
                      className="w-full rounded-sm border border-white/15 bg-obsidian-950 px-3 py-2 text-sm text-sand-100 flex items-center justify-between text-left cursor-pointer"
                      disabled={entryBusy || entryUncertain}
                      onClick={() => setModeDropdownOpen(open => !open)}
                      aria-haspopup="listbox"
                      aria-expanded={modeDropdownOpen}
                    >
                      <span className="truncate">{copy[mode]}</span>
                      <ChevronDown size={14} className={`text-zinc-400 transition-transform ${modeDropdownOpen ? 'rotate-180' : ''}`} />
                    </button>

                    {modeDropdownOpen && (
                      <div
                        className="absolute left-0 right-0 top-full mt-1 max-h-72 overflow-y-auto divide-y divide-white/10 rounded-sm border border-white/15 bg-obsidian-900 shadow-2xl z-50 p-2 space-y-2"
                        role="listbox"
                      >
                        <div>
                          <span className="block px-2 py-1 font-mono text-[10px] uppercase tracking-wider text-zinc-400">
                            {copy.groupGlobal}
                          </span>
                          <div className="flex flex-col gap-1">
                            {(['countrydle'] as const).map(item => (
                              <button
                                key={item}
                                type="button"
                                role="option"
                                aria-selected={mode === item}
                                className={`flex items-center justify-between gap-1.5 rounded-sm px-2.5 py-1.5 text-xs text-left transition-colors cursor-pointer ${
                                  mode === item ? 'bg-emerald-500/20 text-emerald-300 font-medium' : 'text-sand-100 hover:bg-white/5 hover:text-white'
                                }`}
                                onClick={() => {
                                  setMode(item);
                                  setModeDropdownOpen(false);
                                }}
                              >
                                <span>{copy[item]}</span>
                                <span className="text-[10px] font-mono text-zinc-400">195</span>
                              </button>
                            ))}
                          </div>
                        </div>
                        <div className="pt-2">
                          <span className="block px-2 py-1 font-mono text-[10px] uppercase tracking-wider text-zinc-400">
                            {copy.groupContinents}
                          </span>
                          <div className="grid grid-cols-2 gap-1">
                            {([
                              { id: 'europe', badge: '47' },
                              { id: 'asia', badge: '47' },
                              { id: 'africa', badge: '54' },
                              { id: 'americas', badge: '35' },
                            ] as const).map(item => (
                              <button
                                key={item.id}
                                type="button"
                                role="option"
                                aria-selected={mode === item.id}
                                className={`flex items-center justify-between gap-1.5 rounded-sm px-2.5 py-1.5 text-xs text-left transition-colors cursor-pointer ${
                                  mode === item.id ? 'bg-emerald-500/20 text-emerald-300 font-medium' : 'text-sand-100 hover:bg-white/5 hover:text-white'
                                }`}
                                onClick={() => {
                                  setMode(item.id);
                                  setModeDropdownOpen(false);
                                }}
                              >
                                <span className="truncate">{copy[item.id]}</span>
                                <span className="shrink-0 text-[10px] font-mono text-zinc-400">{item.badge}</span>
                              </button>
                            ))}
                          </div>
                        </div>
                        <div className="pt-2">
                          <span className="block px-2 py-1 font-mono text-[10px] uppercase tracking-wider text-zinc-400">
                            {copy.groupRegional}
                          </span>
                          <div className="flex flex-col gap-1">
                            {([
                              { id: 'us_statedle', badge: '50' },
                              { id: 'wojewodztwodle', badge: '16' },
                              { id: 'powiatdle', badge: '380' },
                            ] as const).map(item => (
                              <button
                                key={item.id}
                                type="button"
                                role="option"
                                aria-selected={mode === item.id}
                                className={`flex items-center justify-between gap-1.5 rounded-sm px-2.5 py-1.5 text-xs text-left transition-colors cursor-pointer ${
                                  mode === item.id ? 'bg-emerald-500/20 text-emerald-300 font-medium' : 'text-sand-100 hover:bg-white/5 hover:text-white'
                                }`}
                                onClick={() => {
                                  setMode(item.id);
                                  setModeDropdownOpen(false);
                                }}
                              >
                                <span>{copy[item.id]}</span>
                                <span className="text-[10px] font-mono text-zinc-400">{item.badge}</span>
                              </button>
                            ))}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {entryError && <p role="alert" className="text-xs text-rose-400">{entryError}</p>}
                {entryUncertain && <p className="text-xs text-amber-200">{copy.uncertain}</p>}

                <button
                  type="submit"
                  className="w-full rounded-sm bg-emerald-400 hover:bg-emerald-300 py-2.5 font-mono text-xs font-bold uppercase tracking-wider text-obsidian-950 transition-colors cursor-pointer disabled:opacity-40"
                  disabled={authLoading || entryBusy || !name.trim()}
                >
                  {entryUncertain ? copy.retry : code ? copy.join : copy.create}
                </button>
              </form>
            )}
          </div>
        </div>

        {/* Rules Modal */}
        {rulesOpen && (
          <div
            role="dialog"
            aria-modal="true"
            onClick={() => setRulesOpen(false)}
            className="fixed inset-0 z-[1300] flex items-center justify-center p-4 bg-black/70 backdrop-blur-md animate-in fade-in duration-150 cursor-pointer"
          >
            <div
              className="relative w-full max-w-md rounded-sm border border-white/20 bg-obsidian-950/95 p-5 shadow-2xl space-y-3 cursor-default"
              onClick={e => e.stopPropagation()}
            >
              <div className="flex items-center justify-between border-b border-white/10 pb-2">
                <h3 className="font-mono text-xs uppercase tracking-[0.16em] text-emerald-400 font-semibold">
                  {copy.rulesTitle}
                </h3>
                <button
                  type="button"
                  onClick={() => setRulesOpen(false)}
                  className="text-zinc-400 hover:text-white cursor-pointer"
                >
                  <X size={15} />
                </button>
              </div>
              <p className="text-xs leading-relaxed text-zinc-300">{copy.rules}</p>
              <p className="text-xs leading-relaxed text-zinc-400">{copy.timeoutRules}</p>
            </div>
          </div>
        )}
      </div>
    );
  }

  // SCENARIO B: Active or Lobby Match -> Full Canvas Desktop HUD Redesign
  return (
    <div className="relative h-[calc(100vh-3.5rem)] w-full overflow-hidden bg-obsidian-950 font-sans select-none">
      {/* 1. Full-Canvas Duel Map */}
      <div className="absolute inset-0 h-full w-full">
        <FriendDuelMap
          mode={viewMode}
          matchKey={snapshot.id || `preview-${viewMode}`}
          finished={Boolean(finished)}
          revealedEntityName={revealedOpponent}
          className="h-full w-full rounded-none border-0 shadow-none"
          isLobby={snapshot.status === 'lobby'}
          selectedSecretName={snapshot.own_secret?.name}
          onEntitySelect={(clickedName) => {
            if (snapshot.status === 'lobby' && !self?.ready) {
              const norm = normalizeEntityName(clickedName);
              const match = entities.find(e => normalizeEntityName(e.name) === norm);
              if (match) {
                void room.act('select_secret', { entity_id: match.id });
              }
            }
          }}
        />
      </div>

      {/* 1b. Map Question Turn Ambient Shadow Indicator (Pure Vignette & Rich Alpha, No Hard Border) */}
      {isMyQuestionTurn && (
        <div className={`pointer-events-none absolute inset-0 z-[500] transition-all duration-500 ${turnBorderPhase === 'red' ? 'animate-pulse' : ''}`}>
          <div className={`absolute inset-0 pointer-events-none transition-all duration-500 ${borderGlow}`} />

          {/* 4-Sided Inward Alpha Gradients (Subtle, non-distracting rim glow) */}
          <div className={`absolute inset-x-0 top-0 h-7 sm:h-10 bg-gradient-to-b ${topGradient} transition-all duration-500 pointer-events-none`} />
          <div className={`absolute inset-x-0 bottom-0 h-7 sm:h-10 bg-gradient-to-t ${bottomGradient} transition-all duration-500 pointer-events-none`} />
          <div className={`absolute inset-y-0 left-0 w-7 sm:w-10 bg-gradient-to-r ${leftGradient} transition-all duration-500 pointer-events-none`} />
          <div className={`absolute inset-y-0 right-0 w-7 sm:w-10 bg-gradient-to-l ${rightGradient} transition-all duration-500 pointer-events-none`} />
        </div>
      )}
      {/* 2. Top Unified Status HUD Strip */}
      <div className="pointer-events-none absolute left-1/2 top-3 z-[1000] -translate-x-1/2 px-2">
        <div className="pointer-events-auto flex h-8 items-stretch divide-x divide-white/10 rounded-sm border border-white/15 bg-obsidian-900/85 shadow-lg backdrop-blur-md overflow-hidden text-xs font-mono">
          {/* Brand & Mode */}
          <div className="flex items-center gap-2 px-3 text-[10px] uppercase tracking-[0.16em] text-zinc-400">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
            <span className="font-semibold text-sand-100">{copy[`play_${viewMode}`]}</span>
            {snapshot.status === 'active' && (
              <span className="text-emerald-400 font-bold">Turn {snapshot.turn}</span>
            )}
          </div>

          {/* Self status */}
          <div className="flex items-center gap-1.5 px-3">
            <span className="text-[10px] uppercase tracking-[0.16em] text-zinc-400">{self?.name || copy.you}:</span>
            <span className={`font-semibold ${myTurn && !finished ? 'text-emerald-400' : 'text-sand-100'}`}>
              {snapshot.status === 'lobby'
                ? self?.ready ? copy.ready : copy.notReady
                : `Q:${self?.question_count ?? 0} G:${self?.guess_count ?? 0}`}
            </span>
          </div>

          {/* Opponent status */}
          <div className="flex items-center gap-1.5 px-3">
            <span className="text-[10px] uppercase tracking-[0.16em] text-zinc-400">{opponent?.name || 'Friend'}:</span>
            <span className={`font-semibold ${!myTurn && snapshot.status === 'active' && !finished ? 'text-blue-400' : 'text-zinc-300'}`}>
              {opponent
                ? snapshot.status === 'lobby'
                  ? opponent.ready ? copy.ready : copy.notReady
                  : `Q:${opponent.question_count ?? 0} G:${opponent.guess_count ?? 0}`
                : copy.waitingFriend}
            </span>
          </div>

          {/* Countdown timer */}
          {snapshot.deadline && !finished && (
            <Countdown deadline={snapshot.deadline} copy={copy} />
          )}

          {/* Rules dialog trigger */}
          <button
            type="button"
            onClick={() => setRulesOpen(true)}
            className="flex items-center gap-1.5 px-2.5 text-zinc-400 hover:text-sand-100 hover:bg-white/5 transition-colors text-[10px] uppercase tracking-[0.16em] cursor-pointer whitespace-nowrap"
            title={copy.rulesTitle}
          >
            <HelpCircle size={13} className="text-emerald-400" />
            <span className="hidden sm:inline">Rules</span>
          </button>

          {/* Result modal reopen button */}
          {finished && (
            <button
              type="button"
              onClick={() => setIsResultDismissed(false)}
              className="flex items-center gap-1.5 bg-emerald-500/20 px-3 text-[10px] font-bold uppercase tracking-[0.16em] text-emerald-300 hover:bg-emerald-500/30 transition-colors cursor-pointer"
            >
              <Trophy size={13} />
              <span>Result</span>
            </button>
          )}
        </div>
      </div>


      {/* Entity Load Error Banner */}
      {snapshot && (entitiesError || (!entitiesLoading && !entities.length)) && !finished && (
        <div role="alert" className="pointer-events-none absolute top-20 left-1/2 -translate-x-1/2 z-[1000] px-4 w-full max-w-md">
          <div className="pointer-events-auto rounded-sm border border-amber-400/40 p-3 text-xs text-amber-200 bg-amber-950/80 backdrop-blur-md flex items-center justify-between gap-3 shadow-xl font-mono">
            <p>{entitiesError || copy.noEntities}</p>
            <button
              type="button"
              className="rounded-sm border border-white/10 px-2 py-1 text-xs text-zinc-300 hover:text-white hover:bg-white/5 transition-colors cursor-pointer shrink-0"
              onClick={() => setEntityReload(value => value + 1)}
            >
              {copy.refresh}
            </button>
          </div>
        </div>
      )}

      {/* 3. Unified Deduction & Duel History Overlay (Left Side on Map) */}
      {/* 3. Unified Deduction & Duel History Overlay (Bottom Left Corner) */}
      {(snapshot.status === 'active' || finished) && (
        <div className="pointer-events-none absolute left-4 bottom-4 z-[1000] w-80 sm:w-96 max-w-[calc(100vw-2rem)]">
          {!isHistoryOpen ? (
            <button
              type="button"
              onClick={() => setIsHistoryOpen(true)}
              className="pointer-events-auto flex items-center gap-2 rounded-sm border border-white/15 bg-obsidian-900/85 px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.16em] text-sand-100 shadow-xl backdrop-blur-md hover:bg-obsidian-850 transition-colors cursor-pointer"
              aria-label="Expand Duel Chat"
            >
              <MessageSquare size={13} className="text-emerald-400" />
              <span>Duel chat</span>
              <span className="text-zinc-500">·</span>
              <span className="text-emerald-400 font-semibold">Turn {snapshot.turn}</span>
              <span className="text-zinc-500">·</span>
              <span className="text-sand-200">M: {snapshot.history.length}</span>
              <ChevronUp size={13} className="text-zinc-400 ml-0.5" />
            </button>
          ) : (
            <div className="pointer-events-auto flex h-[48vh] sm:h-[52vh] max-h-[48vh] sm:max-h-[52vh] flex-col overflow-hidden rounded-sm border border-white/15 bg-obsidian-900/85 shadow-2xl backdrop-blur-md transition-all">
              {/* Header */}
              <div className="flex items-center justify-between border-b border-white/10 bg-obsidian-950/70 px-3 py-2 shrink-0">
                <div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.16em] text-sand-100 font-semibold">
                  <MessageSquare size={13} className="text-emerald-400" />
                  <span>Deduction Chat</span>
                  <span className="text-zinc-500 font-normal">({snapshot.history.length})</span>
                </div>
                <button
                  type="button"
                  onClick={() => setIsHistoryOpen(false)}
                  className="rounded-sm p-1 text-zinc-400 hover:bg-white/10 hover:text-sand-100 transition-colors cursor-pointer"
                  title="Minimize chat"
                >
                  <ChevronDown size={14} />
                </button>
              </div>

              {/* Body */}
              <div className="flex-1 min-h-0 overflow-hidden flex flex-col">
                <DuelHistory
                  snapshot={snapshot}
                  copy={copy}
                  busy={busy}
                  correct={(item, answer, observedAiQuestionId) =>
                    room.act('correct_answer', {
                      question_id: item.id,
                      answer,
                      expected_revision: item.revision,
                      ...(observedAiQuestionId ? { observed_ai_question_id: observedAiQuestionId } : {}),
                    })
                  }
                />
              </div>
            </div>
          )}
        </div>
      )}

      {/* 3c. Friend Question Centered Modal */}
      {mustAnswer && pendingQuestion && (
        <FriendQuestionModal
          pendingQuestion={pendingQuestion}
          opponentName={opponent?.name || 'Friend'}
          ownSecret={snapshot.own_secret}
          deadline={snapshot.deadline}
          advice={advice}
          copy={copy}
          busy={busy}
          onAnswer={answer => {
            void room.act('answer', {
              question_id: pendingQuestion.id,
              answer,
              ...(advice?.status === 'completed' ? { observed_ai_question_id: pendingQuestion.id } : {}),
            });
          }}
        />
      )}

      {/* 3b. Lobby Secret Selector & Invite Overlay */}
      {snapshot.status === 'lobby' && (
        <>
          {/* Secret country selector floating bar */}
          <div className="pointer-events-none absolute top-14 left-1/2 -translate-x-1/2 z-[1000] px-2 w-full max-w-lg">
            <div className="pointer-events-auto flex items-center justify-between gap-3 rounded-sm border border-white/15 bg-obsidian-900/90 px-3.5 py-2 shadow-xl backdrop-blur-md">
              <div className="flex items-center gap-2 min-w-0">
                <EyeOff size={14} className="text-emerald-400 shrink-0" />
                <div className="truncate">
                  <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-zinc-400 block">Your Secret:</span>
                  <span className="font-semibold text-sand-100 text-xs truncate">
                    {snapshot.own_secret ? snapshot.own_secret.name : 'Click map to choose'}
                  </span>
                </div>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                {!self?.ready && (
                  <button
                    type="button"
                    onClick={() => { void room.act('randomize_secret', {}); }}
                    disabled={busy || entitiesLoading}
                    className="flex items-center gap-1.5 rounded-sm border border-white/15 bg-white/5 hover:bg-white/10 px-2.5 py-1.5 font-mono text-[10px] uppercase tracking-wider text-amber-300 transition-colors cursor-pointer"
                    title={copy.random}
                  >
                    <Dices size={13} />
                    <span>{copy.random}</span>
                  </button>
                )}

                <button
                  type="button"
                  onClick={() => { void room.act('ready', { ready: !self?.ready }); }}
                  disabled={busy || (!self?.ready && !snapshot.own_secret)}
                  className={`rounded-sm px-3 py-1.5 font-mono text-[10px] font-bold uppercase tracking-wider transition-colors cursor-pointer ${
                    self?.ready
                      ? 'bg-white/10 text-zinc-300 hover:bg-white/15 border border-white/15'
                      : 'bg-emerald-400 text-obsidian-950 hover:bg-emerald-300 disabled:opacity-40'
                  }`}
                >
                  {self?.ready ? copy.unready : copy.acceptAndReady}
                </button>
              </div>
            </div>
          </div>

          {/* Invite Link Card on right */}
          <div className="pointer-events-none absolute right-4 top-14 z-[990]">
            <div className="pointer-events-auto">
              <InviteLink code={snapshot.invite_code} copy={copy} />
            </div>
          </div>
        </>
      )}

      {/* 4. Own Secret Viewing Pill (Top Right on Map during active duel) */}
      {snapshot.status === 'active' && snapshot.own_secret && (
        <div className="pointer-events-none absolute right-3 top-3 z-[1000]">
          <div className="pointer-events-auto flex items-center gap-2 rounded-sm border border-white/10 bg-obsidian-900/80 px-2.5 py-1 backdrop-blur-md shadow text-xs font-mono">
            <span className="text-[10px] uppercase tracking-[0.16em] text-zinc-400">{copy.secret}:</span>
            <span className="font-semibold text-emerald-300 text-xs">
              {showSecret ? snapshot.own_secret.name : '••••••••'}
            </span>
            <button
              type="button"
              className="text-zinc-400 hover:text-sand-100 p-0.5 cursor-pointer ml-1"
              aria-label={showSecret ? copy.hideSecret : copy.showSecret}
              onClick={() => setShowSecret(!showSecret)}
            >
              {showSecret ? <EyeOff size={13} /> : <Eye size={13} />}
            </button>
          </div>
        </div>
      )}

      {/* 5. Floating Bottom Action Dock */}
      {snapshot.status === 'active' && (
        <div className="pointer-events-none absolute bottom-4 left-1/2 z-[990] w-full max-w-md -translate-x-1/2 px-3">
          <div className="pointer-events-auto flex flex-col gap-2 rounded-sm border border-white/15 bg-obsidian-900/85 p-3 shadow-2xl backdrop-blur-md transition-all">
            {/* Case A: Must Answer Opponent's Question */}
            {mustAnswer && pendingQuestion ? (
              <div ref={answerPanel} className="flex items-center justify-between gap-3 px-2 py-1">
                <div className="flex items-center gap-2 font-mono text-[11px] text-amber-300">
                  <Zap size={14} className="text-amber-400 animate-pulse" />
                  <span>Question received — choose answer in modal</span>
                </div>
              </div>
            ) : myTurn ? (
              /* Case B: Your Turn to Ask Question or Make Guess */
              <>
                <div className="flex items-center justify-between border-b border-white/10 mb-1 pb-1">
                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      onClick={() => setActiveActionTab('question')}
                      disabled={snapshot.phase === 'reply'}
                      className={`flex items-center gap-1.5 px-3 py-1 font-mono text-[10px] uppercase tracking-[0.16em] transition-colors cursor-pointer rounded-sm ${
                        activeActionTab === 'question'
                          ? 'border-b-2 border-emerald-400 text-sand-100 font-semibold bg-white/5'
                          : 'text-zinc-400 hover:text-sand-100 hover:bg-white/5 disabled:opacity-40'
                      }`}
                    >
                      <span>Ask question</span>
                    </button>

                    <button
                      type="button"
                      onClick={() => setActiveActionTab('guess')}
                      className={`flex items-center gap-1.5 px-3 py-1 font-mono text-[10px] uppercase tracking-[0.16em] transition-colors cursor-pointer rounded-sm ${
                        activeActionTab === 'guess'
                          ? 'border-b-2 border-emerald-400 text-sand-100 font-semibold bg-white/5'
                          : 'text-zinc-400 hover:text-sand-100 hover:bg-white/5'
                      }`}
                    >
                      <span>Make guess</span>
                    </button>
                  </div>

                  {canGuess && (
                    <button
                      type="button"
                      className="font-mono text-[10px] uppercase tracking-wider text-zinc-400 hover:text-amber-300 disabled:opacity-40 cursor-pointer"
                      disabled={busy}
                      onClick={() => { void room.act('pass', {}); }}
                    >
                      {copy.pass}
                    </button>
                  )}
                </div>

                <div className="pt-0.5">
                  {activeActionTab === 'question' ? (
                    <QuestionInput
                      onAsk={question => room.act('ask', { question: question.trim() })}
                      isLoading={busy}
                      disabled={!myTurn || snapshot.phase !== 'thinking'}
                      placeholder={copy.questionPlaceholder}
                      minLength={3}
                      maxLength={500}
                    />
                  ) : (
                    <GuessInput
                      dropup={true}
                      countries={entities}
                      onGuess={id => room.act('guess', { entity_id: id })}
                      isLoading={busy || entitiesLoading}
                      disabled={!canGuess}
                      placeholder={copy.search}
                      noMatchesLabel={copy.noMatches}
                    />
                  )}
                </div>
              </>
            ) : (
              /* Case C: Opponent's turn */
              <div className="flex items-center justify-between gap-3 px-2 py-1 font-mono text-xs">
                <div className="flex items-center gap-2 text-zinc-400">
                  <Clock size={14} className="text-zinc-500 animate-spin-slow" />
                  <span>
                    {copy.waiting}: {opponent?.name || 'Friend'} {snapshot.phase === 'answering' ? copy.awaitingAnswer : copy.theirTurn}
                  </span>
                </div>

                {/* Draw actions */}
                {snapshot.draw_offer_by === snapshot.you ? (
                  <span className="text-[10px] uppercase tracking-wider text-amber-300">{copy.drawOffered}</span>
                ) : snapshot.draw_offer_by ? (
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      className="rounded-sm bg-amber-400 text-obsidian-950 font-bold px-2 py-0.5 text-[10px] uppercase tracking-wider"
                      disabled={busy}
                      onClick={() => { void room.act('accept_draw', {}); }}
                    >
                      {copy.acceptDraw}
                    </button>
                    <button
                      type="button"
                      className="rounded-sm border border-white/10 px-2 py-0.5 text-[10px] uppercase tracking-wider text-zinc-300"
                      disabled={busy}
                      onClick={() => { void room.act('decline_draw', {}); }}
                    >
                      {copy.declineDraw}
                    </button>
                  </div>
                ) : (
                  <button
                    type="button"
                    className="text-[10px] uppercase tracking-wider text-zinc-500 hover:text-sand-100 cursor-pointer"
                    disabled={busy}
                    onClick={() => { void room.act('offer_draw', {}); }}
                  >
                    {copy.offerDraw}
                  </button>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* 6. Results Modal on Game Over */}
      {finished && !isResultDismissed && (
        <ResultsModal
          snapshot={snapshot}
          copy={copy}
          busy={busy}
          rematch={() => { void room.act('rematch', {}); }}
          onClose={() => setIsResultDismissed(true)}
        />
      )}

      {/* 7. Rules Modal */}
      {rulesOpen && (
        <div
          role="dialog"
          aria-modal="true"
          onClick={() => setRulesOpen(false)}
          className="fixed inset-0 z-[1300] flex items-center justify-center p-4 bg-black/70 backdrop-blur-md animate-in fade-in duration-150 cursor-pointer"
        >
          <div
            className="relative w-full max-w-md rounded-sm border border-white/20 bg-obsidian-950/95 p-5 shadow-2xl space-y-3 cursor-default"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-white/10 pb-2">
              <h3 className="font-mono text-xs uppercase tracking-[0.16em] text-emerald-400 font-semibold">
                {copy.rulesTitle}
              </h3>
              <button
                type="button"
                onClick={() => setRulesOpen(false)}
                className="text-zinc-400 hover:text-white cursor-pointer"
              >
                <X size={15} />
              </button>
            </div>
            <p className="text-xs leading-relaxed text-zinc-300">{copy.rules}</p>
            <p className="text-xs leading-relaxed text-zinc-400">{copy.timeoutRules}</p>
          </div>
        </div>
      )}
    </div>
  );
}

export default function DuelPage() {
  const { code } = useParams<{ code: string }>();
  return <DuelRoom key={code || 'create'} code={code} />;
}
