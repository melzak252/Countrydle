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

interface SingleChartProps {
  title: string;
  buckets: DistributionBucket[];
  average?: number | null;
  averageUnit?: string;
  playerFallbackLabel?: string | null;
}

function SingleBarDistribution({
  title,
  buckets,
  average,
  averageUnit,
  playerFallbackLabel,
}: SingleChartProps) {
  const maxPct = Math.max(...buckets.map((b) => b.pct), 1);
  const hasServerPlayerFlag = buckets.some((b) => b.is_player);

  return (
    <div className="space-y-2.5">
      <div className="flex items-center justify-between gap-2">
        <h4 className="font-mono text-[11px] font-semibold uppercase tracking-wider text-zinc-400">
          {title}
        </h4>
        {average !== null && average !== undefined && Number.isFinite(average) && (
          <span className="inline-flex items-center gap-1 rounded-xs border border-white/10 bg-white/[0.03] px-2 py-0.5 font-mono text-[11px] text-zinc-300 tabular-nums">
            <span className="h-1.5 w-1.5 rounded-full bg-amber-400" aria-hidden="true" />
            avg {average.toFixed(1)}{averageUnit ? ` ${averageUnit}` : ''}
          </span>
        )}
      </div>

      <div className="space-y-1.5" role="list" aria-label={title}>
        {buckets.map((bucket) => {
          const isPlayer = hasServerPlayerFlag
            ? bucket.is_player
            : Boolean(playerFallbackLabel && bucket.label === playerFallbackLabel);
          const barWidth = bucket.pct > 0 ? Math.max(4, Math.round((bucket.pct / maxPct) * 100)) : 0;
          const isFailBucket = bucket.label.toUpperCase() === 'X' || bucket.label.toLowerCase() === 'fail';

          return (
            <div
              key={bucket.label}
              role="listitem"
              className="grid grid-cols-[2.75rem_1fr_3rem] items-center gap-2 text-xs"
            >
              <span
                className={`truncate text-right font-mono text-[11px] tabular-nums ${
                  isPlayer
                    ? 'font-bold text-emerald-300'
                    : isFailBucket
                    ? 'text-rose-400/80'
                    : 'text-zinc-400'
                }`}
                title={bucket.label}
              >
                {bucket.label}
              </span>

              <div className="relative h-6 overflow-hidden rounded-xs bg-white/[0.04] border border-white/[0.06]">
                {barWidth > 0 && (
                  <div
                    className={`h-full rounded-r-xs transition-all duration-500 ease-out ${
                      isPlayer
                        ? 'bg-gradient-to-r from-emerald-500/85 to-emerald-400'
                        : isFailBucket
                        ? 'bg-rose-500/35'
                        : 'bg-zinc-600/55'
                    }`}
                    style={{ width: `${barWidth}%` }}
                  />
                )}
                <div className="pointer-events-none absolute inset-0 flex items-center justify-between px-2">
                  <span className="font-mono text-[10px] text-sand-100/85 tabular-nums">
                    {bucket.count > 0 ? bucket.count.toLocaleString('en-US') : ''}
                  </span>
                  {isPlayer && (
                    <span className="rounded-xs bg-obsidian-950/90 border border-emerald-400/50 px-1.5 py-0.25 font-mono text-[9px] font-bold tracking-wider text-emerald-300 uppercase">
                      YOU
                    </span>
                  )}
                </div>
              </div>

              <span
                className={`text-right font-mono text-[11px] tabular-nums ${
                  isPlayer ? 'font-bold text-emerald-300' : 'text-zinc-400'
                }`}
              >
                {Math.round(bucket.pct)}%
              </span>
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
  playerWon,
  isLoading,
  isUnavailable,
  completedToday,
}: DistributionChartProps) {
  const [mobileTab, setMobileTab] = useState<'questions' | 'guesses'>('questions');

  const hasQuestions = Boolean(questions && questions.length > 0);
  const hasGuesses = Boolean(guesses && guesses.length > 0);
  const hasScore = Boolean(score && score.length > 0);
  const showDualQA = modeKind === 'qa' && hasQuestions && hasGuesses;

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

  return (
    <section
      aria-label="Today's distribution"
      className="rounded-sm border border-white/10 bg-obsidian-900/60 p-4 sm:p-5 space-y-3"
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/10 pb-2.5">
        <div className="flex items-center gap-2">
          <BarChart3 size={15} className="text-emerald-400 shrink-0" aria-hidden="true" />
          <h3 className="font-mono text-xs font-semibold uppercase tracking-wider text-sand-100">
            Today&apos;s Distribution
          </h3>
        </div>
        {completedToday !== undefined && completedToday > 0 && (
          <span className="font-mono text-[11px] text-zinc-400 tabular-nums">
            {completedToday.toLocaleString('en-US')} {completedToday === 1 ? 'finish' : 'finishes'}
          </span>
        )}
      </div>

      {isLoading ? (
        <div className="space-y-2 py-2" role="status" aria-label="Loading distribution">
          {[68, 92, 54, 36, 22].map((w, idx) => (
            <div key={idx} className="grid grid-cols-[2.75rem_1fr_3rem] items-center gap-2">
              <div className="h-3 rounded-xs bg-white/10 animate-pulse" />
              <div className="h-6 rounded-xs bg-white/[0.04] overflow-hidden">
                <div className="h-full bg-white/10 animate-pulse" style={{ width: `${w}%` }} />
              </div>
              <div className="h-3 rounded-xs bg-white/10 animate-pulse" />
            </div>
          ))}
        </div>
      ) : isUnavailable || (!hasQuestions && !hasGuesses && !hasScore) ? (
        <p className="py-4 text-center text-xs text-zinc-400">
          {isUnavailable
            ? 'Live community distributions are temporarily unavailable.'
            : 'Be one of the first players today — distributions update as players finish.'}
        </p>
      ) : showDualQA ? (
        <>
          {/* Mobile tab toggle */}
          <div className="grid grid-cols-2 gap-1 rounded-sm border border-white/10 bg-obsidian-950/70 p-1 md:hidden">
            <button
              type="button"
              onClick={() => setMobileTab('questions')}
              className={`min-h-9 rounded-xs font-mono text-xs font-semibold transition-colors cursor-pointer ${
                mobileTab === 'questions'
                  ? 'bg-emerald-400/15 text-emerald-300 border border-emerald-400/30'
                  : 'text-zinc-400 hover:text-sand-100'
              }`}
            >
              Questions
            </button>
            <button
              type="button"
              onClick={() => setMobileTab('guesses')}
              className={`min-h-9 rounded-xs font-mono text-xs font-semibold transition-colors cursor-pointer ${
                mobileTab === 'guesses'
                  ? 'bg-emerald-400/15 text-emerald-300 border border-emerald-400/30'
                  : 'text-zinc-400 hover:text-sand-100'
              }`}
            >
              Guesses
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            <div className={mobileTab === 'questions' ? 'block' : 'hidden md:block'}>
              <SingleBarDistribution
                title="Questions Used"
                buckets={questions!}
                average={avgQuestions}
                averageUnit="Q"
                playerFallbackLabel={playerQLabel}
              />
            </div>
            <div className={mobileTab === 'guesses' ? 'block' : 'hidden md:block'}>
              <SingleBarDistribution
                title="Guesses Used"
                buckets={guesses!}
                average={avgGuesses}
                averageUnit="G"
                playerFallbackLabel={playerGLabel}
              />
            </div>
          </div>
        </>
      ) : hasGuesses ? (
        <SingleBarDistribution
          title={modeKind === 'route' ? 'Hops Distribution' : 'Guesses Distribution'}
          buckets={guesses!}
          average={avgGuesses}
          averageUnit={modeKind === 'route' ? 'hops' : 'guesses'}
          playerFallbackLabel={playerGLabel}
        />
      ) : hasScore ? (
        <SingleBarDistribution
          title="Score Distribution"
          buckets={score!}
          average={avgScore}
          playerFallbackLabel={null}
        />
      ) : (
        <SingleBarDistribution
          title="Questions Distribution"
          buckets={questions!}
          average={avgQuestions}
          averageUnit="Q"
          playerFallbackLabel={playerQLabel}
        />
      )}
    </section>
  );
}
