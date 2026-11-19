import { useState, useMemo, useRef, useEffect } from 'react';
import {
  Target,
  FastForward,
  Clock,
  Check,
  X,
  AlertCircle,
  Trophy,
  HelpCircle,
} from 'lucide-react';
import { friendError, friendMatchApi } from '../../services/friendMatchApi';
import type {
  FriendGuidance,
  FriendHistory,
  FriendHistoryPage,
  FriendSnapshot,
  HumanAnswer,
} from '../../types/friendMatch';
import { duelButton, humanAnswers } from './copy';
import type { DuelCopy } from './copy';

export function PrivateAdvice({ guidance, copy }: { guidance?: FriendGuidance; copy: DuelCopy }) {
  return (
    <aside className="rounded-sm border border-app-accent/25 bg-app-accent/10 p-3 sm:p-4" aria-label={copy.ai}>
      <div className="flex items-center gap-1.5 text-xs font-medium text-app-accent">
        <h3 className="font-mono text-xs">{copy.ai}</h3>
      </div>
      <p className="mt-1 text-xs leading-relaxed text-app-text-secondary">{copy.aiHelp}</p>
      <div className="mt-2.5 text-xs" aria-live="polite">
        {!guidance || guidance.status === 'pending' || guidance.status === 'running' ? (
          <p className="flex items-center gap-2 text-app-text-secondary font-mono text-[11px]">
            <span className="inline-block h-2 w-2 rounded-full bg-app-accent animate-pulse" />
            {copy.aiPending}
          </p>
        ) : guidance.status === 'failed' ? (
          <p className="text-amber-800 font-mono text-[11px]">{copy.aiFailed}</p>
        ) : (
          <div className="space-y-1.5">
            {guidance.answer && (
              <span className="inline-flex items-center gap-1 rounded bg-app-accent/10 px-2 py-0.5 font-mono text-xs font-bold text-app-accent border border-app-accent/25">
                {copy[guidance.answer]}
              </span>
            )}
            <p className="whitespace-pre-wrap break-words text-xs text-app-text leading-relaxed">
              {guidance.explanation || copy.aiNoExplanation}
            </p>
            {guidance.source && (
              <p className="break-words text-[10px] font-mono text-app-text-muted">
                {copy.source}: <span className="text-app-text-secondary">{guidance.source}</span>
              </p>
            )}
          </div>
        )}
        {guidance?.late && <p className="mt-2 text-xs text-amber-800 font-mono text-[11px]">{copy.late}</p>}
      </div>
    </aside>
  );
}

export function AnswerPicker({
  disabled,
  copy,
  onAnswer,
}: {
  disabled: boolean;
  copy: DuelCopy;
  onAnswer: (answer: HumanAnswer) => void;
}) {
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4" role="group" aria-label={copy.answering}>
      {humanAnswers.map(answer => {
        const isYes = answer === 'yes' || answer === 'mostly_yes';
        const isNo = answer === 'no' || answer === 'mostly_no';
        const badgeColor = isYes
          ? 'border-app-accent/30 bg-app-accent/10 text-app-accent hover:border-app-accent/60 hover:bg-app-accent/15'
          : isNo
          ? 'border-rose-300 bg-rose-50 text-rose-800 hover:border-rose-400 hover:bg-rose-100'
          : 'border-app-border/30 bg-app-surface-muted text-app-text-secondary hover:border-app-border/50 hover:bg-app-border/20';

        return (
          <button
            type="button"
            key={answer}
            disabled={disabled}
            className={`${duelButton} text-center font-mono text-xs py-2 px-2 transition-colors ${badgeColor}`}
            onClick={() => onAnswer(answer)}
          >
            {copy[answer]}
          </button>
        );
      })}
    </div>
  );
}

export function AnswerBadge({
  answer,
  timedOut,
  answeredBy,
  copy,
}: {
  answer: HumanAnswer | null;
  timedOut?: boolean;
  answeredBy?: 'player' | 'ai' | null;
  copy: DuelCopy;
}) {
  return <AnswerBubble answer={answer} timedOut={timedOut} answeredBy={answeredBy} copy={copy} />;
}

export function AnswerBubble({
  answer,
  timedOut,
  answeredBy,
  isCorrected,
  copy,
}: {
  answer: HumanAnswer | null;
  timedOut?: boolean;
  answeredBy?: 'player' | 'ai' | null;
  isCorrected?: boolean;
  copy: DuelCopy;
}) {
  const isAiAnswer = answeredBy === 'ai' || (timedOut && Boolean(answer));

  if (!answer && timedOut) {
    return (
      <div className="rounded-sm border border-rose-300 bg-rose-50 px-3.5 py-1.5 text-xs font-medium text-rose-800 flex items-center gap-2 shadow-sm">
        <Clock size={13} />
        <span>{copy.unanswered}</span>
      </div>
    );
  }

  if (!answer) {
    return (
      <div className="rounded-sm border border-amber-300 bg-amber-50 px-3.5 py-1.5 text-xs font-medium text-amber-900 flex items-center gap-2 animate-pulse shadow-sm">
        <Clock size={13} />
        <span>{copy.pending}…</span>
      </div>
    );
  }

  let bubbleStyle = 'border-app-border/30 bg-app-surface-muted text-app-text-secondary';
  let icon = <AlertCircle size={14} className="text-app-text-muted shrink-0" />;
  let label = copy.unknown;

  if (answer === 'yes') {
    bubbleStyle = 'border-app-accent/40 bg-app-accent/10 text-app-accent';
    icon = <Check size={14} className="text-app-accent stroke-[3] shrink-0" />;
    label = copy.yes;
  } else if (answer === 'mostly_yes') {
    bubbleStyle = 'border-teal-700/30 bg-teal-50 text-teal-900';
    icon = <Check size={14} className="text-teal-800 stroke-[2.5] shrink-0" />;
    label = copy.mostly_yes;
  } else if (answer === 'mostly_no') {
    bubbleStyle = 'border-rose-300 bg-rose-50 text-rose-800';
    icon = <X size={14} className="text-rose-700 stroke-[2.5] shrink-0" />;
    label = copy.mostly_no;
  } else if (answer === 'no') {
    bubbleStyle = 'border-rose-300 bg-rose-50 text-rose-800';
    icon = <X size={14} className="text-rose-700 stroke-[3] shrink-0" />;
    label = copy.no;
  }

  return (
    <div className={`rounded-sm border px-3.5 py-1.5 text-xs sm:text-sm font-medium flex items-center gap-2 shadow-sm ${bubbleStyle}`}>
      {icon}
      <span className="font-semibold">{label}</span>
      {isCorrected && (
        <span className="text-[10px] font-mono font-normal tracking-normal text-current opacity-60 italic">
          (corrected)
        </span>
      )}
      {isAiAnswer && (
        <span className="ml-1 text-[9px] font-mono uppercase tracking-wider bg-amber-100 text-amber-900 border border-amber-300 px-1.5 py-0.2 rounded-sm">
          AI
        </span>
      )}
    </div>
  );
}

function ChatHistoryCard({
  item,
  snapshot,
  copy,
  busy,
  correct,
}: {
  item: FriendHistory;
  snapshot: FriendSnapshot;
  copy: DuelCopy;
  busy: boolean;
  correct: (item: FriendHistory, answer: HumanAnswer, observedAiQuestionId?: string) => Promise<boolean>;
}) {
  const [editing, setEditing] = useState(false);

  const isYou = item.player_id === snapshot.you;
  const authorName = snapshot.players.find(p => p.id === item.player_id)?.name || (isYou ? copy.you : 'Friend');
  const responderName = snapshot.players.find(p => p.id === item.subject_id)?.name || (!isYou ? copy.you : 'Friend');

  return (
    <article className="space-y-1.5">
      {item.type === 'question' ? (
        <div className="space-y-1.5">
          {/* Inquirer's Question Message (Speech bubble on right if you, on left if opponent) */}
          <div className={`flex flex-col max-w-[85%] ${isYou ? 'ml-auto items-end' : 'mr-auto items-start'}`}>
            <div className="flex items-center gap-1.5 mb-0.5 px-1 font-mono text-xs text-app-text-muted">
              <span className={isYou ? 'text-app-accent font-semibold' : 'text-blue-700 font-semibold'}>
                {isYou ? copy.you : authorName} · #{String(item.ordinal).padStart(2, '0')}
              </span>
              <span>·</span>
              <span>
                {new Date(item.created_at).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}
              </span>
            </div>
            <div
              className={`rounded-sm px-3.5 py-2 text-xs sm:text-sm font-medium leading-relaxed shadow-sm ${
                isYou
                  ? 'border border-app-accent/30 bg-app-accent/10 text-app-text text-right'
                  : 'border border-blue-200 bg-blue-50 text-app-text text-left'
              }`}
            >
              {item.question}
            </div>
          </div>

          {/* Responder's Answer Message (Speech bubble on opposite side, NO nested outer boxes) */}
          <div className={`flex flex-col max-w-[85%] ${isYou ? 'mr-auto items-start' : 'ml-auto items-end'}`}>
            <div className="flex items-center gap-1 mb-0.5 px-1 font-mono text-xs text-app-text-muted">
              <span>{item.answered_by === 'ai' || (item.timed_out && item.answer) ? 'AI Response' : `${responderName} Response`}</span>
            </div>

            <div className="flex flex-col gap-1">
              <AnswerBubble
                answer={item.answer}
                timedOut={item.timed_out}
                answeredBy={item.answered_by}
                isCorrected={item.revisions.length > 1 || item.revision > 1}
                copy={copy}
              />
              {/* Edit / Correct Answer (if subject is you) */}
              {snapshot.status === 'active' && item.subject_id === snapshot.you && item.answer && (
                <div className="px-1">
                  <button
                    type="button"
                    className="font-mono text-[9px] uppercase tracking-wider text-app-accent hover:text-app-accent-hover transition-colors cursor-pointer"
                    disabled={busy}
                    onClick={() => setEditing(!editing)}
                  >
                    {editing ? copy.cancel : '✎ ' + copy.correctAnswer}
                  </button>
                  {editing && (
                    <div className="mt-1.5 p-2 rounded-sm border border-app-border/20 bg-app-surface-muted shadow-md">
                      <AnswerPicker
                        copy={copy}
                        disabled={busy}
                        onAnswer={newAnswer => {
                          void correct(item, newAnswer).then(ok => {
                            if (ok) setEditing(false);
                          });
                        }}
                      />
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      ) : item.type === 'guess' ? (
        /* Location Guess Attempt Entry */
        <div className="flex flex-col items-center justify-center my-1.5">
          <div
            className={`w-full rounded-sm border p-2.5 text-xs flex items-center justify-between gap-3 shadow-sm ${
              item.correct
                ? 'border-app-accent/30 bg-app-accent/10 text-app-accent'
                : 'border-rose-300 bg-rose-50 text-rose-800'
            }`}
          >
            <div className="flex items-center gap-2 min-w-0">
              {item.correct ? (
                <Trophy size={14} className="text-amber-700 shrink-0" />
              ) : (
                <Target size={14} className="text-rose-700 shrink-0" />
              )}
              <span className="font-mono text-xs text-app-text-secondary shrink-0">
                {isYou ? copy.you : authorName} guessed:
              </span>
              <strong className="text-app-text truncate">{item.entity?.name || 'Location'}</strong>
            </div>
            <span className="font-mono font-semibold text-xs shrink-0">
              {item.correct ? 'Correct' : 'Incorrect'}
            </span>
          </div>
        </div>
      ) : (
        /* Pass Turn Entry */
        <div className="flex items-center justify-center my-1">
          <span className="inline-flex items-center gap-1.5 rounded-sm border border-app-border/20 bg-app-surface-muted px-2.5 py-0.5 font-mono text-[10px] text-app-text-secondary">
            <FastForward size={11} />
            <span>{isYou ? copy.you : authorName} passed turn</span>
          </span>
        </div>
      )}
    </article>
  );
}

export default function DuelHistory({
  snapshot,
  copy,
  busy,
  correct,
}: {
  snapshot: FriendSnapshot;
  copy: DuelCopy;
  busy: boolean;
  correct: (item: FriendHistory, answer: HumanAnswer, observedAiQuestionId?: string) => Promise<boolean>;
}) {
  const [older, setOlder] = useState<FriendHistory[]>([]);
  const [hasMore, setHasMore] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [chatTab, setChatTab] = useState<'yours' | 'opponent'>('yours');

  const scrollRef = useRef<HTMLDivElement>(null);
  

  const combined = useMemo(() => {
    const map = new Map(older.map(item => [item.id, item]));
    for (const item of snapshot.history) {
      const old = map.get(item.id);
      if (!old || item.revision >= old.revision) map.set(item.id, item);
    }
    return map;
  }, [older, snapshot.history]);

  const history = useMemo(() => {
    return [...combined.values()].sort((a, b) => a.ordinal - b.ordinal);
  }, [combined]);

  // Tab 1: Moves initiated by YOU (your inquiries and guesses)
  const yourMoves = useMemo(() => {
    return history.filter(item => item.player_id === snapshot.you);
  }, [history, snapshot.you]);

  // Tab 2: Moves initiated by OPPONENT (friend's inquiries and guesses)
  const opponentMoves = useMemo(() => {
    return history.filter(item => item.player_id !== snapshot.you);
  }, [history, snapshot.you]);

  const opponentName = snapshot.players.find(p => p.id !== snapshot.you)?.name || 'Friend';

  const activeMoves = chatTab === 'yours' ? yourMoves : opponentMoves;

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [history.length, chatTab]);

  let nextBefore = history[0]?.ordinal;
  let gap = false;
  for (let index = history.length - 1; index > 0; index--) {
    if (history[index].ordinal > history[index - 1].ordinal + 1) {
      nextBefore = history[index].ordinal;
      gap = true;
      break;
    }
  }

  const mergePage = (page: FriendHistoryPage) => {
    setOlder(previous => {
      const merged = new Map(previous.map(item => [item.id, item]));
      for (const item of page.history) merged.set(item.id, item);
      return [...merged.values()];
    });
  };

  const correctAndRefresh = async (
    item: FriendHistory,
    answer: HumanAnswer,
    observedAiQuestionId?: string
  ) => {
    if (!(await correct(item, answer, observedAiQuestionId))) return false;
    try {
      mergePage(await friendMatchApi.history(snapshot.id, item.ordinal + 1));
    } catch (cause) {
      setError(friendError(cause, copy.error));
    }
    return true;
  };

  return (
    <div className="flex flex-col flex-1 min-h-0 h-full overflow-hidden">
      {/* 2-Tab Chat Header Switcher */}
      <div className="flex items-center gap-1 border-b border-app-border/20 bg-app-surface-raised px-2 py-1.5 shrink-0">
        <button
          type="button"
          role="tab"
          aria-selected={chatTab === 'yours'}
          onClick={() => setChatTab('yours')}
          className={`flex-1 flex items-center justify-center gap-1.5 py-1 px-2 rounded-sm font-mono text-xs transition-colors cursor-pointer ${
            chatTab === 'yours'
              ? 'bg-app-accent/10 border border-app-accent/30 text-app-accent font-semibold shadow-sm'
              : 'text-app-text-secondary hover:text-app-text hover:bg-app-surface-muted'
          }`}
        >
          <span className="h-1.5 w-1.5 rounded-full bg-app-accent shrink-0" />
          <span className="truncate">Your inquiries</span>
          <span className="font-mono text-[9px] text-app-text-muted shrink-0">({yourMoves.length})</span>
        </button>

        <button
          type="button"
          role="tab"
          aria-selected={chatTab === 'opponent'}
          onClick={() => setChatTab('opponent')}
          className={`flex-1 flex items-center justify-center gap-1.5 py-1 px-2 rounded-sm font-mono text-xs transition-colors cursor-pointer truncate ${
            chatTab === 'opponent'
              ? 'bg-blue-50 border border-blue-200 text-blue-800 font-semibold shadow-sm'
              : 'text-app-text-secondary hover:text-app-text hover:bg-app-surface-muted'
          }`}
        >
          <span className="h-1.5 w-1.5 rounded-full bg-blue-700 shrink-0" />
          <span className="truncate">{opponentName}&apos;s</span>
          <span className="font-mono text-[9px] text-app-text-muted shrink-0">({opponentMoves.length})</span>
        </button>
      </div>

      {/* Chat Messages Stream */}
      <div
        ref={scrollRef}
        onWheel={(e) => e.stopPropagation()}
        onPointerDown={(e) => e.stopPropagation()}
        className="flex-1 min-h-0 overflow-y-auto p-3 space-y-3 text-xs custom-scrollbar overscroll-contain select-text"
      >
        {activeMoves.length === 0 ? (
          <div className="py-8 text-center text-xs text-app-text-muted space-y-1">
            <HelpCircle size={20} className="mx-auto text-app-text-muted mb-1" />
            <p className="font-mono text-[11px] text-app-text-secondary">
              {chatTab === 'yours'
                ? 'No inquiries sent yet.'
                : `No inquiries received from ${opponentName} yet.`}
            </p>
            <p className="text-[11px] text-app-text-muted">
              {chatTab === 'yours'
                ? 'Ask a question or guess a location on your turn.'
                : 'Waiting for your friend to make a move.'}
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {activeMoves.map(item => (
              <ChatHistoryCard
                key={item.id}
                item={item}
                snapshot={snapshot}
                copy={copy}
                busy={busy}
                correct={correctAndRefresh}
              />
            ))}
          </div>
        )}

        {/* Older moves pagination */}
        {(gap || (hasMore ?? snapshot.history_has_more)) && (
          <button
            type="button"
            className={`${duelButton} mt-2 w-full text-xs font-mono py-1`}
            disabled={loading}
            onClick={() => {
              if (loading || nextBefore === undefined) return;
              setLoading(true);
              setError('');
              void friendMatchApi
                .history(snapshot.id, nextBefore)
                .then(page => {
                  mergePage(page);
                  if (!gap) setHasMore(page.history_has_more);
                })
                .catch(cause => setError(friendError(cause, copy.error)))
                .finally(() => setLoading(false));
            }}
          >
            {loading ? copy.loading : copy.older}
          </button>
        )}

        {error && <p role="alert" className="mt-1 text-xs text-rose-700">{error}</p>}
      </div>
    </div>
  );
}
