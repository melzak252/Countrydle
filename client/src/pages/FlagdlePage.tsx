import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useFlagdleGameStore } from '../stores/gameStore';
import { FlagTiles } from '../components/FlagTiles';
import CountdownTimer from '../components/CountdownTimer';
import { Loader2, HelpCircle, Share2, Check, X, Sparkles, AlertCircle, Trophy } from 'lucide-react';
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
  const [showInstructions, setShowInstructions] = useState(false);
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

  // Filter countries for autocomplete
  const filteredCountries = useMemo(() => {
    const query = inputVal.trim().toLowerCase();
    if (!query) return [];
    return countries
      .filter(
        (c) =>
          c.name.toLowerCase().includes(query) ||
          (c.official_name && c.official_name.toLowerCase().includes(query))
      )
      .slice(0, 8);
  }, [countries, inputVal]);

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
    const name = (selectedCountry ? selectedCountry.name : inputVal).trim();
    if (!name) return;

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

    if (!countryId) {
      toast.error('Please select a valid sovereign country from the list.');
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
    let text = `Countrydle Flagdle #${dailyDate} ${scoreText} 🚩\n\n`;

    guesses.forEach((g: FlagdleGuess, idx: number) => {
      const stageNum = idx + 1;
      const unmaskedCount = g.answer ? 12 : Math.min(12, stageNum);
      const tilesStr = Array.from({ length: 12 }, (_, i) => {
        if (i < unmaskedCount) {
          return g.answer ? '🟩' : '🟨';
        }
        return '⬛';
      }).join('');

      if (g.answer) {
        text += `${tilesStr} 🎯 FOUND!\n`;
      } else {
        const dist = g.distance_km ? `${g.distance_km.toLocaleString()}km` : '';
        const arrow = g.bearing_arrow || '🧭';
        const dir = g.bearing_direction || '';
        text += `${tilesStr} ${arrow} ${dist} ${dir}\n`;
      }
    });

    text += `\nhttps://countrydle.online/flagdle`;

    navigator.clipboard.writeText(text);
    setCopied(true);
    toast.success('Results copied to clipboard!');
    setTimeout(() => setCopied(false), 2500);
  };

  if (!gameState && isLoading) {
    return (
      <div role="status" className="flex h-[60vh] items-center justify-center gap-3 text-emerald-400">
        <Loader2 className="animate-spin" size={24} aria-hidden="true" />
        <span className="text-sm font-medium text-sand-300">Loading daily Flagdle...</span>
      </div>
    );
  }

  const isGameOver = gameState?.is_game_over || false;
  const isWon = gameState?.won || false;

  useEffect(() => {
    if (isGameOver) {
      setShowResultsModal(true);
    }
  }, [isGameOver]);

  const sortedGuesses = useMemo(() => [...guesses].reverse(), [guesses]);
  return (
    <div className="mx-auto w-full max-w-4xl px-3 py-4 sm:px-6">
      {/* Header Bar */}
      <header className="mb-6 flex flex-wrap items-center justify-between gap-3 border-b border-sand-800/80 pb-4">
        <div>
          <div className="mb-1 flex items-center gap-2 text-xs font-mono font-semibold uppercase tracking-wider text-sand-400">
            <span>🚩 Daily Flag Deduction</span>
            <span>•</span>
            <span>{dailyDate}</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-sand-100 sm:text-3xl">Flagdle</h1>
          {isGuest && <p className="mt-1 text-xs text-sand-500">Playing as Guest • No account required</p>}
        </div>

        <div className="flex items-center gap-3">
          {/* Guesses Remaining Pill */}
          <div className="flex items-center rounded-sm border border-white/10 bg-obsidian-900 px-3.5 py-2 shadow-sm">
            <span className="text-xs uppercase tracking-wider text-zinc-400 mr-2 font-mono">Guesses:</span>
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
            className="flex h-9 w-9 items-center justify-center rounded-xl border border-sand-800 bg-sand-900 text-sand-400 hover:border-sand-700 hover:text-sand-200 transition-colors"
            title="How to play Flagdle"
          >
            <HelpCircle size={18} />
          </button>
          {isGameOver && (
            <button
              type="button"
              onClick={() => setShowResultsModal(true)}
              className="flex h-9 items-center gap-1.5 px-3 rounded-xl border border-emerald-500/40 bg-emerald-950/40 text-emerald-300 hover:bg-emerald-900/50 transition-colors text-xs font-semibold cursor-pointer"
              title="Show results"
            >
              <Trophy size={15} />
              <span>Results</span>
            </button>
          )}
        </div>
      </header>

      {/* Main Game Container */}
      <main className="space-y-6">
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
                    className="w-full rounded-sm border border-white/15 bg-obsidian-950 px-4 py-3 text-sm text-sand-100 placeholder:text-zinc-500 shadow-inner focus:border-emerald-500/70 focus:outline-none focus:ring-1 focus:ring-emerald-500/30 disabled:opacity-50"
                  />

                  {/* Suggestion Dropdown */}
                  {showSuggestions && filteredCountries.length > 0 && (
                    <div
                      ref={dropdownRef}
                      className="absolute left-0 right-0 top-full z-50 mt-1.5 max-h-64 overflow-y-auto rounded-sm border border-white/15 bg-obsidian-900 p-1.5 shadow-2xl backdrop-blur-md"
                    >
                      {filteredCountries.map((c, idx) => (
                        <div
                          key={c.id}
                          onClick={() => handleSelectCountry(c)}
                          onMouseEnter={() => setHighlightedIndex(idx)}
                          className={`flex items-center justify-between gap-3 rounded-sm px-3 py-2 cursor-pointer transition-colors ${
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
                  className="inline-flex items-center justify-center rounded-sm bg-emerald-400 px-5 py-3 text-sm font-semibold text-obsidian-950 shadow-md hover:bg-emerald-300 active:scale-95 disabled:pointer-events-none disabled:opacity-50 transition-all cursor-pointer"
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
              <span className="text-xs font-mono uppercase tracking-wider text-zinc-400">Your Guesses</span>
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
                        {g.distance_km.toLocaleString()} km
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
              <span className="font-mono text-xs uppercase tracking-wider text-emerald-400">
                {isWon ? 'Puzzle Solved' : 'Game Over'}
              </span>
              <h3 className="text-base sm:text-lg font-bold text-sand-100">
                {correctCountry?.name || 'Mystery Flag'}
              </h3>
              {isWon && gameState && gameState.points > 0 ? (
                <p className="font-mono text-xs text-emerald-400">+{gameState.points.toLocaleString()} pts</p>
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

        {/* Results Modal */}
        {isGameOver && showResultsModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 overflow-y-auto">
            {/* Backdrop: clicking background closes modal */}
            <div
              className="fixed inset-0 bg-black/80 backdrop-blur-sm transition-opacity cursor-pointer"
              onClick={() => setShowResultsModal(false)}
              aria-hidden="true"
            />

            {/* Modal Dialog Card */}
            <section
              role="dialog"
              aria-modal="true"
              aria-label="Game Result"
              className="relative z-10 mx-auto w-full max-w-xl max-h-[90vh] overflow-y-auto rounded-sm border border-white/15 bg-obsidian-950 p-5 sm:p-6 shadow-2xl text-center space-y-4 my-auto"
              onClick={(e) => e.stopPropagation()}
            >
              {/* Dedicated top header bar with cleanly aligned close button */}
              <div className="flex items-center justify-between border-b border-white/10 pb-3 -mt-1 text-left">
                <span className="font-mono text-xs uppercase tracking-wider text-zinc-400">
                  Flagdle Result · {dailyDate}
                </span>
                <button
                  type="button"
                  onClick={() => setShowResultsModal(false)}
                  className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-white/5 text-zinc-400 hover:bg-white/15 hover:text-white transition-colors cursor-pointer"
                  aria-label="Close"
                  title="Close"
                >
                  <X size={16} />
                </button>
              </div>
              <div className="inline-flex items-center justify-center rounded-full p-3 bg-obsidian-900 border border-white/10">
                {isWon ? (
                  <Sparkles className="text-emerald-400" size={32} />
                ) : (
                  <AlertCircle className="text-rose-400" size={32} />
                )}
              </div>

              <div>
                <h2 className="text-xl sm:text-2xl font-bold text-sand-100">
                  {isWon ? 'Outstanding Vexillological Deduction!' : 'Mission Incomplete'}
                </h2>
                <p className="mt-1 text-sm text-zinc-400">
                  {isWon
                    ? `You accurately identified the flag in ${guesses.length} of 12 guesses.`
                    : 'You used all 12 guesses. Better luck tomorrow!'}
                </p>
              </div>

              {correctCountry && (
                <div className="rounded-sm border border-white/10 bg-obsidian-900/60 p-4 flex items-center justify-center gap-4">
                  {resolvedFlagUrl ? (
                    <img
                      src={resolvedFlagUrl}
                      alt={correctCountry.name}
                      className="h-12 w-20 object-contain rounded shadow border border-white/10"
                    />
                  ) : correctCountry?.iso2 ? (
                    <img
                      src={`https://flagcdn.com/w160/${correctCountry.iso2.toLowerCase()}.png`}
                      alt={correctCountry.name}
                      className="h-12 w-20 object-contain rounded shadow border border-white/10"
                    />
                  ) : null}
                  <div className="text-left">
                    <div className="text-xs uppercase tracking-wider text-zinc-400 font-semibold font-mono">
                      Secret National Flag
                    </div>
                    <div className="text-lg font-bold text-sand-100">{correctCountry.name}</div>
                    {correctCountry.official_name && correctCountry.official_name !== correctCountry.name && (
                      <div className="text-xs text-zinc-400">{correctCountry.official_name}</div>
                    )}
                  </div>
                </div>
              )}

              {isWon && gameState?.points ? (
                <div className="inline-block rounded-sm border border-emerald-500/30 bg-emerald-500/10 px-4 py-2 text-sm font-mono font-bold text-emerald-300">
                  Score: +{gameState.points.toLocaleString()} pts
                </div>
              ) : null}

              <div className="pt-2 flex flex-col gap-2">
                <button
                  type="button"
                  onClick={handleShare}
                  className="w-full inline-flex items-center justify-center gap-2 rounded-sm bg-emerald-400 hover:bg-emerald-300 py-3 text-sm font-semibold text-obsidian-950 shadow-md active:scale-95 transition-all cursor-pointer"
                >
                  {copied ? <Check size={16} /> : <Share2 size={16} />}
                  <span>{copied ? 'Copied to Clipboard!' : 'Share Flagdle Result'}</span>
                </button>
                <button
                  type="button"
                  onClick={() => setShowResultsModal(false)}
                  className="w-full min-h-11 rounded-sm border border-white/20 py-2.5 text-xs font-semibold text-sand-100 hover:bg-white/10 transition-colors"
                >
                  Close & View Flag
                </button>
              </div>

              <div className="border-t border-white/10 pt-3 text-xs text-zinc-400 flex items-center justify-center gap-2">
                <span>Next Flagdle in:</span>
                <CountdownTimer />
              </div>
            </section>
          </div>
        )}

      </main>

      {/* Instructions Modal */}
      {showInstructions && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 overflow-y-auto">
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black/80 backdrop-blur-sm transition-opacity cursor-pointer"
            onClick={() => setShowInstructions(false)}
            aria-hidden="true"
          />

          <div
            role="dialog"
            aria-modal="true"
            aria-label="How to Play Flagdle"
            className="relative z-10 w-full max-w-lg max-h-[90vh] overflow-y-auto rounded-sm border border-white/15 bg-obsidian-950 p-5 sm:p-6 shadow-2xl space-y-4 my-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-white/10 pb-3 -mt-1 text-left">
              <span className="font-mono text-[11px] uppercase tracking-[0.16em] text-emerald-400">
                Flagdle Guide
              </span>
              <button
                type="button"
                onClick={() => setShowInstructions(false)}
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-white/5 text-zinc-400 hover:bg-white/15 hover:text-white transition-colors cursor-pointer"
                aria-label="Close"
              >
                <X size={16} />
              </button>
            </div>

            <div>
              <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-sand-100 flex items-center gap-2">
                <span>🚩 How to Play Flagdle</span>
              </h2>
              <p className="mt-1 text-xs sm:text-sm text-zinc-400 leading-relaxed">
                Deduce the secret national flag in <strong>12 guesses or fewer</strong>. A new mystery flag rotates daily at 00:00 UTC.
              </p>
            </div>

            <div className="space-y-3 text-xs sm:text-sm text-zinc-300 leading-relaxed">
              <div className="rounded-sm border border-white/10 bg-obsidian-900/60 p-3.5 space-y-1.5">
                <div className="font-semibold text-sand-100 flex items-center gap-2">
                  <span>🎴 12-Card Cover Grid (3×4)</span>
                </div>
                <p className="text-zinc-400">
                  The flag is covered by 12 solid cards. Each guess unmasks 1 card, progressively revealing more of the flag underneath.
                </p>
              </div>

              <div className="rounded-sm border border-white/10 bg-obsidian-900/60 p-3.5 space-y-1.5">
                <div className="font-semibold text-sand-100 flex items-center gap-2">
                  <span>🎨 Color Overlap Clues</span>
                </div>
                <p className="text-zinc-400">
                  Each guess analyzes the colors of your guessed flag against the secret target. Green chips show shared colors, while crossed-out chips show colors absent from the secret flag.
                </p>
              </div>

              <div className="rounded-sm border border-white/10 bg-obsidian-900/60 p-3.5 space-y-1.5">
                <div className="font-semibold text-sand-100 flex items-center gap-2">
                  <span>🧭 Distance & Direction</span>
                </div>
                <p className="text-zinc-400">
                  An arrow and distance badge show the great-circle distance and compass bearing from your guessed country to the secret target.
                </p>
              </div>
            </div>

            <button
              type="button"
              onClick={() => setShowInstructions(false)}
              className="w-full rounded-sm bg-emerald-400 hover:bg-emerald-300 py-3 text-sm font-semibold text-obsidian-950 transition-colors shadow-lg cursor-pointer"
            >
              Got it, let's play!
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
