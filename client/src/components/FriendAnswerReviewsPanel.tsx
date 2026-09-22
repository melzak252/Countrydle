import { useEffect, useRef, useState } from 'react';
import api from '../services/api';

interface Evidence {
  id: string;
  match_id: string;
  mode: string;
  target: { id: string; name: string };
  question: string;
  human_answer: string | null;
  human_answered_at: string | null;
  revisions: { answer: string; revision: number; created_at: string }[];
  ai: {
    status: string;
    answer: string | null;
    explanation: string | null;
    source: string | null;
    completed_at: string | null;
    evidence?: unknown;
  };
  comparison: string;
  ai_seen_before_answer: boolean | null;
  review_status: string;
  review_note: string | null;
  reports: { comment: string; created_at: string }[];
}

const comparisons = ['all', 'agree', 'disagree', 'not_comparable', 'ai_invalid', 'ai_unavailable', 'pending_ai'] as const;
const reviewStatuses = ['new', 'confirmed', 'needs_evidence', 'subjective', 'rejected', 'fixed'] as const;
const modes = ['countrydle', 'us_statedle', 'wojewodztwodle', 'powiatdle'];
const control = 'min-h-11 rounded-sm border border-white/15 bg-obsidian-950 px-3 py-2 text-sm text-sand-100 disabled:opacity-40';
const pageSize = 30;
const label = (value: string) => value.replaceAll('_', ' ');
const time = (value: string | null) => value ? new Date(value).toLocaleString() : 'Not available';

function ReviewCard({ item, onSaved }: { item: Evidence; onSaved: () => void }) {
  const [status, setStatus] = useState(item.review_status || 'new');
  const [note, setNote] = useState(item.review_note || '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const pending = useRef(false);

  async function save() {
    if (pending.current) return;
    pending.current = true;
    setSaving(true);
    setError('');
    try {
      await api.patch(`/admin/friend-matches/questions/${item.id}`, { status, note: note.trim() });
      onSaved();
    } catch {
      setError('Could not save the review. Your note is still here; try again.');
    } finally {
      pending.current = false;
      setSaving(false);
    }
  }

  return (
    <article className="space-y-4 rounded-sm border border-white/10 bg-obsidian-900 p-4 sm:p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-semibold text-sand-100">{item.target.name} · {item.mode}</h3>
        <span className={`rounded-sm border px-2 py-1 text-xs ${item.comparison === 'disagree' ? 'border-amber-400/30 text-amber-200' : 'border-white/15 text-zinc-300'}`}>{label(item.comparison)}</span>
      </div>
      <p className="break-words text-lg text-sand-100">{item.question}</p>
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2 rounded-sm bg-white/5 p-3">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-zinc-400">Human answer</h4>
          <p className="font-medium text-sand-100">{item.human_answer ? label(item.human_answer) : 'No answer submitted'}</p>
          <p className="text-xs text-zinc-400">{time(item.human_answered_at)}</p>
          <p className="text-xs text-zinc-300">{item.ai_seen_before_answer ? 'AI recommendation was reported visible before answering.' : 'No AI recommendation recorded as seen before this answer.'}</p>
          {item.revisions?.length > 1 && <details>
            <summary className="cursor-pointer text-sm text-emerald-300">Answer revisions</summary>
            <ol className="mt-2 space-y-1 text-xs text-zinc-300">{item.revisions.map(revision => <li key={revision.revision}>#{revision.revision}: {label(revision.answer)} · {time(revision.created_at)}</li>)}</ol>
          </details>}
        </div>
        <div className="space-y-2 rounded-sm bg-white/5 p-3">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-zinc-400">Private AI recommendation</h4>
          <p className="font-medium text-sand-100">{item.ai?.answer || label(item.ai?.status || 'pending')}</p>
          <p className="whitespace-pre-wrap break-words text-sm text-zinc-300">{item.ai?.explanation || 'No explanation available.'}</p>
          <p className="text-xs text-zinc-400">{item.ai?.source || 'Source unavailable'} · {time(item.ai?.completed_at || null)}</p>
        </div>
      </div>
      {item.reports?.length > 0 && <div className="space-y-2">
        <h4 className="text-sm font-semibold text-sand-100">Post-game reports</h4>
        {item.reports.map((report, index) => <p key={index} className="whitespace-pre-wrap break-words text-sm text-amber-100">{report.comment} <span className="text-xs text-zinc-400">({time(report.created_at)})</span></p>)}
      </div>}
      <details>
        <summary className="cursor-pointer text-sm text-emerald-300">Recorded diagnostic evidence</summary>
        <p className="mt-2 break-all text-xs text-zinc-400">Match {item.match_id} · Question {item.id}</p>
        <pre className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap break-words rounded-sm bg-black/30 p-3 text-xs text-zinc-300">{JSON.stringify(item.ai?.evidence ?? {}, null, 2)}</pre>
      </details>
      <div className="grid gap-3 sm:grid-cols-[12rem_1fr]">
        <label className="space-y-1 text-xs text-zinc-400">Review status
          <select className={`${control} block w-full`} value={status} onChange={event => setStatus(event.target.value)} disabled={saving}>
            {reviewStatuses.map(value => <option key={value} value={value}>{label(value)}</option>)}
          </select>
        </label>
        <label className="space-y-1 text-xs text-zinc-400">Evidence, classification, or fix/release reference
          <textarea className={`${control} block min-h-20 w-full`} value={note} maxLength={2000} onChange={event => setNote(event.target.value)} disabled={saving} />
        </label>
      </div>
      {error && <p role="alert" className="text-sm text-red-300">{error}</p>}
      <button type="button" className={control} onClick={() => void save()} disabled={saving}>{saving ? 'Saving…' : 'Save review'}</button>
    </article>
  );
}

export default function FriendAnswerReviewsPanel() {
  const [query, setQuery] = useState({ comparison: 'all', mode: '', page: 0, revision: 0 });
  const [result, setResult] = useState<{ query: typeof query; items: Evidence[]; total: number; error: string } | null>(null);
  const current = result?.query === query ? result : null;
  const loading = current === null;

  useEffect(() => {
    const controller = new AbortController();
    api.get<{ items: Evidence[]; total: number }>('/admin/friend-matches/questions', {
      params: { comparison: query.comparison, ...(query.mode ? { mode: query.mode } : {}), offset: query.page * pageSize, limit: pageSize },
      signal: controller.signal,
    }).then(({ data }) => {
      if (!controller.signal.aborted) setResult({ query, ...data, error: '' });
    }).catch(() => {
      if (!controller.signal.aborted) setResult({ query, items: [], total: 0, error: 'Could not load friend-game evidence. Try refreshing.' });
    });
    return () => controller.abort();
  }, [query]);

  return (
    <section aria-labelledby="friend-evidence-title" className="min-w-0 space-y-5">
      <div className="space-y-2">
        <h2 id="friend-evidence-title" className="font-serif text-2xl text-sand-100">Human and AI answer comparison</h2>
        <p className="max-w-3xl text-sm text-zinc-300">All saved questions are available, including agreements and late AI results. Agreement is not verified truth; a visible suggestion may influence the player. Reviewing a case never changes game facts or deploys a model update.</p>
      </div>
      <div className="flex flex-wrap items-end gap-3">
        <label className="space-y-1 text-xs text-zinc-400">Comparison
          <select className={`${control} block`} value={query.comparison} onChange={event => setQuery({ ...query, comparison: event.target.value, page: 0 })}>
            {comparisons.map(value => <option key={value} value={value}>{label(value)}</option>)}
          </select>
        </label>
        <label className="space-y-1 text-xs text-zinc-400">Geography
          <select className={`${control} block`} value={query.mode} onChange={event => setQuery({ ...query, mode: event.target.value, page: 0 })}>
            <option value="">All modes</option>
            {modes.map(mode => <option key={mode}>{mode}</option>)}
          </select>
        </label>
        <button type="button" className={control} onClick={() => setQuery({ ...query, revision: query.revision + 1 })} disabled={loading}>Refresh</button>
      </div>
      {loading && <p role="status" className="text-zinc-300">Loading evidence…</p>}
      {current?.error && <p role="alert" className="text-red-300">{current.error}</p>}
      {current && !current.error && <>
        <p role="status" className="text-sm text-zinc-400">{current.total} matching questions</p>
        {current.items.length === 0 && <p className="text-zinc-300">No questions match these filters.</p>}
        {current.items.map(item => <ReviewCard key={`${item.id}:${query.revision}`} item={item} onSaved={() => setQuery(previous => ({ ...previous, revision: previous.revision + 1 }))} />)}
        <div className="flex items-center gap-3">
          <button type="button" className={control} disabled={query.page === 0} onClick={() => setQuery({ ...query, page: query.page - 1 })}>Previous</button>
          <span className="text-sm text-zinc-400">Page {query.page + 1} of {Math.max(1, Math.ceil(current.total / pageSize))}</span>
          <button type="button" className={control} disabled={(query.page + 1) * pageSize >= current.total} onClick={() => setQuery({ ...query, page: query.page + 1 })}>Next</button>
        </div>
      </>}
    </section>
  );
}
