import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Clock, HelpCircle, RefreshCw, Sparkles, Target } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { LiveFeedData, LiveQuestionItem } from '../../types';

interface AdminLiveFeedTabProps {
  data: LiveFeedData;
  isLoading: boolean;
  error: string | null;
  hasLoaded: boolean;
  lastUpdatedAt: string | null;
  onRefresh: (mode?: string) => Promise<void>;
  onTestInQA?: (target: { mode: string; targetName?: string; questionText?: string }) => void;
}

const MODES = [
  { id: 'all', labelKey: 'modes.all' },
  { id: 'countrydle', labelKey: 'modes.countries' },
  { id: 'powiatdle', labelKey: 'modes.powiaty' },
  { id: 'us_statedle', labelKey: 'modes.usStates' },
  { id: 'wojewodztwodle', labelKey: 'modes.voivodeships' },
  { id: 'continental', labelKey: 'modes.continental' },
];

const AUTO_REFRESH_INTERVALS = [
  { seconds: 0, labelKey: 'autoRefresh.paused' },
  { seconds: 10, labelKey: 'autoRefresh.seconds', count: 10 },
  { seconds: 30, labelKey: 'autoRefresh.seconds', count: 30 },
];

const EMPTY_FEED: LiveFeedData = { recent_questions: [], recent_guesses: [] };
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


function formatTimestamp(timestamp: string | null, locale: string): string | null {
  if (!timestamp) return null;
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return timestamp;
  return new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'medium' }).format(date);
}

function getQuestionAnswer(question: LiveQuestionItem, t: (key: string) => string) {
  if (!question.valid) {
    return { label: t('adminLiveFeed.answers.invalid'), className: warningBadgeClass };
  }
  if (question.answer === true) {
    return { label: t('adminLiveFeed.answers.yes'), className: successBadgeClass };
  }
  if (question.answer === false) {
    return { label: t('adminLiveFeed.answers.no'), className: badgeClass };
  }
  return { label: t('adminLiveFeed.answers.noAnswer'), className: badgeClass };
}

export const AdminLiveFeedTab: React.FC<AdminLiveFeedTabProps> = ({
  data,
  isLoading,
  error,
  hasLoaded,
  lastUpdatedAt,
  onRefresh,
  onTestInQA,
}) => {
  const { t } = useTranslation();
  const [selectedMode, setSelectedMode] = useState('all');
  const [autoRefreshSecs, setAutoRefreshSecs] = useState(10);
  const [modeSnapshotReady, setModeSnapshotReady] = useState(false);
  const [requestRevision, setRequestRevision] = useState(0);
  const pendingRequests = useRef(0);
  const isLoadingRef = useRef(isLoading);
  const mounted = useRef(false);
  isLoadingRef.current = isLoading;

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const requestFeed = useCallback(async (mode?: string) => {
    pendingRequests.current += 1;
    try {
      await onRefresh(mode);
    } finally {
      pendingRequests.current -= 1;
      if (mounted.current) setRequestRevision((revision) => revision + 1);
    }
  }, [onRefresh]);

  useEffect(() => {
    void requestFeed(selectedMode === 'all' ? undefined : selectedMode).catch(() => undefined);
  }, [requestFeed, selectedMode]);

  useEffect(() => {
    if (autoRefreshSecs === 0 || isLoading || pendingRequests.current > 0) return;
    let active = true;
    const timeout = window.setTimeout(() => {
      if (!active || isLoadingRef.current || pendingRequests.current > 0) return;
      void requestFeed(selectedMode === 'all' ? undefined : selectedMode).catch(() => undefined);
    }, autoRefreshSecs * 1000);
    return () => {
      active = false;
      window.clearTimeout(timeout);
    };
  }, [autoRefreshSecs, isLoading, requestFeed, requestRevision, selectedMode]);

  useEffect(() => {
    if (hasLoaded && !error) setModeSnapshotReady(true);
  }, [error, hasLoaded]);

  const handleModeChange = (mode: string) => {
    if (mode !== selectedMode) setModeSnapshotReady(false);
    setSelectedMode(mode);
  };
  const hasCurrentSnapshot = hasLoaded && modeSnapshotReady;
  const visibleData = hasCurrentSnapshot ? data : EMPTY_FEED;
  const dateLocale = 'en-US';
  const lastUpdated = formatTimestamp(lastUpdatedAt, dateLocale);

  const renderQuestion = (question: LiveQuestionItem) => {
    const result = getQuestionAnswer(question, t);
    const sourceLabel = question.source === 'local_kb'
      ? t('adminLiveFeed.sources.localKb')
      : question.source === 'fallback'
        ? t('adminLiveFeed.sources.aiFallback')
        : question.source;

    return (
      <article key={`${question.mode}:${question.id}`} className="space-y-3 rounded-md border border-app-border bg-app-surface-muted p-3">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            <span className="break-words font-semibold text-app-text">{question.username}</span>
            <span className={`${badgeClass} font-mono`}>{question.mode}</span>
          </div>
          {question.asked_at && (
            <time className={`${metaClass} shrink-0`} dateTime={question.asked_at}>
              {formatTimestamp(question.asked_at, dateLocale)}
            </time>
          )}
        </div>

        {question.target_name && (
          <p className={`${metaClass} break-words`}>
            {t('adminLiveFeed.target')}: <span className="text-app-text">{question.target_name}</span>
            {question.target_subtitle && <span> ({question.target_subtitle})</span>}
          </p>
        )}

        <p className={questionClass}>“{question.question}”</p>

        <div className="flex flex-wrap items-center gap-2 border-t border-app-border pt-3">
          <span className={result.className}>{result.label}</span>
          {sourceLabel && <span className={badgeClass}>{sourceLabel}</span>}
          {onTestInQA && (
            <button
              type="button"
              onClick={() => onTestInQA({
                mode: question.mode,
                targetName: question.target_name || undefined,
                questionText: question.question,
              })}
              className={`${buttonClass} ml-auto`}
            >
              <Sparkles size={16} aria-hidden="true" />
              {t('adminLiveFeed.testInQa')}
            </button>
          )}
        </div>

        {question.clarification && (
          <div className="border-t border-app-border pt-2 text-xs">
            <span className="font-semibold text-emerald-900">{t('adminLiveFeed.clarification')}: </span>
            <span className="font-medium text-emerald-800">{question.clarification}</span>
          </div>
        )}

        {question.explanation && (
          <details className="border-t border-app-border pt-2">
            <summary className="min-h-11 cursor-pointer py-2 text-sm font-medium text-app-text focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus">{t('adminLiveFeed.explanation')}</summary>
            <p className="break-words pb-2 text-sm text-app-text-muted">{question.explanation}</p>
          </details>
        )}
      </article>
    );
  };

  return (
    <section className="space-y-4 text-app-text">
      <div className={toolbarClass} role="group" aria-label={t('adminLiveFeed.controls')}>
        <div className="grid w-full grid-cols-1 gap-4 sm:grid-cols-2 xl:flex-1">
          <div className={fieldClass}>
            <label htmlFor="admin-live-feed-mode">{t('adminLiveFeed.mode')}</label>
            <select
              id="admin-live-feed-mode"
              className={controlClass}
              value={selectedMode}
              onChange={(event) => handleModeChange(event.target.value)}
            >
              {MODES.map((mode) => (
                <option key={mode.id} value={mode.id}>{t(`adminLiveFeed.${mode.labelKey}`)}</option>
              ))}
            </select>
          </div>

          <div className={fieldClass}>
            <label htmlFor="admin-live-feed-auto-refresh">{t('adminLiveFeed.autoRefresh.label')}</label>
            <select
              id="admin-live-feed-auto-refresh"
              className={controlClass}
              value={autoRefreshSecs}
              onChange={(event) => setAutoRefreshSecs(Number(event.target.value))}
            >
              {AUTO_REFRESH_INTERVALS.map((option) => (
                <option key={option.seconds} value={option.seconds}>
                  {option.count
                    ? t(`adminLiveFeed.${option.labelKey}`, { count: option.count })
                    : t(`adminLiveFeed.${option.labelKey}`)}
                </option>
              ))}
            </select>
          </div>
        </div>
        <div className="flex min-w-0 flex-wrap items-center gap-3">
          <p className={`${metaClass} flex items-center gap-2`} role="status">
            <Clock size={16} aria-hidden="true" />
            {lastUpdated && lastUpdatedAt
              ? <time dateTime={lastUpdatedAt}>{t('adminLiveFeed.lastUpdated', { time: lastUpdated })}</time>
              : t('adminLiveFeed.notUpdated')}
          </p>
          <button
            type="button"
            onClick={() => { void requestFeed(selectedMode === 'all' ? undefined : selectedMode).catch(() => undefined); }}
            disabled={isLoading}
            className={buttonClass}
          >
            <RefreshCw size={16} className={isLoading ? 'animate-spin' : ''} aria-hidden="true" />
            {t('adminLiveFeed.refresh')}
          </button>
        </div>
      </div>

      {isLoading && !hasCurrentSnapshot && (
        <p role="status" className={`${panelClass} text-app-text-muted`}>{t('adminLiveFeed.loading')}</p>
      )}

      {error && (
        <div role="alert" className="min-w-0 rounded-md border border-rose-300 bg-rose-50 p-4 text-rose-800">
          <p>{t('adminLiveFeed.requestFailed')}</p>
          <p className="mt-2 break-words text-sm">{t(error)}</p>
          {hasCurrentSnapshot && (
            <p className={`${metaClass} mt-2`}>{t('adminLiveFeed.staleSnapshot')}</p>
          )}
          <button
            type="button"
            onClick={() => { void requestFeed(selectedMode === 'all' ? undefined : selectedMode).catch(() => undefined); }}
            disabled={isLoading}
            className={`${buttonClass} mt-3`}
          >
            <RefreshCw size={16} aria-hidden="true" />
            {t('adminLiveFeed.retry')}
          </button>
        </div>
      )}

      {isLoading && hasCurrentSnapshot && (
        <p role="status" className={metaClass}>{t('adminLiveFeed.updating')}</p>
      )}

      {hasCurrentSnapshot && (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          <section className={`${panelClass} space-y-4`} aria-labelledby="admin-live-feed-questions-heading">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-app-border pb-3">
              <h2 id="admin-live-feed-questions-heading" className="flex items-center gap-2 text-lg font-semibold text-app-text">
                <HelpCircle size={18} aria-hidden="true" />
                {t('adminLiveFeed.questionsHeading')}
              </h2>
              <span className={metaClass}>
                {t('adminLiveFeed.eventCount', { count: visibleData.recent_questions.length })}
              </span>
            </div>
            {visibleData.recent_questions.length === 0 ? (
              !error && <p className="py-4 text-app-text-muted">{t('adminLiveFeed.noQuestions')}</p>
            ) : (
              <div role="region" aria-labelledby="admin-live-feed-questions-heading" tabIndex={0} className="space-y-3 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus xl:max-h-[700px] xl:overflow-y-auto xl:pr-1">
                {visibleData.recent_questions.map(renderQuestion)}
              </div>
            )}
          </section>

          <section className={`${panelClass} space-y-4`} aria-labelledby="admin-live-feed-guesses-heading">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-app-border pb-3">
              <h2 id="admin-live-feed-guesses-heading" className="flex items-center gap-2 text-lg font-semibold text-app-text">
                <Target size={18} aria-hidden="true" />
                {t('adminLiveFeed.guessesHeading')}
              </h2>
              <span className={metaClass}>
                {t('adminLiveFeed.eventCount', { count: visibleData.recent_guesses.length })}
              </span>
            </div>
            {visibleData.recent_guesses.length === 0 ? (
              !error && <p className="py-4 text-app-text-muted">{t('adminLiveFeed.noGuesses')}</p>
            ) : (
              <div role="region" aria-labelledby="admin-live-feed-guesses-heading" tabIndex={0} className="space-y-3 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus xl:max-h-[700px] xl:overflow-y-auto xl:pr-1">
                {visibleData.recent_guesses.map((guess) => (
                  <article
                    key={`${guess.mode}:${guess.id}`}
                    className="space-y-3 rounded-md border border-app-border bg-app-surface-muted p-3"
                  >
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div className="flex min-w-0 flex-wrap items-center gap-2">
                        <span className="break-words font-semibold text-app-text">{guess.username}</span>
                        <span className={`${badgeClass} font-mono`}>{guess.mode}</span>
                      </div>
                      {guess.guessed_at && (
                        <time className={`${metaClass} shrink-0`} dateTime={guess.guessed_at}>
                          {formatTimestamp(guess.guessed_at, dateLocale)}
                        </time>
                      )}
                    </div>

                    {guess.target_name && (
                      <p className={`${metaClass} break-words`}>
                        {t('adminLiveFeed.target')}: <span className="text-app-text">{guess.target_name}</span>
                      </p>
                    )}

                    <p className={questionClass}>“{guess.guess}”</p>

                    <div className="border-t border-app-border pt-3">
                      <span className={guess.answer ? successBadgeClass : errorBadgeClass}>
                        {guess.answer
                          ? t('adminLiveFeed.outcomes.solved')
                          : t('adminLiveFeed.outcomes.missed')}
                      </span>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </section>
        </div>
      )}
    </section>
  );
};

export default AdminLiveFeedTab;
