import { useEffect, useId, useMemo, useState } from 'react';
import { Trophy, X, ChevronDown, Users, Sparkles } from 'lucide-react';
import { useDailyClock } from '../../hooks/useDailyClock';
import { statsService } from '../../services/api';
import type {
  DashboardLeaderboardPayload,
  DashboardLeaderboardPeriod,
  DashboardSummary,
} from '../../types';
import DistributionChart from './DistributionChart';
import CompactLeaderboard from './CompactLeaderboard';
import ShareActionBar from './ShareActionBar';
import NextModeShelf from './NextModeShelf';
import type { GameResultDashboardProps, ResultDashboardMetric } from './types';

function formatDuration(seconds: number): string {
  const total = Math.max(0, Math.round(seconds));
  const mins = Math.floor(total / 60);
  const secs = total % 60;
  return `${mins}:${String(secs).padStart(2, '0')}`;
}

function buildDefaultShareText(props: GameResultDashboardProps, displayDate: string): string {
  const fullUrl = `https://countrydle.online${props.gamePath === '/game' ? '' : props.gamePath}`;
  let emoji = '🌍';
  if (props.gamePath.includes('us-states')) emoji = '🇺🇸';
  else if (props.gamePath.includes('powiaty')) emoji = '📍';
  else if (props.gamePath.includes('wojewodztwa')) emoji = '🗺️';
  else if (props.gamePath.includes('europe')) emoji = '🧭';
  else if (props.gamePath.includes('asia')) emoji = '🌏';
  else if (props.gamePath.includes('africa')) emoji = '🌍';
  else if (props.gamePath.includes('americas')) emoji = '🌎';
  else if (props.gamePath.includes('flag')) emoji = '🚩';

  const lines: string[] = [`${props.gameName} · ${displayDate}`];

  if (props.modeKind === 'qa' || (props.questionsAsked !== undefined && props.maxQuestions !== undefined)) {
    const qAsked = props.questionsAsked ?? 0;
    const maxQ = props.maxQuestions ?? 10;
    const gMade = props.guessesMade ?? 0;
    const maxG = props.maxGuesses ?? 3;
    if (props.won) {
      if (qAsked === 0) {
        lines.push(`Solved on 1st try (0 questions) ${emoji}`);
      } else {
        const qWord = qAsked === 1 ? 'question' : 'questions';
        const gWord = gMade === 1 ? 'guess' : 'guesses';
        lines.push(`Solved in ${qAsked} ${qWord}, ${gMade} ${gWord} ${emoji}`);
      }
      if (props.points && props.points > 0) {
        lines.push(`Score: ${props.points.toLocaleString('en-US')} pts`);
      }
      lines.push('');
      lines.push(`${'🟩'.repeat(Math.min(qAsked, maxQ))}${'⬜'.repeat(Math.max(0, maxQ - qAsked))} 🎯`);
    } else {
      lines.push(`X/${maxG} guesses (${qAsked}/${maxQ} questions) ${emoji}`);
      lines.push('');
      lines.push('🟥'.repeat(maxG));
    }
  } else if (props.score !== undefined && props.maxScore !== undefined) {
    lines.push(`Score: ${props.score}/${props.maxScore} ${emoji}`);
    if (props.elapsedSeconds !== undefined) {
      lines.push(`Time: ${formatDuration(props.elapsedSeconds)}`);
    }
  } else if (props.guessesMade !== undefined && props.maxGuesses !== undefined) {
    lines.push(
      props.won
        ? `Solved in ${props.guessesMade}/${props.maxGuesses} guesses ${emoji}`
        : `X/${props.maxGuesses} guesses ${emoji}`,
    );
    if (props.points && props.points > 0) {
      lines.push(`Score: ${props.points.toLocaleString('en-US')} pts`);
    }
  } else {
    lines.push(props.won ? `Completed ${emoji}` : `Played ${emoji}`);
  }

  lines.push('');
  lines.push(fullUrl);
  return lines.join('\n');
}

export default function GameResultDashboard(props: GameResultDashboardProps) {
  const {
    mode,
    modeKind = 'qa',
    gameName,
    gamePath,
    date,
    isDaily = true,
    won,
    outcomeLabel,
    subtitle,
    points,
    targetLabel,
    targetName,
    targetSubtitle,
    targetCountryCode,
    targetImageUrl,
    targetImageAlt,
    targetAccessory,
    questionsAsked,
    maxQuestions,
    guessesMade,
    maxGuesses,
    score,
    maxScore,
    elapsedSeconds,
    metrics: customMetrics,
    shareText: customShareText,
    shareTitle,
    duelMode,
    primaryAction,
    secondaryActions,
    detailsSlot,
    detailTabs,
    detailsTitle = 'Details & Notes',
    onClose,
    closeLabel = 'Close',
    variant = 'modal',
  } = props;

  const { today } = useDailyClock();
  const displayDate = date || today;
  const tabListId = useId();

  // Stats & leaderboard state
  const [period, setPeriod] = useState<DashboardLeaderboardPeriod>('daily');
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [leaderboardOverride, setLeaderboardOverride] = useState<DashboardLeaderboardPayload | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(true);
  const [summaryUnavailable, setSummaryUnavailable] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [isExpanding, setIsExpanding] = useState(false);

  // Detail tabs & mobile collapsible state
  const [activeDetailTab, setActiveDetailTab] = useState<string>(detailTabs?.[0]?.id ?? '');
  const [mobileDetailsOpen, setMobileDetailsOpen] = useState(false);

  // Keep activeDetailTab synchronized if detailTabs change
  const resolvedDetailTab =
    detailTabs && detailTabs.length > 0
      ? detailTabs.some((t) => t.id === activeDetailTab)
        ? activeDetailTab
        : detailTabs[0].id
      : '';

  // Body scroll lock + Escape key for modal variant
  useEffect(() => {
    if (variant !== 'modal') return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && onClose) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [variant, onClose]);

  // Fetch dashboard summary from unified stats API
  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    setSummaryLoading(true);
    setSummaryUnavailable(false);
    setLeaderboardOverride(null);
    setIsExpanded(false);

    statsService
      .getSummary(
        mode,
        { date: isDaily ? displayDate : undefined, period, limit: 10 },
        controller.signal,
      )
      .then((data) => {
        if (!active) return;
        setSummary(data);
        setSummaryUnavailable(false);
      })
      .catch((err) => {
        if (!active || controller.signal.aborted) return;
        console.warn('[GameResultDashboard] Stats summary unavailable:', err?.message || err);
        setSummaryUnavailable(true);
      })
      .finally(() => {
        if (active) setSummaryLoading(false);
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, [mode, displayDate, isDaily, period]);

  const handleToggleExpand = async () => {
    if (isExpanded) {
      setIsExpanded(false);
      return;
    }
    setIsExpanded(true);
    const currentEntries = leaderboardOverride?.entries ?? summary?.leaderboard?.entries ?? [];
    const totalRanked = leaderboardOverride?.total_ranked ?? summary?.leaderboard?.total_ranked ?? 0;
    if (currentEntries.length >= 25 || (totalRanked > 0 && currentEntries.length >= totalRanked)) {
      return;
    }
    setIsExpanding(true);
    try {
      const expanded = await statsService.getLeaderboard(mode, {
        date: isDaily ? displayDate : undefined,
        period,
        limit: 25,
        offset: 0,
      });
      setLeaderboardOverride(expanded);
    } catch {
      // Keep existing 10 entries gracefully
    } finally {
      setIsExpanding(false);
    }
  };

  const activeLeaderboard = leaderboardOverride ?? summary?.leaderboard ?? null;

  // Derived KPI metrics
  const kpiMetrics: ResultDashboardMetric[] = useMemo(() => {
    if (customMetrics && customMetrics.length > 0) return customMetrics;
    const list: ResultDashboardMetric[] = [];

    if (questionsAsked !== undefined && maxQuestions !== undefined) {
      list.push({
        label: 'Questions',
        value: `${questionsAsked} / ${maxQuestions}`,
        subtext:
          summary?.avg_questions_won != null
            ? `Avg ${summary.avg_questions_won.toFixed(1)}`
            : undefined,
      });
    }

    if (guessesMade !== undefined && maxGuesses !== undefined) {
      list.push({
        label: modeKind === 'route' ? 'Hops' : 'Guesses',
        value: `${guessesMade} / ${maxGuesses}`,
        subtext:
          summary?.avg_guesses_won != null
            ? `Avg ${summary.avg_guesses_won.toFixed(1)}`
            : undefined,
      });
    }

    if (score !== undefined && maxScore !== undefined) {
      const pct = maxScore > 0 ? Math.round((score / maxScore) * 100) : 0;
      list.push({
        label: 'Score',
        value: `${score} / ${maxScore}`,
        subtext: `${pct}% accuracy`,
        accent: won ? 'emerald' : 'default',
      });
    }

    if (elapsedSeconds !== undefined) {
      list.push({
        label: 'Time',
        value: formatDuration(elapsedSeconds),
        subtext:
          summary?.avg_elapsed_seconds != null
            ? `Avg ${formatDuration(summary.avg_elapsed_seconds)}`
            : undefined,
      });
    }

    if (points !== undefined && points !== null && list.length < 4) {
      list.push({
        label: 'Points',
        value: points > 0 ? `+${points.toLocaleString('en-US')}` : '0',
        accent: won && points > 0 ? 'emerald' : 'default',
      });
    }

    if (summary && summary.played_today > 0 && list.length < 4) {
      list.push({
        label: 'Solve Rate',
        value: `${Math.round(summary.win_rate_pct)}%`,
        subtext: `${summary.played_today.toLocaleString('en-US')} played`,
      });
    }

    return list.slice(0, 4);
  }, [
    customMetrics,
    questionsAsked,
    maxQuestions,
    guessesMade,
    maxGuesses,
    score,
    maxScore,
    elapsedSeconds,
    points,
    won,
    modeKind,
    summary,
  ]);

  const resolvedShareText = useMemo(
    () => customShareText ?? buildDefaultShareText(props, displayDate),
    [customShareText, props, displayDate],
  );

  const flagCode = targetCountryCode?.toLowerCase();
  const resolvedImageSrc =
    targetImageUrl ||
    (flagCode && /^[a-z]{2}$/.test(flagCode) ? `https://flagcdn.com/w320/${flagCode}.png` : null);

  const percentile = summary?.player?.percentile;
  const topPercentileDisplay =
    percentile !== null && percentile !== undefined && Number.isFinite(percentile)
      ? Math.max(1, Math.min(99, Math.round(100 - percentile)))
      : null;

  const hasDetails = Boolean(detailsSlot || (detailTabs && detailTabs.length > 0));

  const detailsContent = (
    <div className="space-y-3">
      {detailTabs && detailTabs.length > 0 ? (
        <>
          <div
            role="tablist"
            aria-label={detailsTitle}
            className="grid gap-1 rounded-sm border border-white/10 bg-obsidian-950/70 p-1"
            style={{ gridTemplateColumns: `repeat(${detailTabs.length}, minmax(0, 1fr))` }}
          >
            {detailTabs.map((tab) => {
              const selected = tab.id === resolvedDetailTab;
              return (
                <button
                  key={tab.id}
                  type="button"
                  id={`${tabListId}-${tab.id}-tab`}
                  role="tab"
                  aria-selected={selected}
                  aria-controls={`${tabListId}-${tab.id}-panel`}
                  onClick={() => setActiveDetailTab(tab.id)}
                  className={`flex min-h-10 items-center justify-center gap-2 rounded-xs px-2.5 py-2 text-xs font-semibold transition-colors cursor-pointer ${
                    selected
                      ? 'bg-white/10 text-sand-100'
                      : 'text-zinc-400 hover:text-sand-100'
                  }`}
                >
                  {tab.icon}
                  <span className="truncate">{tab.label}</span>
                  {tab.badge !== undefined && (
                    <span className="rounded-full bg-white/10 px-1.5 py-0.5 font-mono text-[10px]">
                      {tab.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
          {detailTabs.map((tab) => (
            <div
              key={tab.id}
              id={`${tabListId}-${tab.id}-panel`}
              role="tabpanel"
              aria-labelledby={`${tabListId}-${tab.id}-tab`}
              className={tab.id === resolvedDetailTab ? 'block' : 'hidden'}
            >
              {tab.content}
            </div>
          ))}
        </>
      ) : (
        detailsSlot
      )}
    </div>
  );

  const dashboardBody = (
    <section
      aria-label={`${gameName} result dashboard`}
      className={`relative w-full max-w-6xl xl:max-w-7xl mx-auto rounded-sm border border-white/15 bg-obsidian-950 text-left text-sand-100 shadow-2xl ${
        variant === 'modal'
          ? 'max-h-[calc(var(--app-height,100dvh)-1rem)] sm:max-h-[calc(var(--app-height,100dvh)-2.5rem)] overflow-y-auto overscroll-contain [-webkit-overflow-scrolling:touch]'
          : ''
      }`}
      onClick={(e) => e.stopPropagation()}
    >
      {/* Sticky Top Bar (crucial for mobile sheet ergonomics) */}
      <header className="sticky top-0 z-20 flex items-center justify-between gap-3 border-b border-white/10 bg-obsidian-950/95 backdrop-blur-md px-4 py-3 sm:px-6">
        <div className="flex min-w-0 flex-wrap items-center gap-x-2.5 gap-y-1">
          <span className="font-mono text-xs font-semibold text-emerald-400 uppercase tracking-wider">
            {gameName}
          </span>
          <span className="text-zinc-600 select-none" aria-hidden="true">·</span>
          <time dateTime={displayDate} className="font-mono text-xs text-zinc-400">
            {isDaily ? displayDate : 'Challenge Round'}
          </time>
          {summary && summary.played_today > 0 && (
            <>
              <span className="hidden sm:inline text-zinc-600 select-none" aria-hidden="true">·</span>
              <span className="hidden sm:inline-flex items-center gap-1.5 font-mono text-xs text-zinc-300">
                <Users size={12} className="text-emerald-400" aria-hidden="true" />
                {summary.played_today.toLocaleString('en-US')} played today · {Math.round(summary.win_rate_pct)}% solved
              </span>
            </>
          )}
        </div>

        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="flex h-9 w-9 sm:h-10 sm:w-10 shrink-0 items-center justify-center rounded-full bg-white/5 text-zinc-300 hover:bg-white/15 hover:text-white transition-colors cursor-pointer"
            aria-label={closeLabel}
            title={closeLabel}
          >
            <X size={17} />
          </button>
        )}
      </header>

      {/* Main Dashboard Content */}
      <div className="p-4 sm:p-6 space-y-5">
        {/* 12-Col Hero Banner */}
        <div className="rounded-sm border border-white/10 bg-gradient-to-br from-obsidian-900/90 via-obsidian-900/60 to-obsidian-950 p-4 sm:p-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-4 min-w-0">
            {resolvedImageSrc && (
              <div className="shrink-0 overflow-hidden rounded-sm border border-white/15 bg-obsidian-950/90 p-1.5 shadow-md">
                <img
                  src={resolvedImageSrc}
                  alt={targetImageAlt || targetName || gameName}
                  className="h-14 w-20 sm:h-18 sm:w-28 object-contain"
                />
              </div>
            )}
            <div className="min-w-0">
              {targetLabel && (
                <span className="font-mono text-[11px] font-semibold uppercase tracking-wider text-emerald-400">
                  {targetLabel}
                </span>
              )}
              <h2 className="mt-0.5 break-words font-serif text-2xl sm:text-3xl lg:text-4xl font-bold tracking-tight text-sand-100">
                {targetName || (won ? 'Puzzle Solved' : 'Game Over')}
              </h2>
              {targetSubtitle && (
                <p className="mt-0.5 text-xs sm:text-sm text-zinc-400">{targetSubtitle}</p>
              )}
              {subtitle && (
                <p className="mt-1 text-xs sm:text-sm text-zinc-400 leading-relaxed">{subtitle}</p>
              )}
              {summary && summary.played_today > 0 && (
                <p className="mt-1.5 flex sm:hidden items-center gap-1.5 font-mono text-[11px] text-zinc-400">
                  <Users size={11} className="text-emerald-400" aria-hidden="true" />
                  {summary.played_today.toLocaleString('en-US')} played today · {Math.round(summary.win_rate_pct)}% solved
                </p>
              )}
            </div>
          </div>

          <div className="flex flex-wrap md:flex-col items-center md:items-end justify-between gap-2.5 shrink-0 border-t md:border-t-0 border-white/10 pt-3 md:pt-0">
            <div className="flex flex-wrap items-center gap-2">
              <span
                className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 font-mono text-xs font-semibold ${
                  won
                    ? 'bg-emerald-500/15 border border-emerald-500/35 text-emerald-300'
                    : 'bg-rose-500/15 border border-rose-500/35 text-rose-300'
                }`}
              >
                {won ? <Trophy size={13} aria-hidden="true" /> : <X size={13} aria-hidden="true" />}
                <span>{outcomeLabel ?? (won ? 'Solved' : 'Game Over')}</span>
              </span>

              {won && topPercentileDisplay !== null && (
                <span className="inline-flex items-center gap-1 rounded-full border border-amber-400/35 bg-amber-400/10 px-2.5 py-1 font-mono text-[11px] font-semibold text-amber-200">
                  <Sparkles size={11} aria-hidden="true" />
                  Top {topPercentileDisplay}% today
                </span>
              )}
            </div>

            {won && points !== null && points !== undefined && points > 0 && (
              <div className="font-mono text-2xl sm:text-3xl font-bold text-emerald-300 tabular-nums">
                +{points.toLocaleString('en-US')} <span className="text-sm font-normal text-emerald-400/80">pts</span>
              </div>
            )}

            {targetAccessory && <div className="mt-1">{targetAccessory}</div>}
          </div>
        </div>

        {/* Mobile Share Bar right under Hero for instant sharing */}
        <div className="lg:hidden">
          <ShareActionBar
            shareText={resolvedShareText}
            shareTitle={shareTitle ?? `${gameName} Daily Result`}
            isDaily={isDaily}
            primaryAction={primaryAction}
            secondaryActions={secondaryActions}
          />
        </div>

        {/* 12-Col Desktop Bento Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
          {/* LEFT 7 COLS: KPI Strip + Distribution Chart + Details */}
          <div className="lg:col-span-7 space-y-5 min-w-0">
            {/* KPI Strip */}
            {kpiMetrics.length > 0 && (
              <dl
                className="grid grid-cols-2 sm:grid-cols-4 gap-2.5"
                aria-label="Performance metrics"
              >
                {kpiMetrics.map((metric) => (
                  <div
                    key={metric.label}
                    className="rounded-sm border border-white/10 bg-obsidian-900/60 px-3.5 py-3 min-w-0"
                  >
                    <dt className="font-mono text-[10px] uppercase tracking-wider text-zinc-400 truncate">
                      {metric.label}
                    </dt>
                    <dd
                      className={`mt-1 font-mono text-lg sm:text-xl font-bold tabular-nums truncate ${
                        metric.accent === 'emerald'
                          ? 'text-emerald-300'
                          : metric.accent === 'amber'
                          ? 'text-amber-300'
                          : metric.accent === 'rose'
                          ? 'text-rose-300'
                          : 'text-sand-100'
                      }`}
                    >
                      {metric.value}
                    </dd>
                    {metric.subtext && (
                      <div className="mt-0.5 font-mono text-[10px] text-zinc-400 truncate">
                        {metric.subtext}
                      </div>
                    )}
                  </div>
                ))}
              </dl>
            )}

            {/* Distribution Chart */}
            <DistributionChart
              modeKind={modeKind}
              questions={summary?.distributions?.questions}
              guesses={summary?.distributions?.guesses}
              score={summary?.distributions?.score}
              avgQuestions={summary?.avg_questions_won}
              avgGuesses={summary?.avg_guesses_won}
              avgScore={summary?.avg_score}
              playerQuestions={questionsAsked}
              playerGuesses={guessesMade}
              playerWon={won}
              isLoading={summaryLoading}
              isUnavailable={summaryUnavailable}
              completedToday={summary?.completed_today}
            />

            {/* Details Slot (always open on lg+, collapsible on mobile) */}
            {hasDetails && (
              <section
                aria-label={detailsTitle}
                className="rounded-sm border border-white/10 bg-obsidian-900/60 p-4 sm:p-5"
              >
                <button
                  type="button"
                  onClick={() => setMobileDetailsOpen((prev) => !prev)}
                  aria-expanded={mobileDetailsOpen}
                  className="flex lg:hidden w-full items-center justify-between gap-2 text-left cursor-pointer"
                >
                  <span className="font-mono text-xs font-semibold uppercase tracking-wider text-sand-100">
                    {detailsTitle}
                  </span>
                  <ChevronDown
                    size={16}
                    className={`text-zinc-400 transition-transform ${mobileDetailsOpen ? 'rotate-180' : ''}`}
                    aria-hidden="true"
                  />
                </button>
                <div className={mobileDetailsOpen ? 'mt-3 block' : 'hidden lg:block'}>
                  {detailsContent}
                </div>
              </section>
            )}
          </div>

          {/* RIGHT 5 COLS: Compact Leaderboard + Share (desktop) + Next Mode Shelf */}
          <div className="lg:col-span-5 space-y-5 min-w-0">
            <CompactLeaderboard
              period={period}
              onPeriodChange={setPeriod}
              leaderboard={activeLeaderboard}
              isLoading={summaryLoading}
              isExpanding={isExpanding}
              isExpanded={isExpanded}
              onToggleExpand={handleToggleExpand}
              isUnavailable={summaryUnavailable}
            />

            <div className="hidden lg:block">
              <ShareActionBar
                shareText={resolvedShareText}
                shareTitle={shareTitle ?? `${gameName} Daily Result`}
                isDaily={isDaily}
                primaryAction={primaryAction}
                secondaryActions={secondaryActions}
              />
            </div>

            <NextModeShelf currentPath={gamePath} duelMode={duelMode} />
          </div>
        </div>

        {/* Footer close button for modal */}
        {variant === 'modal' && onClose && (
          <footer className="flex justify-end border-t border-white/10 pt-4 pb-[env(safe-area-inset-bottom)]">
            <button
              type="button"
              onClick={onClose}
              className="min-h-11 w-full sm:w-auto px-5 py-2 rounded-sm border border-white/15 text-xs font-semibold text-zinc-200 hover:bg-white/10 hover:text-white transition-colors cursor-pointer"
            >
              {closeLabel}
            </button>
          </footer>
        )}
      </div>
    </section>
  );

  if (variant === 'inline') {
    return dashboardBody;
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={`${gameName} Daily Results`}
      onClick={onClose}
      className="fixed inset-0 z-[1200] flex items-center justify-center p-2 sm:p-5 bg-black/80 backdrop-blur-md animate-in fade-in duration-150 cursor-pointer"
    >
      <div className="relative z-10 w-full cursor-default">{dashboardBody}</div>
    </div>
  );
}
