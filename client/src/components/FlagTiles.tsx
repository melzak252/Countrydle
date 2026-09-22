import React from 'react';

interface FlagTilesProps {
  stage: number; // 1 to 6
  isGameOver: boolean;
  flagUrl: string | null;
  countryName?: string | null;
}

// 12 grid tiles (3 rows x 4 columns)
// Unmask order uncovers 2 symmetric/tactical cards per stage (12 cards total across 6 stages)
const UNMASK_ORDER = [0, 11, 5, 6, 3, 8, 1, 10, 2, 9, 4, 7];

export const FlagTiles: React.FC<FlagTilesProps> = ({
  stage,
  isGameOver,
  flagUrl,
  countryName,
}) => {
  const effectiveStage = isGameOver ? 6 : Math.max(1, Math.min(6, stage));
  const revealedCount = isGameOver ? 12 : Math.max(2, Math.min(12, effectiveStage * 2));
  const revealedSet = new Set(UNMASK_ORDER.slice(0, revealedCount));
  return (
    <div className="relative mx-auto w-full max-w-xl overflow-hidden rounded-sm border border-white/15 bg-obsidian-950 p-2 sm:p-3 shadow-2xl">
      <div className="relative aspect-[3/2] w-full overflow-hidden rounded-sm bg-obsidian-900 flex items-center justify-center">
        {flagUrl ? (
          <img
            src={flagUrl}
            alt={isGameOver && countryName ? `Flag of ${countryName}` : 'Mystery National Flag'}
            className="h-full w-full object-contain transition-all duration-700 select-none"
            draggable={false}
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-zinc-500 animate-pulse font-mono text-sm">
            Loading Flag...
          </div>
        )}

        {/* 6-Card Physical Cover Overlay (active only before game over) */}
        {!isGameOver && (
          <div className="absolute inset-0 grid grid-cols-4 grid-rows-3 gap-0.5 p-0.5 bg-obsidian-950">
            {Array.from({ length: 12 }, (_, tileIdx) => {
              const isRevealed = revealedSet.has(tileIdx);
              return (
                <div
                  key={tileIdx}
                  className={`relative flex items-center justify-center border border-white/15 transition-all duration-500 ease-out ${
                    isRevealed
                      ? 'pointer-events-none opacity-0 scale-95'
                      : 'bg-[#0f0f14] opacity-100 shadow-lg z-10'
                  }`}
                >
                  {!isRevealed && (
                    <div className="flex flex-col items-center justify-center gap-0.5 text-center p-1 select-none">
                      <div className="flex h-6 w-6 sm:h-7 sm:w-7 items-center justify-center rounded-full border border-white/15 bg-white/5 font-mono text-[10px] sm:text-xs font-semibold text-zinc-300 shadow-inner">
                        {tileIdx + 1}
                      </div>
                      <span className="font-mono text-[8px] sm:text-[9px] uppercase tracking-wider text-zinc-400 font-medium">
                        Card {tileIdx + 1}
                      </span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
      <div className="mt-3 flex items-center justify-between px-2 text-xs sm:text-sm font-medium text-zinc-400">
        <div className="flex items-center gap-1.5">
          <span>{revealedCount} of 12 cards uncovered</span>
        </div>
        <span className="font-mono text-sand-100 font-semibold">
          {Math.min(100, Math.round((revealedCount / 12) * 100))}% Revealed
        </span>
      </div>
    </div>
  );
};

export default FlagTiles;
