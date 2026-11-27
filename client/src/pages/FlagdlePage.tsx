import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useFlagdleGameStore } from '../stores/gameStore';
import { FlagTiles } from '../components/FlagTiles';
import GameResultDashboard from '../components/result-dashboard/GameResultDashboard';
import { Loader2, HelpCircle, Check, X, Trophy, ArrowRight, Flag } from 'lucide-react';
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

  const buildShareText = () => {
    if (!dailyDate || !gameState) return '';
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

    return lines.join('\n');
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
      <div role="status" className="flex h-[60vh] items-center justify-center gap-3 text-emerald-400">
        <Loader2 className="animate-spin" size={24} aria-hidden="true" />
        <span className="text-sm font-medium text-sand-300">Loading daily Flagdle...</span>
      </div>
    );
  }
  return (
    <div className="mx-auto w-full max-w-4xl px-3 py-2 sm:px-6 sm:py-4">
      {/* Header Bar */}
      <header className="mb-3 flex flex-wrap items-center justify-between gap-2 border-b border-sand-800/80 pb-2 sm:mb-6 sm:gap-3 sm:pb-4">
        <div>
          <div className="mb-1 flex items-center gap-2 text-xs font-mono font-semibold text-sand-400">
            <span>Daily Flag Deduction</span>
            <span>•</span>
            <span>{dailyDate}</span>
          </div>
          <h1 className="text-xl font-bold tracking-tight text-sand-100 sm:text-3xl">Flagdle</h1>
          {isGuest && <p className="mt-1 text-xs text-sand-500">Playing as Guest • No account required</p>}
        </div>

        <div className="flex items-center gap-3">
          {/* Guesses Remaining Pill */}
          <div className="flex items-center rounded-sm border border-white/10 bg-obsidian-900 px-2.5 py-1.5 shadow-sm sm:px-3.5 sm:py-2">
            <span className="text-xs text-zinc-400 mr-2 font-mono">Guesses:</span>
            <span
              className={`font-mono text-base font-bold ${
                guesses.length >= 10 ? 'text-amber-400' : 'text-emerald-400'
              }`}
            >
              {guesses.length}
            </span>
            <span className="text-xs text-zinc-500 font-mono"> / 12</span>
          </div>
          {/* Instructions Modal Button */}
          <button
            type="button"
            onClick={() => setShowInstructions(true)}
            className="flex h-11 w-11 items-center justify-center rounded-sm border border-sand-800 bg-sand-900 text-sand-400 hover:border-sand-700 hover:text-sand-200 transition-colors sm:h-9 sm:w-9"
            title="How to play Flagdle"
          >
            <HelpCircle size={18} />
          </button>
          {isGameOver && (
            <button
              type="button"
              onClick={() => setShowResultsModal(true)}
              className="flex h-11 md:h-9 items-center gap-1.5 px-3 rounded-xl border border-emerald-500/40 bg-emerald-950/40 text-emerald-300 hover:bg-emerald-900/50 transition-colors text-xs font-semibold cursor-pointer"
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
                    className="w-full min-w-0 rounded-sm border border-white/15 bg-obsidian-950 px-3 py-2.5 text-base md:text-sm text-sand-100 placeholder:text-zinc-500 shadow-inner focus:border-emerald-500/70 focus:outline-none focus:ring-1 focus:ring-emerald-500/30 disabled:opacity-50 sm:px-4 sm:py-3"
                  />

                  {/* Suggestion Dropdown */}
                  {showSuggestions && filteredCountries.length > 0 && (
                    <div
                      ref={dropdownRef}
                      className="absolute left-0 right-0 top-full z-50 mt-1.5 max-h-64 max-md:max-h-[min(35dvh,calc(var(--app-height,100dvh)-8rem))] overflow-y-auto rounded-sm border border-white/15 bg-obsidian-900 p-1.5 shadow-2xl"
                    >
                      {filteredCountries.map((c, idx) => (
                        <div
                          key={c.id}
                          onClick={() => handleSelectCountry(c)}
                          onMouseEnter={() => setHighlightedIndex(idx)}
                          className={`flex max-md:min-h-11 items-center justify-between gap-2 rounded-sm px-3 py-2 cursor-pointer transition-colors ${
                            idx === highlightedIndex ? 'bg-white/10 text-white' : 'text-zinc-300 hover:bg-white/5'
                          }`}
                        >
                          <span className="text-sm font-medium">{c.name}</span>
                          {c.official_name && c.official_name !== c.name && (
                            <span className="text-xs text-zinc-500 truncate ml-auto">
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
                  className="inline-flex min-h-11 shrink-0 items-center justify-center rounded-sm bg-emerald-400 px-3 py-2.5 text-sm font-semibold text-obsidian-950 shadow-md hover:bg-emerald-300 active:scale-95 disabled:pointer-events-none disabled:opacity-50 transition-colors cursor-pointer sm:px-5 sm:py-3"
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
              <span className="text-xs font-mono text-zinc-400">Your Guesses</span>
              <span className="text-xs font-mono text-zinc-500">{guesses.length} / 12</span>
            </div>
            <ul className="space-y-1.5">
              {sortedGuesses.map((g, idx) => (
                <li
                  key={g.id || idx}
                  className={`flex items-center justify-between rounded-sm border-l-2 bg-obsidian-950 px-3.5 py-2.5 ${
                    g.answer ? 'border-emerald-400' : 'border-rose-500/60'
                  }`}
                >
                  <div className="flex items-center gap-3 min-w-0">
                    {g.answer ? (
                      <Check size={16} className="shrink-0 text-emerald-400" aria-hidden="true" />
                    ) : (
                      <X size={16} className="shrink-0 text-rose-400" aria-hidden="true" />
                    )}
                    <span className="truncate text-sm font-medium text-sand-100">{g.guess}</span>
                  </div>
                  {g.distance_km !== null && g.distance_km !== undefined && !g.answer && (
                    <div className="flex items-center gap-1.5 font-mono text-xs text-zinc-400">
                      <span className="rounded border border-white/10 bg-white/5 px-2 py-0.5 text-zinc-300">
                        {g.distance_km.toLocaleString('en-US')} km
                      </span>
                      {g.bearing_arrow && (
                        <span className="text-emerald-400 text-sm font-semibold">{g.bearing_arrow}</span>
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
            className="mx-auto w-full max-w-xl rounded-sm border border-emerald-500/30 bg-obsidian-950 p-4 sm:p-5 flex items-center justify-between gap-4"
          >
            <div>
              <span className="font-mono text-xs text-emerald-400">
                {isWon ? 'Puzzle Solved' : 'Game Over'}
              </span>
              <h3 className="text-base sm:text-lg font-bold text-sand-100">
                {correctCountry?.name || 'Mystery Flag'}
              </h3>
              {isWon && gameState && gameState.points > 0 ? (
                <p className="font-mono text-xs text-emerald-400">+{gameState.points.toLocaleString('en-US')} pts</p>
              ) : null}
            </div>
            <button
              type="button"
              onClick={() => setShowResultsModal(true)}
              className="inline-flex min-h-10 items-center gap-2 rounded-sm bg-emerald-400 hover:bg-emerald-300 px-4 py-2 text-xs sm:text-sm font-semibold text-obsidian-950 transition-colors cursor-pointer"
            >
              <Trophy size={16} aria-hidden="true" />
              <span>View Results</span>
            </button>
          </section>
        )}

        {/* Results Dashboard */}
        {isGameOver && showResultsModal && (
          <GameResultDashboard
            mode="flagdle"
            modeKind="visual"
            gameName="Flagdle"
            gamePath="/flagdle"
            date={dailyDate}
            won={isWon}
            points={gameState?.points}
            guessesMade={guesses.length}
            maxGuesses={12}
            targetLabel="Secret National Flag"
            targetName={correctCountry?.name || 'Mystery Country'}
            targetSubtitle={
              correctCountry?.official_name && correctCountry.official_name !== correctCountry.name
                ? correctCountry.official_name
                : undefined
            }
            targetImageUrl={resolvedFlagUrl}
            targetCountryCode={correctCountry?.iso2}
            subtitle={
              isWon
                ? `Identified in ${guesses.length} of 12 guesses.`
                : 'Used all 12 guesses. Study the flag and try tomorrow!'
            }
            shareText={buildShareText()}
            duelMode="countrydle"
            onClose={() => setShowResultsModal(false)}
            closeLabel="Close & View Flag"
          />
        )}

      </main>

      {/* Instructions Modal — WIDER CONTAINER (max-w-4xl) */}
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
            aria-label="How to Play Flagdle"
            className="relative z-10 w-full max-w-4xl max-h-full overflow-y-auto rounded-sm border border-white/15 bg-obsidian-950 p-3 md:max-h-[92vh] sm:rounded-md sm:p-8 shadow-2xl space-y-4 sm:space-y-6 my-auto text-sand-100"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between border-b border-white/10 pb-4 text-left gap-4">
              <div>
                <h2 className="text-2xl sm:text-3xl font-serif font-bold tracking-tight text-sand-100 flex items-center gap-2.5">
                  <span>🚩 How to Play Flagdle</span>
                </h2>
                <p className="mt-1.5 text-sm text-zinc-400 leading-relaxed max-w-xl">
                  Deduce the secret national flag in <strong>12 guesses or fewer</strong>. A new mystery flag rotates daily at 00:00 UTC.
                </p>
              </div>
              <button
                type="button"
                onClick={handleCloseInstructions}
                className="flex h-11 w-11 shrink-0 items-center justify-center rounded-sm bg-white/5 text-zinc-400 hover:bg-white/15 hover:text-white transition-colors cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-400 md:h-8 md:w-8"
                aria-label="Close"
                title="Close"
              >
                <X size={16} />
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="rounded-sm border border-emerald-500/30 bg-obsidian-900/80 p-5 space-y-2 flex flex-col justify-between">
                <div>
                  <div className="font-mono text-xs font-semibold text-zinc-300 flex items-center gap-2">
                    <span>1. 12-Card Cover Grid</span>
                  </div>
                  <p className="mt-2 text-xs sm:text-sm text-zinc-300 leading-relaxed">
                    The secret flag is covered by 12 solid tiles in a 3×4 grid. Each guess unmasks 1 tile, progressively revealing more of the national flag design underneath.
                  </p>
                </div>
                <div className="pt-2 border-t border-white/5 text-[11px] font-mono text-zinc-500">
                  1 unmasked tile per guess
                </div>
              </div>

              <div className="rounded-sm border border-cyan-500/30 bg-obsidian-900/80 p-5 space-y-2 flex flex-col justify-between">
                <div>
                  <div className="font-mono text-xs font-semibold text-zinc-300 flex items-center gap-2">
                    <span>2. Color &amp; Symbol Match</span>
                  </div>
                  <p className="mt-2 text-xs sm:text-sm text-zinc-300 leading-relaxed">
                    Each guess compares the colors and symbols of your guessed flag against the secret target. Green chips show matching colors; crossed-out chips indicate absent colors.
                  </p>
                </div>
                <div className="pt-2 border-t border-white/5 text-[11px] font-mono text-zinc-500">
                  Color &amp; symbol overlap clues
                </div>
              </div>

              <div className="rounded-sm border border-amber-500/30 bg-obsidian-900/80 p-5 space-y-2 flex flex-col justify-between">
                <div>
                  <div className="font-mono text-xs font-semibold text-zinc-300 flex items-center gap-2">
                    <span>3. Distance &amp; Direction</span>
                  </div>
                  <p className="mt-2 text-xs sm:text-sm text-zinc-300 leading-relaxed">
                    Distance in kilometers unlocks on guess 3, and compass bearing arrows (e.g. ↗ 3,200 km) point towards the secret target country starting on guess 5.
                  </p>
                </div>
                <div className="pt-2 border-t border-white/5 text-[11px] font-mono text-zinc-500">
                  Great-circle distance &amp; compass bearing
                </div>
              </div>

              <div className="rounded-sm border border-indigo-500/30 bg-obsidian-900/80 p-5 space-y-2 flex flex-col justify-between">
                <div>
                  <div className="font-mono text-xs font-semibold text-zinc-300 flex items-center gap-2">
                    <span>4. Unlimited Free AI Questions</span>
                  </div>
                  <p className="mt-2 text-xs sm:text-sm text-zinc-300 leading-relaxed">
                    Stuck on the visual clues? You can ask unlimited yes/no questions about colors, stripes, stars, or symbols without consuming any of your 12 guess turns!
                  </p>
                </div>
                <div className="pt-2 border-t border-white/5 text-[11px] font-mono text-zinc-500">
                  Free helper questions
                </div>
              </div>
            </div>
            <div className="rounded-sm border border-amber-500/20 bg-amber-500/[0.04] p-3.5 flex items-start gap-3 text-xs">
              <Flag size={15} className="text-amber-400 shrink-0 mt-0.5" />
              <p className="text-zinc-300 leading-relaxed">
                <strong className="text-amber-300">Spot a mistake?</strong> After the game, click the flag icon on any answer card in your history to report it with notes. It helps us spot mistakes and patch them quickly.
              </p>
            </div>

            <div className="border-t border-white/10 pt-4 flex flex-col sm:flex-row items-center justify-between gap-4">
              <p className="text-xs text-zinc-500 font-mono text-center sm:text-left">
                This guide won't show automatically on startup again. You can reopen it anytime via the Flagdle Guide button.
              </p>
              <button
                type="button"
                onClick={handleCloseInstructions}
                className="w-full sm:w-auto inline-flex items-center justify-center gap-2 rounded-sm bg-emerald-400 hover:bg-emerald-300 px-6 py-3 text-sm font-semibold text-obsidian-950 transition-colors shadow-lg cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-400 shrink-0"
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
