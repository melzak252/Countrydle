import { useEffect, useState, useMemo } from 'react';
import { useSearchParams, Link } from 'react-router-dom';

import {
  Route,
  ArrowRight,
  RotateCcw,
  Undo2,
  Trophy,
  Share2,
  Check,
  Sparkles,
  MapPin,
  AlertCircle,
  Loader2,
  Globe,
  ExternalLink,
  Search,
} from 'lucide-react';
import toast from 'react-hot-toast';
import { exploreService, type BorderHopChallenge, type BorderHopMode, type BorderHopVerification } from '../services/api';

type HopMode = BorderHopMode;

const HOP_MODE_LABELS: Record<HopMode, string> = {
  countries: 'World Countries',
  us_states: 'US States',
  powiaty: 'Powiaty',
};

function normalizeTerritoryName(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/ł/g, 'l');
}

function getErrorDetail(err: unknown): string | undefined {
  if (err && typeof err === 'object' && 'response' in err) {
    const res = err.response;
    if (res && typeof res === 'object' && 'data' in res) {
      const data = res.data;
      if (data && typeof data === 'object' && 'detail' in data && typeof data.detail === 'string') {
        return data.detail;
      }
    }
  }
  return undefined;
}

export default function BorderHopPage() {
  
  
  const [searchParams, setSearchParams] = useSearchParams();

  // Mode from URL query or default
  const urlMode = searchParams.get('mode');
  const mode: HopMode = urlMode === 'us_states' || urlMode === 'powiaty' ? urlMode : 'countries';
  const modeLabel = HOP_MODE_LABELS[mode];

  const urlStart = searchParams.get('start');
  const urlTarget = searchParams.get('target');

  // Game state
  const [challenge, setChallenge] = useState<BorderHopChallenge | null>(null);
  const [path, setPath] = useState<string[]>([]);
  const [availableNeighbors, setAvailableNeighbors] = useState<string[]>([]);
  const [loadingChallenge, setLoadingChallenge] = useState<boolean>(true);
  const [loadingNeighbors, setLoadingNeighbors] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const [status, setStatus] = useState<'playing' | 'won' | 'error'>('playing');
  const [verification, setVerification] = useState<BorderHopVerification | null>(null);
  const [searchFilter, setSearchFilter] = useState<string>('');
  const [copied, setCopied] = useState<boolean>(false);

  const currentLocation = path.length > 0 ? path[path.length - 1] : null;

  // 1. Load or fetch challenge
  const fetchChallenge = async (customParams?: {
    mode?: HopMode;
    start?: string;
    target?: string;
    seed?: string;
  }) => {
    setLoadingChallenge(true);
    setError(null);
    setStatus('playing');
    setVerification(null);
    setCopied(false);
    setSearchFilter('');

    const targetMode = customParams?.mode || mode;
    const originParam = customParams?.start || urlStart || undefined;
    const targetParam = customParams?.target || urlTarget || undefined;
    const seedParam = customParams?.seed || undefined;

    try {
      const data = await exploreService.getBorderHopChallenge({
        mode: targetMode,
        origin: originParam,
        target: targetParam,
        seed: seedParam,
      });

      if (!data.connected || !data.start) {
        setError(
          data.message ||
            ('Unable to establish a land-border connection for this target.')
        );
        setStatus('error');
        setChallenge(data);
        setPath([]);
        setAvailableNeighbors([]);
        return;
      }

      setChallenge(data);
      const initialPath = [data.start];
      setPath(initialPath);

      // Load neighbors for starting position
      await loadNeighbors(data.start, targetMode);
    } catch (err: unknown) {
      const detail = getErrorDetail(err);
      setError(
        detail ||
          ('Failed to load border hop challenge. Please try another route.')
      );
      setStatus('error');
    } finally {
      setLoadingChallenge(false);
    }
  };

  // 2. Load neighbors for a given territory
  const loadNeighbors = async (territory: string, activeMode: HopMode) => {
    setLoadingNeighbors(true);
    try {
      const res = await exploreService.getBorderNeighbors(territory, activeMode);
      setAvailableNeighbors(res.neighbors || []);
    } catch {
      setAvailableNeighbors([]);
    } finally {
      setLoadingNeighbors(false);
    }
  };

  // Initial load
  useEffect(() => {
    fetchChallenge();
  }, [mode, urlStart, urlTarget]);

  // Handle hopping to neighbor
  const handleSelectNeighbor = async (nextTerritory: string) => {
    if (status !== 'playing' || !challenge) return;

    const newPath = [...path, nextTerritory];
    setPath(newPath);
    setSearchFilter('');

    if (normalizeTerritoryName(nextTerritory) === normalizeTerritoryName(challenge.target)) {
      setStatus('won');
      try {
        const verifyRes = await exploreService.verifyBorderHop({
          mode,
          start: challenge.start!,
          target: challenge.target,
          path: newPath,
        });
        setVerification(verifyRes);
      } catch {
        // Fallback calculation
        const userHops = newPath.length - 1;
        const optHops = challenge.optimal_hops ?? userHops;
        setVerification({
          valid: true,
          hops: userHops,
          optimal_hops: optHops,
          is_optimal: userHops === optHops,
          rank: userHops === optHops ? 'gold' : userHops <= optHops + 2 ? 'silver' : 'bronze',
          optimal_path: challenge.optimal_path,
        });
      }
    } else {
      await loadNeighbors(nextTerritory, mode);
    }
  };

  // Undo one step
  const handleUndo = async () => {
    if (path.length <= 1) return;
    const newPath = path.slice(0, -1);
    const prevLocation = newPath[newPath.length - 1];
    setPath(newPath);
    setStatus('playing');
    setVerification(null);
    await loadNeighbors(prevLocation, mode);
  };

  // Reset route to origin
  const handleReset = async () => {
    if (!challenge?.start) return;
    const initialPath = [challenge.start];
    setPath(initialPath);
    setStatus('playing');
    setVerification(null);
    await loadNeighbors(challenge.start, mode);
  };

  // Mode switcher
  const handleModeChange = (newMode: HopMode) => {
    if (newMode === mode) return;
    setSearchParams({ mode: newMode });
  };

  // New random practice route
  const handleNewRandomRoute = () => {
    const randomSeed = Math.random().toString(36).substring(2, 9);
    setSearchParams({ mode });
    fetchChallenge({ mode, seed: randomSeed });
  };

  // Reset to daily puzzle
  const handleDailyRoute = () => {
    setSearchParams({ mode });
    fetchChallenge({ mode });
  };

  const filteredNeighbors = useMemo(() => {
    const query = normalizeTerritoryName(searchFilter);
    if (!query) return availableNeighbors;
    return availableNeighbors.filter((neighbor) => normalizeTerritoryName(neighbor).includes(query));
  }, [availableNeighbors, searchFilter]);


  // Share result generator
  const handleCopyResult = async () => {
    if (!challenge) return;
    const hops = path.length - 1;
    const optHops = challenge.optimal_hops ?? hops;
    const rankEmoji = hops === optHops ? '🥇' : hops <= optHops + 2 ? '🥈' : '🥉';
    const hopBoxes = Array.from({ length: hops }, () => '🟩').join(' ➔ ');

    const shareText = [
      `Countrydle Border Hop (${modeLabel})`,
      `${challenge.start} ➔ ${challenge.target}`,
      `Hops: ${hops} (Optimal: ${optHops}) ${rankEmoji}`,
      hopBoxes,
      `https://countrydle.online/border-hop?mode=${mode}`,
    ].join('\n');

    try {
      await navigator.clipboard.writeText(shareText);
      setCopied(true);
      toast.success('Copied result to clipboard!');
      setTimeout(() => setCopied(false), 2500);
    } catch {
      toast.error('Failed to copy');
    }
  };

  const currentHops = path.length > 0 ? path.length - 1 : 0;
  const optimalHops = challenge?.optimal_hops ?? '?';

  return (
    <div className="mx-auto max-w-4xl px-3 sm:px-6 py-3.5 sm:py-8 space-y-4 sm:space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 sm:gap-4 border-b border-app-border/25 pb-3.5 sm:pb-5">
        <div>
          <div className="flex items-center gap-2 sm:gap-2.5">
            <Route className="text-app-accent shrink-0" size={22} />
            <h1 className="font-mono text-xl sm:text-3xl font-bold tracking-tight text-app-text">
              {'Border Hop'}
            </h1>
            <span className="px-2 py-0.5 font-mono text-xs font-semibold text-app-accent shrink-0">
              {'Mini-Game'}
            </span>
          </div>
          <p className="mt-1 text-xs sm:text-sm text-app-text-secondary">
            {'Navigate from start to target exclusively across bordering territories in the fewest hops possible.'}
          </p>
        </div>

        {/* Mode Selector Tabs */}
        <div className="grid grid-cols-3 sm:flex items-center gap-1 sm:gap-1.5 p-1 rounded-sm bg-app-surface-muted border border-app-border/30 w-full sm:w-auto shrink-0">
          <button
            type="button"
            aria-pressed={mode === 'countries'}
            onClick={() => handleModeChange('countries')}
            className={`px-2.5 sm:px-3 py-1.5 rounded-xs text-xs font-semibold font-mono text-center transition-colors ${
              mode === 'countries'
                ? 'bg-app-accent text-white shadow-xs'
                : 'text-app-text-secondary hover:text-app-text'
            }`}
          >
            {HOP_MODE_LABELS.countries}
          </button>
          <button
            type="button"
            aria-pressed={mode === 'us_states'}
            onClick={() => handleModeChange('us_states')}
            className={`px-2.5 sm:px-3 py-1.5 rounded-xs text-xs font-semibold font-mono text-center transition-colors ${
              mode === 'us_states'
                ? 'bg-app-accent text-white shadow-xs'
                : 'text-app-text-secondary hover:text-app-text'
            }`}
          >
            {HOP_MODE_LABELS.us_states}
          </button>
          <button
            type="button"
            aria-pressed={mode === 'powiaty'}
            aria-label="Powiaty (Polish counties)"
            title="Polish county borders"
            onClick={() => handleModeChange('powiaty')}
            className={`px-2.5 sm:px-3 py-1.5 rounded-xs text-xs font-semibold font-mono text-center transition-colors ${
              mode === 'powiaty'
                ? 'bg-app-accent text-white shadow-xs'
                : 'text-app-text-secondary hover:text-app-text'
            }`}
          >
            {HOP_MODE_LABELS.powiaty}
          </button>
        </div>
      </div>

      {/* Loading state */}
      {loadingChallenge ? (
        <div className="rounded-sm border border-app-border/25 bg-app-surface-raised p-8 sm:p-12 text-center space-y-3">
          <Loader2 className="mx-auto h-7 w-7 sm:h-8 sm:w-8 animate-spin text-app-accent" />
          <p className="font-mono text-xs sm:text-sm text-app-text-secondary">
            {'Generating border path challenge...'}
          </p>
        </div>
      ) : error ? (
        /* Error or Island notice */
        <div className="rounded-sm border border-amber-300 bg-amber-50 p-4 sm:p-6 space-y-3 sm:space-y-4 text-left">
          <div className="flex items-start gap-2.5 sm:gap-3">
            <AlertCircle className="text-amber-800 shrink-0 mt-0.5" size={18} />
            <div className="space-y-1">
              <h3 className="font-mono text-sm font-semibold text-app-text">
                {'Route Unavailable'}
              </h3>
              <p className="text-xs sm:text-sm text-app-text-secondary">{error}</p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2 pt-1 sm:pt-2">
            <button
              type="button"
              onClick={handleNewRandomRoute}
              className="inline-flex items-center gap-1.5 rounded-sm bg-app-accent px-3 py-1.5 sm:px-3.5 sm:py-2 text-xs font-bold text-white hover:bg-app-accent-hover"
            >
              <Sparkles size={14} className="shrink-0" />
              <span>{'Try Another Random Route'}</span>
            </button>
            <button
              type="button"
              onClick={handleDailyRoute}
              className="inline-flex items-center gap-1.5 rounded-sm border border-app-border/30 bg-app-surface-raised px-3 py-1.5 sm:px-3.5 sm:py-2 text-xs font-semibold text-app-text-secondary hover:bg-app-surface-muted"
            >
              <Globe size={14} className="shrink-0" />
              <span>{"Today's Daily Route"}</span>
            </button>
          </div>
        </div>
      ) : challenge ? (
        <div className="space-y-3 sm:space-y-5">
          {/* Mission Banner */}
          <div className="rounded-sm border border-app-border/25 bg-app-surface-raised p-3 sm:p-5 flex flex-col md:flex-row md:items-center md:justify-between gap-3 sm:gap-4">
            <div className="space-y-1 sm:space-y-1.5 min-w-0">
              <span className="font-mono text-xs font-semibold text-app-accent block">
                {'Route Objective'}
              </span>
              <div className="flex flex-wrap items-center gap-1.5 sm:gap-3 text-xs sm:text-base md:text-xl font-bold font-mono text-app-text min-w-0">
                <span className="max-w-full bg-app-surface-muted border border-app-border/25 px-2 sm:px-2.5 py-1 rounded-xs text-app-text break-words [overflow-wrap:anywhere]">
                  {challenge.start}
                </span>
                <div className="inline-flex max-w-full items-center gap-1.5 sm:gap-3 min-w-0">
                  <ArrowRight size={14} className="text-app-accent shrink-0 sm:hidden" />
                  <ArrowRight size={18} className="text-app-accent shrink-0 hidden sm:inline-block" />
                  <span className="max-w-full bg-app-accent/10 border border-app-accent/30 text-app-accent px-2 sm:px-2.5 py-1 rounded-xs break-words [overflow-wrap:anywhere]">
                    {challenge.target}
                  </span>
                </div>
              </div>
            </div>

            {/* Score & Hop Benchmark Badges */}
            <div className="grid grid-cols-2 gap-2 sm:flex sm:items-center sm:gap-3 shrink-0">
              <div className="rounded-sm bg-app-surface-muted border border-app-border/25 px-2.5 sm:px-3 py-1.5 sm:py-2 text-center sm:min-w-24">
                <span className="block text-xs font-mono text-app-text-muted">
                  {'Your Hops'}
                </span>
                <span className="font-mono text-base sm:text-lg font-bold text-app-text">{currentHops}</span>
              </div>

              <div className="rounded-sm bg-app-accent/10 border border-app-accent/30 px-2.5 sm:px-3 py-1.5 sm:py-2 text-center sm:min-w-24">
                <span className="block text-xs font-mono text-app-accent">
                  {'Optimal'}
                </span>
                <span className="font-mono text-base sm:text-lg font-bold text-app-accent">{optimalHops}</span>
              </div>
            </div>
          </div>

          {/* Action Toolbar */}
          <div className="flex flex-wrap items-center justify-between gap-2 sm:gap-2.5 text-xs">
            <div className="flex items-center gap-1.5 sm:gap-2">
              <button
                type="button"
                onClick={handleUndo}
                disabled={path.length <= 1 || status === 'won'}
                className="inline-flex items-center gap-1 sm:gap-1.5 px-2.5 sm:px-3 py-1 sm:py-1.5 rounded-sm border border-app-border/30 bg-app-surface-raised text-app-text-secondary hover:bg-app-surface-muted hover:text-app-text disabled:text-app-text-muted disabled:opacity-100 disabled:cursor-not-allowed transition-colors"
                title={'Undo last hop'}
              >
                <Undo2 size={13} className="shrink-0" />
                <span>{'Undo Hop'}</span>
              </button>

              <button
                type="button"
                onClick={handleReset}
                disabled={path.length <= 1 || status === 'won'}
                className="inline-flex items-center gap-1 sm:gap-1.5 px-2.5 sm:px-3 py-1 sm:py-1.5 rounded-sm border border-app-border/30 bg-app-surface-raised text-app-text-secondary hover:bg-app-surface-muted hover:text-app-text disabled:text-app-text-muted disabled:opacity-100 disabled:cursor-not-allowed transition-colors"
                title={'Reset to starting territory'}
              >
                <RotateCcw size={13} className="shrink-0" />
                <span>{'Reset'}</span>
              </button>
            </div>

            <div className="flex items-center gap-1.5 sm:gap-2">
              <button
                type="button"
                onClick={handleDailyRoute}
                className="inline-flex items-center gap-1 sm:gap-1.5 px-2.5 sm:px-3 py-1 sm:py-1.5 rounded-sm border border-app-border/30 bg-app-surface-raised text-app-text-secondary hover:bg-app-surface-muted hover:text-app-text transition-colors"
              >
                <Globe size={13} className="shrink-0" />
                <span>{'Daily Challenge'}</span>
              </button>

              <button
                type="button"
                onClick={handleNewRandomRoute}
                className="inline-flex items-center gap-1 sm:gap-1.5 px-2.5 sm:px-3 py-1 sm:py-1.5 rounded-sm border border-app-border/30 bg-app-surface-raised text-app-text-secondary hover:bg-app-surface-muted hover:text-app-text transition-colors font-medium"
              >
                <Sparkles size={13} className="text-app-accent shrink-0" />
                <span>{'New Random Route'}</span>
              </button>
            </div>
          </div>

          {/* Path Trail (Breadcrumbs) */}
          <div className="rounded-sm border border-app-border/25 bg-app-surface-raised p-2.5 sm:p-3.5 space-y-1.5 sm:space-y-2 text-left">
            <span className="font-mono text-[10px] font-bold uppercase tracking-wider text-app-text-muted block">
              {`Your Path Trail (${path.length} locations)`}
            </span>
            <div className="flex flex-wrap items-center gap-1 sm:gap-1.5">
              {path.map((step, idx) => {
                const isCurrent = idx === path.length - 1;
                const isTarget = normalizeTerritoryName(step) === normalizeTerritoryName(challenge.target);
                const isStart = idx === 0;

                return (
                  <div key={`${step}-${idx}`} className="flex items-center gap-1 sm:gap-1.5 max-w-full">
                    <span
                      className={`inline-flex items-center gap-1 px-2 sm:px-2.5 py-0.5 sm:py-1 rounded-xs font-mono text-xs font-semibold max-w-full break-words [overflow-wrap:anywhere] ${
                        isCurrent
                          ? isTarget
                            ? 'bg-app-accent text-white ring-2 ring-app-accent/30'
                            : 'bg-app-accent/10 text-app-accent border border-app-accent/40'
                          : isStart
                          ? 'bg-app-surface-muted text-app-text border border-app-border/25'
                          : 'bg-app-surface-raised border border-app-border/25 text-app-text-secondary'
                      }`}
                    >
                      <MapPin size={11} className={`shrink-0 ${isCurrent ? 'text-app-accent' : 'text-app-text-muted'}`} />
                      <span className="break-words [overflow-wrap:anywhere]">{step}</span>
                    </span>
                    {idx < path.length - 1 && <ArrowRight size={12} className="text-app-text-muted shrink-0" />}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Victory Debrief Modal / Card */}
          {status === 'won' && verification && (
            <div className="rounded-sm border-2 border-app-accent/50 bg-app-surface-raised p-4 sm:p-6 text-left space-y-4 sm:space-y-5 animate-in fade-in zoom-in-95 duration-200">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-app-border/25 pb-3 sm:pb-4">
                <div className="flex items-center gap-2.5 sm:gap-3">
                  <div className="rounded-sm bg-app-accent/10 border border-app-accent/30 p-2 sm:p-2.5 text-app-accent shrink-0">
                    <Trophy size={22} className="sm:w-6 sm:h-6" />
                  </div>
                  <div>
                    <h2 className="font-mono text-lg sm:text-2xl font-bold text-app-text">
                      {'Route Completed!'}
                    </h2>
                    <p className="text-xs sm:text-sm text-app-accent font-semibold font-mono">
                      {verification.rank === 'gold'
                        ? '🥇 Gold Route — Shortest Possible Path!'
                        : verification.rank === 'silver'
                        ? '🥈 Silver Route — Great Navigation!'
                        : '🥉 Bronze Route — Scenic Detour!'}
                    </p>
                  </div>
                </div>

                {/* Score Summary */}
                <div className="grid grid-cols-2 gap-2 sm:flex sm:items-center sm:gap-3 w-full sm:w-auto self-start sm:self-auto">
                  <div className="rounded-sm bg-app-surface-muted border border-app-border/25 px-2.5 sm:px-3 py-1.5 text-center">
                    <span className="block text-[10px] font-mono uppercase text-app-text-muted">
                      {'Hops Taken'}
                    </span>
                    <span className="font-mono text-sm sm:text-base font-bold text-app-text">{verification.hops}</span>
                  </div>
                  <div className="rounded-sm bg-app-accent/10 border border-app-accent/30 px-2.5 sm:px-3 py-1.5 text-center">
                    <span className="block text-[10px] font-mono uppercase text-app-accent">
                      {'Optimal'}
                    </span>
                    <span className="font-mono text-sm sm:text-base font-bold text-app-accent">
                      {verification.optimal_hops}
                    </span>
                  </div>
                </div>
              </div>

              {/* Path Reveal Comparison */}
              {verification.optimal_path && (
                <div className="space-y-1.5 sm:space-y-2 text-xs">
                  <span className="font-mono text-[10px] sm:text-[11px] font-bold uppercase tracking-wider text-app-text-muted block">
                    {'Optimal Shortest Path:'}
                  </span>
                  <div className="p-2.5 sm:p-3 rounded-sm bg-app-surface-muted border border-app-border/25 font-mono text-app-text-secondary flex flex-wrap items-center gap-1.5">
                    {verification.optimal_path.map((node, i) => (
                      <span key={node} className="inline-flex items-center gap-1 max-w-full">
                        <span className="font-semibold text-app-accent break-words [overflow-wrap:anywhere]">{node}</span>
                        {i < verification.optimal_path!.length - 1 && (
                          <ArrowRight size={11} className="text-app-text-muted shrink-0" />
                        )}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Action Buttons */}
              <div className="flex flex-wrap items-center gap-2 sm:gap-3 pt-1 sm:pt-2">
                <button
                  type="button"
                  onClick={handleCopyResult}
                  className="flex items-center gap-2 rounded-sm bg-app-accent px-3.5 sm:px-4 py-2 sm:py-2.5 text-xs font-bold text-white hover:bg-app-accent-hover transition-colors shadow-sm cursor-pointer"
                >
                  {copied ? <Check size={14} /> : <Share2 size={14} />}
                  <span>{copied ? ('Copied!') : ('Share Result')}</span>
                </button>

                <button
                  type="button"
                  onClick={handleNewRandomRoute}
                  className="flex items-center gap-2 rounded-sm border border-app-border/30 bg-app-surface-raised px-3.5 sm:px-4 py-2 sm:py-2.5 text-xs font-semibold text-app-text-secondary hover:bg-app-surface-muted transition-colors cursor-pointer"
                >
                  <Sparkles size={14} className="text-app-accent shrink-0" />
                  <span>{'Play Another Route'}</span>
                </button>

                <Link
                  to="/explore"
                  className="flex items-center gap-1.5 rounded-sm border border-app-border/30 bg-app-surface-raised px-3.5 sm:px-4 py-2 sm:py-2.5 text-xs font-semibold text-app-text-secondary hover:bg-app-surface-muted transition-colors"
                >
                  <span className="break-words [overflow-wrap:anywhere]">
                    {`Explore ${challenge.target} in Atlas`}
                  </span>
                  <ExternalLink size={13} className="shrink-0" />
                </Link>

                <Link
                  to={mode === 'us_states' ? '/us-states' : mode === 'powiaty' ? '/powiaty' : '/game'}
                  className="text-xs text-app-text-secondary hover:text-app-text w-full sm:w-auto sm:ml-auto flex items-center justify-start sm:justify-end gap-1 pt-1 sm:pt-0 transition-colors"
                >
                  <span>{'Back to Daily Game'}</span>
                  <ArrowRight size={13} className="shrink-0" />
                </Link>
              </div>
            </div>
          )}

          {/* Active Hop Dock (When still playing) */}
          {status === 'playing' && currentLocation && (
            <div className="rounded-sm border border-app-border/25 bg-app-surface-raised p-3 sm:p-5 text-left space-y-3 sm:space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 sm:gap-2.5 border-b border-app-border/25 pb-2.5 sm:pb-3">
                <div className="space-y-0.5 min-w-0">
                  <span className="font-mono text-[10px] uppercase font-bold tracking-wider text-app-accent block">
                    {'Next Border Hop'}
                  </span>
                  <p className="text-xs sm:text-sm font-semibold text-app-text font-mono break-words [overflow-wrap:anywhere]">
                    {(
                      <>
                        You are in: <strong className="text-app-accent">{currentLocation}</strong>. Choose next
                        bordering territory:
                      </>
                    )}
                  </p>
                </div>

                {/* Search Filter Input */}
                {(availableNeighbors.length > 5 || mode === 'powiaty') && (
                  <div className="relative w-full sm:w-56">
                    <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 text-app-text-muted" size={13} />
                    <input
                      type="text"
                      value={searchFilter}
                      aria-label={mode === 'powiaty' ? 'Szukaj sąsiadów' : 'Filter neighbors'}
                      onChange={(e) => setSearchFilter(e.target.value)}
                      placeholder={mode === 'powiaty' ? 'Szukaj sąsiadów...' : 'Filter neighbors...'}
                      className="w-full rounded-sm border border-app-border/35 bg-app-surface-raised py-1.5 pl-8 pr-3 text-xs text-app-text placeholder:text-app-text-muted focus:border-app-focus focus:outline-hidden focus:ring-1 focus:ring-app-focus/20"
                    />
                  </div>
                )}
              </div>

              {/* Neighbors Grid */}
              {loadingNeighbors ? (
                <div className="py-6 text-center text-xs text-app-text-secondary font-mono flex items-center justify-center gap-2">
                  <Loader2 size={14} className="animate-spin text-app-accent" />
                  <span>{'Fetching bordering neighbors...'}</span>
                </div>
              ) : filteredNeighbors.length === 0 ? (
                <div className="py-6 text-center text-xs text-app-text-secondary font-mono">
                  {searchFilter
                    ? 'No bordering neighbors match your search.'
                    : 'No bordering neighbors found (dead end).'}
                </div>
              ) : (
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-1.5 sm:gap-2">
                  {filteredNeighbors.map((neighbor) => {
                    const isTarget = normalizeTerritoryName(neighbor) === normalizeTerritoryName(challenge.target);
                    const alreadyVisited = path.includes(neighbor);

                    return (
                      <button
                        key={neighbor}
                        type="button"
                        onClick={() => handleSelectNeighbor(neighbor)}
                        title={neighbor}
                        className={`group relative flex items-center justify-between p-2 sm:p-2.5 rounded-sm border text-left transition-colors cursor-pointer min-w-0 ${
                          isTarget
                            ? 'bg-app-accent/10 border-app-accent/50 hover:bg-app-accent/15 text-app-accent'
                            : alreadyVisited
                            ? 'bg-app-surface-muted border-app-border/20 hover:border-app-border/35 text-app-text-muted'
                            : 'bg-app-surface-raised border-app-border/30 hover:border-app-accent/50 hover:bg-app-surface-muted text-app-text'
                        }`}
                      >
                        <span className="font-mono text-xs font-semibold break-words [overflow-wrap:anywhere] min-w-0 pr-1 sm:pr-2 leading-tight">{neighbor}</span>
                        {isTarget ? (
                          <span className="shrink-0 rounded-sm bg-app-accent px-1.5 py-0.5 font-mono text-[9px] font-bold text-white uppercase">
                            {'Target'}
                          </span>
                        ) : (
                          <ArrowRight
                            size={12}
                            className="text-app-text-muted group-hover:text-app-accent transition-colors shrink-0"
                          />
                        )}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}
