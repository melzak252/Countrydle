import { BarChart3 } from 'lucide-react';
import type { DistributionBucket } from '../../types';
import type { ResultDashboardModeKind } from './types';

interface DistributionChartProps {
  modeKind: ResultDashboardModeKind;
  questions?: DistributionBucket[];
  guesses?: DistributionBucket[];
  score?: DistributionBucket[];
  avgQuestions?: number | null;
  avgGuesses?: number | null;
  avgScore?: number | null;
  playerQuestions?: number | null;
  playerGuesses?: number | null;
  playerScore?: number | null;
  maxScore?: number | null;
  playerWon?: boolean;
  isLoading: boolean;
  isUnavailable: boolean;
  completedToday?: number;
}

interface HorizontalDistributionProps {
  ariaLabel: string;
  buckets: DistributionBucket[];
  average?: number | null;
  playerFallbackLabel?: string | null;
  compact?: boolean;
}

function getAverageBucketLabel(buckets: DistributionBucket[], average?: number | null): string | null {
  if (average === null || average === undefined || !Number.isFinite(average)) return null;
  let closestLabel: string | null = null;
  let closestDiff = Number.POSITIVE_INFINITY;

  for (const bucket of buckets) {
    const parsed = Number(bucket.label);
    if (!Number.isFinite(parsed)) continue;
    const diff = Math.abs(parsed - average);
    if (diff < closestDiff) {
      closestDiff = diff;
      closestLabel = bucket.label;
    }
  }

  return closestDiff <= 0.55 ? closestLabel : null;
}

function HorizontalAxisHistogram({
  ariaLabel,
  buckets,
  average,
  playerFallbackLabel,
  compact = false,
}: HorizontalDistributionProps) {
  const maxPct = Math.max(...buckets.map((b) => b.pct), 1);
  const hasServerPlayerFlag = buckets.some((b) => b.is_player);
  const avgBucketLabel = getAverageBucketLabel(buckets, average);
  const isDense = buckets.length > 8;
  const barTrackHeight = compact ? 'h-20 sm:h-24' : 'h-28 sm:h-32';

  return (
    <div className="relative pt-2" role="list" aria-label={ariaLabel}>
      {/* Faint horizontal reference lines behind the vertical columns */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-[2.125rem] flex h-28 sm:h-32 flex-col justify-between"
      >
        <div className="w-full border-t border-dashed border-app-border/50" />
        <div className="w-full border-t border-dashed border-app-border/50" />
        <div className="w-full border-t border-dashed border-app-border/50" />
        <div className="w-full border-t border-transparent" />
      </div>

      {/* Columns arranged horizontally left-to-right along the X-axis */}
      <div
        className="relative z-10 grid items-end gap-1.5 sm:gap-2"
        style={{ gridTemplateColumns: `repeat(${buckets.length}, minmax(0, 1fr))` }}
      >
        {buckets.map((bucket) => {
          const isPlayer = hasServerPlayerFlag
            ? bucket.is_player
            : Boolean(playerFallbackLabel && bucket.label === playerFallbackLabel);
          const isFailBucket =
            bucket.label.toUpperCase() === 'X' || bucket.label.toLowerCase() === 'fail';
          const isAvgBucket = avgBucketLabel === bucket.label;
          const barHeightPct =
            bucket.pct > 0 ? Math.max(8, Math.round((bucket.pct / maxPct) * 100)) : 0;

          return (
            <div
              key={bucket.label}
              role="listitem"
              title={`${bucket.label}: ${Math.round(bucket.pct)}% (${bucket.count.toLocaleString('en-US')} players)`}
              className="group flex flex-col items-center min-w-0"
            >
              {/* Top callout: YOU pill or percentage */}
              <div className="mb-1.5 flex h-5 items-end justify-center">
                {isPlayer ? (
                  <span className="rounded-sm bg-app-accent px-1.5 py-0.5 font-mono text-[9px] font-bold leading-none tracking-wider text-app-canvas uppercase shadow-sm">
                    YOU
                  </span>
                ) : bucket.pct > 0 ? (
                  <span
                    className={`font-mono leading-none tabular-nums ${
                      isDense ? 'text-[9px] sm:text-[10px]' : 'text-[10px] sm:text-[11px]'
                    } text-app-text-muted group-hover:text-app-text transition-colors`}
                  >
                    {Math.round(bucket.pct)}%
                  </span>
                ) : null}
              </div>

              {/* Column track (vertical bar rising from horizontal baseline) */}
              <div className={`relative flex ${barTrackHeight} w-full items-end justify-center px-0.5 sm:px-1`}>
                {barHeightPct > 0 ? (
                  <div
                    className={`w-full max-w-[2.5rem] rounded-t-sm transition-all duration-500 ease-out ${
                      isPlayer
                        ? 'bg-app-accent group-hover:bg-app-accent-hover shadow-[0_2px_10px_rgb(var(--app-accent)/0.28)]'
                        : isFailBucket
                        ? 'bg-[#c85243]/45 group-hover:bg-[#c85243]/65'
                        : 'bg-app-text/25 group-hover:bg-app-text/40'
                    }`}
                    style={{ height: `${barHeightPct}%` }}
                  />
                ) : (
                  <div className="h-[2px] w-full max-w-[2.5rem] rounded-full bg-app-border/35" />
                )}
              </div>

              {/* Baseline + X-axis bucket label */}
              <div className="w-full border-t border-app-border/70 pt-2 flex flex-col items-center gap-1">
                <span
                  className={`truncate max-w-full font-mono tabular-nums ${
                    isDense ? 'text-[10px] sm:text-[11px]' : 'text-[11px] sm:text-xs'
                  } ${
                    isPlayer
                      ? 'font-bold text-app-accent'
                      : isFailBucket
                      ? 'font-semibold text-[#c85243]'
                      : 'text-app-text-secondary'
                  }`}
                >
                  {bucket.label}
                </span>
                <span
                  className={`h-1.5 w-1.5 rounded-full ${
                    isAvgBucket ? 'bg-[#9a6b2f]' : 'bg-transparent'
                  }`}
                  title={isAvgBucket ? "Closest to today's average" : undefined}
                  aria-hidden={!isAvgBucket}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function DistributionChart({
  modeKind,
  questions,
  guesses,
  score,
  avgQuestions,
  avgGuesses,
  avgScore,
  playerQuestions,
  playerGuesses,
  playerScore,
  maxScore,
  playerWon,
  isLoading,
  isUnavailable,
  completedToday,
}: DistributionChartProps) {
  const hasQuestions = Boolean(questions && questions.length > 0);
  const hasGuesses = Boolean(guesses && guesses.length > 0);
  const hasScore = Boolean(score && score.length > 0);
  const showDualCharts = modeKind === 'qa' && hasQuestions && hasGuesses;

  const playerQLabel =
    playerWon === false
      ? 'X'
      : playerQuestions !== null && playerQuestions !== undefined
      ? String(playerQuestions)
      : null;

  const playerGLabel =
    playerWon === false
      ? 'X'
      : playerGuesses !== null && playerGuesses !== undefined
      ? String(playerGuesses)
      : null;

  // Single-chart fallback configuration for non-QA modes
  let chartTitle = "Today's Distribution";
  let activeBuckets: DistributionBucket[] | null = null;
  let activeAverage: number | null | undefined = null;
  let activeAvgUnit = '';
  let activePlayerLabel: string | null = null;

  if (!showDualCharts) {
    if (hasGuesses) {
      chartTitle = modeKind === 'route' ? 'Hops Distribution' : 'Guesses Distribution';
      activeBuckets = guesses!;
      activeAverage = avgGuesses;
      activeAvgUnit = modeKind === 'route' ? 'hops' : 'G';
      activePlayerLabel = playerGLabel;
    } else if (hasScore) {
      chartTitle = 'Score Distribution';
      activeBuckets = score!;
      activeAverage = avgScore;
      activeAvgUnit = maxScore && maxScore <= 12 ? `/${maxScore}` : '';
      activePlayerLabel =
        playerScore !== null && playerScore !== undefined ? String(playerScore) : null;
    } else if (hasQuestions) {
      chartTitle = 'Questions Distribution';
      activeBuckets = questions!;
      activeAverage = avgQuestions;
      activeAvgUnit = 'Q';
      activePlayerLabel = playerQLabel;
    }
  }

  return (
    <section
      aria-label="Today's distribution"
      className="flex flex-1 flex-col justify-between rounded-md border border-app-border/70 border-t-2 border-t-app-accent bg-app-surface p-5 sm:p-6 gap-4 shadow-[1px_2px_8px_rgba(85,75,57,0.06)]"
    >
      {/* Header Row */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <BarChart3 size={15} className="text-app-accent shrink-0" aria-hidden="true" />
          <h3 className="font-serif text-base font-semibold tracking-tight text-app-text">
            {showDualCharts ? "Today's Distributions" : chartTitle}
          </h3>
          {!showDualCharts &&
            activeAverage !== null &&
            activeAverage !== undefined &&
            Number.isFinite(activeAverage) && (
              <span className="inline-flex items-center gap-1.5 rounded-sm border border-[#9a6b2f]/35 bg-[#9a6b2f]/10 px-2.5 py-0.5 font-mono text-[11px] font-medium text-[#9a6b2f] tabular-nums">
                <span className="h-1.5 w-1.5 rounded-full bg-[#9a6b2f]" aria-hidden="true" />
                avg {activeAverage.toFixed(1)}
                {activeAvgUnit ? ` ${activeAvgUnit}` : ''}
              </span>
            )}
        </div>

        {completedToday !== undefined && completedToday > 0 && (
          <span className="font-mono text-[11px] text-app-text-muted tabular-nums">
            {completedToday.toLocaleString('en-US')} {completedToday === 1 ? 'finish' : 'finishes'}
          </span>
        )}
      </div>

      {/* Body */}
      {isLoading ? (
        <div className="grid grid-cols-6 items-end gap-2 pt-4" role="status" aria-label="Loading distribution">
          {[32, 68, 92, 54, 36, 20].map((h, idx) => (
            <div key={idx} className="flex flex-col items-center gap-2">
              <div className="flex h-28 w-full items-end rounded-t-sm bg-app-surface-muted/60 px-1">
                <div className="w-full rounded-t-sm bg-app-border/30 animate-pulse" style={{ height: `${h}%` }} />
              </div>
              <div className="h-2.5 w-6 rounded-sm bg-app-border/30 animate-pulse" />
            </div>
          ))}
        </div>
      ) : isUnavailable || (!showDualCharts && !activeBuckets) ? (
        <p className="py-6 text-center text-xs text-app-text-muted">
          {isUnavailable
            ? 'Live community distributions are temporarily unavailable.'
            : 'Be one of the first players today. Distributions update as players finish.'}
        </p>
      ) : showDualCharts ? (
        <div className="flex flex-1 flex-col justify-between gap-5">
          {/* Chart 1: Questions Used */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between gap-2">
              <span className="font-mono text-[11px] font-semibold uppercase tracking-[0.12em] text-app-text-secondary">
                Questions Used
              </span>
              {avgQuestions !== null && avgQuestions !== undefined && Number.isFinite(avgQuestions) && (
                <span className="inline-flex items-center gap-1.5 rounded-sm border border-[#9a6b2f]/35 bg-[#9a6b2f]/10 px-2 py-0.5 font-mono text-[10px] font-medium text-[#9a6b2f] tabular-nums">
                  <span className="h-1.5 w-1.5 rounded-full bg-[#9a6b2f]" aria-hidden="true" />
                  avg {avgQuestions.toFixed(1)} Q
                </span>
              )}
            </div>
            <HorizontalAxisHistogram
              ariaLabel="Questions Used"
              buckets={questions!}
              average={avgQuestions}
              playerFallbackLabel={playerQLabel}
              compact
            />
          </div>

          {/* Chart 2: Guesses Used */}
          <div className="border-t border-app-border/45 pt-4 space-y-1.5">
            <div className="flex items-center justify-between gap-2">
              <span className="font-mono text-[11px] font-semibold uppercase tracking-[0.12em] text-app-text-secondary">
                Guesses Used
              </span>
              {avgGuesses !== null && avgGuesses !== undefined && Number.isFinite(avgGuesses) && (
                <span className="inline-flex items-center gap-1.5 rounded-sm border border-[#9a6b2f]/35 bg-[#9a6b2f]/10 px-2 py-0.5 font-mono text-[10px] font-medium text-[#9a6b2f] tabular-nums">
                  <span className="h-1.5 w-1.5 rounded-full bg-[#9a6b2f]" aria-hidden="true" />
                  avg {avgGuesses.toFixed(1)} G
                </span>
              )}
            </div>
            <HorizontalAxisHistogram
              ariaLabel="Guesses Used"
              buckets={guesses!}
              average={avgGuesses}
              playerFallbackLabel={playerGLabel}
              compact
            />
          </div>
        </div>
      ) : (
        <HorizontalAxisHistogram
          ariaLabel={chartTitle}
          buckets={activeBuckets!}
          average={activeAverage}
          playerFallbackLabel={activePlayerLabel}
        />
      )}
    </section>
  );
}
