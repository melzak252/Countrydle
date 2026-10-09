import React from 'react';
import { Calendar, HelpCircle, Target, Trophy, Users } from 'lucide-react';
import { useTranslation } from 'react-i18next';

export interface AdminModeStats {
  mode_key: string;
  mode_label: string;
  target_name: string;
  players: number;
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
  today?: {
    total_players: number;
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
  onRefresh: () => void;
}

export const AdminOverviewTab: React.FC<AdminOverviewTabProps> = ({ overview, isLoading, error, onRefresh }) => {
  const { t, i18n } = useTranslation();
  const hasOverview = overview !== null;
  const locale = i18n.language.startsWith('pl') ? 'pl-PL' : 'en-US';
  const numberFormat = new Intl.NumberFormat(locale);
  const dateFormat = new Intl.DateTimeFormat(locale, { timeZone: 'UTC', dateStyle: 'medium' });
  const metrics = [
    { label: t('adminOverview.metrics.players'), value: overview?.today?.total_players, note: t('adminOverview.metrics.playersNote'), Icon: Users },
    { label: t('adminOverview.metrics.questions'), value: overview?.today?.total_questions, note: t('adminOverview.metrics.questionsNote'), Icon: HelpCircle },
    { label: t('adminOverview.metrics.guesses'), value: overview?.today?.total_guesses, note: t('adminOverview.metrics.guessesNote'), Icon: Target },
    { label: t('adminOverview.metrics.winRate'), value: overview?.today?.win_rate_pct === undefined ? undefined : `${numberFormat.format(overview.today.win_rate_pct)}%`, note: overview?.today ? t('adminOverview.metrics.winners', { count: overview.today.total_winners }) : '—', Icon: Trophy },
  ];

  return (
    <section className="min-w-0 space-y-6" aria-labelledby="admin-page-title">
      <div className="flex justify-end">
        <button type="button" className="admin-button" onClick={onRefresh} disabled={isLoading}>
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
              <article key={label} className="admin-panel space-y-3">
                <div className="flex items-center justify-between gap-3">
                  <h2 className="admin-meta">{label}</h2>
                  <Icon size={18} aria-hidden="true" className="text-emerald-300" />
                </div>
                <p className="admin-metric tabular-nums">{value === undefined ? '—' : typeof value === 'number' ? numberFormat.format(value) : value}</p>
                <p className="text-sm leading-5 text-slate-300">{note}</p>
              </article>
            ))}
          </div>

          <section className="space-y-3" aria-labelledby="admin-overview-games">
            <h2 id="admin-overview-games" className="text-lg font-semibold text-sand-100">{t('adminOverview.gamesTitle')}</h2>
            {(overview.modes_today?.length ?? 0) === 0 ? (
              <p className="admin-panel admin-muted">{t('adminOverview.noModes')}</p>
            ) : (
              <div className="grid grid-cols-1 gap-4 min-[768px]:grid-cols-2 min-[1280px]:grid-cols-3">
                {overview.modes_today?.map((mode) => {
                  const difficulty = mode.players === 0
                    ? t('adminOverview.difficulty.noAttempts')
                    : mode.win_rate_pct >= 70
                      ? t('adminOverview.difficulty.high')
                      : mode.win_rate_pct >= 40
                        ? t('adminOverview.difficulty.moderate')
                        : t('adminOverview.difficulty.challenging');
                  return (
                    <article key={mode.mode_key} className="admin-panel space-y-4">
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <div className="min-w-0">
                          <p className="admin-meta">{mode.mode_label}</p>
                          <h3 className="mt-1 break-words text-base font-semibold text-sand-100">{mode.target_name}</h3>
                        </div>
                        <span className="admin-badge">{difficulty}</span>
                      </div>
                      <dl className="space-y-2 border-t border-white/10 pt-3 text-sm">
                        <div className="flex justify-between gap-4"><dt className="text-slate-300">{t('adminOverview.players')}</dt><dd className="admin-number">{numberFormat.format(mode.players)}</dd></div>
                        <div className="flex justify-between gap-4"><dt className="text-slate-300">{t('adminOverview.solved')}</dt><dd className="admin-number text-emerald-300">{numberFormat.format(mode.winners)} ({numberFormat.format(mode.win_rate_pct)}%)</dd></div>
                        {mode.avg_questions_won !== undefined && mode.avg_questions_won > 0 && <div className="flex justify-between gap-4"><dt className="text-slate-300">{t('adminOverview.averageQuestions')}</dt><dd className="admin-number">{numberFormat.format(mode.avg_questions_won)}</dd></div>}
                        {mode.avg_guesses_won !== undefined && mode.avg_guesses_won > 0 && <div className="flex justify-between gap-4"><dt className="text-slate-300">{t('adminOverview.averageGuesses')}</dt><dd className="admin-number">{numberFormat.format(mode.avg_guesses_won)}</dd></div>}
                        <div className="flex justify-between gap-4"><dt className="text-slate-300">{t('adminOverview.questions')}</dt><dd className="admin-number">{numberFormat.format(mode.questions)}</dd></div>
                        <div className="flex justify-between gap-4"><dt className="text-slate-300">{t('adminOverview.guesses')}</dt><dd className="admin-number">{numberFormat.format(mode.guesses)}</dd></div>
                      </dl>
                    </article>
                  );
                })}
              </div>
            )}
          </section>

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
