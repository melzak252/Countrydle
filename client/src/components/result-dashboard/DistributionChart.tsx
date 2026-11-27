import { useState } from 'react';
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

function HorizontalBars({
  ariaLabel,
  buckets,
  average,
  playerFallbackLabel,
}: HorizontalDistributionProps) {
  const maxPct = Math.max(...buckets.map((b) => b.pct), 1);
  const hasServerPlayerFlag = buckets.some((b) => b.is_player);
  const avgBucketLabel = getAverageBucketLabel(buckets, average);

  return (
    <div className="space-y-2.5" role="list" aria-label={ariaLabel}>
      {buckets.map((bucket) => {
        const isPlayer = hasServerPlayerFlag
          ? bucket.is_player
          : Boolean(playerFallbackLabel && bucket.label === playerFallbackLabel);
        const isFailBucket =
          bucket.label.toUpperCase() === 'X' || bucket.label.toLowerCase() === 'fail';
        const isAvgBucket = avgBucketLabel === bucket.label;
        const barWidth =
          bucket.pct > 0 ? Math.max(4, Math.round((bucket.pct / maxPct) * 100)) : 0;

        return (
          <div
            key={bucket.label}
            role="listitem"
            className="grid grid-cols-[2.75rem_1fr_4.75rem] items-center gap-3 text-xs"
          >
            {/* Left bucket label */}
            <div className="flex items-center justify-end gap-1.5 min-w-0">
              {isAvgBucket && (
                <span
                  className="h-1.5 w-1.5 shrink-0 rounded-full bg-amber-400/90"
                  title="Closest to today's average"
                  aria-label="Average"
                />
              )}
              <span
                className={`truncate font-mono text-xs tabular-nums ${
                  isPlayer
                    ? 'font-semibold text-emerald-300'
                    : isFailBucket
                    ? 'text-rose-400/80'
                    : 'text-zinc-400'
                }`}
                title={bucket.label}
              >
                {bucket.label}
              </span>
            </div>

            {/* Horizontal bar track */}
            <div className="relative h-7 overflow-hidden rounded-md bg-white/[0.04]">
              {barWidth > 0 && (
                <div
                  className={`h-full rounded-md transition-all duration-500 ease-out ${
                    isPlayer
                      ? 'bg-gradient-to-r from-emerald-500/85 to-emerald-400'
                      : isFailBucket
                      ? 'bg-rose-500/30'
                      : 'bg-white/[0.14]'
                  }`}
                  style={{ width: `${barWidth}%` }}
                />
              )}
              {isPlayer && (
                <div className="pointer-events-none absolute inset-y-0 right-2 flex items-center">
                  <span className="rounded-full bg-obsidian-950/90 border border-emerald-400/45 px-2 py-0.5 font-mono text-[9px] font-bold tracking-wider text-emerald-300 uppercase">
                    YOU
                  </span>
                </div>
              )}
            </div>

            {/* Right percentage + count */}
            <div className="flex items-baseline justify-end gap-1.5 font-mono tabular-nums">
              <span
                className={`text-xs ${
                  isPlayer ? 'font-semibold text-emerald-300' : 'text-zinc-200'
                }`}
              >
                {Math.round(bucket.pct)}%
              </span>
              <span className="text-[11px] text-zinc-500">
                ({bucket.count.toLocaleString('en-US')})
              </span>
            </div>
          </div>
        );
      })}
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
  playerWon,
  isLoading,
  isUnavailable,
  completedToday,
}: DistributionChartProps) {
  const [activeMetric, setActiveMetric] = useState<'questions' | 'guesses'>('questions');

  const hasQuestions = Boolean(questions && questions.length > 0);
  const hasGuesses = Boolean(guesses && guesses.length > 0);
  const hasScore = Boolean(score && score.length > 0);
  const showDualToggle = modeKind === 'qa' && hasQuestions && hasGuesses;

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

  // Determine the single active chart configuration
  let chartTitle = "Today's Distribution";
  let activeBuckets: DistributionBucket[] | null = null;
  let activeAverage: number | null | undefined = null;
  let activeAvgUnit = '';
  let activePlayerLabel: string | null = null;

  if (showDualToggle) {
    if (activeMetric === 'questions') {
      chartTitle = 'Questions Used';
      activeBuckets = questions!;
      activeAverage = avgQuestions;
      activeAvgUnit = 'Q';
      activePlayerLabel = playerQLabel;
    } else {
      chartTitle = 'Guesses Used';
      activeBuckets = guesses!;
      activeAverage = avgGuesses;
      activeAvgUnit = 'G';
      activePlayerLabel = playerGLabel;
    }
  } else if (hasGuesses) {
    chartTitle = modeKind === 'route' ? 'Hops Distribution' : 'Guesses Distribution';
    activeBuckets = guesses!;
    activeAverage = avgGuesses;
    activeAvgUnit = modeKind === 'route' ? 'hops' : 'G';
    activePlayerLabel = playerGLabel;
  } else if (hasScore) {
    chartTitle = 'Score Distribution';
    activeBuckets = score!;
    activeAverage = avgScore;
    activeAvgUnit = '';
    activePlayerLabel = null;
  } else if (hasQuestions) {
    chartTitle = 'Questions Distribution';
    activeBuckets = questions!;
    activeAverage = avgQuestions;
    activeAvgUnit = 'Q';
    activePlayerLabel = playerQLabel;
  }

  return (
    <section
      aria-label="Today's distribution"
      className="rounded-xl border border-white/[0.08] bg-white/[0.02] p-5 sm:p-6 space-y-5"
    >
      {/* Header Row */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <BarChart3 size={15} className="text-emerald-400 shrink-0" aria-hidden="true" />
          <h3 className="font-mono text-xs font-semibold uppercase tracking-wider text-sand-100">
            {showDualToggle ? 'Distribution' : chartTitle}
          </h3>
          {activeAverage !== null && activeAverage !== undefined && Number.isFinite(activeAverage) && (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-white/[0.05] px-2.5 py-0.5 font-mono text-[11px] text-zinc-300 tabular-nums">
              <span className="h-1.5 w-1.5 rounded-full bg-amber-400" aria-hidden="true" />
              avg {activeAverage.toFixed(1)}
              {activeAvgUnit ? ` ${activeAvgUnit}` : ''}
            </span>
          )}
        </div>

        <div className="flex items-center gap-3">
          {showDualToggle ? (
            <div
              role="tablist"
              aria-label="Distribution metric"
              className="inline-flex items-center rounded-full bg-white/[0.05] p-0.5"
            >
              <button
                type="button"
                role="tab"
                aria-selected={activeMetric === 'questions'}
                onClick={() => setActiveMetric('questions')}
                className={`rounded-full px-3 py-1 font-mono text-[11px] font-semibold transition-colors cursor-pointer ${
                  activeMetric === 'questions'
                    ? 'bg-emerald-400/20 text-emerald-300'
                    : 'text-zinc-400 hover:text-sand-100'
                }`}
              >
                Questions
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={activeMetric === 'guesses'}
                onClick={() => setActiveMetric('guesses')}
                className={`rounded-full px-3 py-1 font-mono text-[11px] font-semibold transition-colors cursor-pointer ${
                  activeMetric === 'guesses'
                    ? 'bg-emerald-400/20 text-emerald-300'
                    : 'text-zinc-400 hover:text-sand-100'
                }`}
              >
                Guesses
              </button>
            </div>
          ) : (
            completedToday !== undefined &&
            completedToday > 0 && (
              <span className="font-mono text-[11px] text-zinc-400 tabular-nums">
                {completedToday.toLocaleString('en-US')} {completedToday === 1 ? 'finish' : 'finishes'}
              </span>
            )
          )}
        </div>
      </div>

      {/* Body */}
      {isLoading ? (
        <div className="space-y-2.5 py-1" role="status" aria-label="Loading distribution">
          {[68, 92, 54, 36, 22].map((w, idx) => (
            <div key={idx} className="grid grid-cols-[2.75rem_1fr_4.75rem] items-center gap-3">
              <div className="h-3 rounded bg-white/10 animate-pulse" />
              <div className="h-7 rounded-md bg-white/[0.04] overflow-hidden">
                <div className="h-full rounded-md bg-white/10 animate-pulse" style={{ width: `${w}%` }} />
              </div>
              <div className="h-3 rounded bg-white/10 animate-pulse" />
            </div>
          ))}
        </div>
      ) : isUnavailable || !activeBuckets ? (
        <p className="py-6 text-center text-xs text-zinc-400">
          {isUnavailable
            ? 'Live community distributions are temporarily unavailable.'
            : 'Be one of the first players today. Distributions update as players finish.'}
        </p>
      ) : (
        <HorizontalBars
          ariaLabel={chartTitle}
          buckets={activeBuckets}
          average={activeAverage}
          playerFallbackLabel={activePlayerLabel}
        />
      )}
    </section>
  );
}
