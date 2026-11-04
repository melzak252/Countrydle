import React, { useEffect, useState } from 'react';
import { Activity, Calendar, DollarSign, Trophy, Users } from 'lucide-react';
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
    { label: 'Known players today', value: overview?.today?.total_players, note: 'Accounts + guest browsers', Icon: Users },
    { label: 'Sessions today', value: overview?.today?.total_sessions, note: 'Saved game sessions', Icon: Activity },
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
        <div role="alert" className="admin-panel flex flex-wrap items-center justify-between gap-3 border-rose-400/40 text-rose-200">
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
          <div className="grid grid-cols-1 gap-4 min-[640px]:grid-cols-2 min-[1280px]:grid-cols-4">
            {metrics.map(({ label, value, note, Icon }) => (
              <article key={label} className="admin-panel space-y-1 !p-3">
                <div className="flex items-center justify-between gap-3">
                  <h2 className="admin-meta">{label}</h2>
                  <Icon size={18} aria-hidden="true" className="text-emerald-300" />
                </div>
                <p className={label === 'Countrydle AI cost' ? 'text-xl font-semibold text-sand-100 tabular-nums sm:text-2xl' : 'admin-metric tabular-nums'}>{value === undefined ? '—' : typeof value === 'number' ? numberFormat.format(value) : value}</p>
                <p className="text-xs leading-4 text-slate-400">{note}</p>
              </article>
            ))}
          </div>

          <section className="space-y-3" aria-labelledby="admin-overview-games">
            <h2 id="admin-overview-games" className="text-lg font-semibold text-sand-100">{t('adminOverview.gamesTitle')} <span className="admin-meta">· {overview.date} UTC</span></h2>
            {(overview.modes_today?.length ?? 0) === 0 ? (
              <p className="admin-panel admin-muted">{t('adminOverview.noModes')}</p>
            ) : (
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {overview.modes_today?.map((mode) => (
                  <button key={mode.mode_key} type="button" onClick={() => onOpenSessions(mode.mode_key)} className="admin-panel min-w-0 space-y-1 !p-3 text-left hover:border-emerald-400/60 focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-300">
                    <span className="block font-semibold text-sand-100">{mode.mode_label}</span>
                    <span className="block break-words text-sm text-slate-300">{mode.target_name}</span>
                    <span className="block text-sm text-slate-300">{numberFormat.format(mode.players)} known players · {numberFormat.format(mode.sessions)} sessions · {numberFormat.format(mode.winners)} solved ({numberFormat.format(mode.win_rate_pct)}%)</span>
                    <span className="block text-sm text-emerald-300">View sessions →</span>
                  </button>
                ))}
              </div>
            )}
          </section>
          <details className="text-xs text-slate-400">
            <summary className="cursor-pointer text-emerald-300">Coverage and cost basis</summary>
            <p className="mt-2">Known players are identified accounts and guest browsers; unidentifiable legacy sessions are excluded from player counts, not sessions. Saved sessions include zero-move games and recovered histories, not general site traffic or human views. AI cost covers measured Countrydle Gemini planner and fallback usage only, not platform spend; incomplete coverage is not total cost. The cost date is the completed UTC day shown, not today.</p>
            <button type="button" className="mt-2 text-emerald-300 underline" onClick={onOpenCosts}>View cost details</button>
          </details>

          <section className="space-y-3" aria-labelledby="admin-overview-history">
            <div className="flex items-center gap-2">
              <Calendar size={18} aria-hidden="true" className="text-slate-300" />
              <h2 id="admin-overview-history" className="text-lg font-semibold text-sand-100">{t('adminOverview.historyTitle')}</h2>
            </div>
            {!overview.history_14d?.length ? (
              <p className="admin-panel admin-muted">{t('adminOverview.noHistory')}</p>
            ) : (
              <div className="admin-table overflow-x-auto" role="region" aria-label={t('adminOverview.historyRegion')} tabIndex={0}>
                <table className="w-full min-w-[840px] text-sm">
                  <thead><tr>
                    <th scope="col" className="sticky left-0 z-10 bg-obsidian-850 px-4 py-3 text-left">{t('adminOverview.columns.date')}</th>
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
                        <th scope="row" className="sticky left-0 bg-obsidian-900 px-4 py-3 text-left font-medium text-sand-100">{dateFormat.format(new Date(`${day.date}T00:00:00Z`))}</th>
                        <td className="admin-number px-4 py-3 text-right">{numberFormat.format(day.total_players)}</td>
                        <td className="admin-number px-4 py-3 text-right text-emerald-300">{numberFormat.format(day.total_winners)}</td>
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
