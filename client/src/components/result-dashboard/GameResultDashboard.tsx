import { useEffect, useId, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, Trophy, X, ChevronDown, Sparkles } from 'lucide-react';
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
import NextModeShelf, { getNextDailyGame } from './NextModeShelf';
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

  if (
    props.modeKind === 'qa' ||
    (props.questionsAsked !== undefined && props.maxQuestions !== undefined)
  ) {
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
      lines.push(
        `${'🟩'.repeat(Math.min(qAsked, maxQ))}${'⬜'.repeat(Math.max(0, maxQ - qAsked))} 🎯`,
      );
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
  const [leaderboardOverride, setLeaderboardOverride] =
    useState<DashboardLeaderboardPayload | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(true);
  const [summaryUnavailable, setSummaryUnavailable] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [isExpanding, setIsExpanding] = useState(false);

  // Collapsible details & active tab (collapsed by default on desktop and mobile)
  const [activeDetailTab, setActiveDetailTab] = useState<string>(detailTabs?.[0]?.id ?? '');
  const [detailsOpen, setDetailsOpen] = useState(false);

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
    const totalRanked =
      leaderboardOverride?.total_ranked ?? summary?.leaderboard?.total_ranked ?? 0;
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
      // Keep existing entries gracefully
    } finally {
      setIsExpanding(false);
    }
  };

  const activeLeaderboard = leaderboardOverride ?? summary?.leaderboard ?? null;

  const percentile = summary?.player?.percentile;
  const topPercentileDisplay =
    percentile !== null && percentile !== undefined && Number.isFinite(percentile)
      ? Math.max(1, Math.min(99, Math.round(100 - percentile)))
      : null;

  // Minimal 3-metric stat row (or customMetrics when explicitly provided)
  const statMetrics: ResultDashboardMetric[] = useMemo(() => {
    if (customMetrics && customMetrics.length > 0) {
      return customMetrics.slice(0, 3);
    }

    const playedValue =
      summary && summary.played_today > 0 ? summary.played_today.toLocaleString('en-US') : '--';
    const playedSub =
      summary && summary.completed_today > 0
        ? `${summary.completed_today.toLocaleString('en-US')} finished`
        : isDaily
        ? 'Today'
        : 'Challenge';

    const winRateValue =
      summary && summary.played_today > 0 ? `${Math.round(summary.win_rate_pct)}%` : '--';
    let winRateSub: string | undefined;
    if (summary?.avg_questions_won != null) {
      winRateSub = `Avg ${summary.avg_questions_won.toFixed(1)} Q`;
    } else if (summary?.avg_guesses_won != null) {
      winRateSub = `Avg ${summary.avg_guesses_won.toFixed(1)} ${modeKind === 'route' ? 'hops' : 'G'}`;
    } else if (summary?.avg_score != null) {
      winRateSub = `Avg ${summary.avg_score.toFixed(1)}`;
    } else if (summary?.avg_elapsed_seconds != null) {
      winRateSub = `Avg ${formatDuration(summary.avg_elapsed_seconds)}`;
    }

    // Third metric: Your rank if available, otherwise player's run summary vs average
    let thirdMetric: ResultDashboardMetric;
    if (summary?.player?.daily_rank != null) {
      thirdMetric = {
        label: 'Your rank',
        value: `#${summary.player.daily_rank}`,
        subtext: topPercentileDisplay !== null ? `Top ${topPercentileDisplay}%` : 'Today',
        accent: won ? 'emerald' : 'default',
      };
    } else if (questionsAsked !== undefined && maxQuestions !== undefined) {
      thirdMetric = {
        label: 'Your run',
        value: `${questionsAsked}Q · ${guessesMade ?? 0}G`,
        subtext:
          summary?.avg_questions_won != null
            ? `Avg ${summary.avg_questions_won.toFixed(1)} Q`
            : `${maxQuestions}Q limit`,
        accent: won ? 'emerald' : 'default',
      };
    } else if (score !== undefined && maxScore !== undefined) {
      thirdMetric = {
        label: 'Your score',
        value: `${score} / ${maxScore}`,
        subtext: elapsedSeconds !== undefined ? formatDuration(elapsedSeconds) : undefined,
        accent: won ? 'emerald' : 'default',
      };
    } else if (guessesMade !== undefined && maxGuesses !== undefined) {
      thirdMetric = {
        label: modeKind === 'route' ? 'Your hops' : 'Your guesses',
        value: `${guessesMade} / ${maxGuesses}`,
        subtext:
          summary?.avg_guesses_won != null
            ? `Avg ${summary.avg_guesses_won.toFixed(1)}`
            : undefined,
        accent: won ? 'emerald' : 'default',
      };
    } else if (elapsedSeconds !== undefined) {
      thirdMetric = {
        label: 'Your time',
        value: formatDuration(elapsedSeconds),
        subtext:
          summary?.avg_elapsed_seconds != null
            ? `Avg ${formatDuration(summary.avg_elapsed_seconds)}`
            : undefined,
      };
    } else {
      thirdMetric = {
        label: 'Your rank',
        value: '--',
        subtext: 'Unranked',
      };
    }

    return [
      { label: 'Played today', value: playedValue, subtext: playedSub },
      { label: 'Win rate', value: winRateValue, subtext: winRateSub },
      thirdMetric,
    ];
  }, [
    customMetrics,
    summary,
    isDaily,
    modeKind,
    topPercentileDisplay,
    won,
    questionsAsked,
    maxQuestions,
    guessesMade,
    maxGuesses,
    score,
    maxScore,
    elapsedSeconds,
  ]);

  const nextDailyGame = useMemo(
    () => getNextDailyGame(gamePath, displayDate),
    [gamePath, displayDate],
  );

  const resolvedShareText = useMemo(
    () => customShareText ?? buildDefaultShareText(props, displayDate),
    [customShareText, props, displayDate],
  );

  const flagCode = targetCountryCode?.toLowerCase();
  const resolvedImageSrc =
    targetImageUrl ||
    (flagCode && /^[a-z]{2}$/.test(flagCode) ? `https://flagcdn.com/w320/${flagCode}.png` : null);

  const hasDetails = Boolean(detailsSlot || (detailTabs && detailTabs.length > 0));

  const detailsToggleLabel = useMemo(() => {
    if (detailTabs && detailTabs.length > 0) {
      return detailTabs.map((t) => t.label).join(' & ');
    }
    return detailsTitle;
  }, [detailTabs, detailsTitle]);

  const detailsBadgeCount = useMemo(() => {
    if (!detailTabs) return undefined;
    const withBadge = detailTabs.find((t) => t.badge !== undefined);
    return withBadge?.badge;
  }, [detailTabs]);

  const dashboardBody = (
    <section
      aria-label={`${gameName} result dashboard`}
      className={`relative w-full max-w-5xl xl:max-w-6xl mx-auto rounded-md border border-app-border border-t-2 border-t-app-accent bg-app-canvas text-left text-app-text shadow-[0_24px_60px_rgba(44,36,27,0.28)] ${
        variant === 'modal'
          ? 'max-h-[calc(var(--app-height,100dvh)-1rem)] sm:max-h-[calc(var(--app-height,100dvh)-2.5rem)] overflow-y-auto overscroll-contain [-webkit-overflow-scrolling:touch] custom-scrollbar'
          : ''
      }`}
      onClick={(e) => e.stopPropagation()}
    >
      {/* Calm Sticky Top Bar */}
      <header className="sticky top-0 z-20 flex items-center justify-between gap-3 border-b border-app-border/60 bg-app-canvas/95 backdrop-blur-md px-5 py-3.5 sm:px-7">
        <div className="flex min-w-0 items-center gap-2.5">
          <span className="font-mono text-xs font-semibold text-app-accent uppercase tracking-[0.14em] shrink-0">
            {gameName}
          </span>
          <span className="text-app-border select-none" aria-hidden="true">
            ·
          </span>
          <time dateTime={displayDate} className="font-mono text-xs text-app-text-muted shrink-0">
            {isDaily ? displayDate : 'Challenge'}
          </time>
          {targetName && (
            <span className="truncate text-xs text-app-text-secondary sm:hidden">· {targetName}</span>
          )}
        </div>

        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="flex h-8 w-8 sm:h-9 sm:w-9 shrink-0 items-center justify-center rounded-sm border border-app-border/60 bg-app-surface text-app-text-secondary hover:border-app-accent hover:bg-app-surface-muted hover:text-app-text transition-colors cursor-pointer"
            aria-label={closeLabel}
            title={closeLabel}
          >
            <X size={16} />
          </button>
        )}
      </header>

      {/* Main Airy Content */}
      <div className="p-5 sm:p-7 space-y-6">
        {/* Clean Top Hero (no nested card border) */}
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6 border-b border-app-border/60 pb-6">
          {/* Hero Left: Outcome + Target Reveal */}
          <div className="flex items-start sm:items-center gap-4 sm:gap-5 min-w-0">
            {resolvedImageSrc && (
              <div className="shrink-0 overflow-hidden rounded-sm border border-app-border/70 bg-app-surface p-1.5 shadow-[1px_2px_6px_rgba(85,75,57,0.08)]">
                <img
                  src={resolvedImageSrc}
                  alt={targetImageAlt || targetName || gameName}
                  className="h-14 w-20 sm:h-16 sm:w-24 object-contain rounded-[2px]"
                />
              </div>
            )}

            <div className="min-w-0 space-y-1">
              <div className="flex flex-wrap items-center gap-2">
                <span
                  className={`inline-flex items-center gap-1.5 rounded-sm border px-2.5 py-0.5 font-mono text-[11px] font-semibold uppercase tracking-wider ${
                    won
                      ? 'border-app-accent/30 bg-app-accent/10 text-app-accent'
                      : 'border-[#a84436]/30 bg-[#a84436]/10 text-[#c85243]'
                  }`}
                >
                  {won ? (
                    <Trophy size={12} aria-hidden="true" />
                  ) : (
                    <X size={12} aria-hidden="true" />
                  )}
                  <span>{outcomeLabel ?? (won ? 'Solved' : 'Game Over')}</span>
                </span>

                {targetLabel && (
                  <span className="font-mono text-[11px] uppercase tracking-[0.14em] text-app-text-muted">
                    {targetLabel}
                  </span>
                )}
              </div>

              <div className="flex flex-wrap items-center gap-3">
                <h2 className="break-words font-serif text-2xl sm:text-3xl lg:text-4xl font-semibold tracking-tight text-app-text">
                  {targetName || (won ? 'Puzzle Solved' : 'Game Over')}
                </h2>
                {targetAccessory && <div className="shrink-0">{targetAccessory}</div>}
              </div>

              {(targetSubtitle || subtitle) && (
                <p className="text-xs sm:text-sm text-app-text-secondary leading-relaxed max-w-xl">
                  {targetSubtitle || subtitle}
                </p>
              )}
              {targetSubtitle && subtitle && (
                <p className="text-xs text-app-text-muted leading-relaxed max-w-xl">{subtitle}</p>
              )}
            </div>
          </div>

          {/* Hero Right: Points + Top X% + Inline Share Controls + Countdown */}
          <div className="flex flex-col lg:items-end gap-3 shrink-0">
            {(won && ((points !== null && points !== undefined && points > 0) || topPercentileDisplay !== null)) && (
              <div className="flex flex-wrap items-baseline lg:justify-end gap-2.5">
                {points !== null && points !== undefined && points > 0 && (
                  <div className="font-mono text-2xl sm:text-3xl font-bold text-app-accent tabular-nums">
                    +{points.toLocaleString('en-US')}{' '}
                    <span className="text-xs font-normal text-app-text-secondary">pts</span>
                  </div>
                )}

                {topPercentileDisplay !== null && (
                  <span className="inline-flex items-center gap-1 rounded-sm border border-[#9a6b2f]/35 bg-[#9a6b2f]/10 px-2.5 py-0.5 font-mono text-[11px] font-semibold text-[#c68f42]">
                    <Sparkles size={11} aria-hidden="true" />
                    Top {topPercentileDisplay}% today
                  </span>
                )}
              </div>
            )}

            {nextDailyGame && (
              <Link
                to={nextDailyGame.path}
                className="group inline-flex items-center justify-center lg:justify-end gap-2 rounded-sm border border-app-accent bg-app-accent px-4 py-2 text-xs font-semibold text-app-canvas shadow-[0_2px_8px_rgb(var(--app-accent)/0.25)] hover:bg-app-accent-hover transition-colors"
              >
                <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-app-canvas/85">
                  Next daily:
                </span>
                <span className="font-serif text-sm font-semibold text-app-canvas">
                  {nextDailyGame.name}
                </span>
                <ArrowRight
                  size={14}
                  className="shrink-0 text-app-canvas group-hover:translate-x-0.5 transition-transform"
                  aria-hidden="true"
                />
              </Link>
            )}

            <ShareActionBar
              shareText={resolvedShareText}
              shareTitle={shareTitle ?? `${gameName} Daily Result`}
              isDaily={isDaily}
              primaryAction={primaryAction}
              secondaryActions={secondaryActions}
              align="right"
            />
          </div>
        </div>

        {/* Row 2: Full-Width Summary Metrics Strip */}
        {statMetrics.length > 0 && (
          <dl
            aria-label="Summary metrics"
            className={`grid divide-x divide-app-border/45 rounded-md border border-app-border/70 border-t-2 border-t-app-accent bg-app-surface shadow-[1px_2px_8px_rgba(85,75,57,0.06)] ${
              statMetrics.length === 2 ? 'grid-cols-2' : 'grid-cols-3'
            }`}
          >
            {statMetrics.map((metric) => (
              <div key={metric.label} className="px-4 py-3 sm:px-5 sm:py-3.5 min-w-0">
                <dt className="font-mono text-[10px] sm:text-[11px] uppercase tracking-[0.12em] text-app-text-muted truncate">
                  {metric.label}
                </dt>
                <dd
                  className={`mt-1 font-mono text-lg sm:text-xl font-bold tabular-nums truncate ${
                    metric.accent === 'emerald'
                      ? 'text-app-accent'
                      : metric.accent === 'amber'
                      ? 'text-[#c68f42]'
                      : metric.accent === 'rose'
                      ? 'text-[#c85243]'
                      : 'text-app-text'
                  }`}
                >
                  {metric.value}
                </dd>
                {metric.subtext && (
                  <div className="mt-0.5 font-mono text-[11px] text-app-text-secondary truncate">
                    {metric.subtext}
                  </div>
                )}
              </div>
            ))}
          </dl>
        )}

        {/* Row 3: Equal-Height 2-Column Grid (Distribution + Leaderboard aligned flush top & bottom) */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-stretch">
          <div className="lg:col-span-7 min-w-0 flex flex-col">
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
              playerScore={score}
              maxScore={maxScore}
              playerWon={won}
              isLoading={summaryLoading}
              isUnavailable={summaryUnavailable}
              completedToday={summary?.completed_today}
            />
          </div>

          <div className="lg:col-span-5 min-w-0 flex flex-col">
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
          </div>
        </div>

        {/* Row 4: Full-Width Collapsible Questions & Guesses Card (never stretches one column) */}
        {hasDetails && (
          <section
            aria-label={detailsTitle}
            className="rounded-md border border-app-border/70 bg-app-surface shadow-[1px_2px_8px_rgba(85,75,57,0.06)]"
          >
            <button
              type="button"
              onClick={() => setDetailsOpen((prev) => !prev)}
              aria-expanded={detailsOpen}
              className="flex w-full items-center justify-between gap-3 px-5 py-3.5 text-left hover:bg-app-surface-muted/60 transition-colors rounded-md cursor-pointer"
            >
              <div className="flex items-center gap-2.5 min-w-0">
                <span className="font-serif text-base font-semibold text-app-text truncate">
                  {detailsToggleLabel}
                </span>
                {detailsBadgeCount !== undefined && (
                  <span className="rounded-sm border border-app-border/50 bg-app-surface-muted px-2 py-0.5 font-mono text-[10px] text-app-text-secondary tabular-nums">
                    {detailsBadgeCount}
                  </span>
                )}
              </div>
              <ChevronDown
                size={16}
                className={`shrink-0 text-app-text-muted transition-transform duration-200 ${
                  detailsOpen ? 'rotate-180' : ''
                }`}
                aria-hidden="true"
              />
            </button>

            {detailsOpen && (
              <div className="border-t border-app-border/50 px-5 py-5 space-y-4">
                {detailTabs && detailTabs.length > 0 ? (
                  detailTabs.length === 2 ? (
                    <>
                      {/* Mobile (< lg): compact tabs */}
                      <div className="space-y-4 lg:hidden">
                        <div
                          role="tablist"
                          aria-label={detailsTitle}
                          className="inline-flex flex-wrap items-center gap-1 rounded-sm border border-app-border/50 bg-app-surface-muted p-0.5"
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
                                className={`inline-flex items-center gap-1.5 rounded-sm px-3 py-1.5 text-xs font-semibold transition-colors cursor-pointer ${
                                  selected
                                    ? 'bg-app-surface text-app-accent shadow-sm'
                                    : 'text-app-text-secondary hover:text-app-text'
                                }`}
                              >
                                {tab.icon}
                                <span>{tab.label}</span>
                                {tab.badge !== undefined && (
                                  <span className="rounded-sm bg-app-surface-muted px-1.5 py-0.25 font-mono text-[10px] text-app-text-secondary">
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
                      </div>

                      {/* Desktop (lg+): side-by-side 2-column split (Questions left, Guesses right) */}
                      <div className="hidden lg:grid lg:grid-cols-12 lg:gap-6 items-start">
                        {detailTabs.map((tab, idx) => (
                          <div
                            key={tab.id}
                            className={`min-w-0 space-y-3 ${
                              idx === 0
                                ? 'lg:col-span-7'
                                : 'lg:col-span-5 lg:border-l lg:border-app-border/45 lg:pl-6'
                            }`}
                          >
                            <div className="flex items-center gap-2">
                              <span className="text-app-accent">{tab.icon}</span>
                              <h4 className="font-mono text-xs font-semibold uppercase tracking-[0.12em] text-app-text">
                                {tab.label}
                              </h4>
                              {tab.badge !== undefined && (
                                <span className="rounded-sm border border-app-border/50 bg-app-surface-muted px-1.5 py-0.5 font-mono text-[10px] text-app-text-secondary tabular-nums">
                                  {tab.badge}
                                </span>
                              )}
                            </div>
                            {tab.content}
                          </div>
                        ))}
                      </div>
                    </>
                  ) : (
                    <>
                      {detailTabs.length > 1 && (
                        <div
                          role="tablist"
                          aria-label={detailsTitle}
                          className="inline-flex flex-wrap items-center gap-1 rounded-sm border border-app-border/50 bg-app-surface-muted p-0.5"
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
                                className={`inline-flex items-center gap-1.5 rounded-sm px-3 py-1.5 text-xs font-semibold transition-colors cursor-pointer ${
                                  selected
                                    ? 'bg-app-surface text-app-accent shadow-sm'
                                    : 'text-app-text-secondary hover:text-app-text'
                                }`}
                              >
                                {tab.icon}
                                <span>{tab.label}</span>
                                {tab.badge !== undefined && (
                                  <span className="rounded-sm bg-app-surface-muted px-1.5 py-0.25 font-mono text-[10px] text-app-text-secondary">
                                    {tab.badge}
                                  </span>
                                )}
                              </button>
                            );
                          })}
                        </div>
                      )}

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
                  )
                ) : (
                  detailsSlot
                )}
              </div>
            )}
          </section>
        )}

        {/* Lightweight Bottom Strip */}
        <NextModeShelf currentPath={gamePath} duelMode={duelMode} />
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
      className="fixed inset-0 z-[1200] flex items-center justify-center p-2.5 sm:p-6 bg-[#1f1b16]/55 backdrop-blur-sm animate-in fade-in duration-150 cursor-pointer"
    >
      <div className="relative z-10 w-full cursor-default">{dashboardBody}</div>
    </div>
  );
}
