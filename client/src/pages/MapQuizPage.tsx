import { useCallback, useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { useTranslation } from 'react-i18next';
import { CheckCircle2, Info, Loader2, RotateCcw, Trophy, X, XCircle } from 'lucide-react';
import type { MapQuizDailyState, MapQuizRoundAnswer, MapQuizScope } from '../types';
import { mapQuizService } from '../services/api';
import MapQuizBoard, { type MapQuizFeedback } from '../components/MapQuizBoard';
import CountdownTimer from '../components/CountdownTimer';
import RegionalGeographyCredit from '../components/RegionalGeographyCredit';
import { GameResultDashboard } from '../components/result-dashboard';

const FEEDBACK_DURATION_MS = 1200;

function getHttpStatus(error: unknown): number | undefined {
  if (typeof error !== 'object' || error === null || !('response' in error)) return undefined;
  const response = (error as { response?: unknown }).response;
  if (typeof response !== 'object' || response === null || !('status' in response)) return undefined;
  return typeof response.status === 'number' ? response.status : undefined;
}

export default function MapQuizPage({ scope }: { scope: MapQuizScope }) {
  const { t } = useTranslation();
  const [state, setState] = useState<MapQuizDailyState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [answerError, setAnswerError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [feedback, setFeedback] = useState<MapQuizFeedback | null>(null);
  const [lastResult, setLastResult] = useState<MapQuizRoundAnswer | null>(null);
  const [pendingState, setPendingState] = useState<MapQuizDailyState | null>(null);
  const [dashboardOpen, setDashboardOpen] = useState(false);
  const [rulesOpen, setRulesOpen] = useState(false);
  const [resetSignal, setResetSignal] = useState(0);
  const [mapRetryRevision, setMapRetryRevision] = useState(0);

  const feedbackTimerRef = useRef<number | null>(null);
  const loadSequenceRef = useRef(0);
  const rulesCloseButton = useRef<HTMLButtonElement>(null);
  const rulesInfoButton = useRef<HTMLButtonElement>(null);
  const wasRulesOpen = useRef(false);

  const scopeTitle =
    scope === 'london_boroughs'
      ? t('mapQuiz.londonBoroughsTitle', 'London Boroughs Map Quiz')
      : t('mapQuiz.englandCountiesTitle', 'English Counties Map Quiz');

  const entityLabel =
    scope === 'london_boroughs'
      ? t('mapQuiz.boroughLabel', 'Borough')
      : t('mapQuiz.countyLabel', 'County');

  const clearFeedbackTimer = useCallback(() => {
    if (feedbackTimerRef.current !== null) {
      window.clearTimeout(feedbackTimerRef.current);
      feedbackTimerRef.current = null;
    }
  }, []);

  const loadDaily = useCallback(async () => {
    const sequence = ++loadSequenceRef.current;
    setLoading(true);
    setError(null);
    setAnswerError(null);
    clearFeedbackTimer();
    setFeedback(null);
    setLastResult(null);
    setPendingState(null);

    try {
      const data = await mapQuizService(scope).getDaily();
      if (sequence !== loadSequenceRef.current) return;
      setState(data);
      setDashboardOpen(data.is_completed);
    } catch {
      if (sequence === loadSequenceRef.current) {
        setError(t('mapQuiz.loadError', 'Could not load today’s map quiz. Please try again.'));
      }
    } finally {
      if (sequence === loadSequenceRef.current) {
        setLoading(false);
      }
    }
  }, [scope, clearFeedbackTimer, t]);

  useEffect(() => {
    void loadDaily();
    return () => clearFeedbackTimer();
  }, [loadDaily, clearFeedbackTimer]);

  useEffect(() => {
    if (rulesOpen) {
      rulesCloseButton.current?.focus();
      const closeOnEscape = (event: KeyboardEvent) => {
        if (event.key === 'Escape') setRulesOpen(false);
      };
      window.addEventListener('keydown', closeOnEscape);
      return () => window.removeEventListener('keydown', closeOnEscape);
    }
    if (wasRulesOpen.current) rulesInfoButton.current?.focus();
    wasRulesOpen.current = rulesOpen;
  }, [rulesOpen]);

  const advancePending = useCallback(() => {
    clearFeedbackTimer();
    setFeedback(null);
    setPendingState((next) => {
      if (next) {
        setState(next);
        if (next.is_completed) {
          setDashboardOpen(true);
        }
      }
      return null;
    });
  }, [clearFeedbackTimer]);

  const handleSelectEntity = useCallback(
    async (entity: { id: number; name: string }) => {
      if (!state || state.is_completed || submitting || feedback) return;
      setSubmitting(true);
      setAnswerError(null);
      try {
        const resp = await mapQuizService(scope).submitAnswer({
          entity_id: entity.id,
          round: state.current_round,
        });
        try {
          localStorage.setItem(`map_quiz_${scope}_daily_${resp.state.date}`, '1');
        } catch {
          // Ignore storage unavailability
        }
        setLastResult(resp.result);
        setFeedback({
          targetId: resp.result.target_id,
          clickedId: resp.result.clicked_id,
          targetName: resp.result.target_name,
          clickedName: resp.result.clicked_name,
          correct: resp.result.correct,
        });
        setPendingState(resp.state);
        clearFeedbackTimer();
        feedbackTimerRef.current = window.setTimeout(() => {
          setFeedback(null);
          setState(resp.state);
          setPendingState(null);
          if (resp.state.is_completed) {
            setDashboardOpen(true);
          }
          feedbackTimerRef.current = null;
        }, FEEDBACK_DURATION_MS);
      } catch (err: unknown) {
        if (getHttpStatus(err) === 409) {
          void loadDaily();
          setAnswerError(
            t('mapQuiz.conflictError', 'Your daily run changed elsewhere and has been refreshed.'),
          );
        } else {
          setAnswerError(
            t('mapQuiz.submitError', 'Your answer could not be saved. Please try again.'),
          );
        }
      } finally {
        setSubmitting(false);
      }
    },
    [state, submitting, feedback, scope, clearFeedbackTimer, loadDaily, t],
  );

  const handleMapRetry = () => {
    setMapRetryRevision((revision) => revision + 1);
  };

  const displayedState = state;
  const effectiveState = pendingState ?? displayedState;
  const finished = Boolean(displayedState?.is_completed);
  const isCorrectFeedback = Boolean(feedback && feedback.correct);
  const isIncorrectFeedback = Boolean(feedback && !feedback.correct);

  const targetName =
    feedback?.targetName ??
    (!finished ? displayedState?.current_target?.name : undefined);

  const score = effectiveState?.score ?? 0;
  const roundCount = displayedState?.total_rounds ?? 10;
  const round = feedback && lastResult
    ? lastResult.round
    : displayedState?.current_round ?? 1;

  const gamePath =
    scope === 'london_boroughs' ? '/map-quiz/london-boroughs' : '/map-quiz/england-counties';
  const statsMode =
    scope === 'london_boroughs' ? 'map_quiz_london_boroughs' : 'map_quiz_england_counties';
  const shareText = displayedState
    ? `${scopeTitle} ${displayedState.date}\n${displayedState.score}/${displayedState.total_rounds}${
        displayedState.points !== null ? ` · ${displayedState.points} pts` : ''
      }\n${displayedState.answers.map((a) => (a.correct ? '🟩' : '🟥')).join('')}\nhttps://countrydle.online${gamePath}`
    : undefined;

  return (
    <main className="relative flex h-full min-h-0 flex-1 w-full overflow-hidden bg-app-canvas text-app-text">
      <section aria-label="Clickable region map" className="absolute inset-0 z-0 w-full">
        <MapQuizBoard
          key={`${scope}-${mapRetryRevision}`}
          scope={scope}
          answers={displayedState?.answers ?? []}
          feedback={feedback}
          isCompleted={finished}
          disabled={loading || !displayedState || submitting || feedback !== null}
          resetSignal={resetSignal}
          onSelectEntity={handleSelectEntity}
          onRetryMap={handleMapRetry}
          className="h-full w-full rounded-none border-0 shadow-none"
        />
      </section>

      <div className="pointer-events-none relative z-[500] flex h-full min-h-0 w-full flex-col px-2 py-2 sm:px-3 sm:py-3">
        <motion.header
          aria-label={`${scopeTitle} status`}
          animate={
            isIncorrectFeedback
              ? { x: [0, -7, 7, -5, 5, -2, 0] }
              : isCorrectFeedback
                ? { scale: [1, 1.012, 1] }
                : { x: 0, scale: 1 }
          }
          transition={{ duration: 0.34, ease: 'easeOut' }}
          className={`pointer-events-auto relative mx-auto mt-0 grid w-full max-w-5xl grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1 overflow-hidden border bg-app-surface/95 px-3 py-2 shadow-sm transition-colors sm:px-4 md:grid-cols-[auto_minmax(0,1fr)_auto] ${
            isIncorrectFeedback
              ? 'border-rose-500/70'
              : isCorrectFeedback
                ? 'border-app-accent/70'
                : 'border-app-border/30'
          }`}
        >
          <p className="min-w-0 truncate font-mono text-[10px] uppercase tracking-[0.16em] text-app-text-muted">
            {scopeTitle}
          </p>

          {targetName ? (
            <motion.h1
              key={targetName}
              aria-live="polite"
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
              className="col-span-2 row-start-2 min-w-0 break-words text-center text-lg font-bold leading-tight text-app-text sm:text-xl md:col-span-1 md:col-start-2 md:row-start-1"
            >
              <span className="font-normal text-app-text-secondary">
                {t('mapQuiz.findPrefix', 'Find:')}{' '}
              </span>
              {targetName}
            </motion.h1>
          ) : finished ? (
            <h1 className="col-span-2 row-start-2 text-center text-lg font-bold leading-tight text-app-text sm:text-xl md:col-span-1 md:col-start-2 md:row-start-1">
              {t('mapQuiz.runComplete', 'Run complete')}
            </h1>
          ) : (
            <p
              role="status"
              className="col-span-2 row-start-2 flex items-center justify-center gap-2 text-sm text-app-text-secondary md:col-span-1 md:col-start-2 md:row-start-1"
            >
              <Loader2 size={15} className="animate-spin" aria-hidden="true" />
              {t('mapQuiz.loading', 'Loading today’s map quiz...')}
            </p>
          )}

          <div className="col-start-2 row-start-1 flex min-w-0 items-center justify-self-end gap-2 md:col-start-3 md:row-start-1">
            <p className="whitespace-nowrap font-mono text-xs text-app-text sm:text-sm">
              <span className="font-semibold">
                {t('mapQuiz.scoreLabel', 'Score')} {score}
              </span>
              <span className="text-app-text-muted"> / {roundCount}</span>
              {!finished && displayedState && (
                <span className="text-app-text-secondary">
                  {' · '}
                  {entityLabel} {round} / {roundCount}
                </span>
              )}
            </p>

            {finished && (
              <button
                type="button"
                onClick={() => setDashboardOpen(true)}
                className="inline-flex h-9 items-center gap-1.5 border border-app-accent/40 bg-app-accent/10 px-2.5 text-xs font-semibold text-app-accent hover:bg-app-accent/15 cursor-pointer"
              >
                <Trophy size={14} aria-hidden="true" />
                <span className="hidden sm:inline">{t('mapQuiz.viewResults', 'Results')}</span>
              </button>
            )}

            <button
              type="button"
              onClick={() => setResetSignal((n) => n + 1)}
              aria-label={t('mapQuiz.resetView', 'Reset map view')}
              title={t('mapQuiz.resetView', 'Reset map view')}
              className="inline-flex h-9 w-9 shrink-0 items-center justify-center border border-app-border/40 text-app-text-secondary hover:bg-app-surface-muted hover:text-app-text focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-accent cursor-pointer"
            >
              <RotateCcw size={16} aria-hidden="true" />
            </button>

            <button
              ref={rulesInfoButton}
              type="button"
              aria-label={t('mapQuiz.rulesAria', 'Map quiz rules')}
              aria-haspopup="dialog"
              aria-expanded={rulesOpen}
              onClick={() => setRulesOpen(true)}
              className="inline-flex h-9 w-9 shrink-0 items-center justify-center border border-app-border/40 text-app-text-secondary hover:bg-app-surface-muted hover:text-app-text focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-accent cursor-pointer"
            >
              <Info size={17} aria-hidden="true" />
            </button>
          </div>

          {!loading && error && (
            <div className="col-span-full flex flex-wrap items-center justify-between gap-3 text-sm" role="alert">
              <p className="text-app-text-secondary">{error}</p>
              <button
                type="button"
                onClick={() => void loadDaily()}
                className="shrink-0 border border-app-border/35 bg-app-surface px-3 py-1.5 text-app-text hover:bg-app-surface-muted cursor-pointer"
              >
                {t('mapQuiz.retryDaily', 'Retry daily run')}
              </button>
            </div>
          )}

          {answerError && (
            <p className="col-span-full text-sm text-rose-700 dark:text-rose-300" role="alert">
              {answerError}
            </p>
          )}

          {submitting && (
            <p className="col-span-full text-sm text-app-text-secondary" role="status">
              {t('mapQuiz.saving', 'Saving your answer...')}
            </p>
          )}

          {isCorrectFeedback && lastResult && (
            <div role="status" className="col-span-full flex items-center justify-between gap-3 text-sm font-medium text-app-accent">
              <span>
                {t('mapQuiz.correctBanner', 'Correct! One point added ({{name}}). Advancing to next target...', {
                  name: lastResult.target_name,
                })}
              </span>
              <button
                type="button"
                onClick={advancePending}
                className="shrink-0 border border-app-accent/40 bg-app-accent/10 px-2.5 py-0.5 text-xs font-semibold text-app-accent hover:bg-app-accent/15 cursor-pointer"
              >
                {pendingState?.is_completed
                  ? t('mapQuiz.seeResults', 'See results')
                  : t('mapQuiz.nextRound', 'Next')}
              </button>
            </div>
          )}

          {isIncorrectFeedback && lastResult && (
            <div role="status" className="col-span-full flex items-center justify-between gap-3 text-sm font-medium text-rose-700 dark:text-rose-300">
              <span>
                {t(
                  'mapQuiz.wrongBanner',
                  'Not quite. No point added (you clicked {{clicked}}). {{target}} is highlighted in green. Advancing to next target...',
                  {
                    clicked: lastResult.clicked_name,
                    target: lastResult.target_name,
                  },
                )}
              </span>
              <button
                type="button"
                onClick={advancePending}
                className="shrink-0 border border-rose-500/40 bg-rose-500/10 px-2.5 py-0.5 text-xs font-semibold text-rose-700 dark:text-rose-300 hover:bg-rose-500/15 cursor-pointer"
              >
                {pendingState?.is_completed
                  ? t('mapQuiz.seeResults', 'See results')
                  : t('mapQuiz.nextRound', 'Next')}
              </button>
            </div>
          )}

          {(isCorrectFeedback || isIncorrectFeedback) && (
            <motion.div
              key={`${feedback?.targetId ?? 'done'}-${round}-${isCorrectFeedback ? 'ok' : 'err'}`}
              initial={{ scaleX: 1 }}
              animate={{ scaleX: 0 }}
              transition={{ duration: FEEDBACK_DURATION_MS / 1000, ease: 'linear' }}
              style={{ transformOrigin: 'left center' }}
              className={`absolute bottom-0 left-0 right-0 h-0.5 ${isIncorrectFeedback ? 'bg-rose-500' : 'bg-app-accent'}`}
              aria-hidden="true"
            />
          )}
        </motion.header>
      </div>

      {/* Rules / Info Modal matching MapChallengePage */}
      {rulesOpen && (
        <div
          className="fixed inset-0 z-[1200] flex items-center justify-center bg-black/55 p-3 sm:p-6"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) setRulesOpen(false);
          }}
        >
          <section
            role="dialog"
            aria-modal="true"
            aria-labelledby="map-quiz-rules-title"
            className="max-h-[min(88vh,48rem)] w-full max-w-2xl overflow-y-auto border border-app-border/50 bg-app-surface p-4 text-app-text shadow-xl sm:p-6"
          >
            <header className="flex items-start justify-between gap-4">
              <div>
                <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-app-text-muted">
                  {scopeTitle}
                </p>
                <h2 id="map-quiz-rules-title" className="mt-1 text-xl font-bold">
                  {t('mapQuiz.dailyRulesHeading', 'Daily game rules')}
                </h2>
              </div>
              <button
                ref={rulesCloseButton}
                type="button"
                aria-label={t('mapQuiz.closeRules', 'Close map quiz rules')}
                onClick={() => setRulesOpen(false)}
                className="inline-flex h-9 w-9 shrink-0 items-center justify-center border border-app-border/40 text-app-text-secondary hover:bg-app-surface-muted hover:text-app-text focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-accent cursor-pointer"
              >
                <X size={17} aria-hidden="true" />
              </button>
            </header>

            <ul className="mt-4 space-y-2 text-sm leading-relaxed text-app-text-secondary">
              <li>
                {scope === 'london_boroughs'
                  ? t(
                      'mapQuiz.londonRule1',
                      'Find the 10 London boroughs in today’s daily run. The current target is shown in the top HUD.',
                    )
                  : t(
                      'mapQuiz.englandRule1',
                      'Find the 10 English ceremonial counties in today’s daily run. The current target is shown in the top HUD.',
                    )}
              </li>
              <li>
                {t(
                  'mapQuiz.rule2',
                  'Correct answers earn one point and turn green. Wrong clicks flash red while revealing the actual target in green.',
                )}
              </li>
              <li>
                {t(
                  'mapQuiz.rule3',
                  'Region labels stay hidden during active rounds. Once the run is complete, hover any region on the map to inspect its name.',
                )}
              </li>
              <li>
                {t(
                  'mapQuiz.rule4',
                  'The daily challenge resets at 00:00 UTC.',
                )}
              </li>
            </ul>

            <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-app-border/25 pt-4">
              <CountdownTimer label={t('mapQuiz.nextQuizIn', 'Next quiz in')} />
            </div>

            <div className="mt-4 border-t border-app-border/25 pt-3">
              <RegionalGeographyCredit scope={scope} />
            </div>
          </section>
        </div>
      )}

      {/* Completion Result Dashboard Modal */}
      {finished && dashboardOpen && displayedState && (
        <GameResultDashboard
          variant="modal"
          onClose={() => setDashboardOpen(false)}
          closeLabel={t('mapQuiz.inspectMap', 'Inspect map')}
          mode={statsMode}
          modeKind="quiz"
          isDaily={true}
          gameName={scopeTitle}
          gamePath={gamePath}
          date={displayedState.date}
          won={displayedState.score >= 7}
          outcomeLabel={t('mapQuiz.completedTitle', 'Daily Map Quiz Complete!')}
          targetLabel={t('mapQuiz.scoreLabel', 'Score')}
          targetName={`${displayedState.score} / ${displayedState.total_rounds}`}
          subtitle={t(
            'mapQuiz.exploreHint',
            'Close this summary to hover any region on the map and inspect its name.',
          )}
          points={displayedState.points ?? 0}
          score={displayedState.score}
          maxScore={displayedState.total_rounds}
          elapsedSeconds={displayedState.elapsed_seconds ?? undefined}
          shareText={shareText}
          detailsTitle="Round Breakdown"
          detailsSlot={
            <div className="grid sm:grid-cols-2 gap-2">
              {displayedState.answers.map((ans) => (
                <div
                  key={ans.round}
                  className="flex items-center justify-between gap-2 rounded-lg border border-zinc-800 bg-zinc-950/50 px-3 py-2 text-sm"
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="text-xs font-mono text-zinc-500 w-5">{ans.round}.</span>
                    {ans.correct ? (
                      <CheckCircle2 size={15} className="shrink-0 text-emerald-400" />
                    ) : (
                      <XCircle size={15} className="shrink-0 text-rose-400" />
                    )}
                    <span className="font-medium text-sand-50 truncate">{ans.target_name}</span>
                  </div>
                  {!ans.correct && (
                    <span className="text-xs text-rose-300 truncate shrink-0">
                      {t('mapQuiz.clickedShort', 'clicked {{name}}', { name: ans.clicked_name })}
                    </span>
                  )}
                </div>
              ))}
            </div>
          }
        />
      )}
    </main>
  );
}
