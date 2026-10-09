import { useCallback, useEffect, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { adminService } from '../../services/api';
import type { CountryCostDay, CountryCostReport, CountryCostUsage } from '../../types/countryCostReport';

const DAY_OPTIONS = [7, 14, 30] as const;
type Days = (typeof DAY_OPTIONS)[number];
const number = (value: number | null | undefined) => value == null ? '—' : new Intl.NumberFormat().format(value);
const usd = (value: number | null | undefined) => value == null ? '—' : `$${value.toFixed(6)}`;
const tokenFields: Array<[string, keyof CountryCostUsage]> = [
  ['Input tokens', 'input_tokens'], ['Cached input tokens', 'cached_input_tokens'],
  ['Output tokens', 'output_tokens'], ['Thinking tokens', 'thought_tokens'], ['Total tokens', 'total_tokens'],
  ['Unknown cached-input tokens', 'cached_input_unknown_tokens'], ['Calls with unknown usage', 'unknown_usage_calls'],
  ['Retries', 'retries'], ['Failed attempts', 'failed_attempts'], ['Planner calls', 'new_planner_calls'],
  ['Planner cache hits', 'plan_cache_hits'], ['Fallback cache hits', 'fallback_cache_hits'], ['Fallback model calls', 'fallback_model_calls'],
];

function UsageTable({ title, usage }: { title: string; usage: Record<string, CountryCostUsage> }) {
  const models = Object.entries(usage);
  if (!models.length) return null;
  return <div className="space-y-2">
    <h4 className="text-sm font-semibold text-sand-100">{title}</h4>
    <div className="overflow-x-auto rounded-sm border border-white/10">
      <table className="w-full min-w-[900px] text-left text-xs">
        <caption className="sr-only">{title} token and operation usage by model</caption>
        <thead className="bg-obsidian-850 text-[10px] uppercase tracking-wider text-sand-100/60"><tr>
          <th scope="col" className="p-2">Model</th>{tokenFields.map(([label]) => <th scope="col" key={label} className="p-2">{label}</th>)}
        </tr></thead>
        <tbody className="divide-y divide-white/5 font-mono">{models.map(([model, values]) => <tr key={model}>
          <th scope="row" className="p-2 text-left font-semibold text-sand-100">{model}</th>
          {tokenFields.map(([label, key]) => <td key={label} className="p-2 text-sand-100/75">{number(values[key] as number | undefined)}</td>)}
        </tr>)}</tbody>
      </table>
    </div>
  </div>;
}

function DayDetails({ day }: { day: CountryCostDay }) {
  const stages = Object.entries(day.stage_usage);
  return <details className="mt-3 rounded-sm border border-white/10 bg-obsidian-950/60 p-3">
    <summary className="cursor-pointer text-xs font-semibold text-emerald-300">Inspect stage and model usage</summary>
    <div className="mt-4 space-y-5">
      {stages.length ? stages.map(([stage, usage]) => <UsageTable key={stage} title={`${stage} stage`} usage={usage} />) : <p className="text-xs text-sand-100/60">No measured stage usage for this day.</p>}
      {day.unpriced_models.length > 0 && <p className="text-xs text-amber-200">Unpriced models: {day.unpriced_models.join(', ')}. Their usage is shown above when measured, but excluded from known-cost bounds.</p>}
      {Object.entries(day.unpriced_model_usage).length > 0 && <UsageTable title="Unpriced model usage" usage={day.unpriced_model_usage} />}
      {Object.values(day.priced_models).some((usage) => usage.unknown_usage_calls > 0) && <p className="text-xs text-amber-200">Some usage is unknown; displayed token counts cover measured calls only and cost bounds are an incomplete known-cost subset.</p>}
    </div>
  </details>;
}

function DailyRow({ day }: { day: CountryCostDay }) {
  const unmeasured = day.cost_status === 'no_data' || day.cost_status === 'not_measured';
  const incompleteUsage = day.unpriced_models.length > 0 || Object.values(day.priced_models).some((usage) => usage.cost_incomplete);
  const statusStyle = day.cost_status === 'complete' ? 'text-emerald-300 border-emerald-400/30 bg-emerald-400/10' : 'text-amber-200 border-amber-400/30 bg-amber-400/10';
  const statusLabels: Record<CountryCostDay['cost_status'], string> = {
    no_data: 'No measured data',
    not_measured: 'Not measured',
    incomplete_coverage: 'Partial startup day',
    incomplete: 'Incomplete known-cost subset',
    bounded: 'Cost estimate range',
    complete: 'Complete usage',
  };
  return <tr className="align-top hover:bg-white/5">
    <th scope="row" className="px-3 py-3 text-left font-semibold text-sand-100">{day.day}<DayDetails day={day} /></th>
    <td className="px-3 py-3 font-mono">{unmeasured ? '—' : number(day.requests)}</td><td className="px-3 py-3 font-mono">{number(day.completed_games)}</td>
    <td className="px-3 py-3 font-mono">{unmeasured ? '—' : number(day.template_answers)}</td><td className="px-3 py-3 font-mono">{unmeasured ? '—' : number(day.planner_cache_hits)}</td>
    <td className="px-3 py-3 font-mono">{unmeasured ? '—' : number(day.new_planner_calls)}</td>
    <td className="px-3 py-3 font-mono">{usd(day.cost_lower_usd)} – {usd(day.cost_upper_usd)}<div className="mt-1 text-sand-100/55">/ 1,000 games: {usd(day.cost_lower_per_1000_games_usd)} – {usd(day.cost_upper_per_1000_games_usd)}</div></td>
    <td className="px-3 py-3"><span className={`inline-block rounded border px-2 py-1 text-[10px] font-semibold ${statusStyle}`}>{statusLabels[day.cost_status]}</span>
      <p className="mt-1 text-[10px] text-sand-100/60">{day.measurement_coverage === 'none' ? 'Before measurement began' : day.measurement_coverage === 'partial_startup_day' ? 'Partial-day coverage; rates withheld' : 'After measurement began'}</p>
      {incompleteUsage && <p className="mt-1 max-w-48 text-[10px] leading-relaxed text-amber-100/75">Known-cost subset only; missing usage or unpriced models are excluded.</p>}
    </td>
  </tr>;
}

export default function AdminCountrydleCostsTab() {
  const [days, setDays] = useState<Days>(7);
  const [report, setReport] = useState<CountryCostReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [requestKey, setRequestKey] = useState(0);
  const load = useCallback(async (signal: AbortSignal) => {
    setLoading(true);
    setError(null);
    try { setReport(await adminService.getCountrydleCosts(days, signal)); }
    catch (cause) {
      if (!signal.aborted) setError(cause instanceof Error ? cause.message : 'Could not load cost report.');
    } finally { if (!signal.aborted) setLoading(false); }
  }, [days, requestKey]);
  useEffect(() => { const controller = new AbortController(); void load(controller.signal); return () => controller.abort(); }, [load]);

  return <section className="space-y-5" aria-labelledby="countrydle-costs-heading">
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div><h2 id="countrydle-costs-heading" className="text-xl font-semibold">Countrydle AI Costs</h2><p className="mt-1 text-xs text-sand-100/60">Daily UTC measurements; today is excluded. Cost estimates cover measured Gemini planner and fallback usage only.</p></div>
      <div className="flex flex-wrap items-center gap-2">
        <label htmlFor="cost-days" className="text-xs text-sand-100/70">Completed UTC days</label>
        <select id="cost-days" value={days} onChange={(event) => setDays(Number(event.target.value) as Days)} className="rounded-sm border border-white/15 bg-obsidian-900 px-3 py-2 text-sm text-sand-100">
          {DAY_OPTIONS.map((option) => <option key={option} value={option}>{option} days</option>)}
        </select>
        <button type="button" onClick={() => setRequestKey((value) => value + 1)} disabled={loading} className="flex items-center gap-2 rounded-sm border border-white/10 bg-obsidian-900 px-3 py-2 text-xs font-semibold hover:bg-white/5 disabled:opacity-50" aria-label="Refresh AI cost report">
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Refresh
        </button>
      </div>
    </div>
    {loading && !report && <div role="status" className="flex h-40 items-center justify-center text-sm text-sand-100/65"><span className="mr-3 h-6 w-6 animate-spin rounded-full border-2 border-emerald-400 border-t-transparent" />Loading cost report…</div>}
    {error && <div role="alert" className="rounded-sm border border-rose-400/30 bg-rose-400/10 p-4 text-sm text-rose-100"><p>Could not load Countrydle AI cost report: {error}</p><button type="button" onClick={() => setRequestKey((value) => value + 1)} className="mt-3 rounded-sm border border-white/15 px-3 py-2 text-xs font-semibold hover:bg-white/5">Retry</button></div>}
    {loading && report && <p role="status" className="text-xs text-sand-100/65">Refreshing report…</p>}
    {report && <>
      <div className="rounded-sm border border-white/10 bg-obsidian-900 p-4 text-xs leading-relaxed text-sand-100/70">
        <p className="font-semibold text-sand-100">UTC period: {report.period_utc.start} – {report.period_utc.end}</p>
        <p className="mt-2">Metrics store started: {report.metrics_started_at_utc ?? 'Unknown / no measurement store start recorded'}</p>
        <p className="mt-2">{report.coverage_note}</p><p className="mt-2">{report.denominator_note}</p><p className="mt-2">{report.scope_note}</p><p className="mt-2">{report.pricing_note}</p>
      </div>
      {!error && report.days.length === 0 && <p className="rounded-sm border border-white/10 bg-obsidian-900 p-6 text-center text-sm text-sand-100/65">No daily rows are available for this period.</p>}
      {report.days.length > 0 && <div className="overflow-x-auto rounded-sm border border-white/10">
        <table className="w-full min-w-[1100px] text-left text-xs">
          <caption className="sr-only">Daily Countrydle AI usage and cost bounds in UTC</caption>
          <thead className="bg-obsidian-850 text-[10px] uppercase tracking-wider text-sand-100/60"><tr>
            {['UTC day', 'Requests', 'Completed games', 'Template answers', 'Planner cache hits', 'Paid planner calls', 'Known cost bounds (USD)', 'Coverage / cost status'].map((heading) => <th key={heading} scope="col" className="px-3 py-3">{heading}</th>)}
          </tr></thead><tbody className="divide-y divide-white/5">{report.days.map((day) => <DailyRow key={day.day} day={day} />)}</tbody>
        </table>
      </div>}
      <p className="text-[11px] leading-relaxed text-amber-100/70">A dash (—) means the report supplied no value; it is never treated as zero. Incomplete costs are known-priced usage subsets, not total spend. Per-1,000-game costs are withheld when coverage cannot support them.</p>
    </>}
  </section>;
}
