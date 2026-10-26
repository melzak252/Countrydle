import React, { useEffect, useMemo, useRef, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
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
  Palette,
  Lock,
  RefreshCw,
  Loader2,
} from 'lucide-react';
import GrayscaleFlagCanvas from '../components/GrayscaleFlagCanvas';
import CountdownTimer from '../components/CountdownTimer';
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
  const { i18n } = useTranslation();
  const isPl = i18n?.language?.startsWith('pl');

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
        toast.error(isPl ? 'Nie udało się załadować wyzwania flagi.' : 'Failed to load flag challenge.');
      } finally {
        setIsLoading(false);
      }
    },
    [isPl, persistDailyState]
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
      toast.error(isPl ? 'Ten kraj został już wytypowany!' : 'You already guessed this country!');
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
        isPl
          ? 'Wybierz prawidłowy kraj z listy podpowiedzi.'
          : 'Please select a valid sovereign country from the list.'
      );
      return;
    }

    if (guesses.some((g) => g.country_id === countryId)) {
      toast.error(isPl ? 'Ten kraj został już wytypowany!' : 'You already guessed this country!');
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
      toast.error(isPl ? 'Błąd podczas wysyłania odpowiedzi.' : 'Error submitting your guess.');
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
      isPl
        ? 'Odkryto 1 kolor na fladze (≥10% powierzchni)!'
        : '1 color hint revealed on the flag (≥10% of flag)!'
    );
  };

  const maxGuesses = challenge?.max_guesses || 8;
  const hintUnlockThreshold = challenge?.hint_unlock_guesses || 3;
  const canUnlockHint = !colorHintUsed && !isGameOver && guesses.length >= hintUnlockThreshold;
  const hintLocked = !colorHintUsed && !isGameOver && guesses.length < hintUnlockThreshold;

  const handleShare = () => {
    if (!challenge) return;
    const scoreText = won ? `${guesses.length}/${maxGuesses}` : `X/${maxGuesses}`;
    const hintBadge = colorHintUsed
      ? (isPl ? '🎨 Użyto podpowiedzi koloru' : '🎨 Color Hint used')
      : (isPl ? '🖤 Czyste odgadnięcie w szarości' : '🖤 Pure Grayscale solve');
    const headerTitle =
      mode === 'daily'
        ? (isPl ? `Odcienie Flagi · ${challenge.date}` : `Flag Shades · ${challenge.date}`)
        : (isPl ? 'Odcienie Flagi · Wyzwanie' : 'Flag Shades · Challenge');

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
        const dist = g.distance_km !== null && g.distance_km !== undefined ? `${g.distance_km.toLocaleString()} km` : '';
        const sym = g.matched_symbols && g.matched_symbols.length > 0 ? ` ✦${g.matched_symbols.length}` : '';
        lines.push(`${tile} ${arrow}${dist}${sym}`.trim());
      }
    });

    lines.push('');
    lines.push(
      typeof window !== 'undefined'
        ? `${window.location.origin}/flag-shades`
        : 'https://countrydle.com/flag-shades'
    );

    const fullShareText = lines.join('\n');
    if (navigator.clipboard) {
      navigator.clipboard.writeText(fullShareText);
      setCopied(true);
      toast.success(isPl ? 'Skopiowano wynik do schowka!' : 'Copied results to clipboard!');
      setTimeout(() => setCopied(false), 2500);
    }
  };

  const sortedGuesses = useMemo(() => [...guesses].reverse(), [guesses]);

  if (isLoading && !challenge) {
    return (
      <div role="status" className="flex h-[60vh] items-center justify-center gap-3 text-emerald-400">
        <Loader2 className="animate-spin" size={24} aria-hidden="true" />
        <span className="text-sm font-medium text-sand-300">
          {isPl ? 'Ładowanie Odcieni Flagi...' : 'Loading Flag Shades...'}
        </span>
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-4xl px-3 py-2 sm:px-6 sm:py-4">
      {/* Header Bar */}
      <header className="mb-3 border-b border-sand-800/80 pb-3 sm:mb-6 sm:pb-4 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="mb-1 flex items-center gap-2 text-xs font-mono font-semibold uppercase tracking-wider text-sand-400">
              <span className="flex items-center gap-1.5">
                <Palette size={14} className="text-emerald-400" />
                {isPl ? 'Tryb Szarości' : 'Grayscale Deduction'}
              </span>
              <span>•</span>
              <span>{mode === 'daily' ? challenge?.date || 'Daily' : isPl ? 'Wyzwanie' : 'Challenge'}</span>
            </div>
            <h1 className="text-xl font-bold tracking-tight text-sand-100 sm:text-3xl">
              {isPl ? 'Odcienie Flagi' : 'Flag Shades'}
            </h1>
            <p className="mt-0.5 text-xs text-sand-400 sm:text-sm">
              {isPl
                ? 'Rozpoznaj flagę państwową wyświetlaną wyłącznie w odcieniach szarości.'
                : 'Identify the national flag rendered entirely in shades of grey.'}
            </p>
          </div>

          <div className="flex items-center gap-2 sm:gap-3">
            {/* Guesses Remaining Pill */}
            <div className="flex items-center rounded-sm border border-white/10 bg-obsidian-900 px-2.5 py-1.5 shadow-sm sm:px-3.5 sm:py-2">
              <span className="mr-2 font-mono text-xs uppercase tracking-wider text-zinc-400">
                {isPl ? 'Próby:' : 'Guesses:'}
              </span>
              <span
                className={`font-mono text-base font-bold ${
                  guesses.length >= maxGuesses - 2 ? 'text-amber-400' : 'text-emerald-400'
                }`}
              >
                {guesses.length}
              </span>
              <span className="font-mono text-xs text-zinc-500"> / {maxGuesses}</span>
            </div>

            {/* Help Modal Button */}
            <button
              type="button"
              onClick={() => setShowInstructions(true)}
              className="flex h-10 w-10 sm:h-9 sm:w-9 items-center justify-center rounded-sm border border-sand-800 bg-sand-900 text-sand-400 hover:border-sand-700 hover:text-sand-200 transition-colors"
              title={isPl ? 'Zasady gry Odcienie Flagi' : 'How to play Flag Shades'}
              aria-label={isPl ? 'Zasady gry' : 'Instructions'}
            >
              <HelpCircle size={18} />
            </button>

            {/* Results Button when Game is Over */}
            {isGameOver && (
              <button
                type="button"
                onClick={() => setShowResultsModal(true)}
                className="flex h-10 sm:h-9 items-center gap-1.5 px-3 rounded-sm border border-emerald-500/40 bg-emerald-950/40 text-emerald-300 hover:bg-emerald-900/50 transition-colors text-xs font-semibold cursor-pointer"
                title={isPl ? 'Pokaż wynik' : 'Show results'}
              >
                <Trophy size={15} />
                <span>{isPl ? 'Wyniki' : 'Results'}</span>
              </button>
            )}
          </div>
        </div>

        {/* Mode Switcher Bar */}
        <div className="flex flex-wrap items-center justify-between gap-2 pt-1 border-t border-white/5">
          <div className="inline-flex rounded-sm border border-white/10 bg-obsidian-950 p-1 text-xs font-medium">
            <button
              type="button"
              onClick={() => handleSwitchMode('daily')}
              className={`px-3 py-1.5 rounded-xs transition-colors cursor-pointer ${
                mode === 'daily'
                  ? 'bg-emerald-500/20 text-emerald-300 font-semibold shadow-xs'
                  : 'text-zinc-400 hover:text-sand-200'
              }`}
            >
              📅 {isPl ? 'Dzisiejsza zagadka' : 'Daily Puzzle'}
            </button>
            <button
              type="button"
              onClick={() => handleSwitchMode('challenge')}
              className={`px-3 py-1.5 rounded-xs transition-colors cursor-pointer ${
                mode === 'challenge'
                  ? 'bg-emerald-500/20 text-emerald-300 font-semibold shadow-xs'
                  : 'text-zinc-400 hover:text-sand-200'
              }`}
            >
              ⚡ {isPl ? 'Wyzwanie losowe' : 'Challenge Mode'}
            </button>
          </div>

          {mode === 'challenge' && (
            <button
              type="button"
              onClick={() => loadChallenge('challenge', `challenge-${Date.now()}`)}
              disabled={isLoading}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-sm border border-sand-700 bg-sand-900/60 text-sand-200 hover:bg-sand-800 text-xs font-medium transition-colors cursor-pointer disabled:opacity-50"
            >
              <RefreshCw size={13} className={isLoading ? 'animate-spin' : ''} />
              <span>{isPl ? 'Nowa flaga' : 'New Challenge'}</span>
            </button>
          )}
        </div>
      </header>

      {/* Main Content Area */}
      <main className="space-y-4 sm:space-y-6">
        {/* 1. Grayscale Flag Canvas Container */}
        <section aria-label={isPl ? 'Wizualizacja flagi w skali szarości' : 'Grayscale Flag Display'}>
          <GrayscaleFlagCanvas
            flagUrl={resolvedFlagUrl}
            revealColorHint={colorHintUsed}
            isGameOver={isGameOver}
            countryName={targetCountry?.name}
            onHintInfoChange={setHintInfo}
          />
        </section>

        {/* 2. Color Hint Control Bar */}
        <section aria-label={isPl ? 'Podpowiedź koloru' : 'Color Hint Control'} className="mx-auto w-full max-w-xl">
          {hintLocked && (
            <button
              type="button"
              disabled
              className="flex w-full items-center justify-between rounded-sm border border-white/10 bg-obsidian-900/70 px-4 py-2.5 text-xs text-zinc-400 cursor-not-allowed opacity-75"
            >
              <div className="flex items-center gap-2">
                <Lock size={15} className="text-zinc-500 shrink-0" />
                <span>
                  {isPl
                    ? `Podpowiedź koloru po 3 próbach (${guesses.length}/${hintUnlockThreshold})`
                    : `Color Hint unlocks after 3 guesses (${guesses.length}/${hintUnlockThreshold})`}
                </span>
              </div>
              <span className="font-mono text-[11px] text-zinc-500">
                {hintUnlockThreshold - guesses.length} {isPl ? 'pozostało' : 'left'}
              </span>
            </button>
          )}

          {canUnlockHint && (
            <button
              type="button"
              onClick={handleRevealColorHint}
              className="group relative flex w-full items-center justify-center gap-2.5 rounded-sm border border-amber-500/50 bg-gradient-to-r from-amber-500/20 via-yellow-500/20 to-amber-500/20 px-4 py-3 text-xs sm:text-sm font-bold text-amber-200 shadow-[0_0_15px_rgba(245,158,11,0.25)] hover:border-amber-400 hover:shadow-[0_0_20px_rgba(245,158,11,0.4)] transition-all cursor-pointer animate-pulse"
            >
              <Palette size={18} className="text-amber-300 transition-transform group-hover:scale-110" />
              <span>
                {isPl
                  ? 'Odkryj 1 kolor na fladze (≥10% powierzchni)'
                  : 'Reveal 1 Color Hint (≥10% of flag)'}
              </span>
              <Sparkles size={16} className="text-yellow-300" />
            </button>
          )}

          {!isGameOver && colorHintUsed && (
            <div className="flex items-center justify-between rounded-sm border border-emerald-500/40 bg-emerald-950/40 px-4 py-2.5 text-xs text-emerald-300 font-medium">
              <div className="flex items-center gap-2">
                <Palette size={15} className="text-emerald-400 shrink-0" />
                <span>
                  {isPl
                    ? `Podpowiedź koloru aktywna: ${hintInfo?.colorName ? `przywrócono ${hintInfo.colorName}` : 'przywrócono 1 kolor'} (${hintInfo?.sharePct || '≥10'}% flagi)`
                    : `Color Hint Active: ${hintInfo?.colorName || '1 color'} restored (${hintInfo?.sharePct || '≥10'}% of flag)`}
                </span>
              </div>
              <span className="rounded-full bg-emerald-500/20 px-2 py-0.5 font-mono text-[10px] uppercase font-bold text-emerald-300">
                {isPl ? 'Aktywna' : 'Active'}
              </span>
            </div>
          )}
        </section>

        {/* 3. Autocomplete Guess Input */}
        {!isGameOver && (
          <section aria-label={isPl ? 'Wpisywanie odpowiedzi' : 'Guess Input'} className="mx-auto w-full max-w-xl">
            <div className="relative">
              <div className="flex items-center gap-2">
                <div className="relative flex-1">
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
                      isPl
                        ? 'Wyszukaj flagę państwa po nazwie...'
                        : 'Search national flag by country name...'
                    }
                    disabled={isSubmitting || isLoading}
                    className="w-full min-w-0 rounded-sm border border-white/15 bg-obsidian-950 px-3 py-2.5 text-base md:text-sm text-sand-100 placeholder:text-zinc-500 shadow-inner focus:border-emerald-500/70 focus:outline-none focus:ring-1 focus:ring-emerald-500/30 disabled:opacity-50 sm:px-4 sm:py-3"
                  />

                  {/* Autocomplete Dropdown */}
                  {showSuggestions && filteredCountries.length > 0 && (
                    <div
                      ref={dropdownRef}
                      className="absolute left-0 right-0 z-50 mt-1 max-h-60 overflow-y-auto rounded-sm border border-white/15 bg-obsidian-900 shadow-2xl"
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
                              ? 'bg-emerald-500/20 text-emerald-200'
                              : 'text-sand-100 hover:bg-white/5'
                          }`}
                        >
                          <span className="font-medium">{c.name}</span>
                          {c.official_name && c.official_name !== c.name && (
                            <span className="text-xs text-zinc-400 truncate max-w-[200px] ml-2">
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
                  className="inline-flex min-h-[44px] items-center justify-center gap-1.5 rounded-sm bg-emerald-400 hover:bg-emerald-300 px-4 py-2 text-sm font-semibold text-obsidian-950 transition-colors shadow-sm disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
                >
                  {isSubmitting ? (
                    <Loader2 size={16} className="animate-spin" />
                  ) : (
                    <>
                      <span>{isPl ? 'Zgadnij' : 'Guess'}</span>
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
          <section aria-label={isPl ? 'Historia prób' : 'Guess History'} className="mx-auto w-full max-w-xl space-y-2">
            <div className="flex items-center justify-between px-1">
              <span className="text-xs font-mono uppercase tracking-wider text-zinc-400">
                {isPl ? 'Twoje próby' : 'Your Guesses'}
              </span>
              <span className="text-xs font-mono text-zinc-500">
                {guesses.length} / {maxGuesses}
              </span>
            </div>

            <ul className="space-y-2">
              {sortedGuesses.map((g, idx) => (
                <li
                  key={idx}
                  className={`rounded-sm border-l-2 bg-obsidian-950 p-3 sm:px-4 sm:py-3 transition-colors ${
                    g.answer ? 'border-emerald-400 shadow-sm' : 'border-rose-500/60'
                  }`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-3 min-w-0">
                      {g.answer ? (
                        <Check size={18} className="shrink-0 text-emerald-400" aria-hidden="true" />
                      ) : (
                        <X size={18} className="shrink-0 text-rose-400" aria-hidden="true" />
                      )}
                      <span className="truncate text-sm font-semibold text-sand-100">{g.guess}</span>
                    </div>

                    {/* Distance & Bearing Arrow */}
                    {g.distance_km !== null && g.distance_km !== undefined && !g.answer && (
                      <div className="flex items-center gap-2 font-mono text-xs text-zinc-300">
                        <span className="rounded border border-white/10 bg-white/5 px-2 py-0.5">
                          {g.distance_km.toLocaleString()} km
                        </span>
                        {g.bearing_arrow && (
                          <span className="text-emerald-400 text-sm font-bold" title={g.bearing_direction || ''}>
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
                            className="inline-flex items-center gap-1 rounded-full border border-indigo-500/40 bg-indigo-500/15 px-2 py-0.5 text-[11px] font-mono text-indigo-300"
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
                            className="inline-flex items-center rounded border border-emerald-500/40 bg-emerald-500/10 px-1.5 py-0.5 text-[10px] font-mono text-emerald-300"
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
            aria-label={isPl ? 'Podsumowanie wyniku' : 'Game Result Summary'}
            className="mx-auto w-full max-w-xl rounded-sm border border-emerald-500/30 bg-obsidian-950 p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4"
          >
            <div>
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs uppercase tracking-wider text-emerald-400 font-semibold">
                  {won ? (isPl ? 'Flaga Odgadnięta!' : 'Flag Identified!') : (isPl ? 'Koniec Gry' : 'Game Over')}
                </span>
                <span className="text-zinc-600">·</span>
                <span className="text-xs font-mono text-zinc-400">
                  {colorHintUsed
                    ? isPl
                      ? '🎨 Użyto podpowiedzi koloru'
                      : '🎨 Color Hint used'
                    : isPl
                    ? '🖤 Czyste odgadnięcie w szarości'
                    : '🖤 Pure Grayscale solve'}
                </span>
              </div>
              <h3 className="text-lg sm:text-xl font-bold text-sand-100 mt-1">
                {targetCountry?.name || (won && guesses[guesses.length - 1]?.guess) || (isPl ? 'Tajemniczy Kraj' : 'Mystery Country')}
              </h3>
              <p className="text-xs text-zinc-400 mt-0.5">
                {won
                  ? isPl
                    ? `Zgadnięto w ${guesses.length} z ${maxGuesses} prób.`
                    : `Solved in ${guesses.length} of ${maxGuesses} guesses.`
                  : isPl
                  ? 'Wykorzystano wszystkie próby. Sprawdź pełną flagę!'
                  : 'All guesses used. Check out the revealed flag!'}
              </p>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setShowResultsModal(true)}
                className="inline-flex min-h-10 items-center gap-2 rounded-sm bg-emerald-400 hover:bg-emerald-300 px-4 py-2 text-xs sm:text-sm font-semibold text-obsidian-950 transition-colors cursor-pointer"
              >
                <Trophy size={16} aria-hidden="true" />
                <span>{isPl ? 'Szczegóły' : 'View Results'}</span>
              </button>

              <button
                type="button"
                onClick={handleShare}
                className="inline-flex min-h-10 items-center gap-1.5 rounded-sm border border-white/20 bg-white/5 hover:bg-white/10 px-3 py-2 text-xs sm:text-sm font-semibold text-sand-100 transition-colors cursor-pointer"
                title={isPl ? 'Udostępnij' : 'Share'}
              >
                {copied ? <Check size={16} className="text-emerald-400" /> : <Share2 size={16} />}
              </button>
            </div>
          </section>
        )}

        {/* 6. Results Modal */}
        {isGameOver && showResultsModal && (
          <div className="fixed inset-0 z-[2000] flex max-h-[var(--app-height,100dvh)] items-center justify-center p-2 pb-[calc(env(safe-area-inset-bottom)+0.5rem)] sm:px-4 sm:pt-4 sm:pb-[calc(env(safe-area-inset-bottom)+1rem)] overflow-y-auto md:z-50 md:max-h-none">
            {/* Backdrop */}
            <div
              className="fixed inset-0 bg-black/80 backdrop-blur-sm transition-opacity cursor-pointer"
              onClick={() => setShowResultsModal(false)}
              aria-hidden="true"
            />

            {/* Modal Dialog Card */}
            <section
              role="dialog"
              aria-modal="true"
              aria-label={isPl ? 'Wynik gry' : 'Game Result'}
              className="relative z-10 mx-auto w-full max-w-2xl sm:max-w-3xl max-h-full overflow-y-auto rounded-sm border border-white/15 bg-obsidian-950 p-4 sm:p-8 shadow-2xl text-left space-y-4 sm:space-y-6 my-auto"
              onClick={(e) => e.stopPropagation()}
            >
              {/* Header Bar */}
              <div className="flex items-center justify-between border-b border-white/10 pb-3 text-left">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs uppercase tracking-wider text-emerald-400 font-semibold">
                    {isPl ? 'Wynik Odcieni Flagi' : 'Flag Shades Result'}
                  </span>
                  <span className="text-zinc-600">·</span>
                  <span className="font-mono text-xs text-zinc-400">
                    {mode === 'daily' ? challenge?.date || 'Daily' : isPl ? 'Wyzwanie' : 'Challenge'}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => setShowResultsModal(false)}
                  className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-white/5 text-zinc-400 hover:bg-white/15 hover:text-white transition-colors cursor-pointer"
                  aria-label={isPl ? 'Zamknij' : 'Close'}
                >
                  <X size={16} />
                </button>
              </div>

              {/* Revealed Country Card */}
              <div className="rounded-sm border border-white/10 bg-obsidian-900/70 p-4 sm:p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div className="flex items-center gap-4 min-w-0">
                  <div className="shrink-0 overflow-hidden rounded-sm border border-white/15 bg-obsidian-950 p-1 shadow-md">
                    {resolvedFlagUrl ? (
                      <img
                        src={resolvedFlagUrl}
                        alt={targetCountry?.name || 'Country Flag'}
                        className="h-16 w-24 sm:h-20 sm:w-30 object-contain"
                      />
                    ) : null}
                  </div>
                  <div className="min-w-0">
                    <span className="font-mono text-[10px] sm:text-xs uppercase tracking-widest text-emerald-400 font-semibold">
                      {isPl ? 'Prawidłowa flaga państwowa' : 'Secret National Flag'}
                    </span>
                    <h2 className="mt-0.5 break-words font-serif text-2xl sm:text-3xl text-sand-100">
                      {targetCountry?.name || (won && guesses[guesses.length - 1]?.guess) || (isPl ? 'Tajemniczy Kraj' : 'Mystery Country')}
                    </h2>
                    <p className="mt-1 text-xs text-zinc-400">
                      {won
                        ? isPl
                          ? `Rozpoznano w ${guesses.length} z ${maxGuesses} prób.`
                          : `Identified in ${guesses.length} of ${maxGuesses} guesses.`
                        : isPl
                        ? `Wykorzystano wszystkie ${maxGuesses} prób.`
                        : `Used all ${maxGuesses} guesses.`}
                    </p>
                  </div>
                </div>

                <div className="flex sm:flex-col items-center sm:items-end justify-between gap-2 shrink-0 border-t sm:border-t-0 border-white/10 pt-3 sm:pt-0">
                  <div
                    className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold font-mono ${
                      won
                        ? 'bg-emerald-500/15 border border-emerald-500/30 text-emerald-300'
                        : 'bg-rose-500/15 border border-rose-500/30 text-rose-300'
                    }`}
                  >
                    {won ? <Sparkles size={14} /> : <AlertCircle size={14} />}
                    <span>{won ? (isPl ? 'Odgadnięte' : 'Solved') : (isPl ? 'Nieodgadnięte' : 'Game Over')}</span>
                  </div>

                  <span className="text-xs font-mono text-zinc-400">
                    {colorHintUsed
                      ? isPl
                        ? '🎨 Użyto podpowiedzi koloru'
                        : '🎨 Color Hint used'
                      : isPl
                      ? '🖤 Czyste odgadnięcie w szarości'
                      : '🖤 Pure Grayscale solve'}
                  </span>
                </div>
              </div>

              {/* Performance Metrics */}
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 sm:gap-4">
                <div className="rounded-sm border border-white/10 bg-obsidian-900/40 p-4">
                  <span className="text-[11px] uppercase font-mono tracking-wider text-zinc-400 block">
                    {isPl ? 'Wykorzystane próby' : 'Guesses Used'}
                  </span>
                  <div className="mt-1 flex items-baseline gap-1.5">
                    <span className="font-mono text-2xl font-bold text-sand-100">{guesses.length}</span>
                    <span className="text-xs text-zinc-500 font-mono">/ {maxGuesses}</span>
                  </div>
                </div>

                <div className="rounded-sm border border-white/10 bg-obsidian-900/40 p-4">
                  <span className="text-[11px] uppercase font-mono tracking-wider text-zinc-400 block">
                    {isPl ? 'Tryb Rozwiązania' : 'Solve Mode'}
                  </span>
                  <div className="mt-1 font-mono text-sm font-semibold text-emerald-300 flex items-center gap-1.5">
                    {colorHintUsed ? (
                      <>
                        <Palette size={15} />
                        <span>{isPl ? 'Z podpowiedzią' : 'With Hint'}</span>
                      </>
                    ) : (
                      <>
                        <span>🖤</span>
                        <span>{isPl ? 'Czyste szarości' : 'Pure Grayscale'}</span>
                      </>
                    )}
                  </div>
                </div>

                <div className="col-span-2 sm:col-span-1 rounded-sm border border-white/10 bg-obsidian-900/40 p-4 flex flex-col justify-between">
                  <span className="text-[11px] uppercase font-mono tracking-wider text-zinc-400 block">
                    {isPl ? 'Następna zagadka' : 'Next Daily'}
                  </span>
                  <div className="mt-1 font-mono text-lg font-semibold text-emerald-400">
                    <CountdownTimer variant="minimal" className="text-lg text-emerald-400 font-semibold" />
                  </div>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="space-y-3 pt-2">
                <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
                  <button
                    type="button"
                    onClick={handleShare}
                    className="flex-1 flex min-h-12 items-center justify-center gap-2.5 rounded-sm bg-emerald-400 hover:bg-emerald-300 px-5 py-3 text-sm font-bold text-obsidian-950 transition-colors shadow-md cursor-pointer"
                  >
                    {copied ? <Check size={16} aria-hidden="true" /> : <Share2 size={16} aria-hidden="true" />}
                    <span>{copied ? (isPl ? 'Skopiowano do schowka!' : 'Copied to Clipboard!') : (isPl ? 'Udostępnij wynik' : 'Share Results')}</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      setShowResultsModal(false);
                      setMode('challenge');
                      loadChallenge('challenge', `challenge-${Date.now()}`);
                    }}
                    className="flex min-h-12 items-center justify-center gap-2 rounded-sm border border-amber-400/30 bg-amber-400/10 px-4 py-3 text-xs sm:text-sm font-semibold text-amber-300 hover:bg-amber-400/20 transition-colors cursor-pointer"
                  >
                    <span>⚡ {isPl ? 'Zagraj w wyzwanie' : 'Play Challenge Round'}</span>
                    <ArrowRight size={15} />
                  </button>
                </div>

                <button
                  type="button"
                  onClick={() => setShowResultsModal(false)}
                  className="w-full min-h-11 rounded-sm border border-white/20 py-2.5 text-xs font-semibold text-sand-100 hover:bg-white/10 transition-colors cursor-pointer"
                >
                  {isPl ? 'Zamknij i zobacz flagę' : 'Close & View Flag'}
                </button>
              </div>
            </section>
          </div>
        )}
      </main>

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
            aria-label={isPl ? 'Zasady gry Odcienie Flagi' : 'How to Play Flag Shades'}
            className="relative z-10 w-full max-w-3xl max-h-full overflow-y-auto rounded-sm border border-white/15 bg-obsidian-950 p-4 md:max-h-[92vh] sm:p-8 shadow-2xl space-y-4 sm:space-y-6 my-auto text-sand-100"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between border-b border-white/10 pb-4 text-left gap-4">
              <div>
                <h2 className="text-2xl sm:text-3xl font-serif font-bold tracking-tight text-sand-100 flex items-center gap-2.5">
                  <Palette className="text-emerald-400" size={26} />
                  <span>{isPl ? 'Jak grać w Odcienie Flagi' : 'How to Play Flag Shades'}</span>
                </h2>
                <p className="mt-1.5 text-sm text-zinc-400 leading-relaxed max-w-xl">
                  {isPl
                    ? 'Odgadnij tajemniczą flagę państwową w 8 próbach lub mniej. Cała flaga wyświetla się w odcieniach szarości.'
                    : 'Deduce the secret national flag in 8 guesses or fewer. The full flag is shown in shades of grey.'}
                </p>
              </div>
              <button
                type="button"
                onClick={handleCloseInstructions}
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-sm bg-white/5 text-zinc-400 hover:bg-white/15 hover:text-white transition-colors cursor-pointer"
                aria-label={isPl ? 'Zamknij' : 'Close'}
              >
                <X size={16} />
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="rounded-sm border border-emerald-500/30 bg-obsidian-900/80 p-5 space-y-2 flex flex-col justify-between">
                <div>
                  <div className="font-mono text-xs font-bold uppercase tracking-wider text-emerald-400 flex items-center gap-2">
                    <span>🖤 1. {isPl ? 'Skala jasności szarości' : 'Luminance Grayscale'}</span>
                  </div>
                  <p className="mt-2 text-xs sm:text-sm text-zinc-300 leading-relaxed">
                    {isPl
                      ? 'Wszystkie barwy flagi zostają przekonwertowane na odcienie szarości na podstawie ich percepcyjnej jasności. Żółty jest jasny, granat ciemny, a biel i czerń pozostają sobą.'
                      : 'All flag colors are transformed into perceptual luminance grayscale. Yellow renders light grey, navy renders dark grey, and white/black stay true.'}
                  </p>
                </div>
                <div className="pt-2 border-t border-white/5 text-[11px] font-mono text-zinc-500">
                  {isPl ? 'Pełna flaga od startu' : 'Full flag visible from start'}
                </div>
              </div>

              <div className="rounded-sm border border-amber-500/30 bg-obsidian-900/80 p-5 space-y-2 flex flex-col justify-between">
                <div>
                  <div className="font-mono text-xs font-bold uppercase tracking-wider text-amber-400 flex items-center gap-2">
                    <span>🎨 2. {isPl ? 'Podpowiedź koloru po 3 próbach' : 'Color Hint after 3 Guesses'}</span>
                  </div>
                  <p className="mt-2 text-xs sm:text-sm text-zinc-300 leading-relaxed">
                    {isPl
                      ? 'Po 3 nieudanych próbach odblokowuje się przycisk podpowiedzi, który przywraca dokładnie 1 główny kolor chromatyczny (pokrywający ≥10% powierzchni flagi).'
                      : 'After 3 guesses, unlock a color hint button that restores exactly 1 major chromatic color family (covering ≥10% of the flag image).'}
                  </p>
                </div>
                <div className="pt-2 border-t border-white/5 text-[11px] font-mono text-zinc-500">
                  {isPl ? 'Opcjonalna pomoc po 3 próbach' : 'Optional hint after 3 attempts'}
                </div>
              </div>

              <div className="rounded-sm border border-cyan-500/30 bg-obsidian-900/80 p-5 space-y-2 flex flex-col justify-between">
                <div>
                  <div className="font-mono text-xs font-bold uppercase tracking-wider text-cyan-400 flex items-center gap-2">
                    <span>🧭 3. {isPl ? 'Odległość i kierunek geograficzny' : 'Distance & Compass Bearing'}</span>
                  </div>
                  <p className="mt-2 text-xs sm:text-sm text-zinc-300 leading-relaxed">
                    {isPl
                      ? 'Każda nietrafiona próba podaje odległość w kilometrach oraz strzałkę kierunkową wskazującą położenie poszukiwanego państwa na kuli ziemskiej.'
                      : 'Each missed guess provides great-circle distance in kilometers and a compass bearing arrow pointing toward the secret target country.'}
                  </p>
                </div>
                <div className="pt-2 border-t border-white/5 text-[11px] font-mono text-zinc-500">
                  {isPl ? 'Geograficzne wskazówki' : 'Great-circle guidance'}
                </div>
              </div>

              <div className="rounded-sm border border-indigo-500/30 bg-obsidian-900/80 p-5 space-y-2 flex flex-col justify-between">
                <div>
                  <div className="font-mono text-xs font-bold uppercase tracking-wider text-indigo-400 flex items-center gap-2">
                    <span>✦ 4. {isPl ? 'Wspólne symbole na flagach' : 'Shared Flag Symbols'}</span>
                  </div>
                  <p className="mt-2 text-xs sm:text-sm text-zinc-300 leading-relaxed">
                    {isPl
                      ? 'Jeśli Twoja wytypowana flaga dzieli z celem symbole (np. gwiazdy, pasy, słońce, orła), pojawią się one w historii prób jako wskazówki!'
                      : 'If your guessed flag shares national symbols with the target (e.g. stars, stripes, sun, eagle), they appear in your guess trail as clues!'}
                  </p>
                </div>
                <div className="pt-2 border-t border-white/5 text-[11px] font-mono text-zinc-500">
                  {isPl ? 'Dopasowanie symboli' : 'Symbol overlap clues'}
                </div>
              </div>
            </div>

            <div className="border-t border-white/10 pt-4 flex flex-col sm:flex-row items-center justify-between gap-4">
              <p className="text-xs text-zinc-500 font-mono text-center sm:text-left">
                {isPl
                  ? 'Zagadka codzienna zmienia się o 00:00 UTC. Tryb wyzwania pozwala grać bez limitu.'
                  : 'Daily puzzle rotates at 00:00 UTC. Challenge mode lets you play unlimited rounds.'}
              </p>
              <button
                type="button"
                onClick={handleCloseInstructions}
                className="w-full sm:w-auto inline-flex items-center justify-center gap-2 rounded-sm bg-emerald-400 hover:bg-emerald-300 px-6 py-3 text-sm font-semibold text-obsidian-950 transition-colors shadow-lg cursor-pointer"
              >
                <span>{isPl ? 'Rozumiem, gramy!' : "Got it, let's play!"}</span>
                <ArrowRight size={16} />
              </button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
