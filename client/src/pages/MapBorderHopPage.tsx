import { type FormEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ChevronDown, ChevronUp, Loader2, RotateCcw, Trophy, Undo2 } from 'lucide-react';
import { useSearchParams } from 'react-router-dom';
import { ControlledPowiatyMap } from '../components/PowiatyMap';
import { ControlledUSStatesMap } from '../components/USStatesMap';
import { GameResultDashboard } from '../components/result-dashboard';
import { useDailyDate } from '../hooks/useDailyClock';
import { exploreService, type BorderHopChallenge, type BorderHopVerification } from '../services/api';
import {
  getRevealedOptimalPath,
  mapBorderHopMarkings,
  matchTypedNeighbor,
  resetMapBorderHop,
  undoMapBorderHop,
} from '../lib/mapBorderHop';
import { createIsolatedMapInteraction } from '../lib/mapChallenge';
import { normalizeMapRegionName, parseMapGameMode, type MapGameMode } from '../lib/mapGameMode';

const EMPTY_MARKINGS = {};

interface StoredDailyBorderHop {
  start: string;
  target: string;
  path: string[];
  verification: BorderHopVerification | null;
}

function dailyStorageKey(mode: MapGameMode, today: string): string {
  return `map_border_hop_${mode}_${today}`;
}

function readStoredDaily(mode: MapGameMode, today: string): StoredDailyBorderHop | null {
  try {
    const raw = window.localStorage.getItem(dailyStorageKey(mode, today));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as StoredDailyBorderHop;
    if (!parsed?.start || !parsed?.target || !Array.isArray(parsed.path)) return null;
    return parsed;
  } catch {
    return null;
  }
}

function writeStoredDaily(mode: MapGameMode, today: string, payload: StoredDailyBorderHop): void {
  try {
    window.localStorage.setItem(dailyStorageKey(mode, today), JSON.stringify(payload));
  } catch {
    // Ignore storage quota errors
  }
}

function rankPoints(rank?: string | null): number {
  if (rank === 'gold') return 1000;
  if (rank === 'silver') return 700;
  if (rank === 'bronze') return 400;
  return 0;
}

export default function MapBorderHopPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const mode = parseMapGameMode(searchParams.get('mode'));
  const today = useDailyDate();
  const [challengeRevision, setChallengeRevision] = useState(0);
  const [challenge, setChallenge] = useState<BorderHopChallenge | null>(null);
  const [path, setPath] = useState<string[]>([]);
  const [availableNeighbors, setAvailableNeighbors] = useState<string[]>([]);
  const [loadingChallenge, setLoadingChallenge] = useState(true);
  const [loadingNeighbors, setLoadingNeighbors] = useState(false);
  const [status, setStatus] = useState<'playing' | 'verifying' | 'won' | 'invalid'>('playing');
  const [verification, setVerification] = useState<BorderHopVerification | null>(null);
  const [isResultDismissed, setIsResultDismissed] = useState(false);
  const [routeError, setRouteError] = useState<string | null>(null);
  const [neighborError, setNeighborError] = useState<string | null>(null);
  const [typedName, setTypedName] = useState('');
  const [feedback, setFeedback] = useState<string | null>(null);
  const [controlsCollapsed, setControlsCollapsed] = useState(false);
  const requestId = useRef(0);
  const startedAtRef = useRef<number | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const focusInput = useCallback(() => {
    requestAnimationFrame(() => {
      inputRef.current?.focus({ preventScroll: true });
    });
  }, []);

  const loadNeighbors = useCallback(async (name: string, expectedRequestId: number) => {
    setLoadingNeighbors(true);
    setNeighborError(null);
    try {
      const response = await exploreService.getBorderNeighbors(name, mode);
      if (requestId.current === expectedRequestId) setAvailableNeighbors(response.neighbors || []);
      return response.neighbors || [];
    } catch {
      if (requestId.current === expectedRequestId) {
        setAvailableNeighbors([]);
        setNeighborError('Could not load borders for this region. You can still undo or reset the route.');
      }
      return [];
    } finally {
      if (requestId.current === expectedRequestId) setLoadingNeighbors(false);
    }
  }, [mode]);

  useEffect(() => {
    const activeRequestId = ++requestId.current;
    setLoadingChallenge(true);
    setLoadingNeighbors(false);
    setChallenge(null);
    setPath([]);
    setAvailableNeighbors([]);
    setStatus('playing');
    setVerification(null);
    setIsResultDismissed(false);
    setRouteError(null);
    setNeighborError(null);
    setTypedName('');
    setFeedback(null);
    startedAtRef.current = null;

    const loadChallenge = async () => {
      try {
        const nextChallenge = await exploreService.getBorderHopChallenge({
          mode,
          seed: `daily-${today}`,
        });
        if (requestId.current !== activeRequestId) return;
        if (!nextChallenge.connected || !nextChallenge.start) {
          setChallenge(nextChallenge);
          setRouteError(nextChallenge.message || 'Could not find a connected border route for this challenge.');
          return;
        }
        setChallenge(nextChallenge);

        const stored = readStoredDaily(mode, today);
        if (
          stored &&
          normalizeMapRegionName(stored.start) === normalizeMapRegionName(nextChallenge.start) &&
          normalizeMapRegionName(stored.target) === normalizeMapRegionName(nextChallenge.target)
        ) {
          setPath(stored.path);
          setVerification(stored.verification);
          setStatus('won');
          return;
        }

        setPath([nextChallenge.start]);
        await loadNeighbors(nextChallenge.start, activeRequestId);
      } catch {
        if (requestId.current === activeRequestId) {
          setRouteError('Could not load today’s Border Hop challenge. Please try again.');
        }
      } finally {
        if (requestId.current === activeRequestId) setLoadingChallenge(false);
      }
    };
    void loadChallenge();

    return () => {
      if (requestId.current === activeRequestId) requestId.current += 1;
    };
  }, [mode, today, challengeRevision, loadNeighbors]);

  const currentLocation = path[path.length - 1] ?? null;
  const optimalPath = getRevealedOptimalPath(verification);
  const mapInteraction = useMemo(
    () => createIsolatedMapInteraction(challenge
      ? mapBorderHopMarkings(path, challenge.start, challenge.target, optimalPath)
      : EMPTY_MARKINGS),
    [path, challenge?.start, challenge?.target, optimalPath],
  );

  const completeRoute = useCallback(
    async (finalPath: string[], activeRequestId: number, autoCompletedNote?: string) => {
      if (!challenge?.start || !challenge.target) return;
      setPath(finalPath);
      setStatus('verifying');
      const elapsedSeconds =
        startedAtRef.current !== null
          ? Math.max(1, Math.round((Date.now() - startedAtRef.current) / 1000))
          : undefined;
      try {
        const result = await exploreService.verifyBorderHop({
          mode,
          start: challenge.start,
          target: challenge.target,
          path: finalPath,
          is_daily: true,
          elapsed_seconds: elapsedSeconds,
        });
        if (requestId.current !== activeRequestId) return;
        if (result.valid) {
          setVerification(result);
          setStatus('won');
          setIsResultDismissed(false);
          if (autoCompletedNote) setFeedback(autoCompletedNote);
          writeStoredDaily(mode, today, {
            start: challenge.start,
            target: challenge.target,
            path: finalPath,
            verification: result,
          });
        } else {
          setStatus('invalid');
          setFeedback(result.message || 'The route could not be verified. Undo a step or reset and try again.');
        }
      } catch {
        if (requestId.current === activeRequestId) {
          setStatus('won');
          setIsResultDismissed(false);
          setFeedback('Route complete. Verification details are unavailable right now.');
          writeStoredDaily(mode, today, {
            start: challenge.start,
            target: challenge.target,
            path: finalPath,
            verification: null,
          });
        }
      }
    },
    [challenge?.start, challenge?.target, mode, today],
  );

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!challenge?.start || !challenge.target || status !== 'playing' || loadingNeighbors || !currentLocation) return;

    const activeRequestId = requestId.current;
    const nextLocation = matchTypedNeighbor(typedName, availableNeighbors, path);
    if (!nextLocation) {
      setFeedback('That region is not an unvisited neighbor of your current location.');
      focusInput();
      return;
    }

    if (startedAtRef.current === null) {
      startedAtRef.current = Date.now();
    }

    const nextPath = [...path, nextLocation];
    setPath(nextPath);
    setTypedName('');
    setFeedback(null);
    setNeighborError(null);
    focusInput();

    if (normalizeMapRegionName(nextLocation) === normalizeMapRegionName(challenge.target)) {
      await completeRoute(nextPath, activeRequestId);
      return;
    }

    const nextNeighbors = await loadNeighbors(nextLocation, activeRequestId);
    if (requestId.current !== activeRequestId) return;

    // Auto-finish as soon as the player reaches a region bordering the destination
    const bordersTarget = nextNeighbors.some(
      (neighbor) => normalizeMapRegionName(neighbor) === normalizeMapRegionName(challenge.target),
    );
    if (bordersTarget) {
      const finalPath = [...nextPath, challenge.target];
      await completeRoute(
        finalPath,
        activeRequestId,
        `${nextLocation} borders ${challenge.target}, so your route is complete!`,
      );
    }
  };

  const handleUndo = async () => {
    if (!challenge?.start || path.length <= 1 || loadingNeighbors || status === 'verifying' || status === 'won') return;
    const previousPath = undoMapBorderHop(path);
    setPath(previousPath);
    setStatus('playing');
    setVerification(null);
    setTypedName('');
    setFeedback(null);
    setNeighborError(null);
    await loadNeighbors(previousPath[previousPath.length - 1], requestId.current);
  };

  const handleReset = async () => {
    if (!challenge?.start || loadingNeighbors || status === 'verifying' || status === 'won') return;
    const initialPath = resetMapBorderHop(challenge.start);
    setPath(initialPath);
    setStatus('playing');
    setVerification(null);
    setTypedName('');
    setFeedback(null);
    setNeighborError(null);
    await loadNeighbors(initialPath[0], requestId.current);
  };

  const handleModeChange = (nextMode: MapGameMode) => {
    setSearchParams({ mode: nextMode });
  };

  const handleNewRoute = () => setChallengeRevision((revision) => revision + 1);
  const retryNeighbors = () => {
    if (currentLocation) void loadNeighbors(currentLocation, requestId.current);
  };
  const title = mode === 'powiaty' ? 'Powiat Map Border Hop' : 'US State Map Border Hop';
  const mapClassName = 'h-full w-full rounded-none border-0 shadow-none';
  const mapElement = mode === 'powiaty'
    ? <ControlledPowiatyMap className={mapClassName} interaction={mapInteraction} hideUnlistedTooltips visibleRegionNames={path} showMapToolbar={false} />
    : <ControlledUSStatesMap className={mapClassName} interaction={mapInteraction} hideUnlistedTooltips visibleRegionNames={path} showMapToolbar={false} />;

  return (
    <main className="relative flex h-full min-h-0 flex-1 w-full overflow-hidden bg-app-canvas text-app-text">
      <section aria-label="Border Hop route map" className="absolute inset-0 z-0 w-full">
        {mapElement}
      </section>

      <div className="pointer-events-none relative z-[500] flex h-full min-h-0 w-full flex-col justify-between gap-2 px-2 py-2 sm:px-3 sm:py-3">
        <header
          aria-label="Border Hop status"
          className="pointer-events-auto mx-auto grid w-full max-w-5xl grid-cols-1 items-center gap-x-4 gap-y-2 border border-app-border/30 bg-app-surface/95 px-3 py-2 shadow-sm sm:px-4 md:grid-cols-[minmax(0,1fr)_auto]"
        >
          <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1">
            <div className="min-w-0">
              <h1 className="font-mono text-[10px] font-semibold uppercase tracking-[0.16em] text-app-text-muted">{title}</h1>
              {loadingChallenge && (
                <p role="status" className="mt-1 flex items-center gap-2 text-sm text-app-text-secondary">
                  <Loader2 size={15} className="animate-spin" aria-hidden="true" /> Loading route…
                </p>
              )}
            </div>
            {challenge && (
              <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1 text-xs sm:text-sm">
                <p className="min-w-0 truncate"><span className="font-mono text-[10px] uppercase tracking-wide text-app-text-muted">Start</span> <span className="font-semibold text-app-text">{challenge.start || '-'}</span></p>
                <span aria-hidden="true" className="text-app-text-muted">→</span>
                <p className="min-w-0 truncate"><span className="font-mono text-[10px] uppercase tracking-wide text-app-text-muted">Target</span> <span className="font-semibold text-app-text">{challenge.target}</span></p>
                <p className="whitespace-nowrap font-mono text-xs text-app-text-secondary">Hops {Math.max(0, path.length - 1)}</p>
              </div>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-1.5">
            {status === 'won' && (
              <button
                type="button"
                onClick={() => setIsResultDismissed(false)}
                className="inline-flex items-center gap-1.5 border border-app-accent bg-app-accent px-3 py-2 text-xs font-semibold text-app-canvas hover:bg-app-accent-hover cursor-pointer"
              >
                <Trophy size={13} aria-hidden="true" />
                <span>Results</span>
              </button>
            )}
            <ModeButton mode="powiaty" currentMode={mode} label="Powiaty" onSelect={handleModeChange} />
            <ModeButton mode="us_states" currentMode={mode} label="US States" onSelect={handleModeChange} />
          </div>
          {routeError && (
            <div role="alert" className="col-span-full flex flex-wrap items-center justify-between gap-2 text-sm">
              <p className="text-app-text-secondary">{routeError}</p>
              <button type="button" onClick={handleNewRoute} className="shrink-0 border border-app-border/35 bg-app-surface px-3 py-2 text-sm font-semibold text-app-text hover:bg-app-surface-muted">
                Try another route
              </button>
            </div>
          )}
        </header>

        {challenge && !routeError && (
          <section
            aria-label="Border Hop controls"
            className="pointer-events-auto mx-auto mt-auto max-h-[45vh] w-full max-w-5xl overflow-y-auto border border-app-border/30 bg-app-surface/95 px-3 py-2.5 shadow-sm sm:px-4 md:max-h-[38vh]"
          >
            <div className="mb-2 flex items-center justify-between gap-2">
              <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-app-text-muted">
                {currentLocation ? `Current: ${currentLocation}` : 'Route controls'}
                {path.length > 0 ? ` · ${path.length - 1} hops` : ''}
              </span>
              <button
                type="button"
                onClick={() => setControlsCollapsed((prev) => !prev)}
                aria-expanded={!controlsCollapsed}
                className="inline-flex items-center gap-1 rounded-sm border border-app-border/40 bg-app-surface-muted px-2 py-1 text-[11px] font-medium text-app-text-secondary hover:border-app-accent hover:text-app-text cursor-pointer"
              >
                {controlsCollapsed ? <ChevronUp size={13} aria-hidden="true" /> : <ChevronDown size={13} aria-hidden="true" />}
                <span>{controlsCollapsed ? 'Show controls' : 'Minimize to view map'}</span>
              </button>
            </div>

            {!controlsCollapsed && (
              <>
            {status === 'won' ? (
              <div role="status" className="mb-3 border-b border-app-border/20 pb-3">
                <p className="font-semibold text-app-accent">Route complete</p>
                <p className="mt-1 text-sm text-app-text-secondary">
                  {feedback || `You reached ${challenge.target} in ${verification?.hops ?? path.length - 1} hops.`}
                </p>
                {verification && (
                  <p className="mt-1 text-xs text-app-text-muted">
                    {verification.rank ? `${verification.rank} route` : 'Route verified'}
                    {verification.optimal_hops !== null ? ` · optimal ${verification.optimal_hops} hops` : ''}
                  </p>
                )}
                {optimalPath && <p className="mt-1 text-xs font-medium text-amber-900 dark:text-amber-200">The shortest route is shown in yellow.</p>}
              </div>
            ) : status === 'verifying' ? (
              <p role="status" className="mb-3 flex items-center gap-2 border-b border-app-border/20 pb-3 text-sm text-app-text-secondary">
                <Loader2 size={16} className="animate-spin" aria-hidden="true" /> Verifying route…
              </p>
            ) : status === 'invalid' ? (
              <p role="alert" className="mb-3 border-b border-app-border/20 pb-3 text-sm font-medium text-rose-700 dark:text-rose-300">
                {feedback || 'The route could not be verified. Undo a step or reset and try again.'}
              </p>
            ) : null}

            {status === 'playing' && (
              <form onSubmit={handleSubmit} className="flex flex-col gap-2 sm:flex-row sm:items-end">
                <div className="min-w-0 flex-1">
                  <label htmlFor="next-region" className="sr-only">
                    Next neighbor of {currentLocation || 'your current region'}
                  </label>
                  <input
                    ref={inputRef}
                    id="next-region"
                    autoComplete="off"
                    value={typedName}
                    onChange={(event) => setTypedName(event.target.value)}
                    placeholder="Type the next bordering region"
                    readOnly={loadingNeighbors || !currentLocation}
                    aria-busy={loadingNeighbors}
                    className="w-full border border-app-border/35 bg-app-surface px-3 py-2 text-sm text-app-text placeholder:text-app-text-muted focus:border-app-focus focus:outline-none focus:ring-2 focus:ring-app-focus/25 read-only:opacity-60"
                  />
                </div>
                <button
                  type="submit"
                  disabled={!typedName.trim() || loadingNeighbors || !currentLocation}
                  className="border border-app-accent/45 bg-app-accent/10 px-4 py-2 text-sm font-semibold text-app-accent hover:bg-app-accent/15 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {loadingNeighbors ? 'Loading borders…' : 'Add region'}
                </button>
              </form>
            )}

            {(feedback || neighborError) && status === 'playing' && (
              <p role="status" className="mt-2 text-sm font-medium text-rose-700 dark:text-rose-300">{feedback || neighborError}</p>
            )}
            {neighborError && status === 'playing' && (
              <button type="button" onClick={retryNeighbors} disabled={loadingNeighbors} className="mt-2 border border-app-border/35 bg-app-surface px-3 py-2 text-sm font-medium text-app-text-secondary hover:bg-app-surface-muted disabled:opacity-50">
                Retry border lookup
              </button>
            )}

            <div className="mt-3 flex flex-col gap-3 border-t border-app-border/20 pt-3 sm:flex-row sm:items-end sm:justify-between">
              <div className="min-w-0 flex-1">
                <h2 className="font-mono text-[10px] uppercase tracking-wide text-app-text-muted">Route so far · {Math.max(0, path.length - 1)} hops</h2>
                <ol aria-label="Visited route regions" className="mt-1.5 flex flex-wrap gap-1.5">
                  {path.map((name, index) => (
                    <li key={`${name}-${index}`} className="border border-app-border/30 bg-app-surface px-2 py-1 text-xs font-medium text-app-text-secondary">
                      {name}
                    </li>
                  ))}
                </ol>
              </div>
            {status !== 'won' && (
              <div className="flex shrink-0 gap-2">
                <button
                  type="button"
                  onClick={handleUndo}
                  disabled={path.length <= 1 || loadingNeighbors || status === 'verifying'}
                  className="inline-flex items-center justify-center gap-1.5 border border-app-border/35 bg-app-surface px-3 py-2 text-sm font-medium text-app-text-secondary hover:bg-app-surface-muted disabled:cursor-not-allowed disabled:opacity-45"
                >
                  <Undo2 size={15} aria-hidden="true" /> Undo
                </button>
                <button
                  type="button"
                  onClick={handleReset}
                  disabled={path.length <= 1 || loadingNeighbors || status === 'verifying'}
                  className="inline-flex items-center justify-center gap-1.5 border border-app-border/35 bg-app-surface px-3 py-2 text-sm font-medium text-app-text-secondary hover:bg-app-surface-muted disabled:cursor-not-allowed disabled:opacity-45"
                >
                  <RotateCcw size={15} aria-hidden="true" /> Reset
                </button>
              </div>
            )}
            </div>
              </>
            )}
          </section>
        )}
      </div>

      {status === 'won' && !isResultDismissed && challenge && (
        <GameResultDashboard
          variant="modal"
          mode={mode === 'powiaty' ? 'border_hop:powiaty' : 'border_hop:us_states'}
          modeKind="route"
          isDaily
          gameName={title}
          gamePath={`/map-border-hop?mode=${mode}`}
          date={today}
          won
          points={rankPoints(verification?.rank)}
          guessesMade={verification?.hops ?? Math.max(0, path.length - 1)}
          maxGuesses={verification?.optimal_hops ?? undefined}
          targetLabel="Daily Route"
          targetName={`${challenge.start} → ${challenge.target}`}
          subtitle={
            verification?.rank === 'gold'
              ? 'Gold Route: Shortest possible path!'
              : verification?.rank === 'silver'
              ? 'Silver Route: Great navigation!'
              : 'Route complete! Compare your path with the shortest route below.'
          }
          detailsTitle="Route Comparison"
          detailsSlot={
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 text-xs">
              <div className="space-y-2">
                <p className="font-mono text-[11px] font-semibold uppercase tracking-wider text-app-text-secondary">
                  Your Route ({verification?.hops ?? Math.max(0, path.length - 1)} hops)
                </p>
                <div className="flex flex-wrap items-center gap-1.5">
                  {path.map((step, i) => (
                    <span
                      key={`${step}-${i}`}
                      className="rounded-sm border border-app-border/60 bg-app-canvas px-2 py-1 font-medium text-app-text"
                    >
                      {step}
                    </span>
                  ))}
                </div>
              </div>
              {optimalPath && optimalPath.length > 0 && (
                <div className="space-y-2 lg:border-l lg:border-app-border/45 lg:pl-4">
                  <p className="font-mono text-[11px] font-semibold uppercase tracking-wider text-[#c68f42]">
                    Shortest Route ({verification?.optimal_hops ?? optimalPath.length - 1} hops)
                  </p>
                  <div className="flex flex-wrap items-center gap-1.5">
                    {optimalPath.map((step, i) => (
                      <span
                        key={`${step}-${i}`}
                        className="rounded-sm border border-[#c68f42]/40 bg-[#c68f42]/10 px-2 py-1 font-medium text-app-text"
                      >
                        {step}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          }
          onClose={() => setIsResultDismissed(true)}
          closeLabel="Inspect Route on Map"
        />
      )}
    </main>
  );
}

function ModeButton({
  mode,
  currentMode,
  label,
  onSelect,
}: {
  mode: MapGameMode;
  currentMode: MapGameMode;
  label: string;
  onSelect: (mode: MapGameMode) => void;
}) {
  const isSelected = mode === currentMode;
  return (
    <button
      type="button"
      aria-pressed={isSelected}
      onClick={() => onSelect(mode)}
      className={`border px-3 py-2 text-sm font-medium ${isSelected
        ? 'border-app-accent/45 bg-app-accent/10 text-app-accent'
        : 'border-app-border/30 bg-app-surface-raised text-app-text-secondary hover:bg-app-surface-muted'}`}
    >
      {label}
    </button>
  );
}
