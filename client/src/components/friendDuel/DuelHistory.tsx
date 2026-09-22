import { useState, useMemo } from 'react';
import {
  HelpCircle,
  Target,
  FastForward,
  User,
  Users,
  Clock,
  Check,
  X,
  AlertCircle,
  Sparkles,
} from 'lucide-react';
import { friendError, friendMatchApi } from '../../services/friendMatchApi';
import type {
  FriendGuidance,
  FriendHistory,
  FriendHistoryPage,
  FriendSnapshot,
  HumanAnswer,
} from '../../types/friendMatch';
import { duelButton, duelInput, duelPanel, duelPrimary, humanAnswers } from './copy';
import type { DuelCopy } from './copy';

export function PrivateAdvice({ guidance, copy }: { guidance?: FriendGuidance; copy: DuelCopy }) {
  return (
    <aside className="rounded-sm border border-emerald-500/20 bg-emerald-950/20 p-3 sm:p-4" aria-label={copy.ai}>
      <div className="flex items-center gap-1.5 text-xs font-medium text-emerald-300">
        <Sparkles size={14} className="text-emerald-400" />
        <h3>{copy.ai}</h3>
      </div>
      <p className="mt-1 text-xs leading-5 text-zinc-400">{copy.aiHelp}</p>
      <div className="mt-3 text-sm" aria-live="polite">
        {!guidance || guidance.status === 'pending' || guidance.status === 'running' ? (
          <p className="flex items-center gap-2 text-zinc-400">
            <span className="inline-block h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
            {copy.aiPending}
          </p>
        ) : guidance.status === 'failed' ? (
          <p className="text-amber-300">{copy.aiFailed}</p>
        ) : (
          <div className="space-y-2">
            {guidance.answer && (
              <span className="inline-flex items-center gap-1 rounded bg-emerald-500/20 px-2 py-0.5 font-mono text-xs font-semibold text-emerald-300 border border-emerald-500/30">
                {copy[guidance.answer]}
              </span>
            )}
            <p className="whitespace-pre-wrap break-words text-xs text-zinc-300 leading-relaxed">
              {guidance.explanation || copy.aiNoExplanation}
            </p>
            {guidance.source && (
              <p className="break-words text-[11px] text-zinc-500">
                {copy.source}: <span className="text-zinc-400">{guidance.source}</span>
              </p>
            )}
          </div>
        )}
        {guidance?.late && <p className="mt-2 text-xs text-amber-300">{copy.late}</p>}
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
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3" role="group" aria-label={copy.answering}>
      {humanAnswers.map(answer => {
        const isYes = answer === 'yes' || answer === 'mostly_yes';
        const isNo = answer === 'no' || answer === 'mostly_no';
        const badgeColor = isYes
          ? 'hover:border-emerald-400 hover:bg-emerald-500/10 hover:text-emerald-300'
          : isNo
          ? 'hover:border-rose-400 hover:bg-rose-500/10 hover:text-rose-300'
          : 'hover:border-zinc-400 hover:bg-white/5 hover:text-sand-100';

        return (
          <button
            type="button"
            key={answer}
            disabled={disabled}
            className={`${duelButton} text-center font-medium transition-all ${badgeColor}`}
            onClick={() => onAnswer(answer)}
          >
            {copy[answer]}
          </button>
        );
      })}
    </div>
  );
}

function AnswerBadge({ answer, timedOut, copy }: { answer: HumanAnswer | null; timedOut?: boolean; copy: DuelCopy }) {
  if (timedOut) {
    return (
      <span className="inline-flex items-center gap-1 rounded bg-rose-950/70 border border-rose-500/40 px-2.5 py-1 text-xs font-semibold text-rose-300">
        <Clock size={12} />
        {copy.unanswered}
      </span>
    );
  }

  if (!answer) {
    return (
      <span className="inline-flex items-center gap-1 rounded bg-amber-950/50 border border-amber-500/40 px-2.5 py-1 text-xs font-semibold text-amber-300 animate-pulse">
        <Clock size={12} />
        {copy.pending}
      </span>
    );
  }

  switch (answer) {
    case 'yes':
      return (
        <span className="inline-flex items-center gap-1 rounded bg-emerald-950/80 border border-emerald-500/50 px-2.5 py-1 text-xs font-bold text-emerald-300 shadow-sm">
          <Check size={14} className="stroke-[3]" />
          {copy.yes.toUpperCase()}
        </span>
      );
    case 'mostly_yes':
      return (
        <span className="inline-flex items-center gap-1 rounded bg-teal-950/70 border border-teal-500/40 px-2.5 py-1 text-xs font-semibold text-teal-300">
          <Check size={13} />
          {copy.mostly_yes}
        </span>
      );
    case 'no':
      return (
        <span className="inline-flex items-center gap-1 rounded bg-rose-950/80 border border-rose-500/50 px-2.5 py-1 text-xs font-bold text-rose-300 shadow-sm">
          <X size={14} className="stroke-[3]" />
          {copy.no.toUpperCase()}
        </span>
      );
    case 'mostly_no':
      return (
        <span className="inline-flex items-center gap-1 rounded bg-rose-950/50 border border-rose-400/30 px-2.5 py-1 text-xs font-semibold text-rose-300">
          <X size={13} />
          {copy.mostly_no}
        </span>
      );
    case 'unknown':
      return (
        <span className="inline-flex items-center gap-1 rounded bg-zinc-800 border border-zinc-600 px-2.5 py-1 text-xs font-semibold text-zinc-300">
          <AlertCircle size={13} />
          {copy.unknown}
        </span>
      );
  }
}

function HistoryCard({
  item,
  snapshot,
  copy,
  busy,
  correct,
  guidance,
}: {
  item: FriendHistory;
  snapshot: FriendSnapshot;
  copy: DuelCopy;
  busy: boolean;
  guidance?: FriendGuidance;
  correct: (item: FriendHistory, answer: HumanAnswer, observedAiQuestionId?: string) => Promise<boolean>;
}) {
  const [editing, setEditing] = useState(false);
  const [reporting, setReporting] = useState(false);
  const [report, setReport] = useState('');
  const [reportBusy, setReportBusy] = useState(false);
  const [reportError, setReportError] = useState('');
  const [reported, setReported] = useState(false);

  const isYou = item.player_id === snapshot.you;
  const authorName = snapshot.players.find(p => p.id === item.player_id)?.name || (isYou ? copy.you : 'Friend');

  return (
    <article
      className={`relative overflow-hidden rounded-sm border p-3 transition-all ${
        isYou
          ? 'border-l-4 border-l-emerald-400 border-white/10 bg-emerald-950/15 hover:border-l-emerald-300 ml-auto max-w-[92%]'
          : 'border-l-4 border-l-blue-400 border-white/10 bg-blue-950/15 hover:border-l-blue-300 mr-auto max-w-[92%]'
      }`}
    >
      {/* Header: Author badge, type badge, timestamp */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/5 pb-2 text-xs">
        <div className="flex items-center gap-2">
          <span
            className={`flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold tracking-wide ${
              isYou ? 'bg-emerald-500/20 text-emerald-300' : 'bg-blue-500/20 text-blue-300'
            }`}
          >
            <User size={11} />
            {isYou ? copy.you : authorName}
          </span>
          <span className="flex items-center gap-1 font-mono text-[10px] uppercase tracking-wider text-zinc-500">
            {item.type === 'question' ? (
              <>
                <HelpCircle size={11} className={isYou ? 'text-emerald-400' : 'text-blue-400'} />
                {copy.question}
              </>
            ) : item.type === 'guess' ? (
              <>
                <Target size={11} className={isYou ? 'text-emerald-400' : 'text-blue-400'} />
                {copy.guess}
              </>
            ) : (
              <>
                <FastForward size={11} className="text-zinc-400" />
                {copy.passed}
              </>
            )}
          </span>
        </div>
        <time dateTime={item.created_at} className="font-mono text-[11px] text-zinc-500">
          {new Date(item.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </time>
      </div>

      {/* Main Content */}
      <div className="mt-3">
        {item.type === 'question' ? (
          <div className="space-y-2.5">
            <p className={`whitespace-pre-wrap break-words text-xs sm:text-sm font-medium text-sand-100 leading-snug ${isYou ? 'text-right' : 'text-left'}`}>
              {item.question}
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs text-zinc-400">
                {isYou ? copy.waitingForAnswer : copy.answering}:
              </span>
              <AnswerBadge answer={item.answer} timedOut={item.timed_out} copy={copy} />
            </div>

            {/* Revisions history */}
            {item.revisions.length > 1 && (
              <details className="rounded border border-white/5 bg-black/20 p-2 text-xs text-zinc-400">
                <summary className="cursor-pointer hover:text-zinc-200">
                  {copy.revision} {item.revision} ({item.revisions.length} updates)
                </summary>
                <ol className="mt-2 space-y-1 pl-2 border-l border-zinc-700">
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
              <div className="pt-1">
                <button
                  type="button"
                  className={`${duelButton} text-xs py-1 px-2.5`}
                  disabled={busy}
                  onClick={() => setEditing(!editing)}
                >
                  {editing ? copy.cancel : copy.correctAnswer}
                </button>
                {editing && (
                  <div className="mt-3 space-y-3 rounded border border-white/10 bg-black/30 p-3">
                    <p className="text-xs text-zinc-300 font-medium">{copy.saveCorrection}:</p>
                    <AnswerPicker
                      disabled={busy}
                      copy={copy}
                      onAnswer={answer => {
                        void correct(
                          item,
                          answer,
                          guidance?.status === 'completed' ? item.id : undefined
                        ).then(saved => {
                          if (saved) setEditing(false);
                        });
                      }}
                    />
                    <PrivateAdvice guidance={guidance} copy={copy} />
                  </div>
                )}
              </div>
            )}

            {/* Report form (after duel ended) */}
            {snapshot.status === 'finished' && (
              <div className="pt-1">
                {reported ? (
                  <p role="status" className="text-xs text-emerald-300 flex items-center gap-1">
                    <Check size={12} />
                    {copy.reported}
                  </p>
                ) : (
                  <>
                    <button
                      type="button"
                      className={`${duelButton} text-xs py-1 px-2.5 text-zinc-400`}
                      onClick={() => setReporting(!reporting)}
                    >
                      {reporting ? copy.cancel : copy.report}
                    </button>
                    {reporting && (
                      <form
                        className="mt-3 space-y-2 rounded border border-white/10 bg-black/30 p-3"
                        onSubmit={event => {
                          event.preventDefault();
                          if (reportBusy || report.trim().length < 3) return;
                          setReportBusy(true);
                          setReportError('');
                          void friendMatchApi
                            .report(snapshot.id, item.id, report.trim())
                            .then(() => {
                              setReported(true);
                              setReporting(false);
                            })
                            .catch(cause => setReportError(friendError(cause, copy.error)))
                            .finally(() => setReportBusy(false));
                        }}
                      >
                        <label className="block text-xs text-zinc-300" htmlFor={`report-${item.id}`}>
                          {copy.reportHelp}
                        </label>
                        <textarea
                          id={`report-${item.id}`}
                          className={`${duelInput} text-xs`}
                          value={report}
                          minLength={3}
                          maxLength={2000}
                          required
                          rows={2}
                          onChange={event => setReport(event.target.value)}
                          disabled={reportBusy}
                        />
                        {reportError && <p role="alert" className="text-xs text-red-300">{reportError}</p>}
                        <button
                          className={`${duelPrimary} text-xs py-1 px-3`}
                          disabled={reportBusy || report.trim().length < 3}
                        >
                          {copy.sendReport}
                        </button>
                      </form>
                    )}
                  </>
                )}
              </div>
            )}
          </div>
        ) : item.type === 'guess' ? (
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Target size={18} className={isYou ? 'text-emerald-400' : 'text-blue-400'} />
              <p className="text-base font-semibold text-sand-100">{item.entity?.name}</p>
            </div>
            {item.correct ? (
              <span className="inline-flex items-center gap-1 rounded bg-emerald-500 text-obsidian-950 px-2.5 py-1 text-xs font-bold shadow-md">
                <Check size={14} className="stroke-[3]" />
                {copy.correct}
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 rounded bg-rose-950/80 border border-rose-500/50 px-2.5 py-1 text-xs font-semibold text-rose-300">
                <X size={14} />
                {copy.incorrect}
              </span>
            )}
          </div>
        ) : (
          <p className="text-xs text-zinc-400 italic">
            {item.timed_out ? copy.timedOut : copy.passed}
          </p>
        )}
      </div>
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
  const [olderGuidance, setOlderGuidance] = useState<FriendGuidance[]>([]);
  const [hasMore, setHasMore] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [filterTab, setFilterTab] = useState<'all' | 'you' | 'opponent'>('all');

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

  const guidanceById = useMemo(() => {
    const map = new Map(olderGuidance.map(item => [item.question_id, item]));
    for (const item of snapshot.guidance) {
      const old = map.get(item.question_id);
      if (
        !old ||
        old.status === 'pending' ||
        old.status === 'running' ||
        item.status === 'completed' ||
        item.status === 'failed'
      ) {
        map.set(item.question_id, item);
      }
    }
    return map;
  }, [olderGuidance, snapshot.guidance]);

  const guidance = useMemo(() => [...guidanceById.values()], [guidanceById]);

  // Counts for tabs
  const youMovesCount = useMemo(() => history.filter(item => item.player_id === snapshot.you).length, [history, snapshot.you]);
  const opponentMovesCount = useMemo(() => history.filter(item => item.player_id !== snapshot.you).length, [history, snapshot.you]);

  // Filtered list
  const filteredHistory = useMemo(() => {
    if (filterTab === 'you') {
      return history.filter(item => item.player_id === snapshot.you);
    }
    if (filterTab === 'opponent') {
      return history.filter(item => item.player_id !== snapshot.you);
    }
    return history;
  }, [history, filterTab, snapshot.you]);

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
    setOlderGuidance(previous => {
      const merged = new Map(previous.map(item => [item.question_id, item]));
      for (const item of page.guidance || []) merged.set(item.question_id, item);
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

  const opponentName = snapshot.players.find(p => p.id !== snapshot.you)?.name || copy.friendMoves;

  return (
    <div className="space-y-4">
      <section className={duelPanel} aria-label={copy.intelHistory}>
        {/* Header with Title and Filter Tabs */}
        <div className="border-b border-white/10 pb-3">
          <div className="flex items-center justify-between gap-2 mb-3">
            <h2 className="flex items-center gap-2 text-sm font-semibold text-sand-100">
              <Users size={16} className="text-emerald-400" />
              {copy.intelHistory}
            </h2>
            <span className="font-mono text-xs text-zinc-400">
              {history.length} {history.length === 1 ? 'move' : 'moves'}
            </span>
          </div>

          {/* Filter Tabs: All | Your Moves | Friend's Moves */}
          <div className="flex rounded-sm bg-obsidian-950 p-1 border border-white/10" role="tablist">
            <button
              type="button"
              role="tab"
              aria-selected={filterTab === 'all'}
              className={`flex-1 rounded-sm py-1.5 px-2 text-xs font-medium transition-colors ${
                filterTab === 'all'
                  ? 'bg-zinc-800 text-sand-100 shadow-sm'
                  : 'text-zinc-400 hover:text-sand-100'
              }`}
              onClick={() => setFilterTab('all')}
            >
              {copy.allMoves} ({history.length})
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={filterTab === 'you'}
              className={`flex-1 rounded-sm py-1.5 px-2 text-xs font-medium transition-colors flex items-center justify-center gap-1.5 ${
                filterTab === 'you'
                  ? 'bg-emerald-950 text-emerald-300 border border-emerald-500/40 shadow-sm'
                  : 'text-zinc-400 hover:text-emerald-300'
              }`}
              onClick={() => setFilterTab('you')}
            >
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
              {copy.yourMoves} ({youMovesCount})
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={filterTab === 'opponent'}
              className={`flex-1 rounded-sm py-1.5 px-2 text-xs font-medium transition-colors flex items-center justify-center gap-1.5 truncate ${
                filterTab === 'opponent'
                  ? 'bg-blue-950 text-blue-300 border border-blue-500/40 shadow-sm'
                  : 'text-zinc-400 hover:text-blue-300'
              }`}
              onClick={() => setFilterTab('opponent')}
            >
              <span className="h-1.5 w-1.5 rounded-full bg-blue-400" />
              <span className="truncate">{opponentName} ({opponentMovesCount})</span>
            </button>
          </div>
        </div>

        {/* Moves Feed */}
        <div className="mt-3">
          {filteredHistory.length === 0 ? (
            <div className="py-8 text-center text-xs text-zinc-500">
              <p>{copy.noHistory}</p>
              <p className="mt-1 text-zinc-600">{copy.noQuestions}</p>
            </div>
          ) : (
            <ol className="space-y-3 max-h-[38rem] overflow-y-auto pr-1">
              {[...filteredHistory].reverse().map(item => (
                <li key={item.id}>
                  <HistoryCard
                    item={item}
                    snapshot={snapshot}
                    copy={copy}
                    busy={busy}
                    correct={correctAndRefresh}
                    guidance={guidanceById.get(item.id)}
                  />
                </li>
              ))}
            </ol>
          )}

          {/* Older moves pagination */}
          {(gap || (hasMore ?? snapshot.history_has_more)) && (
            <button
              type="button"
              className={`${duelButton} mt-3 w-full text-xs`}
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

          {error && <p role="alert" className="mt-2 text-xs text-red-300">{error}</p>}
        </div>
      </section>

      {/* Private AI Guidance History */}
      {guidance.length > 0 && (
        <details className={duelPanel}>
          <summary className="cursor-pointer font-medium text-xs text-zinc-400 hover:text-sand-100 flex items-center gap-1.5">
            <Sparkles size={14} className="text-emerald-400" />
            {copy.privateHistory} ({guidance.length})
          </summary>
          <p className="mt-2 text-xs text-zinc-500">{copy.privateHistoryHelp}</p>
          <div className="mt-3 space-y-3 max-h-72 overflow-y-auto pr-1">
            {guidance.map(item => {
              const question = combined.get(item.question_id);
              return (
                <div key={item.question_id} className="rounded border border-white/5 bg-black/20 p-2.5">
                  {question && (
                    <p className="mb-2 whitespace-pre-wrap break-words text-xs font-medium text-sand-100">
                      "{question.question}"
                    </p>
                  )}
                  <PrivateAdvice guidance={item} copy={copy} />
                </div>
              );
            })}
          </div>
        </details>
      )}
    </div>
  );
}
