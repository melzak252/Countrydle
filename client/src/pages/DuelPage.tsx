import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  Clock3,
  Eye,
  EyeOff,
  Users,
  Target,
  HelpCircle,
  Maximize2,
  Minimize2,
  Zap,
  Dices,
  Clock,
  Compass,
  ChevronDown,
} from 'lucide-react';
import { useFriendMatch } from '../hooks/useFriendMatch';
import { useAuthStore } from '../stores/authStore';
import { friendError, friendMatchApi, friendRequestId, uncertainFriendRequest } from '../services/friendMatchApi';
import type { FriendEntity, FriendMode, FriendSnapshot } from '../types/friendMatch';
import GuessInput from '../components/GuessInput';
import QuestionInput from '../components/QuestionInput';
import FriendDuelMap from '../components/friendDuel/FriendDuelMap';
import DuelHistory, { AnswerPicker, PrivateAdvice } from '../components/friendDuel/DuelHistory';
import { duelButton, duelCopy, duelInput, duelModes, duelPanel, duelPrimary } from '../components/friendDuel/copy';
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
      className={`flex items-center gap-2 rounded-sm border px-3 py-1.5 text-xs font-semibold ${
        isUrgent
          ? 'border-amber-400/60 bg-amber-950/60 text-amber-200 animate-pulse'
          : 'border-white/15 bg-obsidian-950 text-sand-100'
      }`}
    >
      <Clock3 size={14} className={isUrgent ? 'text-amber-400' : 'text-zinc-400'} aria-hidden="true" />
      <span className="sr-only">{copy.deadline}</span>
      <span role="timer" className="font-mono tabular-nums text-sm">
        {seconds > 0 ? `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}` : copy.expired}
      </span>
    </div>
  );
}

function InviteLink({ code, copy }: { code: string; copy: DuelCopy }) {
  const [notice, setNotice] = useState('');
  const link = `${window.location.origin}/duel/${encodeURIComponent(code)}`;

  return (
    <section className={duelPanel} aria-label={copy.invite}>
      <h2 className="flex items-center gap-2 text-sm font-semibold text-sand-100">
        <Users size={16} className="text-emerald-400" />
        {copy.invite}
      </h2>
      <label className="sr-only" htmlFor="duel-invite-link">{copy.invite}</label>
      <input
        id="duel-invite-link"
        className={`${duelInput} my-3 font-mono text-xs select-all`}
        value={link}
        readOnly
        onFocus={event => event.target.select()}
      />
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className={duelPrimary}
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
            className={duelButton}
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
      <p className="mt-3 text-xs leading-5 text-zinc-400">{copy.guest}</p>
    </section>
  );
}

function Results({
  snapshot,
  copy,
  busy,
  rematch,
}: {
  snapshot: FriendSnapshot;
  copy: DuelCopy;
  busy: boolean;
  rematch: () => void;
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
    <section className={`${duelPanel} border-emerald-500/40 bg-gradient-to-b from-obsidian-900 to-obsidian-950`} aria-label={copy.results}>
      <p className="font-mono text-[10px] uppercase tracking-widest text-zinc-400">{copy.results}</p>
      <h2 className={`mt-2 text-2xl font-bold sm:text-3xl ${isWinner ? 'text-emerald-300' : 'text-sand-100'}`}>
        {outcome}
      </h2>

      <h3 className="mb-2 mt-5 text-xs font-semibold uppercase tracking-wider text-zinc-400">{copy.reveals}</h3>
      <ul className="space-y-2 rounded-sm border border-white/10 bg-black/20 p-3">
        {snapshot.reveals?.map(reveal => {
          const playerName = snapshot.players.find(p => p.id === reveal.player_id)?.name || 'Player';
          const isYou = reveal.player_id === snapshot.you;
          return (
            <li key={reveal.player_id} className="flex flex-wrap items-center justify-between gap-2 text-sm">
              <span className={`text-xs font-medium ${isYou ? 'text-emerald-400' : 'text-blue-400'}`}>
                {playerName} {isYou ? `(${copy.you})` : ''}
              </span>
              <strong className="text-sand-100">{reveal.entity.name}</strong>
            </li>
          );
        })}
      </ul>

      {snapshot.session_score && (
        <p className="mt-4 text-xs text-zinc-400">
          {copy.wins}:{' '}
          {snapshot.session_score
            .map(score => `${snapshot.players.find(p => p.id === score.player_id)?.name || '—'}: ${score.wins}`)
            .join(' · ')}
          {snapshot.draw_count !== undefined && ` · ${copy.draws}: ${snapshot.draw_count}`}
        </p>
      )}

      <div className="mt-5 flex flex-wrap items-center gap-3">
        {snapshot.rematch_code ? (
          <Link className={duelPrimary} to={`/duel/${encodeURIComponent(snapshot.rematch_code)}`}>
            {copy.rematchOpen}
          </Link>
        ) : snapshot.players.length < 2 ? null : self?.rematch_ready ? (
          <p role="status" className="text-sm font-medium text-emerald-300">{copy.rematchWaiting}</p>
        ) : (
          <>
            {opponent?.rematch_ready && <p className="w-full text-sm font-medium text-emerald-300">{copy.rematchReceived}</p>}
            <button type="button" className={duelPrimary} disabled={busy} onClick={rematch}>
              {copy.rematch}
            </button>
          </>
        )}
        <Link className={duelButton} to="/duel">{copy.newDuel}</Link>
      </div>
    </section>
  );
}

function DuelRoom({ code }: { code?: string }) {
  const { i18n, t } = useTranslation();
  const copy = duelCopy(i18n.resolvedLanguage || i18n.language);
  const navigate = useNavigate();
  const room = useFriendMatch(code, copy.error, copy.stale);
  const snapshot = room.snapshot;

  const accountName = useAuthStore(state => state.user?.username);
  const authLoading = useAuthStore(state => state.isLoading);
  const [guestName, setGuestName] = useState('');
  const name = accountName || guestName;
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
  const [mapExpanded, setMapExpanded] = useState(false);
  const [activeActionTab, setActiveActionTab] = useState<'question' | 'guess'>('question');

  const answerPanel = useRef<HTMLElement>(null);
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

  useEffect(() => {
    if (mustAnswer && window.innerWidth < 1024) {
      answerPanel.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
  }, [mustAnswer, pendingQuestion?.id]);

  return (
    <div className="mx-auto w-full max-w-7xl pb-12">
      {/* Top Header */}
      <header className="mb-4 flex flex-wrap items-center justify-between gap-3 border-b border-white/10 pb-3">
        <div>
          <p className="mb-1 flex items-center gap-2 font-mono text-[10px] uppercase tracking-wider text-zinc-400">
            <Users size={13} className="text-emerald-400" aria-hidden="true" />
            {copy.multiplayer}
            <span className="text-emerald-400">
              {snapshot?.status === 'active' ? `${copy.turn} ${snapshot.turn}` : finished ? copy.results : copy.lobby}
            </span>
          </p>
          <h1 className="text-xl font-bold tracking-tight text-sand-100 sm:text-2xl">
            {copy[`play_${viewMode}`]}
          </h1>
        </div>
        {snapshot && (
          <div className="flex items-center gap-3">
            <span
              role="status"
              className={`flex items-center gap-1.5 text-xs font-medium ${
                room.connection === 'connected' ? 'text-emerald-400' : 'text-amber-300'
              }`}
            >
              <span className="h-2 w-2 rounded-full bg-current" />
              {copy[room.connection]}
            </span>
            {snapshot.deadline && !finished && <Countdown deadline={snapshot.deadline} copy={copy} />}
          </div>
        )}
      </header>

      {/* Errors and Retry Alerts */}
      {(room.error || room.retryable) && (
        <div role="alert" className="mb-4 space-y-3 rounded-sm border border-red-500/40 bg-red-950/20 p-4 text-sm text-red-200">
          {room.error && <p>{room.error}</p>}
          {room.retryable && <p>{copy.uncertain}</p>}
          <div className="flex flex-wrap gap-2">
            {room.retryable && (
              <button type="button" className={duelButton} disabled={room.busy} onClick={() => { void room.retry(); }}>
                {copy.retry}
              </button>
            )}
            <button type="button" className={duelButton} onClick={() => { void room.refresh(); }}>
              {copy.refresh}
            </button>
          </div>
        </div>
      )}

      {/* PROMINENT HERO TURN BANNER - When Game is Active */}
      {snapshot && snapshot.status === 'active' && (
        <div className="mb-5 overflow-hidden rounded-md border shadow-lg transition-all">
          {mustAnswer ? (
            /* Urgently need to answer friend's question */
            <div className="flex flex-wrap items-center justify-between gap-3 border-amber-500/60 bg-gradient-to-r from-amber-950/80 via-amber-900/40 to-obsidian-950 p-4 border-l-8 border-l-amber-400">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/40">
                  <Zap size={20} className="animate-pulse" />
                </div>
                <div>
                  <h2 className="text-sm font-bold uppercase tracking-wider text-amber-300 sm:text-base">
                    {copy.actionRequired}: {copy.answering}
                  </h2>
                  <p className="text-xs text-amber-100/90 sm:text-sm">
                    {opponent?.name || copy.friendMoves} {copy.friendAsked}: <span className="font-semibold italic">"{pendingQuestion?.question}"</span>
                  </p>
                </div>
              </div>
              <span className="rounded bg-amber-400 text-obsidian-950 px-3 py-1 text-xs font-bold uppercase tracking-wider shadow">
                {copy.answering}
              </span>
            </div>
          ) : myTurn ? (
            /* It is YOUR turn to make a move (ask or guess) */
            <div className="flex flex-wrap items-center justify-between gap-3 border-emerald-500/60 bg-gradient-to-r from-emerald-950/80 via-emerald-900/40 to-obsidian-950 p-4 border-l-8 border-l-emerald-400">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
                  <Target size={20} className="text-emerald-400 animate-spin-slow" />
                </div>
                <div>
                  <h2 className="text-sm font-bold uppercase tracking-wider text-emerald-300 sm:text-base flex items-center gap-2">
                    {copy.yourTurn}
                    <span className="inline-block h-2 w-2 rounded-full bg-emerald-400" />
                  </h2>
                  <p className="text-xs text-emerald-100/90 sm:text-sm">
                    {snapshot.phase === 'reply' ? copy.reply : copy.turnHelp}
                  </p>
                </div>
              </div>
              <span className="rounded bg-emerald-400 text-obsidian-950 px-3 py-1 text-xs font-bold uppercase tracking-wider shadow">
                {copy.activeTurn}
              </span>
            </div>
          ) : snapshot.phase === 'answering' ? (
            /* Friend is answering your question */
            <div className="flex flex-wrap items-center justify-between gap-3 border-blue-500/40 bg-gradient-to-r from-blue-950/70 via-blue-900/30 to-obsidian-950 p-4 border-l-8 border-l-blue-400">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-blue-500/20 text-blue-300 border border-blue-500/40">
                  <Clock size={20} className="animate-spin-slow" />
                </div>
                <div>
                  <h2 className="text-sm font-bold uppercase tracking-wider text-blue-300 sm:text-base">
                    {copy.awaitingAnswer}
                  </h2>
                  <p className="text-xs text-blue-100/80 sm:text-sm">
                    {opponent?.name || copy.friendMoves} is answering your question.
                  </p>
                </div>
              </div>
              <span className="rounded border border-blue-500/40 bg-blue-950 text-blue-300 px-3 py-1 text-xs font-medium">
                {copy.waiting}
              </span>
            </div>
          ) : (
            /* Friend is thinking */
            <div className="flex flex-wrap items-center justify-between gap-3 border-white/15 bg-gradient-to-r from-zinc-900 via-obsidian-900 to-obsidian-950 p-4 border-l-8 border-l-zinc-500">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-white/5 text-zinc-300 border border-white/10">
                  <Clock size={20} />
                </div>
                <div>
                  <h2 className="text-sm font-bold uppercase tracking-wider text-sand-100 sm:text-base">
                    {opponent?.name || copy.friendMoves}: {copy.theirTurn}
                  </h2>
                  <p className="text-xs text-zinc-400 sm:text-sm">
                    {copy.theirTurn}
                  </p>
                </div>
              </div>
              <span className="rounded border border-white/10 bg-black/40 text-zinc-400 px-3 py-1 text-xs font-medium">
                {copy.waiting}
              </span>
            </div>
          )}
        </div>
      )}

      {/* DISTINCT PLAYERS BAR (You vs Friend) */}
      {snapshot && (
        <div className="mb-5 grid grid-cols-1 sm:grid-cols-2 gap-3">
          {/* Card: YOU */}
          <section
            className={`rounded-md border p-3.5 transition-all ${
              myTurn && !finished
                ? 'border-emerald-500/60 bg-emerald-950/20 shadow-md ring-1 ring-emerald-500/30'
                : 'border-white/10 bg-obsidian-900'
            }`}
          >
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2.5">
                <div className="flex h-7 w-7 items-center justify-center rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 font-bold text-xs">
                  {self?.name?.charAt(0).toUpperCase() || 'Y'}
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-sand-100 text-sm truncate max-w-[150px]">
                      {self?.name || copy.you}
                    </span>
                    <span className="rounded bg-emerald-500/20 text-emerald-300 text-[10px] font-bold px-1.5 py-0.5 border border-emerald-500/30">
                      {copy.you}
                    </span>
                  </div>
                  <span className="text-[11px] text-zinc-400">
                    {snapshot.status === 'lobby'
                      ? self?.ready ? copy.ready : copy.notReady
                      : `${copy.questions}: ${self?.question_count ?? 0} · ${copy.guesses}: ${self?.guess_count ?? 0}`}
                  </span>
                </div>
              </div>

              {/* Turn pill */}
              {!finished && snapshot.status === 'active' && (
                <span
                  className={`text-[11px] font-semibold px-2 py-0.5 rounded-full flex items-center gap-1 ${
                    myTurn
                      ? 'bg-emerald-500 text-obsidian-950 font-bold'
                      : 'bg-zinc-800 text-zinc-400'
                  }`}
                >
                  {myTurn && <span className="h-1.5 w-1.5 rounded-full bg-obsidian-950" />}
                  {myTurn ? copy.yourTurn : copy.waiting}
                </span>
              )}
            </div>

            {/* Secret view toggle */}
            {snapshot.own_secret && (
              <div className="mt-2.5 pt-2 border-t border-white/5 flex items-center justify-between text-xs">
                <span className="text-zinc-400 text-[11px]">{copy.secret}:</span>
                <div className="flex items-center gap-1.5">
                  {showSecret ? (
                    <span className="font-semibold text-emerald-300">{snapshot.own_secret.name}</span>
                  ) : (
                    <span className="font-mono text-zinc-500">••••••••</span>
                  )}
                  <button
                    type="button"
                    className="text-zinc-400 hover:text-sand-100 p-0.5"
                    aria-label={showSecret ? copy.hideSecret : copy.showSecret}
                    onClick={() => setShowSecret(!showSecret)}
                  >
                    {showSecret ? <EyeOff size={13} /> : <Eye size={13} />}
                  </button>
                </div>
              </div>
            )}
          </section>

          {/* Card: FRIEND */}
          <section
            className={`rounded-md border p-3.5 transition-all ${
              !myTurn && snapshot.status === 'active' && !finished
                ? 'border-blue-500/60 bg-blue-950/20 shadow-md ring-1 ring-blue-500/30'
                : 'border-white/10 bg-obsidian-900'
            }`}
          >
            {opponent ? (
              <>
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2.5">
                    <div className="flex h-7 w-7 items-center justify-center rounded-full bg-blue-500/20 text-blue-300 border border-blue-500/40 font-bold text-xs">
                      {opponent.name.charAt(0).toUpperCase()}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-sand-100 text-sm truncate max-w-[150px]">
                          {opponent.name}
                        </span>
                        <span className="rounded bg-blue-500/20 text-blue-300 text-[10px] font-bold px-1.5 py-0.5 border border-blue-500/30">
                          {copy.title}
                        </span>
                      </div>
                      <span className="text-[11px] text-zinc-400">
                        {snapshot.status === 'lobby'
                          ? opponent.ready ? copy.ready : copy.notReady
                          : `${copy.questions}: ${opponent.question_count} · ${copy.guesses}: ${opponent.guess_count}`}
                      </span>
                    </div>
                  </div>

                  {/* Turn pill */}
                  {!finished && snapshot.status === 'active' && (
                    <span
                      className={`text-[11px] font-semibold px-2 py-0.5 rounded-full flex items-center gap-1 ${
                        !myTurn
                          ? 'bg-blue-500 text-obsidian-950 font-bold'
                          : 'bg-zinc-800 text-zinc-400'
                      }`}
                    >
                      {!myTurn && <span className="h-1.5 w-1.5 rounded-full bg-obsidian-950" />}
                      {!myTurn ? copy.activeTurn : copy.waiting}
                    </span>
                  )}
                </div>

                {Boolean(opponent.timeout_count) && (
                  <p className="mt-2 text-[11px] text-amber-300">
                    {copy.timeoutWarning}: {opponent.timeout_count}
                  </p>
                )}
              </>
            ) : (
              <div className="flex h-full items-center justify-center text-xs text-zinc-500 italic py-2">
                {copy.waitingFriend}
              </div>
            )}
          </section>
        </div>
      )}

      {/* MAIN TWO-COLUMN WORKSPACE: 9 cols on map in lobby, 7 cols during active game */}
      <div className="grid items-start gap-6 lg:grid-cols-12">
        {/* LEFT COLUMN: Map & Action Station */}
        <section className={`min-w-0 space-y-5 ${snapshot?.status === 'lobby' ? 'lg:col-span-8 xl:col-span-9' : 'lg:col-span-7'}`} aria-label={copy.atlas}>
          {/* ACTION STATION: Shown FIRST if you must answer or it's your turn */}
          {snapshot?.status === 'active' && mustAnswer && pendingQuestion && (
            <section ref={answerPanel} className={`${duelPanel} border-amber-500/60 bg-amber-950/20 shadow-lg ring-1 ring-amber-500/40`}>
              <div className="flex items-center gap-2 mb-2">
                <Zap size={16} className="text-amber-400" />
                <h2 className="text-sm font-bold uppercase tracking-wider text-amber-300">{copy.answering}</h2>
              </div>
              <p className="my-3 whitespace-pre-wrap break-words text-lg font-semibold text-sand-100 bg-black/30 p-3.5 rounded border border-white/10">
                "{pendingQuestion.question}"
              </p>
              <div className="space-y-4">
                <AnswerPicker
                  copy={copy}
                  disabled={busy}
                  onAnswer={answer => {
                    void room.act('answer', {
                      question_id: pendingQuestion.id,
                      answer,
                      ...(advice?.status === 'completed' ? { observed_ai_question_id: pendingQuestion.id } : {}),
                    });
                  }}
                />
                <PrivateAdvice guidance={advice} copy={copy} />
              </div>
            </section>
          )}

          {/* ACTION STATION: If it's your turn to ask or guess */}
          {snapshot?.status === 'active' && myTurn && !mustAnswer && (
            <section className={`${duelPanel} border-emerald-500/50 bg-emerald-950/15 shadow-lg ring-1 ring-emerald-500/30`}>
              <div className="mb-4 flex items-center justify-between gap-3 border-b border-white/10 pb-3">
                <h2 className="flex items-center gap-2 text-sm font-bold text-emerald-300">
                  <Compass size={16} />
                  {copy.yourTurnToAct}
                </h2>
                {canGuess && (
                  <button
                    type="button"
                    className="text-xs text-zinc-400 hover:text-amber-200 underline underline-offset-4 disabled:opacity-40"
                    disabled={busy}
                    onClick={() => { void room.act('pass', {}); }}
                  >
                    {copy.pass}
                  </button>
                )}
              </div>

              {snapshot.phase === 'reply' ? (
                <div className="space-y-4">
                  <p className="text-sm text-amber-200 font-medium">{copy.reply}</p>
                  <div>
                    <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-sand-100">{copy.guess}</h3>
                    <GuessInput
                      countries={entities}
                      onGuess={id => room.act('guess', { entity_id: id })}
                      isLoading={busy || entitiesLoading}
                      disabled={!canGuess}
                      placeholder={copy.search}
                      noMatchesLabel={copy.noMatches}
                    />
                  </div>
                </div>
              ) : (
                <div className="space-y-4">
                  {/* Action switcher tabs: Question vs Guess */}
                  <div className="flex rounded-sm bg-obsidian-950 p-1 border border-white/10" role="tablist">
                    <button
                      type="button"
                      role="tab"
                      aria-selected={activeActionTab === 'question'}
                      className={`flex-1 rounded-sm py-1.5 px-3 text-xs font-semibold flex items-center justify-center gap-1.5 transition-all ${
                        activeActionTab === 'question'
                          ? 'bg-emerald-950 text-emerald-300 border border-emerald-500/50 shadow-sm'
                          : 'text-zinc-400 hover:text-sand-100'
                      }`}
                      onClick={() => setActiveActionTab('question')}
                    >
                      <HelpCircle size={13} />
                      {copy.askQuestionTab}
                    </button>
                    <button
                      type="button"
                      role="tab"
                      aria-selected={activeActionTab === 'guess'}
                      className={`flex-1 rounded-sm py-1.5 px-3 text-xs font-semibold flex items-center justify-center gap-1.5 transition-all ${
                        activeActionTab === 'guess'
                          ? 'bg-emerald-950 text-emerald-300 border border-emerald-500/50 shadow-sm'
                          : 'text-zinc-400 hover:text-sand-100'
                      }`}
                      onClick={() => setActiveActionTab('guess')}
                    >
                      <Target size={13} />
                      {copy.makeGuessTab}
                    </button>
                  </div>

                  {activeActionTab === 'question' ? (
                    <div>
                      <QuestionInput
                        onAsk={question => room.act('ask', { question: question.trim() })}
                        isLoading={busy}
                        disabled={!myTurn || snapshot.phase !== 'thinking'}
                        placeholder={copy.questionPlaceholder}
                        minLength={3}
                        maxLength={500}
                      />
                      <p className="mt-2 text-[11px] text-zinc-500">{copy.turnHelp}</p>
                    </div>
                  ) : (
                    <div>
                      <GuessInput
                        countries={entities}
                        onGuess={id => room.act('guess', { entity_id: id })}
                        isLoading={busy || entitiesLoading}
                        disabled={!canGuess}
                        placeholder={copy.search}
                        noMatchesLabel={copy.noMatches}
                      />
                      <p className="mt-2 text-[11px] text-zinc-500">{copy.turnHelp}</p>
                    </div>
                  )}
                </div>
              )}
            </section>
          )}

          {/* MAP CARD (Compact by default with Expand/Minimize toggle) */}
          <div className="overflow-hidden rounded-md border border-white/10 bg-obsidian-900 shadow-md">
            {/* Map Header with Compact/Expand toggle */}
            <div className="flex items-center justify-between gap-3 border-b border-white/10 px-4 py-2.5 font-mono text-xs text-zinc-400">
              <span className="flex items-center gap-1.5">
                <Compass size={14} className="text-emerald-400" />
                <span className="font-semibold text-sand-100 uppercase tracking-wider">{copy.atlas}</span>
                <span className="text-zinc-500">/ {copy[viewMode]}</span>
              </span>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  className="flex items-center gap-1 rounded bg-white/5 hover:bg-white/10 px-2 py-1 text-[11px] text-zinc-300 transition-colors border border-white/10"
                  onClick={() => setMapExpanded(!mapExpanded)}
                  title={mapExpanded ? copy.collapseMap : copy.expandMap}
                >
                  {mapExpanded ? <Minimize2 size={12} /> : <Maximize2 size={12} />}
                  <span>{mapExpanded ? copy.collapseMap : copy.expandMap}</span>
                </button>
              </div>
            </div>

            {/* Map Frame: Large map during lobby preparation */}
            <div
              className={`relative ${
                mapExpanded
                  ? 'h-[620px] sm:h-[720px]'
                  : snapshot?.status === 'lobby'
                  ? 'h-[500px] sm:h-[580px] lg:h-[640px]'
                  : 'h-[280px] sm:h-[340px]'
              }`}
            >
              <FriendDuelMap
                mode={viewMode}
                matchKey={snapshot?.id || `preview-${viewMode}`}
                finished={Boolean(finished)}
                revealedEntityName={revealedOpponent}
                className="h-full !rounded-none !border-0 !shadow-none"
                isLobby={snapshot?.status === 'lobby'}
                selectedSecretName={snapshot?.own_secret?.name}
                onEntitySelect={(clickedName) => {
                  if (snapshot?.status === 'lobby' && !self?.ready) {
                    const norm = normalizeEntityName(clickedName);
                    const match = entities.find(e => normalizeEntityName(e.name) === norm);
                    if (match) {
                      void room.act('select_secret', { entity_id: match.id });
                    }
                  }
                }}
              />
              {/* LOBBY SECRET PICKER: Toolbar-style pill on top of the map next to color buttons */}
              {snapshot?.status === 'lobby' && (
                <div className="absolute top-2 right-2 sm:right-3 z-[1000] flex items-center gap-1.5 rounded-sm border border-white/10 bg-obsidian-950/90 px-2 py-1 shadow-md backdrop-blur-sm max-w-[calc(100%-140px)]">
                  <div className="flex items-center gap-1.5 text-xs mr-1 truncate">
                    <EyeOff size={13} className="text-emerald-400 shrink-0" />
                    {snapshot.own_secret ? (
                      <span className="font-semibold text-emerald-300 truncate max-w-[120px] sm:max-w-[200px]" title={snapshot.own_secret.name}>
                        {snapshot.own_secret.name}
                      </span>
                    ) : (
                      <span className="text-[11px] text-zinc-400 italic hidden sm:inline truncate">
                        {copy.chooseSecretOnMap || 'Click map to choose'}
                      </span>
                    )}
                  </div>

                  <div className="h-3.5 w-px bg-white/15 shrink-0" aria-hidden="true" />

                  {self?.ready ? (
                    <button
                      type="button"
                      onClick={() => { void room.act('ready', { ready: false }); }}
                      disabled={busy}
                      className="flex h-6 items-center gap-1 rounded-sm bg-white/10 hover:bg-white/15 px-2 text-[11px] text-zinc-300 font-medium transition-colors cursor-pointer"
                      title={copy.unready}
                    >
                      {copy.unready}
                    </button>
                  ) : (
                    <div className="flex items-center gap-1 shrink-0">
                      <button
                        type="button"
                        onClick={() => { void room.act('randomize_secret', {}); }}
                        disabled={busy || entitiesLoading}
                        className="group relative flex h-6 w-6 items-center justify-center rounded-sm text-zinc-400 hover:text-amber-300 hover:bg-white/10 transition-colors cursor-pointer"
                        title={copy.random}
                        aria-label={copy.random}
                      >
                        <Dices size={14} className="text-amber-400 group-hover:scale-110 transition-transform" />
                        <span className="pointer-events-none absolute bottom-full mb-1.5 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-obsidian-950 px-2 py-0.5 text-[10px] font-medium text-amber-200 opacity-0 shadow-lg border border-white/15 transition-opacity group-hover:opacity-100 z-50">
                          {copy.random}
                        </span>
                      </button>

                      <button
                        type="button"
                        onClick={() => { void room.act('ready', { ready: true }); }}
                        disabled={busy || !snapshot.own_secret}
                        className="flex h-6 items-center gap-1 rounded-sm bg-emerald-500 hover:bg-emerald-400 disabled:opacity-40 disabled:cursor-not-allowed px-2 text-[11px] font-bold text-obsidian-950 transition-colors cursor-pointer"
                        title={copy.acceptAndReady}
                      >
                        <span>{copy.acceptAndReady}</span>
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
            <p className="border-t border-white/10 px-4 py-2 text-[11px] text-zinc-500">
              {copy.mapHelp}
            </p>
          </div>

          {/* (Lobby secret selection overlay is embedded directly inside the Map card) */}

          {/* ACTIVE GAME DRAW CONTROLS */}
          {snapshot?.status === 'active' && (
            <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-zinc-400 pt-1">
              {snapshot.draw_offer_by === snapshot.you ? (
                <p className="text-amber-300 font-medium">{copy.drawOffered}</p>
              ) : snapshot.draw_offer_by ? (
                <div className="flex items-center gap-2">
                  <p className="text-amber-300 font-medium">{copy.drawReceived}</p>
                  <button
                    type="button"
                    className={`${duelPrimary} py-1 px-2.5 text-xs`}
                    disabled={busy}
                    onClick={() => { void room.act('accept_draw', {}); }}
                  >
                    {copy.acceptDraw}
                  </button>
                  <button
                    type="button"
                    className={`${duelButton} py-1 px-2.5 text-xs`}
                    disabled={busy}
                    onClick={() => { void room.act('decline_draw', {}); }}
                  >
                    {copy.declineDraw}
                  </button>
                </div>
              ) : (
                <button
                  type="button"
                  className="hover:text-sand-100 disabled:opacity-40 underline underline-offset-4 text-xs"
                  disabled={busy}
                  onClick={() => { void room.act('offer_draw', {}); }}
                >
                  {copy.offerDraw}
                </button>
              )}
            </div>
          )}

          {/* RESULTS DISPLAY */}
          {snapshot && finished && (
            <Results snapshot={snapshot} copy={copy} busy={busy} rematch={() => { void room.act('rematch', {}); }} />
          )}

          {/* ENTITY LIST LOAD ERROR */}
          {snapshot && (entitiesError || (!entitiesLoading && !entities.length)) && !finished && (
            <div role="alert" className="rounded-sm border border-amber-400/40 p-4 text-sm text-amber-200 bg-amber-950/20">
              <p>{entitiesError || copy.noEntities}</p>
              <button
                type="button"
                className={`${duelButton} mt-2 text-xs`}
                onClick={() => setEntityReload(value => value + 1)}
              >
                {copy.refresh}
              </button>
            </div>
          )}
        </section>

        {/* RIGHT COLUMN: Sidebar (4 cols in lobby, 5 cols during active game) */}
        <aside className={`min-w-0 space-y-4 ${snapshot?.status === 'lobby' ? 'lg:col-span-4 xl:col-span-3' : 'lg:col-span-5'}`} aria-label={copy.title}>
          {room.loading ? (
            <div className={`${duelPanel} text-center py-12`}>
              <div className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-emerald-400 border-t-transparent mb-2" />
              <p className="text-xs text-emerald-300">{copy.loading}</p>
            </div>
          ) : !snapshot ? (
            /* Lobby Entry Form */
            <section className={duelPanel}>
              <h2 className="mb-2 text-lg font-bold text-sand-100">{code ? copy.join : copy.multiplayer}</h2>
              <p className="mb-5 text-xs leading-relaxed text-zinc-400">{copy.subtitle}</p>
              {room.invite && (
                <div className="mb-4 rounded border border-emerald-500/30 bg-emerald-950/20 p-2.5 text-xs text-emerald-300">
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
                  <div className="rounded border border-amber-500/40 bg-amber-950/20 p-3 text-xs text-amber-200">
                    <p className="font-semibold text-amber-300 mb-1">
                      {room.invite.status === 'finished' ? copy.ended : copy.full}
                    </p>
                  </div>
                  <Link to="/friends" className={`${duelPrimary} block w-full text-center`}>
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
                    <label className="mb-2 block text-xs font-medium text-zinc-300" htmlFor="duel-name">
                      {accountName ? t('auth.username') : copy.name}
                    </label>
                    <input
                      id="duel-name"
                      className={duelInput}
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
                      <label className="mb-2 block text-xs font-medium text-zinc-300" htmlFor="duel-mode-btn">
                        {copy.mode}
                      </label>
                      <button
                        id="duel-mode-btn"
                        type="button"
                        className={`${duelInput} flex items-center justify-between text-left cursor-pointer`}
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
                                  className={`flex items-center justify-between gap-1.5 rounded-sm px-2.5 py-1.5 text-xs text-left transition-colors ${
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
                                  className={`flex items-center justify-between gap-1.5 rounded-sm px-2.5 py-1.5 text-xs text-left transition-colors ${
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
                                  className={`flex items-center justify-between gap-1.5 rounded-sm px-2.5 py-1.5 text-xs text-left transition-colors ${
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
                  {entryError && <p role="alert" className="text-xs text-red-300">{entryError}</p>}
                  {entryUncertain && <p className="text-xs text-amber-200">{copy.uncertain}</p>}
                  <button type="submit" className={`${duelPrimary} w-full`} disabled={authLoading || entryBusy || !name.trim()}>
                    {entryUncertain ? copy.retry : code ? copy.join : copy.create}
                  </button>
                  <p className="text-xs leading-5 text-zinc-400">{copy.guest}</p>
                  <p className="text-[11px] leading-5 text-zinc-500">
                    {copy.collection}{' '}
                    <Link to="/privacy-policy" className="text-zinc-300 underline underline-offset-2">
                      {copy.privacy}
                    </Link>
                  </p>
                </form>
              )}
            </section>
          ) : snapshot.status === 'lobby' ? (
            /* Invite link in lobby */
            <InviteLink code={snapshot.invite_code} copy={copy} />
          ) : (
            /* Duel History Feed with Tabs */
            <DuelHistory
              key={snapshot.id}
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
          )}

          {/* Rules Collapsible */}
          <details className={duelPanel}>
            <summary className="cursor-pointer text-xs font-semibold text-zinc-300 hover:text-sand-100">
              {copy.rulesTitle}
            </summary>
            <p className="mt-3 text-xs leading-relaxed text-zinc-400">{copy.rules}</p>
            <p className="mt-2 text-xs leading-relaxed text-zinc-400">{copy.timeoutRules}</p>
          </details>

          {/* Leave duel */}
          {snapshot && !finished && (
            <button
              type="button"
              className="w-full text-center text-xs text-zinc-500 underline underline-offset-4 hover:text-rose-400 disabled:opacity-40 py-2"
              disabled={busy}
              onClick={() => {
                if (window.confirm(copy.leaveConfirm)) void room.act('leave', {});
              }}
            >
              {copy.leave}
            </button>
          )}
        </aside>
      </div>
    </div>
  );
}

export default function DuelPage() {
  const { code } = useParams<{ code: string }>();
  return <DuelRoom key={code || 'create'} code={code} />;
}
