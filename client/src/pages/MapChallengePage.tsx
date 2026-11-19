import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Info, Loader2, RotateCcw, X } from 'lucide-react';
import { ControlledPowiatyMap } from '../components/PowiatyMap';
import { ControlledUSStatesMap } from '../components/USStatesMap';
import { useMapData } from '../hooks/useMapData';
import {
  advanceMapChallenge,
  answerMapChallenge,
  createIsolatedMapInteraction,
  createMapChallengeState,
  getMapChallengePool,
  MAP_CHALLENGE_FEEDBACK_DELAY_MS,
  type MapChallengeState,
} from '../lib/mapChallenge';
import { getMapChallengePowiatHint, getMapChallengeStateHint } from '../lib/mapChallengeHints';
import { isRegionNameVisible } from '../lib/mapRegionTooltips';
import { normalizeMapRegionName, type MapGameMode } from '../lib/mapGameMode';
import {
  exploreService,
  powiatMapQuizService,
  powiatService,
  type PowiatMapQuizDailyState,
  type PowiatMapQuizDailyStats,
  type PowiatMapQuizHistoryItem,
} from '../services/api';
import { useAuthStore } from '../stores/authStore';

const EMPTY_MARKINGS: MapChallengeState['markings'] = {};
const EMPTY_REGION_HINTS: Readonly<Record<string, string>> = {};

type PowiatFeedback = {
  targetName: string;
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
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const authLoading = useAuthStore((state) => state.isLoading);
  const mapUrl = mode === 'powiaty' ? '/powiaty-min.geojson' : '/us-states.geojson';
  const { data: mapData, error: mapError, retry: retryMap } = useMapData(mapUrl);
  const [mapRetryRevision, setMapRetryRevision] = useState(0);
  const promptPool = useMemo(() => getMapChallengePool(mapData, mode), [mapData, mode]);

  const [stateRun, setStateRun] = useState<{ mode: MapGameMode; state: MapChallengeState } | null>(null);
  const game = stateRun?.mode === mode ? stateRun.state : null;
  const [dailyRun, setDailyRun] = useState<PowiatMapQuizDailyState | null>(null);
  const [powiatIds, setPowiatIds] = useState<ReadonlyMap<string, number>>(() => new Map());
  const [regionHints, setRegionHints] = useState<Readonly<Record<string, string>>>(EMPTY_REGION_HINTS);
  const [activeHintName, setActiveHintName] = useState<string | null>(null);
  const [dailyLoading, setDailyLoading] = useState(false);
  const [dailyError, setDailyError] = useState<string | null>(null);
  const [answerError, setAnswerError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [powiatFeedback, setPowiatFeedback] = useState<PowiatFeedback | null>(null);
  const dailyLoadSequence = useRef(0);
  const authLoginLoadObserved = useRef(false);

  const loadPowiatDaily = useCallback(async (claimFirst: boolean) => {
    const sequence = ++dailyLoadSequence.current;
    setDailyLoading(true);
    setDailyError(null);
    setAnswerError(null);
    setPowiatFeedback(null);

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
      setDailyRun(state);
      setActiveHintName(null);
    } catch {
      if (sequence === dailyLoadSequence.current) {
        setDailyError('The daily Powiat quiz could not be loaded. Please try again.');
      }
    } finally {
      if (sequence === dailyLoadSequence.current) setDailyLoading(false);
    }
  }, []);

  useEffect(() => {
    if (mode !== 'powiaty') return;
    const handleAuthLogin = () => {
      authLoginLoadObserved.current = true;
      void loadPowiatDaily(true);
    };
    window.addEventListener('auth-login', handleAuthLogin);
    return () => window.removeEventListener('auth-login', handleAuthLogin);
  }, [mode, loadPowiatDaily]);

  useEffect(() => {
    if (mode === 'powiaty') {
      setStateRun(null);
      if (authLoading) return;
      if (authLoginLoadObserved.current && isAuthenticated) {
        authLoginLoadObserved.current = false;
        return;
      }
      void loadPowiatDaily(isAuthenticated);
      return;
    }

    if (!promptPool.length) return;
    setStateRun((current) => current?.mode === mode
      ? current
      : { mode, state: createMapChallengeState(promptPool) });
  }, [mode, authLoading, isAuthenticated, promptPool, loadPowiatDaily]);

  const hasAnsweredState = mode === 'us_states' && (game?.status === 'correct' || game?.status === 'incorrect');
  useEffect(() => {
    if (!hasAnsweredState) return;
    const timeoutId = window.setTimeout(() => {
      setStateRun((current) => current?.mode === mode
        ? { ...current, state: advanceMapChallenge(current.state) }
        : current);
    }, MAP_CHALLENGE_FEEDBACK_DELAY_MS);
    return () => window.clearTimeout(timeoutId);
  }, [game?.currentPromptIndex, game?.status, hasAnsweredState, mode]);

  useEffect(() => {
    if (!powiatFeedback) return;
    const timeoutId = window.setTimeout(() => setPowiatFeedback(null), MAP_CHALLENGE_FEEDBACK_DELAY_MS);
    return () => window.clearTimeout(timeoutId);
  }, [powiatFeedback]);

  useEffect(() => {
    if (mode !== 'powiaty' || !dailyRun) return;
    const stateHints: Record<string, string> = {};
    for (const answer of dailyRun.answers) {
      const hint = getMapChallengePowiatHint(answer.target_name);
      if (hint) stateHints[normalizeMapRegionName(answer.target_name).toUpperCase()] = hint;
    }
    setRegionHints(stateHints);
  }, [dailyRun, mode]);

  const markings = useMemo<MapChallengeState['markings']>(() => {
    if (mode !== 'powiaty') return game?.markings ?? EMPTY_MARKINGS;
    const result: MapChallengeState['markings'] = {};
    for (const answer of dailyRun?.answers ?? []) {
      result[answer.target_name.toUpperCase()] = answer.correct ? 'green' : 'red';
    }
    return result;
  }, [dailyRun?.answers, game?.markings, mode]);
  const visibleRegionNames = useMemo(() => Object.keys(markings), [markings]);
  const interaction = useMemo(() => createIsolatedMapInteraction(markings), [markings]);

  const handleHintOpen = useCallback((name: string) => setActiveHintName(name), []);
  const handleHintClose = useCallback((name: string) => {
    setActiveHintName((current) => current && normalizeMapRegionName(current) === normalizeMapRegionName(name)
      ? null
      : current);
  }, []);

  const handleRegionClick = useCallback((name: string) => {
    if (isRegionNameVisible(name, visibleRegionNames)) {
      setActiveHintName(name);
      return;
    }
    setActiveHintName(null);

    if (mode === 'powiaty') {
      if (!dailyRun || dailyRun.is_complete || powiatFeedback || submitting || dailyLoading) return;
      const guessId = powiatIds.get(normalizeMapRegionName(name));
      if (guessId === undefined) {
        setAnswerError('This map region could not be matched to the Powiat list.');
        return;
      }
      const targetName = dailyRun.current_target;
      if (!targetName) return;

      setSubmitting(true);
      setAnswerError(null);
      void powiatMapQuizService.submitAnswer({
        guess_id: guessId,
        expected_round: dailyRun.expected_round,
      }).then((state) => {
        setDailyRun(state);
        if (state.last_answer) {
          setPowiatFeedback({
            targetName,
            round: state.last_answer.round,
            correct: state.last_answer.correct,
          });
        }
      }).catch((error: unknown) => {
        if (getHttpStatus(error) === 409) {
          void loadPowiatDaily(isAuthenticated);
          setAnswerError('Your daily run changed elsewhere and has been refreshed.');
        } else {
          setAnswerError('Your answer could not be saved. Please try again.');
        }
      }).finally(() => setSubmitting(false));

      const hint = getMapChallengePowiatHint(targetName);
      if (hint) {
        setRegionHints((current) => ({
          ...current,
          [normalizeMapRegionName(targetName).toUpperCase()]: hint,
        }));
      }
      return;
    }

    if (!game || game.status !== 'playing') return;
    const targetName = game.prompts[game.currentPromptIndex];
    setStateRun((current) => current?.mode === mode
      ? { ...current, state: answerMapChallenge(current.state, name) }
      : current);
    if (targetName) {
      void exploreService.getUSStateDetail(targetName).then((detail) => {
        const hint = getMapChallengeStateHint(detail);
        if (hint) {
          setRegionHints((current) => ({
            ...current,
            [normalizeMapRegionName(targetName).toUpperCase()]: hint,
          }));
        }
      }).catch(() => undefined);
    }
  }, [
    dailyLoading,
    dailyRun,
    game,
    isAuthenticated,
    loadPowiatDaily,
    mode,
    powiatFeedback,
    powiatIds,
    submitting,
    visibleRegionNames,
  ]);

  const startNewRun = () => {
    if (mode === 'us_states' && promptPool.length) {
      setStateRun({ mode, state: createMapChallengeState(promptPool) });
    }
  };

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
    void powiatMapQuizService.getDailyStats().then((stats) => {
      if (active) setDailyStats(stats);
    }).catch(() => {
      if (active) setDailyStatsError(true);
    }).finally(() => {
      if (active) setDailyStatsLoading(false);
    });
    void powiatMapQuizService.getHistory().then((history) => {
      if (active) setPrivateHistory(history.items);
    }).catch(() => {
      if (active) setPrivateHistoryError(true);
    }).finally(() => {
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
  const target = mode === 'powiaty'
    ? powiatFeedback?.targetName ?? dailyRun?.current_target ?? undefined
    : game && game.status !== 'finished' ? game.prompts[game.currentPromptIndex] : undefined;
  const finished = mode === 'powiaty' ? Boolean(dailyRun?.is_complete) : game?.status === 'finished';
  const score = mode === 'powiaty' ? dailyRun?.score ?? 0 : game?.score ?? 0;
  const roundCount = mode === 'powiaty' ? dailyRun?.round_count ?? 10 : game?.prompts.length ?? 10;
  const round = mode === 'powiaty'
    ? (powiatFeedback?.round ?? dailyRun?.expected_round ?? 0) + 1
    : (game?.currentPromptIndex ?? 0) + 1;
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
  const mapElement = mode === 'powiaty'
    ? <ControlledPowiatyMap key={mapKey} {...sharedMapProps} onPowiatClick={handleRegionClick} />
    : <ControlledUSStatesMap key={mapKey} {...sharedMapProps} onStateClick={handleRegionClick} />;

  return (
    <main className="relative flex h-full min-h-0 flex-1 w-full overflow-hidden bg-app-canvas text-app-text">
      <section aria-label="Clickable region map" className="absolute inset-0 z-0 w-full">
        {mapElement}
      </section>

      <div className="pointer-events-none relative z-[500] flex h-full min-h-0 w-full flex-col px-2 py-2 sm:px-3 sm:py-3">
        <header aria-label={`${title} status`} className="pointer-events-auto mx-auto mt-0 grid w-full max-w-5xl grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1 border border-app-border/30 bg-app-surface/95 px-3 py-2 shadow-sm sm:px-4 md:grid-cols-[auto_minmax(0,1fr)_auto]">
          <p className="min-w-0 truncate font-mono text-[10px] uppercase tracking-[0.16em] text-app-text-muted">{title}</p>
          {target ? (
            <h1 aria-live="polite" className="col-span-2 row-start-2 min-w-0 break-words text-center text-lg font-bold leading-tight text-app-text sm:text-xl md:col-span-1 md:col-start-2 md:row-start-1">
              {target}
            </h1>
          ) : finished ? (
            <h1 className="col-span-2 row-start-2 text-center text-lg font-bold leading-tight text-app-text sm:text-xl md:col-span-1 md:col-start-2 md:row-start-1">
              Run complete
            </h1>
          ) : (
            <p role="status" className="col-span-2 row-start-2 flex items-center justify-center gap-2 text-sm text-app-text-secondary md:col-span-1 md:col-start-2 md:row-start-1">
              <Loader2 size={15} className="animate-spin" aria-hidden="true" />
              {mode === 'powiaty' ? 'Loading today’s Powiat run…' : 'Loading the first state…'}
            </p>
          )}

          <div className="col-start-2 row-start-1 flex min-w-0 items-center justify-self-end gap-2 md:col-start-3 md:row-start-1">
            <p className="whitespace-nowrap font-mono text-xs text-app-text sm:text-sm">
              <span className="font-semibold">Score {score}</span>
              <span className="text-app-text-muted"> / {roundCount}</span>
              {!finished && (
                <span className="text-app-text-secondary">
                  {' · '}{mode === 'powiaty' ? 'Powiat' : 'State'} {round} of {roundCount}
                </span>
              )}
            </p>
            {mode === 'us_states' && finished && (
              <button type="button" onClick={startNewRun} className="inline-flex min-h-10 items-center gap-2 border border-app-accent/40 bg-app-accent/10 px-3 py-2 text-sm font-semibold text-app-accent hover:bg-app-accent/15">
                <RotateCcw size={15} aria-hidden="true" /> Start another run
              </button>
            )}
            <button
              ref={rulesInfoButton}
              type="button"
              aria-label="Map quiz rules"
              aria-haspopup="dialog"
              aria-expanded={rulesOpen}
              onClick={() => setRulesOpen(true)}
              className="inline-flex h-9 w-9 shrink-0 items-center justify-center border border-app-border/40 text-app-text-secondary hover:bg-app-surface-muted hover:text-app-text focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-accent"
            >
              <Info size={17} aria-hidden="true" />
            </button>
          </div>

          {mode === 'powiaty' && dailyError && (
            <div className="col-span-full flex flex-wrap items-center justify-between gap-3 text-sm" role="alert">
              <p className="text-app-text-secondary">{dailyError}</p>
              <button type="button" onClick={() => void loadPowiatDaily(isAuthenticated)} className="shrink-0 border border-app-border/35 bg-app-surface px-3 py-2 text-app-text hover:bg-app-surface-muted">
                Retry daily run
              </button>
            </div>
          )}
          {answerError && <p className="col-span-full text-sm text-rose-700 dark:text-rose-300" role="alert">{answerError}</p>}
          {submitting && <p className="col-span-full text-sm text-app-text-secondary" role="status">Saving your answer…</p>}
          {(powiatFeedback?.correct || game?.status === 'correct') && (
            <p role="status" className="col-span-full text-sm font-medium text-app-accent">Correct — one point added.</p>
          )}
          {(powiatFeedback && !powiatFeedback.correct || game?.status === 'incorrect') && (
            <p role="status" className="col-span-full text-sm text-rose-700 dark:text-rose-300">
              Not quite. No point added; the correct region is highlighted red.
            </p>
          )}
          {mapError && !mapData && (
            <div className="col-span-full flex items-center justify-between gap-3 text-sm" role="alert">
              <p className="text-app-text-secondary">Map data could not be loaded.</p>
              <button type="button" onClick={handleMapRetry} className="shrink-0 border border-app-border/35 bg-app-surface px-3 py-2 text-app-text hover:bg-app-surface-muted">
                Retry map loading
              </button>
            </div>
          )}
        </header>
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
                <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-app-text-muted">{title}</p>
                <h2 id="map-quiz-rules-title" className="mt-1 text-xl font-bold">
                  {mode === 'powiaty' ? 'Daily game rules' : 'How to play'}
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
                      <p className="mt-2 text-sm text-app-text-secondary">Loading aggregate performance…</p>
                    ) : dailyStatsError ? (
                      <p className="mt-2 text-sm text-app-text-secondary">Aggregate performance is temporarily unavailable.</p>
                    ) : dailyStats ? (
                      <div className="mt-2 space-y-1 text-sm text-app-text-secondary">
                        <p>{dailyStats.completed_count ?? '—'} completed</p>
                        <p>Average score: {dailyStats.average_score ?? 'Not enough completed runs yet'}</p>
                        <p>Score distribution: {
                          dailyStats.score_distribution
                            ? Object.entries(dailyStats.score_distribution).sort(([a], [b]) => Number(a) - Number(b)).map(([scoreValue, count]) => `${scoreValue}: ${count}`).join(' · ') || 'Not available yet'
                            : 'Not available yet'
                        }</p>
                      </div>
                    ) : null}
                  </section>
                  <section aria-label="Your private score history" className="border border-app-border/35 p-3">
                    <h3 className="font-semibold">Your private score history</h3>
                    {privateHistoryLoading ? (
                      <p className="mt-2 text-sm text-app-text-secondary">Loading your history…</p>
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
                <li>Each run is a repeatable round of 10 US States.</li>
                <li>Correct answers earn one point and turn green. Wrong answers add no point and reveal the correct State in red.</li>
                <li>When a run is complete, choose Start another run to play again.</li>
              </ul>
            )}
          </section>
        </div>
      )}
    </main>
  );
}
