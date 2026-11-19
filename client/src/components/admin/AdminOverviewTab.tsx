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
    { label: 'Unique players today', value: overview?.today?.total_players, note: 'Distinct accounts + guest browsers who played', Icon: Users },
    { label: 'Active sessions today', value: overview?.today?.total_sessions, note: 'Sum of played modes (excludes empty opens)', Icon: Activity },
    { label: 'Countrydle AI cost', value: costState === 'loading' ? 'Loading…' : costState === 'error' || costValue === '—' ? 'Unavailable' : costValue, note: costState === 'error' ? 'Report unavailable · refresh to retry' : cost ? `${cost.day} UTC · ${cost.cost_status.replaceAll('_', ' ')}` : 'No completed-day data', Icon: DollarSign },
    { label: 'Win rate today', value: overview?.today?.win_rate_pct === undefined ? undefined : `${numberFormat.format(overview.today.win_rate_pct)}%`, note: overview?.today ? t('adminOverview.metrics.winners', { count: overview.today.total_winners }) : '—', Icon: Trophy },
  ];

  return (
    <section className="min-w-0 space-y-4" aria-labelledby="admin-page-title">
      <div className="flex justify-end -mt-2">
        <button type="button" className="admin-button" onClick={() => { onRefresh(); setCostState('loading'); setCostRevision((value) => value + 1); }} disabled={isLoading}>
          {isLoading ? t('adminCommon.updating') : t('adminCommon.refresh')}
        </button>
      </div>
      {error && (
        <div role="alert" className="admin-panel flex flex-wrap items-center justify-between gap-3 border-rose-200 bg-rose-50 text-rose-900">
          <span>{t(error)}</span>
          {hasOverview && <p className="admin-meta w-full">{t('adminCommon.stale')}</p>}
          <button type="button" className="admin-button" onClick={onRefresh} disabled={isLoading}>
            {t('adminCommon.retry')}
          </button>
        </div>
      )}
      {!hasOverview && isLoading && <p role="status" className="admin-panel">{t('adminCommon.loading')}</p>}
      {!hasOverview && !isLoading && !error && <p className="admin-panel">{t('adminOverview.notLoaded')}</p>}
      {hasOverview && isLoading && <p role="status" className="admin-meta">{t('adminCommon.updating')}</p>}

      {hasOverview && (
        <>
          {!overview.today && <p className="admin-panel admin-muted">{t('adminOverview.noDailyStats')}</p>}
          <div className="grid grid-cols-2 gap-3 min-[1280px]:grid-cols-4">
            {metrics.map(({ label, value, note, Icon }) => (
              <article key={label} className="admin-panel admin-overview-metric">
                <div className="flex items-center justify-between gap-3">
                  <h2 className="admin-meta">{label}</h2>
                  <Icon size={18} aria-hidden="true" className="text-app-accent" />
                </div>
                <p className={label === 'Countrydle AI cost' ? 'text-xl font-semibold text-app-text tabular-nums sm:text-2xl' : 'admin-metric tabular-nums'}>{value === undefined ? '—' : typeof value === 'number' ? numberFormat.format(value) : value}</p>
                <p className="text-xs leading-4 text-app-text-muted">{note}</p>
              </article>
            ))}
          </div>

          <section className="space-y-3" aria-labelledby="admin-overview-games">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div>
                <h2 id="admin-overview-games" className="text-lg font-semibold text-app-text">{t('adminOverview.gamesTitle')}</h2>
                <p className="admin-meta mt-1">{overview.date} UTC · {numberFormat.format(overview.modes_today?.length ?? 0)} modes</p>
              </div>
              <label className="admin-overview-search">
                <span className="sr-only">Search modes and targets</span>
                <Search size={18} aria-hidden="true" />
                <input type="search" value={modeSearch} onChange={(event) => setModeSearch(event.target.value)} placeholder="Search modes and targets" />
              </label>
            </div>
            <p className="admin-overview-caveat">Participants are active accounts and guest browsers, not unique people. One person can use multiple browsers; guest play and a later login may not be linked.</p>
            {(overview.modes_today?.length ?? 0) === 0 ? (
              <p className="admin-panel admin-muted">{t('adminOverview.noModes')}</p>
            ) : filteredModes.length === 0 ? (
              <p className="admin-panel admin-muted" role="status">No modes or targets match “{modeSearch}”</p>
            ) : (
              <div className="admin-overview-mode-list" role="list" aria-label="Modes today">
                {filteredModes.map((mode) => (
                  <article key={mode.mode_key} className="admin-panel admin-overview-mode" role="listitem">
                    <div className="admin-overview-mode-title">
                      <h3 className="break-words font-semibold text-app-text">{mode.mode_label}</h3>
                      <p className="break-words text-sm text-app-text-secondary">{mode.target_name}</p>
                    </div>
                    <dl className="admin-overview-mode-stats">
                      <div><dt>Accounts + browsers</dt><dd>{numberFormat.format(mode.players)}</dd></div>
                      <div><dt>Sessions</dt><dd>{numberFormat.format(mode.sessions)}</dd></div>
                      <div><dt>Solved</dt><dd>{numberFormat.format(mode.winners)} <span>({numberFormat.format(mode.win_rate_pct)}%)</span></dd></div>
                      <div><dt>Questions / guesses</dt><dd>{numberFormat.format(mode.questions)} / {numberFormat.format(mode.guesses)}</dd></div>
                    </dl>
                    <button type="button" onClick={() => onOpenSessions(mode.mode_key)} className="admin-button admin-overview-session-link">View sessions</button>
                  </article>
                ))}
              </div>
            )}
          </section>
          <details className="admin-overview-coverage text-sm text-app-text-secondary">
            <summary className="cursor-pointer text-emerald-800">Coverage and cost basis</summary>
            <p className="mt-2">Participant counts combine active accounts and guest browsers; the same person may use multiple browsers, and guest play may not be linked to a later login. Unidentifiable legacy sessions are excluded from player counts, not sessions. Saved sessions include zero-move games and recovered histories, not general site traffic or human views. AI cost covers measured Countrydle Gemini planner and fallback usage only, not platform spend; incomplete coverage is not total cost. The cost date is the completed UTC day shown, not today.</p>
            <button type="button" className="mt-2 text-emerald-800 underline" onClick={onOpenCosts}>View cost details</button>
          </details>

          <section className="space-y-3" aria-labelledby="admin-overview-history">
            <div className="flex items-center gap-2">
              <Calendar size={18} aria-hidden="true" className="text-app-text-secondary" />
              <h2 id="admin-overview-history" className="text-lg font-semibold text-app-text">{t('adminOverview.historyTitle')}</h2>
            </div>
            {!overview.history_14d?.length ? (
              <p className="admin-panel admin-muted">{t('adminOverview.noHistory')}</p>
            ) : (
              <div className="admin-table overflow-x-auto" role="region" aria-label={t('adminOverview.historyRegion')} tabIndex={0}>
                <table className="w-full min-w-[840px] text-sm">
                  <thead><tr>
                    <th scope="col" className="sticky left-0 z-10 bg-app-surface-muted px-4 py-3 text-left">{t('adminOverview.columns.date')}</th>
                    <th scope="col" className="admin-number px-4 py-3">{t('adminOverview.columns.players')}</th>
                    <th scope="col" className="admin-number px-4 py-3">{t('adminOverview.columns.winners')}</th>
                    <th scope="col" className="admin-number px-4 py-3">{t('adminOverview.columns.winRate')}</th>
                    <th scope="col" className="admin-number px-4 py-3">{t('adminOverview.columns.averageQuestions')}</th>
                    <th scope="col" className="admin-number px-4 py-3">{t('adminOverview.columns.questions')}</th>
                    <th scope="col" className="admin-number px-4 py-3">{t('adminOverview.columns.guesses')}</th>
                  </tr></thead>
                  <tbody>
                    {overview.history_14d.map((day) => (
                      <tr key={day.date}>
                        <th scope="row" className="sticky left-0 bg-app-surface px-4 py-3 text-left font-medium text-app-text">{dateFormat.format(new Date(`${day.date}T00:00:00Z`))}</th>
                        <td className="admin-number px-4 py-3 text-right">{numberFormat.format(day.total_players)}</td>
                        <td className="admin-number px-4 py-3 text-right text-emerald-800">{numberFormat.format(day.total_winners)}</td>
                        <td className="admin-number px-4 py-3 text-right">{numberFormat.format(day.win_rate_pct)}%</td>
                        <td className="admin-number px-4 py-3 text-right">{day.avg_questions_won ? numberFormat.format(day.avg_questions_won) : '—'}</td>
                        <td className="admin-number px-4 py-3 text-right">{numberFormat.format(day.total_questions)}</td>
                        <td className="admin-number px-4 py-3 text-right">{numberFormat.format(day.total_guesses)}</td>
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
