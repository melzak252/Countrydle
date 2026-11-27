import React, { useEffect, useMemo, useRef, useState, useCallback } from 'react';
import toast from 'react-hot-toast';
import {
  HelpCircle,
  Share2,
  Check,
  X,
  Trophy,
  ArrowRight,
  Palette,
  Lock,
  RefreshCw,
  Loader2,
} from 'lucide-react';
import GrayscaleFlagCanvas from '../components/GrayscaleFlagCanvas';
import GameResultDashboard from '../components/result-dashboard/GameResultDashboard';
import { flagShadesService } from '../services/api';
import type { FlagdleCountry, FlagShadesChallenge, FlagShadesGuessResult } from '../types';

type GameMode = 'daily' | 'challenge';

interface StoredDailyState {
  date: string;
  seed: string;
  token: string;
  flag_asset_url: string;
  guesses: FlagShadesGuessResult[];
  colorHintUsed: boolean;
  isGameOver: boolean;
  won: boolean;
  targetCountry: { id: number; name: string } | null;
}

const FLAG_SHADES_GUIDE_KEY = 'flag_shades_guide_seen';

export default function FlagShadesPage() {

  // Mode state
  const [mode, setMode] = useState<GameMode>('daily');
  const [challenge, setChallenge] = useState<FlagShadesChallenge | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  // Gameplay state
  const [guesses, setGuesses] = useState<FlagShadesGuessResult[]>([]);
  const [colorHintUsed, setColorHintUsed] = useState<boolean>(false);
  const [isGameOver, setIsGameOver] = useState<boolean>(false);
  const [won, setWon] = useState<boolean>(false);
  const [targetCountry, setTargetCountry] = useState<{ id: number; name: string } | null>(null);
  const [hintInfo, setHintInfo] = useState<{ colorName: string; sharePct: number } | null>(null);

  // Countries for autocomplete
  const [countries, setCountries] = useState<FlagdleCountry[]>([]);
  const [inputVal, setInputVal] = useState<string>('');
  const [selectedCountry, setSelectedCountry] = useState<FlagdleCountry | null>(null);
  const [showSuggestions, setShowSuggestions] = useState<boolean>(false);
  const [highlightedIndex, setHighlightedIndex] = useState<number>(0);

  // UI state
  const [copied, setCopied] = useState<boolean>(false);
  const [showResultsModal, setShowResultsModal] = useState<boolean>(false);
  const [showInstructions, setShowInstructions] = useState<boolean>(() => {
    try {
      return localStorage.getItem(FLAG_SHADES_GUIDE_KEY) !== 'true';
    } catch {
      return false;
    }
  });

  const inputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Resolve Flag URL
  const resolvedFlagUrl = useMemo(() => {
    if (!challenge?.flag_asset_url) return null;
    const url = challenge.flag_asset_url;
    if (url.startsWith('http://') || url.startsWith('https://')) {
      return url;
    }
    const cleanPath = url.startsWith('/') ? url : `/${url}`;
    if (!cleanPath.startsWith('/api')) {
      return `/api${cleanPath}`;
    }
    return cleanPath;
  }, [challenge?.flag_asset_url]);

  // Load countries once
  useEffect(() => {
    let mounted = true;
    flagShadesService
      .getCountries()
      .then((data) => {
        if (mounted) setCountries(data);
      })
      .catch((err) => {
        console.error('Failed to load countries for Flag Shades:', err);
      });
    return () => {
      mounted = false;
    };
  }, []);

  // Helper to persist daily state into localStorage
  const persistDailyState = useCallback(
    (date: string, partial: Partial<StoredDailyState>) => {
      try {
        const key = `flag_shades_daily_${date}`;
        const existingRaw = localStorage.getItem(key);
        const existing: Partial<StoredDailyState> = existingRaw ? JSON.parse(existingRaw) : {};
        const updated: StoredDailyState = {
          date,
          seed: partial.seed ?? existing.seed ?? '',
          token: partial.token ?? existing.token ?? '',
          flag_asset_url: partial.flag_asset_url ?? existing.flag_asset_url ?? '',
          guesses: partial.guesses ?? existing.guesses ?? [],
          colorHintUsed: partial.colorHintUsed ?? existing.colorHintUsed ?? false,
          isGameOver: partial.isGameOver ?? existing.isGameOver ?? false,
          won: partial.won ?? existing.won ?? false,
          targetCountry: partial.targetCountry !== undefined ? partial.targetCountry : (existing.targetCountry ?? null),
        };
        localStorage.setItem(key, JSON.stringify(updated));
      } catch (e) {
        console.warn('Failed to save Flag Shades daily progress in localStorage:', e);
      }
    },
    []
  );

  // Load challenge for given mode and optional seed
  const loadChallenge = useCallback(
    async (targetMode: GameMode, customSeed?: string) => {
      setIsLoading(true);
      setInputVal('');
      setSelectedCountry(null);
      setShowSuggestions(false);

      try {
        const seedParam = targetMode === 'daily' ? undefined : (customSeed || `challenge-${Date.now()}`);
        const ch = await flagShadesService.getChallenge(seedParam);
        setChallenge(ch);

        if (targetMode === 'daily') {
          // Check local storage for existing daily puzzle session
          const storageKey = `flag_shades_daily_${ch.date}`;
          let saved: StoredDailyState | null = null;
          try {
            const raw = localStorage.getItem(storageKey);
            if (raw) saved = JSON.parse(raw);
          } catch {
            saved = null;
          }

          if (saved && saved.date === ch.date && Array.isArray(saved.guesses)) {
            setGuesses(saved.guesses);
            setColorHintUsed(saved.colorHintUsed || false);
            setIsGameOver(saved.isGameOver || false);
            setWon(saved.won || false);
            setTargetCountry(saved.targetCountry || null);
            if (saved.isGameOver) {
              setShowResultsModal(true);
            }
          } else {
            // Fresh daily round
            setGuesses([]);
            setColorHintUsed(false);
            setIsGameOver(false);
            setWon(false);
            setTargetCountry(null);
            setShowResultsModal(false);
            persistDailyState(ch.date, {
              date: ch.date,
              seed: ch.seed,
              token: ch.token,
              flag_asset_url: ch.flag_asset_url,
              guesses: [],
              colorHintUsed: false,
              isGameOver: false,
              won: false,
              targetCountry: null,
            });
          }
        } else {
          // Challenge mode: fresh round
          setGuesses([]);
          setColorHintUsed(false);
          setIsGameOver(false);
          setWon(false);
          setTargetCountry(null);
          setShowResultsModal(false);
        }
      } catch (err) {
        console.error('Failed to load Flag Shades challenge:', err);
        toast.error('Failed to load flag challenge.');
      } finally {
        setIsLoading(false);
      }
    },
    [persistDailyState]
  );

  // Initial load on mount or when mode toggles
  useEffect(() => {
    loadChallenge(mode);
  }, [mode, loadChallenge]);

  // Handle mode toggle
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

  const handleCloseInstructions = () => {
    setShowInstructions(false);
    try {
      localStorage.setItem(FLAG_SHADES_GUIDE_KEY, 'true');
    } catch {
      // ignore
    }
  };

  // Filter countries for autocomplete
  const filteredCountries = useMemo(() => {
    const query = inputVal.trim().toLowerCase();
    if (!query) return [];
    const guessedIds = new Set(guesses.map((g) => g.country_id).filter(Boolean));
    const guessedNames = new Set(guesses.map((g) => g.guess.toLowerCase()));

    return countries
      .filter(
        (c) =>
          !guessedIds.has(c.id) &&
          !guessedNames.has(c.name.toLowerCase()) &&
          (c.name.toLowerCase().includes(query) ||
            (c.official_name && c.official_name.toLowerCase().includes(query)))
      )
      .slice(0, 8);
  }, [countries, inputVal, guesses]);

  const handleSelectCountry = (country: FlagdleCountry) => {
    setSelectedCountry(country);
    setInputVal(country.name);
    setShowSuggestions(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!showSuggestions || filteredCountries.length === 0) {
      if (e.key === 'Enter') {
        handleSubmitGuess();
      }
      return;
    }

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlightedIndex((prev) => (prev + 1) % filteredCountries.length);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlightedIndex((prev) => (prev - 1 + filteredCountries.length) % filteredCountries.length);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      const target = filteredCountries[highlightedIndex];
      if (target) {
        handleSelectCountry(target);
      }
    } else if (e.key === 'Escape') {
      setShowSuggestions(false);
    }
  };

  const handleSubmitGuess = async () => {
    if (isGameOver || isSubmitting || !challenge) return;
    const name = (selectedCountry ? selectedCountry.name : inputVal).trim();
    if (!name) return;

    const guessedNames = new Set(guesses.map((g) => g.guess.toLowerCase()));
    if (guessedNames.has(name.toLowerCase())) {
      toast.error('You already guessed this country!');
      return;
    }

    let countryId = selectedCountry?.id;
    if (!countryId) {
      const match = countries.find(
        (c) =>
          c.name.toLowerCase() === name.toLowerCase() ||
          (c.official_name && c.official_name.toLowerCase() === name.toLowerCase())
      );
      if (match) {
        countryId = match.id;
      }
    }

    if (!countryId || !countries.some((c) => c.id === countryId)) {
      toast.error(
        'Please select a valid sovereign country from the list.'
      );
      return;
    }

    if (guesses.some((g) => g.country_id === countryId)) {
      toast.error('You already guessed this country!');
      return;
    }

    setIsSubmitting(true);
    try {
      const result = await flagShadesService.submitGuess({
        token: challenge.token,
        guess: name,
        country_id: countryId,
        guesses_made: guesses.length + 1,
      });

      const nextGuesses = [...guesses, result];
      setGuesses(nextGuesses);
      setInputVal('');
      setSelectedCountry(null);
      setShowSuggestions(false);

      const nextGameOver = result.is_game_over;
      const nextWon = result.won;
      const nextTarget = result.target_country || null;

      if (nextGameOver) {
        setIsGameOver(true);
        setWon(nextWon);
        if (nextTarget) setTargetCountry(nextTarget);
        setShowResultsModal(true);
      }

      if (mode === 'daily' && challenge.date) {
        persistDailyState(challenge.date, {
          guesses: nextGuesses,
          isGameOver: nextGameOver,
          won: nextWon,
          targetCountry: nextTarget,
        });
      }
    } catch (err) {
      console.error('Failed to submit Flag Shades guess:', err);
      toast.error('Error submitting your guess.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRevealColorHint = () => {
    if (colorHintUsed || isGameOver || guesses.length < (challenge?.hint_unlock_guesses || 3)) {
      return;
    }
    setColorHintUsed(true);
    if (mode === 'daily' && challenge?.date) {
      persistDailyState(challenge.date, { colorHintUsed: true });
    }
    toast.success(
      '1 color hint revealed on the flag (≥10% of flag)!'
    );
  };

  const maxGuesses = challenge?.max_guesses || 12;
  const hintUnlockThreshold = challenge?.hint_unlock_guesses || 3;
  const canUnlockHint = !colorHintUsed && !isGameOver && guesses.length >= hintUnlockThreshold;
  const hintLocked = !colorHintUsed && !isGameOver && guesses.length < hintUnlockThreshold;

  const buildShareText = () => {
    if (!challenge) return '';
    const scoreText = won ? `${guesses.length}/${maxGuesses}` : `X/${maxGuesses}`;
    const hintBadge = colorHintUsed
      ? ('🎨 Color Hint used')
      : ('🖤 Pure Grayscale solve');
    const headerTitle =
      mode === 'daily'
        ? (`Flag Shades · ${challenge.date}`)
        : ('Flag Shades · Challenge');

    const lines: string[] = [];
    lines.push(headerTitle);
    lines.push(`${scoreText} guesses · ${hintBadge}`);
    lines.push('');

    guesses.forEach((g) => {
      if (g.answer) {
        lines.push('🟩 🎯');
      } else {
        const isClose =
          (g.distance_km !== null && g.distance_km !== undefined && g.distance_km < 2500) ||
          (g.matched_symbols && g.matched_symbols.length > 0);
        const tile = isClose ? '🟨' : '⬛';
        const arrow = g.bearing_arrow ? `${g.bearing_arrow} ` : '';
        const dist = g.distance_km !== null && g.distance_km !== undefined ? `${g.distance_km.toLocaleString('en-US')} km` : '';
        const sym = g.matched_symbols && g.matched_symbols.length > 0 ? ` ✦${g.matched_symbols.length}` : '';
        lines.push(`${tile} ${arrow}${dist}${sym}`.trim());
      }
    });

    lines.push('');
    lines.push(
      typeof window !== 'undefined'
        ? `${window.location.origin}/flag-shades`
        : 'https://countrydle.online/flag-shades'
    );

    return lines.join('\n');
  };

  const handleShare = () => {
    const fullShareText = buildShareText();
    if (!fullShareText) return;
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
      <div role="status" className="flex h-[60vh] items-center justify-center gap-3 text-app-accent">
        <Loader2 className="animate-spin" size={24} aria-hidden="true" />
        <span className="text-sm font-medium text-app-text-secondary">
          {'Loading Flag Shades...'}
        </span>
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-4xl px-3 py-2 sm:px-6 sm:py-4">
      {/* Header Bar */}
      <header className="mb-2.5 border-b border-app-border/30 pb-2.5 sm:mb-6 sm:pb-4 space-y-2 sm:space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2 sm:gap-3">
          <div className="min-w-0">
            <div className="mb-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs font-mono font-semibold text-app-text-muted sm:mb-1">
              <span className="inline-flex items-center gap-1.5 shrink-0 whitespace-nowrap">
                <Palette size={14} className="text-app-accent shrink-0" />
                <span>{'Grayscale Deduction'}</span>
              </span>
              <span className="text-app-text-muted hidden min-[340px]:inline select-none" aria-hidden="true">•</span>
              <span className="whitespace-nowrap shrink-0 text-app-text-secondary">
                {mode === 'daily' ? challenge?.date || 'Daily' : 'Challenge'}
              </span>
            </div>
            <h1 className="text-xl font-bold tracking-tight text-app-text sm:text-3xl">
              {'Flag Shades'}
            </h1>
            <p className="mt-0.5 text-xs text-app-text-secondary sm:text-sm leading-snug">
              {'Identify the national flag rendered entirely in shades of grey.'}
            </p>
          </div>

          <div className="flex items-center gap-2 sm:gap-3">
            {/* Guesses Remaining Pill */}
            <div className="flex items-center rounded-sm border border-app-border/25 bg-app-surface-raised px-2 py-1 shadow-sm sm:px-3.5 sm:py-2">
              <span className="mr-1.5 font-mono text-xs text-app-text-muted sm:mr-2">
                {'Guesses:'}
              </span>
              <span
                className={`font-mono text-sm sm:text-base font-bold ${
                  guesses.length >= maxGuesses - 2 ? 'text-amber-800' : 'text-app-accent'
                }`}
              >
                {guesses.length}
              </span>
              <span className="font-mono text-[11px] sm:text-xs text-app-text-muted"> / {maxGuesses}</span>
            </div>

            {/* Help Modal Button */}
            <button
              type="button"
              onClick={() => setShowInstructions(true)}
              className="flex h-11 w-11 sm:h-9 sm:w-9 items-center justify-center rounded-sm border border-app-border/30 bg-app-surface-raised text-app-text-secondary hover:border-app-accent/50 hover:text-app-accent transition-colors shrink-0"
              title={'How to play Flag Shades'}
              aria-label={'Instructions'}
            >
              <HelpCircle size={18} />
            </button>

            {/* Results Button when Game is Over */}
            {isGameOver && (
              <button
                type="button"
                onClick={() => setShowResultsModal(true)}
                className="flex min-h-[44px] sm:min-h-0 sm:h-9 items-center gap-1.5 px-3 rounded-sm border border-app-accent/30 bg-app-accent/10 text-app-accent hover:bg-app-accent/15 transition-colors text-xs font-semibold cursor-pointer shrink-0"
                title={'Show results'}
              >
                <Trophy size={15} />
                <span>{'Results'}</span>
              </button>
            )}
          </div>
        </div>

        {/* Mode Switcher Bar */}
        <div className="flex flex-wrap items-center justify-between gap-1.5 sm:gap-2 pt-1 border-t border-app-border/20">
          <div className="inline-flex rounded-sm border border-app-border/30 bg-app-surface-muted p-0.5 sm:p-1 text-xs font-medium">
            <button
              type="button"
              onClick={() => handleSwitchMode('daily')}
              className={`px-2.5 py-1 sm:px-3 sm:py-1.5 rounded-xs transition-colors cursor-pointer text-[11px] sm:text-xs ${
                mode === 'daily'
                  ? 'bg-app-accent/10 text-app-accent font-semibold shadow-xs'
                  : 'text-app-text-secondary hover:text-app-text'
              }`}
            >
              📅 {'Daily Puzzle'}
            </button>
            <button
              type="button"
              onClick={() => handleSwitchMode('challenge')}
              className={`px-2.5 py-1 sm:px-3 sm:py-1.5 rounded-xs transition-colors cursor-pointer text-[11px] sm:text-xs ${
                mode === 'challenge'
                  ? 'bg-app-accent/10 text-app-accent font-semibold shadow-xs'
                  : 'text-app-text-secondary hover:text-app-text'
              }`}
            >
              ⚡ {'Challenge Mode'}
            </button>
          </div>

          {mode === 'challenge' && (
            <button
              type="button"
              onClick={() => loadChallenge('challenge', `challenge-${Date.now()}`)}
              disabled={isLoading}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 sm:px-3 sm:py-1.5 rounded-sm border border-app-border/30 bg-app-surface-raised text-app-text-secondary hover:bg-app-surface-muted text-[11px] sm:text-xs font-medium transition-colors cursor-pointer disabled:opacity-50"
            >
              <RefreshCw size={13} className={isLoading ? 'animate-spin' : ''} />
              <span>{'New Challenge'}</span>
            </button>
          )}
        </div>
      </header>

      {/* Main Content Area */}
      <main className="space-y-2.5 sm:space-y-6">
        {/* 1. Grayscale Flag Canvas Container */}
        <section aria-label={'Grayscale Flag Display'}>
          <GrayscaleFlagCanvas
            stage={guesses.length + 1}
            flagUrl={resolvedFlagUrl}
            revealColorHint={colorHintUsed}
            isGameOver={isGameOver}
            countryName={targetCountry?.name}
            onHintInfoChange={setHintInfo}
          />
        </section>

        {/* 2. Color Hint Control Bar */}
        <section aria-label={'Color Hint Control'} className="mx-auto w-full max-w-xl">
          {hintLocked && (
            <button
              type="button"
              disabled
              className="flex min-h-[44px] w-full items-center justify-between rounded-sm border border-app-border/25 bg-app-surface-muted px-3 py-2 sm:px-4 sm:py-2.5 text-xs text-app-text-secondary cursor-not-allowed"
            >
              <div className="flex items-center gap-2 min-w-0 text-left">
                <Lock size={15} className="text-app-text-muted shrink-0" />
                <span className="leading-snug sm:leading-normal">
                  {`Color Hint unlocks after 3 guesses (${guesses.length}/${hintUnlockThreshold})`}
                </span>
              </div>
              <span className="font-mono text-[11px] text-app-text-muted shrink-0 ml-2 whitespace-nowrap">
                {hintUnlockThreshold - guesses.length} {'left'}
              </span>
            </button>
          )}

          {canUnlockHint && (
            <button
              type="button"
              onClick={handleRevealColorHint}
              className="flex min-h-[44px] w-full items-center justify-center gap-2 rounded-sm border border-amber-300 bg-amber-50 px-3 py-2 sm:px-4 sm:py-3 text-xs sm:text-sm font-semibold text-amber-900 transition-colors hover:border-amber-400 hover:bg-amber-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-amber-700 cursor-pointer"
            >
              <Palette size={16} className="shrink-0 sm:h-[18px] sm:w-[18px]" />
              <span className="text-center leading-snug sm:leading-normal">
                {'Reveal 1 Color Hint (≥10% of flag)'}
              </span>
            </button>
          )}

          {!isGameOver && colorHintUsed && (
            <div className="flex min-h-[44px] items-center justify-between rounded-sm border border-app-accent/30 bg-app-accent/10 px-3 py-2 sm:px-4 sm:py-2.5 text-xs text-app-accent font-medium">
              <div className="flex items-center gap-2 min-w-0 text-left">
                <Palette size={15} className="text-app-accent shrink-0" />
                <span className="leading-snug sm:leading-normal">
                  {`Color Hint Active: ${hintInfo?.colorName || '1 color'} restored (${hintInfo?.sharePct || '≥10'}% of flag)`}
                </span>
              </div>
              <span className="rounded-sm bg-app-accent/10 px-2 py-0.5 font-mono text-[10px] uppercase font-bold text-app-accent shrink-0 ml-2 whitespace-nowrap">
                {'Active'}
              </span>
            </div>
          )}
        </section>

        {/* 3. Autocomplete Guess Input */}
        {!isGameOver && (
          <section aria-label={'Guess Input'} className="mx-auto w-full max-w-xl">
            <div className="relative">
              <div className="flex items-center gap-2">
                <div className="relative flex-1 min-w-0">
                  <input
                    ref={inputRef}
                    type="text"
                    value={inputVal}
                    onChange={(e) => {
                      setInputVal(e.target.value);
                      setSelectedCountry(null);
                      setShowSuggestions(true);
                      setHighlightedIndex(0);
                    }}
                    onFocus={() => {
                      if (inputVal.trim()) setShowSuggestions(true);
                    }}
                    onKeyDown={handleKeyDown}
                    placeholder={
                      'Search flag by country name...'
                    }
                    disabled={isSubmitting || isLoading}
                    className="w-full min-w-0 rounded-sm border border-app-border/35 bg-app-surface-raised px-3 py-2.5 text-base md:text-sm text-app-text placeholder:text-app-text-muted focus:border-app-focus focus:outline-none focus:ring-1 focus:ring-app-focus/20 disabled:bg-app-surface-muted disabled:text-app-text-muted disabled:opacity-100 sm:px-4 sm:py-3"
                  />

                  {/* Autocomplete Dropdown */}
                  {showSuggestions && filteredCountries.length > 0 && (
                    <div
                      ref={dropdownRef}
                      className="absolute left-0 right-0 z-50 mt-1 max-h-60 overflow-y-auto rounded-sm border border-app-border/30 bg-app-surface-raised shadow-sm"
                    >
                      {filteredCountries.map((c, idx) => (
                        <button
                          key={c.id}
                          type="button"
                          onMouseDown={(e) => {
                            e.preventDefault();
                            handleSelectCountry(c);
                          }}
                          className={`w-full px-4 py-2.5 text-left text-sm transition-colors flex items-center justify-between ${
                            idx === highlightedIndex
                              ? 'bg-app-accent/10 text-app-accent'
                              : 'text-app-text-secondary hover:bg-app-surface-muted'
                          }`}
                        >
                          <span className="font-medium">{c.name}</span>
                          {c.official_name && c.official_name !== c.name && (
                            <span className="text-xs text-app-text-muted truncate max-w-[200px] ml-2">
                              {c.official_name}
                            </span>
                          )}
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                <button
                  type="button"
                  onClick={handleSubmitGuess}
                  disabled={isSubmitting || isLoading || !inputVal.trim()}
                  className="inline-flex min-h-[44px] items-center justify-center gap-1.5 rounded-sm bg-app-accent hover:bg-app-accent-hover px-3.5 sm:px-4 py-2 text-sm font-semibold text-white transition-colors shadow-sm disabled:opacity-60 disabled:cursor-not-allowed cursor-pointer shrink-0"
                >
                  {isSubmitting ? (
                    <Loader2 size={16} className="animate-spin" />
                  ) : (
                    <>
                      <span>{'Guess'}</span>
                      <ArrowRight size={16} />
                    </>
                  )}
                </button>
              </div>
            </div>
          </section>
        )}

        {/* 4. Previous Guesses Trail */}
        {guesses.length > 0 && (
          <section aria-label={'Guess History'} className="mx-auto w-full max-w-xl space-y-2">
            <div className="flex items-center justify-between px-1">
              <span className="text-xs font-mono text-app-text-secondary">
                {'Your Guesses'}
              </span>
              <span className="text-xs font-mono text-app-text-muted">
                {guesses.length} / {maxGuesses}
              </span>
            </div>

            <ul className="space-y-2">
              {sortedGuesses.map((g, idx) => (
                <li
                  key={idx}
                  className={`rounded-sm border border-app-border/25 border-l-2 bg-app-surface-raised p-3 sm:px-4 sm:py-3 transition-colors ${
                    g.answer ? 'border-l-app-accent shadow-sm' : 'border-l-rose-400'
                  }`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-3 min-w-0">
                      {g.answer ? (
                        <Check size={18} className="shrink-0 text-app-accent" aria-hidden="true" />
                      ) : (
                        <X size={18} className="shrink-0 text-rose-700" aria-hidden="true" />
                      )}
                      <span className="truncate text-sm font-semibold text-app-text">{g.guess}</span>
                    </div>

                    {/* Distance & Bearing Arrow */}
                    {g.distance_km !== null && g.distance_km !== undefined && !g.answer && (
                      <div className="flex items-center gap-2 font-mono text-xs text-app-text-secondary">
                        <span className="rounded-sm border border-app-border/25 bg-app-surface-muted px-2 py-0.5">
                          {g.distance_km.toLocaleString('en-US')} km
                        </span>
                        {g.bearing_arrow && (
                          <span className="text-app-accent text-sm font-bold" title={g.bearing_direction || ''}>
                            {g.bearing_arrow}
                          </span>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Clues Trail: Matched Symbols & (Post-Game only) Colors */}
                  <div className="mt-2 flex flex-wrap items-center gap-1.5">
                    {/* Matched Symbols Chips */}
                    {g.matched_symbols && g.matched_symbols.length > 0 && (
                      <div className="flex flex-wrap items-center gap-1">
                        {g.matched_symbols.map((sym) => (
                          <span
                            key={sym}
                            className="inline-flex items-center gap-1 rounded-sm border border-indigo-300 bg-indigo-50 px-2 py-0.5 text-[11px] font-mono text-indigo-900"
                          >
                            <span>✦</span>
                            <span>{sym}</span>
                          </span>
                        ))}
                      </div>
                    )}

                    {/* Colors Revealed AFTER Game Over Only (so no spoilers during grayscale play) */}
                    {isGameOver && g.matched_colors && g.matched_colors.length > 0 && (
                      <div className="flex flex-wrap items-center gap-1">
                        {g.matched_colors.map((c) => (
                          <span
                            key={c}
                            className="inline-flex items-center rounded-sm border border-app-accent/30 bg-app-accent/10 px-1.5 py-0.5 text-[10px] font-mono text-app-accent"
                          >
                            ✓ {c}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          </section>
        )}

        {/* 5. Game Over Banner */}
        {isGameOver && (
          <section
            aria-label={'Game Result Summary'}
            className="mx-auto w-full max-w-xl rounded-sm border border-app-accent/30 bg-app-surface-raised p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4"
          >
            <div>
              <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                <span className="font-mono text-xs text-app-accent font-semibold whitespace-nowrap">
                  {won ? ('Flag Identified') : ('Game Over')}
                </span>
                <span className="text-app-text-muted hidden min-[340px]:inline select-none" aria-hidden="true">·</span>
                <span className="text-xs font-mono text-app-text-secondary whitespace-nowrap">
                  {colorHintUsed
                    ? '🎨 Color Hint used'
                    : '🖤 Pure Grayscale solve'}
                </span>
              </div>
              <h3 className="text-lg sm:text-xl font-bold text-app-text mt-1">
                {targetCountry?.name || (won && guesses[guesses.length - 1]?.guess) || ('Mystery Country')}
              </h3>
              <p className="text-xs text-app-text-secondary mt-0.5">
                {won
                  ? `Solved in ${guesses.length} of ${maxGuesses} guesses.`
                  : 'All guesses used. Check out the revealed flag!'}
              </p>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setShowResultsModal(true)}
                className="inline-flex min-h-10 items-center gap-2 rounded-sm bg-app-accent hover:bg-app-accent-hover px-4 py-2 text-xs sm:text-sm font-semibold text-white transition-colors cursor-pointer"
              >
                <Trophy size={16} aria-hidden="true" />
                <span>{'View Results'}</span>
              </button>

              <button
                type="button"
                onClick={handleShare}
                className="inline-flex min-h-10 items-center gap-1.5 rounded-sm border border-app-border/30 bg-app-surface-muted hover:bg-app-surface-raised px-3 py-2 text-xs sm:text-sm font-semibold text-app-text-secondary transition-colors cursor-pointer"
                title={'Share'}
              >
                {copied ? <Check size={16} className="text-app-accent" /> : <Share2 size={16} />}
              </button>
            </div>
          </section>
        )}

        {/* 6. Results Dashboard */}
        {isGameOver && showResultsModal && (
          <GameResultDashboard
            mode="flag_shades"
            modeKind="visual"
            gameName="Flag Shades"
            gamePath="/flag-shades"
            date={challenge?.date}
            isDaily={mode === 'daily'}
            won={won}
            guessesMade={guesses.length}
            maxGuesses={maxGuesses}
            targetLabel="Secret National Flag"
            targetName={
              targetCountry?.name ||
              (won && guesses[guesses.length - 1]?.guess) ||
              'Mystery Country'
            }
            targetImageUrl={resolvedFlagUrl}
            subtitle={
              won
                ? `Identified in ${guesses.length} of ${maxGuesses} guesses · ${
                    colorHintUsed ? 'Color Hint used' : 'Pure Grayscale solve'
                  }`
                : `Used all ${maxGuesses} guesses.`
            }
            metrics={[
              { label: 'Guesses', value: `${guesses.length} / ${maxGuesses}` },
              {
                label: 'Solve Mode',
                value: colorHintUsed ? 'With Hint' : 'Pure Grayscale',
                accent: colorHintUsed ? 'amber' : 'emerald',
              },
            ]}
            shareText={buildShareText()}
            duelMode="countrydle"
            primaryAction={{
              label: 'Play Challenge Round',
              onClick: () => {
                setShowResultsModal(false);
                setMode('challenge');
                loadChallenge('challenge', `challenge-${Date.now()}`);
              },
              icon: <ArrowRight size={15} />,
            }}
            onClose={() => setShowResultsModal(false)}
            closeLabel="Close & View Flag"
          />
        )}
      </main>

      {/* 7. Instructions Modal */}
      {showInstructions && (
        <div className="fixed inset-0 z-[2000] flex max-h-[var(--app-height,100dvh)] items-center justify-center p-2 pb-[calc(env(safe-area-inset-bottom)+0.5rem)] sm:px-6 sm:pt-6 sm:pb-[calc(env(safe-area-inset-bottom)+1.5rem)] overflow-y-auto md:z-50 md:max-h-none">
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-app-canvas/85 backdrop-blur-sm transition-opacity cursor-pointer"
            onClick={handleCloseInstructions}
            aria-hidden="true"
          />

          <section
            role="dialog"
            aria-modal="true"
            aria-label={'How to Play Flag Shades'}
            className="relative z-10 w-full max-w-3xl max-h-full overflow-y-auto rounded-sm border border-app-border/30 bg-app-surface-raised p-4 md:max-h-[92vh] sm:p-8 shadow-sm space-y-4 sm:space-y-6 my-auto text-app-text"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between border-b border-app-border/25 pb-4 text-left gap-4">
              <div>
                <h2 className="text-2xl sm:text-3xl font-serif font-bold tracking-tight text-app-text flex items-center gap-2.5">
                  <Palette className="text-app-accent" size={26} />
                  <span>{'How to Play Flag Shades'}</span>
                </h2>
                <p className="mt-1.5 text-sm text-app-text-secondary leading-relaxed max-w-xl">
                  {'Deduce the secret national flag in 8 guesses or fewer. The full flag is shown in shades of grey.'}
                </p>
              </div>
              <button
                type="button"
                onClick={handleCloseInstructions}
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-sm bg-app-surface-muted text-app-text-secondary hover:bg-app-canvas hover:text-app-text transition-colors cursor-pointer"
                aria-label={'Close'}
              >
                <X size={16} />
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="rounded-sm border border-app-accent/30 bg-app-surface-raised p-5 space-y-2 flex flex-col justify-between">
                <div>
                  <div className="font-mono text-xs font-semibold text-app-text flex items-center gap-2">
                    <span>1. {'Luminance Grayscale'}</span>
                  </div>
                  <p className="mt-2 text-xs sm:text-sm text-app-text-secondary leading-relaxed">
                    {'All flag colors are transformed into perceptual luminance grayscale. Yellow renders light grey, navy renders dark grey, and white/black stay true.'}
                  </p>
                </div>
                <div className="pt-2 border-t border-app-border/25 text-[11px] font-mono text-app-text-muted">
                  {'Full flag visible from start'}
                </div>
              </div>

              <div className="rounded-sm border border-amber-300 bg-amber-50 p-5 space-y-2 flex flex-col justify-between">
                <div>
                  <div className="font-mono text-xs font-semibold text-app-text flex items-center gap-2">
                    <span>2. {'Color Hint after 3 Guesses'}</span>
                  </div>
                  <p className="mt-2 text-xs sm:text-sm text-app-text-secondary leading-relaxed">
                    {'After 3 guesses, unlock a color hint button that restores exactly 1 major chromatic color family (covering ≥10% of the flag image).'}
                  </p>
                </div>
                <div className="pt-2 border-t border-app-border/25 text-[11px] font-mono text-app-text-muted">
                  {'Optional hint after 3 attempts'}
                </div>
              </div>

              <div className="rounded-sm border border-cyan-300 bg-cyan-50 p-5 space-y-2 flex flex-col justify-between">
                <div>
                  <div className="font-mono text-xs font-semibold text-app-text flex items-center gap-2">
                    <span>3. {'Distance & Compass Bearing'}</span>
                  </div>
                  <p className="mt-2 text-xs sm:text-sm text-app-text-secondary leading-relaxed">
                    {'Each missed guess provides great-circle distance in kilometers and a compass bearing arrow pointing toward the secret target country.'}
                  </p>
                </div>
                <div className="pt-2 border-t border-app-border/25 text-[11px] font-mono text-app-text-muted">
                  {'Great-circle guidance'}
                </div>
              </div>

              <div className="rounded-sm border border-indigo-300 bg-indigo-50 p-5 space-y-2 flex flex-col justify-between">
                <div>
                  <div className="font-mono text-xs font-semibold text-app-text flex items-center gap-2">
                    <span>4. {'Shared Flag Symbols'}</span>
                  </div>
                  <p className="mt-2 text-xs sm:text-sm text-app-text-secondary leading-relaxed">
                    {'If your guessed flag shares national symbols with the target (e.g. stars, stripes, sun, eagle), they appear in your guess trail as clues!'}
                  </p>
                </div>
                <div className="pt-2 border-t border-app-border/25 text-[11px] font-mono text-app-text-muted">
                  {'Symbol overlap clues'}
                </div>
              </div>
            </div>

            <div className="border-t border-app-border/25 pt-4 flex flex-col sm:flex-row items-center justify-between gap-4">
              <p className="text-xs text-app-text-muted font-mono text-center sm:text-left">
                {'Daily puzzle rotates at 00:00 UTC. Challenge mode lets you play unlimited rounds.'}
              </p>
              <button
                type="button"
                onClick={handleCloseInstructions}
                className="w-full sm:w-auto inline-flex items-center justify-center gap-2 rounded-sm bg-app-accent hover:bg-app-accent-hover px-6 py-3 text-sm font-semibold text-white transition-colors shadow-sm cursor-pointer"
              >
                <span>{"Got it, let's play"}</span>
                <ArrowRight size={16} />
              </button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
