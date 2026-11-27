import { Trophy, ChevronDown, ChevronUp, LogIn } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useAuthStore } from '../../stores/authStore';
import type {
  DashboardLeaderboardEntry,
  DashboardLeaderboardPayload,
  DashboardLeaderboardPeriod,
} from '../../types';

interface CompactLeaderboardProps {
  period: DashboardLeaderboardPeriod;
  onPeriodChange: (period: DashboardLeaderboardPeriod) => void;
  leaderboard: DashboardLeaderboardPayload | null;
  isLoading: boolean;
  isExpanding: boolean;
  isExpanded: boolean;
  onToggleExpand: () => void;
  isUnavailable: boolean;
}

const PERIOD_TABS: { id: DashboardLeaderboardPeriod; label: string }[] = [
  { id: 'daily', label: 'Today' },
  { id: 'monthly', label: 'Monthly' },
  { id: 'all_time', label: 'All-Time' },
];

function rankBadgeClass(rank: number): string {
  if (rank === 1) return 'text-amber-300 font-bold';
  if (rank === 2) return 'text-zinc-200 font-bold';
  if (rank === 3) return 'text-amber-500 font-bold';
  return 'text-zinc-400';
}

function formatEntryPrimaryMetric(entry: DashboardLeaderboardEntry, period: DashboardLeaderboardPeriod): string {
  if (entry.points > 0) return `${entry.points.toLocaleString('en-US')} pts`;
  if (period === 'daily' && entry.score !== null && entry.score !== undefined) {
    return `${entry.score.toLocaleString('en-US')} pts`;
  }
  if (period === 'daily' && entry.guesses_used !== null && entry.guesses_used !== undefined) {
    return `${entry.guesses_used}g`;
  }
  return `${entry.points.toLocaleString('en-US')} pts`;
}

function formatEntrySubMetric(entry: DashboardLeaderboardEntry, period: DashboardLeaderboardPeriod): string | null {
  if (period === 'daily') {
    const parts: string[] = [];
    if (entry.questions_used !== null && entry.questions_used !== undefined) {
      parts.push(`${entry.questions_used}Q`);
    }
    if (entry.guesses_used !== null && entry.guesses_used !== undefined) {
      parts.push(`${entry.guesses_used}G`);
    }
    if (parts.length > 0) return parts.join(' · ');
    if (entry.elapsed_seconds !== null && entry.elapsed_seconds !== undefined) {
      const m = Math.floor(entry.elapsed_seconds / 60);
      const s = Math.round(entry.elapsed_seconds % 60);
      return `${m}:${String(s).padStart(2, '0')}`;
    }
    return null;
  }
  if (entry.games_played > 0) {
    return `${entry.wins}W / ${entry.games_played}`;
  }
  return null;
}

function LeaderboardRow({
  entry,
  period,
  isCurrentUser,
  mobileHidden,
}: {
  entry: DashboardLeaderboardEntry;
  period: DashboardLeaderboardPeriod;
  isCurrentUser: boolean;
  mobileHidden?: boolean;
}) {
  const sub = formatEntrySubMetric(entry, period);
  const isNamedProfile = Boolean(entry.username && !entry.username.toLowerCase().startsWith('guest'));

  return (
    <div
      className={`${mobileHidden ? 'hidden lg:grid' : 'grid'} grid-cols-[2.25rem_1fr_auto] items-center gap-2 rounded-xs px-2.5 py-2 text-xs transition-colors ${
        isCurrentUser
          ? 'bg-emerald-500/15 border border-emerald-400/35 text-emerald-100'
          : 'hover:bg-white/[0.04] border border-transparent text-sand-100'
      }`}
    >
      <span className={`font-mono text-xs tabular-nums ${rankBadgeClass(entry.rank)}`}>
        #{entry.rank}
      </span>

      <div className="min-w-0 flex items-center gap-1.5">
        {isNamedProfile ? (
          <Link
            to={`/profile/${encodeURIComponent(entry.username)}`}
            className={`truncate font-medium hover:underline ${
              isCurrentUser ? 'text-emerald-200 font-semibold' : 'text-sand-100 hover:text-emerald-300'
            }`}
          >
            {entry.username}
          </Link>
        ) : (
          <span className={`truncate font-medium ${isCurrentUser ? 'text-emerald-200 font-semibold' : 'text-zinc-300'}`}>
            {entry.username}
          </span>
        )}
        {isCurrentUser && (
          <span className="shrink-0 rounded-xs bg-emerald-400/20 border border-emerald-400/40 px-1.5 py-0.25 font-mono text-[9px] font-bold uppercase text-emerald-300">
            YOU
          </span>
        )}
      </div>

      <div className="text-right font-mono tabular-nums">
        <div className={`text-xs font-semibold ${isCurrentUser ? 'text-emerald-300' : 'text-sand-100'}`}>
          {formatEntryPrimaryMetric(entry, period)}
        </div>
        {sub && <div className="text-[10px] text-zinc-400">{sub}</div>}
      </div>
    </div>
  );
}

export default function CompactLeaderboard({
  period,
  onPeriodChange,
  leaderboard,
  isLoading,
  isExpanding,
  isExpanded,
  onToggleExpand,
  isUnavailable,
}: CompactLeaderboardProps) {
  const { user, isAuthenticated } = useAuthStore();
  const entries = leaderboard?.entries ?? [];
  const currentUserEntry = leaderboard?.current_user_entry ?? null;
  const totalRanked = leaderboard?.total_ranked ?? entries.length;

  const isEntryCurrentUser = (entry: DashboardLeaderboardEntry) => {
    if (entry.is_current_user) return true;
    if (user?.username && entry.username.toLowerCase() === user.username.toLowerCase()) return true;
    return false;
  };

  const currentUserInList = entries.some(isEntryCurrentUser);
  const showPinnedSelf = Boolean(currentUserEntry && !currentUserInList);
  const canExpand = totalRanked > 5 && (totalRanked > entries.length || isExpanded || entries.length > 5);

  return (
    <section
      aria-label="Leaderboard"
      className="rounded-sm border border-white/10 bg-obsidian-900/60 p-4 sm:p-5 space-y-3"
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/10 pb-2.5">
        <div className="flex items-center gap-2">
          <Trophy size={15} className="text-amber-400 shrink-0" aria-hidden="true" />
          <h3 className="font-mono text-xs font-semibold uppercase tracking-wider text-sand-100">
            Leaderboard
          </h3>
        </div>
        {totalRanked > 0 && (
          <span className="font-mono text-[11px] text-zinc-400 tabular-nums">
            {totalRanked.toLocaleString('en-US')} ranked
          </span>
        )}
      </div>

      {/* Period tabs */}
      <div
        role="tablist"
        aria-label="Leaderboard timeframe"
        className="grid grid-cols-3 gap-1 rounded-sm border border-white/10 bg-obsidian-950/70 p-1"
      >
        {PERIOD_TABS.map((tab) => {
          const active = period === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={active}
              onClick={() => onPeriodChange(tab.id)}
              className={`min-h-8 rounded-xs font-mono text-[11px] font-semibold transition-colors cursor-pointer ${
                active
                  ? 'bg-emerald-400/15 text-emerald-300 border border-emerald-400/30'
                  : 'text-zinc-400 hover:text-sand-100 border border-transparent'
              }`}
            >
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Rows */}
      {isLoading ? (
        <div className="space-y-1.5 py-1" role="status" aria-label="Loading leaderboard">
          {[0, 1, 2, 3, 4].map((idx) => (
            <div key={idx} className="h-9 rounded-xs bg-white/[0.04] animate-pulse" />
          ))}
        </div>
      ) : isUnavailable ? (
        <p className="py-5 text-center text-xs text-zinc-400">
          Rankings are temporarily unavailable. Your result is still saved.
        </p>
      ) : entries.length === 0 ? (
        <p className="py-5 text-center text-xs text-zinc-400">
          No ranked entries yet for this timeframe.
        </p>
      ) : (
        <div className="space-y-1">
          <div className={isExpanded ? 'max-h-80 overflow-y-auto pr-1 space-y-1' : 'space-y-1'}>
            {entries.map((entry, idx) => (
              <LeaderboardRow
                key={`${entry.rank}-${entry.username}-${idx}`}
                entry={entry}
                period={period}
                isCurrentUser={isEntryCurrentUser(entry)}
                mobileHidden={!isExpanded && idx >= 5}
              />
            ))}
          </div>

          {showPinnedSelf && currentUserEntry && (
            <div className="border-t border-dashed border-white/15 pt-1.5 mt-1.5">
              <LeaderboardRow
                entry={currentUserEntry}
                period={period}
                isCurrentUser
              />
            </div>
          )}

          {canExpand && (
            <button
              type="button"
              onClick={onToggleExpand}
              disabled={isExpanding}
              className="mt-2 flex min-h-9 w-full items-center justify-center gap-1.5 rounded-xs border border-white/10 bg-white/[0.03] px-3 py-1.5 font-mono text-[11px] font-semibold text-zinc-300 hover:bg-white/[0.08] hover:text-sand-100 transition-colors cursor-pointer disabled:opacity-50"
            >
              {isExpanding ? (
                <span>Loading top 25…</span>
              ) : isExpanded ? (
                <>
                  <ChevronUp size={14} aria-hidden="true" />
                  <span>Show fewer</span>
                </>
              ) : (
                <>
                  <ChevronDown size={14} aria-hidden="true" />
                  <span>Show top {Math.min(25, Math.max(totalRanked, 10))}</span>
                </>
              )}
            </button>
          )}
        </div>
      )}

      {/* Guest sign-in CTA */}
      {!isAuthenticated && (
        <div className="rounded-xs border border-emerald-400/20 bg-emerald-500/[0.06] px-3 py-2.5 flex flex-wrap items-center justify-between gap-2 text-xs">
          <span className="text-zinc-300">
            Sign in to claim your rank &amp; save streaks.
          </span>
          <div className="flex items-center gap-2 shrink-0">
            <Link
              to="/login"
              className="inline-flex items-center gap-1 font-mono text-[11px] font-semibold text-emerald-300 hover:text-emerald-200 underline"
            >
              <LogIn size={12} aria-hidden="true" />
              Log in
            </Link>
            <Link
              to="/register"
              className="rounded-xs bg-emerald-400/20 border border-emerald-400/35 px-2 py-0.5 font-mono text-[11px] font-semibold text-emerald-200 hover:bg-emerald-400/30 transition-colors"
            >
              Sign up
            </Link>
          </div>
        </div>
      )}
    </section>
  );
}
