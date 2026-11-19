import { type FormEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ChevronDown, ChevronUp, Loader2, RotateCcw, Undo2 } from 'lucide-react';
import { useSearchParams } from 'react-router-dom';
import { ControlledPowiatyMap } from '../components/PowiatyMap';
import { ControlledUSStatesMap } from '../components/USStatesMap';
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

export default function MapBorderHopPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const mode = parseMapGameMode(searchParams.get('mode'));
  const [challengeRevision, setChallengeRevision] = useState(0);
  const [challenge, setChallenge] = useState<BorderHopChallenge | null>(null);
  const [path, setPath] = useState<string[]>([]);
  const [availableNeighbors, setAvailableNeighbors] = useState<string[]>([]);
  const [loadingChallenge, setLoadingChallenge] = useState(true);
  const [loadingNeighbors, setLoadingNeighbors] = useState(false);
  const [status, setStatus] = useState<'playing' | 'verifying' | 'won' | 'invalid'>('playing');
  const [verification, setVerification] = useState<BorderHopVerification | null>(null);
  const [routeError, setRouteError] = useState<string | null>(null);
  const [neighborError, setNeighborError] = useState<string | null>(null);
  const [typedName, setTypedName] = useState('');
  const [feedback, setFeedback] = useState<string | null>(null);
  const [controlsCollapsed, setControlsCollapsed] = useState(false);
  const requestId = useRef(0);
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
    setRouteError(null);
    setNeighborError(null);
    setTypedName('');
    setFeedback(null);

    const loadChallenge = async () => {
      try {
        const nextChallenge = await exploreService.getBorderHopChallenge({ mode });
        if (requestId.current !== activeRequestId) return;
        if (!nextChallenge.connected || !nextChallenge.start) {
          setChallenge(nextChallenge);
          setRouteError(nextChallenge.message || 'Could not find a connected border route for this challenge.');
          return;
        }
        setChallenge(nextChallenge);
        setPath([nextChallenge.start]);
        await loadNeighbors(nextChallenge.start, activeRequestId);
      } catch {
        if (requestId.current === activeRequestId) {
          setRouteError('Could not load a Border Hop challenge. Please try again.');
        }
      } finally {
        if (requestId.current === activeRequestId) setLoadingChallenge(false);
      }
    };
    void loadChallenge();

    return () => {
      if (requestId.current === activeRequestId) requestId.current += 1;
    };
  }, [mode, challengeRevision, loadNeighbors]);

  const currentLocation = path[path.length - 1] ?? null;
  const optimalPath = getRevealedOptimalPath(verification);
  const mapInteraction = useMemo(
    () => createIsolatedMapInteraction(challenge
      ? mapBorderHopMarkings(path, challenge.start, challenge.target, optimalPath)
      : EMPTY_MARKINGS),
    [path, challenge?.start, challenge?.target, optimalPath],
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

    const nextPath = [...path, nextLocation];
    setPath(nextPath);
    setTypedName('');
    setFeedback(null);
    setNeighborError(null);
    focusInput();

    if (normalizeMapRegionName(nextLocation) === normalizeMapRegionName(challenge.target)) {
      setStatus('verifying');
      try {
        const result = await exploreService.verifyBorderHop({
          mode,
          start: challenge.start,
          target: challenge.target,
          path: nextPath,
        });
        if (requestId.current !== activeRequestId) return;
        if (result.valid) {
          setVerification(result);
          setStatus('won');
        } else {
          setStatus('invalid');
          setFeedback(result.message || 'The route could not be verified. Undo a step or reset and try again.');
        }
      } catch {
        if (requestId.current === activeRequestId) {
          setStatus('won');
          setFeedback('Route complete. Verification details are unavailable right now.');
        }
      }
      return;
    }

    await loadNeighbors(nextLocation, activeRequestId);
  };

  const handleUndo = async () => {
    if (!challenge?.start || path.length <= 1 || loadingNeighbors || status === 'verifying') return;
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
    if (!challenge?.start || loadingNeighbors || status === 'verifying') return;
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
                <p className="min-w-0 truncate"><span className="font-mono text-[10px] uppercase tracking-wide text-app-text-muted">Start</span> <span className="font-semibold text-app-text">{challenge.start || '—'}</span></p>
                <span aria-hidden="true" className="text-app-text-muted">→</span>
                <p className="min-w-0 truncate"><span className="font-mono text-[10px] uppercase tracking-wide text-app-text-muted">Target</span> <span className="font-semibold text-app-text">{challenge.target}</span></p>
                <p className="whitespace-nowrap font-mono text-xs text-app-text-secondary">Hops {Math.max(0, path.length - 1)}</p>
              </div>
            )}
          </div>

          <div className="flex flex-wrap gap-1.5">
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
            </div>
              </>
            )}
          </section>
        )}
      </div>
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
