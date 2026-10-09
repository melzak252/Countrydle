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
}

const MODES = ['countrydle', 'powiatdle', 'us_statedle', 'wojewodztwodle', 'continental'] as const;
const PAGE_SIZE = 20;

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
    return { label: t('adminSessions.invalid'), className: 'admin-answer-invalid' };
  }
  if (event.answer === true) {
    return { label: t('adminSessions.yes'), className: 'admin-answer-yes' };
  }
  if (event.answer === false) {
    return { label: t('adminSessions.no'), className: '' };
  }
  return { label: t('adminSessions.noAnswer'), className: '' };
}

export const AdminSessionsTab: React.FC<AdminSessionsTabProps> = ({ onTestInQA }) => {
  const { t, i18n } = useTranslation();
  const locale = i18n.language.startsWith('pl') ? 'pl-PL' : 'en-US';
  const idPrefix = useId().replace(/:/g, '');
  const [selectedMode, setSelectedMode] = useState<string>('countrydle');
  const [selectedDate, setSelectedDate] = useState<string>(() => new Date().toISOString().slice(0, 10));
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
    date.setDate(date.getDate() - offsetDays);
    setSelectedDate(date.toISOString().slice(0, 10));
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
    <div className="space-y-4">
      <div className="admin-toolbar" role="group" aria-label={t('adminSessions.filters')}>
        <label className="admin-field w-full min-w-0 sm:min-w-[180px] sm:flex-1">
          <span>{t('adminSessions.mode')}</span>
          <select
            className="admin-control"
            value={selectedMode}
            onChange={(event) => {
              setSelectedMode(event.target.value);
              setPage(1);
            }}
          >
            {MODES.map((mode) => (
              <option key={mode} value={mode}>{t(`adminSessions.modes.${mode}`)}</option>
            ))}
          </select>
        </label>

        <div className="admin-field w-full min-w-0 sm:min-w-[250px] sm:flex-[2]">
          <span>{t('adminSessions.date')}</span>
          <div className="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap sm:items-center">
            <button type="button" className="admin-button" onClick={() => handleDatePreset(0)}>
              {t('adminSessions.today')}
            </button>
            <button type="button" className="admin-button" onClick={() => handleDatePreset(1)}>
              {t('adminSessions.yesterday')}
            </button>
            <label className="col-span-2 flex min-w-0 items-center gap-2 sm:min-w-[180px] sm:flex-1">
              <Calendar className="h-4 w-4 shrink-0 text-slate-400" aria-hidden="true" />
              <span className="sr-only">{t('adminSessions.date')}</span>
              <input
                className="admin-control min-w-0 flex-1"
                type="date"
                value={selectedDate}
                onChange={(event) => {
                  setSelectedDate(event.target.value);
                  setPage(1);
                }}
              />
            </label>
          </div>
        </div>

        <button
          type="button"
          className="admin-button w-full sm:w-auto"
          onClick={refreshAll}
          disabled={sessionsLoading || statsLoading}
        >
          <RefreshCw className="h-4 w-4" aria-hidden="true" />
          {t('adminCommon.refresh')}
        </button>
      </div>

      <section className="admin-panel space-y-4" aria-label={t('adminSessions.targetSummary')}>
        <div className="grid min-w-0 gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,2fr)] xl:items-center">
          <div className="min-w-0">
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <span className="admin-badge">{t('adminSessions.targetEntity')}</span>
              {stats?.target_subtitle && <span className="admin-badge">{stats.target_subtitle}</span>}
            </div>
            {stats ? (
              <>
                <h2 className="flex min-w-0 items-center gap-2 break-words text-sand-100">
                  <Target className="h-6 w-6 shrink-0 text-slate-300" aria-hidden="true" />
                  {stats.target_name}
                </h2>
                <p className="admin-meta mt-1">
                  {t('adminSessions.challengeDate', {
                    date: formatGameDate(stats.game_date || selectedDate, locale),
                  })}
                </p>
              </>
            ) : (
              <p className="text-base font-semibold text-sand-100" role={statsError ? undefined : 'status'}>
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
              {
                label: t('adminSessions.avgQuestionsWon'),
                value: stats ? formatNumber(stats.avg_questions_winners, locale, 1) : '—',
              },
              {
                label: t('adminSessions.avgQuestionsLost'),
                value: stats ? formatNumber(stats.avg_questions_losers, locale, 1) : '—',
              },
            ].map((metric) => (
              <div key={metric.label} className="min-w-0 rounded-md border border-white/10 bg-obsidian-950 p-3">
                <div className="admin-meta">{metric.label}</div>
                <div className="admin-metric mt-1 text-sand-100">{metric.value}</div>
              </div>
            ))}
          </div>
        </div>

        {statsLoading && stats && (
          <p className="admin-meta" role="status">{t('adminCommon.updating')}</p>
        )}
        {statsError && (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-rose-400/40 p-3" role="alert">
            <span>
              {t('adminSessions.statsError')}
              {stats && ` ${t('adminSessions.staleData')}`}
            </span>
            <button
              type="button"
              className="admin-button"
              onClick={() => setStatsRetry((value) => value + 1)}
              disabled={statsLoading}
            >
              {t('adminCommon.retry')}
            </button>
          </div>
        )}
      </section>

      <section className="admin-panel space-y-4" aria-labelledby={`${idPrefix}-sessions-heading`}>
        <div className="flex flex-col gap-4 border-b border-white/10 pb-4 xl:flex-row xl:items-end xl:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h2 id={`${idPrefix}-sessions-heading`}>{t('adminSessions.sessionsTitle')}</h2>
              {sessions && (
                <span className="admin-badge">
                  {t('adminSessions.sessionCount', { count: sessions.total })}
                </span>
              )}
            </div>
          </div>

          <div className="grid min-w-0 gap-3 sm:grid-cols-2 xl:w-[min(100%,32rem)]">
            <label className="admin-field min-w-0">
              <span>{t('adminSessions.statusFilter')}</span>
              <select
                className="admin-control"
                value={statusFilter}
                onChange={(event) => {
                  setStatusFilter(event.target.value);
                  setPage(1);
                }}
              >
                <option value="all">{t('adminSessions.statusAll')}</option>
                <option value="won">{t('adminSessions.statusWon')}</option>
                <option value="lost">{t('adminSessions.statusLost')}</option>
                <option value="in_progress">{t('adminSessions.statusInProgress')}</option>
              </select>
            </label>
            <label className="admin-field min-w-0">
              <span>{t('adminSessions.playerTypeFilter')}</span>
              <select
                className="admin-control"
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
          <p className="flex items-center gap-2 text-sand-100" role="status">
            <Loader2 className="h-4 w-4 animate-spin text-slate-300" aria-hidden="true" />
            {sessions ? t('adminCommon.updating') : t('adminSessions.sessionsLoading')}
          </p>
        )}
        {sessionsError && (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-rose-400/40 p-3" role="alert">
            <span>
              {t('adminSessions.sessionsError')}
              {sessions && ` ${t('adminSessions.staleData')}`}
            </span>
            <button
              type="button"
              className="admin-button"
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
              const statusLabel = t(`adminSessions.status.${session.status}`);
              const started = formatDateTime(session.started_at, locale);
              const duration = formatDuration(session.duration_seconds, locale, t);
              const accessibleName = t('adminSessions.sessionSummary', {
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
                <article key={session.session_id} className="overflow-hidden rounded-md border border-white/10 bg-obsidian-950">
                  <button
                    id={buttonId}
                    type="button"
                    className="admin-row-button flex w-full items-center justify-between gap-3 p-4 text-left hover:bg-white/5"
                    aria-expanded={isExpanded}
                    aria-controls={panelId}
                    aria-label={accessibleName}
                    onClick={() => toggleSession(session.session_id)}
                  >
                    <span className="flex min-w-0 items-start gap-3">
                      <span className="mt-1 rounded-md border border-white/10 bg-obsidian-900 p-2 text-slate-300" aria-hidden="true">
                        {session.is_guest ? <UserX className="h-4 w-4" /> : <UserIcon className="h-4 w-4" />}
                      </span>
                      <span className="min-w-0">
                        <span className="flex flex-wrap items-center gap-2">
                          <span className="max-w-full break-words text-base font-semibold text-sand-100" title={session.username}>
                            {session.username}
                          </span>
                          {session.is_guest && <span className="admin-badge">{t('adminSessions.guest')}</span>}
                          <span
                            className={`admin-badge ${
                              session.status === 'won'
                                ? 'border-emerald-400 text-emerald-200'
                                : session.status === 'lost'
                                  ? 'border-rose-400 text-rose-200'
                                  : ''
                            }`}
                          >
                            {statusLabel}
                          </span>
                        </span>
                        <span className="admin-meta mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
                          <span>{t('adminSessions.startedAt', { time: started || t('adminSessions.unknownTime') })}</span>
                          <span>{t('adminSessions.questionCount', { count: session.questions_asked })}</span>
                          <span>{t('adminSessions.guessCount', { count: session.guesses_made })}</span>
                          {session.duration_seconds != null && (
                            <span className="inline-flex items-center gap-1">
                              <Clock className="h-3.5 w-3.5" aria-hidden="true" />
                              {t('adminSessions.durationLabel', { duration })}
                            </span>
                          )}
                        </span>
                      </span>
                    </span>
                    <span className="flex shrink-0 items-center gap-2 text-sand-100">
                      <span>{isExpanded ? t('adminSessions.hideReplay') : t('adminSessions.showReplay')}</span>
                      {isExpanded
                        ? <ChevronDown className="h-4 w-4" aria-hidden="true" />
                        : <ChevronRight className="h-4 w-4" aria-hidden="true" />}
                    </span>
                  </button>

                  <div
                    id={panelId}
                    aria-labelledby={buttonId}
                    hidden={!isExpanded}
                    className="space-y-4 border-t border-white/10 bg-obsidian-900 p-4"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/10 pb-3">
                      <h3>{t('adminSessions.timelineTitle', { count: session.timeline.length })}</h3>
                      <span className="admin-meta">{t('adminSessions.timelineOrder')}</span>
                    </div>

                    {session.timeline.length === 0 ? (
                      <p className="admin-muted py-4">{t('adminSessions.noTimeline')}</p>
                    ) : (
                      <ol className="list-decimal space-y-3 pl-7 marker:font-semibold marker:text-slate-400">
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
                            <li key={`${event.id}-${index}`} className="min-w-0 rounded-md border border-white/10 bg-obsidian-950 p-4">
                              <div className="flex min-w-0 flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                                <div className="min-w-0 space-y-2">
                                  <div className="flex flex-wrap items-center gap-2">
                                    <span className="admin-badge">
                                      {t(isQuestion ? 'adminSessions.questionType' : 'adminSessions.guessType')}
                                    </span>
                                    {isQuestion && answer && (
                                      <span className={`admin-badge ${answer.className}`}>{answer.label}</span>
                                    )}
                                    {isQuestion && sourceLabel && (
                                      <span className="admin-badge">
                                        {sourceLabel}
                                        {event.source === 'local_kb' && event.relation ? ` (${event.relation})` : ''}
                                      </span>
                                    )}
                                    {!isQuestion && (
                                      <span className={`admin-badge ${
                                        event.correct ? 'border-emerald-400 text-emerald-200' : 'border-rose-400 text-rose-200'
                                      }`}>
                                        {event.correct
                                          ? t('adminSessions.targetFound')
                                          : t('adminSessions.incorrectGuess')}
                                      </span>
                                    )}
                                  </div>

                                  {isQuestion ? (
                                    <p className="admin-question break-words text-sand-100">{questionText}</p>
                                  ) : (
                                    <p className="admin-question break-words text-sand-100">{event.guess || ''}</p>
                                  )}
                                </div>

                                <div className="flex shrink-0 flex-wrap items-center gap-2">
                                  {event.timestamp && (
                                    <time className="admin-meta" dateTime={event.timestamp}>{eventTime}</time>
                                  )}
                                  {isQuestion && onTestInQA && (
                                    <button
                                      type="button"
                                      className="admin-button"
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

                              {isQuestion && event.explanation && (
                                <p className="admin-muted mt-3 border-l-2 border-slate-500 pl-3">
                                  <span className="font-semibold">{t('adminSessions.explanation')}: </span>
                                  {event.explanation}
                                </p>
                              )}
                              {event.context && (
                                <details className="mt-2">
                                  <summary>{t('adminSessions.rawContext')}</summary>
                                  <pre className="admin-diagnostics" tabIndex={0} aria-label={t('adminSessions.rawContext')}>
                                    {event.context}
                                  </pre>
                                </details>
                              )}
                            </li>
                          );
                        })}
                      </ol>
                    )}
                  </div>
                </article>
              );
            })}
          </div>
        )}

        {!sessionsLoading && !sessionsError && sessions?.items.length === 0 && (
          <p className="admin-muted rounded-md border border-dashed border-white/20 p-6 text-center">
            {t('adminSessions.noSessions')}
          </p>
        )}

        {sessions && (
          <div className="admin-pager border-t border-white/10 pt-4">
            <span className="admin-meta">
              {t('adminCommon.page', {
                page: formatNumber(page, locale),
                pages: formatNumber(totalPages, locale),
                count: sessions.total,
              })}
            </span>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                className="admin-button"
                disabled={page <= 1 || sessionsLoading}
                onClick={() => setPage((current) => Math.max(1, current - 1))}
              >
                {t('adminCommon.previous')}
              </button>
              <button
                type="button"
                className="admin-button"
                disabled={page >= totalPages || sessionsLoading}
                onClick={() => setPage((current) => Math.min(totalPages, current + 1))}
              >
                {t('adminCommon.next')}
              </button>
            </div>
          </div>
        )}
      </section>

      <details className="admin-panel">
        <summary className="flex list-none items-center justify-between gap-3">
          <span className="flex items-center gap-2">
            <TrendingUp className="h-5 w-5 text-slate-300" aria-hidden="true" />
            <span className="text-lg font-semibold">{t('adminSessions.strategyInsights')}</span>
          </span>
          <ChevronDown className="h-4 w-4 text-slate-300" aria-hidden="true" />
        </summary>

        {stats && (
          <div className="mt-4 grid min-w-0 gap-4 xl:grid-cols-2">
            <section className="min-w-0 rounded-md border border-white/10 bg-obsidian-950 p-4" aria-labelledby={`${idPrefix}-top-questions`}>
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                <h3 id={`${idPrefix}-top-questions`} className="flex items-center gap-2">
                  <HelpCircle className="h-4 w-4 text-slate-300" aria-hidden="true" />
                  {t('adminSessions.topQuestions')}
                </h3>
                <span className="admin-meta">{t('adminSessions.topQuestionsContext')}</span>
              </div>

              {stats.top_questions.length > 0 ? (
                <ol className="list-decimal space-y-2 pl-7 marker:text-slate-400">
                  {stats.top_questions.slice(0, 6).map((question, index) => (
                    <li key={`${question.text}-${index}`} className="min-w-0 rounded-md border border-white/10 bg-obsidian-900 p-3">
                      <div className="flex min-w-0 flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                        <div className="min-w-0">
                          <p className="break-words text-sand-100">“{question.text}”</p>
                          <div className="admin-meta mt-2 flex flex-wrap gap-x-4 gap-y-1">
                            <span>{t('adminSessions.askedCount', { count: question.count })}</span>
                            <span>{t('adminSessions.yesPercentage', { percent: formatPercent(question.yes_pct, locale) })}</span>
                            <span>{t('adminSessions.winCorrelation', { percent: formatPercent(question.win_correlation, locale) })}</span>
                          </div>
                        </div>
                        {onTestInQA && (
                          <button
                            type="button"
                            className="admin-button shrink-0"
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
                <p className="admin-muted py-6 text-center">{t('adminSessions.noQuestions')}</p>
              )}
            </section>

            <section className="min-w-0 rounded-md border border-white/10 bg-obsidian-950 p-4" aria-labelledby={`${idPrefix}-top-guesses`}>
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                <h3 id={`${idPrefix}-top-guesses`} className="flex items-center gap-2">
                  <TrendingUp className="h-4 w-4 text-slate-300" aria-hidden="true" />
                  {t('adminSessions.topGuesses')}
                </h3>
                <span className="admin-meta">{t('adminSessions.topGuessesContext')}</span>
              </div>

              {stats.top_guesses.length > 0 ? (
                <ol className="list-decimal space-y-2 pl-7 marker:text-slate-400">
                  {stats.top_guesses.slice(0, 6).map((guess, index) => (
                    <li key={`${guess.guess}-${index}`} className="min-w-0 rounded-md border border-white/10 bg-obsidian-900 p-3">
                      <div className="flex min-w-0 flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                        <div className="min-w-0">
                          <p className="break-words font-medium text-sand-100">{guess.guess}</p>
                          <p className="admin-meta mt-1">
                            {t('adminSessions.guessCount', { count: guess.count })}
                            {' · '}
                            {t('adminSessions.correctPercentage', { percent: formatPercent(guess.correct_pct, locale) })}
                          </p>
                        </div>
                        <span className={`admin-badge shrink-0 ${
                          guess.correct_pct > 0 ? 'border-emerald-400 text-emerald-200' : ''
                        }`}>
                          {guess.correct_pct > 0
                            ? t('adminSessions.targetGuess')
                            : t('adminSessions.mistakenGuess')}
                        </span>
                      </div>
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="admin-muted py-6 text-center">{t('adminSessions.noGuesses')}</p>
              )}
            </section>
          </div>
        )}

        {!stats && statsLoading && (
          <p className="mt-4 flex items-center gap-2 text-sand-100" role="status">
            <Loader2 className="h-4 w-4 animate-spin text-slate-300" aria-hidden="true" />
            {t('adminSessions.loadingInsights')}
          </p>
        )}
        {!stats && statsError && (
          <p className="admin-muted mt-4">{t('adminSessions.insightsUnavailable')}</p>
        )}
      </details>
    </div>
  );
};

export default AdminSessionsTab;
