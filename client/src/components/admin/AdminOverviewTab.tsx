import React, { useEffect, useMemo, useState } from 'react';
import { Activity, Calendar, ChevronRight, DollarSign, RefreshCw, Search, Trophy, Users } from 'lucide-react';
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

type CategoryId = 'active' | 'all' | 'world' | 'poland' | 'uk_us' | 'symbols';

const CATEGORIES: { id: CategoryId; label: string }[] = [
  { id: 'active', label: 'Active Today' },
  { id: 'all', label: 'All Modes' },
  { id: 'world', label: 'World & Continents' },
  { id: 'poland', label: 'Poland' },
  { id: 'uk_us', label: 'UK & US' },
  { id: 'symbols', label: 'Symbols & Quizzes' },
];

function classifyModeCategory(modeKey: string): Exclude<CategoryId, 'active' | 'all'> {
  if (modeKey === 'countrydle' || modeKey === 'flagdle' || modeKey.startsWith('continental:')) {
    return 'world';
  }
  if (modeKey === 'powiatdle' || modeKey === 'wojewodztwodle' || modeKey === 'plates_quiz') {
    return 'poland';
  }
  if (modeKey === 'us_statedle' || modeKey === 'countydle' || modeKey.startsWith('map_quiz:')) {
    return 'uk_us';
  }
  return 'symbols';
}

export const AdminOverviewTab: React.FC<AdminOverviewTabProps> = ({
  overview,
  isLoading,
  error,
  onRefresh,
  onOpenSessions,
  onOpenCosts,
}) => {
  const hasOverview = overview !== null;
  const num = new Intl.NumberFormat('en-US');
  const dateFmt = new Intl.DateTimeFormat('en-US', { timeZone: 'UTC', dateStyle: 'medium' });

  const [cost, setCost] = useState<CountryCostDay | null>(null);
  const [costState, setCostState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [costRevision, setCostRevision] = useState(0);
  const [category, setCategory] = useState<CategoryId>('active');
  const [modeSearch, setModeSearch] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    adminService
      .getCountrydleCosts(1, controller.signal)
      .then((report) => {
        if (!controller.signal.aborted) {
          setCost(report.days[0] ?? null);
          setCostState('ready');
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) setCostState('error');
      });
    return () => controller.abort();
  }, [costRevision]);

  const allModes = useMemo(() => {
    const list = [...(overview?.modes_today ?? [])];
    list.sort((a, b) => b.sessions - a.sessions || b.players - a.players || a.mode_label.localeCompare(b.mode_label));
    return list;
  }, [overview?.modes_today]);

  const activeCount = useMemo(() => allModes.filter((m) => m.sessions > 0).length, [allModes]);

  const filteredModes = useMemo(() => {
    const q = modeSearch.trim().toLowerCase();
    return allModes.filter((mode) => {
      if (category === 'active' && mode.sessions === 0) return false;
      if (category !== 'active' && category !== 'all' && classifyModeCategory(mode.mode_key) !== category) {
        return false;
      }
      if (!q) return true;
      return `${mode.mode_label} ${mode.target_name} ${mode.mode_key}`.toLowerCase().includes(q);
    });
  }, [allModes, category, modeSearch]);

  const costValue =
    cost?.cost_lower_usd == null || cost.cost_upper_usd == null
      ? null
      : cost.cost_lower_usd === cost.cost_upper_usd
        ? `$${cost.cost_lower_usd.toFixed(4)}`
        : `$${cost.cost_lower_usd.toFixed(4)}-$${cost.cost_upper_usd.toFixed(4)}`;

  return (
    <section className="min-w-0 space-y-6" aria-labelledby="admin-page-title">
      {/* Header Row */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs font-mono uppercase tracking-wider text-app-text-muted">
            {overview?.date ? `${overview.date} UTC · Completed games only` : 'Completed games only'}
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            onRefresh();
            setCostState('loading');
            setCostRevision((v) => v + 1);
          }}
          disabled={isLoading}
          className="inline-flex items-center gap-1.5 rounded-sm border border-app-border bg-app-surface px-3 py-1.5 text-xs font-medium text-app-text hover:bg-app-surface-muted cursor-pointer disabled:opacity-50"
        >
          <RefreshCw size={13} className={isLoading ? 'animate-spin' : ''} aria-hidden="true" />
          {isLoading ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>

      {error && (
        <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-rose-300 bg-rose-50 px-4 py-3 text-sm text-rose-900">
          <span>{error}</span>
          <button type="button" onClick={onRefresh} disabled={isLoading} className="rounded-sm border border-rose-300 bg-white px-3 py-1 text-xs font-medium cursor-pointer">
            Retry
          </button>
        </div>
      )}

      {!hasOverview && isLoading && (
        <div role="status" className="rounded-md border border-app-border bg-app-surface p-8 text-center text-sm text-app-text-muted">
          Loading dashboard...
        </div>
      )}

      {hasOverview && (
        <>
          {/* 4 KPI Cards */}
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <article className="rounded-md border border-app-border bg-app-surface p-4 space-y-1">
              <div className="flex items-center justify-between text-xs text-app-text-muted">
                <span>Completed games</span>
                <Activity size={15} className="text-app-accent" aria-hidden="true" />
              </div>
              <p className="text-2xl font-bold tabular-nums text-app-text">
                {num.format(overview.today?.total_sessions ?? 0)}
              </p>
              <p className="text-[11px] text-app-text-muted">{activeCount} active modes today</p>
            </article>

            <article className="rounded-md border border-app-border bg-app-surface p-4 space-y-1">
              <div className="flex items-center justify-between text-xs text-app-text-muted">
                <span>Unique finishers</span>
                <Users size={15} className="text-app-accent" aria-hidden="true" />
              </div>
              <p className="text-2xl font-bold tabular-nums text-app-text">
                {num.format(overview.today?.total_players ?? 0)}
              </p>
              <p className="text-[11px] text-app-text-muted">Accounts + guest browsers</p>
            </article>

            <article className="rounded-md border border-app-border bg-app-surface p-4 space-y-1">
              <div className="flex items-center justify-between text-xs text-app-text-muted">
                <span>Win rate today</span>
                <Trophy size={15} className="text-app-accent" aria-hidden="true" />
              </div>
              <p className="text-2xl font-bold tabular-nums text-app-text">
                {num.format(overview.today?.win_rate_pct ?? 0)}%
              </p>
              <p className="text-[11px] text-app-text-muted">
                {num.format(overview.today?.total_winners ?? 0)} solved
              </p>
            </article>

            <button
              type="button"
              onClick={onOpenCosts}
              className="rounded-md border border-app-border bg-app-surface p-4 space-y-1 text-left transition-colors hover:border-app-accent/60 cursor-pointer"
            >
              <div className="flex items-center justify-between text-xs text-app-text-muted">
                <span>Countrydle AI cost</span>
                <DollarSign size={15} className="text-app-accent" aria-hidden="true" />
              </div>
              <p className="text-xl font-bold tabular-nums text-app-text sm:text-2xl">
                {costState === 'loading' ? '...' : costValue ?? 'N/A'}
              </p>
              <p className="text-[11px] text-app-text-muted">
                {cost ? `${cost.day} UTC` : 'View cost report'}
              </p>
            </button>
          </div>

          {/* Games Today Table with Category Tabs + Search */}
          <section className="rounded-md border border-app-border bg-app-surface overflow-hidden" aria-labelledby="admin-overview-games">
            <div className="border-b border-app-border p-4 space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 id="admin-overview-games" className="text-base font-semibold text-app-text">
                    Games Today
                  </h2>
                  <p className="text-xs text-app-text-muted">
                    Click any mode to inspect its completed sessions.
                  </p>
                </div>
                <div className="relative w-full sm:w-64">
                  <Search size={14} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-app-text-muted" aria-hidden="true" />
                  <input
                    type="search"
                    value={modeSearch}
                    onChange={(e) => setModeSearch(e.target.value)}
                    placeholder="Filter modes or targets..."
                    aria-label="Filter modes or targets"
                    className="w-full rounded-sm border border-app-border bg-app-canvas py-1.5 pl-9 pr-3 text-xs text-app-text placeholder:text-app-text-muted focus:border-app-accent focus:outline-none"
                  />
                </div>
              </div>

              <div className="flex flex-wrap gap-1.5" role="tablist" aria-label="Game categories">
                {CATEGORIES.map((cat) => {
                  const active = category === cat.id;
                  const countBadge =
                    cat.id === 'active'
                      ? activeCount
                      : cat.id === 'all'
                        ? allModes.length
                        : allModes.filter((m) => classifyModeCategory(m.mode_key) === cat.id).length;
                  return (
                    <button
                      key={cat.id}
                      type="button"
                      role="tab"
                      aria-selected={active}
                      onClick={() => setCategory(cat.id)}
                      className={`inline-flex items-center gap-1.5 rounded-sm border px-2.5 py-1 text-xs font-medium transition-colors cursor-pointer ${
                        active
                          ? 'border-app-accent bg-app-accent text-app-canvas'
                          : 'border-app-border bg-app-surface-muted text-app-text-secondary hover:text-app-text'
                      }`}
                    >
                      <span>{cat.label}</span>
                      <span className={`font-mono text-[10px] ${active ? 'opacity-85' : 'text-app-text-muted'}`}>
                        {countBadge}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>

            {filteredModes.length === 0 ? (
              <div className="p-8 text-center text-sm text-app-text-muted space-y-2">
                <p>
                  {category === 'active' && !modeSearch
                    ? 'No completed games yet today.'
                    : 'No modes match your filter.'}
                </p>
                {category === 'active' && !modeSearch && (
                  <button
                    type="button"
                    onClick={() => setCategory('all')}
                    className="text-xs font-medium text-app-accent underline cursor-pointer"
                  >
                    Show all {allModes.length} modes
                  </button>
                )}
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-app-border bg-app-surface-muted/60 text-left text-[11px] font-mono uppercase tracking-wider text-app-text-muted">
                      <th className="px-4 py-2.5">Mode</th>
                      <th className="px-4 py-2.5">Today&apos;s Target</th>
                      <th className="px-4 py-2.5 text-right">Completed</th>
                      <th className="px-4 py-2.5 text-right">Won</th>
                      <th className="px-4 py-2.5 text-right">Q / G</th>
                      <th className="px-3 py-2.5 w-10" aria-label="Action" />
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-app-border/60">
                    {filteredModes.map((mode) => (
                      <tr
                        key={mode.mode_key}
                        onClick={() => onOpenSessions(mode.mode_key)}
                        className="group cursor-pointer transition-colors hover:bg-app-surface-muted/70"
                      >
                        <td className="px-4 py-2.5 font-medium text-app-text">
                          {mode.mode_label}
                        </td>
                        <td className="px-4 py-2.5 text-app-text-secondary">
                          {mode.target_name}
                        </td>
                        <td className="px-4 py-2.5 text-right font-mono tabular-nums text-app-text">
                          {num.format(mode.sessions)}
                        </td>
                        <td className="px-4 py-2.5 text-right font-mono tabular-nums">
                          <span className="text-emerald-700 font-medium">{num.format(mode.winners)}</span>
                          <span className="ml-1 text-xs text-app-text-muted">({num.format(mode.win_rate_pct)}%)</span>
                        </td>
                        <td className="px-4 py-2.5 text-right font-mono tabular-nums text-xs text-app-text-secondary">
                          {num.format(mode.questions)} / {num.format(mode.guesses)}
                        </td>
                        <td className="px-3 py-2.5 text-right text-app-text-muted group-hover:text-app-accent">
                          <ChevronRight size={15} className="inline" aria-hidden="true" />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          {/* 14-Day History */}
          <section className="rounded-md border border-app-border bg-app-surface overflow-hidden" aria-labelledby="admin-overview-history">
            <div className="flex items-center gap-2 border-b border-app-border px-4 py-3">
              <Calendar size={15} className="text-app-accent" aria-hidden="true" />
              <h2 id="admin-overview-history" className="text-sm font-semibold text-app-text">
                Last 14 Days (Completed Games)
              </h2>
            </div>
            {!overview.history_14d?.length ? (
              <p className="p-6 text-center text-sm text-app-text-muted">No recent history.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[640px] text-xs sm:text-sm">
                  <thead>
                    <tr className="border-b border-app-border bg-app-surface-muted/60 text-right font-mono text-[11px] uppercase tracking-wider text-app-text-muted">
                      <th className="px-4 py-2.5 text-left">Date</th>
                      <th className="px-4 py-2.5">Finishers</th>
                      <th className="px-4 py-2.5">Winners</th>
                      <th className="px-4 py-2.5">Win Rate</th>
                      <th className="px-4 py-2.5">Avg Q (Won)</th>
                      <th className="px-4 py-2.5">Q / G</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-app-border/60 font-mono tabular-nums">
                    {overview.history_14d.map((day) => (
                      <tr key={day.date} className="hover:bg-app-surface-muted/40">
                        <th scope="row" className="px-4 py-2 text-left font-sans font-medium text-app-text">
                          {dateFmt.format(new Date(`${day.date}T00:00:00Z`))}
                        </th>
                        <td className="px-4 py-2 text-right text-app-text">{num.format(day.total_players)}</td>
                        <td className="px-4 py-2 text-right text-emerald-700 font-medium">{num.format(day.total_winners)}</td>
                        <td className="px-4 py-2 text-right text-app-text">{num.format(day.win_rate_pct)}%</td>
                        <td className="px-4 py-2 text-right text-app-text-secondary">
                          {day.avg_questions_won ? num.format(day.avg_questions_won) : '-'}
                        </td>
                        <td className="px-4 py-2 text-right text-app-text-secondary">
                          {num.format(day.total_questions)} / {num.format(day.total_guesses)}
                        </td>
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
