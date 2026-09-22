import React from 'react';
import type { FlagdleGuess } from '../types';
import { Check, X, Compass, Palette, ShieldAlert } from 'lucide-react';

interface FlagClueTimelineProps {
  guesses: FlagdleGuess[];
}

const COLOR_CONFIG: Record<string, { dot: string; text: string; label: string }> = {
  red: { dot: 'bg-red-500 shadow-red-500/50', text: 'text-red-300', label: 'Red' },
  white: { dot: 'bg-white shadow-white/50', text: 'text-zinc-200', label: 'White' },
  blue: { dot: 'bg-blue-500 shadow-blue-500/50', text: 'text-blue-300', label: 'Blue' },
  yellow: { dot: 'bg-yellow-400 shadow-yellow-400/50', text: 'text-yellow-300', label: 'Yellow' },
  green: { dot: 'bg-emerald-500 shadow-emerald-500/50', text: 'text-emerald-300', label: 'Green' },
  black: { dot: 'bg-zinc-800 shadow-zinc-800/50 border border-zinc-600', text: 'text-zinc-300', label: 'Black' },
  orange: { dot: 'bg-orange-500 shadow-orange-500/50', text: 'text-orange-300', label: 'Orange' },
};

const SYMBOL_LABELS: Record<string, string> = {
  star: '★ Star',
  stars: '★ Stars',
  stripes: '≡ Stripes',
  cross: '✚ Cross',
  crescent: '🌙 Crescent',
  sun: '☀️ Sun',
  circle: '● Circle',
  eagle: '🦅 Eagle',
  coat_of_arms: '🛡️ Coat of arms',
};

function getDistanceBadgeClass(distanceKm: number): string {
  if (distanceKm <= 500) {
    return 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300';
  }
  if (distanceKm <= 2000) {
    return 'border-amber-500/30 bg-amber-500/10 text-amber-300';
  }
  return 'border-sand-700/50 bg-sand-900/40 text-sand-300';
}

export const FlagClueTimeline: React.FC<FlagClueTimelineProps> = ({ guesses }) => {
  if (guesses.length === 0) {
    return null;
  }

  return (
    <div className="mx-auto w-full max-w-xl space-y-3">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-sand-400 px-1">
        Deduction Timeline & Clues
      </h3>

      <div className="space-y-3">
        {guesses.map((g, idx) => {
          const attemptNum = idx + 1;
          const hasDistance = g.distance_km !== null && g.distance_km !== undefined && !g.answer;
          const hasBearing = Boolean(g.bearing_direction && !g.answer);
          const matchedColors = g.matched_colors || [];
          const missedColors = g.missed_colors || [];
          const matchedSymbols = g.matched_symbols || [];

          return (
            <div
              key={g.id || idx}
              className={`rounded-xl border bg-sand-950 p-3 sm:p-4 shadow-lg transition-all ${
                g.answer
                  ? 'border-emerald-500/80 shadow-emerald-950/40'
                  : 'border-sand-800/80 shadow-sand-950/60'
              }`}
            >
              {/* Top Row: Attempt #, Country Name, and Result Badge */}
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-sand-800/50 pb-2.5">
                <div className="flex items-center gap-2.5 min-w-0">
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-sand-900 text-xs font-mono font-bold text-sand-400">
                    #{attemptNum}
                  </span>
                  <span className="truncate text-base font-semibold text-sand-100">
                    {g.guess}
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  {g.answer ? (
                    <span className="inline-flex items-center gap-1 rounded-full border border-emerald-500/40 bg-emerald-500/10 px-2.5 py-0.5 text-xs font-semibold text-emerald-400">
                      <Check size={14} /> Correct Target
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 rounded-full border border-rose-500/40 bg-rose-500/10 px-2.5 py-0.5 text-xs font-semibold text-rose-400">
                      <X size={14} /> Incorrect
                    </span>
                  )}
                </div>
              </div>

              {/* Middle Section: Clue Matrix */}
              {!g.answer && (
                <div className="mt-3 space-y-2.5 text-xs">
                  {/* 1. Distance & Compass Bearing */}
                  {hasDistance && (
                    <div className="flex items-center gap-2 text-sand-300">
                      <Compass size={15} className="shrink-0 text-amber-400" />
                      <span className="font-medium text-sand-400">Distance & Direction:</span>
                      <span
                        className={`rounded px-2 py-0.5 font-mono font-bold border ${getDistanceBadgeClass(
                          g.distance_km!
                        )}`}
                      >
                        {g.distance_km!.toLocaleString()} km
                      </span>
                      {hasBearing && (
                        <span className="font-mono font-bold text-amber-300">
                          {g.bearing_arrow} {g.bearing_direction}
                        </span>
                      )}
                    </div>
                  )}

                  {/* 2. Color Overlap Chips */}
                  <div className="space-y-1.5 pt-1">
                    <div className="flex items-center gap-1.5 text-sand-400 font-medium">
                      <Palette size={14} className="shrink-0 text-sand-400" />
                      <span>Color Analysis:</span>
                    </div>

                    <div className="flex flex-wrap items-center gap-1.5 pl-5">
                      {/* Matched Colors */}
                      {matchedColors.map((col) => {
                        const conf = COLOR_CONFIG[col.toLowerCase()] || {
                          dot: 'bg-sand-400',
                          text: 'text-sand-300',
                          label: col,
                        };
                        return (
                          <span
                            key={col}
                            className="inline-flex items-center gap-1.5 rounded-md border border-emerald-600/40 bg-emerald-950/40 px-2 py-0.5 text-xs font-medium text-emerald-200"
                            title={`Color ${conf.label} is in the secret flag`}
                          >
                            <span className={`h-2 w-2 rounded-full shadow-sm ${conf.dot}`} />
                            {conf.label}
                            <Check size={11} className="text-emerald-400" />
                          </span>
                        );
                      })}

                      {/* Missed Colors */}
                      {missedColors.map((col) => {
                        const conf = COLOR_CONFIG[col.toLowerCase()] || {
                          dot: 'bg-sand-500',
                          text: 'text-sand-400',
                          label: col,
                        };
                        return (
                          <span
                            key={col}
                            className="inline-flex items-center gap-1.5 rounded-md border border-sand-800 bg-sand-900/60 px-2 py-0.5 text-xs font-medium text-sand-400 line-through decoration-rose-500/80"
                            title={`Color ${conf.label} is NOT in the secret flag`}
                          >
                            <span className={`h-2 w-2 rounded-full opacity-60 ${conf.dot}`} />
                            {conf.label}
                          </span>
                        );
                      })}

                      {matchedColors.length === 0 && missedColors.length === 0 && (
                        <span className="text-sand-500 italic">No color data</span>
                      )}

                      {/* Remaining undiscovered colors count */}
                      {g.remaining_colors_count !== null && g.remaining_colors_count !== undefined && (
                        <span className="ml-auto text-[11px] font-mono text-sand-500">
                          {g.remaining_colors_count === 0
                            ? 'All flag colors found!'
                            : `${g.remaining_colors_count} undiscovered ${
                                g.remaining_colors_count === 1 ? 'color' : 'colors'
                              } left`}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* 3. Symbol Match Badges */}
                  <div className="space-y-1.5 pt-1">
                    <div className="flex items-center gap-1.5 text-sand-400 font-medium">
                      <ShieldAlert size={14} className="shrink-0 text-sand-400" />
                      <span>Shared Heraldic Symbols:</span>
                    </div>

                    <div className="flex flex-wrap items-center gap-1.5 pl-5">
                      {matchedSymbols.length > 0 ? (
                        matchedSymbols.map((sym) => (
                          <span
                            key={sym}
                            className="inline-flex items-center gap-1 rounded-md border border-amber-600/40 bg-amber-950/40 px-2 py-0.5 text-xs font-semibold text-amber-200"
                          >
                            {SYMBOL_LABELS[sym.toLowerCase()] || sym}
                            <Check size={11} className="text-amber-400" />
                          </span>
                        ))
                      ) : (
                        <span className="text-sand-500 italic text-[11px]">
                          No shared symbols (star, stripes, cross, crescent, etc.)
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default FlagClueTimeline;
