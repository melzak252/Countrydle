import React, { useEffect, useId, useState } from 'react';
import {
  Calendar,
  ChevronDown,
  ChevronRight,
  Clock,
  HelpCircle,
  Loader2,
  RefreshCw,
  Sparkles,
  Target,
  TrendingUp,
  User as UserIcon,
  UserX,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { adminService } from '../../services/api';
import type {
  AdminGameSessionItem,
  AdminGameSessionTimelineEvent,
  AdminTargetStrategyStats,
} from '../../types';

interface AdminSessionsTabProps {
  onTestInQA?: (target: { mode: string; targetName?: string; questionText?: string }) => void;
  selectedMode: string;
  selectedDate: string;
  onFiltersChange: (mode: string, date: string) => void;
}

const REGIONAL_LABELS = {
  voivodeships: 'Polish voivodeships',
  london_boroughs: 'London boroughs',
  england_counties: 'English ceremonial counties',
} as const;

const MODES = [
  ['countrydle', 'World countries'], ['powiatdle', 'Polish counties'],
  ['us_statedle', 'US states'], ['wojewodztwodle', 'Polish voivodeships'],
  ['flagdle', 'Flags'], ['continental', 'Continental (all)'],
  ['continental:europe', 'Europe'], ['continental:asia', 'Asia'],
  ['continental:africa', 'Africa'], ['continental:americas', 'Americas'],
  ['heraldry', 'County coats of arms'], ['coats_quiz', 'Coats quiz'],
  ['county_flags', 'County flags'], ['county_flags_quiz', 'County flags quiz'],
  ...(['voivodeships', 'london_boroughs', 'england_counties'] as const).flatMap((scope) =>
    (['coat', 'flag'] as const).flatMap((symbol) =>
      ([false, true] as const).map((quiz) => [
        `regional_symbols:${scope}:${symbol}${quiz ? ':quiz' : ''}`,
        `${REGIONAL_LABELS[scope]} ${symbol === 'coat' ? 'coats of arms' : 'flags'}${quiz ? ' quiz' : ''}`,
      ] as const))),
] as const;
const PAGE_SIZE = 20;
const panelClass = 'min-w-0 rounded-md border border-app-border bg-app-surface p-4 text-app-text';
const toolbarClass = 'flex flex-wrap items-end gap-4 rounded-md border border-app-border bg-app-surface p-4';
const fieldClass = 'flex min-w-0 flex-col gap-2 text-sm font-medium text-app-text-secondary';
const controlClass = 'min-h-11 w-full min-w-0 rounded-sm border border-app-border bg-app-surface-muted px-3 py-2 text-app-text placeholder:text-app-text-muted focus:border-app-accent focus:outline-none focus:ring-2 focus:ring-app-focus disabled:cursor-not-allowed disabled:opacity-50';
const buttonBaseClass = 'inline-flex min-h-11 items-center justify-center gap-2 rounded-sm border px-3 py-2 text-sm font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus disabled:cursor-not-allowed disabled:opacity-50';
const buttonClass = `${buttonBaseClass} border-app-border bg-app-surface-muted text-app-text hover:border-app-accent-hover hover:bg-app-surface-raised`;
const badgeBaseClass = 'inline-flex items-center gap-1 rounded-sm border px-2 py-0.5 text-xs font-medium';
const badgeClass = `${badgeBaseClass} border-app-border bg-app-surface-muted text-app-text-secondary`;
const successBadgeClass = `${badgeBaseClass} border-emerald-300 bg-emerald-50 text-emerald-800`;
const warningBadgeClass = `${badgeBaseClass} border-amber-300 bg-amber-50 text-amber-900`;
const errorBadgeClass = `${badgeBaseClass} border-rose-300 bg-rose-50 text-rose-800`;
const metaClass = 'text-xs leading-5 text-app-text-muted';
const questionClass = 'break-words text-base leading-6 text-app-text [overflow-wrap:anywhere]';
const diagnosticsClass = 'max-h-[360px] max-w-full overflow-auto whitespace-pre-wrap break-words rounded-sm bg-app-surface-muted p-3 font-mono text-xs leading-5 text-app-text-secondary focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus';
const pagerClass = 'flex flex-wrap items-center justify-between gap-3';

const isQuizMode = (mode: string) => ['coats_quiz', 'county_flags_quiz'].includes(mode) || (mode.startsWith('regional_symbols:') && mode.endsWith(':quiz'));
const isSymbolMode = (mode: string) => ['heraldry', 'county_flags'].includes(mode) || mode.startsWith('regional_symbols:');
const isFlagQuiz = (mode: string) => mode === 'county_flags_quiz' || (mode.startsWith('regional_symbols:') && mode.endsWith(':flag:quiz'));

type SessionResult = {
  queryKey: string;
  items: AdminGameSessionItem[];
  total: number;
};

type RequestState = {
  queryKey: string;
  status: 'loading' | 'success' | 'error';
};

function formatNumber(value: number, locale: string, maximumFractionDigits = 0): string {
  return new Intl.NumberFormat(locale, { maximumFractionDigits }).format(value);
}

function formatPercent(value: number, locale: string): string {
  return new Intl.NumberFormat(locale, {
    style: 'percent',
    maximumFractionDigits: 1,
  }).format(value / 100);
}

function formatGameDate(dateString: string, locale: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(dateString);
  if (!match) return dateString;
  const date = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])));
  return new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeZone: 'UTC' }).format(date);
}

function formatDateTime(isoString: string | null | undefined, locale: string): string {
  if (!isoString) return '';
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return isoString;
  return new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'short' }).format(date);
}

function formatTime(isoString: string | null | undefined, locale: string): string {
  if (!isoString) return '';
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return isoString;
  return new Intl.DateTimeFormat(locale, {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(date);
}

function formatDuration(
  seconds: number | null | undefined,
  locale: string,
  t: (key: string, options?: Record<string, unknown>) => string,
): string {
  if (seconds == null || seconds < 0) return '—';
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  const values = {
    minutes: formatNumber(minutes, locale),
    seconds: formatNumber(remainingSeconds, locale),
  };
  return minutes === 0
    ? t('adminSessions.durationSeconds', { count: values.seconds })
    : t('adminSessions.durationMinutesSeconds', values);
}

function getAnswerLabel(
  event: AdminGameSessionTimelineEvent,
  t: (key: string) => string,
): { label: string; className: string } {
  if (event.valid === false) {
    return { label: t('adminSessions.invalid'), className: warningBadgeClass };
  }
  if (event.answer === true) {
    return { label: t('adminSessions.yes'), className: successBadgeClass };
  }
  if (event.answer === false) {
    return { label: t('adminSessions.no'), className: badgeClass };
  }
  return { label: t('adminSessions.noAnswer'), className: badgeClass };
}

export const AdminSessionsTab: React.FC<AdminSessionsTabProps> = ({ onTestInQA, selectedMode, selectedDate, onFiltersChange }) => {
  const { t } = useTranslation();
  const locale = 'en-US';
  const idPrefix = useId().replace(/:/g, '');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [playerTypeFilter, setPlayerTypeFilter] = useState<string>('all');
  const [page, setPage] = useState(1);
  const [listRefresh, setListRefresh] = useState(0);
  const [statsRefresh, setStatsRefresh] = useState(0);
  const [listRetry, setListRetry] = useState(0);
  const [statsRetry, setStatsRetry] = useState(0);
  const [sessionResult, setSessionResult] = useState<SessionResult | null>(null);
  const [sessionRequest, setSessionRequest] = useState<RequestState | null>(null);
  const [statsResult, setStatsResult] = useState<{
    queryKey: string;
    stats: AdminTargetStrategyStats;
  } | null>(null);
  const [statsRequest, setStatsRequest] = useState<RequestState | null>(null);
  const [expandedSessions, setExpandedSessions] = useState<Record<string, boolean>>({});

  const sessionQueryKey = JSON.stringify({
    mode: selectedMode,
    date: selectedDate,
    status: statusFilter,
    playerType: playerTypeFilter,
    page,
  });
  const statsQueryKey = JSON.stringify({ mode: selectedMode, date: selectedDate });

  useEffect(() => {
    let active = true;
    setSessionRequest({ queryKey: sessionQueryKey, status: 'loading' });

    adminService
      .getGameSessions({
        mode: selectedMode,
        date: selectedDate,
        status: statusFilter,
        player_type: playerTypeFilter,
        page,
        limit: PAGE_SIZE,
      })
      .then((response) => {
        if (!active) return;
        setSessionResult({
          queryKey: sessionQueryKey,
          items: response.items,
          total: response.total,
        });
        setSessionRequest({ queryKey: sessionQueryKey, status: 'success' });
      })
      .catch(() => {
        if (active) setSessionRequest({ queryKey: sessionQueryKey, status: 'error' });
      });

    return () => {
      active = false;
    };
  }, [selectedMode, selectedDate, statusFilter, playerTypeFilter, page, listRefresh, listRetry, sessionQueryKey]);

  useEffect(() => {
    let active = true;
    setStatsRequest({ queryKey: statsQueryKey, status: 'loading' });

    adminService
      .getTargetStrategyStats({ mode: selectedMode, date: selectedDate })
      .then((stats) => {
        if (!active) return;
        setStatsResult({ queryKey: statsQueryKey, stats });
        setStatsRequest({ queryKey: statsQueryKey, status: 'success' });
      })
      .catch(() => {
        if (active) setStatsRequest({ queryKey: statsQueryKey, status: 'error' });
      });

    return () => {
      active = false;
    };
  }, [selectedMode, selectedDate, statsRefresh, statsRetry, statsQueryKey]);

  const sessions = sessionResult?.queryKey === sessionQueryKey ? sessionResult : null;
  const stats = statsResult?.queryKey === statsQueryKey ? statsResult.stats : null;
  const sessionStatus = sessionRequest?.queryKey === sessionQueryKey ? sessionRequest.status : 'loading';
  const statsStatus = statsRequest?.queryKey === statsQueryKey ? statsRequest.status : 'loading';
  const sessionsLoading = sessionStatus === 'loading';
  const statsLoading = statsStatus === 'loading';
  const sessionsError = sessionStatus === 'error';
  const statsError = statsStatus === 'error';
  const totalPages = Math.max(1, Math.ceil((sessions?.total ?? 0) / PAGE_SIZE));

  const handleDatePreset = (offsetDays: number) => {
    const date = new Date();
    date.setUTCDate(date.getUTCDate() - offsetDays);
    onFiltersChange(selectedMode, date.toISOString().slice(0, 10));
    setPage(1);
  };

  const refreshAll = () => {
    setListRefresh((value) => value + 1);
    setStatsRefresh((value) => value + 1);
  };

  const toggleSession = (sessionId: string) => {
    setExpandedSessions((previous) => ({
      ...previous,
      [sessionId]: !previous[sessionId],
    }));
  };

  return (
    <div className="space-y-4 text-app-text">
      <div className={toolbarClass} role="group" aria-label={t('adminSessions.filters')}>
        <label className={`${fieldClass} w-full sm:min-w-[180px] sm:flex-1`}>
          <span>{t('adminSessions.mode')}</span>
          <select
            className={controlClass}
            value={selectedMode}
            onChange={(event) => {
              onFiltersChange(event.target.value, selectedDate);
              setPage(1);
            }}
          >
            {MODES.map(([mode, label]) => (
              <option key={mode} value={mode}>{label}</option>
            ))}
          </select>
        </label>

        <div className={`${fieldClass} w-full sm:min-w-[250px] sm:flex-[2]`}>
          <span>{t('adminSessions.date')}</span>
          <div className="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap sm:items-center">
            <button type="button" className={buttonClass} onClick={() => handleDatePreset(0)}>
              {t('adminSessions.today')}
            </button>
            <button type="button" className={buttonClass} onClick={() => handleDatePreset(1)}>
              {t('adminSessions.yesterday')}
            </button>
            <label className="col-span-2 flex min-w-0 items-center gap-2 sm:min-w-[180px] sm:flex-1">
              <Calendar className="h-4 w-4 shrink-0 text-app-text-muted" aria-hidden="true" />
              <span className="sr-only">{t('adminSessions.date')}</span>
              <input
                className={`${controlClass} flex-1`}
                type="date"
                value={selectedDate}
                onChange={(event) => {
                  onFiltersChange(selectedMode, event.target.value);
                  setPage(1);
                }}
              />
            </label>
          </div>
        </div>

        <button
          type="button"
          className={`${buttonClass} w-full sm:w-auto`}
          onClick={refreshAll}
          disabled={sessionsLoading || statsLoading}
        >
          <RefreshCw className="h-4 w-4" aria-hidden="true" />
          {t('adminCommon.refresh')}
        </button>
      </div>

      <section className={`${panelClass} space-y-4`} aria-label={isQuizMode(selectedMode) ? 'Quiz scope and summary' : t('adminSessions.targetSummary')}>
        <div className="grid min-w-0 gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,2fr)] xl:items-center">
          <div className="min-w-0">
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <span className={badgeClass}>{isQuizMode(selectedMode) ? 'Quiz scope' : t('adminSessions.targetEntity')}</span>
              {stats?.target_subtitle && <span className={badgeClass}>{stats.target_subtitle}</span>}
            </div>
            {stats ? (
              <>
                <h2 className="flex min-w-0 items-center gap-2 break-words text-lg font-semibold text-app-text">
                  <Target className="h-6 w-6 shrink-0 text-app-text-muted" aria-hidden="true" />
                  {stats.target_name}
                </h2>
                <p className={`${metaClass} mt-1`}>
                  {isQuizMode(selectedMode) ? `Sessions on ${formatGameDate(stats.game_date || selectedDate, locale)}` : t('adminSessions.challengeDate', {
                    date: formatGameDate(stats.game_date || selectedDate, locale),
                  })}
                </p>
              </>
            ) : (
              <p className="text-base font-semibold text-app-text" role={statsError ? undefined : 'status'}>
                {statsError ? t('adminSessions.targetUnavailable') : t('adminSessions.loadingTarget')}
              </p>
            )}
          </div>

          <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
            {[
              {
                label: t('adminSessions.totalPlayers'),
                value: stats ? formatNumber(stats.total_players, locale) : '—',
              },
              {
                label: t('adminSessions.solveRate'),
                value: stats ? formatPercent(stats.win_rate_pct, locale) : '—',
              },
              ...((isQuizMode(selectedMode) || isSymbolMode(selectedMode) || selectedMode === 'flagdle') ? [] : [
                { label: t('adminSessions.avgQuestionsWon'), value: stats ? formatNumber(stats.avg_questions_winners, locale, 1) : '—' },
                { label: t('adminSessions.avgQuestionsLost'), value: stats ? formatNumber(stats.avg_questions_losers, locale, 1) : '—' },
              ]),
            ].map((metric) => (
              <div key={metric.label} className="min-w-0 rounded-md border border-app-border bg-app-surface-muted p-3">
                <div className={metaClass}>{metric.label}</div>
                <div className="mt-1 text-2xl font-semibold tabular-nums text-app-text">{metric.value}</div>
              </div>
            ))}
          </div>
        </div>

        {statsLoading && stats && (
          <p className={metaClass} role="status">{t('adminCommon.updating')}</p>
        )}
        {statsError && (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-rose-300 bg-rose-50 p-3 text-rose-800" role="alert">
            <span>
              {t('adminSessions.statsError')}
              {stats && ` ${t('adminSessions.staleData')}`}
            </span>
            <button
              type="button"
              className={buttonClass}
              onClick={() => setStatsRetry((value) => value + 1)}
              disabled={statsLoading}
            >
              {t('adminCommon.retry')}
            </button>
          </div>
        )}
      </section>

      <section className={`${panelClass} space-y-4`} aria-labelledby={`${idPrefix}-sessions-heading`}>
        <div className="flex flex-col gap-4 border-b border-app-border pb-4 xl:flex-row xl:items-end xl:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h2 id={`${idPrefix}-sessions-heading`} className="text-lg font-semibold text-app-text">{t('adminSessions.sessionsTitle')}</h2>
              {sessions && (
                <span className={badgeClass}>
                  {t('adminSessions.sessionCount', { count: sessions.total })}
                </span>
              )}
            </div>
          </div>

          <div className="grid min-w-0 gap-3 sm:grid-cols-2 xl:w-[min(100%,32rem)]">
            <label className={fieldClass}>
              <span>{t('adminSessions.statusFilter')}</span>
              <select
                className={controlClass}
                value={statusFilter}
                onChange={(event) => {
                  setStatusFilter(event.target.value);
                  setPage(1);
                }}
              >
                <option value="all">{t('adminSessions.statusAll')}</option>
                <option value="won">{isQuizMode(selectedMode) ? 'Completed' : t('adminSessions.statusWon')}</option>
                <option value="lost">{isQuizMode(selectedMode) ? 'Stopped' : t('adminSessions.statusLost')}</option>
                <option value="in_progress">{t('adminSessions.statusInProgress')}</option>
              </select>
            </label>
            <label className={fieldClass}>
              <span>{t('adminSessions.playerTypeFilter')}</span>
              <select
                className={controlClass}
                value={playerTypeFilter}
                onChange={(event) => {
                  setPlayerTypeFilter(event.target.value);
                  setPage(1);
                }}
              >
                <option value="all">{t('adminSessions.playerTypeAll')}</option>
                <option value="registered">{t('adminSessions.playerTypeRegistered')}</option>
                <option value="guest">{t('adminSessions.playerTypeGuest')}</option>
              </select>
            </label>
          </div>
        </div>

        {sessionsLoading && (
          <p className="flex items-center gap-2 text-app-text" role="status">
            <Loader2 className="h-4 w-4 animate-spin text-app-accent" aria-hidden="true" />
            {sessions ? t('adminCommon.updating') : t('adminSessions.sessionsLoading')}
          </p>
        )}
        {sessionsError && (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-rose-300 bg-rose-50 p-3 text-rose-800" role="alert">
            <span>
              {t('adminSessions.sessionsError')}
              {sessions && ` ${t('adminSessions.staleData')}`}
            </span>
            <button
              type="button"
              className={buttonClass}
              onClick={() => setListRetry((value) => value + 1)}
              disabled={sessionsLoading}
            >
              {t('adminCommon.retry')}
            </button>
          </div>
        )}

        {sessions && sessions.items.length > 0 && (
          <div className="space-y-3" role="region" aria-label={t('adminSessions.sessionResults')}>
            {sessions.items.map((session) => {
              const isExpanded = Boolean(expandedSessions[session.session_id]);
              const encodedId = encodeURIComponent(session.session_id);
              const buttonId = `${idPrefix}-session-button-${encodedId}`;
              const panelId = `${idPrefix}-session-panel-${encodedId}`;
              const isQuiz = isQuizMode(session.mode);
              const hasDetails = session.timeline.length > 0 || session.quiz_solves.length > 0;
              const statusLabel = isQuiz && session.quiz_status === 'given_up' ? 'Stopped' : isQuiz && session.quiz_status === 'completed' ? 'Completed' : t(`adminSessions.status.${session.status}`);
              const started = formatDateTime(session.started_at, locale);
              const completed = formatDateTime(session.completed_at, locale);
              const duration = formatDuration(session.duration_seconds, locale, t);
              const accessibleName = isQuiz
                ? `${session.username}, ${statusLabel}, ${session.solved_count == null ? 'solved count unavailable' : session.mode === 'coats_quiz' ? `${session.solved_count} of 380 solved` : `${session.solved_count} solved`}. ${isExpanded ? 'Hide' : 'Show'} details`
                : t('adminSessions.sessionSummary', {
                username: session.username,
                playerType: session.is_guest ? t('adminSessions.guest') : t('adminSessions.registered'),
                status: statusLabel,
                started: started || t('adminSessions.unknownTime'),
                questions: formatNumber(session.questions_asked, locale),
                guesses: formatNumber(session.guesses_made, locale),
                duration,
                action: isExpanded ? t('adminSessions.hideReplay') : t('adminSessions.showReplay'),
              });

              return (
                <article key={session.session_id} className="overflow-hidden rounded-md border border-app-border bg-app-surface">
                  <button
                    id={buttonId}
                    type="button"
                    className="flex w-full items-center justify-between gap-3 p-4 text-left text-app-text transition-colors hover:bg-app-surface-muted focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-app-focus disabled:cursor-not-allowed disabled:opacity-50"
                    disabled={!hasDetails}
                    aria-expanded={hasDetails ? isExpanded : undefined}
                    aria-controls={hasDetails ? panelId : undefined}
                    aria-label={hasDetails ? accessibleName : undefined}
                    onClick={() => toggleSession(session.session_id)}
                  >
                    <span className="flex min-w-0 items-start gap-3">
                      <span className="mt-1 rounded-md border border-app-border bg-app-surface-muted p-2 text-app-text-muted" aria-hidden="true">
                        {session.is_guest ? <UserX className="h-4 w-4" /> : <UserIcon className="h-4 w-4" />}
                      </span>
                      <span className="min-w-0">
                        <span className="flex flex-wrap items-center gap-2">
                          <span className="max-w-full break-words text-base font-semibold text-app-text" title={session.username}>
                            {session.username}
                          </span>
                          {session.is_guest && <span className={badgeClass}>{t('adminSessions.guest')}</span>}
                          <span
                            className={`${badgeBaseClass} ${
                              session.status === 'won'
                                ? 'border-emerald-300 bg-emerald-50 text-emerald-800'
                                : session.status === 'lost'
                                  ? 'border-rose-300 bg-rose-50 text-rose-800'
                                  : 'border-amber-300 bg-amber-50 text-amber-900'
                            }`}
                          >
                            {statusLabel}
                          </span>
                        </span>
                        <span className={`${metaClass} mt-1 flex flex-wrap items-center gap-x-3 gap-y-1`}>
                          <span>{t('adminSessions.startedAt', { time: started || t('adminSessions.unknownTime') })}</span>
                          {completed && <span>{t('adminSessions.completedAt', { time: completed })}</span>}
                          {isQuiz ? <span>{session.solved_count == null ? 'Solved count unavailable' : session.mode === 'coats_quiz' ? `${session.solved_count}/380 solved` : `${session.solved_count} solved`}</span> : <>
                            <span>{t('adminSessions.questionCount', { count: session.questions_asked })}</span>
                            <span>{t('adminSessions.guessCount', { count: session.guesses_made })}</span>
                          </>}
                          {isSymbolMode(session.mode) && !isQuiz && session.points != null && <span>{formatNumber(session.points, locale)} points</span>}
                          {isQuiz && session.active_elapsed_seconds != null && <span>Active time: {formatDuration(session.active_elapsed_seconds, locale, t)} (client-reported)</span>}
                          {!isQuiz && session.duration_seconds != null && (
                            <span className="inline-flex items-center gap-1">
                              <Clock className="h-3.5 w-3.5" aria-hidden="true" />
                              {t('adminSessions.durationLabel', { duration })}
                            </span>
                          )}
                        </span>
                      </span>
                    </span>
                    {hasDetails && <span className="flex shrink-0 items-center gap-2 text-app-text">
                      <span>{isQuiz ? `${isExpanded ? 'Hide' : 'Show'} solved ${isFlagQuiz(session.mode) ? 'flags' : 'coats'}` : (isExpanded ? t('adminSessions.hideReplay') : t('adminSessions.showReplay'))}</span>
                      {isExpanded
                        ? <ChevronDown className="h-4 w-4" aria-hidden="true" />
                        : <ChevronRight className="h-4 w-4" aria-hidden="true" />}
                    </span>}
                  </button>

                  <div
                    id={panelId}
                    aria-labelledby={buttonId}
                    hidden={!isExpanded}
                    className="space-y-4 border-t border-app-border bg-app-surface-muted p-4"
                  >
                    {session.quiz_solves.length > 0 && <section aria-label={isFlagQuiz(session.mode) ? 'Solved flags' : 'Solved coats'}>
                      <h3 className="text-base font-semibold text-app-text">{isFlagQuiz(session.mode) ? 'Solved flags' : 'Solved coats'}</h3>
                      <p className={`${metaClass} mt-1`}>Active elapsed time since quiz start, client-reported.</p>
                      <ul className="mt-3 space-y-1 text-sm">
                        {session.quiz_solves.map((solve) => <li key={solve.powiat_id} className="flex flex-wrap justify-between gap-2"><span>{solve.name}</span><span>{formatDuration(solve.active_elapsed_seconds, locale, t)}</span></li>)}
                      </ul>
                    </section>}
                    {session.timeline.length > 0 && <>
                    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-app-border pb-3">
                      <h3 className="text-lg font-semibold text-app-text">{t('adminSessions.timelineTitle', { count: session.timeline.length })}</h3>
                      <span className={metaClass}>{t('adminSessions.timelineOrder')}</span>
                    </div>

                    {session.timeline.length === 0 ? (
                      <p className="py-4 text-app-text-muted">{t('adminSessions.noTimeline')}</p>
                    ) : (
                      <ol className="list-decimal space-y-3 pl-7 marker:font-semibold marker:text-app-text-muted">
                        {session.timeline.map((event, index) => {
                          const isQuestion = event.event_type === 'question';
                          const answer = isQuestion ? getAnswerLabel(event, (key) => t(key)) : null;
                          const questionText = event.original_question || event.question || '';
                          const eventTime = formatTime(event.timestamp, locale);
                          const sourceLabel = event.source === 'local_kb'
                            ? t('adminSessions.sourceLocalKb')
                            : event.source === 'fallback'
                              ? t('adminSessions.sourceFallback')
                              : event.source === 'invalid'
                                ? t('adminSessions.sourceInvalid')
                                : event.source;

                          return (
                            <li key={`${event.id}-${index}`} className="min-w-0 rounded-md border border-app-border bg-app-surface p-4">
                              <div className="flex min-w-0 flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                                <div className="min-w-0 space-y-2">
                                  <div className="flex flex-wrap items-center gap-2">
                                    <span className={badgeClass}>
                                      {t(isQuestion ? 'adminSessions.questionType' : 'adminSessions.guessType')}
                                    </span>
                                    {isQuestion && answer && (
                                      <span className={answer.className}>{answer.label}</span>
                                    )}
                                    {isQuestion && sourceLabel && (
                                      <span className={badgeClass}>
                                        {sourceLabel}
                                        {event.source === 'local_kb' && event.relation ? ` (${event.relation})` : ''}
                                      </span>
                                    )}
                                    {!isQuestion && (
                                      <span className={event.correct ? successBadgeClass : errorBadgeClass}>
                                        {event.correct
                                          ? t('adminSessions.targetFound')
                                          : t('adminSessions.incorrectGuess')}
                                      </span>
                                    )}
                                  </div>

                                  {isQuestion ? (
                                    <p className={questionClass}>{questionText}</p>
                                  ) : (
                                    <p className={questionClass}>{event.guess || ''}</p>
                                  )}
                                </div>

                                <div className="flex shrink-0 flex-wrap items-center gap-2">
                                  {event.timestamp && (
                                    <time className={metaClass} dateTime={event.timestamp}>{eventTime}</time>
                                  )}
                                  {isQuestion && onTestInQA && (
                                    <button
                                      type="button"
                                      className={buttonClass}
                                      aria-label={t('adminSessions.testQuestionInQA', { question: questionText })}
                                      onClick={() => onTestInQA({
                                        mode: session.mode,
                                        targetName: session.target_name,
                                        questionText,
                                      })}
                                    >
                                      <Sparkles className="h-4 w-4" aria-hidden="true" />
                                      {t('adminSessions.testInQA')}
                                    </button>
                                  )}
                                </div>
                              </div>

                              {isQuestion && event.clarification && (
                                <p className="mt-3 border-l-2 border-emerald-300 pl-3 text-xs font-medium text-emerald-800">
                                  <span className="font-semibold text-emerald-900">{t('adminSessions.clarification')}: </span>
                                  {event.clarification}
                                </p>
                              )}
                              {isQuestion && event.explanation && (
                                <p className="mt-2 border-l-2 border-app-border pl-3 text-sm text-app-text-secondary">
                                  <span className="font-semibold">{t('adminSessions.explanation')}: </span>
                                  {event.explanation}
                                </p>
                              )}
                              {event.context && (
                                <details className="mt-2">
                                  <summary className="min-h-11 cursor-pointer py-2 text-sm font-medium text-app-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus">{t('adminSessions.rawContext')}</summary>
                                  <pre className={diagnosticsClass} tabIndex={0} aria-label={t('adminSessions.rawContext')}>
                                    {event.context}
                                  </pre>
                                </details>
                              )}
                            </li>
                          );
                        })}
                      </ol>
                    )}
                    </>}
                  </div>
                </article>
              );
            })}
          </div>
        )}

        {!sessionsLoading && !sessionsError && sessions?.items.length === 0 && (
          <p className="rounded-md border border-dashed border-app-border p-6 text-center text-app-text-muted">
            {t('adminSessions.noSessions')}
          </p>
        )}

        {sessions && (
          <div className={`${pagerClass} border-t border-app-border pt-4`}>
            <span className={metaClass}>
              {t('adminCommon.page', {
                page: formatNumber(page, locale),
                pages: formatNumber(totalPages, locale),
                count: sessions.total,
              })}
            </span>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                className={buttonClass}
                disabled={page <= 1 || sessionsLoading}
                onClick={() => setPage((current) => Math.max(1, current - 1))}
              >
                {t('adminCommon.previous')}
              </button>
              <button
                type="button"
                className={buttonClass}
                disabled={page >= totalPages || sessionsLoading}
                onClick={() => setPage((current) => Math.min(totalPages, current + 1))}
              >
                {t('adminCommon.next')}
              </button>
            </div>
          </div>
        )}
      </section>

      {!isQuizMode(selectedMode) && <details className={panelClass}>
        <summary className="flex min-h-11 list-none cursor-pointer items-center justify-between gap-3 py-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus">
          <span className="flex items-center gap-2">
            <TrendingUp className="h-5 w-5 text-app-text-muted" aria-hidden="true" />
            <span className="text-lg font-semibold">{t('adminSessions.strategyInsights')}</span>
          </span>
          <ChevronDown className="h-4 w-4 text-app-text-muted" aria-hidden="true" />
        </summary>

        {stats && (
          <div className="mt-4 grid min-w-0 gap-4 xl:grid-cols-2">
            {!isSymbolMode(selectedMode) && selectedMode !== 'flagdle' && <section className="min-w-0 rounded-md border border-app-border bg-app-surface-muted p-4" aria-labelledby={`${idPrefix}-top-questions`}>
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                <h3 id={`${idPrefix}-top-questions`} className="flex items-center gap-2 text-base font-semibold text-app-text">
                  <HelpCircle className="h-4 w-4 text-app-text-muted" aria-hidden="true" />
                  {t('adminSessions.topQuestions')}
                </h3>
                <span className={metaClass}>{t('adminSessions.topQuestionsContext')}</span>
              </div>

              {stats.top_questions.length > 0 ? (
                <ol className="list-decimal space-y-2 pl-7 marker:text-app-text-muted">
                  {stats.top_questions.slice(0, 6).map((question, index) => (
                    <li key={`${question.text}-${index}`} className="min-w-0 rounded-md border border-app-border bg-app-surface p-3">
                      <div className="flex min-w-0 flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                        <div className="min-w-0">
                          <p className="break-words text-app-text">“{question.text}”</p>
                          <div className={`${metaClass} mt-2 flex flex-wrap gap-x-4 gap-y-1`}>
                            <span>{t('adminSessions.askedCount', { count: question.count })}</span>
                            <span>{t('adminSessions.yesPercentage', { percent: formatPercent(question.yes_pct, locale) })}</span>
                            <span>{t('adminSessions.winCorrelation', { percent: formatPercent(question.win_correlation, locale) })}</span>
                          </div>
                        </div>
                        {onTestInQA && (
                          <button
                            type="button"
                            className={`${buttonClass} shrink-0`}
                            aria-label={t('adminSessions.testQuestionInQA', { question: question.text })}
                            onClick={() => onTestInQA({
                              mode: selectedMode,
                              targetName: stats.target_name,
                              questionText: question.text,
                            })}
                          >
                            <Sparkles className="h-4 w-4" aria-hidden="true" />
                            {t('adminSessions.testInQA')}
                          </button>
                        )}
                      </div>
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="py-6 text-center text-app-text-muted">{t('adminSessions.noQuestions')}</p>
              )}
            </section>}

            <section className="min-w-0 rounded-md border border-app-border bg-app-surface-muted p-4" aria-labelledby={`${idPrefix}-top-guesses`}>
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                <h3 id={`${idPrefix}-top-guesses`} className="flex items-center gap-2 text-base font-semibold text-app-text">
                  <TrendingUp className="h-4 w-4 text-app-text-muted" aria-hidden="true" />
                  {t('adminSessions.topGuesses')}
                </h3>
                <span className={metaClass}>{t('adminSessions.topGuessesContext')}</span>
              </div>

              {stats.top_guesses.length > 0 ? (
                <ol className="list-decimal space-y-2 pl-7 marker:text-app-text-muted">
                  {stats.top_guesses.slice(0, 6).map((guess, index) => (
                    <li key={`${guess.guess}-${index}`} className="min-w-0 rounded-md border border-app-border bg-app-surface p-3">
                      <div className="flex min-w-0 flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                        <div className="min-w-0">
                          <p className="break-words font-medium text-app-text">{guess.guess}</p>
                          <p className={`${metaClass} mt-1`}>
                            {t('adminSessions.guessCount', { count: guess.count })}
                            {' · '}
                            {t('adminSessions.correctPercentage', { percent: formatPercent(guess.correct_pct, locale) })}
                          </p>
                        </div>
                        <span className={`${
                          guess.correct_pct > 0 ? successBadgeClass : badgeClass
                        } shrink-0`}>
                          {guess.correct_pct > 0
                            ? t('adminSessions.targetGuess')
                            : t('adminSessions.mistakenGuess')}
                        </span>
                      </div>
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="py-6 text-center text-app-text-muted">{t('adminSessions.noGuesses')}</p>
              )}
            </section>
          </div>
        )}

        {!stats && statsLoading && (
          <p className="mt-4 flex items-center gap-2 text-app-text" role="status">
            <Loader2 className="h-4 w-4 animate-spin text-app-accent" aria-hidden="true" />
            {t('adminSessions.loadingInsights')}
          </p>
        )}
        {!stats && statsError && (
          <p className="mt-4 text-app-text-muted">{t('adminSessions.insightsUnavailable')}</p>
        )}
      </details>}
    </div>
  );
};

export default AdminSessionsTab;
