import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
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
const control = 'min-h-11 rounded-sm border border-app-border bg-app-surface-muted px-3 py-2 text-app-text focus:border-app-accent focus:outline-none focus:ring-2 focus:ring-app-focus disabled:opacity-60';
const pageSize = 30;

function ReviewCard({ item, onSaved }: { item: Evidence; onSaved: () => void }) {
  const { t } = useTranslation('translation', { keyPrefix: 'adminFriendDuels' });
  const { t: modesT } = useTranslation('translation');
  const dateLocale = 'en-GB';
  const formatTime = (value: string | null) => value
    ? new Intl.DateTimeFormat(dateLocale, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
    : t('timeUnavailable');
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
      setError(t('saveError'));
    } finally {
      pending.current = false;
      setSaving(false);
    }
  }

  return (
    <article className="min-w-0 space-y-4 rounded-md border border-app-border bg-app-surface p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="break-words text-lg font-semibold text-app-text">{item.target.name} · {modesT(`adminModes.modes.${item.mode}`, { defaultValue: item.mode })}</h3>
        <span className={`inline-flex rounded-sm border px-2 py-1 text-xs font-medium ${item.comparison === 'agree' ? 'border-emerald-700/25 bg-emerald-50 text-emerald-900' : item.comparison === 'disagree' ? 'border-rose-700/25 bg-rose-50 text-rose-900' : item.comparison === 'ai_invalid' ? 'border-amber-700/25 bg-amber-50 text-amber-900' : 'border-app-border bg-app-surface-muted text-app-text-secondary'}`}>{t(`labels.${item.comparison}`, { defaultValue: item.comparison })}</span>
      </div>
      <p className="rounded-sm border-l-2 border-app-accent bg-app-surface-muted p-3 text-app-text">{item.question}</p>
      <div className="grid gap-4 xl:grid-cols-2">
        <section aria-label={t('humanAnswer')} className="min-w-0 space-y-3 rounded-sm border border-app-border bg-app-surface-muted p-4">
          <h4 className="text-base font-semibold text-app-text">{t('humanAnswer')}</h4>
          <p className="text-sm text-app-text">{item.human_answer ? t(`labels.${item.human_answer.toLowerCase()}`, { defaultValue: item.human_answer }) : t('noAnswerSubmitted')}</p>
          <p className="text-sm text-app-text-muted">{formatTime(item.human_answered_at)}</p>
          <p className="text-sm leading-relaxed text-app-text-secondary">{item.ai_seen_before_answer ? t('aiSeen') : t('aiNotSeen')}</p>
          {item.revisions?.length > 1 && <details className="text-sm">
            <summary className="cursor-pointer rounded-sm py-2 text-app-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus">{t('answerRevisions')}</summary>
            <ol className="mt-2 list-decimal space-y-2 pl-5 text-sm text-app-text-secondary">
              {item.revisions.map(revision => <li key={revision.revision}>#{revision.revision}: {t(`labels.${revision.answer.toLowerCase()}`, { defaultValue: revision.answer })} · {formatTime(revision.created_at)}</li>)}
            </ol>
          </details>}
        </section>
        <section aria-label={t('privateAiRecommendation')} className="min-w-0 space-y-3 rounded-sm border border-app-border bg-app-surface-muted p-4">
          <h4 className="text-base font-semibold text-app-text">{t('privateAiRecommendation')}</h4>
          <p className="text-sm text-app-text">{t(`labels.${(item.ai?.answer || item.ai?.status || 'pending').toLowerCase()}`, { defaultValue: item.ai?.answer || item.ai?.status || 'pending' })}</p>
          <p className="whitespace-pre-wrap break-words text-sm leading-relaxed text-app-text-secondary">{item.ai?.explanation || t('noExplanation')}</p>
          <p className="break-words text-sm text-app-text-muted">{item.ai?.source || t('sourceUnavailable')} · {formatTime(item.ai?.completed_at || null)}</p>
        </section>
      </div>
      {item.reports?.length > 0 && <section className="space-y-2">
        <h4 className="text-base font-semibold text-app-text">{t('postGameReports')}</h4>
        {item.reports.map((report, index) => <p key={index} className="whitespace-pre-wrap break-words text-sm leading-relaxed text-app-text-secondary">{report.comment} <span className="text-app-text-muted">({formatTime(report.created_at)})</span></p>)}
      </section>}
      <details className="text-sm">
        <summary className="cursor-pointer rounded-sm py-2 text-app-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus">{t('diagnosticEvidence')}</summary>
        <p className="mt-2 break-all text-sm text-app-text-muted">{t('recordIds', { matchId: item.match_id, questionId: item.id })}</p>
        <pre tabIndex={0} aria-label={t('diagnosticEvidence')} className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap break-words rounded-sm border border-app-border bg-app-surface-muted p-3 font-mono text-xs leading-5 text-app-text-secondary">{JSON.stringify(item.ai?.evidence ?? {}, null, 2)}</pre>
      </details>
      <div className="grid gap-4 xl:grid-cols-[minmax(12rem,0.4fr)_minmax(0,1fr)]">
        <label className="flex min-w-0 flex-col gap-1.5 text-sm text-app-text-secondary">
          <span>{t('reviewStatus')}</span>
          <select className={`${control} w-full`} value={status} onChange={event => setStatus(event.target.value)} disabled={saving}>
            {reviewStatuses.map(value => <option key={value} value={value}>{t(`labels.${value}`)}</option>)}
          </select>
        </label>
        <label className="flex min-w-0 flex-col gap-1.5 text-sm text-app-text-secondary">
          <span>{t('reviewNote')}</span>
          <textarea className={`${control} min-h-24 w-full`} value={note} maxLength={2000} onChange={event => setNote(event.target.value)} disabled={saving} />
        </label>
      </div>
      {error && <p role="alert" className="text-sm text-red-800">{error}</p>}
      <button type="button" className="inline-flex min-h-11 items-center justify-center rounded-sm bg-app-accent px-3 py-2 text-sm font-semibold text-app-canvas transition-colors hover:bg-app-accent-hover focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus disabled:cursor-not-allowed disabled:opacity-50" onClick={() => void save()} disabled={saving}>{saving ? t('saving') : t('saveReview')}</button>
    </article>
  );
}

export default function FriendAnswerReviewsPanel() {
  const { t } = useTranslation('translation', { keyPrefix: 'adminFriendDuels' });
  const { t: modesT } = useTranslation('translation');
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
      if (!controller.signal.aborted) setResult({ query, items: [], total: 0, error: t('loadError') });
    });
    return () => controller.abort();
  }, [query, t]);

  const retry = () => setQuery(previous => ({ ...previous, revision: previous.revision + 1 }));
  const pageCount = current ? Math.max(1, Math.ceil(current.total / pageSize)) : 1;

  return (
    <section aria-labelledby="admin-page-title" className="min-w-0 space-y-5">
      <details className="rounded-md border border-app-border bg-app-surface p-4 text-sm leading-relaxed text-app-text-secondary">
        <summary className="cursor-pointer rounded-sm text-app-text focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus">{t('reviewCaveatTitle')}</summary>
        <p className="mt-3">{t('reviewCaveat')}</p>
      </details>
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex min-w-0 flex-col gap-1.5 text-sm text-app-text-secondary">
          <span>{t('comparison')}</span>
          <select className={control} value={query.comparison} onChange={event => setQuery({ ...query, comparison: event.target.value, page: 0 })}>
            {comparisons.map(value => <option key={value} value={value}>{t(`labels.${value}`)}</option>)}
          </select>
        </label>
        <label className="flex min-w-0 flex-col gap-1.5 text-sm text-app-text-secondary">
          <span>{t('geography')}</span>
          <select className={control} value={query.mode} onChange={event => setQuery({ ...query, mode: event.target.value, page: 0 })}>
            <option value="">{t('allModes')}</option>
            {modes.map(mode => <option key={mode} value={mode}>{modesT(`adminModes.modes.${mode}`, { defaultValue: mode })}</option>)}
          </select>
        </label>
        <button type="button" className="min-h-11 rounded-sm border border-app-border px-3 py-2 text-sm text-app-text-secondary transition-colors hover:bg-app-surface-muted focus-visible:outline focus-visible:outline-2 focus-visible:outline-app-focus disabled:cursor-not-allowed disabled:opacity-50" onClick={retry} disabled={loading}>{t('refresh')}</button>
      </div>
      {loading && <p role="status" className="text-sm text-app-text-secondary">{t('loading')}</p>}
      {current?.error && <div className="space-y-3" role="alert">
        <p className="text-sm text-red-800">{current.error}</p>
        <button type="button" className="min-h-11 rounded-sm border border-app-border px-3 py-2 text-sm text-app-text-secondary transition-colors hover:bg-app-surface-muted focus-visible:outline focus-visible:outline-2 focus-visible:outline-app-focus" onClick={retry}>{t('retry')}</button>
      </div>}
      {current && !current.error && <>
        <p role="status" className="text-sm text-app-text-muted">{t('matchingQuestions', { count: current.total })}</p>
        {current.items.length === 0 && <p className="text-sm text-app-text-secondary">{t('empty')}</p>}
        <div className="space-y-4">
          {current.items.map(item => <ReviewCard key={`${item.mode}:${item.id}:${query.revision}`} item={item} onSaved={() => setQuery(previous => ({ ...previous, revision: previous.revision + 1 }))} />)}
        </div>
        {current.total > 0 && <nav aria-label={t('pagination')} className="flex flex-wrap items-center gap-3">
          <button type="button" className="min-h-11 rounded-sm border border-app-border px-3 py-2 text-sm text-app-text-secondary transition-colors hover:bg-app-surface-muted focus-visible:outline focus-visible:outline-2 focus-visible:outline-app-focus disabled:cursor-not-allowed disabled:opacity-50" disabled={query.page === 0} onClick={() => setQuery({ ...query, page: query.page - 1 })}>{t('previous')}</button>
          <span className="text-sm text-app-text-muted" aria-live="polite">{t('pageOf', { page: query.page + 1, pages: pageCount })}</span>
          <button type="button" className="min-h-11 rounded-sm border border-app-border px-3 py-2 text-sm text-app-text-secondary transition-colors hover:bg-app-surface-muted focus-visible:outline focus-visible:outline-2 focus-visible:outline-app-focus disabled:cursor-not-allowed disabled:opacity-50" disabled={(query.page + 1) * pageSize >= current.total} onClick={() => setQuery({ ...query, page: query.page + 1 })}>{t('next')}</button>
        </nav>}
      </>}
    </section>
  );
}
