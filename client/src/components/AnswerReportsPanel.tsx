import { useEffect, useRef, useState } from 'react';
import { CheckCircle2, RefreshCw, RotateCcw } from 'lucide-react';
import { adminService } from '../services/api';
import type { AnswerReport, AnswerReportMode, AnswerReportStatus } from '../types';

const PAGE_SIZE = 25;
const MODE_LABELS: Record<AnswerReportMode, string> = {
  countrydle: 'Countrydle',
  us_statedle: 'US Statedle',
  powiatdle: 'Powiatdle',
  wojewodztwodle: 'Województwodle',
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

const controlClass = 'rounded-sm border border-white/10 bg-obsidian-950 px-3 py-2 text-sm text-sand-100 disabled:cursor-not-allowed disabled:opacity-40';

export default function AnswerReportsPanel() {
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
          setResult({ query, items: [], total: 0, error: 'Could not load reports. Please refresh to try again.' });
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
      setNotice(`Report #${report.id} ${reviewed ? 'marked reviewed' : 'reopened'}.`);
      // Invalidate the page before fetching so rows never retain a stale review status.
      setQuery((current) => ({ ...current, revision: current.revision + 1 }));
    } catch {
      if (mounted.current) setActionError(`Could not update report #${report.id}. Please try again.`);
    } finally {
      mutationPending.current = false;
      if (mounted.current) setBusyId(null);
    }
  };

  return (
    <section aria-labelledby="answer-reports-title" className="min-w-0 space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 id="answer-reports-title" className="font-serif text-2xl text-sand-100">Answer reports</h2>
          <p className="mt-1 text-sm text-sand-100/65">Player feedback with the original, server-recorded answer context.</p>
        </div>
        <button
          type="button"
          disabled={loading || busyId !== null}
          onClick={() => changeQuery({ revision: query.revision + 1 })}
          className={`${controlClass} flex items-center gap-2 hover:bg-white/5`}
        >
          <RefreshCw size={14} aria-hidden="true" className={loading ? 'animate-spin' : ''} />
          Refresh reports
        </button>
      </div>

      <div className="flex flex-wrap gap-4">
        <label className="flex flex-col gap-1.5 text-xs text-sand-100/65">
          Status
          <select
            value={query.status}
            disabled={busyId !== null}
            onChange={(event) => changeQuery({ status: event.target.value as AnswerReportStatus, page: 1 })}
            className={controlClass}
          >
            <option value="open">Open</option>
            <option value="reviewed">Reviewed</option>
            <option value="all">All statuses</option>
          </select>
        </label>
        <label className="flex flex-col gap-1.5 text-xs text-sand-100/65">
          Game mode
          <select
            value={query.mode}
            disabled={busyId !== null}
            onChange={(event) => changeQuery({ mode: event.target.value as AnswerReportMode | '', page: 1 })}
            className={controlClass}
          >
            <option value="">All modes</option>
            {Object.entries(MODE_LABELS).map(([mode, label]) => <option key={mode} value={mode}>{label}</option>)}
          </select>
        </label>
      </div>

      {notice && <p role="status" className="text-sm text-emerald-300">{notice}</p>}
      {actionError && <p role="alert" className="text-sm text-red-300">{actionError}</p>}
      <div aria-busy={loading} className="space-y-4">
        {loading ? (
          <p role="status" className="py-8 text-sm text-sand-100/65">Loading reports…</p>
        ) : currentResult?.error ? (
          <p role="alert" className="border border-red-400/30 bg-red-400/5 p-4 text-sm text-red-300">{currentResult.error}</p>
        ) : currentResult?.items.length === 0 ? (
          <p role="status" className="rounded-sm border border-white/10 bg-obsidian-900 p-8 text-sm text-sand-100/65">No reports match these filters.</p>
        ) : currentResult?.items.map((report) => (
          <article key={report.id} aria-labelledby={`report-${report.id}-title`} className="min-w-0 space-y-5 rounded-sm border border-white/10 bg-obsidian-900 p-4 sm:p-6">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="space-y-1">
                <h3 id={`report-${report.id}-title`} className="text-sm font-semibold text-sand-100">
                  Report #{report.id} · {MODE_LABELS[report.mode]}
                </h3>
                <p className="break-words text-xs text-sand-100/65">
                  {report.reporter_username || 'Guest'} · Submitted <time dateTime={report.created_at}>{new Date(report.created_at).toLocaleString('en-US')}</time>
                </p>
                <p className={`text-xs ${report.reviewed_at ? 'text-sand-100/65' : 'text-emerald-300'}`}>
                  {report.reviewed_at ? <>Reviewed <time dateTime={report.reviewed_at}>{new Date(report.reviewed_at).toLocaleString('en-US')}</time></> : 'Open'}
                </p>
              </div>
              <button
                type="button"
                disabled={busyId !== null}
                onClick={() => void reviewReport(report)}
                aria-label={`${report.reviewed_at ? 'Reopen' : 'Mark reviewed'} report #${report.id}`}
                className={`${controlClass} flex items-center gap-2 hover:border-emerald-400/40 hover:text-emerald-300`}
              >
                {report.reviewed_at ? <RotateCcw size={14} aria-hidden="true" /> : <CheckCircle2 size={14} aria-hidden="true" />}
                {busyId === report.id ? 'Saving…' : report.reviewed_at ? 'Reopen' : 'Mark reviewed'}
              </button>
            </div>

            <div className="border-l-2 border-emerald-400/50 bg-emerald-400/5 p-4">
              <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-emerald-300">Player comment</p>
              <p className="whitespace-pre-wrap break-words text-base leading-relaxed text-sand-100">{report.comment}</p>
            </div>

            <dl className="grid min-w-0 grid-cols-1 gap-4 text-sm sm:grid-cols-2">
              <div className="min-w-0">
                <dt className="mb-1 text-xs text-sand-100/55">Original question · #{report.question_id}</dt>
                <dd className="whitespace-pre-wrap break-words text-sand-100">{report.details.original_question}</dd>
              </div>
              <div className="min-w-0">
                <dt className="mb-1 text-xs text-sand-100/55">Improved question</dt>
                <dd className="whitespace-pre-wrap break-words text-sand-100">{report.details.question ?? 'Not available'}</dd>
              </div>
              <div>
                <dt className="mb-1 text-xs text-sand-100/55">Classification / answer</dt>
                <dd className="font-semibold text-sand-100">
                  {report.details.valid ? 'Valid' : 'Invalid'} · {report.details.answer === null ? 'No yes/no answer' : report.details.answer ? 'YES' : 'NO'}
                </dd>
              </div>
              <div className="min-w-0">
                <dt className="mb-1 text-xs text-sand-100/55">Game date / target</dt>
                <dd className="break-words text-sand-100"><time dateTime={report.details.game_date}>{report.details.game_date}</time> · {report.details.target_name}</dd>
              </div>
              <div className="min-w-0 sm:col-span-2">
                <dt className="mb-1 text-xs text-sand-100/55">Explanation</dt>
                <dd className="whitespace-pre-wrap break-words leading-relaxed text-sand-100/80">{report.details.explanation || 'No explanation recorded.'}</dd>
              </div>
              <div className="min-w-0">
                <dt className="mb-1 text-xs text-sand-100/55">Server version</dt>
                <dd className="break-words font-mono text-xs text-sand-100/80">{report.details.server_version ?? 'Not recorded'}</dd>
              </div>
              <div>
                <dt className="mb-1 text-xs text-sand-100/55">Day ID</dt>
                <dd className="text-sand-100/80">{report.details.day_id}</dd>
              </div>
            </dl>
            {report.details.context !== null && (
              <details className="min-w-0 border-t border-white/10 pt-4">
                <summary className="cursor-pointer text-sm text-emerald-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-300">Server context (admin only)</summary>
                <pre className="mt-3 max-h-96 overflow-auto whitespace-pre-wrap break-words rounded-sm bg-obsidian-950 p-3 font-mono text-xs leading-relaxed text-sand-100/75">{report.details.context || 'No context recorded.'}</pre>
              </details>
            )}
          </article>
        ))}
      </div>

      {currentResult && !currentResult.error && (
        <nav aria-label="Report pages" className="flex flex-wrap items-center justify-between gap-3 text-xs text-sand-100/65">
          <p>Page {query.page} of {totalPages} · {currentResult.total} reports</p>
          <div className="flex gap-2">
            <button type="button" disabled={busyId !== null || query.page <= 1} onClick={() => changeQuery({ page: query.page - 1 })} className={`${controlClass} hover:bg-white/5`}>Previous</button>
            <button type="button" disabled={busyId !== null || query.page >= totalPages} onClick={() => changeQuery({ page: query.page + 1 })} className={`${controlClass} hover:bg-white/5`}>Next</button>
          </div>
        </nav>
      )}
    </section>
  );
}
