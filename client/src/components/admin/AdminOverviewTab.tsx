import React from 'react';
import { 
  Users, 
  HelpCircle, 
  Target, 
  Trophy, 
  Globe, 
  Calendar,
} from 'lucide-react';

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
}
export const AdminOverviewTab: React.FC<AdminOverviewTabProps> = ({ overview, isLoading }) => {
  if (isLoading && !overview) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-emerald-400 border-t-transparent" />
      </div>
    );
  }

  const getDifficultyBadge = (winRate: number, players: number) => {
    if (players === 0) return { label: 'No attempts', color: 'text-zinc-400 bg-white/5 border-white/10' };
    if (winRate >= 70) return { label: 'High Solve Rate', color: 'text-emerald-300 bg-emerald-400/10 border-emerald-400/30' };
    if (winRate >= 40) return { label: 'Moderate Difficulty', color: 'text-amber-300 bg-amber-400/10 border-amber-400/30' };
    return { label: 'Challenging Target', color: 'text-rose-300 bg-rose-400/10 border-rose-400/30' };
  };

  return (
    <div className="space-y-8 animate-message">
      {/* Key Metric Hero Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-6 bg-obsidian-900 border border-white/10 rounded-sm space-y-2">
          <div className="flex items-center justify-between text-sand-100/65 text-xs font-semibold uppercase tracking-wider">
            <span>Active Players Today</span>
            <Users size={18} className="text-emerald-300" />
          </div>
          <div className="text-3xl md:text-4xl font-semibold text-sand-100 font-mono">
            {overview?.today?.total_players ?? 0}
          </div>
          <p className="text-xs text-sand-100/55">Unique accounts and guest browsers across daily challenges</p>
        </div>

        <div className="p-6 bg-obsidian-900 border border-white/10 rounded-sm space-y-2">
          <div className="flex items-center justify-between text-sand-100/65 text-xs font-semibold uppercase tracking-wider">
            <span>Questions Today</span>
            <HelpCircle size={18} className="text-sand-100/80" />
          </div>
          <div className="text-3xl md:text-4xl font-semibold text-sand-100/80 font-mono">
            {overview?.today?.total_questions ?? 0}
          </div>
          <p className="text-xs text-sand-100/55">Deduction queries evaluated</p>
        </div>

        <div className="p-6 bg-obsidian-900 border border-white/10 rounded-sm space-y-2">
          <div className="flex items-center justify-between text-sand-100/65 text-xs font-semibold uppercase tracking-wider">
            <span>Guesses Submitted</span>
            <Target size={18} className="text-sand-100/80" />
          </div>
          <div className="text-3xl md:text-4xl font-semibold text-sand-100/80 font-mono">
            {overview?.today?.total_guesses ?? 0}
          </div>
          <p className="text-xs text-sand-100/55">Target attempts submitted</p>
        </div>

        <div className="p-6 bg-obsidian-900 border border-white/10 rounded-sm space-y-2">
          <div className="flex items-center justify-between text-sand-100/65 text-xs font-semibold uppercase tracking-wider">
            <span>Overall Win Rate</span>
            <Trophy size={18} className="text-emerald-300" />
          </div>
          <div className="text-3xl md:text-4xl font-semibold text-emerald-300 font-mono">
            {overview?.today?.win_rate_pct ?? 0}%
          </div>
          <p className="text-xs text-sand-100/55">
            Total wins: <span className="text-sand-100 font-semibold">{overview?.today?.total_winners ?? 0}</span>
          </p>
        </div>
      </div>

      {/* Today's Mode Breakdown & Gameplay Progression */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold text-sand-100 flex items-center gap-2">
            <Globe size={18} className="text-emerald-300" />
            <span>Today's Mode Breakdown & Scheduled Targets</span>
          </h2>
          <span className="text-xs text-sand-100/55">Live field solve metrics</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {(overview?.modes_today || []).map((m: AdminModeStats) => {
            const diff = getDifficultyBadge(m.win_rate_pct, m.players);
            return (
              <div
                key={m.mode_key}
                className="bg-obsidian-900 border border-white/10 rounded-sm p-5 space-y-4 flex flex-col justify-between hover:border-white/20 transition-colors"
              >
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-sand-100/65 uppercase tracking-wider">
                      {m.mode_label}
                    </span>
                    <span className={`text-[10px] font-semibold px-2 py-0.5 rounded border ${diff.color}`}>
                      {diff.label}
                    </span>
                  </div>
                  <div className="text-xl font-semibold text-sand-100 truncate" title={m.target_name}>
                    {m.target_name}
                  </div>
                </div>

                <div className="space-y-2 pt-2 border-t border-white/10 text-xs">
                  <div className="flex justify-between text-sand-100/65">
                    <span>Players active:</span>
                    <span className="font-semibold text-sand-100 font-mono">{m.players}</span>
                  </div>
                  <div className="flex justify-between text-sand-100/65">
                    <span>Winners / Solved:</span>
                    <span className="font-semibold text-emerald-300 font-mono">
                      {m.winners} ({m.win_rate_pct}%)
                    </span>
                  </div>
                  {m.avg_questions_won !== undefined && m.avg_questions_won > 0 && (
                    <div className="flex justify-between text-sand-100/65">
                      <span>Avg Qs to win:</span>
                      <span className="font-semibold text-sand-100 font-mono">{m.avg_questions_won} qs</span>
                    </div>
                  )}
                  {m.avg_guesses_won !== undefined && m.avg_guesses_won > 0 && (
                    <div className="flex justify-between text-sand-100/65">
                      <span>Avg guesses to win:</span>
                      <span className="font-semibold text-sand-100 font-mono">{m.avg_guesses_won} tries</span>
                    </div>
                  )}
                  <div className="flex justify-between text-sand-100/65">
                    <span>Questions asked:</span>
                    <span className="font-semibold text-sand-100/80 font-mono">{m.questions}</span>
                  </div>
                  <div className="flex justify-between text-sand-100/65">
                    <span>Guesses made:</span>
                    <span className="font-semibold text-sand-100/80 font-mono">{m.guesses}</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* 14-Day Historical Performance Table */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold text-sand-100 flex items-center gap-2">
            <Calendar size={18} className="text-sand-100/80" />
            <span>Community Solve History (Last 14 Days)</span>
          </h2>
          <span className="text-xs text-sand-100/55">Player volume & success trends</span>
        </div>

        <div className="overflow-x-auto border border-white/10 rounded-sm">
          <table className="w-full text-left text-xs">
            <thead className="bg-obsidian-850 border-b border-white/10 text-sand-100/65 uppercase tracking-wider font-mono text-[10px]">
              <tr>
                <th className="py-3 px-4">Date</th>
                <th className="py-3 px-4">Unique Players</th>
                <th className="py-3 px-4">Total Winners</th>
                <th className="py-3 px-4">Win Rate</th>
                <th className="py-3 px-4">Avg Questions (Won)</th>
                <th className="py-3 px-4">Total Questions</th>
                <th className="py-3 px-4">Total Guesses</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5 font-mono">
              {(overview?.history_14d || []).map((day: AdminHistoryDay) => (
                <tr key={day.date} className="hover:bg-white/5 transition-colors">
                  <td className="py-3 px-4 font-semibold text-sand-100">{day.date}</td>
                  <td className="py-3 px-4 text-sand-100/80">{day.total_players}</td>
                  <td className="py-3 px-4 text-emerald-300 font-semibold">{day.total_winners}</td>
                  <td className="py-3 px-4">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-semibold border ${
                      day.win_rate_pct >= 60 ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300' :
                      day.win_rate_pct >= 40 ? 'border-amber-500/30 bg-amber-500/10 text-amber-300' :
                      'border-white/10 bg-white/5 text-zinc-400'
                    }`}>
                      {day.win_rate_pct}%
                    </span>
                  </td>
                  <td className="py-3 px-4 text-sand-100/65">{day.avg_questions_won ? `${day.avg_questions_won} qs` : '—'}</td>
                  <td className="py-3 px-4 text-sand-100/65">{day.total_questions}</td>
                  <td className="py-3 px-4 text-sand-100/65">{day.total_guesses}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default AdminOverviewTab;
