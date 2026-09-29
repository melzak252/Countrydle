import { useEffect, useRef, useState } from 'react';
import { CheckCircle2, RefreshCw, RotateCcw, ShieldCheck } from 'lucide-react';
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

const controlClass = 'rounded-sm border border-white/10 bg-obsidian-950 px-3 py-2 text-sm text-sand-100 disabled:cursor-not-allowed disabled:opacity-40';

export default function TemplateDivergencesPanel({ onTestQuestion }: { onTestQuestion?: (question: string, mode: string) => void }) {
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
          setResult({ query, items: [], total: 0, error: 'Could not load divergences. Please refresh to try again.' });
        }
      });
    return () => { cancelled = true; };
  }, [query]);

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
      setNotice(`Divergence #${item.id} ${reviewed ? 'marked as reviewed' : 'reopened'}.`);
      setQuery((current) => ({ ...current, revision: current.revision + 1 }));
    } catch {
      if (mounted.current) {
        setActionError(`Could not update divergence #${item.id}.`);
      }
    } finally {
      if (mounted.current) {
        setBusyId(null);
      }
      mutationPending.current = false;
    }
  };

  return (
    <section aria-labelledby="template-divergences-title" className="min-w-0 space-y-5 animate-message">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <ShieldCheck size={20} className="text-emerald-400" />
            <h2 id="template-divergences-title" className="font-serif text-2xl text-sand-100">Template Shadow Audit</h2>
          </div>
          <p className="mt-1 text-sm text-sand-100/65">
            Background AI checks comparing fast template plans with Gemini 2.5 Flash Lite plans to detect subtle divergences.
          </p>
        </div>
        <button
          type="button"
          disabled={loading || busyId !== null}
          onClick={() => changeQuery({ revision: query.revision + 1 })}
          className={`${controlClass} flex items-center gap-2 hover:bg-white/5 cursor-pointer`}
        >
          <RefreshCw size={14} aria-hidden="true" className={loading ? 'animate-spin' : ''} />
          Refresh divergences
        </button>
      </div>

      <div className="flex flex-wrap gap-4">
        <label className="flex flex-col gap-1.5 text-xs text-sand-100/65">
          Status
          <select
            value={query.status}
            disabled={busyId !== null}
            onChange={(event) => changeQuery({ status: event.target.value as TemplateDivergenceStatus, page: 1 })}
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
            onChange={(event) => changeQuery({ mode: event.target.value, page: 1 })}
            className={controlClass}
          >
            <option value="">All modes</option>
            {Object.entries(MODE_LABELS).map(([modeKey, label]) => <option key={modeKey} value={modeKey}>{label}</option>)}
          </select>
        </label>
      </div>

      {notice && <p role="status" className="text-sm text-emerald-300">{notice}</p>}
      {actionError && <p role="alert" className="text-sm text-red-300">{actionError}</p>}

      <div aria-busy={loading} className="space-y-4">
        {loading ? (
          <p role="status" className="py-8 text-sm text-sand-100/65">Loading divergences…</p>
        ) : currentResult?.error ? (
          <p role="alert" className="border border-red-400/30 bg-red-400/5 p-4 text-sm text-red-300">{currentResult.error}</p>
        ) : currentResult?.items.length === 0 ? (
          <div className="rounded-sm border border-white/10 bg-obsidian-900 p-8 text-center text-sm text-sand-100/65">
            <CheckCircle2 size={24} className="mx-auto text-emerald-400 mb-2 opacity-80" />
            <p>No template divergences match these filters. Fast templates match Gemini plans cleanly.</p>
          </div>
        ) : currentResult?.items.map((item) => (
          <article key={item.id} className="min-w-0 space-y-4 rounded-sm border border-white/10 bg-obsidian-900 p-4 sm:p-6">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="space-y-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-sm font-semibold text-sand-100">
                    Divergence #{item.id} · {MODE_LABELS[item.mode] || item.mode}
                  </h3>
                  <span className="rounded-full border border-amber-400/30 bg-amber-400/10 px-2.5 py-0.5 text-[11px] font-mono font-medium text-amber-300">
                    {item.divergence_type}
                  </span>
                </div>
                <p className="break-words text-xs text-sand-100/65">
                  Captured <time dateTime={item.created_at}>{new Date(item.created_at).toLocaleString('en-US')}</time>
                </p>
                <p className={`text-xs ${item.reviewed_at ? 'text-sand-100/65' : 'text-emerald-300'}`}>
                  {item.reviewed_at ? <>Reviewed <time dateTime={item.reviewed_at}>{new Date(item.reviewed_at).toLocaleString('en-US')}</time></> : 'Open'}
                </p>
              </div>

              <div className="flex flex-wrap gap-2">
                {onTestQuestion && (
                  <button
                    type="button"
                    disabled={busyId !== null}
                    onClick={() => onTestQuestion(item.question, item.mode)}
                    className={`${controlClass} hover:border-emerald-400/40 hover:text-emerald-300 cursor-pointer`}
                  >
                    Test in QA
                  </button>
                )}
                <button
                  type="button"
                  disabled={busyId !== null}
                  onClick={() => void reviewDivergence(item)}
                  className={`${controlClass} flex items-center gap-2 hover:border-emerald-400/40 hover:text-emerald-300 cursor-pointer`}
                >
                  {item.reviewed_at ? <RotateCcw size={14} aria-hidden="true" /> : <CheckCircle2 size={14} aria-hidden="true" />}
                  {busyId === item.id ? 'Saving…' : item.reviewed_at ? 'Reopen' : 'Mark reviewed'}
                </button>
              </div>
            </div>

            <div className="rounded-sm border border-white/10 bg-obsidian-950/70 p-3.5 space-y-1">
              <span className="font-mono text-[10px] uppercase tracking-wider text-sand-100/60">Question</span>
              <p className="text-sm font-medium text-sand-100 break-words">{item.question}</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Template Plan */}
              <div className="rounded-sm border border-emerald-400/20 bg-emerald-400/[0.03] p-3.5 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[11px] font-semibold uppercase tracking-wider text-emerald-300">⚡ Template Fast Match</span>
                </div>
                {item.details?.template_improved_question && (
                  <p className="text-xs text-sand-100/80 italic">"{item.details.template_improved_question}"</p>
                )}
                <pre className="overflow-x-auto text-[11px] font-mono text-emerald-200/90 custom-scrollbar p-2 bg-obsidian-950/80 rounded-sm">
                  {JSON.stringify(item.template_plan, null, 2)}
                </pre>
              </div>

              {/* Gemini Plan */}
              <div className="rounded-sm border border-sky-400/20 bg-sky-400/[0.03] p-3.5 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[11px] font-semibold uppercase tracking-wider text-sky-300">🤖 Gemini 2.5 Flash Lite</span>
                </div>
                {item.details?.gemini_improved_question && (
                  <p className="text-xs text-sand-100/80 italic">"{item.details.gemini_improved_question}"</p>
                )}
                <pre className="overflow-x-auto text-[11px] font-mono text-sky-200/90 custom-scrollbar p-2 bg-obsidian-950/80 rounded-sm">
                  {JSON.stringify(item.gemini_plan, null, 2)}
                </pre>
              </div>
            </div>

            {item.details?.gemini_explanation && (
              <p className="text-xs text-zinc-400 border-l-2 border-amber-400/50 pl-3 py-0.5">
                <span className="font-semibold text-sand-100">Gemini explanation:</span> {item.details.gemini_explanation}
              </p>
            )}
          </article>
        ))}
      </div>

      {totalPages > 1 && (
        <div className="flex flex-wrap items-center justify-between gap-4 pt-2">
          <p className="text-xs text-sand-100/65">
            Page {query.page} of {totalPages} ({currentResult?.total ?? 0} divergences)
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              disabled={query.page <= 1 || loading}
              onClick={() => changeQuery({ page: query.page - 1 })}
              className={`${controlClass} hover:bg-white/5 cursor-pointer`}
            >
              Previous
            </button>
            <button
              type="button"
              disabled={query.page >= totalPages || loading}
              onClick={() => changeQuery({ page: query.page + 1 })}
              className={`${controlClass} hover:bg-white/5 cursor-pointer`}
            >
              Next
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
