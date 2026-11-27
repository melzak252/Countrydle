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
  return 'text-zinc-500';
}

function formatEntryPrimaryMetric(
  entry: DashboardLeaderboardEntry,
  period: DashboardLeaderboardPeriod,
): string {
  if (entry.points > 0) return `${entry.points.toLocaleString('en-US')} pts`;
  if (period === 'daily' && entry.score !== null && entry.score !== undefined) {
    return `${entry.score.toLocaleString('en-US')} pts`;
  }
  if (period === 'daily' && entry.guesses_used !== null && entry.guesses_used !== undefined) {
    return `${entry.guesses_used}g`;
  }
  return `${entry.points.toLocaleString('en-US')} pts`;
}

function formatEntrySubMetric(
  entry: DashboardLeaderboardEntry,
  period: DashboardLeaderboardPeriod,
): string | null {
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
}: {
  entry: DashboardLeaderboardEntry;
  period: DashboardLeaderboardPeriod;
  isCurrentUser: boolean;
}) {
  const sub = formatEntrySubMetric(entry, period);
  const isNamedProfile = Boolean(
    entry.username && !entry.username.toLowerCase().startsWith('guest'),
  );

  return (
    <div
      className={`grid grid-cols-[2.25rem_1fr_auto] items-center gap-3 rounded-lg px-3 py-2.5 text-xs transition-colors ${
        isCurrentUser
          ? 'bg-emerald-500/12 text-emerald-100 ring-1 ring-inset ring-emerald-400/30'
          : 'hover:bg-white/[0.03] text-sand-100'
      }`}
    >
      <span className={`font-mono text-xs tabular-nums ${rankBadgeClass(entry.rank)}`}>
        #{entry.rank}
      </span>

      <div className="min-w-0 flex items-center gap-2">
        {isNamedProfile ? (
          <Link
            to={`/profile/${encodeURIComponent(entry.username)}`}
            className={`truncate font-medium hover:underline ${
              isCurrentUser
                ? 'text-emerald-200 font-semibold'
                : 'text-sand-100 hover:text-emerald-300'
            }`}
          >
            {entry.username}
          </Link>
        ) : (
          <span
            className={`truncate font-medium ${
              isCurrentUser ? 'text-emerald-200 font-semibold' : 'text-zinc-300'
            }`}
          >
            {entry.username}
          </span>
        )}
        {isCurrentUser && (
          <span className="shrink-0 rounded-full bg-emerald-400/20 px-2 py-0.5 font-mono text-[9px] font-bold uppercase tracking-wider text-emerald-300">
            YOU
          </span>
        )}
      </div>

      <div className="text-right font-mono tabular-nums">
        <div
          className={`text-xs font-semibold ${
            isCurrentUser ? 'text-emerald-300' : 'text-sand-100'
          }`}
        >
          {formatEntryPrimaryMetric(entry, period)}
        </div>
        {sub && <div className="text-[10px] text-zinc-500">{sub}</div>}
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
    if (user?.username && entry.username.toLowerCase() === user.username.toLowerCase()) {
      return true;
    }
    return false;
  };

  const visibleEntries = isExpanded ? entries : entries.slice(0, 5);
  const currentUserVisible = visibleEntries.some(isEntryCurrentUser);
  const showPinnedSelf = Boolean(currentUserEntry && !currentUserVisible);
  const canExpand = totalRanked > 5 || entries.length > 5 || isExpanded;

  return (
    <section
      aria-label="Leaderboard"
      className="rounded-xl border border-white/[0.08] bg-white/[0.02] p-5 sm:p-6 space-y-4"
    >
      {/* Header + Segmented Pill Tabs */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Trophy size={15} className="text-amber-400 shrink-0" aria-hidden="true" />
          <h3 className="font-mono text-xs font-semibold uppercase tracking-wider text-sand-100">
            Leaderboard
          </h3>
        </div>

        <div
          role="tablist"
          aria-label="Leaderboard timeframe"
          className="inline-flex items-center rounded-full bg-white/[0.05] p-0.5"
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
                className={`rounded-full px-2.5 py-1 font-mono text-[11px] font-semibold transition-colors cursor-pointer ${
                  active
                    ? 'bg-emerald-400/20 text-emerald-300'
                    : 'text-zinc-400 hover:text-sand-100'
                }`}
              >
                {tab.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Rows */}
      {isLoading ? (
        <div className="space-y-2 py-1" role="status" aria-label="Loading leaderboard">
          {[0, 1, 2, 3, 4].map((idx) => (
            <div key={idx} className="h-10 rounded-lg bg-white/[0.04] animate-pulse" />
          ))}
        </div>
      ) : isUnavailable ? (
        <p className="py-6 text-center text-xs text-zinc-400">
          Rankings are temporarily unavailable. Your result is still saved.
        </p>
      ) : entries.length === 0 ? (
        <p className="py-6 text-center text-xs text-zinc-400">
          No ranked entries yet for this timeframe.
        </p>
      ) : (
        <div className="space-y-1">
          <div
            className={
              isExpanded ? 'max-h-80 overflow-y-auto pr-1 space-y-1' : 'space-y-1'
            }
          >
            {visibleEntries.map((entry, idx) => (
              <LeaderboardRow
                key={`${entry.rank}-${entry.username}-${idx}`}
                entry={entry}
                period={period}
                isCurrentUser={isEntryCurrentUser(entry)}
              />
            ))}
          </div>

          {showPinnedSelf && currentUserEntry && (
            <div className="border-t border-dashed border-white/15 pt-2 mt-2">
              <LeaderboardRow entry={currentUserEntry} period={period} isCurrentUser />
            </div>
          )}

          {canExpand && (
            <div className="pt-2">
              <button
                type="button"
                onClick={onToggleExpand}
                disabled={isExpanding}
                className="flex w-full items-center justify-center gap-1.5 rounded-lg py-2 font-mono text-[11px] font-medium text-zinc-400 hover:bg-white/[0.04] hover:text-sand-100 transition-colors cursor-pointer disabled:opacity-50"
              >
                {isExpanding ? (
                  <span>Loading more...</span>
                ) : isExpanded ? (
                  <>
                    <ChevronUp size={14} aria-hidden="true" />
                    <span>Show less</span>
                  </>
                ) : (
                  <>
                    <ChevronDown size={14} aria-hidden="true" />
                    <span>
                      Show more ({Math.min(25, Math.max(totalRanked, entries.length))})
                    </span>
                  </>
                )}
              </button>
            </div>
          )}
        </div>
      )}

      {/* Subtle guest sign-in prompt */}
      {!isAuthenticated && (
        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-white/[0.08] pt-3.5 text-xs">
          <span className="text-zinc-400">Sign in to claim your rank and streak.</span>
          <div className="flex items-center gap-3 shrink-0">
            <Link
              to="/login"
              className="inline-flex items-center gap-1 font-mono text-[11px] font-semibold text-emerald-300 hover:text-emerald-200 transition-colors"
            >
              <LogIn size={12} aria-hidden="true" />
              Log in
            </Link>
            <Link
              to="/register"
              className="rounded-full bg-emerald-400/15 px-2.5 py-1 font-mono text-[11px] font-semibold text-emerald-300 hover:bg-emerald-400/25 transition-colors"
            >
              Sign up
            </Link>
          </div>
        </div>
      )}
    </section>
  );
}
