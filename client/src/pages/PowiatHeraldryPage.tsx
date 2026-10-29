import React, { useEffect, useMemo, useRef, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import toast from 'react-hot-toast';
import {
  HelpCircle,
  Share2,
  Check,
  X,
  Sparkles,
  AlertCircle,
  Trophy,
  ArrowRight,
  Shield,
  Lock,
  RefreshCw,
  Loader2,
  ExternalLink,
  Car,
  Compass,
  Maximize2,
  ZoomIn,
  ZoomOut,
  Sun,
  Moon,
} from 'lucide-react';
import { powiatHeraldryService } from '../services/api';
import type {
  PowiatHeraldryChallenge,
  PowiatHeraldryGuessResult,
  PowiatHeraldryItem,
  PowiatHeraldrySourceAttribution,
  PowiatHeraldryTarget,
} from '../types';

type GameMode = 'daily' | 'challenge';

const POWIAT_HERALDRY_GUIDE_KEY = 'powiat_heraldry_guide_seen';

function normalizePolishText(str: string): string {
  return str
    .toLowerCase()
    .replace(/ą/g, 'a')
    .replace(/ć/g, 'c')
    .replace(/ę/g, 'e')
    .replace(/ł/g, 'l')
    .replace(/ń/g, 'n')
    .replace(/ó/g, 'o')
    .replace(/ś/g, 's')
    .replace(/ź/g, 'z')
    .replace(/ż/g, 'z');
}

function getStoredDailyToken(dateStr?: string): string | null {
  try {
    if (dateStr) {
      const direct = localStorage.getItem(`powiat_heraldry_daily_token_${dateStr}`);
      if (direct) return direct;
    }
    const today = new Date().toISOString().slice(0, 10);
    const todayToken = localStorage.getItem(`powiat_heraldry_daily_token_${today}`);
    if (todayToken) return todayToken;
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key && key.startsWith('powiat_heraldry_daily_token_')) {
        return localStorage.getItem(key);
      }
    }
  } catch {
    return null;
  }
  return null;
}

function PolishLicensePlateBadge({ plates }: { plates: string[] }) {
  return (
    <div
      className="inline-flex items-stretch rounded-md border-2 border-black bg-white shadow-md overflow-hidden select-none"
      title="Polskie tablice rejestracyjne / Polish registration plates"
    >
      {/* Euroband */}
      <div className="flex flex-col items-center justify-between bg-[#003399] px-1.5 py-1 text-white min-w-[24px]">
        <div className="text-[10px] leading-none text-yellow-400 font-bold" aria-hidden="true">
          ★
        </div>
        <span className="font-mono text-[10px] sm:text-xs font-black tracking-tighter leading-none text-white">
          PL
        </span>
      </div>
      {/* Plate characters */}
      <div className="flex items-center px-3 py-1 font-mono font-black text-zinc-950 text-base sm:text-xl tracking-widest uppercase">
        {plates.join(' · ')}
      </div>
    </div>
  );
}

export default function PowiatHeraldryPage() {

  // Mode state
  const [mode, setMode] = useState<GameMode>('daily');
  const [challenge, setChallenge] = useState<PowiatHeraldryChallenge | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  // Gameplay state
  const [guesses, setGuesses] = useState<PowiatHeraldryGuessResult[]>([]);
  const [isGameOver, setIsGameOver] = useState<boolean>(false);
  const [won, setWon] = useState<boolean>(false);
  const [registrationPlates, setRegistrationPlates] = useState<string[] | null>(null);
  const [targetPowiat, setTargetPowiat] = useState<PowiatHeraldryTarget | null>(null);
  const [attribution, setAttribution] = useState<PowiatHeraldrySourceAttribution | null>(null);

  // Shield image loading & error state
  const [imageLoading, setImageLoading] = useState<boolean>(true);
  const [imageError, setImageError] = useState<boolean>(false);
  const [retryNonce, setRetryNonce] = useState<number>(0);

  // Counties for autocomplete
  const [counties, setCounties] = useState<PowiatHeraldryItem[]>([]);
  const [inputVal, setInputVal] = useState<string>('');
  const [selectedCounty, setSelectedCounty] = useState<PowiatHeraldryItem | null>(null);
  const [showSuggestions, setShowSuggestions] = useState<boolean>(false);
  const [highlightedIndex, setHighlightedIndex] = useState<number>(0);

  // UI state
  const [copied, setCopied] = useState<boolean>(false);
  const [showResultsModal, setShowResultsModal] = useState<boolean>(false);
  const [isFullscreenOpen, setIsFullscreenOpen] = useState<boolean>(false);
  const [zoomLevel, setZoomLevel] = useState<number>(1);
  const [lightBackdrop, setLightBackdrop] = useState<boolean>(false);
  const [showInstructions, setShowInstructions] = useState<boolean>(() => {
    try {
      return localStorage.getItem(POWIAT_HERALDRY_GUIDE_KEY) !== 'true';
    } catch {
      return false;
    }
  });

  const inputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Load counties list once
  useEffect(() => {
    let mounted = true;
    powiatHeraldryService
      .getCounties()
      .then((data) => {
        if (mounted) setCounties(data);
      })
      .catch((err) => {
        console.error('Failed to load counties for Heraldry:', err);
      });
    return () => {
      mounted = false;
    };
  }, []);

  // Resolve coat URL
  const resolvedCoatUrl = useMemo(() => {
    if (!challenge?.coat_asset_url) return null;
    const url = challenge.coat_asset_url;
    if (url.startsWith('http://') || url.startsWith('https://')) {
      return url;
    }
    return url.startsWith('/api') ? url : `/api${url}`;
  }, [challenge?.coat_asset_url]);

  // Reset image state when coat URL changes
  useEffect(() => {
    setImageLoading(true);
    setImageError(false);
    setRetryNonce(0);
    setIsFullscreenOpen(false);
    setZoomLevel(1);
  }, [resolvedCoatUrl]);

  // Load challenge
  const loadChallenge = useCallback(
    async (targetMode: GameMode, customSeed?: string) => {
      setIsLoading(true);
      setInputVal('');
      setSelectedCounty(null);
      setShowSuggestions(false);

      try {
        if (targetMode === 'daily') {
          const savedToken = getStoredDailyToken();
          const ch = await powiatHeraldryService.getChallenge(
            savedToken ? { token: savedToken } : undefined
          );
          setChallenge(ch);
          if (ch.date && ch.token) {
            try {
              localStorage.setItem(`powiat_heraldry_daily_token_${ch.date}`, ch.token);
            } catch {
              // ignore
            }
          }
          setGuesses(ch.guesses || []);
          setIsGameOver(Boolean(ch.is_game_over));
          setWon(Boolean(ch.won));
          setRegistrationPlates(ch.registration_plates || null);
          setTargetPowiat(ch.target_powiat || null);
          setAttribution(ch.source_attribution || null);
          if (ch.is_game_over) {
            setShowResultsModal(true);
          }
        } else {
          const seedParam = customSeed || `challenge-${Date.now()}`;
          const ch = await powiatHeraldryService.getChallenge({ seed: seedParam });
          setChallenge(ch);
          setGuesses([]);
          setIsGameOver(false);
          setWon(false);
          setRegistrationPlates(null);
          setTargetPowiat(null);
          setAttribution(ch.source_attribution || null);
          setShowResultsModal(false);
        }
      } catch (err) {
        console.error('Failed to load heraldry challenge:', err);
        toast.error(
          'Failed to load coat of arms challenge.'
        );
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  // Initial load
  useEffect(() => {
    loadChallenge(mode);
  }, [mode, loadChallenge]);

  const handleSwitchMode = (nextMode: GameMode) => {
    if (nextMode === mode) return;
    setMode(nextMode);
  };

  // Close dropdown on outside click
  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(e.target as Node) &&
        inputRef.current &&
        !inputRef.current.contains(e.target as Node)
      ) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener('mousedown', handleOutsideClick);
    return () => document.removeEventListener('mousedown', handleOutsideClick);
  }, []);

  // Close fullscreen modal on Escape
  useEffect(() => {
    if (!isFullscreenOpen) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setIsFullscreenOpen(false);
      }
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [isFullscreenOpen]);

  const handleCloseInstructions = () => {
    setShowInstructions(false);
    try {
      localStorage.setItem(POWIAT_HERALDRY_GUIDE_KEY, 'true');
    } catch {
      // ignore
    }
  };

  // Filter counties for autocomplete
  const filteredCounties = useMemo(() => {
    const query = inputVal.trim();
    if (!query) return [];
    const normalizedQuery = normalizePolishText(query);
    const guessedIds = new Set(guesses.map((g) => g.powiat_id).filter(Boolean));
    const guessedNames = new Set(guesses.map((g) => g.guess.toLowerCase()));

    return counties
      .filter((c) => {
        if (guessedIds.has(c.id) || guessedNames.has(c.name.toLowerCase())) {
          return false;
        }
        const matchName = normalizePolishText(c.name).includes(normalizedQuery);
        const matchVoivodeship = normalizePolishText(c.voivodeship).includes(normalizedQuery);
        return matchName || matchVoivodeship;
      })
      .slice(0, 8);
  }, [counties, inputVal, guesses]);

  const handleSelectCounty = (item: PowiatHeraldryItem) => {
    setSelectedCounty(item);
    setInputVal(item.name);
    setShowSuggestions(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!showSuggestions || filteredCounties.length === 0) {
      if (e.key === 'Enter') {
        handleSubmitGuess();
      }
      return;
    }

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlightedIndex((prev) => (prev + 1) % filteredCounties.length);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlightedIndex((prev) => (prev - 1 + filteredCounties.length) % filteredCounties.length);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      const target = filteredCounties[highlightedIndex];
      if (target) {
        handleSelectCounty(target);
      }
    } else if (e.key === 'Escape') {
      setShowSuggestions(false);
    }
  };

  const handleSubmitGuess = async () => {
    if (isGameOver || isSubmitting || !challenge) return;
    const name = (selectedCounty ? selectedCounty.name : inputVal).trim();
    if (!name) return;

    const guessedNames = new Set(guesses.map((g) => g.guess.toLowerCase()));
    if (guessedNames.has(name.toLowerCase())) {
      toast.error('You already guessed this county!');
      return;
    }

    let countyId = selectedCounty?.id;
    if (!countyId) {
      const match = counties.find(
        (c) =>
          c.name.toLowerCase() === name.toLowerCase() ||
          normalizePolishText(c.name) === normalizePolishText(name)
      );
      if (match) {
        countyId = match.id;
      }
    }

    setIsSubmitting(true);
    try {
      const result = await powiatHeraldryService.submitGuess({
        token: challenge.token,
        guess: name,
        powiat_id: countyId,
      });

      if (result.token) {
        setChallenge((prev) => (prev ? { ...prev, token: result.token! } : prev));
        if (mode === 'daily' && challenge.date) {
          try {
            localStorage.setItem(`powiat_heraldry_daily_token_${challenge.date}`, result.token);
          } catch {
            // ignore
          }
        }
      }

      const nextGuesses = [...guesses, result];
      setGuesses(nextGuesses);
      setInputVal('');
      setSelectedCounty(null);

      if (result.registration_plates && result.registration_plates.length > 0) {
        setRegistrationPlates(result.registration_plates);
      }
      if (result.target_powiat) {
        setTargetPowiat(result.target_powiat);
      }
      if (result.source_attribution) {
        setAttribution(result.source_attribution);
      }

      if (result.is_game_over) {
        setIsGameOver(true);
        setWon(result.won);
        setShowResultsModal(true);
        if (result.won) {
          toast.success(
            'Congratulations! You solved the coat of arms!'
          );
        } else {
          toast.error('All 8 guesses exhausted!');
        }
      }
    } catch (err) {
      console.error('Failed to submit heraldry guess:', err);
      toast.error('Error submitting your guess.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const maxGuesses = challenge?.max_guesses || 8;
  const hintUnlockThreshold = challenge?.hint_unlock_guesses || 5;
  const isPlatesUnlocked = Boolean(registrationPlates && registrationPlates.length > 0);

  const handleShare = () => {
    if (!challenge) return;
    const scoreText = won ? `${guesses.length}/${maxGuesses}` : `X/${maxGuesses}`;
    const headerTitle =
      mode === 'daily'
        ? (`County Coats of Arms · ${challenge.date}`)
        : ('County Coats of Arms · Challenge');

    const lines: string[] = [];
    lines.push(headerTitle);
    lines.push(`${scoreText} guesses`);
    if (registrationPlates && registrationPlates.length > 0) {
      lines.push(`🚗 [${registrationPlates.join(' · ')}]`);
    }
    lines.push('');

    guesses.forEach((g) => {
      if (g.answer) {
        lines.push('🟩 🎯');
      } else {
        const vTile = g.same_voivodeship ? '🟩' : '⬛';
        const arrow = g.bearing_arrow ? `${g.bearing_arrow} ` : '';
        const dist = g.distance_km !== null && g.distance_km !== undefined ? `${g.distance_km} km` : '';
        lines.push(`${vTile} ${arrow}${dist}`.trim());
      }
    });

    lines.push('');
    lines.push(
      typeof window !== 'undefined'
        ? `${window.location.origin}/herby-powiatow`
        : 'https://countrydle.com/herby-powiatow'
    );

    const fullShareText = lines.join('\n');
    if (navigator.clipboard) {
      navigator.clipboard.writeText(fullShareText);
      setCopied(true);
      toast.success('Copied results to clipboard!');
      setTimeout(() => setCopied(false), 2500);
    }
  };

  const sortedGuesses = useMemo(() => [...guesses].reverse(), [guesses]);

  if (isLoading && !challenge) {
    return (
      <div role="status" className="flex h-[60vh] items-center justify-center gap-3 text-emerald-400">
        <Loader2 className="animate-spin" size={24} aria-hidden="true" />
        <span className="text-sm font-medium text-sand-300">
          {'Loading County Coats of Arms...'}
        </span>
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-4xl px-2.5 py-1.5 sm:px-6 sm:py-4">
      {/* Header Bar */}
      <header className="mb-2 sm:mb-6 border-b border-sand-800/80 pb-2 sm:pb-4 space-y-2 sm:space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2 sm:gap-3">
          <div>
            <div className="mb-0.5 sm:mb-1 flex items-center gap-1.5 sm:gap-2 text-[11px] sm:text-xs font-mono font-semibold uppercase tracking-wider text-sand-400">
              <span className="flex items-center gap-1.5">
                <Shield size={14} className="text-emerald-400" />
                {'County Heraldry'}
              </span>
              <span>•</span>
              <span>{mode === 'daily' ? challenge?.date || 'Daily' : 'Challenge'}</span>
            </div>
            <h1 className="text-lg font-bold tracking-tight text-sand-100 sm:text-3xl">
              {'County Coats of Arms'}
            </h1>
            <p className="mt-0.5 text-[11px] leading-tight text-sand-400 sm:text-sm sm:leading-normal">
              {'Identify the Polish county by its official coat of arms. Registration plates reveal after 5 wrong guesses.'}
            </p>
          </div>

          <div className="flex items-center gap-1.5 sm:gap-3">
            {/* Guesses Remaining Pill */}
            <div className="flex items-center rounded-sm border border-white/10 bg-obsidian-900 px-2 py-1 shadow-sm sm:px-3.5 sm:py-2">
              <span className="mr-1.5 sm:mr-2 font-mono text-[11px] sm:text-xs uppercase tracking-wider text-zinc-400">
                {'Guesses:'}
              </span>
              <span
                className={`font-mono text-sm sm:text-base font-bold ${
                  guesses.length >= maxGuesses - 2 ? 'text-amber-400' : 'text-emerald-400'
                }`}
              >
                {guesses.length}
              </span>
              <span className="font-mono text-[11px] sm:text-xs text-zinc-500"> / {maxGuesses}</span>
            </div>

            {/* Help Modal Button */}
            <button
              type="button"
              onClick={() => setShowInstructions(true)}
              className="flex h-8 w-8 sm:h-9 sm:w-9 items-center justify-center rounded-sm border border-sand-800 bg-sand-900 text-sand-400 hover:border-sand-700 hover:text-sand-200 transition-colors cursor-pointer"
              title={'How to play County Coats of Arms'}
              aria-label={'Instructions'}
            >
              <HelpCircle size={17} />
            </button>

            {/* Results Button when Game is Over */}
            {isGameOver && (
              <button
                type="button"
                onClick={() => setShowResultsModal(true)}
                className="flex h-8 sm:h-9 items-center gap-1.5 px-2.5 sm:px-3 rounded-sm border border-emerald-500/40 bg-emerald-950/40 text-emerald-300 hover:bg-emerald-900/50 transition-colors text-xs font-semibold cursor-pointer"
                title={'Show results'}
              >
                <Trophy size={14} />
                <span>{'Results'}</span>
              </button>
            )}
          </div>
        </div>

        {/* Mode Switcher Bar */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1.5 sm:gap-2 pt-1 border-t border-white/5">
          <div className="grid grid-cols-2 sm:inline-flex rounded-sm border border-white/10 bg-obsidian-950 p-0.5 sm:p-1 text-xs font-medium w-full sm:w-auto">
            <button
              type="button"
              onClick={() => handleSwitchMode('daily')}
              className={`px-2 sm:px-3 py-1 sm:py-1.5 rounded-xs transition-colors cursor-pointer text-center ${
                mode === 'daily'
                  ? 'bg-emerald-500/20 text-emerald-300 font-semibold shadow-xs'
                  : 'text-zinc-400 hover:text-sand-200'
              }`}
            >
              📅 {'Daily Shield'}
            </button>
            <button
              type="button"
              onClick={() => handleSwitchMode('challenge')}
              className={`px-2 sm:px-3 py-1 sm:py-1.5 rounded-xs transition-colors cursor-pointer text-center ${
                mode === 'challenge'
                  ? 'bg-emerald-500/20 text-emerald-300 font-semibold shadow-xs'
                  : 'text-zinc-400 hover:text-sand-200'
              }`}
            >
              ⚡ {'Random Challenge'}
            </button>
            <Link
              to="/quiz-herbow"
              className="hidden sm:inline-flex items-center px-3 py-1.5 rounded-xs text-zinc-400 hover:text-emerald-300 transition-colors"
            >
              🏆 {'380 Coats Grid Quiz'}
            </Link>
          </div>

          <div className="flex items-center gap-1.5 w-full sm:w-auto">
            {mode === 'challenge' && (
              <button
                type="button"
                onClick={() => loadChallenge('challenge', `challenge-${Date.now()}`)}
                disabled={isLoading}
                className="flex-1 sm:flex-initial inline-flex items-center justify-center gap-1.5 px-2.5 sm:px-3 py-1 sm:py-1.5 rounded-sm border border-sand-700 bg-sand-900/60 text-sand-200 hover:bg-sand-800 text-xs font-medium transition-colors cursor-pointer disabled:opacity-50"
              >
                <RefreshCw size={13} className={isLoading ? 'animate-spin' : ''} />
                <span>{'New Challenge'}</span>
              </button>
            )}
            <Link
              to="/quiz-herbow"
              className="sm:hidden flex-1 inline-flex items-center justify-center gap-1 px-2 py-1 rounded-sm border border-white/10 bg-obsidian-950 text-zinc-400 hover:text-emerald-300 text-xs font-medium transition-colors text-center"
            >
              <span className="truncate">🏆 {'380 Coats Quiz'}</span>
            </Link>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="space-y-2.5 sm:space-y-6">
        {/* 1. Coat of Arms Shield Display */}
        <section
          aria-label={'County Coat of Arms Shield'}
          className="relative flex flex-col items-center justify-center rounded-xl border border-sand-800/80 bg-obsidian-950/60 p-2 sm:p-6 shadow-inner"
        >
          {/* Decorative heraldic background glow */}
          <div
            className="absolute inset-0 bg-radial-gradient from-emerald-500/5 via-transparent to-transparent pointer-events-none rounded-xl"
            aria-hidden="true"
          />

          {/* Heraldic Shield Frame */}
          <div
            onClick={() => {
              if (resolvedCoatUrl && !imageError && !imageLoading) {
                setZoomLevel(1);
                setIsFullscreenOpen(true);
              }
            }}
            role={resolvedCoatUrl && !imageError && !imageLoading ? 'button' : undefined}
            tabIndex={resolvedCoatUrl && !imageError && !imageLoading ? 0 : undefined}
            onKeyDown={(e) => {
              if (
                resolvedCoatUrl &&
                !imageError &&
                !imageLoading &&
                (e.key === 'Enter' || e.key === ' ')
              ) {
                e.preventDefault();
                setZoomLevel(1);
                setIsFullscreenOpen(true);
              }
            }}
            aria-label={
              'Click to inspect coat of arms in fullscreen'
            }
            className={`group relative h-48 sm:h-80 aspect-[4/5] flex items-center justify-center p-2 sm:p-4 rounded-lg border border-sand-700/50 bg-obsidian-900/90 shadow-2xl transition-all shadow-black/80 ${
              resolvedCoatUrl && !imageError && !imageLoading
                ? 'cursor-zoom-in hover:border-emerald-500/50 hover:shadow-emerald-950/30'
                : ''
            }`}
          >
            {resolvedCoatUrl && !imageError && (
              <img
                src={
                  retryNonce > 0
                    ? `${resolvedCoatUrl}${resolvedCoatUrl.includes('?') ? '&' : '?'}retry=${retryNonce}`
                    : resolvedCoatUrl
                }
                alt={
                  targetPowiat
                    ? `Coat of arms of ${targetPowiat.name}`
                    : 'Polish county coat of arms'
                }
                className={`h-full w-full object-contain filter drop-shadow-xl transition-transform duration-300 group-hover:scale-[1.02] ${
                  imageLoading ? 'opacity-0' : 'opacity-100'
                }`}
                onLoad={() => setImageLoading(false)}
                onError={() => {
                  setImageLoading(false);
                  setImageError(true);
                }}
              />
            )}
            {resolvedCoatUrl && !imageError && !imageLoading && (
              <span
                aria-hidden="true"
                className="pointer-events-none absolute bottom-1.5 right-1.5 sm:bottom-2 sm:right-2 inline-flex h-6 w-6 sm:h-7 sm:w-7 items-center justify-center rounded bg-obsidian-950/85 border border-white/15 text-zinc-300 opacity-85 group-hover:opacity-100 group-hover:border-emerald-400/50 group-hover:text-emerald-300 transition-all shadow"
              >
                <Maximize2 size={13} />
              </span>
            )}

            {/* Spinner while loading */}
            {imageLoading && !imageError && (
              <div
                role="status"
                className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-emerald-400 bg-obsidian-950/70 backdrop-blur-xs rounded-lg"
              >
                <Loader2 className="animate-spin" size={28} aria-hidden="true" />
                <span className="text-[11px] sm:text-xs font-mono text-sand-300">
                  {'Loading heraldic shield...'}
                </span>
              </div>
            )}

            {/* Honest 503 / Network Error State */}
            {imageError && (
              <div
                role="alert"
                className="flex flex-col items-center justify-center p-4 sm:p-6 text-center text-amber-300 gap-2.5 max-w-xs"
              >
                <AlertCircle size={30} className="text-amber-400" />
                <div className="space-y-1">
                  <p className="text-xs sm:text-sm font-semibold text-sand-100">
                    {'Failed to load coat of arms'}
                  </p>
                  <p className="text-[11px] sm:text-xs text-sand-400 leading-snug">
                    {'Network error or Wikimedia/cache service returned status 503.'}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setImageError(false);
                    setImageLoading(true);
                    setRetryNonce((n) => n + 1);
                  }}
                  className="mt-0.5 inline-flex items-center gap-1.5 px-2.5 py-1 rounded-sm border border-amber-500/40 bg-amber-950/40 text-amber-300 hover:bg-amber-900/50 text-xs font-medium transition-colors cursor-pointer"
                >
                  <RefreshCw size={12} />
                  <span>{'Retry loading'}</span>
                </button>
              </div>
            )}
          </div>
        </section>

        {/* 2. Automatic Full Registration Plate Hint After 5th Wrong Guess */}
        <section aria-label={'Registration plate hint'}>
          {isPlatesUnlocked ? (
            <div className="flex flex-col sm:flex-row items-center justify-between gap-2.5 sm:gap-3 rounded-lg border border-blue-500/30 bg-blue-950/30 p-2.5 sm:px-5 sm:py-4 shadow-sm">
              <div className="flex items-center gap-2 text-blue-300 text-xs sm:text-sm font-medium">
                <Car size={16} className="text-blue-400 shrink-0" />
                <span>
                  {'Target county registration plate codes revealed:'}
                </span>
              </div>
              <PolishLicensePlateBadge plates={registrationPlates!} />
            </div>
          ) : (
            <div className="flex items-center justify-between gap-2.5 sm:gap-3 rounded-lg border border-amber-500/20 bg-obsidian-900/60 px-3 py-2 sm:px-4 sm:py-3 text-[11px] sm:text-sm text-sand-300">
              <div className="flex items-center gap-2 min-w-0">
                <Lock size={15} className="text-amber-400 shrink-0" />
                <span className="leading-snug">
                  {`Full registration plate ID reveals after 5th wrong guess (${guesses.length}/${hintUnlockThreshold})`}
                </span>
              </div>
              <div className="flex items-center gap-1 font-mono text-[11px] sm:text-xs text-amber-400 font-bold shrink-0">
                {guesses.length < hintUnlockThreshold ? (
                  <span>
                    {`${hintUnlockThreshold - guesses.length} left`}
                  </span>
                ) : (
                  <span>{'Ready'}</span>
                )}
              </div>
            </div>
          )}
        </section>

        {/* 3. County Autocomplete & Guess Input Form */}
        {!isGameOver ? (
          <section aria-label={'Submit guess'}>
            <div className="relative">
              <div className="flex flex-row items-stretch gap-1.5 sm:gap-2">
                <div className="relative flex-1 min-w-0">
                  <input
                    ref={inputRef}
                    type="text"
                    value={inputVal}
                    onChange={(e) => {
                      setInputVal(e.target.value);
                      setSelectedCounty(null);
                      setShowSuggestions(true);
                      setHighlightedIndex(0);
                    }}
                    onFocus={() => {
                      if (inputVal.trim()) setShowSuggestions(true);
                    }}
                    onKeyDown={handleKeyDown}
                    placeholder={
                      'Type county name (e.g. Poznań)...'
                    }
                    disabled={isSubmitting}
                    autoComplete="off"
                    spellCheck="false"
                    className="w-full rounded-sm border border-sand-700 bg-obsidian-950 px-3 sm:px-3.5 py-2 sm:py-2.5 text-xs sm:text-sm text-sand-100 placeholder-sand-500 focus:border-emerald-500 focus:outline-hidden focus:ring-1 focus:ring-emerald-500"
                  />
                  {inputVal && (
                    <button
                      type="button"
                      onClick={() => {
                        setInputVal('');
                        setSelectedCounty(null);
                        setShowSuggestions(false);
                      }}
                      className="absolute right-2 top-1/2 -translate-y-1/2 text-sand-500 hover:text-sand-300 p-1 cursor-pointer"
                      aria-label={'Clear input'}
                    >
                      <X size={14} />
                    </button>
                  )}
                </div>

                <button
                  type="button"
                  onClick={handleSubmitGuess}
                  disabled={isSubmitting || !inputVal.trim()}
                  className="flex items-center justify-center gap-1.5 sm:gap-2 rounded-sm bg-emerald-600 px-3.5 sm:px-5 py-2 sm:py-2.5 text-xs sm:text-sm font-semibold text-white shadow-xs hover:bg-emerald-500 transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer shrink-0"
                >
                  {isSubmitting ? (
                    <Loader2 size={15} className="animate-spin" />
                  ) : (
                    <ArrowRight size={15} />
                  )}
                  <span>{'Guess'}</span>
                </button>
              </div>
              {/* Autocomplete Dropdown */}
              {showSuggestions && filteredCounties.length > 0 && (
                <div
                  ref={dropdownRef}
                  className="absolute z-30 mt-1 w-full rounded-sm border border-sand-700 bg-obsidian-950 shadow-xl max-h-60 overflow-y-auto"
                >
                  <ul role="listbox" className="py-1">
                    {filteredCounties.map((item, index) => {
                      const isHighlighted = index === highlightedIndex;
                      return (
                        <li
                          key={item.id}
                          role="option"
                          aria-selected={isHighlighted}
                          onMouseEnter={() => setHighlightedIndex(index)}
                          onClick={() => handleSelectCounty(item)}
                          className={`flex items-center justify-between px-3.5 py-2 text-sm cursor-pointer transition-colors ${
                            isHighlighted ? 'bg-emerald-950/60 text-emerald-200' : 'text-sand-200 hover:bg-sand-900/60'
                          }`}
                        >
                          <div className="flex items-center gap-2">
                            <span className="font-medium">{item.name}</span>
                          </div>
                          <div className="flex items-center gap-1.5">
                            <span className="rounded-xs border border-white/10 bg-sand-900/80 px-1.5 py-0.5 text-[11px] font-mono text-sand-400">
                              woj. {item.voivodeship}
                            </span>
                            <span className="rounded-xs border border-sand-800 bg-obsidian-900 px-1.5 py-0.5 text-[10px] text-zinc-400">
                              {item.is_city_county
                                ? 'City county'
                                : 'Land county'}
                            </span>
                          </div>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              )}
            </div>
          </section>
        ) : null}

        {/* 4. Terminal / Victory Banner & Attribution */}
        {isGameOver && (
          <section
            aria-label={'Game summary'}
            className="rounded-xl border border-sand-800 bg-obsidian-900/90 p-4 sm:p-6 shadow-xl space-y-4"
          >
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-white/10 pb-4">
              <div>
                <div className="flex items-center gap-2">
                  {won ? (
                    <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/20 px-2.5 py-0.5 text-xs font-semibold text-emerald-300">
                      <Trophy size={14} />
                      {'Victory!'}
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1.5 rounded-full bg-red-500/20 px-2.5 py-0.5 text-xs font-semibold text-red-300">
                      <X size={14} />
                      {'Game Over'}
                    </span>
                  )}
                </div>
                <h2 className="mt-2 text-lg sm:text-xl font-bold text-sand-100">
                  {targetPowiat ? (
                    <>
                      {targetPowiat.name}{' '}
                      <span className="font-normal text-sand-400 text-sm sm:text-base">
                        (woj. {targetPowiat.voivodeship})
                      </span>
                    </>
                  ) : (
                    'Game Over'
                  )}
                </h2>
                <p className="mt-0.5 text-xs text-sand-400">
                  {won
                    ? `Solved in ${guesses.length} of ${maxGuesses} guesses!`
                    : `Out of guesses. Better luck next time!`}
                </p>
              </div>

              {/* Registration Plates on Victory Card */}
              {registrationPlates && registrationPlates.length > 0 && (
                <div className="flex flex-col sm:items-end gap-1">
                  <span className="text-[11px] font-mono text-sand-400 uppercase tracking-wider">
                    {'Registration plates:'}
                  </span>
                  <PolishLicensePlateBadge plates={registrationPlates} />
                </div>
              )}
            </div>

            {/* Attribution */}
            {attribution && (
              <div className="rounded-lg border border-white/5 bg-obsidian-950/60 p-3 text-xs text-sand-400 space-y-1">
                <div className="font-semibold text-sand-300 flex items-center gap-1.5">
                  <Shield size={13} className="text-emerald-400" />
                  <span>{'Heraldic Source & Attribution:'}</span>
                </div>
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-zinc-400">
                  {attribution.title && (
                    <span>
                      <strong>{attribution.title}</strong>
                    </span>
                  )}
                  {(attribution.artist || attribution.author) && (
                    <span>
                      {'Author: '}
                      {attribution.artist || attribution.author}
                    </span>
                  )}
                  {attribution.license && (
                    <span className="rounded-xs border border-white/10 bg-sand-900/60 px-1.5 py-0.5 text-[10px] font-mono">
                      {attribution.license}
                    </span>
                  )}
                  {attribution.source_url && (
                    <a
                      href={attribution.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-emerald-400 hover:text-emerald-300 underline underline-offset-2 transition-colors"
                    >
                      <span>Wikimedia Commons</span>
                      <ExternalLink size={11} />
                    </a>
                  )}
                </div>
              </div>
            )}

            {/* Action Buttons */}
            <div className="flex flex-wrap items-center gap-2 pt-2">
              <button
                type="button"
                onClick={handleShare}
                className="inline-flex items-center gap-2 rounded-sm bg-emerald-600 px-4 py-2 text-xs sm:text-sm font-semibold text-white shadow-xs hover:bg-emerald-500 transition-colors cursor-pointer"
              >
                {copied ? <Check size={15} /> : <Share2 size={15} />}
                <span>{copied ? ('Copied!') : 'Share Results'}</span>
              </button>

              <button
                type="button"
                onClick={() => {
                  if (mode === 'challenge') {
                    loadChallenge('challenge', `challenge-${Date.now()}`);
                  } else {
                    setMode('challenge');
                    loadChallenge('challenge', `challenge-${Date.now()}`);
                  }
                }}
                className="inline-flex items-center gap-2 rounded-sm border border-sand-700 bg-sand-900/60 px-4 py-2 text-xs sm:text-sm font-semibold text-sand-200 hover:bg-sand-800 transition-colors cursor-pointer"
              >
                <RefreshCw size={15} />
                <span>{'New Challenge'}</span>
              </button>
            </div>
          </section>
        )}

        {/* 5. Guess History List */}
        <section aria-label={'Guess history'} className="space-y-2">
          <div className="flex items-center justify-between border-b border-sand-800/80 pb-2">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-sand-400 font-mono flex items-center gap-1.5">
              <span>{'Guess History'}</span>
              <span className="text-xs text-zinc-500">({guesses.length}/{maxGuesses})</span>
            </h3>
          </div>

          {guesses.length === 0 ? (
            <div className="rounded-lg border border-dashed border-sand-800 p-6 text-center text-xs sm:text-sm text-sand-500">
              {'Enter a county name above to submit your first guess.'}
            </div>
          ) : (
            <div className="space-y-1.5">
              {sortedGuesses.map((g, index) => {
                const originalNumber = guesses.length - index;
                return (
                  <div
                    key={`${g.powiat_id}-${originalNumber}`}
                    className={`flex flex-wrap items-center justify-between gap-2 rounded-sm border px-3 py-2 text-xs sm:text-sm transition-colors ${
                      g.answer
                        ? 'border-emerald-500/50 bg-emerald-950/40 text-emerald-200'
                        : 'border-white/10 bg-obsidian-950 text-sand-200'
                    }`}
                  >
                    {/* Left: Number and Guess Name */}
                    <div className="flex items-center gap-2.5">
                      <span className="font-mono text-xs text-zinc-500 font-bold min-w-[20px]">
                        #{originalNumber}
                      </span>
                      <span className="font-medium text-sand-100">{g.guess}</span>
                      {g.answer && (
                        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/20 px-2 py-0.5 text-[11px] font-semibold text-emerald-300">
                          <Check size={12} />
                          {'Correct!'}
                        </span>
                      )}
                    </div>

                    {/* Right: Voivodeship badge, Distance & Bearing */}
                    <div className="flex items-center gap-2 sm:gap-3">
                      {/* Voivodeship Badge */}
                      <span
                        className={`rounded-xs px-2 py-0.5 text-[11px] font-mono border ${
                          g.same_voivodeship
                            ? 'border-emerald-500/40 bg-emerald-950/40 text-emerald-300'
                            : 'border-zinc-800 bg-obsidian-900 text-zinc-400'
                        }`}
                        title={
                          g.same_voivodeship
                            ? 'Same voivodeship as target!'
                            : 'Different voivodeship than target.'
                        }
                      >
                        {g.same_voivodeship ? '🟩' : '⬛'} woj. {g.voivodeship}
                      </span>

                      {/* Distance */}
                      <span
                        className="font-mono text-xs font-semibold min-w-[60px] text-right"
                        title={'Distance to target'}
                      >
                        {g.distance_km !== null && g.distance_km !== undefined
                          ? `${g.distance_km} km`
                          : '—'}
                      </span>

                      {/* Compass Bearing */}
                      <span
                        className="font-mono text-xs text-sand-300 flex items-center gap-1 min-w-[45px]"
                        title={
                          g.bearing_direction
                            ? `${'Direction:'} ${g.bearing_direction}`
                            : undefined
                        }
                      >
                        {g.bearing_arrow && <span className="text-base leading-none">{g.bearing_arrow}</span>}
                        {g.bearing_direction && (
                          <span className="text-[11px] text-zinc-400">{g.bearing_direction}</span>
                        )}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>
      </main>

      {/* 6. Results Modal */}
      {showResultsModal && isGameOver && (
        <div className="fixed inset-0 z-[2000] flex max-h-[var(--app-height,100dvh)] items-center justify-center p-3 overflow-y-auto md:z-50 md:max-h-none">
          <div
            className="fixed inset-0 bg-black/85 backdrop-blur-md transition-opacity cursor-pointer"
            onClick={() => setShowResultsModal(false)}
            aria-hidden="true"
          />

          <section
            role="dialog"
            aria-modal="true"
            aria-label={'Game Results'}
            className="relative z-10 w-full max-w-lg rounded-xl border border-white/15 bg-obsidian-950 p-5 sm:p-7 shadow-2xl space-y-4 my-auto text-sand-100"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between border-b border-white/10 pb-3">
              <div>
                <h2 className="text-xl sm:text-2xl font-bold text-sand-100 flex items-center gap-2">
                  {won ? (
                    <>
                      <Trophy className="text-emerald-400" size={24} />
                      <span>{'Victory!'}</span>
                    </>
                  ) : (
                    <>
                      <X className="text-red-400" size={24} />
                      <span>{'Game Over'}</span>
                    </>
                  )}
                </h2>
                <p className="mt-1 text-xs text-sand-400">
                  {won
                    ? `Identified county coat of arms in ${guesses.length}/${maxGuesses} guesses!`
                    : 'Out of guesses this round.'}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setShowResultsModal(false)}
                className="flex h-8 w-8 items-center justify-center rounded-sm bg-white/5 text-zinc-400 hover:bg-white/15 hover:text-white transition-colors cursor-pointer"
                aria-label={'Close'}
              >
                <X size={16} />
              </button>
            </div>

            {/* Revealed target */}
            {targetPowiat && (
              <div className="rounded-lg border border-sand-800 bg-obsidian-900/80 p-4 space-y-2">
                <div className="text-xs font-mono uppercase text-sand-400">
                  {'Target county:'}
                </div>
                <div className="text-lg font-bold text-sand-100">{targetPowiat.name}</div>
                <div className="text-xs text-emerald-400 font-mono">
                  Voivodeship {targetPowiat.voivodeship}
                </div>
              </div>
            )}

            {/* Registration plates badge */}
            {registrationPlates && registrationPlates.length > 0 && (
              <div className="rounded-lg border border-blue-500/20 bg-blue-950/20 p-3 flex items-center justify-between">
                <span className="text-xs text-blue-300 font-medium">
                  {'Registration plates:'}
                </span>
                <PolishLicensePlateBadge plates={registrationPlates} />
              </div>
            )}

            {/* Attribution */}
            {attribution && (
              <div className="text-[11px] text-zinc-400 border-t border-white/5 pt-2">
                {attribution.title && <div>{attribution.title}</div>}
                {(attribution.artist || attribution.author) && (
                  <div>
                    {'Author: '}
                    {attribution.artist || attribution.author} {attribution.license ? `(${attribution.license})` : ''}
                  </div>
                )}
              </div>
            )}

            {/* Buttons */}
            <div className="flex items-center gap-2 pt-2 border-t border-white/10">
              <button
                type="button"
                onClick={handleShare}
                className="flex-1 inline-flex items-center justify-center gap-2 rounded-sm bg-emerald-600 px-4 py-2 text-xs sm:text-sm font-semibold text-white shadow-xs hover:bg-emerald-500 transition-colors cursor-pointer"
              >
                {copied ? <Check size={15} /> : <Share2 size={15} />}
                <span>{copied ? ('Copied!') : 'Share Results'}</span>
              </button>

              <button
                type="button"
                onClick={() => {
                  setShowResultsModal(false);
                  if (mode === 'challenge') {
                    loadChallenge('challenge', `challenge-${Date.now()}`);
                  } else {
                    setMode('challenge');
                    loadChallenge('challenge', `challenge-${Date.now()}`);
                  }
                }}
                className="inline-flex items-center justify-center gap-1.5 rounded-sm border border-sand-700 bg-sand-900/60 px-4 py-2 text-xs sm:text-sm font-semibold text-sand-200 hover:bg-sand-800 transition-colors cursor-pointer"
              >
                <RefreshCw size={14} />
                <span>{'New Challenge'}</span>
              </button>
            </div>
          </section>
        </div>
      )}

      {/* 7. Instructions Modal */}
      {showInstructions && (
        <div className="fixed inset-0 z-[2000] flex max-h-[var(--app-height,100dvh)] items-center justify-center p-2 pb-[calc(env(safe-area-inset-bottom)+0.5rem)] sm:px-6 sm:pt-6 sm:pb-[calc(env(safe-area-inset-bottom)+1.5rem)] overflow-y-auto md:z-50 md:max-h-none">
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black/85 backdrop-blur-md transition-opacity cursor-pointer"
            onClick={handleCloseInstructions}
            aria-hidden="true"
          />

          <section
            role="dialog"
            aria-modal="true"
            aria-label={'How to Play County Coats of Arms'}
            className="relative z-10 w-full max-w-3xl max-h-full overflow-y-auto rounded-xl border border-white/15 bg-obsidian-950 p-4 md:max-h-[92vh] sm:p-8 shadow-2xl space-y-4 sm:space-y-6 my-auto text-sand-100"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between border-b border-white/10 pb-4 text-left gap-4">
              <div>
                <h2 className="text-2xl sm:text-3xl font-serif font-bold tracking-tight text-sand-100 flex items-center gap-2.5">
                  <Shield className="text-emerald-400" size={26} />
                  <span>{'How to Play County Coats of Arms'}</span>
                </h2>
                <p className="mt-1.5 text-sm text-zinc-400 leading-relaxed max-w-xl">
                  {'Deduce the Polish county from its official coat of arms in 8 guesses or fewer.'}
                </p>
              </div>
              <button
                type="button"
                onClick={handleCloseInstructions}
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-sm bg-white/5 text-zinc-400 hover:bg-white/15 hover:text-white transition-colors cursor-pointer"
                aria-label={'Close'}
              >
                <X size={16} />
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="rounded-lg border border-emerald-500/30 bg-obsidian-900/80 p-5 space-y-2 flex flex-col justify-between">
                <div>
                  <div className="font-mono text-xs font-bold uppercase tracking-wider text-emerald-400 flex items-center gap-2">
                    <Shield size={16} />
                    <span>1. {'Official Heraldic Shield'}</span>
                  </div>
                  <p className="mt-2 text-xs sm:text-sm text-zinc-300 leading-relaxed">
                    {'Each puzzle displays the authentic coat of arms of one of Poland\'s 380 counties (land or city counties), sourced from Wikimedia Commons and Wikidata.'}
                  </p>
                </div>
                <div className="pt-2 border-t border-white/5 text-[11px] font-mono text-zinc-500">
                  {'Vector SVG artwork'}
                </div>
              </div>

              <div className="rounded-lg border border-blue-500/30 bg-obsidian-900/80 p-5 space-y-2 flex flex-col justify-between">
                <div>
                  <div className="font-mono text-xs font-bold uppercase tracking-wider text-blue-400 flex items-center gap-2">
                    <Car size={16} />
                    <span>2. {'Plate Code Reveal after 5 Guesses'}</span>
                  </div>
                  <p className="mt-2 text-xs sm:text-sm text-zinc-300 leading-relaxed">
                    {'After 5 wrong guesses, the target county\'s official registration plate prefix (e.g. PO for Poznań or KRA for Krakow land county) is automatically revealed.'}
                  </p>
                </div>
                <div className="pt-2 border-t border-white/5 text-[11px] font-mono text-zinc-500">
                  {'Automatic unlock'}
                </div>
              </div>

              <div className="rounded-lg border border-amber-500/30 bg-obsidian-900/80 p-5 space-y-2 flex flex-col justify-between">
                <div>
                  <div className="font-mono text-xs font-bold uppercase tracking-wider text-amber-400 flex items-center gap-2">
                    <Compass size={16} />
                    <span>3. {'Distance & Direction'}</span>
                  </div>
                  <p className="mt-2 text-xs sm:text-sm text-zinc-300 leading-relaxed">
                    {'Every missed attempt shows distance in kilometers between county centroids along with a compass direction arrow.'}
                  </p>
                </div>
                <div className="pt-2 border-t border-white/5 text-[11px] font-mono text-zinc-500">
                  {'Geographic feedback'}
                </div>
              </div>

              <div className="rounded-lg border border-purple-500/30 bg-obsidian-900/80 p-5 space-y-2 flex flex-col justify-between">
                <div>
                  <div className="font-mono text-xs font-bold uppercase tracking-wider text-purple-400 flex items-center gap-2">
                    <Sparkles size={16} />
                    <span>4. {'Voivodeship Match'}</span>
                  </div>
                  <p className="mt-2 text-xs sm:text-sm text-zinc-300 leading-relaxed">
                    {'A 🟩 tag shows that your guess is located in the same voivodeship as the mystery county. A ⬛ tag indicates a different province.'}
                  </p>
                </div>
                <div className="pt-2 border-t border-white/5 text-[11px] font-mono text-zinc-500">
                  {'16 Polish provinces'}
                </div>
              </div>
            </div>

            <div className="pt-3 border-t border-white/10 flex justify-end">
              <button
                type="button"
                onClick={handleCloseInstructions}
                className="w-full sm:w-auto px-6 py-2.5 rounded-sm bg-emerald-600 text-white font-semibold text-sm hover:bg-emerald-500 transition-colors cursor-pointer"
              >
                {'Got it, let\'s play!'}
              </button>
            </div>
          </section>
        </div>
      )}

      {/* Fullscreen Coat of Arms Inspection Lightbox */}
      {isFullscreenOpen && resolvedCoatUrl && !imageError && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={'Fullscreen coat of arms inspection'}
          className="fixed inset-0 z-[2100] flex flex-col bg-obsidian-950/95 backdrop-blur-md animate-fade-in"
          onClick={() => setIsFullscreenOpen(false)}
        >
          {/* Top Toolbar */}
          <div
            className="flex flex-wrap items-center justify-between gap-2 sm:gap-3 border-b border-white/10 bg-obsidian-900/90 px-3 py-2 sm:px-6 sm:py-3"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-2 text-xs sm:text-sm font-semibold text-sand-100">
              <Shield size={16} className="text-emerald-400 shrink-0" />
              <span className="truncate">
                {targetPowiat
                  ? targetPowiat.name
                  : 'Coat of Arms Detail Inspector'}
              </span>
            </div>

            <div className="flex flex-wrap items-center gap-1.5 sm:gap-2">
              {/* Zoom Controls */}
              <div className="inline-flex items-center rounded-sm border border-white/15 bg-obsidian-950 p-0.5 text-xs font-mono">
                <button
                  type="button"
                  onClick={() => setZoomLevel((z) => Math.max(1, Number((z - 0.5).toFixed(1))))}
                  disabled={zoomLevel <= 1}
                  className="inline-flex h-8 w-8 items-center justify-center rounded-xs text-zinc-300 hover:bg-white/10 hover:text-white disabled:opacity-40 cursor-pointer"
                  aria-label={'Zoom out'}
                  title={'Zoom out'}
                >
                  <ZoomOut size={14} />
                </button>
                <button
                  type="button"
                  onClick={() => setZoomLevel(1)}
                  className="px-2 h-8 text-sand-100 hover:bg-white/10 rounded-xs cursor-pointer text-xs"
                  title={'Reset zoom'}
                >
                  {Math.round(zoomLevel * 100)}%
                </button>
                <button
                  type="button"
                  onClick={() => setZoomLevel((z) => Math.min(3, Number((z + 0.5).toFixed(1))))}
                  disabled={zoomLevel >= 3}
                  className="inline-flex h-8 w-8 items-center justify-center rounded-xs text-zinc-300 hover:bg-white/10 hover:text-white disabled:opacity-40 cursor-pointer"
                  aria-label={'Zoom in'}
                  title={'Zoom in'}
                >
                  <ZoomIn size={14} />
                </button>
              </div>

              {/* Backdrop Contrast Toggle (helpful for dark heraldic charges) */}
              <button
                type="button"
                onClick={() => setLightBackdrop((prev) => !prev)}
                className="inline-flex h-8 sm:h-9 items-center gap-1.5 rounded-sm border border-white/15 bg-obsidian-950 px-2 sm:px-3 text-xs font-medium text-zinc-200 hover:bg-white/10 hover:text-white transition-colors cursor-pointer"
                title={'Toggle background contrast'}
              >
                {lightBackdrop ? <Moon size={13} className="text-sky-300" /> : <Sun size={13} className="text-amber-300" />}
                <span className="hidden xs:inline">{lightBackdrop ? ('Dark bg') : ('Light bg')}</span>
              </button>

              {/* Close Button */}
              <button
                type="button"
                onClick={() => setIsFullscreenOpen(false)}
                className="inline-flex h-8 sm:h-9 items-center gap-1 rounded-sm border border-white/15 bg-white/10 px-2 sm:px-3 text-xs font-semibold text-sand-100 hover:bg-white/20 transition-colors cursor-pointer"
                aria-label={'Close fullscreen'}
              >
                <X size={14} />
                <span>{'Close'}<span className="hidden sm:inline"> (Esc)</span></span>
              </button>
            </div>
          </div>

          {/* Scrollable / Zoomable Shield Canvas */}
          <div className="flex-1 overflow-auto flex items-center justify-center p-4 sm:p-8">
            <div
              onClick={(e) => e.stopPropagation()}
              className={`relative flex items-center justify-center rounded-2xl border p-6 sm:p-10 shadow-2xl transition-colors duration-200 ${
                lightBackdrop
                  ? 'border-zinc-300 bg-stone-100 shadow-black/50'
                  : 'border-white/15 bg-obsidian-900/95 shadow-black/80'
              }`}
            >
              <img
                src={
                  retryNonce > 0
                    ? `${resolvedCoatUrl}${resolvedCoatUrl.includes('?') ? '&' : '?'}retry=${retryNonce}`
                    : resolvedCoatUrl
                }
                alt={
                  targetPowiat
                    ? `Coat of arms of ${targetPowiat.name}`
                    : 'Polish county coat of arms (fullscreen)'
                }
                style={{
                  height: `${Math.round(68 * zoomLevel)}vh`,
                  maxHeight: `${Math.round(68 * zoomLevel)}vh`,
                  width: 'auto',
                }}
                className="max-w-[88vw] object-contain select-none filter drop-shadow-2xl transition-all duration-150"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
