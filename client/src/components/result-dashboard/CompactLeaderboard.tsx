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
];

function rankBadgeClass(rank: number): string {
  if (rank === 1) return 'text-[#c68f42] font-bold';
  if (rank === 2) return 'text-[#355c7d] font-bold';
  if (rank === 3) return 'text-[#c85243] font-bold';
  return 'text-app-text-muted';
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
      className={`grid grid-cols-[2.25rem_1fr_auto] items-center gap-3 rounded-sm border px-3 py-2.5 text-xs transition-colors ${
        isCurrentUser
          ? 'bg-app-accent/10 border-app-accent/30 text-app-text'
          : 'border-transparent hover:bg-app-surface-muted/70 text-app-text'
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
                ? 'text-app-accent font-semibold'
                : 'text-app-text hover:text-app-accent'
            }`}
          >
            {entry.username}
          </Link>
        ) : (
          <span
            className={`truncate font-medium ${
              isCurrentUser ? 'text-app-accent font-semibold' : 'text-app-text-secondary'
            }`}
          >
            {entry.username}
          </span>
        )}
        {isCurrentUser && (
          <span className="shrink-0 rounded-sm bg-app-accent px-1.5 py-0.5 font-mono text-[9px] font-bold uppercase tracking-wider text-app-canvas">
            YOU
          </span>
        )}
      </div>

      <div className="text-right font-mono tabular-nums">
        <div
          className={`text-xs font-semibold ${
            isCurrentUser ? 'text-app-accent' : 'text-app-text'
          }`}
        >
          {formatEntryPrimaryMetric(entry, period)}
        </div>
        {sub && <div className="text-[10px] text-app-text-muted">{sub}</div>}
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
      className="flex flex-1 flex-col rounded-md border border-app-border/70 border-t-2 border-t-app-accent bg-app-surface p-5 sm:p-6 space-y-4 shadow-[1px_2px_8px_rgba(85,75,57,0.06)]"
    >
      {/* Header + Segmented Pill Tabs */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Trophy size={15} className="text-[#c68f42] shrink-0" aria-hidden="true" />
          <h3 className="font-serif text-base font-semibold tracking-tight text-app-text">
            Leaderboard
          </h3>
        </div>

        <div
          role="tablist"
          aria-label="Leaderboard timeframe"
          className="inline-flex items-center rounded-sm border border-app-border/50 bg-app-surface-muted p-0.5"
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
                className={`rounded-sm px-2.5 py-1 font-mono text-[11px] font-semibold transition-colors cursor-pointer ${
                  active
                    ? 'bg-app-surface text-app-accent shadow-sm'
                    : 'text-app-text-secondary hover:text-app-text'
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
            <div key={idx} className="h-10 rounded-sm bg-app-surface-muted/80 animate-pulse" />
          ))}
        </div>
      ) : isUnavailable ? (
        <p className="py-6 text-center text-xs text-app-text-muted">
          Rankings are temporarily unavailable. Your result is still saved.
        </p>
      ) : entries.length === 0 ? (
        <p className="py-6 text-center text-xs text-app-text-muted">
          No ranked entries yet for this timeframe.
        </p>
      ) : (
        <div className="space-y-1">
          <div
            className={
              isExpanded ? 'max-h-80 overflow-y-auto pr-1 space-y-1 custom-scrollbar' : 'space-y-1'
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
            <div className="border-t border-dashed border-app-border/60 pt-2 mt-2">
              <LeaderboardRow entry={currentUserEntry} period={period} isCurrentUser />
            </div>
          )}

          {canExpand && (
            <div className="pt-2">
              <button
                type="button"
                onClick={onToggleExpand}
                disabled={isExpanding}
                className="flex w-full items-center justify-center gap-1.5 rounded-sm border border-app-border/50 bg-app-surface-muted/50 py-2 font-mono text-[11px] font-medium text-app-text-secondary hover:border-app-accent/60 hover:bg-app-surface-muted hover:text-app-text transition-colors cursor-pointer disabled:opacity-50"
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
        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-app-border/50 pt-3.5 text-xs">
          <span className="text-app-text-secondary">Sign in to claim your rank and streak.</span>
          <div className="flex items-center gap-3 shrink-0">
            <Link
              to="/login"
              className="inline-flex items-center gap-1 font-mono text-[11px] font-semibold text-app-accent hover:text-app-accent-hover transition-colors"
            >
              <LogIn size={12} aria-hidden="true" />
              Log in
            </Link>
            <Link
              to="/register"
              className="rounded-sm border border-app-accent/35 bg-app-accent/10 px-2.5 py-1 font-mono text-[11px] font-semibold text-app-accent hover:bg-app-accent/20 transition-colors"
            >
              Sign up
            </Link>
          </div>
        </div>
      )}
    </section>
  );
}
