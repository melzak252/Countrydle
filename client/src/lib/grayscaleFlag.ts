/**
 * Utility functions for flag grayscale rendering and chromatic color hint extraction.
 */

export type ChromaticColorFamily =
  | 'Red'
  | 'Orange'
  | 'Yellow'
  | 'Green'
  | 'Light Blue'
  | 'Blue'
  | 'Purple';

export interface ColorHintFamily {
  colorName: string;
  sharePct: number;
}

/**
 * Converts RGB (0..255) to HSL [h (0..360), s (0..1), l (0..1)].
 */
export function rgbToHsl(r: number, g: number, b: number): [number, number, number] {
  const rNorm = Math.max(0, Math.min(1, r / 255));
  const gNorm = Math.max(0, Math.min(1, g / 255));
  const bNorm = Math.max(0, Math.min(1, b / 255));

  const max = Math.max(rNorm, gNorm, bNorm);
  const min = Math.min(rNorm, gNorm, bNorm);
  const delta = max - min;

  const l = (max + min) / 2;

  if (delta === 0) {
    return [0, 0, l];
  }

  const s = l > 0.5 ? delta / (2 - max - min) : delta / (max + min);

  let h = 0;
  if (max === rNorm) {
    h = (gNorm - bNorm) / delta + (gNorm < bNorm ? 6 : 0);
  } else if (max === gNorm) {
    h = (bNorm - rNorm) / delta + 2;
  } else {
    h = (rNorm - gNorm) / delta + 4;
  }

  h *= 60;
  if (h < 0) {
    h += 360;
  } else if (h >= 360) {
    h -= 360;
  }

  return [h, s, l];
}

/**
 * Classifies a pixel into one of 7 human-readable chromatic color families.
 * Excludes transparent pixels, black (l <= 0.12), white (l >= 0.90), and grey (s < 0.18).
 */
export function classifyChromaticColor(
  r: number,
  g: number,
  b: number,
  a = 255
): ChromaticColorFamily | null {
  if (a < 128) {
    return null;
  }

  const [h, s, l] = rgbToHsl(r, g, b);

  // Exclude Black, White, and Grey
  if (l <= 0.12 || l >= 0.90 || s < 0.18) {
    return null;
  }

  if (h >= 340 || h < 15) {
    return 'Red';
  }
  if (h >= 15 && h < 42) {
    return 'Orange';
  }
  if (h >= 42 && h < 70) {
    return 'Yellow';
  }
  if (h >= 70 && h < 165) {
    return 'Green';
  }
  if (h >= 165 && h < 205) {
    return 'Light Blue';
  }
  if (h >= 205 && h < 265) {
    return 'Blue';
  }
  if (h >= 265 && h < 340) {
    return 'Purple';
  }

  return null;
}

/**
 * Iterates over pixel RGBA data and determines the primary chromatic color family
 * for the flag color hint (at least minShare = 10% of visible pixels, or fallback to largest).
 */
export function selectColorHintFamily(
  rgba: Uint8ClampedArray,
  minShare = 0.10
): ColorHintFamily | null {
  let totalVisible = 0;
  const familyCounts: Record<string, number> = {};

  for (let i = 0; i < rgba.length; i += 4) {
    const a = rgba[i + 3];
    if (a < 128) continue;
    totalVisible++;

    const family = classifyChromaticColor(rgba[i], rgba[i + 1], rgba[i + 2], a);
    if (family) {
      familyCounts[family] = (familyCounts[family] || 0) + 1;
    }
  }

  if (totalVisible === 0) {
    return null;
  }

  const families = Object.entries(familyCounts).map(([colorName, count]) => ({
    colorName,
    count,
    share: count / totalVisible,
  }));

  const qualifying = families.filter((f) => f.share >= minShare);
  if (qualifying.length > 0) {
    qualifying.sort((a, b) => b.count - a.count || a.colorName.localeCompare(b.colorName));
    const best = qualifying[0];
    return {
      colorName: best.colorName,
      sharePct: Math.round(best.share * 100),
    };
  }

  // Fallback for flags whose only non-black/non-white emblem is < 10% of the image
  const chromatic = families.filter((f) => f.count > 0);
  if (chromatic.length > 0) {
    chromatic.sort((a, b) => b.count - a.count || a.colorName.localeCompare(b.colorName));
    const best = chromatic[0];
    return {
      colorName: best.colorName,
      sharePct: Math.round(best.share * 100),
    };
  }

  return null;
}

/**
 * Transforms RGBA pixel buffer to perceptual luminance grayscale, optionally
 * keeping a specific chromatic color family in original color or full color when gameOver.
 */
export function transformFlagPixels(
  rgba: Uint8ClampedArray,
  options: { revealColorFamily?: string | null; fullColor?: boolean } = {}
): Uint8ClampedArray {
  const output = new Uint8ClampedArray(rgba.length);

  if (options.fullColor) {
    output.set(rgba);
    return output;
  }

  const reveal = options.revealColorFamily;

  for (let i = 0; i < rgba.length; i += 4) {
    const r = rgba[i];
    const g = rgba[i + 1];
    const b = rgba[i + 2];
    const a = rgba[i + 3];

    if (reveal && classifyChromaticColor(r, g, b, a) === reveal) {
      output[i] = r;
      output[i + 1] = g;
      output[i + 2] = b;
      output[i + 3] = a;
    } else {
      const y = Math.round(0.299 * r + 0.587 * g + 0.114 * b);
      output[i] = y;
      output[i + 1] = y;
      output[i + 2] = y;
      output[i + 3] = a;
    }
  }

  return output;
}
