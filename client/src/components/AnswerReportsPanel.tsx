import { useEffect, useRef, useState } from 'react';
import { CheckCircle2, RefreshCw, RotateCcw } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { adminService } from '../services/api';
import type { AnswerReport, AnswerReportMode, AnswerReportStatus } from '../types';

const PAGE_SIZE = 25;
const MODE_LABELS: Record<AnswerReportMode, string> = {
  countrydle: 'Countrydle',
  us_statedle: 'US Statedle',
  powiatdle: 'Powiatdle',
  wojewodztwodle: 'Województwodle',
  continental: 'Europedle / Continental',
};

type ReportQuery = {
  status: AnswerReportStatus;
  mode: AnswerReportMode | '';
  page: number;
  revision: number;
};

type ReportResult = {
  query: ReportQuery;
  items: AnswerReport[];
  total: number;
  error: string | null;
};

const controlClass = 'admin-control';

export default function AnswerReportsPanel({ onTestQuestion }: { onTestQuestion: (report: AnswerReport) => void }) {
  const { t, i18n } = useTranslation('translation', { keyPrefix: 'adminReports' });
  const { t: modesT } = useTranslation('translation');
  const [query, setQuery] = useState<ReportQuery>({ status: 'open', mode: '', page: 1, revision: 0 });
  const [result, setResult] = useState<ReportResult | null>(null);
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
    adminService.getAnswerReports(query.status, query.page, PAGE_SIZE, query.mode || undefined)
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
          setResult({ query, items: [], total: 0, error: 'loadError' });
        }
      });
    return () => { cancelled = true; };
  }, [query]);

  const changeQuery = (changes: Partial<ReportQuery>) => {
    setActionError(null);
    setNotice('');
    setQuery((current) => ({ ...current, ...changes }));
  };

  const reviewReport = async (report: AnswerReport) => {
    if (mutationPending.current) return;
    mutationPending.current = true;
    setBusyId(report.id);
    setActionError(null);
    setNotice('');
    const reviewed = report.reviewed_at === null;
    try {
      await adminService.reviewAnswerReport(report.id, reviewed);
      if (!mounted.current) return;
      setNotice(reviewed ? t('reviewed') : t('open'));
      // Invalidate the page before fetching so rows never retain a stale review status.
      setQuery((current) => ({ ...current, revision: current.revision + 1 }));
    } catch {
      if (mounted.current) setActionError(t('updateError', { id: report.id }));
    } finally {
      mutationPending.current = false;
      if (mounted.current) setBusyId(null);
    }
  };

  return (
    <section aria-labelledby="admin-page-title" className="min-w-0 space-y-5">
      <div className="flex justify-end">
        <button
          type="button"
          disabled={loading || busyId !== null}
          onClick={() => changeQuery({ revision: query.revision + 1 })}
          className="admin-button flex items-center gap-2"
        >
          <RefreshCw size={14} aria-hidden="true" className={loading ? 'animate-spin' : ''} />
          {t('refresh')}
        </button>
      </div>

      <div className="admin-toolbar">
        <label className="flex flex-col gap-1.5 text-sm text-slate-300">
          {t('status')}
          <select value={query.status} disabled={busyId !== null} onChange={(event) => changeQuery({ status: event.target.value as AnswerReportStatus, page: 1 })} className={controlClass}>
            <option value="open">{t('open')}</option>
            <option value="reviewed">{t('reviewed')}</option>
            <option value="all">{t('allStatuses')}</option>
          </select>
        </label>
        <label className="flex flex-col gap-1.5 text-sm text-slate-300">
          {t('mode')}
          <select value={query.mode} disabled={busyId !== null} onChange={(event) => changeQuery({ mode: event.target.value as AnswerReportMode | '', page: 1 })} className={controlClass}>
            <option value="">{t('allModes')}</option>
            {Object.keys(MODE_LABELS).map((mode) => <option key={mode} value={mode}>{modesT(`adminModes.modes.${mode}`, { defaultValue: MODE_LABELS[mode as AnswerReportMode] })}</option>)}
          </select>
        </label>
      </div>
      {notice && <p role="status" className="text-sm text-emerald-300">{notice}</p>}
      {actionError && <p role="alert" className="text-sm text-rose-300">{actionError}</p>}

      <div aria-busy={loading} className="space-y-4">
        {loading ? (
          <p role="status" className="py-8 text-sm text-slate-300">{t('loading')}</p>
        ) : currentResult?.error ? (
          <div role="alert" className="admin-panel space-y-3 border border-rose-400/30 p-4 text-sm text-rose-300">
            <p>{t(currentResult.error)}</p>
            <button type="button" onClick={() => changeQuery({ revision: query.revision + 1 })} className="admin-button">{t('retry')}</button>
          </div>
        ) : currentResult?.items.length === 0 ? (
          <p role="status" className="admin-panel p-8 text-sm text-slate-300">{t('empty')}</p>
        ) : currentResult?.items.map((report) => (
          <article key={report.id} aria-labelledby={`report-${report.id}-title`} className="admin-panel min-w-0 space-y-5 p-4 sm:p-5">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
              <div className="min-w-0 flex-1 space-y-1">
                <h3 id={`report-${report.id}-title`} className="whitespace-pre-wrap break-words text-base font-semibold text-sand-100">{report.comment || t('noComment')}</h3>
                <p className="whitespace-pre-wrap break-words text-base text-sand-100">{report.details.original_question}</p>
                <p className="text-sm font-semibold"><span className={report.details.valid ? 'text-emerald-300' : 'text-amber-300'}>{report.details.valid ? t('valid') : t('invalid')}</span> · <span className={report.details.valid && report.details.answer === true ? 'text-emerald-300' : 'text-slate-300'}>{report.details.answer === null ? t('noAnswer') : report.details.answer ? t('yes') : t('no')}</span></p>
                <p className="text-sm text-slate-300">{t('caseId', { id: report.id })}</p>
                <div className="flex flex-wrap gap-2">
                  <span className="admin-badge">{modesT(`adminModes.modes.${report.mode}`, { defaultValue: MODE_LABELS[report.mode] })}</span>
                  <span className={`admin-badge ${report.reviewed_at ? '' : 'text-amber-300'}`}>{report.reviewed_at ? t('reviewedAt', { date: new Date(report.reviewed_at).toLocaleString(i18n.language) }) : t('open')}</span>
                </div>
                <p className="text-sm text-slate-300">{t('reporter')}: {report.reporter_username || t('guest')} · {t('submitted')}: {new Date(report.created_at).toLocaleString(i18n.language)}</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  disabled={busyId !== null}
                  onClick={() => onTestQuestion(report)}
                  className="admin-button admin-button-primary"
                >
                  {t('testInQA')}
                </button>
              <button
                type="button"
                disabled={busyId !== null}
                onClick={() => void reviewReport(report)}
                aria-label={`${report.reviewed_at ? t('reopen') : t('markReviewed')} ${t('report')} #${report.id}`}
                className="admin-button"
              >
                {report.reviewed_at ? <RotateCcw size={14} aria-hidden="true" /> : <CheckCircle2 size={14} aria-hidden="true" />}
                {busyId === report.id ? t('saving') : report.reviewed_at ? t('reopen') : t('markReviewed')}
              </button>
              </div>
            </div>


            <dl className="grid min-w-0 grid-cols-1 gap-4 text-sm sm:grid-cols-2">
              <div className="min-w-0">
                <dt className="mb-1 text-sm text-slate-300">{t('improvedQuestion')}</dt>
                <dd className="whitespace-pre-wrap break-words text-sand-100">{report.details.question ?? t('notAvailable')}</dd>
              </div>
              <div className="min-w-0">
                <dt className="mb-1 text-sm text-slate-300">{t('gameDateTarget')}</dt>
                <dd className="break-words text-sand-100"><time dateTime={report.details.game_date}>{report.details.game_date}</time> · {report.details.target_name}</dd>
              </div>
              <div className="min-w-0 sm:col-span-2">
                <dt className="mb-1 text-sm text-slate-300">{t('explanation')}</dt>
                <dd className="whitespace-pre-wrap break-words leading-relaxed text-sand-100">{report.details.explanation || t('noExplanation')}</dd>
              </div>
              <div className="min-w-0 sm:col-span-2">
                <details className="border-t border-white/10 pt-3">
                  <summary className="cursor-pointer text-sm text-emerald-300">{t('recordDetails')}</summary>
                  <dl className="mt-3 grid gap-3 sm:grid-cols-2">
                    <div><dt className="text-sm text-slate-300">{t('reportId')}</dt><dd>{report.id}</dd></div>
                    <div><dt className="text-sm text-slate-300">{t('questionId')}</dt><dd>{report.question_id}</dd></div>
                    <div><dt className="text-sm text-slate-300">{t('serverVersion')}</dt><dd className="break-words font-mono text-sm">{report.details.server_version ?? t('notRecorded')}</dd></div>
                    <div><dt className="text-sm text-slate-300">{t('dayId')}</dt><dd>{report.details.day_id}</dd></div>
                  </dl>
                </details>
              </div>
              <div className="min-w-0 sm:col-span-2">
                {report.details.context !== null && (
                  <details className="border-t border-white/10 pt-4">
                    <summary className="cursor-pointer text-sm text-emerald-300">{t('serverContext')}</summary>
                    <pre tabIndex={0} aria-label={t('serverContext')} className="admin-diagnostics mt-3 max-h-96 overflow-auto whitespace-pre-wrap break-words">{report.details.context || t('noContext')}</pre>
                  </details>
                )}
              </div>
            </dl>
          </article>
        ))}
      </div>

      {currentResult && !currentResult.error && (
        <nav aria-label={t('pagination')} className="flex flex-wrap items-center justify-between gap-3 text-sm text-slate-300">
          <p>{t('page', { page: query.page, pages: totalPages, count: currentResult.total })}</p>
          <div className="flex gap-2">
            <button type="button" disabled={busyId !== null || query.page <= 1} onClick={() => changeQuery({ page: query.page - 1 })} className="admin-button">{t('previous')}</button>
            <button type="button" disabled={busyId !== null || query.page >= totalPages} onClick={() => changeQuery({ page: query.page + 1 })} className="admin-button">{t('next')}</button>
          </div>
        </nav>
      )}
    </section>
  );
}
