import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { CheckCircle2, Info, Loader2, Trophy, X, XCircle } from 'lucide-react';
import { ControlledPowiatyMap } from '../components/PowiatyMap';
import { ControlledUSStatesMap } from '../components/USStatesMap';
import { GameResultDashboard } from '../components/result-dashboard';
import { useDailyClock } from '../hooks/useDailyClock';
import { useMapData } from '../hooks/useMapData';
import {
  createIsolatedMapInteraction,
  MAP_CHALLENGE_FEEDBACK_DELAY_MS,
  type MapChallengeState,
} from '../lib/mapChallenge';
import { getMapChallengePowiatHint, getMapChallengeStateHint } from '../lib/mapChallengeHints';
import { isRegionNameVisible } from '../lib/mapRegionTooltips';
import { MAP_QUIZ_PATHS, normalizeMapRegionName, type MapGameMode } from '../lib/mapGameMode';
import {
  exploreService,
  powiatMapQuizService,
  powiatService,
  usStateMapQuizService,
  type PowiatMapQuizDailyState,
  type PowiatMapQuizDailyStats,
  type PowiatMapQuizHistoryItem,
} from '../services/api';
import type { MapQuizDailyState } from '../types';
import { useAuthStore } from '../stores/authStore';

const EMPTY_REGION_HINTS: Readonly<Record<string, string>> = {};

type RoundFeedback = {
  targetName: string;
  clickedName: string;
  round: number;
  correct: boolean;
};

function getHttpStatus(error: unknown): number | undefined {
  if (typeof error !== 'object' || error === null || !('response' in error)) return undefined;
  const response = (error as { response?: unknown }).response;
  if (typeof response !== 'object' || response === null || !('status' in response)) return undefined;
  return typeof response.status === 'number' ? response.status : undefined;
}

export default function MapChallengePage({ mode }: { mode: MapGameMode }) {
  const { today } = useDailyClock();
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const authLoading = useAuthStore((state) => state.isLoading);
  const mapUrl = mode === 'powiaty' ? '/powiaty-min.geojson' : '/us-states.geojson';
  const { data: mapData, error: mapError, retry: retryMap } = useMapData(mapUrl);
  const [mapRetryRevision, setMapRetryRevision] = useState(0);

  const [powiatDailyRun, setPowiatDailyRun] = useState<PowiatMapQuizDailyState | null>(null);
  const [usDailyRun, setUsDailyRun] = useState<MapQuizDailyState | null>(null);
  const [powiatIds, setPowiatIds] = useState<ReadonlyMap<string, number>>(() => new Map());
  const [usStateIds, setUsStateIds] = useState<ReadonlyMap<string, number>>(() => new Map());
  const [regionHints, setRegionHints] = useState<Readonly<Record<string, string>>>(EMPTY_REGION_HINTS);
  const [activeHintName, setActiveHintName] = useState<string | null>(null);
  const [dailyLoading, setDailyLoading] = useState(false);
  const [dailyError, setDailyError] = useState<string | null>(null);
  const [answerError, setAnswerError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [feedback, setFeedback] = useState<RoundFeedback | null>(null);
  const [dashboardOpen, setDashboardOpen] = useState(false);

  const dailyLoadSequence = useRef(0);
  const authLoginLoadObserved = useRef(false);
  const dashboardOpenedKeyRef = useRef<string | null>(null);

  const loadPowiatDaily = useCallback(async (claimFirst: boolean) => {
    const sequence = ++dailyLoadSequence.current;
    setDailyLoading(true);
    setDailyError(null);
    setAnswerError(null);
    setFeedback(null);

    try {
      if (claimFirst) {
        try {
          await powiatMapQuizService.claimDaily();
        } catch (error) {
          const status = getHttpStatus(error);
          if (status !== 404 && status !== 409) throw error;
        }
      }

      const [state, powiats] = await Promise.all([
        powiatMapQuizService.getDaily(),
        powiatService.getPowiaty(),
      ]);
      if (sequence !== dailyLoadSequence.current) return;

      const ids = new Map<string, number>();
      for (const powiat of powiats) {
        ids.set(normalizeMapRegionName(powiat.nazwa), powiat.id);
      }
      const hints: Record<string, string> = {};
      for (const answer of state.answers) {
        const hint = getMapChallengePowiatHint(answer.target_name);
        if (hint) hints[normalizeMapRegionName(answer.target_name).toUpperCase()] = hint;
      }
      setPowiatIds(ids);
      setRegionHints(hints);
      setPowiatDailyRun(state);
      setActiveHintName(null);
    } catch {
      if (sequence === dailyLoadSequence.current) {
        setDailyError('The daily Powiat quiz could not be loaded. Please try again.');
      }
    } finally {
      if (sequence === dailyLoadSequence.current) setDailyLoading(false);
    }
  }, []);

  const loadUSStateDaily = useCallback(async (claimFirst: boolean) => {
    const sequence = ++dailyLoadSequence.current;
    setDailyLoading(true);
    setDailyError(null);
    setAnswerError(null);
    setFeedback(null);

    try {
      if (claimFirst) {
        try {
          await usStateMapQuizService.sync();
        } catch (error) {
          const status = getHttpStatus(error);
          if (status !== 404 && status !== 409) throw error;
        }
      }

      const [state, entities] = await Promise.all([
        usStateMapQuizService.getDaily(),
        usStateMapQuizService.getEntities(),
      ]);
      if (sequence !== dailyLoadSequence.current) return;

      const ids = new Map<string, number>();
      for (const entity of entities) {
        ids.set(normalizeMapRegionName(entity.name), entity.id);
      }
      setUsStateIds(ids);
      setRegionHints(EMPTY_REGION_HINTS);
      setUsDailyRun(state);
      setActiveHintName(null);
    } catch {
      if (sequence === dailyLoadSequence.current) {
        setDailyError('The daily US State map quiz could not be loaded. Please try again.');
      }
    } finally {
      if (sequence === dailyLoadSequence.current) setDailyLoading(false);
    }
  }, []);

  const reloadCurrentMode = useCallback(
    (claimFirst: boolean) => {
      if (mode === 'powiaty') {
        void loadPowiatDaily(claimFirst);
      } else {
        void loadUSStateDaily(claimFirst);
      }
    },
    [mode, loadPowiatDaily, loadUSStateDaily],
  );

  useEffect(() => {
    const handleAuthLogin = () => {
      authLoginLoadObserved.current = true;
      reloadCurrentMode(true);
    };
    window.addEventListener('auth-login', handleAuthLogin);
    return () => window.removeEventListener('auth-login', handleAuthLogin);
  }, [reloadCurrentMode]);

  useEffect(() => {
    setDashboardOpen(false);
    dashboardOpenedKeyRef.current = null;
    if (authLoading) return;
    if (authLoginLoadObserved.current && isAuthenticated) {
      authLoginLoadObserved.current = false;
      return;
    }
    reloadCurrentMode(isAuthenticated);
  }, [mode, authLoading, isAuthenticated, reloadCurrentMode]);

  useEffect(() => {
    if (!feedback) return;
    const timeoutId = window.setTimeout(() => setFeedback(null), MAP_CHALLENGE_FEEDBACK_DELAY_MS);
    return () => window.clearTimeout(timeoutId);
  }, [feedback]);

  useEffect(() => {
    if (mode !== 'powiaty' || !powiatDailyRun) return;
    const stateHints: Record<string, string> = {};
    for (const answer of powiatDailyRun.answers) {
      const hint = getMapChallengePowiatHint(answer.target_name);
      if (hint) stateHints[normalizeMapRegionName(answer.target_name).toUpperCase()] = hint;
    }
    setRegionHints(stateHints);
  }, [powiatDailyRun, mode]);

  const finished =
    mode === 'powiaty' ? Boolean(powiatDailyRun?.is_complete) : Boolean(usDailyRun?.is_completed);

  const runDate =
    mode === 'powiaty' ? (powiatDailyRun?.date ?? today) : (usDailyRun?.date ?? today);

  useEffect(() => {
    if (!finished || feedback) return;
    const storageKey =
      mode === 'powiaty' ? `map_quiz_powiaty_${runDate}` : `map_quiz_us_states_${runDate}`;
    try {
      localStorage.setItem(storageKey, '1');
    } catch {
      // Ignore storage unavailability
    }
    if (dashboardOpenedKeyRef.current !== storageKey) {
      dashboardOpenedKeyRef.current = storageKey;
      setDashboardOpen(true);
    }
  }, [finished, feedback, mode, runDate]);

  const markings = useMemo<MapChallengeState['markings']>(() => {
    const result: MapChallengeState['markings'] = {};
    if (mode === 'powiaty') {
      for (const answer of powiatDailyRun?.answers ?? []) {
        result[answer.target_name.toUpperCase()] = answer.correct ? 'green' : 'red';
      }
      return result;
    }
    for (const answer of usDailyRun?.answers ?? []) {
      result[answer.target_name.toUpperCase()] = answer.correct ? 'green' : 'red';
    }
    return result;
  }, [powiatDailyRun?.answers, usDailyRun?.answers, mode]);

  const visibleRegionNames = useMemo(() => Object.keys(markings), [markings]);
  const interaction = useMemo(() => createIsolatedMapInteraction(markings), [markings]);

  const handleHintOpen = useCallback((name: string) => setActiveHintName(name), []);
  const handleHintClose = useCallback((name: string) => {
    setActiveHintName((current) =>
      current && normalizeMapRegionName(current) === normalizeMapRegionName(name)
        ? null
        : current,
    );
  }, []);

  const handleRegionClick = useCallback(
    (name: string) => {
      if (isRegionNameVisible(name, visibleRegionNames)) {
        setActiveHintName(name);
        return;
      }
      setActiveHintName(null);

      if (mode === 'powiaty') {
        if (!powiatDailyRun || powiatDailyRun.is_complete || feedback || submitting || dailyLoading) return;
        const guessId = powiatIds.get(normalizeMapRegionName(name));
        if (guessId === undefined) {
          setAnswerError('This map region could not be matched to the Powiat list.');
          return;
        }
        const targetName = powiatDailyRun.current_target;
        if (!targetName) return;

        setSubmitting(true);
        setAnswerError(null);
        void powiatMapQuizService
          .submitAnswer({
            guess_id: guessId,
            expected_round: powiatDailyRun.expected_round,
          })
          .then((state) => {
            setPowiatDailyRun(state);
            if (state.last_answer) {
              setFeedback({
                targetName,
                clickedName: name,
                round: state.last_answer.round + 1,
                correct: state.last_answer.correct,
              });
            }
          })
          .catch((error: unknown) => {
            if (getHttpStatus(error) === 409) {
              void loadPowiatDaily(isAuthenticated);
              setAnswerError('Your daily run changed elsewhere and has been refreshed.');
            } else {
              setAnswerError('Your answer could not be saved. Please try again.');
            }
          })
          .finally(() => setSubmitting(false));

        const hint = getMapChallengePowiatHint(targetName);
        if (hint) {
          setRegionHints((current) => ({
            ...current,
            [normalizeMapRegionName(targetName).toUpperCase()]: hint,
          }));
        }
        return;
      }

      if (!usDailyRun || usDailyRun.is_completed || feedback || submitting || dailyLoading) return;
      const entityId = usStateIds.get(normalizeMapRegionName(name));
      if (entityId === undefined) {
        setAnswerError('This map region could not be matched to the US State list.');
        return;
      }
      const targetName = usDailyRun.current_target?.name;
      if (!targetName) return;

      setSubmitting(true);
      setAnswerError(null);
      void usStateMapQuizService
        .submitAnswer({
          entity_id: entityId,
          round: usDailyRun.current_round,
        })
        .then((resp) => {
          setUsDailyRun(resp.state);
          try {
            localStorage.setItem(`map_quiz_us_states_${resp.state.date}`, '1');
          } catch {
            // Ignore storage unavailability
          }
          setFeedback({
            targetName: resp.result.target_name,
            clickedName: resp.result.clicked_name,
            round: resp.result.round,
            correct: resp.result.correct,
          });
        })
        .catch((error: unknown) => {
          if (getHttpStatus(error) === 409) {
            void loadUSStateDaily(isAuthenticated);
            setAnswerError('Your daily run changed elsewhere and has been refreshed.');
          } else {
            setAnswerError('Your answer could not be saved. Please try again.');
          }
        })
        .finally(() => setSubmitting(false));

      void exploreService
        .getUSStateDetail(targetName)
        .then((detail) => {
          const hint = getMapChallengeStateHint(detail);
          if (hint) {
            setRegionHints((current) => ({
              ...current,
              [normalizeMapRegionName(targetName).toUpperCase()]: hint,
            }));
          }
        })
        .catch(() => undefined);
    },
    [
      dailyLoading,
      feedback,
      isAuthenticated,
      loadPowiatDaily,
      loadUSStateDaily,
      mode,
      powiatDailyRun,
      powiatIds,
      submitting,
      usDailyRun,
      usStateIds,
      visibleRegionNames,
    ],
  );

  const handleMapRetry = () => {
    retryMap();
    setMapRetryRevision((revision) => revision + 1);
  };

  const [rulesOpen, setRulesOpen] = useState(false);
  const rulesCloseButton = useRef<HTMLButtonElement>(null);
  const rulesInfoButton = useRef<HTMLButtonElement>(null);
  const wasRulesOpen = useRef(false);
  const [dailyStats, setDailyStats] = useState<PowiatMapQuizDailyStats | null>(null);
  const [dailyStatsLoading, setDailyStatsLoading] = useState(false);
  const [dailyStatsError, setDailyStatsError] = useState(false);
  const [privateHistory, setPrivateHistory] = useState<PowiatMapQuizHistoryItem[] | null>(null);
  const [privateHistoryLoading, setPrivateHistoryLoading] = useState(false);
  const [privateHistoryError, setPrivateHistoryError] = useState(false);

  useEffect(() => {
    if (!rulesOpen || mode !== 'powiaty') return;
    let active = true;
    setDailyStats(null);
    setPrivateHistory(null);
    setDailyStatsLoading(true);
    setPrivateHistoryLoading(true);
    setDailyStatsError(false);
    setPrivateHistoryError(false);
    void powiatMapQuizService
      .getDailyStats()
      .then((stats) => {
        if (active) setDailyStats(stats);
      })
      .catch(() => {
        if (active) setDailyStatsError(true);
      })
      .finally(() => {
        if (active) setDailyStatsLoading(false);
      });
    void powiatMapQuizService
      .getHistory()
      .then((history) => {
        if (active) setPrivateHistory(history.items);
      })
      .catch(() => {
        if (active) setPrivateHistoryError(true);
      })
      .finally(() => {
        if (active) setPrivateHistoryLoading(false);
      });
    return () => {
      active = false;
    };
  }, [rulesOpen, mode]);

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

  const title = mode === 'powiaty' ? 'Powiat Map Quiz' : 'US State Map Quiz';
  const target =
    mode === 'powiaty'
      ? feedback?.targetName ?? powiatDailyRun?.current_target ?? undefined
      : feedback?.targetName ?? (!finished ? usDailyRun?.current_target?.name : undefined);
  const isCorrectFeedback = Boolean(feedback?.correct);
  const isIncorrectFeedback = Boolean(feedback && !feedback.correct);
  const wrongClickedName = feedback && !feedback.correct ? feedback.clickedName : null;
  const score = mode === 'powiaty' ? powiatDailyRun?.score ?? 0 : usDailyRun?.score ?? 0;
  const roundCount =
    mode === 'powiaty' ? powiatDailyRun?.round_count ?? 10 : usDailyRun?.total_rounds ?? 10;
  const round =
    mode === 'powiaty'
      ? feedback?.round ?? (powiatDailyRun?.expected_round ?? 0) + 1
      : feedback?.round ?? usDailyRun?.current_round ?? 1;

  const mapClassName = 'h-full w-full rounded-none border-0 shadow-none';
  const mapKey = `${mode}-${mapRetryRevision}`;
  const sharedMapProps = {
    className: mapClassName,
    interaction,
    hideUnlistedTooltips: true,
    visibleRegionNames,
    regionHints,
    activeHintName,
    onHintOpen: handleHintOpen,
    onHintClose: handleHintClose,
    showMapToolbar: false,
    onRetryMap: handleMapRetry,
  };
  const mapElement =
    mode === 'powiaty' ? (
      <ControlledPowiatyMap key={mapKey} {...sharedMapProps} onPowiatClick={handleRegionClick} />
    ) : (
      <ControlledUSStatesMap key={mapKey} {...sharedMapProps} onStateClick={handleRegionClick} />
    );

  const shareText =
    mode === 'powiaty' && powiatDailyRun
      ? `${title} ${powiatDailyRun.date}\n${powiatDailyRun.score}/${powiatDailyRun.round_count}\n${powiatDailyRun.answers.map((a) => (a.correct ? '🟩' : '🟥')).join('')}\nhttps://countrydle.online${MAP_QUIZ_PATHS.powiaty}`
      : usDailyRun
        ? `${title} ${usDailyRun.date}\n${usDailyRun.score}/${usDailyRun.total_rounds}${
            usDailyRun.points !== null ? ` · ${usDailyRun.points} pts` : ''
          }\n${usDailyRun.answers.map((a) => (a.correct ? '🟩' : '🟥')).join('')}\nhttps://countrydle.online${MAP_QUIZ_PATHS.us_states}`
        : undefined;

  return (
    <main className="relative flex h-full min-h-0 flex-1 w-full overflow-hidden bg-app-canvas text-app-text">
      <section aria-label="Clickable region map" className="absolute inset-0 z-0 w-full">
        {mapElement}
      </section>

      <div className="pointer-events-none relative z-[500] flex h-full min-h-0 w-full flex-col px-2 py-2 sm:px-3 sm:py-3">
        <motion.header
          aria-label={`${title} status`}
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
            {title}
          </p>
          {target ? (
            <motion.h1
              key={target}
              aria-live="polite"
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
              className="col-span-2 row-start-2 min-w-0 break-words text-center text-lg font-bold leading-tight text-app-text sm:text-xl md:col-span-1 md:col-start-2 md:row-start-1"
            >
              {target}
            </motion.h1>
          ) : finished ? (
            <h1 className="col-span-2 row-start-2 text-center text-lg font-bold leading-tight text-app-text sm:text-xl md:col-span-1 md:col-start-2 md:row-start-1">
              Run complete
            </h1>
          ) : (
            <p
              role="status"
              className="col-span-2 row-start-2 flex items-center justify-center gap-2 text-sm text-app-text-secondary md:col-span-1 md:col-start-2 md:row-start-1"
            >
              <Loader2 size={15} className="animate-spin" aria-hidden="true" />
              {mode === 'powiaty'
                ? 'Loading today’s Powiat run...'
                : 'Loading today’s US State run...'}
            </p>
          )}

          <div className="col-start-2 row-start-1 flex min-w-0 items-center justify-self-end gap-2 md:col-start-3 md:row-start-1">
            <p className="whitespace-nowrap font-mono text-xs text-app-text sm:text-sm">
              <span className="font-semibold">Score {score}</span>
              <span className="text-app-text-muted"> / {roundCount}</span>
              {!finished && (
                <span className="text-app-text-secondary">
                  {' · '}
                  {mode === 'powiaty' ? 'Powiat' : 'State'} {round} of {roundCount}
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
                <span className="hidden sm:inline">Results</span>
              </button>
            )}
            <button
              ref={rulesInfoButton}
              type="button"
              aria-label="Map quiz rules"
              aria-haspopup="dialog"
              aria-expanded={rulesOpen}
              onClick={() => setRulesOpen(true)}
              className="inline-flex h-9 w-9 shrink-0 items-center justify-center border border-app-border/40 text-app-text-secondary hover:bg-app-surface-muted hover:text-app-text focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-accent cursor-pointer"
            >
              <Info size={17} aria-hidden="true" />
            </button>
          </div>

          {dailyError && (
            <div className="col-span-full flex flex-wrap items-center justify-between gap-3 text-sm" role="alert">
              <p className="text-app-text-secondary">{dailyError}</p>
              <button
                type="button"
                onClick={() => reloadCurrentMode(isAuthenticated)}
                className="shrink-0 border border-app-border/35 bg-app-surface px-3 py-2 text-app-text hover:bg-app-surface-muted"
              >
                Retry daily run
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
              Saving your answer...
            </p>
          )}
          {isCorrectFeedback && (
            <p role="status" className="col-span-full text-sm font-medium text-app-accent">
              Correct! One point added.{target ? ` (${target})` : ''} Advancing to next target...
            </p>
          )}
          {isIncorrectFeedback && (
            <p role="status" className="col-span-full text-sm font-medium text-rose-700 dark:text-rose-300">
              Not quite. No point added{wrongClickedName ? ` (you clicked ${wrongClickedName})` : ''};{' '}
              {target ? `${target} is highlighted red` : 'the correct region is highlighted red'}. Advancing to next target...
            </p>
          )}
          {mapError && !mapData && (
            <div className="col-span-full flex items-center justify-between gap-3 text-sm" role="alert">
              <p className="text-app-text-secondary">Map data could not be loaded.</p>
              <button
                type="button"
                onClick={handleMapRetry}
                className="shrink-0 border border-app-border/35 bg-app-surface px-3 py-2 text-app-text hover:bg-app-surface-muted"
              >
                Retry map loading
              </button>
            </div>
          )}
          {(isCorrectFeedback || isIncorrectFeedback) && (
            <motion.div
              key={`${target ?? 'done'}-${round}-${isCorrectFeedback ? 'ok' : 'err'}`}
              initial={{ scaleX: 1 }}
              animate={{ scaleX: 0 }}
              transition={{ duration: MAP_CHALLENGE_FEEDBACK_DELAY_MS / 1000, ease: 'linear' }}
              style={{ transformOrigin: 'left center' }}
              className={`absolute bottom-0 left-0 right-0 h-0.5 ${isIncorrectFeedback ? 'bg-rose-500' : 'bg-app-accent'}`}
              aria-hidden="true"
            />
          )}
        </motion.header>
      </div>

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
                  {title}
                </p>
                <h2 id="map-quiz-rules-title" className="mt-1 text-xl font-bold">
                  Daily game rules
                </h2>
              </div>
              <button
                ref={rulesCloseButton}
                type="button"
                aria-label="Close map quiz rules"
                onClick={() => setRulesOpen(false)}
                className="inline-flex h-9 w-9 shrink-0 items-center justify-center border border-app-border/40 text-app-text-secondary hover:bg-app-surface-muted hover:text-app-text focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-accent"
              >
                <X size={17} aria-hidden="true" />
              </button>
            </header>

            {mode === 'powiaty' ? (
              <>
                <ul className="mt-4 space-y-2 text-sm leading-relaxed text-app-text-secondary">
                  <li>Find the 10 Powiats in today’s daily run. The current Powiat is shown in the HUD.</li>
                  <li>Correct answers earn one point and turn green. Wrong answers add no point and reveal the correct Powiat in red.</li>
                  <li>The daily run resets at 00:00 UTC. Your completed-run history is private; aggregate performance is shown separately below.</li>
                </ul>
                <div className="mt-5 grid gap-4 sm:grid-cols-2">
                  <section aria-label="Daily aggregate performance" className="border border-app-border/35 p-3">
                    <h3 className="font-semibold">All-player daily aggregate</h3>
                    {dailyStatsLoading ? (
                      <p className="mt-2 text-sm text-app-text-secondary">Loading aggregate performance...</p>
                    ) : dailyStatsError ? (
                      <p className="mt-2 text-sm text-app-text-secondary">Aggregate performance is temporarily unavailable.</p>
                    ) : dailyStats ? (
                      <div className="mt-2 space-y-1 text-sm text-app-text-secondary">
                        <p>{dailyStats.completed_count ?? '-'} completed</p>
                        <p>Average score: {dailyStats.average_score ?? 'Not enough completed runs yet'}</p>
                        <p>
                          Score distribution:{' '}
                          {dailyStats.score_distribution
                            ? Object.entries(dailyStats.score_distribution)
                                .sort(([a], [b]) => Number(a) - Number(b))
                                .map(([scoreValue, count]) => `${scoreValue}: ${count}`)
                                .join(' · ') || 'Not available yet'
                            : 'Not available yet'}
                        </p>
                      </div>
                    ) : null}
                  </section>
                  <section aria-label="Your private score history" className="border border-app-border/35 p-3">
                    <h3 className="font-semibold">Your private score history</h3>
                    {privateHistoryLoading ? (
                      <p className="mt-2 text-sm text-app-text-secondary">Loading your history...</p>
                    ) : privateHistoryError ? (
                      <p className="mt-2 text-sm text-app-text-secondary">Your history is temporarily unavailable.</p>
                    ) : privateHistory?.length ? (
                      <ul className="mt-2 space-y-1 text-sm text-app-text-secondary">
                        {privateHistory.map((run) => (
                          <li key={`${run.date}-${run.completed_at ?? ''}`}>
                            {run.date} · {run.score} / {run.round_count}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="mt-2 text-sm text-app-text-secondary">No completed runs in your history yet.</p>
                    )}
                  </section>
                </div>
              </>
            ) : (
              <ul className="mt-4 space-y-2 text-sm leading-relaxed text-app-text-secondary">
                <li>Find the 10 US States in today’s daily run. The current target state is shown in the HUD.</li>
                <li>Correct answers earn one point and turn green. Wrong answers add no point and reveal the correct state in red.</li>
                <li>Every player gets the same 10 states each day, with one attempt per UTC day resetting at 00:00 UTC.</li>
              </ul>
            )}
          </section>
        </div>
      )}

      {finished && dashboardOpen && (
        <GameResultDashboard
          variant="modal"
          onClose={() => setDashboardOpen(false)}
          closeLabel="Inspect map"
          mode={mode === 'powiaty' ? 'map_quiz_powiaty' : 'map_quiz_us_states'}
          modeKind="quiz"
          isDaily={true}
          gameName={title}
          gamePath={MAP_QUIZ_PATHS[mode]}
          date={runDate}
          won={mode === 'powiaty' ? score >= 6 : score >= 7}
          outcomeLabel={
            mode === 'powiaty'
              ? 'Daily Powiat Map Quiz Complete!'
              : 'Daily US State Map Quiz Complete!'
          }
          targetLabel="Score"
          targetName={`${score} / ${roundCount}`}
          subtitle="Close this summary to hover any region on the map and inspect its details."
          points={mode === 'powiaty' ? score * 100 : (usDailyRun?.points ?? 0)}
          score={score}
          maxScore={roundCount}
          elapsedSeconds={mode === 'us_states' ? (usDailyRun?.elapsed_seconds ?? undefined) : undefined}
          shareText={shareText}
          detailsTitle="Round Breakdown"
          detailsSlot={
            <div className="grid sm:grid-cols-2 gap-2">
              {mode === 'powiaty'
                ? (powiatDailyRun?.answers ?? []).map((ans) => (
                    <div
                      key={ans.round}
                      className="flex items-center justify-between gap-2 rounded-lg border border-zinc-800 bg-zinc-950/50 px-3 py-2 text-sm"
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="text-xs font-mono text-zinc-500 w-5">{ans.round + 1}.</span>
                        {ans.correct ? (
                          <CheckCircle2 size={15} className="shrink-0 text-emerald-400" />
                        ) : (
                          <XCircle size={15} className="shrink-0 text-rose-400" />
                        )}
                        <span className="font-medium text-sand-50 truncate">{ans.target_name}</span>
                      </div>
                    </div>
                  ))
                : (usDailyRun?.answers ?? []).map((ans) => (
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
                          clicked {ans.clicked_name}
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
