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

function formatTimestamp(timestamp: string | null, locale: string): string | null {
  if (!timestamp) return null;
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return timestamp;
  return new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'medium' }).format(date);
}

function getQuestionAnswer(question: LiveQuestionItem, t: (key: string) => string) {
  if (!question.valid) {
    return { label: t('adminLiveFeed.answers.invalid'), className: 'admin-badge admin-answer-invalid' };
  }
  if (question.answer === true) {
    return { label: t('adminLiveFeed.answers.yes'), className: 'admin-badge admin-answer-yes' };
  }
  if (question.answer === false) {
    return { label: t('adminLiveFeed.answers.no'), className: 'admin-badge admin-muted' };
  }
  return { label: t('adminLiveFeed.answers.noAnswer'), className: 'admin-badge admin-muted' };
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
  const { t, i18n } = useTranslation();
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
  const dateLocale = i18n.language.startsWith('pl') ? 'pl-PL' : 'en-US';
  const lastUpdated = formatTimestamp(lastUpdatedAt, dateLocale);

  const renderQuestion = (question: LiveQuestionItem) => {
    const result = getQuestionAnswer(question, t);
    const sourceLabel = question.source === 'local_kb'
      ? t('adminLiveFeed.sources.localKb')
      : question.source === 'fallback'
        ? t('adminLiveFeed.sources.aiFallback')
        : question.source;

    return (
      <article key={`${question.mode}:${question.id}`} className="space-y-3 rounded-md border border-white/10 bg-obsidian-950 p-3">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            <span className="break-words font-semibold text-sand-100">{question.username}</span>
            <span className="admin-badge font-mono">{question.mode}</span>
          </div>
          {question.asked_at && (
            <time className="admin-meta shrink-0" dateTime={question.asked_at}>
              {formatTimestamp(question.asked_at, dateLocale)}
            </time>
          )}
        </div>

        {question.target_name && (
          <p className="admin-meta break-words">
            {t('adminLiveFeed.target')}: <span className="text-sand-100">{question.target_name}</span>
            {question.target_subtitle && <span> ({question.target_subtitle})</span>}
          </p>
        )}

        <p className="admin-question break-words">“{question.question}”</p>

        <div className="flex flex-wrap items-center gap-2 border-t border-white/10 pt-3">
          <span className={result.className}>{result.label}</span>
          {sourceLabel && <span className="admin-badge">{sourceLabel}</span>}
          {onTestInQA && (
            <button
              type="button"
              onClick={() => onTestInQA({
                mode: question.mode,
                targetName: question.target_name || undefined,
                questionText: question.question,
              })}
              className="admin-button ml-auto"
            >
              <Sparkles size={16} aria-hidden="true" />
              {t('adminLiveFeed.testInQa')}
            </button>
          )}
        </div>

        {question.explanation && (
          <details className="border-t border-white/10 pt-2">
            <summary className="text-sm font-medium text-sand-100">{t('adminLiveFeed.explanation')}</summary>
            <p className="admin-muted break-words pb-2">{question.explanation}</p>
          </details>
        )}
      </article>
    );
  };

  return (
    <section className="space-y-4">
      <div className="admin-toolbar" role="group" aria-label={t('adminLiveFeed.controls')}>
        <div className="grid w-full grid-cols-1 gap-4 sm:grid-cols-2 xl:flex-1">
          <div className="admin-field">
            <label htmlFor="admin-live-feed-mode">{t('adminLiveFeed.mode')}</label>
            <select
              id="admin-live-feed-mode"
              className="admin-control"
              value={selectedMode}
              onChange={(event) => handleModeChange(event.target.value)}
            >
              {MODES.map((mode) => (
                <option key={mode.id} value={mode.id}>{t(`adminLiveFeed.${mode.labelKey}`)}</option>
              ))}
            </select>
          </div>

          <div className="admin-field">
            <label htmlFor="admin-live-feed-auto-refresh">{t('adminLiveFeed.autoRefresh.label')}</label>
            <select
              id="admin-live-feed-auto-refresh"
              className="admin-control"
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
          <p className="admin-meta flex items-center gap-2" role="status">
            <Clock size={16} aria-hidden="true" />
            {lastUpdated && lastUpdatedAt
              ? <time dateTime={lastUpdatedAt}>{t('adminLiveFeed.lastUpdated', { time: lastUpdated })}</time>
              : t('adminLiveFeed.notUpdated')}
          </p>
          <button
            type="button"
            onClick={() => { void requestFeed(selectedMode === 'all' ? undefined : selectedMode).catch(() => undefined); }}
            disabled={isLoading}
            className="admin-button"
          >
            <RefreshCw size={16} className={isLoading ? 'animate-spin' : ''} aria-hidden="true" />
            {t('adminLiveFeed.refresh')}
          </button>
        </div>
      </div>

      {isLoading && !hasCurrentSnapshot && (
        <p role="status" className="admin-panel admin-muted">{t('adminLiveFeed.loading')}</p>
      )}

      {error && (
        <div role="alert" className="admin-panel border-rose-400/40 text-rose-200">
          <p>{t('adminLiveFeed.requestFailed')}</p>
          <p className="mt-2 break-words text-sm">{t(error)}</p>
          {hasCurrentSnapshot && (
            <p className="admin-meta mt-2">{t('adminLiveFeed.staleSnapshot')}</p>
          )}
          <button
            type="button"
            onClick={() => { void requestFeed(selectedMode === 'all' ? undefined : selectedMode).catch(() => undefined); }}
            disabled={isLoading}
            className="admin-button mt-3"
          >
            <RefreshCw size={16} aria-hidden="true" />
            {t('adminLiveFeed.retry')}
          </button>
        </div>
      )}

      {isLoading && hasCurrentSnapshot && (
        <p role="status" className="admin-meta">{t('adminLiveFeed.updating')}</p>
      )}

      {hasCurrentSnapshot && (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          <section className="admin-panel space-y-4" aria-labelledby="admin-live-feed-questions-heading">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/10 pb-3">
              <h2 id="admin-live-feed-questions-heading" className="flex items-center gap-2">
                <HelpCircle size={18} aria-hidden="true" />
                {t('adminLiveFeed.questionsHeading')}
              </h2>
              <span className="admin-meta">
                {t('adminLiveFeed.eventCount', { count: visibleData.recent_questions.length })}
              </span>
            </div>
            {visibleData.recent_questions.length === 0 ? (
              !error && <p className="admin-muted py-4">{t('adminLiveFeed.noQuestions')}</p>
            ) : (
              <div role="region" aria-labelledby="admin-live-feed-questions-heading" tabIndex={0} className="space-y-3 xl:max-h-[700px] xl:overflow-y-auto xl:pr-1">
                {visibleData.recent_questions.map(renderQuestion)}
              </div>
            )}
          </section>

          <section className="admin-panel space-y-4" aria-labelledby="admin-live-feed-guesses-heading">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/10 pb-3">
              <h2 id="admin-live-feed-guesses-heading" className="flex items-center gap-2">
                <Target size={18} aria-hidden="true" />
                {t('adminLiveFeed.guessesHeading')}
              </h2>
              <span className="admin-meta">
                {t('adminLiveFeed.eventCount', { count: visibleData.recent_guesses.length })}
              </span>
            </div>
            {visibleData.recent_guesses.length === 0 ? (
              !error && <p className="admin-muted py-4">{t('adminLiveFeed.noGuesses')}</p>
            ) : (
              <div role="region" aria-labelledby="admin-live-feed-guesses-heading" tabIndex={0} className="space-y-3 xl:max-h-[700px] xl:overflow-y-auto xl:pr-1">
                {visibleData.recent_guesses.map((guess) => (
                  <article
                    key={`${guess.mode}:${guess.id}`}
                    className="space-y-3 rounded-md border border-white/10 bg-obsidian-950 p-3"
                  >
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div className="flex min-w-0 flex-wrap items-center gap-2">
                        <span className="break-words font-semibold text-sand-100">{guess.username}</span>
                        <span className="admin-badge font-mono">{guess.mode}</span>
                      </div>
                      {guess.guessed_at && (
                        <time className="admin-meta shrink-0" dateTime={guess.guessed_at}>
                          {formatTimestamp(guess.guessed_at, dateLocale)}
                        </time>
                      )}
                    </div>

                    {guess.target_name && (
                      <p className="admin-meta break-words">
                        {t('adminLiveFeed.target')}: <span className="text-sand-100">{guess.target_name}</span>
                        {guess.target_subtitle && <span> ({guess.target_subtitle})</span>}
                      </p>
                    )}

                    <p className="admin-question break-words">“{guess.guess}”</p>

                    <div className="border-t border-white/10 pt-3">
                      <span className={`admin-badge ${guess.answer ? 'admin-answer-yes' : 'admin-outcome-error'}`}>
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
