import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useFlagdleGameStore } from '../stores/gameStore';
import { FlagTiles } from '../components/FlagTiles';
import CountdownTimer from '../components/CountdownTimer';
import { Loader2, HelpCircle, Share2, Check, X, Sparkles, AlertCircle, Trophy, ArrowRight, Flag } from 'lucide-react';
import { Link } from 'react-router-dom';
import toast from 'react-hot-toast';
import type { FlagdleCountry, FlagdleGuess } from '../types';


export default function FlagdlePage() {
  const {
    gameState,
    guesses,
    stage,
    flagAssetUrl,
    correctCountry,
    countries,
    dailyDate,
    isLoading,
    isGuest,
    fetchGameState,
    fetchCountries,
    makeGuess,
    syncGuestData,
  } = useFlagdleGameStore();

  const [inputVal, setInputVal] = useState('');
  const [selectedCountry, setSelectedCountry] = useState<FlagdleCountry | null>(null);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(0);
  const FLAGDLE_GUIDE_KEY = 'flagdle_guide_seen';
  const [showInstructions, setShowInstructions] = useState(() => {
    try {
      return localStorage.getItem(FLAGDLE_GUIDE_KEY) !== 'true';
    } catch {
      return false;
    }
  });
  const handleCloseInstructions = () => {
    setShowInstructions(false);
    try {
      localStorage.setItem(FLAGDLE_GUIDE_KEY, 'true');
    } catch {
      // ignore
    }
  };
  const [copied, setCopied] = useState(false);
  const [showResultsModal, setShowResultsModal] = useState(true);
  const inputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const resolvedFlagUrl = useMemo(() => {
    if (!flagAssetUrl) return null;
    if (flagAssetUrl.startsWith('http://') || flagAssetUrl.startsWith('https://')) {
      return flagAssetUrl;
    }
    const cleanPath = flagAssetUrl.startsWith('/') ? flagAssetUrl : `/${flagAssetUrl}`;
    if (!cleanPath.startsWith('/api')) {
      return `/api${cleanPath}`;
    }
    return cleanPath;
  }, [flagAssetUrl]);


  useEffect(() => {
    fetchGameState();
    fetchCountries();
    const handleLogin = () => {
      syncGuestData();
    };
    window.addEventListener('auth-login', handleLogin);
    return () => window.removeEventListener('auth-login', handleLogin);
  }, [fetchGameState, fetchCountries, syncGuestData]);

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

  // Filter countries for autocomplete (excluding already guessed countries)
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
    if (!countries.some(available => available.id === country.id)) return;
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

    if (!countryId || !countries.some(country => country.id === countryId)) {
      toast.error('Please select a valid sovereign country from the list.');
      return;
    }

    if (guesses.some((g) => g.country_id === countryId)) {
      toast.error('You already guessed this country!');
      return;
    }

    await makeGuess(name, countryId);
    setInputVal('');
    setSelectedCountry(null);
    setShowSuggestions(false);
  };

  const handleShare = () => {
    if (!dailyDate || !gameState) return;
    const isWon = gameState.won;
    const scoreText = isWon ? `${guesses.length}/12` : 'X/12';
    const lines: string[] = [];
    lines.push(`Flagdle · ${dailyDate}`);
    lines.push(`${scoreText} guesses 🚩`);

    if (isWon && gameState.points && gameState.points > 0) {
      lines.push(`Score: ${gameState.points.toLocaleString('en-US')} pts`);
    }

    lines.push('');

    // Concise, authentic attempt trail
    guesses.forEach((g: FlagdleGuess) => {
      if (g.answer) {
        lines.push('🟩 🎯');
      } else {
        const isClose = (g.distance_km !== null && g.distance_km !== undefined && g.distance_km < 2500) || (g.matched_colors && g.matched_colors.length > 0);
        const tile = isClose ? '🟨' : '⬛';
        const arrow = g.bearing_arrow ? `${g.bearing_arrow} ` : '';
        const dist = g.distance_km ? `${g.distance_km.toLocaleString('en-US')} km` : '';
        lines.push(`${tile} ${arrow}${dist}`.trim());
      }
    });

    lines.push('');
    lines.push('https://countrydle.online/flagdle');

    const text = lines.join('\n');

    navigator.clipboard.writeText(text);
    setCopied(true);
    toast.success('Results copied to clipboard!');
    setTimeout(() => setCopied(false), 2500);
  };


  const isGameOver = gameState?.is_game_over || false;
  const isWon = gameState?.won || false;

  useEffect(() => {
    if (isGameOver) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setShowResultsModal(true);
    }
  }, [isGameOver]);

  const sortedGuesses = useMemo(() => [...guesses].reverse(), [guesses]);
  if (!gameState && isLoading) {
    return (
      <div role="status" className="flex h-[60vh] items-center justify-center gap-3 text-app-accent">
        <Loader2 className="animate-spin" size={24} aria-hidden="true" />
        <span className="text-sm font-medium text-app-text-secondary">Loading daily Flagdle...</span>
      </div>
    );
  }
  return (
    <div className="mx-auto w-full max-w-4xl px-3 py-2 sm:px-6 sm:py-4">
      {/* Header Bar */}
      <header className="mb-3 flex flex-wrap items-center justify-between gap-2 border-b border-app-border/20 pb-2 sm:mb-6 sm:gap-3 sm:pb-4">
        <div>
          <div className="mb-1 flex items-center gap-2 text-xs font-mono font-semibold text-app-text-secondary">
            <span>Daily Flag Deduction</span>
            <span>•</span>
            <span>{dailyDate}</span>
          </div>
          <h1 className="text-xl font-bold tracking-tight text-app-text sm:text-3xl">Flagdle</h1>
          {isGuest && <p className="mt-1 text-xs text-app-text-muted">Playing as Guest • No account required</p>}
        </div>

        <div className="flex items-center gap-3">
          {/* Guesses Remaining Pill */}
          <div className="flex items-center rounded-sm border border-app-border/20 bg-app-surface px-2.5 py-1.5 shadow-sm sm:px-3.5 sm:py-2">
            <span className="text-xs text-app-text-secondary mr-2 font-mono">Guesses:</span>
            <span
              className={`font-mono text-base font-bold ${
                guesses.length >= 10 ? 'text-amber-800' : 'text-app-accent'
              }`}
            >
              {guesses.length}
            </span>
            <span className="text-xs text-app-text-muted font-mono"> / 12</span>
          </div>
          {/* Instructions Modal Button */}
          <button
            type="button"
            onClick={() => setShowInstructions(true)}
            className="flex h-11 w-11 items-center justify-center rounded-sm border border-app-border bg-app-surface-muted text-app-text-secondary hover:border-app-border/80 hover:text-app-text transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-app-focus sm:h-9 sm:w-9"
            title="How to play Flagdle"
          >
            <HelpCircle size={18} />
          </button>
          {isGameOver && (
            <button
              type="button"
              onClick={() => setShowResultsModal(true)}
              className="flex h-11 md:h-9 items-center gap-1.5 px-3 rounded-sm border border-app-accent/30 bg-app-accent/10 text-app-accent hover:bg-app-accent/20 transition-colors text-xs font-semibold cursor-pointer"
              title="Show results"
            >
              <Trophy size={15} />
              <span>Results</span>
            </button>
          )}
        </div>
      </header>

      {/* Main Game Container */}
      <main className="space-y-3 sm:space-y-6">
        {/* 1. The 12-Card Progressive Unmasking Canvas (3 rows x 4 columns) */}
        <section aria-label="Flag Visualizer">
          <FlagTiles
            stage={stage}
            isGameOver={isGameOver}
            flagUrl={resolvedFlagUrl}
            countryName={correctCountry?.name}
          />
        </section>
        {/* 2. Autocomplete Search Input (active when game not over) */}
        {!isGameOver && (
          <section aria-label="Guess Input" className="mx-auto w-full max-w-xl">
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
                    placeholder="Search national flag by country name..."
                    disabled={isLoading || isGameOver}
                    className="w-full min-w-0 rounded-sm border border-app-border/30 bg-app-surface-raised px-3 py-2.5 text-base md:text-sm text-app-text placeholder:text-app-text-muted focus:border-app-focus focus:outline-none focus:ring-1 focus:ring-app-focus/30 disabled:bg-app-surface-muted disabled:text-app-text-muted disabled:opacity-100 sm:px-4 sm:py-3"
                  />

                  {/* Suggestion Dropdown */}
                  {showSuggestions && filteredCountries.length > 0 && (
                    <div
                      ref={dropdownRef}
                      className="absolute left-0 right-0 top-full z-50 mt-1.5 max-h-64 max-md:max-h-[min(35dvh,calc(var(--app-height,100dvh)-8rem))] overflow-y-auto rounded-sm border border-app-border/30 bg-app-surface-raised p-1.5 shadow-sm"
                    >
                      {filteredCountries.map((c, idx) => (
                        <div
                          key={c.id}
                          onClick={() => handleSelectCountry(c)}
                          onMouseEnter={() => setHighlightedIndex(idx)}
                          className={`flex max-md:min-h-11 items-center justify-between gap-2 rounded-sm px-3 py-2 cursor-pointer transition-colors ${
                            idx === highlightedIndex ? 'bg-app-accent/10 text-app-text' : 'text-app-text-secondary hover:bg-app-surface-muted'
                          }`}
                        >
                          <span className="text-sm font-medium">{c.name}</span>
                          {c.official_name && c.official_name !== c.name && (
                            <span className="text-xs text-app-text-muted truncate ml-auto">
                              {c.official_name}
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <button
                  type="button"
                  onClick={handleSubmitGuess}
                  disabled={isLoading || !inputVal.trim()}
                  className="inline-flex min-h-11 shrink-0 items-center justify-center rounded-sm bg-app-accent px-3 py-2.5 text-sm font-semibold text-white shadow-md hover:bg-app-accent-hover active:scale-95 disabled:pointer-events-none disabled:bg-app-surface-muted disabled:text-app-text-muted disabled:opacity-100 transition-colors cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-app-focus sm:px-5 sm:py-3"
                >
                  {isLoading ? <Loader2 size={18} className="animate-spin" /> : 'Guess'}
                </button>
              </div>
            </div>
          </section>
        )}

        {/* Previous Guesses List */}
        {guesses.length > 0 && (
          <section aria-label="Previous Guesses" className="mx-auto w-full max-w-xl space-y-2">
            <div className="flex items-center justify-between px-1">
              <span className="text-xs font-mono text-app-text-secondary">Your Guesses</span>
              <span className="text-xs font-mono text-app-text-muted">{guesses.length} / 12</span>
            </div>
            <ul className="space-y-1.5">
              {sortedGuesses.map((g, idx) => (
                <li
                  key={g.id || idx}
                  className={`flex items-center justify-between rounded-sm border-l-2 bg-app-surface-raised px-3.5 py-2.5 ${
                    g.answer ? 'border-app-accent' : 'border-rose-600/70'
                  }`}
                >
                  <div className="flex items-center gap-3 min-w-0">
                    {g.answer ? (
                      <Check size={16} className="shrink-0 text-app-accent" aria-hidden="true" />
                    ) : (
                      <X size={16} className="shrink-0 text-rose-600" aria-hidden="true" />
                    )}
                    <span className="truncate text-sm font-medium text-app-text">{g.guess}</span>
                  </div>
                  {g.distance_km !== null && g.distance_km !== undefined && !g.answer && (
                    <div className="flex items-center gap-1.5 font-mono text-xs text-app-text-secondary">
                      <span className="rounded border border-app-border/20 bg-app-surface-muted px-2 py-0.5 text-app-text-secondary">
                        {g.distance_km.toLocaleString('en-US')} km
                      </span>
                      {g.bearing_arrow && (
                        <span className="text-app-accent text-sm font-semibold">{g.bearing_arrow}</span>
                      )}
                    </div>
                  )}
                </li>
              ))}
            </ul>
          </section>
        )}
        {isGameOver && (
          <section
            aria-label="Game Result Summary"
            className="mx-auto w-full max-w-xl rounded-sm border border-app-accent/30 bg-app-surface-raised p-4 sm:p-5 flex items-center justify-between gap-4"
          >
            <div>
              <span className="font-mono text-xs text-app-accent">
                {isWon ? 'Puzzle Solved' : 'Game Over'}
              </span>
              <h3 className="text-base sm:text-lg font-bold text-app-text">
                {correctCountry?.name || 'Mystery Flag'}
              </h3>
              {isWon && gameState && gameState.points > 0 ? (
                <p className="font-mono text-xs text-app-accent">+{gameState.points.toLocaleString('en-US')} pts</p>
              ) : null}
            </div>
            <button
              type="button"
              onClick={() => setShowResultsModal(true)}
              className="inline-flex min-h-10 items-center gap-2 rounded-sm bg-app-accent hover:bg-app-accent-hover px-4 py-2 text-xs sm:text-sm font-semibold text-white transition-colors cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-app-focus"
            >
              <Trophy size={16} aria-hidden="true" />
              <span>View Results</span>
            </button>
          </section>
        )}

        {/* Results Modal */}
        {isGameOver && showResultsModal && (
          <div className="fixed inset-0 z-[2000] flex max-h-[var(--app-height,100dvh)] items-center justify-center p-2 pb-[calc(env(safe-area-inset-bottom)+0.5rem)] sm:px-4 sm:pt-4 sm:pb-[calc(env(safe-area-inset-bottom)+1rem)] overflow-y-auto md:z-50 md:max-h-none">
            {/* Backdrop: clicking background closes modal */}
            <div
              className="fixed inset-0 bg-app-canvas/85 backdrop-blur-sm transition-opacity cursor-pointer"
              onClick={() => setShowResultsModal(false)}
              aria-hidden="true"
            />

            {/* Modal Dialog Card */}
            <section
              role="dialog"
              aria-modal="true"
              aria-label="Game Result"
              className="relative z-10 mx-auto w-full max-w-2xl sm:max-w-3xl max-h-full overflow-y-auto rounded-sm border border-app-border/30 bg-app-surface-raised p-3 md:max-h-[92vh] sm:p-8 shadow-sm text-left space-y-4 sm:space-y-6 my-auto"
              onClick={(e) => e.stopPropagation()}
            >
              {/* Header Bar */}
              <div className="flex items-center justify-between border-b border-app-border/20 pb-3.5 -mt-1 text-left">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs text-app-accent font-semibold">
                    Flagdle Result
                  </span>
                  <span className="text-app-text-muted">·</span>
                  <span className="font-mono text-xs text-app-text-secondary">
                    {dailyDate}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => setShowResultsModal(false)}
                  className="flex h-11 w-11 md:h-8 md:w-8 shrink-0 items-center justify-center rounded-sm bg-app-surface-muted text-app-text-secondary hover:bg-app-border/20 hover:text-app-text transition-colors cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-app-focus"
                  aria-label="Close"
                  title="Close"
                >
                  <X size={16} />
                </button>
              </div>

              {/* Hero Reveal Banner */}
              <div className="rounded-sm border border-app-border/20 bg-app-surface-muted p-3 sm:p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-3 sm:gap-5">
                <div className="flex items-center gap-4 sm:gap-5 min-w-0">
                  {correctCountry && (
                    <div className="shrink-0 overflow-hidden rounded-sm border border-app-border/30 bg-app-surface p-1 shadow-md">
                      {resolvedFlagUrl ? (
                        <img
                          src={resolvedFlagUrl}
                          alt={correctCountry.name}
                          className="h-14 w-22 sm:h-18 sm:w-28 object-contain"
                        />
                      ) : correctCountry?.iso2 ? (
                        <img
                          src={`https://flagcdn.com/w320/${correctCountry.iso2.toLowerCase()}.png`}
                          alt={correctCountry.name}
                          className="h-14 w-22 sm:h-18 sm:w-28 object-contain"
                        />
                      ) : null}
                    </div>
                  )}
                  <div className="min-w-0">
                    <span className="font-mono text-xs text-app-accent font-semibold">
                      Secret National Flag
                    </span>
                    <h2 className="mt-0.5 break-words font-serif text-3xl sm:text-4xl text-app-text">
                      {correctCountry?.name || 'Mystery Country'}
                    </h2>
                    {correctCountry?.official_name && correctCountry.official_name !== correctCountry.name && (
                      <p className="mt-0.5 text-xs text-app-text-secondary truncate">{correctCountry.official_name}</p>
                    )}
                    <p className="mt-1 text-xs text-app-text-secondary">
                      {isWon
                        ? `Identified in ${guesses.length} of 12 guesses.`
                        : 'Used all 12 guesses. Study the flag and try tomorrow!'}
                    </p>
                  </div>
                </div>

                {/* Outcome Badge & Points */}
                <div className="flex sm:flex-col items-center sm:items-end justify-between gap-2 shrink-0 border-t sm:border-t-0 border-app-border/20 pt-3 sm:pt-0">
                  <div className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-sm text-xs font-semibold font-mono ${
                    isWon ? 'bg-app-accent/10 border border-app-accent/30 text-app-accent' : 'bg-rose-50 border border-rose-300 text-rose-800'
                  }`}>
                    {isWon ? <Sparkles size={14} /> : <AlertCircle size={14} />}
                    <span>{isWon ? 'Solved' : 'Game Over'}</span>
                  </div>
                  {isWon && gameState?.points ? (
                    <div className="font-mono text-xl sm:text-2xl font-bold text-app-accent">
                      +{gameState.points.toLocaleString('en-US')} pts
                    </div>
                  ) : null}
                </div>
              </div>

              {/* Performance Metrics Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 sm:gap-4">
                <div className="rounded-sm border border-app-border/20 bg-app-surface p-4">
                  <span className="text-xs font-mono text-app-text-secondary block">
                    Guesses Used
                  </span>
                  <div className="mt-1 flex items-baseline gap-1.5">
                    <span className="font-mono text-2xl sm:text-3xl font-bold text-app-text">{guesses.length}</span>
                    <span className="text-xs text-app-text-muted font-mono">/ 12</span>
                  </div>
                </div>

                <div className="rounded-sm border border-app-border/20 bg-app-surface p-4">
                  <span className="text-xs font-mono text-app-text-secondary block">
                    Points Earned
                  </span>
                  <div className="mt-1 font-mono text-2xl sm:text-3xl font-bold text-app-accent">
                    {isWon && gameState?.points ? `+${gameState.points.toLocaleString('en-US')}` : '0 pts'}
                  </div>
                </div>

                <div className="col-span-2 sm:col-span-1 rounded-sm border border-app-border/20 bg-app-surface p-4 flex flex-col justify-between">
                  <span className="text-xs font-mono text-app-text-secondary block">
                    Next Flagdle
                  </span>
                  <div className="mt-1 font-mono text-lg sm:text-xl font-semibold text-app-accent">
                    <CountdownTimer variant="minimal" className="text-lg sm:text-xl text-app-accent font-semibold" />
                  </div>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="space-y-3 pt-1">
                <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
                  <button
                    type="button"
                    onClick={handleShare}
                    className="flex-1 flex min-h-12 items-center justify-center gap-2.5 rounded-sm bg-app-accent hover:bg-app-accent-hover px-5 py-3 text-sm font-bold text-white transition-colors shadow-md cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-app-focus"
                  >
                    {copied ? <Check size={16} aria-hidden="true" /> : <Share2 size={16} aria-hidden="true" />}
                    <span>{copied ? 'Copied to clipboard' : 'Share Flagdle Result'}</span>
                  </button>
                  <Link
                    to="/friends?mode=countrydle"
                    className="flex min-h-12 items-center justify-center gap-2 rounded-sm border border-amber-700/25 bg-amber-500/10 px-4 py-3 text-xs sm:text-sm font-semibold text-amber-800 hover:bg-amber-500/15 transition-colors"
                  >
                    <span className="rounded-sm bg-amber-500/15 px-2 py-0.5 font-mono text-[10px] uppercase font-bold text-amber-800">
                      1v1 Duel
                    </span>
                    <span>Challenge a friend</span>
                    <ArrowRight size={15} />
                  </Link>
                </div>

                <button
                  type="button"
                  onClick={() => setShowResultsModal(false)}
                  className="w-full min-h-11 rounded-sm border border-app-border/30 py-2.5 text-xs font-semibold text-app-text-secondary hover:bg-app-surface-muted transition-colors cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-app-focus"
                >
                  Close & View Flag
                </button>
              </div>
            </section>
          </div>
        )}

      </main>

      {/* Instructions Modal — WIDER CONTAINER (max-w-4xl) */}
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
            aria-label="How to Play Flagdle"
            className="relative z-10 w-full max-w-4xl max-h-full overflow-y-auto rounded-sm border border-app-border/30 bg-app-surface-raised p-3 md:max-h-[92vh] sm:rounded-sm sm:p-8 shadow-sm space-y-4 sm:space-y-6 my-auto text-app-text"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between border-b border-app-border/20 pb-4 text-left gap-4">
              <div>
                <h2 className="text-2xl sm:text-3xl font-serif font-bold tracking-tight text-app-text flex items-center gap-2.5">
                  <span>🚩 How to Play Flagdle</span>
                </h2>
                <p className="mt-1.5 text-sm text-app-text-secondary leading-relaxed max-w-xl">
                  Deduce the secret national flag in <strong>12 guesses or fewer</strong>. A new mystery flag rotates daily at 00:00 UTC.
                </p>
              </div>
              <button
                type="button"
                onClick={handleCloseInstructions}
                className="flex h-11 w-11 shrink-0 items-center justify-center rounded-sm bg-app-surface-muted text-app-text-secondary hover:bg-app-border/20 hover:text-app-text transition-colors cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-app-focus md:h-8 md:w-8"
                aria-label="Close"
                title="Close"
              >
                <X size={16} />
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="rounded-sm border border-emerald-700/25 bg-app-surface-muted p-5 space-y-2 flex flex-col justify-between">
                <div>
                  <div className="font-mono text-xs font-semibold text-app-text flex items-center gap-2">
                    <span>1. 12-Card Cover Grid</span>
                  </div>
                  <p className="mt-2 text-xs sm:text-sm text-app-text-secondary leading-relaxed">
                    The secret flag is covered by 12 solid tiles in a 3×4 grid. Each guess unmasks 1 tile, progressively revealing more of the national flag design underneath.
                  </p>
                </div>
                <div className="pt-2 border-t border-app-border/20 text-[11px] font-mono text-app-text-muted">
                  1 unmasked tile per guess
                </div>
              </div>

              <div className="rounded-sm border border-cyan-700/25 bg-app-surface-muted p-5 space-y-2 flex flex-col justify-between">
                <div>
                  <div className="font-mono text-xs font-semibold text-app-text flex items-center gap-2">
                    <span>2. Color &amp; Symbol Match</span>
                  </div>
                  <p className="mt-2 text-xs sm:text-sm text-app-text-secondary leading-relaxed">
                    Each guess compares the colors and symbols of your guessed flag against the secret target. Green chips show matching colors; crossed-out chips indicate absent colors.
                  </p>
                </div>
                <div className="pt-2 border-t border-app-border/20 text-[11px] font-mono text-app-text-muted">
                  Color &amp; symbol overlap clues
                </div>
              </div>

              <div className="rounded-sm border border-amber-700/25 bg-app-surface-muted p-5 space-y-2 flex flex-col justify-between">
                <div>
                  <div className="font-mono text-xs font-semibold text-app-text flex items-center gap-2">
                    <span>3. Distance &amp; Direction</span>
                  </div>
                  <p className="mt-2 text-xs sm:text-sm text-app-text-secondary leading-relaxed">
                    Distance in kilometers unlocks on guess 3, and compass bearing arrows (e.g. ↗ 3,200 km) point towards the secret target country starting on guess 5.
                  </p>
                </div>
                <div className="pt-2 border-t border-app-border/20 text-[11px] font-mono text-app-text-muted">
                  Great-circle distance &amp; compass bearing
                </div>
              </div>

              <div className="rounded-sm border border-indigo-700/25 bg-app-surface-muted p-5 space-y-2 flex flex-col justify-between">
                <div>
                  <div className="font-mono text-xs font-semibold text-app-text flex items-center gap-2">
                    <span>4. Unlimited Free AI Questions</span>
                  </div>
                  <p className="mt-2 text-xs sm:text-sm text-app-text-secondary leading-relaxed">
                    Stuck on the visual clues? You can ask unlimited yes/no questions about colors, stripes, stars, or symbols without consuming any of your 12 guess turns!
                  </p>
                </div>
                <div className="pt-2 border-t border-app-border/20 text-[11px] font-mono text-app-text-muted">
                  Free helper questions
                </div>
              </div>
            </div>
            <div className="rounded-sm border border-amber-700/20 bg-amber-50 p-3.5 flex items-start gap-3 text-xs">
              <Flag size={15} className="text-amber-800 shrink-0 mt-0.5" />
              <p className="text-amber-950 leading-relaxed">
                <strong className="text-amber-950">Spot a mistake?</strong> After the game, click the flag icon on any answer card in your history to report it with notes — it helps us see mistakes and patch them quickly.
              </p>
            </div>

            <div className="border-t border-app-border/20 pt-4 flex flex-col sm:flex-row items-center justify-between gap-4">
              <p className="text-xs text-app-text-muted font-mono text-center sm:text-left">
                This guide won't show automatically on startup again. You can reopen it anytime via the Flagdle Guide button.
              </p>
              <button
                type="button"
                onClick={handleCloseInstructions}
                className="w-full sm:w-auto inline-flex items-center justify-center gap-2 rounded-sm bg-app-accent hover:bg-app-accent-hover px-6 py-3 text-sm font-semibold text-white transition-colors shadow-lg cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-app-focus shrink-0"
              >
                <span>Got it, let's play</span>
                <ArrowRight size={16} />
              </button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
