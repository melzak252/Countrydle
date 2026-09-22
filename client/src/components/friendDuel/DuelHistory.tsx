import { useState } from 'react';
import { friendError, friendMatchApi } from '../../services/friendMatchApi';
import type { FriendGuidance, FriendHistory, FriendHistoryPage, FriendSnapshot, HumanAnswer } from '../../types/friendMatch';
import { duelButton, duelInput, duelPanel, duelPrimary, humanAnswers } from './copy';
import type { DuelCopy } from './copy';

export function PrivateAdvice({ guidance, copy }: { guidance?: FriendGuidance; copy: DuelCopy }) {
  return <aside className="rounded-sm border border-white/10 bg-white/[0.02] p-3" aria-label={copy.ai}>
    <h3 className="text-xs font-medium text-emerald-300">{copy.ai}</h3>
    <p className="mt-1 text-xs leading-5 text-zinc-500">{copy.aiHelp}</p>
    <div className="mt-3 text-sm" aria-live="polite">
      {!guidance || guidance.status === 'pending' || guidance.status === 'running' ? <p>{copy.aiPending}</p> :
        guidance.status === 'failed' ? <p className="text-amber-200">{copy.aiFailed}</p> : <>
          {guidance.answer && <strong>{copy[guidance.answer]}</strong>}
          <p className="mt-1 whitespace-pre-wrap break-words text-zinc-300">{guidance.explanation || copy.aiNoExplanation}</p>
          {guidance.source && <p className="mt-2 break-words text-xs text-zinc-500">{copy.source}: {guidance.source}</p>}
        </>}
      {guidance?.late && <p className="mt-2 text-xs text-amber-300">{copy.late}</p>}
    </div>
  </aside>;
}

export function AnswerPicker({ disabled, copy, onAnswer }: { disabled: boolean; copy: DuelCopy; onAnswer: (answer: HumanAnswer) => void }) {
  return <div className="grid grid-cols-2 gap-2 sm:grid-cols-3" role="group" aria-label={copy.answering}>
    {humanAnswers.map(answer => <button type="button" key={answer} disabled={disabled} className={`${duelButton} text-left hover:border-emerald-400/50 hover:text-emerald-300`}
      onClick={() => onAnswer(answer)}>{copy[answer]}</button>)}
  </div>;
}

function HistoryMove({ item, snapshot, copy, busy, correct, guidance }: {
  item: FriendHistory; snapshot: FriendSnapshot; copy: DuelCopy; busy: boolean; guidance?: FriendGuidance;
  correct: (item: FriendHistory, answer: HumanAnswer, observedAiQuestionId?: string) => Promise<boolean>;
}) {
  const [editing, setEditing] = useState(false);
  const [reporting, setReporting] = useState(false);
  const [report, setReport] = useState('');
  const [reportBusy, setReportBusy] = useState(false);
  const [reportError, setReportError] = useState('');
  const [reported, setReported] = useState(false);
  const author = snapshot.players.find(player => player.id === item.player_id)?.name;
  return <li className="space-y-2 border-t border-white/10 py-4 first:border-t-0">
    <div className="flex flex-wrap justify-between gap-2 text-xs text-zinc-400">
      <span>{author}{item.player_id === snapshot.you ? ` · ${copy.you}` : ''}</span>
      <time dateTime={item.created_at}>{new Date(item.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</time>
    </div>
    {item.type === 'question' ? <>
      <p className="whitespace-pre-wrap break-words">{item.question}</p>
      <p className="font-medium text-emerald-300">{item.answer ? copy[item.answer] : item.timed_out ? copy.unanswered : copy.pending}</p>
      {item.revisions.length > 1 && <details className="text-xs text-zinc-400">
        <summary className="cursor-pointer">{copy.revision} {item.revision}</summary>
        <ol className="mt-2 space-y-1">{item.revisions.map(revision => <li key={revision.revision}>
          {copy.revision} {revision.revision}: {copy[revision.answer]}
        </li>)}</ol>
      </details>}
      {snapshot.status === 'active' && item.subject_id === snapshot.you && item.answer && <>
        <button type="button" className={duelButton} disabled={busy} onClick={() => setEditing(!editing)}>{editing ? copy.cancel : copy.correctAnswer}</button>
        {editing && <div className="space-y-3">
          <AnswerPicker disabled={busy} copy={copy} onAnswer={answer => {
            void correct(item, answer, guidance?.status === 'completed' ? item.id : undefined).then(saved => { if (saved) setEditing(false); });
          }} />
          <PrivateAdvice guidance={guidance} copy={copy} />
        </div>}
      </>}
      {snapshot.status === 'finished' && <div>
        {reported ? <p role="status" className="text-sm text-emerald-300">{copy.reported}</p> : <>
          <button type="button" className={duelButton} onClick={() => setReporting(!reporting)}>{reporting ? copy.cancel : copy.report}</button>
          {reporting && <form className="mt-3 space-y-2" onSubmit={event => {
            event.preventDefault();
            if (reportBusy || report.trim().length < 3) return;
            setReportBusy(true); setReportError('');
            void friendMatchApi.report(snapshot.id, item.id, report.trim())
              .then(() => { setReported(true); setReporting(false); })
              .catch(cause => setReportError(friendError(cause, copy.error)))
              .finally(() => setReportBusy(false));
          }}>
            <label className="block text-sm" htmlFor={`report-${item.id}`}>{copy.reportHelp}</label>
            <textarea id={`report-${item.id}`} className={duelInput} value={report} minLength={3} maxLength={2000} required rows={3}
              onChange={event => setReport(event.target.value)} disabled={reportBusy} />
            {reportError && <p role="alert" className="text-sm text-red-300">{reportError}</p>}
            <button className={duelPrimary} disabled={reportBusy || report.trim().length < 3}>{copy.sendReport}</button>
          </form>}
        </>}
      </div>}
    </> : item.type === 'guess' ? <>
      <p>{item.entity?.name}</p>
      <p className={item.correct ? 'text-emerald-300' : 'text-amber-200'}>{item.correct ? copy.correct : copy.incorrect}</p>
    </> : <p>{item.timed_out ? copy.timedOut : copy.passed}</p>}
  </li>;
}

export default function DuelHistory({ snapshot, copy, busy, correct }: {
  snapshot: FriendSnapshot; copy: DuelCopy; busy: boolean;
  correct: (item: FriendHistory, answer: HumanAnswer, observedAiQuestionId?: string) => Promise<boolean>;
}) {
  const [older, setOlder] = useState<FriendHistory[]>([]);
  const [olderGuidance, setOlderGuidance] = useState<FriendGuidance[]>([]);
  const [hasMore, setHasMore] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const combined = new Map(older.map(item => [item.id, item]));
  for (const item of snapshot.history) {
    const old = combined.get(item.id);
    if (!old || item.revision >= old.revision) combined.set(item.id, item);
  }
  const history = [...combined.values()].sort((a, b) => a.ordinal - b.ordinal);
  const guidanceById = new Map(olderGuidance.map(item => [item.question_id, item]));
  for (const item of snapshot.guidance) {
    const old = guidanceById.get(item.question_id);
    if (!old || old.status === 'pending' || old.status === 'running' || item.status === 'completed' || item.status === 'failed') {
      guidanceById.set(item.question_id, item);
    }
  }
  const guidance = [...guidanceById.values()];
  // The live snapshot is a moving window. Fill any gap before extending further
  // into the past, including when a long-running match outgrows a loaded page.
  let nextBefore = history[0]?.ordinal;
  let gap = false;
  for (let index = history.length - 1; index > 0; index--) {
    if (history[index].ordinal > history[index - 1].ordinal + 1) {
      nextBefore = history[index].ordinal; gap = true; break;
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
  const correctAndRefresh = async (item: FriendHistory, answer: HumanAnswer, observedAiQuestionId?: string) => {
    if (!await correct(item, answer, observedAiQuestionId)) return false;
    try { mergePage(await friendMatchApi.history(snapshot.id, item.ordinal + 1)); }
    catch (cause) { setError(friendError(cause, copy.error)); }
    return true;
  };
  return <>
    <section className={duelPanel} aria-label={copy.history}>
      <div className="mb-3 flex items-center justify-between gap-3"><h2 className="text-sm font-medium">{copy.guesses}</h2><span className="font-mono text-xs text-zinc-500">{snapshot.players.reduce((sum, player) => sum + player.guess_count, 0).toString().padStart(2, '0')}</span></div>
      {!history.some(item => item.type === 'guess') && <p className="py-3 text-sm text-zinc-500">{copy.noGuesses}</p>}
      <ol className="max-h-52 overflow-y-auto">{history.filter(item => item.type === 'guess').reverse().map(item => <HistoryMove key={item.id} item={item} snapshot={snapshot} copy={copy} busy={busy} correct={correctAndRefresh} />)}</ol>
      <div className="-mx-4 mb-4 mt-4 border-t border-white/10 sm:-mx-5" />
      <div className="mb-3 flex items-center justify-between gap-3"><h2 className="text-sm font-medium">{copy.questionHistory}</h2><span className="font-mono text-xs text-zinc-500">{snapshot.players.reduce((sum, player) => sum + player.question_count, 0).toString().padStart(2, '0')}</span></div>
      {!history.some(item => item.type === 'question') && <p className="py-4 text-sm leading-6 text-zinc-500">{copy.noQuestions}</p>}
      {(gap || (hasMore ?? snapshot.history_has_more)) && <button type="button" className={`${duelButton} mt-3`} disabled={loading}
        onClick={() => {
          if (loading || nextBefore === undefined) return;
          setLoading(true); setError('');
          void friendMatchApi.history(snapshot.id, nextBefore)
            .then(page => { mergePage(page); if (!gap) setHasMore(page.history_has_more); })
            .catch(cause => setError(friendError(cause, copy.error)))
            .finally(() => setLoading(false));
        }}>{copy.older}</button>}
      {older.length > 0 && <button type="button" className={`${duelButton} ml-2 mt-3`} disabled={loading} onClick={() => {
        setLoading(true); setError('');
        void (async () => {
          try {
            let cursor: number | null = history[history.length - 1].ordinal + 1;
            const oldest = history[0].ordinal;
            while (cursor !== null && cursor > oldest) {
              const page = await friendMatchApi.history(snapshot.id, cursor);
              mergePage(page);
              cursor = page.next_before;
            }
          } catch (cause) { setError(friendError(cause, copy.error)); }
          finally { setLoading(false); }
        })();
      }}>{copy.refresh}</button>}
      {error && <p role="alert" className="mt-2 text-sm text-red-300">{error}</p>}
      <ol className="max-h-[32rem] overflow-y-auto">{history.filter(item => item.type !== 'guess').reverse().map(item => <HistoryMove key={item.id} item={item} snapshot={snapshot} copy={copy} busy={busy} correct={correctAndRefresh} guidance={guidanceById.get(item.id)} />)}</ol>
    </section>
    {guidance.length > 0 && <details className={duelPanel}>
      <summary className="cursor-pointer font-medium">{copy.privateHistory}</summary>
      <p className="mt-2 text-sm text-zinc-400">{copy.privateHistoryHelp}</p>
      <div className="mt-4 space-y-4">{guidance.map(item => {
        const question = combined.get(item.question_id);
        return <div key={item.question_id}>
          {question && <p className="mb-2 whitespace-pre-wrap break-words text-sm">{question.question}</p>}
          <PrivateAdvice guidance={item} copy={copy} />
        </div>;
      })}</div>
    </details>}
  </>;
}
