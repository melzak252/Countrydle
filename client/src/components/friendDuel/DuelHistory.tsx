import { useState, useMemo, useRef, useEffect } from 'react';
import {
  Target,
  FastForward,
  Clock,
  Check,
  X,
  AlertCircle,
  Sparkles,
  Bot,
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
    <aside className="rounded-sm border border-emerald-500/20 bg-emerald-950/20 p-3 sm:p-4" aria-label={copy.ai}>
      <div className="flex items-center gap-1.5 text-xs font-medium text-emerald-300">
        <Sparkles size={14} className="text-emerald-400" />
        <h3 className="font-mono uppercase tracking-wider text-[11px]">{copy.ai}</h3>
      </div>
      <p className="mt-1 text-xs leading-relaxed text-zinc-400">{copy.aiHelp}</p>
      <div className="mt-2.5 text-xs" aria-live="polite">
        {!guidance || guidance.status === 'pending' || guidance.status === 'running' ? (
          <p className="flex items-center gap-2 text-zinc-400 font-mono text-[11px]">
            <span className="inline-block h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
            {copy.aiPending}
          </p>
        ) : guidance.status === 'failed' ? (
          <p className="text-amber-300 font-mono text-[11px]">{copy.aiFailed}</p>
        ) : (
          <div className="space-y-1.5">
            {guidance.answer && (
              <span className="inline-flex items-center gap-1 rounded bg-emerald-500/20 px-2 py-0.5 font-mono text-xs font-bold text-emerald-300 border border-emerald-500/30">
                {copy[guidance.answer]}
              </span>
            )}
            <p className="whitespace-pre-wrap break-words text-xs text-zinc-300 leading-relaxed">
              {guidance.explanation || copy.aiNoExplanation}
            </p>
            {guidance.source && (
              <p className="break-words text-[10px] font-mono text-zinc-500">
                {copy.source}: <span className="text-zinc-400">{guidance.source}</span>
              </p>
            )}
          </div>
        )}
        {guidance?.late && <p className="mt-2 text-xs text-amber-300 font-mono text-[11px]">{copy.late}</p>}
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
          ? 'border-emerald-500/30 bg-emerald-950/60 text-emerald-300 hover:border-emerald-400 hover:bg-emerald-500/20'
          : isNo
          ? 'border-rose-500/30 bg-rose-950/60 text-rose-300 hover:border-rose-400 hover:bg-rose-500/20'
          : 'border-zinc-700 bg-zinc-900 text-zinc-300 hover:border-zinc-500 hover:bg-zinc-800';

        return (
          <button
            type="button"
            key={answer}
            disabled={disabled}
            className={`${duelButton} text-center font-mono text-xs uppercase tracking-wider py-2 px-2 transition-all ${badgeColor}`}
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
  const isAiAnswer = answeredBy === 'ai' || (timedOut && Boolean(answer));

  if (isAiAnswer && answer) {
    return (
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="inline-flex items-center gap-1 rounded bg-amber-950/70 border border-amber-500/40 px-2 py-0.5 text-[10px] font-mono font-semibold text-amber-300">
          <Bot size={12} className="text-amber-400" />
          <span>{copy.aiAnswered || '🤖 AI Answer (Time expired)'}:</span>
          <strong className="uppercase text-amber-200">{copy[answer]}</strong>
        </span>
      </div>
    );
  }

  if (timedOut && !answer) {
    return (
      <span className="inline-flex items-center gap-1 rounded bg-rose-950/70 border border-rose-500/40 px-2.5 py-0.5 font-mono text-[10px] font-semibold text-rose-300">
        <Clock size={11} />
        {copy.unanswered}
      </span>
    );
  }

  if (!answer) {
    return (
      <span className="inline-flex items-center gap-1 rounded bg-amber-950/50 border border-amber-500/40 px-2.5 py-0.5 font-mono text-[10px] font-semibold text-amber-300 animate-pulse">
        <Clock size={11} />
        {copy.pending}
      </span>
    );
  }

  switch (answer) {
    case 'yes':
      return (
        <span className="inline-flex items-center gap-1 rounded bg-emerald-950/80 border border-emerald-500/50 px-2.5 py-0.5 font-mono text-[10px] font-bold text-emerald-300 shadow-sm uppercase tracking-wider">
          <Check size={13} className="stroke-[3]" />
          {copy.yes}
        </span>
      );
    case 'mostly_yes':
      return (
        <span className="inline-flex items-center gap-1 rounded bg-teal-950/70 border border-teal-500/40 px-2.5 py-0.5 font-mono text-[10px] font-semibold text-teal-300 shadow-sm uppercase tracking-wider">
          <Check size={12} />
          {copy.mostly_yes}
        </span>
      );
    case 'no':
      return (
        <span className="inline-flex items-center gap-1 rounded bg-rose-950/80 border border-rose-500/50 px-2.5 py-0.5 font-mono text-[10px] font-bold text-rose-300 shadow-sm uppercase tracking-wider">
          <X size={13} className="stroke-[3]" />
          {copy.no}
        </span>
      );
    case 'mostly_no':
      return (
        <span className="inline-flex items-center gap-1 rounded bg-rose-950/50 border border-rose-400/30 px-2.5 py-0.5 font-mono text-[10px] font-semibold text-rose-300 shadow-sm uppercase tracking-wider">
          <X size={12} />
          {copy.mostly_no}
        </span>
      );
    case 'unknown':
      return (
        <span className="inline-flex items-center gap-1 rounded bg-zinc-800 border border-zinc-600 px-2.5 py-0.5 font-mono text-[10px] font-semibold text-zinc-300 uppercase tracking-wider">
          <AlertCircle size={12} />
          {copy.unknown}
        </span>
      );
  }
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
    <article className="space-y-1.5 transition-all">
      {item.type === 'question' ? (
        <div className="space-y-2">
          {/* Inquirer's Question Message (Right-aligned if you asked, left-aligned if friend asked) */}
          <div className={`flex flex-col max-w-[88%] ${isYou ? 'ml-auto items-end' : 'mr-auto items-start'}`}>
            <div className="flex items-center gap-2 mb-1 font-mono text-[9px] uppercase tracking-[0.16em] text-zinc-400">
              <span className="font-semibold text-emerald-400">
                {isYou ? copy.you : authorName} · #{String(item.ordinal).padStart(2, '0')}
              </span>
              <span className="text-zinc-500">
                {new Date(item.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
            </div>
            <div
              className={`rounded-sm px-3.5 py-2 text-xs sm:text-sm font-medium leading-relaxed shadow-sm ${
                isYou
                  ? 'border border-emerald-500/25 bg-emerald-500/15 text-sand-100'
                  : 'border border-blue-500/25 bg-blue-500/15 text-sand-100'
              }`}
            >
              {item.question}
            </div>
          </div>

          {/* Responder's Answer Card (Opposite alignment) */}
          <div className={`flex flex-col max-w-[88%] ${isYou ? 'mr-auto items-start' : 'ml-auto items-end'}`}>
            <div className="flex items-center gap-1.5 mb-1 font-mono text-[9px] uppercase tracking-[0.16em] text-zinc-400">
              <span>{item.answered_by === 'ai' || (item.timed_out && item.answer) ? '🤖 AI' : responderName}:</span>
            </div>

            <div className="rounded-sm border border-white/10 bg-obsidian-950/80 px-3 py-2 space-y-1.5 shadow-sm">
              <AnswerBadge
                answer={item.answer}
                timedOut={item.timed_out}
                answeredBy={item.answered_by}
                copy={copy}
              />

              {/* Revisions history */}
              {item.revisions.length > 1 && (
                <details className="rounded border border-white/5 bg-black/20 p-1.5 text-[10px] text-zinc-400">
                  <summary className="cursor-pointer hover:text-zinc-200 font-mono">
                    {copy.revision} {item.revision} ({item.revisions.length} updates)
                  </summary>
                  <ol className="mt-1 space-y-0.5 pl-2 border-l border-zinc-700">
                    {item.revisions.map(rev => (
                      <li key={rev.revision}>
                        v{rev.revision}: <strong className="text-sand-100">{copy[rev.answer]}</strong>
                      </li>
                    ))}
                  </ol>
                </details>
              )}

              {/* Edit / Correct Answer (if subject is you) */}
              {snapshot.status === 'active' && item.subject_id === snapshot.you && item.answer && (
                <div className="pt-1 border-t border-white/5">
                  <button
                    type="button"
                    className="font-mono text-[9px] uppercase tracking-wider text-emerald-400 hover:text-emerald-300 transition-colors cursor-pointer"
                    disabled={busy}
                    onClick={() => setEditing(!editing)}
                  >
                    {editing ? copy.cancel : copy.correctAnswer}
                  </button>
                  {editing && (
                    <div className="mt-2 space-y-2 border-t border-white/10 pt-2">
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
                ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300'
                : 'border-rose-500/40 bg-rose-500/10 text-rose-300'
            }`}
          >
            <div className="flex items-center gap-2 min-w-0">
              {item.correct ? (
                <Trophy size={14} className="text-amber-400 shrink-0" />
              ) : (
                <Target size={14} className="text-rose-400 shrink-0" />
              )}
              <span className="font-mono text-[10px] uppercase tracking-wider text-zinc-400 shrink-0">
                {isYou ? copy.you : authorName} guessed:
              </span>
              <strong className="text-sand-100 truncate">{item.entity?.name || 'Location'}</strong>
            </div>
            <span className="font-mono font-bold text-[10px] uppercase tracking-wider shrink-0">
              {item.correct ? 'Correct! 🎉' : 'Incorrect'}
            </span>
          </div>
        </div>
      ) : (
        /* Pass Turn Entry */
        <div className="flex items-center justify-center my-1">
          <span className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/5 px-2.5 py-0.5 font-mono text-[10px] text-zinc-400">
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
  const prevCount = useRef(snapshot.history.length);

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

  // Auto-scroll inside container ONLY when new items arrive
  useEffect(() => {
    if (history.length > prevCount.current) {
      prevCount.current = history.length;
      if (scrollRef.current) {
        scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
      }
    } else {
      prevCount.current = history.length;
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
    <div className="flex flex-col h-full">
      {/* 2-Tab Chat Header Switcher */}
      <div className="flex items-center gap-1 border-b border-white/10 bg-obsidian-950/80 px-2 py-1.5 shrink-0">
        <button
          type="button"
          role="tab"
          aria-selected={chatTab === 'yours'}
          onClick={() => setChatTab('yours')}
          className={`flex-1 flex items-center justify-center gap-1.5 py-1 px-2 rounded-sm font-mono text-[10px] uppercase tracking-[0.16em] transition-all cursor-pointer ${
            chatTab === 'yours'
              ? 'bg-emerald-950/80 border border-emerald-500/40 text-emerald-300 font-semibold shadow-sm'
              : 'text-zinc-400 hover:text-sand-100 hover:bg-white/5'
          }`}
        >
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 shrink-0" />
          <span className="truncate">Your inquiries</span>
          <span className="font-mono text-[9px] text-zinc-500 shrink-0">({yourMoves.length})</span>
        </button>

        <button
          type="button"
          role="tab"
          aria-selected={chatTab === 'opponent'}
          onClick={() => setChatTab('opponent')}
          className={`flex-1 flex items-center justify-center gap-1.5 py-1 px-2 rounded-sm font-mono text-[10px] uppercase tracking-[0.16em] transition-all cursor-pointer truncate ${
            chatTab === 'opponent'
              ? 'bg-blue-950/80 border border-blue-500/40 text-blue-300 font-semibold shadow-sm'
              : 'text-zinc-400 hover:text-sand-100 hover:bg-white/5'
          }`}
        >
          <span className="h-1.5 w-1.5 rounded-full bg-blue-400 shrink-0" />
          <span className="truncate">{opponentName}&apos;s</span>
          <span className="font-mono text-[9px] text-zinc-500 shrink-0">({opponentMoves.length})</span>
        </button>
      </div>

      {/* Chat Messages Stream */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-3 space-y-3 text-xs custom-scrollbar"
      >
        {activeMoves.length === 0 ? (
          <div className="py-8 text-center text-xs text-zinc-500 space-y-1">
            <HelpCircle size={20} className="mx-auto text-zinc-600 mb-1" />
            <p className="font-mono text-[11px] text-zinc-400">
              {chatTab === 'yours'
                ? 'No inquiries sent yet.'
                : `No inquiries received from ${opponentName} yet.`}
            </p>
            <p className="text-[11px] text-zinc-600">
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

        {error && <p role="alert" className="mt-1 text-xs text-red-300">{error}</p>}
      </div>
    </div>
  );
}
