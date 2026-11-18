import { useEffect, useRef, useState } from 'react';
import { CheckCircle2, RefreshCw, RotateCcw } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { adminService } from '../../services/api';
import type { TemplateDivergence, TemplateDivergenceStatus } from '../../types';

const PAGE_SIZE = 25;
const MODE_LABELS: Record<string, string> = {
  countrydle: 'Countrydle',
  us_statedle: 'US Statedle',
  powiatdle: 'Powiatdle',
  wojewodztwodle: 'Województwodle',
  continental: 'Europedle / Continental',
};

type DivergenceQuery = {
  status: TemplateDivergenceStatus;
  mode: string;
  page: number;
  revision: number;
};

type DivergenceResult = {
  query: DivergenceQuery;
  items: TemplateDivergence[];
  total: number;
  error: string | null;
};

const panelBaseClass = 'min-w-0 rounded-md border p-4';
const panelClass = `${panelBaseClass} border-app-border bg-app-surface text-app-text`;
const toolbarClass = 'flex flex-wrap items-end gap-4 rounded-md border border-app-border bg-app-surface p-4';
const controlClass = 'min-h-11 w-full min-w-0 rounded-sm border border-app-border bg-app-surface-muted px-3 py-2 text-app-text placeholder:text-app-text-muted focus:border-app-accent focus:outline-none focus:ring-2 focus:ring-app-focus disabled:cursor-not-allowed disabled:opacity-50';
const buttonBaseClass = 'inline-flex min-h-11 items-center justify-center gap-2 rounded-sm border px-3 py-2 text-sm font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus disabled:cursor-not-allowed disabled:opacity-50';
const buttonClass = `${buttonBaseClass} border-app-border bg-app-surface-muted text-app-text hover:border-app-accent-hover hover:bg-app-surface-raised`;
const badgeBaseClass = 'inline-flex items-center gap-1 rounded-sm border px-2 py-0.5 text-xs font-medium';
const badgeClass = `${badgeBaseClass} border-app-border bg-app-surface-muted text-app-text-secondary`;
const metaClass = 'text-xs leading-5 text-app-text-muted';
const diagnosticsClass = 'max-w-full overflow-auto whitespace-pre-wrap break-words rounded-sm border border-app-border bg-app-surface-muted p-3 font-mono text-xs leading-5 text-app-text-secondary focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus';

export default function TemplateDivergencesPanel({ onTestQuestion }: { onTestQuestion?: (question: string, mode: string) => void }) {
  const { t } = useTranslation('translation', { keyPrefix: 'adminTemplateAudit' });
  const { t: modesT } = useTranslation('translation');
  const [query, setQuery] = useState<DivergenceQuery>({ status: 'open', mode: '', page: 1, revision: 0 });
  const [result, setResult] = useState<DivergenceResult | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [notice, setNotice] = useState('');
  const mounted = useRef(false);
  const mutationPending = useRef(false);
  const loading = result?.query !== query;
  const currentResult = loading ? null : result;
  const totalPages = Math.max(1, Math.ceil((currentResult?.total ?? 0) / PAGE_SIZE));

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  useEffect(() => {
    let cancelled = false;
    adminService.getTemplateDivergences(query.status, query.page, PAGE_SIZE, query.mode || undefined)
      .then((data) => {
        if (cancelled) return;
        const lastPage = Math.max(1, Math.ceil(data.total / PAGE_SIZE));
        if (query.page > lastPage) {
          setQuery((current) => ({ ...current, page: lastPage }));
          return;
        }
        setResult({ query, ...data, error: null });
      })
      .catch(() => {
        if (!cancelled) {
          setResult({ query, items: [], total: 0, error: t('loadError') });
        }
      });
    return () => { cancelled = true; };
  }, [query, t]);

  const changeQuery = (changes: Partial<DivergenceQuery>) => {
    setActionError(null);
    setNotice('');
    setQuery((current) => ({ ...current, ...changes }));
  };

  const reviewDivergence = async (item: TemplateDivergence) => {
    if (mutationPending.current) return;
    mutationPending.current = true;
    setBusyId(item.id);
    setActionError(null);
    setNotice('');
    const reviewed = item.reviewed_at === null;
    try {
      await adminService.reviewTemplateDivergence(item.id, reviewed);
      if (!mounted.current) return;
      setNotice(t(reviewed ? 'markedReviewedNotice' : 'reopenedNotice', { id: item.id }));
      setQuery((current) => ({ ...current, revision: current.revision + 1 }));
    } catch {
      if (mounted.current) {
        setActionError(t('updateError', { id: item.id }));
      }
    } finally {
      if (mounted.current) {
        setBusyId(null);
      }
      mutationPending.current = false;
    }
  };

  return (
    <section aria-labelledby="admin-page-title" className="min-w-0 space-y-5 text-app-text">
      <div className={toolbarClass}>
        <label className="flex min-w-0 flex-col gap-1.5 text-sm font-medium text-app-text-secondary">
          {t('status')}
          <select value={query.status} disabled={busyId !== null} onChange={(event) => changeQuery({ status: event.target.value as TemplateDivergenceStatus, page: 1 })} className={controlClass}>
            <option value="open">{t('open')}</option>
            <option value="reviewed">{t('reviewed')}</option>
            <option value="all">{t('allStatuses')}</option>
          </select>
        </label>
        <label className="flex min-w-0 flex-col gap-1.5 text-sm font-medium text-app-text-secondary">
          {t('mode')}
          <select value={query.mode} disabled={busyId !== null} onChange={(event) => changeQuery({ mode: event.target.value, page: 1 })} className={controlClass}>
            <option value="">{t('allModes')}</option>
            {Object.entries(MODE_LABELS).map(([modeKey, label]) => <option key={modeKey} value={modeKey}>{modesT(`adminModes.modes.${modeKey}`, { defaultValue: label })}</option>)}
          </select>
        </label>
        <button type="button" disabled={loading || busyId !== null} onClick={() => changeQuery({ revision: query.revision + 1 })} className={`${buttonClass} ml-auto`}>
          <RefreshCw size={16} aria-hidden="true" />{t('refresh')}
        </button>
      </div>

      {notice && <p role="status" className="text-sm text-emerald-800">{notice}</p>}
      {actionError && <p role="alert" className="text-sm text-rose-800">{actionError}</p>}

      <div aria-busy={loading} className="space-y-4">
        {loading ? <p role="status" className="py-8 text-sm text-app-text-secondary">{t('loading')}</p>
          : currentResult?.error ? <div role="alert" className="space-y-3 rounded-md border border-rose-300 bg-rose-50 p-4 text-sm text-rose-800">
            <p>{currentResult.error}</p>
            <button type="button" onClick={() => changeQuery({ revision: query.revision + 1 })} className={buttonClass}><RefreshCw size={16} aria-hidden="true" />{t('retry')}</button>
          </div>
          : currentResult?.items.length === 0 ? <p role="status" className={`${panelBaseClass} border-app-border bg-app-surface text-sm text-app-text-muted`}>{t('empty')}</p>
            : currentResult?.items.map((item) => (
              <article key={item.id} className={`${panelClass} space-y-4`}>
                <div className="flex min-w-0 flex-wrap items-start justify-between gap-4">
                  <div className="min-w-0 space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <h2 className="text-base font-semibold text-app-text">{t('record', { id: item.id, mode: modesT(`adminModes.modes.${item.mode}`, { defaultValue: MODE_LABELS[item.mode] || item.mode }) })}</h2>
                      <span className={badgeClass}>{item.divergence_type}</span>
                      <span className={`${badgeBaseClass} ${item.reviewed_at ? 'border-app-border bg-app-surface-muted text-app-text-secondary' : 'border-amber-300 bg-amber-50 text-amber-900'}`}>{item.reviewed_at ? t('reviewed') : t('open')}</span>
                    </div>
                    <p className="text-sm text-app-text-secondary">{t('captured')} <time dateTime={item.created_at}>{new Date(item.created_at).toLocaleString('en-US')}</time></p>
                    {item.reviewed_at && <p className="text-sm text-app-text-secondary">{t('reviewedAt')} <time dateTime={item.reviewed_at}>{new Date(item.reviewed_at).toLocaleString('en-US')}</time></p>}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {onTestQuestion && <button type="button" disabled={busyId !== null} onClick={() => onTestQuestion(item.question, item.mode)} className={buttonClass}>{t('testInQa')}</button>}
                    <button type="button" disabled={busyId !== null} onClick={() => void reviewDivergence(item)} className={buttonClass}>
                      {busyId === item.id ? <RefreshCw size={16} aria-hidden="true" className="animate-spin" /> : item.reviewed_at ? <RotateCcw size={16} aria-hidden="true" /> : <CheckCircle2 size={16} aria-hidden="true" />}
                      {busyId === item.id ? t('saving') : item.reviewed_at ? t('reopen') : t('markReviewed')}
                    </button>
                  </div>
                </div>
                <div className="space-y-1">
                  <p className={metaClass}>{t('question')}</p>
                  <p className="break-words text-base leading-6 text-app-text [overflow-wrap:anywhere]">{item.question}</p>
                </div>
                {item.details?.gemini_explanation && <p className="whitespace-pre-wrap break-words rounded-sm border-l-2 border-amber-400 bg-amber-50 py-2 pl-3 pr-2 text-sm text-amber-900"><span className="font-medium text-amber-950">{t('modelExplanation')}</span> {item.details.gemini_explanation}</p>}
                <details className="border-t border-app-border pt-3">
                  <summary className="min-h-11 cursor-pointer py-2 text-sm font-medium text-app-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus">{t('comparePlans')}</summary>
                  <div className="mt-3 grid min-w-0 gap-4 xl:grid-cols-2">
                    <section className="min-w-0 space-y-3">
                      <h3 className="text-base font-medium text-app-text">{t('templatePlan')}</h3>
                      {item.details?.template_improved_question && <p className="whitespace-pre-wrap break-words text-sm text-app-text-secondary">{item.details.template_improved_question}</p>}
                      <pre tabIndex={0} aria-label={t('templatePlan')} className={`${diagnosticsClass} max-h-96`}>{JSON.stringify(item.template_plan, null, 2)}</pre>
                    </section>
                    <section className="min-w-0 space-y-3">
                      <h3 className="text-base font-medium text-app-text">{t('modelPlan')}</h3>
                      {item.details?.gemini_improved_question && <p className="whitespace-pre-wrap break-words text-sm text-app-text-secondary">{item.details.gemini_improved_question}</p>}
                      <pre tabIndex={0} aria-label={t('modelPlan')} className={`${diagnosticsClass} max-h-96`}>{JSON.stringify(item.gemini_plan, null, 2)}</pre>
                    </section>
                  </div>
                </details>
              </article>
            ))}
      </div>

      {currentResult && !currentResult.error && (
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-app-border pt-4">
          <p className="text-sm text-app-text-secondary">{t('page', { page: query.page, pages: totalPages, count: currentResult?.total ?? 0 })}</p>
          <div className="flex gap-2">
            <button type="button" disabled={query.page <= 1 || loading} onClick={() => changeQuery({ page: query.page - 1 })} className={buttonClass}>{t('previous')}</button>
            <button type="button" disabled={query.page >= totalPages || loading} onClick={() => changeQuery({ page: query.page + 1 })} className={buttonClass}>{t('next')}</button>
          </div>
        </div>
      )}
    </section>
  );
}
