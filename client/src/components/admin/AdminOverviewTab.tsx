import React, { useEffect, useMemo, useState } from 'react';
import { Activity, Calendar, DollarSign, Search, Trophy, Users } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { adminService } from '../../services/api';
import type { CountryCostDay } from '../../types/countryCostReport';

export interface AdminModeStats {
  mode_key: string;
  mode_label: string;
  target_name: string;
  players: number;
  sessions: number;
  winners: number;
  win_rate_pct: number;
  questions: number;
  guesses: number;
  avg_questions_won?: number;
  avg_guesses_won?: number;
}

export interface AdminHistoryDay {
  date: string;
  total_players: number;
  total_winners: number;
  win_rate_pct: number;
  total_questions: number;
  total_guesses: number;
  avg_questions_won?: number;
  avg_guesses_won?: number;
}

export interface AdminOverviewData {
  date: string;
  today?: {
    total_players: number;
    total_sessions: number;
    total_questions: number;
    total_guesses: number;
    win_rate_pct: number;
    total_winners: number;
  };
  modes_today?: AdminModeStats[];
  history_14d?: AdminHistoryDay[];
}

interface AdminOverviewTabProps {
  overview: AdminOverviewData | null;
  isLoading: boolean;
  error: string | null;
  onOpenSessions: (mode: string) => void;
  onOpenCosts: () => void;
  onRefresh: () => void;
}

export const AdminOverviewTab: React.FC<AdminOverviewTabProps> = ({ overview, isLoading, error, onRefresh, onOpenSessions, onOpenCosts }) => {
  const { t } = useTranslation();
  const hasOverview = overview !== null;
  const locale = 'en-US';
  const numberFormat = new Intl.NumberFormat(locale);
  const dateFormat = new Intl.DateTimeFormat(locale, { timeZone: 'UTC', dateStyle: 'medium' });
  const [cost, setCost] = useState<CountryCostDay | null>(null);
  const [costState, setCostState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [costRevision, setCostRevision] = useState(0);
  const [modeSearch, setModeSearch] = useState('');
  const filteredModes = useMemo(() => {
    const query = modeSearch.trim().toLocaleLowerCase(locale);
    const modes = overview?.modes_today ?? [];
    return query
      ? modes.filter((mode) => `${mode.mode_label} ${mode.target_name} ${mode.mode_key}`.toLocaleLowerCase(locale).includes(query))
      : modes;
  }, [locale, modeSearch, overview?.modes_today]);
  useEffect(() => {
    const controller = new AbortController();
    adminService.getCountrydleCosts(1, controller.signal).then((report) => {
      if (!controller.signal.aborted) { setCost(report.days[0] ?? null); setCostState('ready'); }
    }).catch(() => { if (!controller.signal.aborted) setCostState('error'); });
    return () => controller.abort();
  }, [costRevision]);
  const costValue = cost?.cost_lower_usd == null || cost.cost_upper_usd == null
    ? '—'
    : cost.cost_lower_usd === cost.cost_upper_usd
      ? `$${cost.cost_lower_usd.toFixed(4)}`
      : `$${cost.cost_lower_usd.toFixed(4)}–$${cost.cost_upper_usd.toFixed(4)}`;
  const metrics = [
    { label: 'Participating identities', value: overview?.today?.total_players, note: 'Accounts + guest browsers, not people', Icon: Users },
    { label: 'Sessions today', value: overview?.today?.total_sessions, note: 'Saved game sessions', Icon: Activity },
    { label: 'Countrydle AI cost', value: costState === 'loading' ? 'Loading…' : costState === 'error' || costValue === '—' ? 'Unavailable' : costValue, note: costState === 'error' ? 'Report unavailable · refresh to retry' : cost ? `${cost.day} UTC · ${cost.cost_status.replaceAll('_', ' ')}` : 'No completed-day data', Icon: DollarSign },
    { label: 'Win rate today', value: overview?.today?.win_rate_pct === undefined ? undefined : `${numberFormat.format(overview.today.win_rate_pct)}%`, note: overview?.today ? t('adminOverview.metrics.winners', { count: overview.today.total_winners }) : '—', Icon: Trophy },
  ];

  return (
    <section className="min-w-0 space-y-4 bg-app-canvas text-app-text" aria-labelledby="admin-page-title">
      <div className="flex justify-end -mt-2">
        <button type="button" className="min-h-11 rounded-md border border-app-border bg-app-surface-muted px-3 py-2 text-sm font-medium text-app-text transition-colors hover:bg-app-surface-raised focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus disabled:cursor-not-allowed disabled:opacity-50" onClick={() => { onRefresh(); setCostState('loading'); setCostRevision((value) => value + 1); }} disabled={isLoading}>
          {isLoading ? t('adminCommon.updating') : t('adminCommon.refresh')}
        </button>
      </div>
      {error && (
        <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-rose-300 bg-rose-50 p-4 text-rose-800">
          <span>{t(error)}</span>
          {hasOverview && <p className="w-full text-sm text-rose-700">{t('adminCommon.stale')}</p>}
          <button type="button" className="min-h-11 rounded-md border border-rose-300 bg-white px-3 py-2 text-sm font-medium text-rose-800 transition-colors hover:bg-rose-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus disabled:cursor-not-allowed disabled:opacity-50" onClick={onRefresh} disabled={isLoading}>
            {t('adminCommon.retry')}
          </button>
        </div>
      )}
      {!hasOverview && isLoading && <p role="status" className="rounded-md border border-app-border bg-app-surface p-4 text-app-text-secondary">{t('adminCommon.loading')}</p>}
      {!hasOverview && !isLoading && !error && <p className="rounded-md border border-app-border bg-app-surface p-4 text-app-text-secondary">{t('adminOverview.notLoaded')}</p>}
      {hasOverview && isLoading && <p role="status" className="text-sm text-app-text-muted">{t('adminCommon.updating')}</p>}

      {hasOverview && (
        <>
          {!overview.today && <p className="rounded-md border border-app-border bg-app-surface p-4 text-app-text-secondary">{t('adminOverview.noDailyStats')}</p>}
          <div className="grid grid-cols-2 gap-3 min-[1280px]:grid-cols-4">
            {metrics.map(({ label, value, note, Icon }) => (
              <article key={label} className="flex min-w-0 flex-col justify-between gap-2 rounded-md border border-app-border bg-app-surface p-4">
                <div className="flex items-center justify-between gap-3">
                  <h2 className="text-xs font-semibold text-app-text-muted">{label}</h2>
                  <Icon size={18} aria-hidden="true" className="text-app-accent" />
                </div>
                <p className={label === 'Countrydle AI cost' ? 'text-xl font-semibold text-app-text tabular-nums sm:text-2xl' : 'text-2xl font-semibold leading-tight text-app-text tabular-nums'}>{value === undefined ? '—' : typeof value === 'number' ? numberFormat.format(value) : value}</p>
                <p className={costState === 'error' && label === 'Countrydle AI cost' ? 'text-xs leading-4 text-rose-700' : 'text-xs leading-4 text-app-text-muted'}>{note}</p>
              </article>
            ))}
          </div>

          <section className="space-y-3" aria-labelledby="admin-overview-games">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div>
                <h2 id="admin-overview-games" className="text-lg font-semibold text-app-text">{t('adminOverview.gamesTitle')}</h2>
                <p className="mt-1 text-sm text-app-text-muted">{overview.date} UTC · {numberFormat.format(overview.modes_today?.length ?? 0)} modes</p>
              </div>
              <label className="flex min-h-11 w-full max-w-[360px] items-center gap-2.5 rounded-md border border-app-border bg-app-surface px-3 text-app-text-secondary focus-within:border-app-accent focus-within:ring-2 focus-within:ring-app-focus">
                <span className="sr-only">Search modes and targets</span>
                <Search size={18} aria-hidden="true" />
                <input type="search" value={modeSearch} onChange={(event) => setModeSearch(event.target.value)} placeholder="Search modes and targets" className="min-h-10 w-full min-w-0 border-0 bg-transparent p-0 text-sm text-app-text placeholder:text-app-text-muted focus:outline-none focus:ring-0" />
              </label>
            </div>
            <p className="border-l-2 border-app-accent py-2 pl-3 text-sm leading-5 text-app-text-secondary">Participants are active accounts and guest browsers, not unique people. One person can use multiple browsers; guest play and a later login may not be linked.</p>
            {(overview.modes_today?.length ?? 0) === 0 ? (
              <p className="rounded-md border border-app-border bg-app-surface p-4 text-app-text-secondary">{t('adminOverview.noModes')}</p>
            ) : filteredModes.length === 0 ? (
              <p className="rounded-md border border-app-border bg-app-surface p-4 text-app-text-secondary" role="status">No modes or targets match “{modeSearch}”</p>
            ) : (
              <div className="grid grid-cols-1 gap-2" role="list" aria-label="Modes today">
                {filteredModes.map((mode) => (
                  <article key={mode.mode_key} className="grid min-w-0 gap-3 rounded-md border border-app-border bg-app-surface p-4 md:grid-cols-[minmax(180px,1fr)_minmax(0,2fr)_auto] md:items-center md:gap-5" role="listitem">
                    <div className="min-w-0">
                      <h3 className="break-words font-semibold text-app-text">{mode.mode_label}</h3>
                      <p className="break-words text-sm text-app-text-secondary">{mode.target_name}</p>
                    </div>
                    <dl className="grid min-w-0 grid-cols-2 gap-3 md:grid-cols-4 [&>div]:min-w-0">
                      <div><dt className="text-xs leading-4 text-app-text-muted">Accounts + browsers</dt><dd className="mt-1 break-words text-lg font-semibold leading-6 text-app-text tabular-nums">{numberFormat.format(mode.players)}</dd></div>
                      <div><dt className="text-xs leading-4 text-app-text-muted">Sessions</dt><dd className="mt-1 break-words text-lg font-semibold leading-6 text-app-text tabular-nums">{numberFormat.format(mode.sessions)}</dd></div>
                      <div><dt className="text-xs leading-4 text-app-text-muted">Solved</dt><dd className="mt-1 break-words text-lg font-semibold leading-6 text-app-text tabular-nums">{numberFormat.format(mode.winners)} <span className="text-sm font-normal text-app-text-secondary">({numberFormat.format(mode.win_rate_pct)}%)</span></dd></div>
                      <div><dt className="text-xs leading-4 text-app-text-muted">Questions / guesses</dt><dd className="mt-1 break-words text-lg font-semibold leading-6 text-app-text tabular-nums">{numberFormat.format(mode.questions)} / {numberFormat.format(mode.guesses)}</dd></div>
                    </dl>
                    <button type="button" onClick={() => onOpenSessions(mode.mode_key)} className="inline-flex min-h-11 items-center justify-center justify-self-start rounded-sm border border-app-accent px-3 py-2 text-sm font-medium text-app-accent transition-colors hover:bg-app-surface-muted focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus">View sessions</button>
                  </article>
                ))}
              </div>
            )}
          </section>
          <details className="rounded-md border border-app-border bg-app-surface p-4 text-sm text-app-text-secondary">
            <summary className="min-h-11 cursor-pointer py-2 font-medium text-app-accent">Coverage and cost basis</summary>
            <p className="mt-2">Participant counts combine active accounts and guest browsers; the same person may use multiple browsers, and guest play may not be linked to a later login. Unidentifiable legacy sessions are excluded from player counts, not sessions. Saved sessions include zero-move games and recovered histories, not general site traffic or human views. AI cost covers measured Countrydle Gemini planner and fallback usage only, not platform spend; incomplete coverage is not total cost. The cost date is the completed UTC day shown, not today.</p>
            <button type="button" className="mt-2 min-h-11 text-app-accent underline underline-offset-2 hover:text-app-accent-hover focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus" onClick={onOpenCosts}>View cost details</button>
          </details>

          <section className="space-y-3" aria-labelledby="admin-overview-history">
            <div className="flex items-center gap-2">
              <Calendar size={18} aria-hidden="true" className="text-app-text-muted" />
              <h2 id="admin-overview-history" className="text-lg font-semibold text-app-text">{t('adminOverview.historyTitle')}</h2>
            </div>
            {!overview.history_14d?.length ? (
              <p className="rounded-md border border-app-border bg-app-surface p-4 text-app-text-secondary">{t('adminOverview.noHistory')}</p>
            ) : (
              <div className="overflow-x-auto rounded-md border border-app-border bg-app-surface" role="region" aria-label={t('adminOverview.historyRegion')} tabIndex={0}>
                <table className="w-full min-w-[840px] border-collapse text-sm leading-5">
                  <thead><tr>
                    <th scope="col" className="sticky left-0 z-10 border-b border-app-border bg-app-surface-raised px-4 py-3 text-left font-semibold text-app-text-secondary">{t('adminOverview.columns.date')}</th>
                    <th scope="col" className="border-b border-app-border px-4 py-3 text-right font-semibold text-app-text-secondary tabular-nums">{t('adminOverview.columns.players')}</th>
                    <th scope="col" className="border-b border-app-border px-4 py-3 text-right font-semibold text-app-text-secondary tabular-nums">{t('adminOverview.columns.winners')}</th>
                    <th scope="col" className="border-b border-app-border px-4 py-3 text-right font-semibold text-app-text-secondary tabular-nums">{t('adminOverview.columns.winRate')}</th>
                    <th scope="col" className="border-b border-app-border px-4 py-3 text-right font-semibold text-app-text-secondary tabular-nums">{t('adminOverview.columns.averageQuestions')}</th>
                    <th scope="col" className="border-b border-app-border px-4 py-3 text-right font-semibold text-app-text-secondary tabular-nums">{t('adminOverview.columns.questions')}</th>
                    <th scope="col" className="border-b border-app-border px-4 py-3 text-right font-semibold text-app-text-secondary tabular-nums">{t('adminOverview.columns.guesses')}</th>
                  </tr></thead>
                  <tbody>
                    {overview.history_14d.map((day) => (
                      <tr key={day.date}>
                        <th scope="row" className="sticky left-0 border-b border-app-border bg-app-surface px-4 py-3 text-left font-medium text-app-text">{dateFormat.format(new Date(`${day.date}T00:00:00Z`))}</th>
                        <td className="border-b border-app-border px-4 py-3 text-right text-app-text-secondary tabular-nums">{numberFormat.format(day.total_players)}</td>
                        <td className="border-b border-app-border px-4 py-3 text-right text-emerald-700 tabular-nums">{numberFormat.format(day.total_winners)}</td>
                        <td className="border-b border-app-border px-4 py-3 text-right text-app-text-secondary tabular-nums">{numberFormat.format(day.win_rate_pct)}%</td>
                        <td className="border-b border-app-border px-4 py-3 text-right text-app-text-secondary tabular-nums">{day.avg_questions_won ? numberFormat.format(day.avg_questions_won) : '—'}</td>
                        <td className="border-b border-app-border px-4 py-3 text-right text-app-text-secondary tabular-nums">{numberFormat.format(day.total_questions)}</td>
                        <td className="border-b border-app-border px-4 py-3 text-right text-app-text-secondary tabular-nums">{numberFormat.format(day.total_guesses)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
    </section>
  );
};

export default AdminOverviewTab;
