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
const control = 'admin-control';
const pageSize = 30;

function ReviewCard({ item, onSaved }: { item: Evidence; onSaved: () => void }) {
  const { t, i18n } = useTranslation('translation', { keyPrefix: 'adminFriendDuels' });
  const { t: modesT } = useTranslation('translation');
  const dateLocale = i18n.language.startsWith('pl') ? 'pl-PL' : 'en-GB';
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
    <article className="admin-panel min-w-0 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="break-words text-lg font-semibold text-sand-100">{item.target.name} · {modesT(`adminModes.modes.${item.mode}`, { defaultValue: item.mode })}</h3>
        <span className="admin-badge">{t(`labels.${item.comparison}`, { defaultValue: item.comparison })}</span>
      </div>
      <p className="admin-question break-words">{item.question}</p>
      <div className="grid gap-4 xl:grid-cols-2">
        <section aria-label={t('humanAnswer')} className="min-w-0 space-y-3 rounded-sm border border-white/10 bg-obsidian-950 p-4">
          <h4 className="text-base font-semibold text-sand-100">{t('humanAnswer')}</h4>
          <p className="text-sm text-sand-100">{item.human_answer ? t(`labels.${item.human_answer.toLowerCase()}`, { defaultValue: item.human_answer }) : t('noAnswerSubmitted')}</p>
          <p className="admin-meta">{formatTime(item.human_answered_at)}</p>
          <p className="text-sm leading-relaxed text-slate-300">{item.ai_seen_before_answer ? t('aiSeen') : t('aiNotSeen')}</p>
          {item.revisions?.length > 1 && <details className="text-sm">
            <summary className="cursor-pointer rounded-sm py-2 text-emerald-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-300">{t('answerRevisions')}</summary>
            <ol className="mt-2 list-decimal space-y-2 pl-5 text-sm text-slate-300">
              {item.revisions.map(revision => <li key={revision.revision}>#{revision.revision}: {t(`labels.${revision.answer.toLowerCase()}`, { defaultValue: revision.answer })} · {formatTime(revision.created_at)}</li>)}
            </ol>
          </details>}
        </section>
        <section aria-label={t('privateAiRecommendation')} className="min-w-0 space-y-3 rounded-sm border border-white/10 bg-obsidian-950 p-4">
          <h4 className="text-base font-semibold text-sand-100">{t('privateAiRecommendation')}</h4>
          <p className="text-sm text-sand-100">{t(`labels.${(item.ai?.answer || item.ai?.status || 'pending').toLowerCase()}`, { defaultValue: item.ai?.answer || item.ai?.status || 'pending' })}</p>
          <p className="whitespace-pre-wrap break-words text-sm leading-relaxed text-slate-300">{item.ai?.explanation || t('noExplanation')}</p>
          <p className="admin-meta break-words">{item.ai?.source || t('sourceUnavailable')} · {formatTime(item.ai?.completed_at || null)}</p>
        </section>
      </div>
      {item.reports?.length > 0 && <section className="space-y-2">
        <h4 className="text-base font-semibold text-sand-100">{t('postGameReports')}</h4>
        {item.reports.map((report, index) => <p key={index} className="whitespace-pre-wrap break-words text-sm leading-relaxed text-slate-200">{report.comment} <span className="admin-meta">({formatTime(report.created_at)})</span></p>)}
      </section>}
      <details className="text-sm">
        <summary className="cursor-pointer rounded-sm py-2 text-emerald-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-300">{t('diagnosticEvidence')}</summary>
        <p className="admin-meta mt-2 break-all">{t('recordIds', { matchId: item.match_id, questionId: item.id })}</p>
        <pre tabIndex={0} aria-label={t('diagnosticEvidence')} className="admin-diagnostics mt-2 max-h-72 overflow-auto whitespace-pre-wrap break-words rounded-sm bg-black/30 p-3">{JSON.stringify(item.ai?.evidence ?? {}, null, 2)}</pre>
      </details>
      <div className="grid gap-4 xl:grid-cols-[minmax(12rem,0.4fr)_minmax(0,1fr)]">
        <label className="admin-field">
          <span>{t('reviewStatus')}</span>
          <select className={`${control} w-full`} value={status} onChange={event => setStatus(event.target.value)} disabled={saving}>
            {reviewStatuses.map(value => <option key={value} value={value}>{t(`labels.${value}`)}</option>)}
          </select>
        </label>
        <label className="admin-field">
          <span>{t('reviewNote')}</span>
          <textarea className={`${control} min-h-24 w-full`} value={note} maxLength={2000} onChange={event => setNote(event.target.value)} disabled={saving} />
        </label>
      </div>
      {error && <p role="alert" className="text-sm text-rose-300">{error}</p>}
      <button type="button" className="admin-button admin-button-primary" onClick={() => void save()} disabled={saving}>{saving ? t('saving') : t('saveReview')}</button>
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
      <details className="admin-panel text-sm leading-relaxed text-slate-300">
        <summary className="cursor-pointer rounded-sm text-sand-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-300">{t('reviewCaveatTitle')}</summary>
        <p className="mt-3">{t('reviewCaveat')}</p>
      </details>
      <div className="admin-toolbar">
        <label className="admin-field">
          <span>{t('comparison')}</span>
          <select className={control} value={query.comparison} onChange={event => setQuery({ ...query, comparison: event.target.value, page: 0 })}>
            {comparisons.map(value => <option key={value} value={value}>{t(`labels.${value}`)}</option>)}
          </select>
        </label>
        <label className="admin-field">
          <span>{t('geography')}</span>
          <select className={control} value={query.mode} onChange={event => setQuery({ ...query, mode: event.target.value, page: 0 })}>
            <option value="">{t('allModes')}</option>
            {modes.map(mode => <option key={mode} value={mode}>{modesT(`adminModes.modes.${mode}`, { defaultValue: mode })}</option>)}
          </select>
        </label>
        <button type="button" className="admin-button" onClick={retry} disabled={loading}>{t('refresh')}</button>
      </div>
      {loading && <p role="status" className="text-sm text-slate-300">{t('loading')}</p>}
      {current?.error && <div className="space-y-3" role="alert">
        <p className="text-sm text-rose-300">{current.error}</p>
        <button type="button" className="admin-button" onClick={retry}>{t('retry')}</button>
      </div>}
      {current && !current.error && <>
        <p role="status" className="admin-meta">{t('matchingQuestions', { count: current.total })}</p>
        {current.items.length === 0 && <p className="text-sm text-slate-300">{t('empty')}</p>}
        <div className="space-y-4">
          {current.items.map(item => <ReviewCard key={`${item.mode}:${item.id}:${query.revision}`} item={item} onSaved={() => setQuery(previous => ({ ...previous, revision: previous.revision + 1 }))} />)}
        </div>
        {current.total > 0 && <nav aria-label={t('pagination')} className="flex flex-wrap items-center gap-3">
          <button type="button" className="admin-button" disabled={query.page === 0} onClick={() => setQuery({ ...query, page: query.page - 1 })}>{t('previous')}</button>
          <span className="admin-meta" aria-live="polite">{t('pageOf', { page: query.page + 1, pages: pageCount })}</span>
          <button type="button" className="admin-button" disabled={(query.page + 1) * pageSize >= current.total} onClick={() => setQuery({ ...query, page: query.page + 1 })}>{t('next')}</button>
        </nav>}
      </>}
    </section>
  );
}
