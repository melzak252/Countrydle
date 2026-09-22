import React from 'react';

interface FlagTilesProps {
  stage: number; // 1 to 6
  isGameOver: boolean;
  flagUrl: string | null;
  countryName?: string | null;
}

// 6 grid tiles (row 1: 0, 1, 2; row 2: 3, 4, 5)
// Unmask order: [0, 4, 2, 5, 1, 3]
const UNMASK_ORDER = [0, 4, 2, 5, 1, 3];

export const FlagTiles: React.FC<FlagTilesProps> = ({
  stage,
  isGameOver,
  flagUrl,
  countryName,
}) => {
  const effectiveStage = isGameOver ? 6 : Math.max(1, Math.min(6, stage));
  const revealedSet = new Set(UNMASK_ORDER.slice(0, effectiveStage));

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

        {/* 6-Tile Curtain Mask Overlay (active only before game over) */}
        {!isGameOver && (
          <div className="absolute inset-0 grid grid-cols-3 grid-rows-2">
            {[0, 1, 2, 3, 4, 5].map((tileIdx) => {
              const isRevealed = revealedSet.has(tileIdx);
              return (
                <div
                  className={`border border-white/10 backdrop-blur-sm transition-all duration-700 ease-out flex items-center justify-center ${
                    isRevealed
                      ? 'pointer-events-none opacity-0 scale-95'
                      : 'bg-obsidian-900/98 opacity-100 shadow-inner'
                  }`}
                >
                  {!isRevealed && (
                    <span className="select-none font-mono text-xs sm:text-sm font-semibold text-zinc-600">
                      ?
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div className="mt-3 flex items-center justify-between px-2 text-xs sm:text-sm font-medium text-zinc-400">
        <div className="flex items-center gap-1.5">
          <span className="inline-block h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
          <span>Tile {effectiveStage} of 6</span>
        </div>
        <span className="font-mono text-sand-100 font-semibold">
          {Math.min(100, Math.round((effectiveStage / 6) * 100))}% Unmasked
        </span>
      </div>
    </div>
  );
};

export default FlagTiles;
