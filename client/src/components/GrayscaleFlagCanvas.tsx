import React, { useEffect, useRef, useState } from 'react';
import {
  type ColorHintFamily,
  selectColorHintFamily,
  transformFlagPixels,
} from '../lib/grayscaleFlag';

export interface GrayscaleFlagCanvasProps {
  stage?: number; // 1 to 12
  flagUrl: string | null;
  revealColorHint: boolean;
  isGameOver: boolean;
  countryName?: string | null;
  onHintInfoChange?: (info: { colorName: string; sharePct: number } | null) => void;
}

// 12 grid tiles (3 rows x 4 columns) — same unmask progression as Flagdle
const UNMASK_ORDER = [0, 11, 5, 6, 3, 8, 1, 10, 2, 9, 4, 7];
function formatFlagUrl(rawUrl: string): string {
  try {
    const parsed = new URL(
      rawUrl,
      typeof window !== 'undefined' ? window.location.origin : 'http://localhost'
    );
    parsed.searchParams.delete('fit');
    if (!rawUrl.startsWith('http://') && !rawUrl.startsWith('https://')) {
      return `${parsed.pathname}${parsed.search}${parsed.hash}`;
    }
    return parsed.toString();
  } catch {
    return rawUrl.replace(/[?&]fit=grid/, '');
  }
}

export const GrayscaleFlagCanvas: React.FC<GrayscaleFlagCanvasProps> = ({
  stage = 1,
  flagUrl,
  revealColorHint,
  isGameOver,
  countryName,
  onHintInfoChange,
}) => {
  const effectiveStage = isGameOver ? 12 : Math.max(1, Math.min(12, stage));
  const revealedSet = new Set(UNMASK_ORDER.slice(0, effectiveStage));
  const visibleCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const rawImageDataRef = useRef<ImageData | null>(null);
  const onHintInfoChangeRef = useRef(onHintInfoChange);

  const [hintInfo, setHintInfo] = useState<ColorHintFamily | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [hasError, setHasError] = useState(false);

  useEffect(() => {
    onHintInfoChangeRef.current = onHintInfoChange;
  }, [onHintInfoChange]);

  const paintVisibleCanvas = (
    raw: ImageData,
    reveal: boolean,
    gameOver: boolean,
    hint: ColorHintFamily | null
  ) => {
    const canvas = visibleCanvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const transformed = transformFlagPixels(raw.data, {
      revealColorFamily: reveal && hint ? hint.colorName : null,
      fullColor: gameOver,
    });

    const output = ctx.createImageData(900, 600);
    output.data.set(transformed);
    ctx.putImageData(output, 0, 0);
  };

  // Load and process the flag image whenever flagUrl or isGameOver changes
  useEffect(() => {
    if (!flagUrl) {
      rawImageDataRef.current = null;
      setHintInfo(null);
      onHintInfoChangeRef.current?.(null);
      setIsLoading(false);
      setHasError(false);

      const canvas = visibleCanvasRef.current;
      if (canvas) {
        const ctx = canvas.getContext('2d');
        ctx?.clearRect(0, 0, canvas.width, canvas.height);
      }
      return;
    }

    let cancelled = false;
    setIsLoading(true);
    setHasError(false);

    const img = new Image();
    img.crossOrigin = 'anonymous';
    const targetUrl = formatFlagUrl(flagUrl);

    img.onload = () => {
      if (cancelled) return;

      try {
        const offCanvas = document.createElement('canvas');
        offCanvas.width = 900;
        offCanvas.height = 600;
        const offCtx = offCanvas.getContext('2d', { willReadFrequently: true });
        if (!offCtx) {
          setIsLoading(false);
          return;
        }

        offCtx.clearRect(0, 0, 900, 600);

        // Always preserve natural proportions and center on 900x600 canvas without squashing width
        const nw = img.naturalWidth || img.width;
        const nh = img.naturalHeight || img.height;
        if (nw > 0 && nh > 0) {
          const imgAspect = nw / nh;
          const canvasAspect = 900 / 600;
          let dw = 900;
          let dh = 600;
          let dx = 0;
          let dy = 0;
          if (Math.abs(imgAspect - canvasAspect) > 0.01) {
            if (imgAspect > canvasAspect) {
              dw = 900;
              dh = 900 / imgAspect;
              dy = (600 - dh) / 2;
            } else {
              dh = 600;
              dw = 600 * imgAspect;
              dx = (900 - dw) / 2;
            }
            offCtx.drawImage(img, dx, dy, dw, dh);
          } else {
            offCtx.drawImage(img, 0, 0, 900, 600);
          }
        } else {
          offCtx.drawImage(img, 0, 0, 900, 600);
        }

        const raw = offCtx.getImageData(0, 0, 900, 600);
        rawImageDataRef.current = raw;

        const computedHint = selectColorHintFamily(raw.data, 0.10);
        setHintInfo(computedHint);
        onHintInfoChangeRef.current?.(computedHint);
        setIsLoading(false);

        // Paint immediately onto the visible canvas
        paintVisibleCanvas(raw, revealColorHint, isGameOver, computedHint);
      } catch (err) {
        if (!cancelled) {
          setHasError(true);
          setIsLoading(false);
        }
      }
    };

    img.onerror = () => {
      if (!cancelled) {
        setHasError(true);
        setIsLoading(false);
      }
    };

    img.src = targetUrl;

    return () => {
      cancelled = true;
    };
  }, [flagUrl, isGameOver]);

  // Re-paint whenever hint reveal toggle or hint info changes without reloading image
  useEffect(() => {
    if (rawImageDataRef.current) {
      paintVisibleCanvas(rawImageDataRef.current, revealColorHint, isGameOver, hintInfo);
    }
  }, [revealColorHint, isGameOver, hintInfo]);

  return (
    <div className="relative mx-auto w-full max-w-xl overflow-hidden rounded-sm border border-white/15 bg-obsidian-950 p-2 sm:p-3 shadow-2xl">
      <div className="relative aspect-[3/2] w-full overflow-hidden rounded-sm bg-obsidian-900 flex items-center justify-center">
        {(!flagUrl || (isLoading && !rawImageDataRef.current)) && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-obsidian-900 text-zinc-500 animate-pulse font-mono text-sm">
            Loading Flag...
          </div>
        )}
        {hasError && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-obsidian-900 text-rose-400 font-mono text-sm">
            Failed to load flag
          </div>
        )}
        <canvas
          ref={visibleCanvasRef}
          width={900}
          height={600}
          aria-label={isGameOver && countryName ? `Flag of ${countryName}` : 'Flag in Shades of Grey'}
          className="h-full w-full object-contain select-none"
        />

        {/* 12-Card Physical Cover Overlay (uncovers 1 card per stage over the grayscale flag) */}
        {!isGameOver && (
          <div className="absolute inset-0 grid grid-cols-4 grid-rows-3 gap-0 p-0 bg-transparent pointer-events-none">
            {Array.from({ length: 12 }, (_, tileIdx) => {
              const isRevealed = revealedSet.has(tileIdx);
              return (
                <div
                  key={tileIdx}
                  className={`relative flex items-center justify-center transition-opacity duration-300 ease-out ${
                    isRevealed
                      ? 'opacity-0 pointer-events-none'
                      : 'bg-[#0f0f14] opacity-100 z-10 pointer-events-auto border border-white/10'
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

      {/* Status Footer Bar */}
      <div className="mt-2.5 flex flex-wrap items-center justify-between gap-2 px-1 text-xs font-mono text-zinc-400">
        <div className="flex items-center gap-1.5">
          <span className="inline-block h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
          <span>
            {effectiveStage} of 12 cards uncovered ({Math.min(100, Math.round((effectiveStage / 12) * 100))}%)
          </span>
        </div>
        <span data-testid="flag-shades-status">
          {isGameOver
            ? `Full Flag Colors Revealed${countryName ? ` · ${countryName}` : ''}`
            : revealColorHint && hintInfo
              ? `Color Hint Active · ${hintInfo.colorName} revealed (${hintInfo.sharePct}% of flag)`
              : 'Shades of Grey Mode · 0 colors revealed'}
        </span>
      </div>
    </div>
  );
};

export default GrayscaleFlagCanvas;
