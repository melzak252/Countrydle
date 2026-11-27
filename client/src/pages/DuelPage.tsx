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
import GameActionComposer from '../components/GameActionComposer';
import BackToMapButton from '../components/BackToMapButton';
import FriendDuelMap from '../components/friendDuel/FriendDuelMap';
import DuelHistory from '../components/friendDuel/DuelHistory';
import FriendQuestionModal from '../components/friendDuel/FriendQuestionModal';
import { useIsMobile } from '../hooks/useMediaQuery';
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
          ? 'bg-amber-50 text-amber-900 animate-pulse'
          : 'text-app-text'
      }`}
    >
      <Clock3 size={13} className={isUrgent ? 'text-amber-800' : 'text-app-text-muted'} aria-hidden="true" />
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
    <section className="w-full max-w-sm rounded-sm border border-app-border/30 bg-app-surface-raised p-4 shadow-xl" aria-label={copy.invite}>
      <h2 className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.16em] text-app-text">
        <Users size={14} className="text-app-accent" />
        <span>{copy.invite}</span>
      </h2>
      <label className="sr-only" htmlFor="duel-invite-link">{copy.invite}</label>
      <textarea
        id="duel-invite-link"
        className="my-2.5 min-h-11 w-full resize-none break-all rounded-sm border border-app-border/30 bg-app-surface px-3 py-2 font-mono text-xs text-app-text select-all focus:border-app-focus focus:outline-none focus:ring-1 focus:ring-app-focus/30"
        rows={2}
        value={link}
        readOnly
        onFocus={event => event.target.select()}
      />
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className="min-h-11 rounded-sm bg-app-accent hover:bg-app-accent-hover px-3 py-2 font-mono text-[10px] font-bold uppercase tracking-wider text-white transition-colors cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-app-focus"
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
            className="min-h-11 rounded-sm border border-app-border/30 bg-app-surface-muted hover:bg-app-border/20 px-3 py-2 font-mono text-[10px] uppercase tracking-wider text-app-text-secondary transition-colors cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-app-focus"
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
      {notice && <p role="status" className="mt-2 text-xs text-app-accent font-medium">{notice}</p>}
      <p className="mt-2.5 text-[11px] leading-relaxed text-app-text-secondary">{copy.guest}</p>
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
      className="fixed inset-0 z-[1200] flex items-start justify-center overflow-y-auto p-3 pb-[calc(env(safe-area-inset-bottom)+0.75rem)] sm:items-center sm:px-4 sm:pt-4 sm:pb-[calc(env(safe-area-inset-bottom)+1rem)] bg-black/70 backdrop-blur-md animate-in fade-in duration-150 cursor-pointer"
    >
      <div
        className="relative my-auto w-full max-w-lg max-h-[calc(var(--app-height,100dvh)-1.5rem)] overflow-y-auto rounded-sm border border-app-border/30 bg-app-surface-raised p-4 sm:p-6 shadow-2xl cursor-default"
        onClick={e => e.stopPropagation()}
      >
        <button
          type="button"
          onClick={onClose}
          className="absolute right-3 top-3 max-md:min-h-11 max-md:min-w-11 flex items-center justify-center rounded-sm border border-app-border/30 bg-app-surface-muted p-1.5 text-app-text-secondary hover:bg-app-border/20 hover:text-app-text transition-colors cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-app-focus"
          title="Inspect Map"
          aria-label="Close modal and explore map"
        >
          <X size={15} />
        </button>

        <p className="font-mono text-xs text-app-text-secondary">{copy.results}</p>
        <h2 className={`mt-1.5 text-2xl font-bold sm:text-3xl ${isWinner ? 'text-app-accent' : 'text-app-text'}`}>
          {outcome}
        </h2>

        <h3 className="mb-2 mt-5 font-mono text-xs text-app-text-secondary">{copy.reveals}</h3>
        <ul className="space-y-2 rounded-sm border border-app-border/20 bg-app-surface-muted p-3">
          {snapshot.reveals?.map(reveal => {
            const playerName = snapshot.players.find(p => p.id === reveal.player_id)?.name || 'Player';
            const isYou = reveal.player_id === snapshot.you;
            return (
              <li key={reveal.player_id} className="flex flex-wrap items-center justify-between gap-2 text-sm">
                <span className={`text-xs font-medium ${isYou ? 'text-app-accent font-mono' : 'text-blue-700 font-mono'}`}>
                  {playerName} {isYou ? `(${copy.you})` : ''}
                </span>
                <strong className="text-app-text">{reveal.entity.name}</strong>
              </li>
            );
          })}
        </ul>

        {snapshot.session_score && (
          <p className="mt-3 font-mono text-xs text-app-text-secondary">
            {copy.wins}:{' '}
            {snapshot.session_score
              .map(score => `${snapshot.players.find(p => p.id === score.player_id)?.name || '—'}: ${score.wins}`)
              .join(' · ')}
            {snapshot.draw_count !== undefined && ` · ${copy.draws}: ${snapshot.draw_count}`}
          </p>
        )}

        <div className="mt-5 flex flex-wrap items-center gap-3">
          {snapshot.rematch_code ? (
            <Link className="max-md:min-h-11 inline-flex items-center rounded-sm bg-app-accent hover:bg-app-accent-hover px-4 py-2 font-mono text-xs font-semibold text-white transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-app-focus" to={`/duel/${encodeURIComponent(snapshot.rematch_code)}`}>
              {copy.rematchOpen}
            </Link>
          ) : snapshot.players.length < 2 ? null : self?.rematch_ready ? (
            <p role="status" className="text-sm font-medium text-app-accent font-mono">{copy.rematchWaiting}</p>
          ) : (
            <>
              {opponent?.rematch_ready && <p className="w-full text-sm font-medium text-app-accent font-mono">{copy.rematchReceived}</p>}
              <button type="button" className="max-md:min-h-11 rounded-sm bg-app-accent hover:bg-app-accent-hover px-4 py-2 font-mono text-xs font-semibold text-white transition-colors cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-app-focus" disabled={busy} onClick={rematch}>
                {copy.rematch}
              </button>
            </>
          )}
          <Link className="max-md:min-h-11 inline-flex items-center rounded-sm border border-app-border/30 bg-app-surface-muted hover:bg-app-border/20 px-4 py-2 font-mono text-xs text-app-text-secondary transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-app-focus" to="/friends">{copy.newDuel}</Link>

          <button
            type="button"
            className="ml-auto flex max-md:min-h-11 items-center gap-1.5 px-4 py-2 font-mono text-xs text-app-text-secondary hover:text-app-text rounded-sm border border-app-border/30 hover:bg-app-surface-muted transition-colors cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-app-focus"
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
  const { t } = useTranslation();
  const copy = duelCopy;
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
  const [entityPool, setEntityPool] = useState<{ mode: FriendMode; entities: FriendEntity[] } | null>(null);
  const [entitiesError, setEntitiesError] = useState('');
  const [entityReload, setEntityReload] = useState(0);
  const [entitiesLoading, setEntitiesLoading] = useState(false);
  const [showSecret, setShowSecret] = useState(false);
  const [activeActionTab, setActiveActionTab] = useState<'question' | 'guess'>('question');

  // Desktop & Mobile HUD & Chat state
  const isMobile = useIsMobile();
  const [isHistoryOpen, setIsHistoryOpen] = useState(true);
  const [isResultDismissed, setIsResultDismissed] = useState(false);
  const [rulesOpen, setRulesOpen] = useState(false);

  useEffect(() => {
    if (!isMobile) {
      setIsHistoryOpen(true);
    }
  }, [isMobile]);
  const answerPanel = useRef<HTMLDivElement>(null);
  const activeMode = snapshot?.mode;
  const viewMode = activeMode || room.invite?.mode || mode;
  const entities = entityPool?.mode === viewMode ? entityPool.entities : [];

  useEffect(() => {
    let alive = true;
    void (async () => {
      setEntitiesLoading(true);
      setEntitiesError('');
      try {
        const list = await friendMatchApi.entities(viewMode);
        if (alive) setEntityPool({ mode: viewMode, entities: list });
      } catch (cause) {
        if (alive) setEntitiesError(friendError(cause, copy.error));
      } finally {
        if (alive) setEntitiesLoading(false);
      }
    })();
    return () => { alive = false; };
  }, [viewMode, entityReload, copy.error]);


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
  const turnBorderColor =
    turnBorderPhase === 'red'
      ? 'border-rose-500/70'
      : turnBorderPhase === 'yellow'
      ? 'border-amber-400/60'
      : 'border-emerald-400/50';
  // Auto-switch action tab if reply phase requires guessing
  useEffect(() => {
    if (snapshot?.phase === 'reply') {
      setActiveActionTab('guess');
    }
  }, [snapshot?.phase]);

  // SCENARIO A: Lobby Entry (no snapshot yet) -> Clean centered card layout
  if (!snapshot) {
    return (
      <div className="relative flex-1 min-h-0 h-full w-full overflow-hidden bg-app-canvas font-sans select-none">
        {/* Full-Canvas Background Map (previews selected mode!) */}
        <div className="game-map-layer absolute inset-0 z-0 w-full">
          <FriendDuelMap
            eligibleCountries={entities}
            mode={viewMode}
            matchKey={`entry-preview-${viewMode}`}
            finished={false}
            className="h-full w-full rounded-none border-0 shadow-none"
            isLobby={true}
          />
        </div>

        {/* Top Status HUD Bar */}
        <div className="game-status-bar pointer-events-none absolute inset-x-0 top-0 z-[1200] w-full md:inset-x-auto md:left-1/2 md:top-3 md:z-[1000] md:w-auto md:-translate-x-1/2 md:px-2 md:max-w-full">
          <div className="pointer-events-auto flex h-11 w-full items-stretch border-b border-app-border/15 bg-app-surface/95 text-xs font-mono text-app-text md:h-8 md:w-auto md:divide-x md:divide-app-border/15 md:rounded-sm md:border md:border-app-border/20 md:bg-app-surface/95 md:shadow-sm">
            <div className="flex min-w-0 flex-1 items-center gap-1.5 px-2 text-[10px] uppercase tracking-wider text-app-text-secondary sm:gap-2 sm:px-3 sm:tracking-[0.16em] md:flex-none">
              <span className="h-1.5 w-1.5 rounded-full bg-app-accent animate-pulse" />
              <span className="max-w-[35vw] truncate">{copy[`play_${viewMode}`]}</span>
              <span className="hidden md:inline font-semibold text-app-text">Multiplayer</span>
            </div>
            <button
              type="button"
              onClick={() => setRulesOpen(true)}
              className="flex min-h-11 md:min-h-0 shrink-0 items-center gap-1.5 px-2.5 text-app-text-secondary hover:text-app-text hover:bg-app-surface-muted transition-colors text-[10px] uppercase tracking-wider cursor-pointer whitespace-nowrap sm:tracking-[0.16em]"
              title={copy.rulesTitle}
            >
              <HelpCircle size={13} className="text-app-accent" />
              <span className="md:hidden">{'Guide'}</span>
              <span className="hidden md:inline">{copy.rulesTitle}</span>
            </button>
          </div>
        </div>
        <div
          role="region"
          aria-labelledby="friend-entry-title"
          className="absolute inset-0 z-[1000] flex items-start justify-center overflow-y-auto p-3 pb-[calc(env(safe-area-inset-bottom)+0.75rem)] sm:items-center sm:px-4 sm:pt-4 sm:pb-[calc(env(safe-area-inset-bottom)+1rem)] bg-black/40 backdrop-blur-sm animate-in fade-in duration-150"
        >
          <div className="relative z-10 my-auto max-h-[calc(var(--app-height,100dvh)-1.5rem)] w-full max-w-md overflow-y-auto rounded-sm border border-app-border/30 bg-app-surface-raised p-4 shadow-2xl space-y-4 sm:p-6">
            <div>
              <p className="mb-1 font-mono text-[10px] uppercase tracking-[0.16em] text-app-accent">
                {copy.multiplayer}
              </p>
              <h2 id="friend-entry-title" className="text-xl font-bold text-app-text">
                {code ? copy.join : copy.create}
              </h2>
              <p className="mt-1 text-xs leading-relaxed text-app-text-secondary">{copy.subtitle}</p>
            </div>

            {room.invite && (
              <div className="rounded-sm border border-app-accent/30 bg-app-accent/10 p-2.5 font-mono text-xs text-app-accent">
                <span className="font-semibold text-app-text-secondary">Players: </span>
                {room.invite.players.map(p => p.name).join(' / ')}
              </div>
            )}

            {code && !room.invite ? (
              <button type="button" className={duelButton} onClick={() => { void room.refresh(); }}>
                {copy.refresh}
              </button>
            ) : code && room.invite && (room.invite.full || room.invite.status !== 'lobby') ? (
              <div className="space-y-4">
                <div className="rounded-sm border border-amber-700/25 bg-amber-50 p-3 text-xs text-amber-900">
                  <p className="font-semibold text-amber-900 mb-1">
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
                  <label className="mb-1.5 block font-mono text-[10px] uppercase tracking-[0.16em] text-app-text-secondary" htmlFor="duel-name">
                    {accountName ? t('auth.username') : copy.name}
                  </label>
                  <input
                    id="duel-name"
                    className="w-full rounded-sm border border-app-border/30 bg-app-surface px-3 py-2.5 text-base md:text-sm text-app-text placeholder:text-app-text-muted focus:border-app-focus focus:outline-none focus:ring-1 focus:ring-app-focus/30"
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
                  <div>
                    <label className="mb-1.5 block font-mono text-[10px] uppercase tracking-[0.16em] text-app-text-secondary" htmlFor="duel-mode">
                      {copy.mode}
                    </label>
                    <select
                      id="duel-mode"
                      className="min-h-11 w-full rounded-sm border border-app-border/30 bg-app-surface px-3 py-2 text-base md:text-sm text-app-text [color-scheme:light] focus:border-app-focus focus:outline-none focus:ring-1 focus:ring-app-focus/30"
                      value={mode}
                      disabled={entryBusy || entryUncertain}
                      onChange={event => setMode(event.target.value as FriendMode)}
                    >
                      <optgroup label={copy.groupGlobal}>
                        <option value="countrydle">{copy.countrydle} (195)</option>
                      </optgroup>
                      <optgroup label={copy.groupContinents}>
                        {([
                          { id: 'europe', badge: '47' },
                          { id: 'asia', badge: '46' },
                          { id: 'africa', badge: '54' },
                          { id: 'americas', badge: '35' },
                        ] as const).map(item => (
                          <option key={item.id} value={item.id}>{copy[item.id]} ({item.badge})</option>
                        ))}
                      </optgroup>
                      <optgroup label={copy.groupRegional}>
                        {([
                          { id: 'us_statedle', badge: '50' },
                          { id: 'wojewodztwodle', badge: '16' },
                          { id: 'powiatdle', badge: '380' },
                        ] as const).map(item => (
                          <option key={item.id} value={item.id}>{copy[item.id]} ({item.badge})</option>
                        ))}
                      </optgroup>
                    </select>
                  </div>
                )}

                {entryError && <p role="alert" className="text-xs text-rose-700">{entryError}</p>}
                {entryUncertain && <p className="text-xs text-amber-900">{copy.uncertain}</p>}

                <button
                  type="submit"
                  className="max-md:min-h-11 w-full rounded-sm bg-app-accent hover:bg-app-accent-hover py-2.5 font-mono text-xs font-bold uppercase tracking-wider text-white transition-colors cursor-pointer disabled:bg-app-surface-muted disabled:text-app-text-muted disabled:opacity-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-app-focus"
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
            className="fixed inset-0 z-[1300] flex items-start justify-center overflow-y-auto p-3 pb-[calc(env(safe-area-inset-bottom)+0.75rem)] sm:items-center sm:px-4 sm:pt-4 sm:pb-[calc(env(safe-area-inset-bottom)+1rem)] bg-black/70 backdrop-blur-md animate-in fade-in duration-150 cursor-pointer"
          >
            <div
              className="relative my-auto max-h-[calc(var(--app-height,100dvh)-1.5rem)] w-full max-w-md overflow-y-auto rounded-sm border border-app-border/30 bg-app-surface-raised p-4 shadow-2xl space-y-3 cursor-default sm:p-5"
              onClick={e => e.stopPropagation()}
            >
              <div className="flex items-center justify-between border-b border-app-border/20 pb-2">
                <h3 className="font-mono text-xs uppercase tracking-[0.16em] text-app-accent font-semibold">
                  {copy.rulesTitle}
                </h3>
                <button
                  type="button"
                  onClick={() => setRulesOpen(false)}
                  className="max-md:min-h-11 max-md:min-w-11 flex items-center justify-center text-app-text-secondary hover:text-app-text cursor-pointer"
                >
                  <X size={15} />
                </button>
              </div>
              <p className="text-xs leading-relaxed text-app-text-secondary">{copy.rules}</p>
              <p className="text-xs leading-relaxed text-app-text-muted">{copy.timeoutRules}</p>
            </div>
          </div>
        )}
      </div>
    );
  }

  // SCENARIO B: Active or Lobby Match -> Full Canvas Desktop HUD Redesign
  return (
    <div className={`relative flex-1 min-h-0 h-full w-full overflow-hidden bg-app-canvas font-sans select-none ${snapshot.status === 'active' ? 'duel-active' : ''} ${snapshot.status === 'lobby' ? 'max-md:[&_[role=toolbar]]:hidden' : ''}`}>
      {/* 1. Full-Canvas Duel Map */}
      <div className="game-map-layer absolute inset-0 w-full">
        <FriendDuelMap
          eligibleCountries={entities}
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

      {/* Question turn status border */}
      {isMyQuestionTurn && (
        <div className={`pointer-events-none absolute inset-0 z-[500] border-2 ${turnBorderColor}`} />
      )}
      {/* 2. Top Unified Status HUD Strip */}
      <div className="game-status-bar pointer-events-none absolute inset-x-0 top-0 z-[1200] w-full md:inset-x-auto md:left-1/2 md:top-3 md:z-[1000] md:w-auto md:-translate-x-1/2 md:px-2 md:max-w-full">
        <div className={`pointer-events-auto grid grid-cols-[auto_minmax(0,1fr)_auto] items-stretch border-b border-app-border/15 bg-app-surface/95 text-xs font-mono text-app-text md:flex md:h-8 md:divide-x md:divide-app-border/15 md:rounded-sm md:border md:border-app-border/20 md:bg-app-surface/95 md:shadow-sm ${snapshot.status === 'active' ? 'max-md:h-[5.5rem]' : 'max-md:h-11'} ${finished ? 'max-md:grid-cols-[auto_minmax(0,1fr)_auto_auto]' : ''}`}>
          {/* Brand & Mode */}
          <div className="hidden md:flex items-center gap-2 px-3 text-[10px] uppercase tracking-[0.16em] text-app-text-secondary">
            <span className="h-1.5 w-1.5 rounded-full bg-app-accent shrink-0" />
            <span className="font-semibold text-app-text hidden sm:inline">{copy[`play_${viewMode}`]}</span>
            <span className="font-semibold text-app-text sm:hidden">Duel</span>
            {snapshot.status === 'active' && (
              <span className="text-app-accent font-bold ml-1">T{snapshot.turn}</span>
            )}
          </div>

          {/* Self status (compact on mobile) */}
          <div className="flex min-h-11 items-center gap-1 px-2 md:min-h-0 md:gap-1.5 md:px-3">
            <span className="text-[10px] uppercase tracking-[0.16em] text-app-text-secondary hidden md:inline">{self?.name || copy.you}:</span>
            {!finished && <span className="text-[10px] uppercase tracking-[0.16em] text-app-text-secondary md:hidden">{copy.you}:</span>}
            <span className={`font-semibold ${myTurn && !finished ? 'text-app-accent' : 'text-app-text'}`}>
              {snapshot.status === 'lobby'
                ? self?.ready ? copy.ready : copy.notReady
                : <span className="whitespace-nowrap" aria-label={`${copy.questions}: ${self?.question_count ?? 0}. ${copy.guesses}: ${self?.guess_count ?? 0}. ${copy.unlimited}`}>Q:{self?.question_count ?? 0} G:{self?.guess_count ?? 0}</span>}
            </span>
          </div>

          {/* Opponent status */}
          <div className="flex min-w-0 flex-col justify-center gap-0.5 px-2 py-1 md:shrink-0 md:flex-row md:items-center md:gap-1.5 md:px-3 md:py-0">
            <span className="min-w-0 text-[10px] uppercase tracking-normal text-app-text-secondary md:tracking-[0.16em]" title={opponent?.name}>
              {opponent?.name ? <span className="block truncate">{opponent.name}:</span> : <>
                <span className="md:hidden">{copy.waitingForFriend}</span>
                <span className="hidden md:inline">{copy.waitingFriend}</span>
              </>}
            </span>
            {opponent && (
              <span className={`whitespace-nowrap font-semibold ${!myTurn && snapshot.status === 'active' && !finished ? 'text-blue-700' : 'text-app-text-secondary'}`}>
                {snapshot.status === 'lobby'
                  ? opponent.ready ? copy.ready : copy.notReady
                  : `Q:${opponent.question_count ?? 0} G:${opponent.guess_count ?? 0}`}
              </span>
            )}
          </div>

          {/* Countdown timer */}
          {snapshot.deadline && !finished && (
            <Countdown deadline={snapshot.deadline} copy={copy} />
          )}

          {/* Mobile Secret Pill inside HUD */}
          {snapshot.status === 'active' && snapshot.own_secret && (
            <div className="col-span-2 flex min-h-11 min-w-0 items-center gap-1 px-2 text-[10px] md:hidden">
              <span className="font-semibold text-app-accent truncate max-w-[65px]">
                {showSecret ? snapshot.own_secret.name : '••••'}
              </span>
              <button
                type="button"
                className="flex min-h-11 min-w-11 items-center justify-center text-app-text-secondary hover:text-app-text p-0.5"
                aria-label={showSecret ? copy.hideSecret : copy.showSecret}
                onClick={() => setShowSecret(!showSecret)}
              >
                {showSecret ? <EyeOff size={11} /> : <Eye size={11} />}
              </button>
              {isHistoryOpen && (
                <BackToMapButton
                  onClick={() => setIsHistoryOpen(false)}
                  className="duel-compact-map"
                />
              )}
            </div>
          )}

          {/* Rules dialog trigger */}
          <button
            type="button"
            onClick={() => setRulesOpen(true)}
            className={`flex min-h-11 min-w-11 md:min-h-0 shrink-0 items-center justify-center gap-1.5 px-2.5 text-app-text-secondary hover:text-app-text hover:bg-app-surface-muted transition-colors text-[10px] uppercase tracking-wider cursor-pointer whitespace-nowrap md:tracking-[0.16em] ${snapshot.status === 'active' ? 'max-md:col-start-3 max-md:row-start-2' : ''}`}
            title={copy.rulesTitle}
          >
            <HelpCircle size={13} className="text-app-accent" />
            <span className="md:hidden">{'Guide'}</span>
            <span className="hidden md:inline">{copy.rulesTitle}</span>
          </button>

          {/* Result modal reopen button */}
          {finished && (
            <button
              type="button"
              onClick={() => setIsResultDismissed(false)}
              className="flex items-center gap-1.5 bg-app-accent/10 px-3 text-[10px] font-bold uppercase tracking-[0.16em] text-app-accent hover:bg-app-accent/20 transition-colors cursor-pointer"
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
          <div className="pointer-events-auto rounded-sm border border-amber-700/25 p-3 text-xs text-amber-900 bg-amber-50 backdrop-blur-md flex items-center justify-between gap-3 shadow-xl font-mono">
            <p>{entitiesError || copy.noEntities}</p>
            <button
              type="button"
              className="rounded-sm border border-amber-700/25 px-2 py-1 text-xs text-amber-900 hover:bg-amber-100 transition-colors cursor-pointer shrink-0"
              onClick={() => setEntityReload(value => value + 1)}
            >
              {copy.refresh}
            </button>
          </div>
        </div>
      )}

      {/* 3. Unified Deduction & Duel History Overlay (Left Side on Map) */}

      {(snapshot.status === 'active' || finished) && (
        <div className={`pointer-events-none ${
          isHistoryOpen
            ? 'game-notebook-layer max-md:absolute max-md:inset-0 max-md:z-[1100] md:absolute md:left-4 md:bottom-4 md:z-[1000] md:w-[28rem] md:max-w-[calc(100vw-2rem)]'
            : 'max-md:absolute max-md:inset-x-0 max-md:bottom-0 max-md:z-[995] max-md:w-full md:absolute md:left-4 md:bottom-4 md:z-[1000] md:w-fit md:max-w-[calc(100vw-2rem)]'
        }`}>
          {!isHistoryOpen ? (
            <>
            <div className="pointer-events-auto flex items-center gap-2 border-t border-app-border/20 bg-app-surface-raised px-2 pt-2 pb-[max(calc(env(safe-area-inset-bottom)+0.25rem),0.75rem)] md:hidden">
              <button
                type="button"
                onClick={() => { setActiveActionTab('question'); setIsHistoryOpen(true); }}
                className="min-h-11 flex-1 rounded-sm bg-app-accent/10 px-2 font-mono text-[10px] uppercase tracking-wider text-app-accent"
              >
                {copy.question}
              </button>
              <button
                type="button"
                onClick={() => { setActiveActionTab('guess'); setIsHistoryOpen(true); }}
                className="min-h-11 flex-1 rounded-sm bg-app-accent px-2 font-mono text-[10px] uppercase tracking-wider text-white"
              >
                {copy.guess}
              </button>
            </div>
            <button
              type="button"
              onClick={() => setIsHistoryOpen(true)}
              className="pointer-events-auto hidden min-h-11 md:min-h-0 items-center gap-2 rounded-sm border border-app-border/30 bg-app-surface-raised px-3 font-mono text-[10px] uppercase tracking-[0.16em] text-app-text-secondary shadow-sm hover:bg-app-surface-muted transition-colors cursor-pointer md:flex"
              aria-label="Expand Duel Chat"
            >
              <MessageSquare size={13} className="text-app-accent" />
              <span>Chat</span>
              <span className="text-app-text-muted">·</span>
              <span className="text-app-accent font-semibold">T{snapshot.turn}</span>
              <span className="text-app-text-muted">·</span>
              <span className="text-app-text">M: {snapshot.history.length}</span>
              <ChevronUp size={13} className="text-app-text-muted ml-0.5" />
            </button>
            </>
          ) : (
            <div
              onWheel={(e) => e.stopPropagation()}
              onPointerDown={(e) => e.stopPropagation()}
              className="pointer-events-auto flex h-full flex-col overflow-hidden bg-app-surface-raised shadow-sm max-md:absolute max-md:inset-0 md:h-[68vh] md:max-h-[72vh] md:w-[28rem] md:rounded-sm md:border md:border-app-border/20 md:bg-app-surface"
            >
              {/* Header */}
              <div className="duel-notebook-heading flex items-center justify-between border-b border-app-border/20 bg-app-surface-raised px-3 md:py-2 shrink-0">
                <div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.16em] text-app-text font-semibold">
                  <MessageSquare size={13} className="text-app-accent" />
                  <span>Deduction Chat</span>
                  <span className="text-app-text-muted font-normal">({snapshot.history.length})</span>
                </div>
                <BackToMapButton onClick={() => setIsHistoryOpen(false)} />
              </div>
              {snapshot.status === 'active' && (
                <div className="flex items-center justify-between gap-2 border-b border-app-border/20 bg-app-surface-muted px-3 py-1.5 font-mono text-[10px] text-app-text-secondary md:hidden">
                  <span className="truncate">
                    T{snapshot.turn} · {mustAnswer ? copy.answering : myTurn ? copy.yourTurn : copy.waitingForFriend}
                  </span>
                  {snapshot.deadline && <Countdown deadline={snapshot.deadline} copy={copy} />}
                </div>
              )}


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
              {snapshot.status === 'active' && (
                mustAnswer && pendingQuestion ? (
                  <div ref={answerPanel} className="shrink-0 border-t border-app-border/20 bg-app-surface-raised px-4 py-3">
                    <div className="flex items-center gap-2 font-mono text-[11px] text-amber-900">
                      <Zap size={14} className="text-amber-800 animate-pulse" />
                      <span>Question received: choose answer in modal</span>
                    </div>
                  </div>
                ) : myTurn ? (
                  <GameActionComposer
                    activeAction={activeActionTab}
                    onActionChange={action => setActiveActionTab(action)}
                    questionDisabled={snapshot.phase === 'reply'}
                    trailingActions={canGuess && (
                      <button
                        type="button"
                        className="ml-1 cursor-pointer font-mono text-[10px] uppercase tracking-wider text-app-text-secondary hover:text-amber-800 disabled:text-app-text-muted disabled:opacity-100"
                        disabled={busy}
                        onClick={() => { void room.act('pass', {}); }}
                      >
                        {copy.pass}
                      </button>
                    )}
                    helperText={snapshot.phase === 'thinking' ? copy.unlimited : undefined}
                  >
                    {activeActionTab === 'question' ? (
                      <QuestionInput
                        onAsk={question => room.act('ask', { question: question.trim() })}
                        isLoading={busy}
                        disabled={!myTurn || snapshot.phase !== 'thinking'}
                        placeholder={copy.questionPlaceholder}
                        minLength={3}
                        maxLength={500}
                        mode={viewMode}
                      />
                    ) : (
                      <GuessInput
                        dropup={true}
                        countries={entities}
                        alreadyGuessedNames={snapshot.history.filter(h => h.player_id === snapshot.you && h.type === 'guess' && h.entity).map(h => h.entity!.name)}
                        alreadyGuessedIds={snapshot.history.filter(h => h.player_id === snapshot.you && h.type === 'guess' && h.entity).map(h => h.entity!.id)}
                        onGuess={id => room.act('guess', { entity_id: id })}
                        isLoading={busy || entitiesLoading}
                        disabled={!canGuess}
                        placeholder={copy.search}
                        noMatchesLabel={copy.noMatches}
                      />
                    )}
                  </GameActionComposer>
                ) : (
                  <div className="shrink-0 border-t border-app-border/20 bg-app-surface-raised px-4 py-3">
                    <div className="flex flex-wrap items-center justify-between gap-2 font-mono text-xs">
                      <div className="flex items-center gap-2 text-app-text-secondary">
                        <Clock size={14} className="text-app-text-muted animate-spin-slow" />
                        <span>
                          {copy.waiting}: {opponent?.name || copy.waitingFriend} {snapshot.phase === 'answering' ? copy.awaitingAnswer : copy.theirTurn}
                        </span>
                      </div>
                      {snapshot.draw_offer_by === snapshot.you ? (
                        <span className="text-[10px] uppercase tracking-wider text-amber-800">{copy.drawOffered}</span>
                      ) : snapshot.draw_offer_by ? (
                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            className="max-md:min-h-11 rounded-sm bg-amber-500 px-3 py-2 text-[10px] font-bold uppercase tracking-wider text-amber-950"
                            disabled={busy}
                            onClick={() => { void room.act('accept_draw', {}); }}
                          >
                            {copy.acceptDraw}
                          </button>
                          <button
                            type="button"
                            className="max-md:min-h-11 rounded-sm border border-app-border/30 bg-app-surface-muted px-3 py-2 text-[10px] uppercase tracking-wider text-app-text-secondary hover:bg-app-border/20"
                            disabled={busy}
                            onClick={() => { void room.act('decline_draw', {}); }}
                          >
                            {copy.declineDraw}
                          </button>
                        </div>
                      ) : (
                        <button
                          type="button"
                          className="max-md:min-h-11 cursor-pointer rounded-sm px-3 py-2 text-[10px] uppercase tracking-wider text-app-text-muted hover:text-app-text"
                          disabled={busy}
                          onClick={() => { void room.act('offer_draw', {}); }}
                        >
                          {copy.offerDraw}
                        </button>
                      )}
                    </div>
                  </div>
                )
              )}
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
        <div className="pointer-events-none absolute inset-x-2 top-14 z-[1000] flex flex-col items-center gap-3 sm:inset-x-auto sm:right-4 sm:top-14 sm:w-full sm:max-w-sm sm:items-stretch">
          {/* Secret country selector floating bar */}
          <div className="pointer-events-auto flex flex-col items-stretch justify-between gap-2 rounded-sm border border-app-border/30 bg-app-surface-raised px-3 py-2.5 shadow-md backdrop-blur-md sm:flex-row sm:items-center sm:gap-3">
            <div className="flex items-center gap-2 min-w-0">
              <EyeOff size={14} className="text-app-accent shrink-0" />
              <div className="min-w-0">
                <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-app-text-secondary block">{copy.secret}:</span>
                <span className="break-words font-semibold text-app-text text-xs">
                  {snapshot.own_secret ? snapshot.own_secret.name : copy.chooseSecretOnMap}
                </span>
              </div>
            </div>

            <div className="flex items-stretch justify-end gap-2 shrink-0">
              {!self?.ready && (
                <button
                  type="button"
                  onClick={() => { void room.act('randomize_secret', {}); }}
                  disabled={busy || entitiesLoading}
                  className="flex max-md:min-h-11 max-md:flex-1 min-w-0 items-center justify-center gap-1.5 rounded-sm border border-app-border/30 bg-app-surface-muted hover:bg-app-border/20 px-2.5 py-2 font-mono text-[10px] uppercase tracking-wider text-app-text-secondary transition-colors cursor-pointer"
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
                className={`max-md:min-h-11 max-md:flex-1 min-w-0 rounded-sm px-3 py-2 font-mono text-[10px] font-bold uppercase tracking-wider transition-colors cursor-pointer ${
                  self?.ready
                    ? 'bg-app-surface-muted text-app-text-secondary hover:bg-app-border/20 border border-app-border/30'
                    : 'bg-app-accent text-white hover:bg-app-accent-hover disabled:bg-app-surface-muted disabled:text-app-text-muted disabled:opacity-100'
                }`}
              >
                {self?.ready ? copy.unready : copy.acceptAndReady}
              </button>
            </div>
          </div>

          {/* Invite Link Card (hidden when friend joins the lobby) */}
          {!opponent && (
            <div className="pointer-events-auto w-full">
              <InviteLink code={snapshot.invite_code} copy={copy} />
            </div>
          )}
        </div>
      )}

      {/* 4. Own Secret Viewing Pill (Top Right on Map during active duel) */}
      {snapshot.status === 'active' && snapshot.own_secret && (
        <div className="hidden sm:block pointer-events-none absolute right-3 top-3 z-[1000]">
          <div className="pointer-events-auto flex items-center gap-2 rounded-sm border border-app-border/30 bg-app-surface-raised px-2.5 py-1 backdrop-blur-md shadow-sm text-xs font-mono">
            <span className="text-[10px] uppercase tracking-[0.16em] text-app-text-secondary">{copy.secret}:</span>
            <span className="font-semibold text-app-accent text-xs">
              {showSecret ? snapshot.own_secret.name : '••••••••'}
            </span>
            <button
              type="button"
              className="text-app-text-secondary hover:text-app-text p-0.5 cursor-pointer ml-1"
              aria-label={showSecret ? copy.hideSecret : copy.showSecret}
              onClick={() => setShowSecret(!showSecret)}
            >
              {showSecret ? <EyeOff size={13} /> : <Eye size={13} />}
            </button>
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
          className="fixed inset-0 z-[1300] flex items-start justify-center overflow-y-auto p-3 pb-[calc(env(safe-area-inset-bottom)+0.75rem)] sm:items-center sm:px-4 sm:pt-4 sm:pb-[calc(env(safe-area-inset-bottom)+1rem)] bg-black/70 backdrop-blur-md animate-in fade-in duration-150 cursor-pointer"
        >
          <div
            className="relative my-auto max-h-[calc(var(--app-height,100dvh)-1.5rem)] w-full max-w-md overflow-y-auto rounded-sm border border-app-border/30 bg-app-surface-raised p-4 shadow-2xl space-y-3 cursor-default sm:p-5"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-app-border/20 pb-2">
              <h3 className="font-mono text-xs uppercase tracking-[0.16em] text-app-accent font-semibold">
                {copy.rulesTitle}
              </h3>
              <button
                type="button"
                onClick={() => setRulesOpen(false)}
                className="max-md:min-h-11 max-md:min-w-11 flex items-center justify-center text-app-text-secondary hover:text-app-text cursor-pointer"
              >
                <X size={15} />
              </button>
            </div>
            <p className="text-xs leading-relaxed text-app-text-secondary">{copy.rules}</p>
            <p className="text-xs leading-relaxed text-app-text-muted">{copy.timeoutRules}</p>
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
