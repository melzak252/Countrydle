import { useEffect, useState, useMemo } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
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
import { exploreService, type BorderHopChallenge, type BorderHopVerification } from '../services/api';

type HopMode = 'countries' | 'us_states';

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
  const { i18n } = useTranslation();
  const isPl = i18n.language.startsWith('pl');
  const [searchParams, setSearchParams] = useSearchParams();

  // Mode from URL query or default
  const urlMode = searchParams.get('mode');
  const mode: HopMode = urlMode === 'us_states' ? 'us_states' : 'countries';

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
            (isPl
              ? 'Nie można połączyć wybranych terytoriów drogą lądową.'
              : 'Unable to establish a land-border connection for this target.')
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
          (isPl
            ? 'Błąd podczas ładowania wyzwania. Wybierz inną trasę.'
            : 'Failed to load border hop challenge. Please try another route.')
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

    // Check if target reached
    if (nextTerritory.toLowerCase() === challenge.target.toLowerCase()) {
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

  // Filter neighbors based on search
  const filteredNeighbors = useMemo(() => {
    if (!searchFilter.trim()) return availableNeighbors;
    const q = searchFilter.toLowerCase();
    return availableNeighbors.filter((n) => n.toLowerCase().includes(q));
  }, [availableNeighbors, searchFilter]);

  // Share result generator
  const handleCopyResult = async () => {
    if (!challenge) return;
    const hops = path.length - 1;
    const optHops = challenge.optimal_hops ?? hops;
    const rankEmoji = hops === optHops ? '🥇' : hops <= optHops + 2 ? '🥈' : '🥉';
    const hopBoxes = Array.from({ length: hops }, () => '🟩').join(' ➔ ');

    const shareText = [
      `Countrydle Border Hop (${mode === 'us_states' ? 'US States' : 'World Countries'})`,
      `${challenge.start} ➔ ${challenge.target}`,
      `Hops: ${hops} (Optimal: ${optHops}) ${rankEmoji}`,
      hopBoxes,
      `https://countrydle.online/border-hop?mode=${mode}`,
    ].join('\n');

    try {
      await navigator.clipboard.writeText(shareText);
      setCopied(true);
      toast.success(isPl ? 'Skopiowano wynik do schowka!' : 'Copied result to clipboard!');
      setTimeout(() => setCopied(false), 2500);
    } catch {
      toast.error(isPl ? 'Nie udało się skopiować' : 'Failed to copy');
    }
  };

  const currentHops = path.length > 0 ? path.length - 1 : 0;
  const optimalHops = challenge?.optimal_hops ?? '?';

  return (
    <div className="mx-auto max-w-4xl px-3 sm:px-6 py-6 sm:py-8 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-white/10 pb-5">
        <div>
          <div className="flex items-center gap-2.5">
            <Route className="text-emerald-400" size={26} />
            <h1 className="font-mono text-2xl sm:text-3xl font-bold tracking-tight text-sand-100">
              {isPl ? 'Border Hop' : 'Border Hop'}
            </h1>
            <span className="rounded-full bg-emerald-500/10 border border-emerald-500/30 px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider text-emerald-400">
              {isPl ? 'Mini-gra' : 'Mini-Game'}
            </span>
          </div>
          <p className="mt-1 text-xs sm:text-sm text-zinc-400">
            {isPl
              ? 'Przejdź od terytorium startowego do docelowego wyłącznie przez bezpośrednio graniczące państwa lub stany.'
              : 'Navigate from start to target exclusively across bordering territories in the fewest hops possible.'}
          </p>
        </div>

        {/* Mode Selector Tabs */}
        <div className="flex items-center gap-1.5 p-1 rounded-sm bg-obsidian-900 border border-white/10 self-start sm:self-auto">
          <button
            type="button"
            onClick={() => handleModeChange('countries')}
            className={`px-3 py-1.5 rounded-xs text-xs font-semibold font-mono transition-colors ${
              mode === 'countries'
                ? 'bg-emerald-400 text-obsidian-950 shadow-xs'
                : 'text-zinc-400 hover:text-sand-100'
            }`}
          >
            {isPl ? 'Kraje Świata' : 'World Countries'}
          </button>
          <button
            type="button"
            onClick={() => handleModeChange('us_states')}
            className={`px-3 py-1.5 rounded-xs text-xs font-semibold font-mono transition-colors ${
              mode === 'us_states'
                ? 'bg-emerald-400 text-obsidian-950 shadow-xs'
                : 'text-zinc-400 hover:text-sand-100'
            }`}
          >
            {isPl ? 'Stany USA' : 'US States'}
          </button>
        </div>
      </div>

      {/* Loading state */}
      {loadingChallenge ? (
        <div className="rounded-sm border border-white/10 bg-obsidian-900/40 p-12 text-center space-y-3">
          <Loader2 className="mx-auto h-8 w-8 animate-spin text-emerald-400" />
          <p className="font-mono text-sm text-zinc-300">
            {isPl ? 'Generowanie wyzwania granic...' : 'Generating border path challenge...'}
          </p>
        </div>
      ) : error ? (
        /* Error or Island notice */
        <div className="rounded-sm border border-amber-500/30 bg-amber-500/10 p-6 space-y-4 text-left">
          <div className="flex items-start gap-3">
            <AlertCircle className="text-amber-400 shrink-0 mt-0.5" size={20} />
            <div className="space-y-1">
              <h3 className="font-mono text-sm font-semibold text-sand-100">
                {isPl ? 'Wyzwanie niedostępne' : 'Route Unavailable'}
              </h3>
              <p className="text-xs sm:text-sm text-zinc-300">{error}</p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2 pt-2">
            <button
              type="button"
              onClick={handleNewRandomRoute}
              className="inline-flex items-center gap-1.5 rounded-sm bg-emerald-400 px-3.5 py-2 text-xs font-bold text-obsidian-950 hover:bg-emerald-300"
            >
              <Sparkles size={14} />
              <span>{isPl ? 'Losuj inną trasę' : 'Try Another Random Route'}</span>
            </button>
            <button
              type="button"
              onClick={handleDailyRoute}
              className="inline-flex items-center gap-1.5 rounded-sm border border-white/15 px-3.5 py-2 text-xs font-semibold text-zinc-200 hover:bg-white/10"
            >
              <Globe size={14} />
              <span>{isPl ? 'Dzisiejsza trasa dnia' : "Today's Daily Route"}</span>
            </button>
          </div>
        </div>
      ) : challenge ? (
        <div className="space-y-5">
          {/* Mission Banner */}
          <div className="rounded-sm border border-white/10 bg-obsidian-900/60 p-4 sm:p-5 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <div className="space-y-1.5">
              <span className="font-mono text-[10px] font-bold uppercase tracking-wider text-emerald-400 block">
                {isPl ? 'Zadanie trasy' : 'Route Objective'}
              </span>
              <div className="flex flex-wrap items-center gap-2 sm:gap-3 text-base sm:text-xl font-bold font-mono text-sand-100">
                <span className="bg-obsidian-950/80 border border-white/10 px-2.5 py-1 rounded-xs text-sand-100">
                  {challenge.start}
                </span>
                <ArrowRight size={18} className="text-emerald-400 shrink-0" />
                <span className="bg-obsidian-950/80 border border-emerald-500/40 text-emerald-300 px-2.5 py-1 rounded-xs">
                  {challenge.target}
                </span>
              </div>
            </div>

            {/* Score & Hop Benchmark Badges */}
            <div className="flex flex-wrap items-center gap-3">
              <div className="rounded-sm bg-obsidian-950/60 border border-white/10 px-3 py-2 text-center min-w-24">
                <span className="block text-[10px] font-mono uppercase tracking-wider text-zinc-400">
                  {isPl ? 'Wykonano' : 'Your Hops'}
                </span>
                <span className="font-mono text-lg font-bold text-sand-100">{currentHops}</span>
              </div>

              <div className="rounded-sm bg-obsidian-950/60 border border-emerald-500/30 px-3 py-2 text-center min-w-24">
                <span className="block text-[10px] font-mono uppercase tracking-wider text-emerald-400">
                  {isPl ? 'Optymalnie' : 'Optimal'}
                </span>
                <span className="font-mono text-lg font-bold text-emerald-300">{optimalHops}</span>
              </div>
            </div>
          </div>

          {/* Action Toolbar */}
          <div className="flex flex-wrap items-center justify-between gap-2.5 text-xs">
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleUndo}
                disabled={path.length <= 1 || status === 'won'}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-sm border border-white/15 bg-obsidian-900/60 text-zinc-300 hover:bg-white/10 hover:text-white disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                title={isPl ? 'Cofnij ostatni krok' : 'Undo last hop'}
              >
                <Undo2 size={13} />
                <span>{isPl ? 'Cofnij krok' : 'Undo Hop'}</span>
              </button>

              <button
                type="button"
                onClick={handleReset}
                disabled={path.length <= 1 || status === 'won'}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-sm border border-white/15 bg-obsidian-900/60 text-zinc-300 hover:bg-white/10 hover:text-white disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                title={isPl ? 'Resetuj trasę od początku' : 'Reset to starting territory'}
              >
                <RotateCcw size={13} />
                <span>{isPl ? 'Reset trasy' : 'Reset'}</span>
              </button>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleDailyRoute}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-sm border border-white/15 bg-obsidian-900/60 text-zinc-300 hover:bg-white/10 hover:text-white transition-colors"
              >
                <Globe size={13} />
                <span>{isPl ? 'Dzienne wyzwanie' : 'Daily Challenge'}</span>
              </button>

              <button
                type="button"
                onClick={handleNewRandomRoute}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-sm bg-white/10 text-sand-100 hover:bg-white/15 transition-colors font-medium"
              >
                <Sparkles size={13} className="text-amber-400" />
                <span>{isPl ? 'Losowa trasa' : 'New Random Route'}</span>
              </button>
            </div>
          </div>

          {/* Path Trail (Breadcrumbs) */}
          <div className="rounded-sm border border-white/10 bg-obsidian-900/40 p-3.5 space-y-2 text-left">
            <span className="font-mono text-[10px] font-bold uppercase tracking-wider text-zinc-400 block">
              {isPl ? `Twoja trasa (${path.length} etapów)` : `Your Path Trail (${path.length} locations)`}
            </span>
            <div className="flex flex-wrap items-center gap-1.5">
              {path.map((step, idx) => {
                const isCurrent = idx === path.length - 1;
                const isTarget = step.toLowerCase() === challenge.target.toLowerCase();
                const isStart = idx === 0;

                return (
                  <div key={`${step}-${idx}`} className="flex items-center gap-1.5">
                    <span
                      className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-xs font-mono text-xs font-semibold ${
                        isCurrent
                          ? isTarget
                            ? 'bg-emerald-400 text-obsidian-950 ring-2 ring-emerald-300'
                            : 'bg-emerald-500/20 text-emerald-300 border border-emerald-400/40'
                          : isStart
                          ? 'bg-white/10 text-sand-100 border border-white/15'
                          : 'bg-obsidian-950 border border-white/10 text-zinc-300'
                      }`}
                    >
                      <MapPin size={11} className={isCurrent ? 'text-emerald-400' : 'text-zinc-500'} />
                      <span>{step}</span>
                    </span>
                    {idx < path.length - 1 && <ArrowRight size={12} className="text-zinc-600 shrink-0" />}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Victory Debrief Modal / Card */}
          {status === 'won' && verification && (
            <div className="rounded-sm border-2 border-emerald-400 bg-obsidian-900/90 p-5 sm:p-6 text-left space-y-5 animate-in fade-in zoom-in-95 duration-200">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-white/10 pb-4">
                <div className="flex items-center gap-3">
                  <div className="rounded-full bg-emerald-500/20 border border-emerald-500/40 p-2.5 text-emerald-400">
                    <Trophy size={24} />
                  </div>
                  <div>
                    <h2 className="font-mono text-xl sm:text-2xl font-bold text-sand-100">
                      {isPl ? 'Trasa ukończona!' : 'Route Completed!'}
                    </h2>
                    <p className="text-xs sm:text-sm text-emerald-400 font-semibold font-mono">
                      {verification.rank === 'gold'
                        ? isPl
                          ? '🥇 Złota Trasa — najkrótsza możliwa ścieżka!'
                          : '🥇 Gold Route — Shortest Possible Path!'
                        : verification.rank === 'silver'
                        ? isPl
                          ? '🥈 Srebrna Trasa — świetna nawigacja!'
                          : '🥈 Silver Route — Great Navigation!'
                        : isPl
                        ? '🥉 Brązowa Trasa — malowniczy objazd!'
                        : '🥉 Bronze Route — Scenic Detour!'}
                    </p>
                  </div>
                </div>

                {/* Score Summary */}
                <div className="flex items-center gap-3 self-start sm:self-auto">
                  <div className="rounded-sm bg-obsidian-950 border border-white/10 px-3 py-1.5 text-center">
                    <span className="block text-[10px] font-mono uppercase text-zinc-400">
                      {isPl ? 'Przeskoki' : 'Hops Taken'}
                    </span>
                    <span className="font-mono text-base font-bold text-sand-100">{verification.hops}</span>
                  </div>
                  <div className="rounded-sm bg-obsidian-950 border border-emerald-500/30 px-3 py-1.5 text-center">
                    <span className="block text-[10px] font-mono uppercase text-emerald-400">
                      {isPl ? 'Optymalnie' : 'Optimal'}
                    </span>
                    <span className="font-mono text-base font-bold text-emerald-300">
                      {verification.optimal_hops}
                    </span>
                  </div>
                </div>
              </div>

              {/* Path Reveal Comparison */}
              {verification.optimal_path && (
                <div className="space-y-2 text-xs">
                  <span className="font-mono text-[11px] font-bold uppercase tracking-wider text-zinc-400 block">
                    {isPl ? 'Optymalna najkrótsza ścieżka:' : 'Optimal Shortest Path:'}
                  </span>
                  <div className="p-3 rounded-sm bg-obsidian-950/70 border border-white/10 font-mono text-zinc-300 flex flex-wrap items-center gap-1.5">
                    {verification.optimal_path.map((node, i) => (
                      <span key={node} className="inline-flex items-center gap-1">
                        <span className="font-semibold text-emerald-300">{node}</span>
                        {i < verification.optimal_path!.length - 1 && (
                          <ArrowRight size={11} className="text-zinc-600" />
                        )}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Action Buttons */}
              <div className="flex flex-wrap items-center gap-3 pt-2">
                <button
                  type="button"
                  onClick={handleCopyResult}
                  className="flex items-center gap-2 rounded-sm bg-emerald-400 px-4 py-2.5 text-xs font-bold text-obsidian-950 hover:bg-emerald-300 transition-colors shadow-md cursor-pointer"
                >
                  {copied ? <Check size={15} /> : <Share2 size={15} />}
                  <span>{copied ? (isPl ? 'Skopiowano!' : 'Copied!') : (isPl ? 'Kopiuj wynik' : 'Share Result')}</span>
                </button>

                <button
                  type="button"
                  onClick={handleNewRandomRoute}
                  className="flex items-center gap-2 rounded-sm border border-white/15 px-4 py-2.5 text-xs font-semibold text-sand-100 hover:bg-white/10 transition-colors cursor-pointer"
                >
                  <Sparkles size={14} className="text-amber-400" />
                  <span>{isPl ? 'Nowa trasa' : 'Play Another Route'}</span>
                </button>

                <Link
                  to="/explore"
                  className="flex items-center gap-1.5 rounded-sm border border-white/15 px-4 py-2.5 text-xs font-semibold text-zinc-300 hover:bg-white/10 transition-colors"
                >
                  <span>{isPl ? `Odkryj ${challenge.target} w Atlasie` : `Explore ${challenge.target} in Atlas`}</span>
                  <ExternalLink size={13} />
                </Link>

                <Link
                  to={mode === 'us_states' ? '/us-states' : '/game'}
                  className="text-xs text-zinc-400 hover:text-sand-100 ml-auto flex items-center gap-1 transition-colors"
                >
                  <span>{isPl ? 'Wróć do gry dnia' : 'Back to Daily Game'}</span>
                  <ArrowRight size={13} />
                </Link>
              </div>
            </div>
          )}

          {/* Active Hop Dock (When still playing) */}
          {status === 'playing' && currentLocation && (
            <div className="rounded-sm border border-white/10 bg-obsidian-900/50 p-4 sm:p-5 text-left space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2.5 border-b border-white/10 pb-3">
                <div className="space-y-0.5">
                  <span className="font-mono text-[10px] uppercase font-bold tracking-wider text-emerald-400 block">
                    {isPl ? 'Następny przeskok' : 'Next Border Hop'}
                  </span>
                  <p className="text-sm font-semibold text-sand-100 font-mono">
                    {isPl ? (
                      <>
                        Jesteś w: <strong className="text-emerald-300">{currentLocation}</strong>. Wybierz sąsiada:
                      </>
                    ) : (
                      <>
                        You are in: <strong className="text-emerald-300">{currentLocation}</strong>. Choose next
                        bordering territory:
                      </>
                    )}
                  </p>
                </div>

                {/* Search Filter Input */}
                {availableNeighbors.length > 5 && (
                  <div className="relative w-full sm:w-56">
                    <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 text-zinc-500" size={13} />
                    <input
                      type="text"
                      value={searchFilter}
                      onChange={(e) => setSearchFilter(e.target.value)}
                      placeholder={isPl ? 'Szukaj sąsiada...' : 'Filter neighbors...'}
                      className="w-full rounded-sm border border-white/10 bg-obsidian-950 py-1.5 pl-8 pr-3 text-xs text-sand-100 placeholder:text-zinc-500 focus:border-emerald-400 focus:outline-hidden"
                    />
                  </div>
                )}
              </div>

              {/* Neighbors Grid */}
              {loadingNeighbors ? (
                <div className="py-6 text-center text-xs text-zinc-400 font-mono flex items-center justify-center gap-2">
                  <Loader2 size={14} className="animate-spin text-emerald-400" />
                  <span>{isPl ? 'Sprawdzanie granic...' : 'Fetching bordering neighbors...'}</span>
                </div>
              ) : filteredNeighbors.length === 0 ? (
                <div className="py-6 text-center text-xs text-zinc-400 font-mono">
                  {searchFilter
                    ? isPl
                      ? 'Brak sąsiadów pasujących do filtra.'
                      : 'No bordering neighbors match your search.'
                    : isPl
                    ? 'Brak lądowych sąsiadów (ślepy zaułek).'
                    : 'No bordering neighbors found (dead end).'}
                </div>
              ) : (
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
                  {filteredNeighbors.map((neighbor) => {
                    const isTarget = neighbor.toLowerCase() === challenge.target.toLowerCase();
                    const alreadyVisited = path.includes(neighbor);

                    return (
                      <button
                        key={neighbor}
                        type="button"
                        onClick={() => handleSelectNeighbor(neighbor)}
                        className={`group relative flex items-center justify-between p-2.5 rounded-sm border text-left transition-all cursor-pointer ${
                          isTarget
                            ? 'bg-emerald-500/20 border-emerald-400/80 hover:bg-emerald-500/30 text-emerald-200'
                            : alreadyVisited
                            ? 'bg-obsidian-950/40 border-white/5 hover:border-white/20 text-zinc-400'
                            : 'bg-obsidian-950/80 border-white/10 hover:border-emerald-400/50 hover:bg-white/5 text-sand-100'
                        }`}
                      >
                        <span className="font-mono text-xs font-semibold truncate pr-2">{neighbor}</span>
                        {isTarget ? (
                          <span className="shrink-0 rounded-xs bg-emerald-400 px-1.5 py-0.5 font-mono text-[9px] font-bold text-obsidian-950 uppercase">
                            {isPl ? 'Cel' : 'Target'}
                          </span>
                        ) : (
                          <ArrowRight
                            size={12}
                            className="text-zinc-600 group-hover:text-emerald-400 group-hover:translate-x-0.5 transition-all shrink-0"
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
