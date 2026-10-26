import { describe, expect, it } from 'bun:test';
import {
  classifyChromaticColor,
  rgbToHsl,
  selectColorHintFamily,
  transformFlagPixels,
} from '../src/lib/grayscaleFlag';

function makeBuffer(
  pixels: Array<[number, number, number, number]>
): Uint8ClampedArray {
  const buffer = new Uint8ClampedArray(pixels.length * 4);
  pixels.forEach(([r, g, b, a], idx) => {
    buffer[idx * 4] = r;
    buffer[idx * 4 + 1] = g;
    buffer[idx * 4 + 2] = b;
    buffer[idx * 4 + 3] = a;
  });
  return buffer;
}

function repeatPixel(
  pixel: [number, number, number, number],
  count: number
): Array<[number, number, number, number]> {
  return Array.from({ length: count }, () => [...pixel]);
}

describe('rgbToHsl', () => {
  it('converts pure primary RGB colors to HSL', () => {
    const [rRed, sRed, lRed] = rgbToHsl(255, 0, 0);
    expect(rRed).toBe(0);
    expect(sRed).toBe(1);
    expect(lRed).toBe(0.5);

    const [rGreen, sGreen, lGreen] = rgbToHsl(0, 255, 0);
    expect(rGreen).toBe(120);
    expect(sGreen).toBe(1);
    expect(lGreen).toBe(0.5);

    const [rBlue, sBlue, lBlue] = rgbToHsl(0, 0, 255);
    expect(rBlue).toBe(240);
    expect(sBlue).toBe(1);
    expect(lBlue).toBe(0.5);
  });

  it('converts pure secondary RGB colors to HSL', () => {
    const [rYellow, sYellow, lYellow] = rgbToHsl(255, 255, 0);
    expect(rYellow).toBe(60);
    expect(sYellow).toBe(1);
    expect(lYellow).toBe(0.5);

    const [rCyan, sCyan, lCyan] = rgbToHsl(0, 255, 255);
    expect(rCyan).toBe(180);
    expect(sCyan).toBe(1);
    expect(lCyan).toBe(0.5);

    const [rMagenta, sMagenta, lMagenta] = rgbToHsl(255, 0, 255);
    expect(rMagenta).toBe(300);
    expect(sMagenta).toBe(1);
    expect(lMagenta).toBe(0.5);
  });

  it('converts achromatic colors (black, white, grey) to HSL', () => {
    const [hBlack, sBlack, lBlack] = rgbToHsl(0, 0, 0);
    expect(hBlack).toBe(0);
    expect(sBlack).toBe(0);
    expect(lBlack).toBe(0);

    const [hWhite, sWhite, lWhite] = rgbToHsl(255, 255, 255);
    expect(hWhite).toBe(0);
    expect(sWhite).toBe(0);
    expect(lWhite).toBe(1);

    const [hGrey, sGrey, lGrey] = rgbToHsl(128, 128, 128);
    expect(hGrey).toBe(0);
    expect(sGrey).toBe(0);
    expect(Math.abs(lGrey - 128 / 255)).toBeLessThan(0.001);
  });
});

describe('classifyChromaticColor', () => {
  it('returns null for black, white, and grey', () => {
    expect(classifyChromaticColor(0, 0, 0)).toBeNull();
    expect(classifyChromaticColor(255, 255, 255)).toBeNull();
    expect(classifyChromaticColor(128, 128, 128)).toBeNull();

    // Near black (l <= 0.12)
    expect(classifyChromaticColor(20, 20, 20)).toBeNull();
    // Near white (l >= 0.90)
    expect(classifyChromaticColor(245, 245, 245)).toBeNull();
    // Achromatic grey with low saturation (s < 0.18)
    expect(classifyChromaticColor(135, 130, 125)).toBeNull();
  });

  it('returns null for low-alpha pixels (a < 128)', () => {
    expect(classifyChromaticColor(0, 0, 255, 0)).toBeNull();
    expect(classifyChromaticColor(0, 0, 255, 100)).toBeNull();
    expect(classifyChromaticColor(0, 0, 255, 127)).toBeNull();
    expect(classifyChromaticColor(0, 0, 255, 128)).toBe('Blue');
  });

  it('maps hues into chromatic color families', () => {
    expect(classifyChromaticColor(255, 0, 0)).toBe('Red'); // h=0
    expect(classifyChromaticColor(220, 20, 60)).toBe('Red'); // Crimson h≈348
    expect(classifyChromaticColor(255, 128, 0)).toBe('Orange'); // h≈30
    expect(classifyChromaticColor(255, 215, 0)).toBe('Yellow'); // Gold h≈51
    expect(classifyChromaticColor(0, 180, 50)).toBe('Green'); // h≈137
    expect(classifyChromaticColor(0, 200, 255)).toBe('Light Blue'); // Sky h≈193
    expect(classifyChromaticColor(0, 50, 220)).toBe('Blue'); // h≈226
    expect(classifyChromaticColor(140, 40, 200)).toBe('Purple'); // h≈278
  });
});

describe('selectColorHintFamily', () => {
  it('excludes black, white, and grey even when they occupy 80% of the image', () => {
    // 80% white, 20% blue
    const whitePixels = repeatPixel([255, 255, 255, 255], 80);
    const bluePixels = repeatPixel([0, 0, 255, 255], 20);
    const buffer1 = makeBuffer([...whitePixels, ...bluePixels]);

    const result1 = selectColorHintFamily(buffer1, 0.10);
    expect(result1).not.toBeNull();
    expect(result1?.colorName).toBe('Blue');
    expect(result1?.sharePct).toBe(20);

    // 80% black, 20% red
    const blackPixels = repeatPixel([0, 0, 0, 255], 80);
    const redPixels = repeatPixel([255, 0, 0, 255], 20);
    const buffer2 = makeBuffer([...blackPixels, ...redPixels]);

    const result2 = selectColorHintFamily(buffer2, 0.10);
    expect(result2?.colorName).toBe('Red');
    expect(result2?.sharePct).toBe(20);

    // 80% grey, 20% green
    const greyPixels = repeatPixel([128, 128, 128, 255], 80);
    const greenPixels = repeatPixel([0, 255, 0, 255], 20);
    const buffer3 = makeBuffer([...greyPixels, ...greenPixels]);

    const result3 = selectColorHintFamily(buffer3, 0.10);
    expect(result3?.colorName).toBe('Green');
    expect(result3?.sharePct).toBe(20);
  });

  it('skips chromatic color occupying < 10% in favor of chromatic color occupying >= 10%', () => {
    // 60% white (achromatic), 5% yellow (<10%), 35% blue (>=10%)
    const whitePixels = repeatPixel([255, 255, 255, 255], 60);
    const yellowPixels = repeatPixel([255, 255, 0, 255], 5);
    const bluePixels = repeatPixel([0, 0, 255, 255], 35);
    const buffer = makeBuffer([...whitePixels, ...yellowPixels, ...bluePixels]);

    const result = selectColorHintFamily(buffer, 0.10);
    expect(result).not.toBeNull();
    expect(result?.colorName).toBe('Blue');
    expect(result?.sharePct).toBe(35);
  });

  it('falls back to largest chromatic family when no chromatic family reaches 10%', () => {
    // 95% white, 3% red, 2% yellow (e.g. small central emblem on white field)
    const whitePixels = repeatPixel([255, 255, 255, 255], 95);
    const redPixels = repeatPixel([255, 0, 0, 255], 3);
    const yellowPixels = repeatPixel([255, 255, 0, 255], 2);
    const buffer = makeBuffer([...whitePixels, ...redPixels, ...yellowPixels]);

    const result = selectColorHintFamily(buffer, 0.10);
    expect(result).not.toBeNull();
    expect(result?.colorName).toBe('Red');
    expect(result?.sharePct).toBe(3);
  });

  it('returns null when flag has only black and white with no chromatic pixels', () => {
    const whitePixels = repeatPixel([255, 255, 255, 255], 50);
    const blackPixels = repeatPixel([0, 0, 0, 255], 50);
    const buffer = makeBuffer([...whitePixels, ...blackPixels]);

    const result = selectColorHintFamily(buffer, 0.10);
    expect(result).toBeNull();
  });

  it('ignores fully transparent pixels', () => {
    const transparentPixels = repeatPixel([255, 0, 0, 0], 100);
    const buffer = makeBuffer(transparentPixels);

    const result = selectColorHintFamily(buffer, 0.10);
    expect(result).toBeNull();
  });

  it('tie-breaks alphabetically when multiple chromatic families have equal counts >= 10%', () => {
    // 20% Blue, 20% Green, 60% White
    const whitePixels = repeatPixel([255, 255, 255, 255], 60);
    const bluePixels = repeatPixel([0, 0, 255, 255], 20);
    const greenPixels = repeatPixel([0, 255, 0, 255], 20);
    const buffer = makeBuffer([...whitePixels, ...greenPixels, ...bluePixels]);

    const result = selectColorHintFamily(buffer, 0.10);
    // 'Blue' precedes 'Green' alphabetically
    expect(result?.colorName).toBe('Blue');
    expect(result?.sharePct).toBe(20);
  });
});

describe('transformFlagPixels', () => {
  it('converts all pixels to luminance grayscale when revealColorFamily is null', () => {
    const pixels: Array<[number, number, number, number]> = [
      [255, 0, 0, 255], // Red
      [0, 255, 0, 255], // Green
      [0, 0, 255, 255], // Blue
      [255, 255, 255, 255], // White
      [0, 0, 0, 255], // Black
    ];
    const buffer = makeBuffer(pixels);
    const transformed = transformFlagPixels(buffer, { revealColorFamily: null });

    for (let i = 0; i < transformed.length; i += 4) {
      const r = transformed[i];
      const g = transformed[i + 1];
      const b = transformed[i + 2];
      expect(r).toBe(g);
      expect(g).toBe(b);
    }

    // Perceptual luminance check:
    // Red: 0.299 * 255 = 76.245 -> 76
    expect(transformed[0]).toBe(76);
    expect(transformed[1]).toBe(76);
    expect(transformed[2]).toBe(76);

    // Green: 0.587 * 255 = 149.685 -> 150
    expect(transformed[4]).toBe(150);
    expect(transformed[5]).toBe(150);
    expect(transformed[6]).toBe(150);

    // Blue: 0.114 * 255 = 29.07 -> 29
    expect(transformed[8]).toBe(29);
    expect(transformed[9]).toBe(29);
    expect(transformed[10]).toBe(29);

    // White: 255
    expect(transformed[12]).toBe(255);
    expect(transformed[13]).toBe(255);
    expect(transformed[14]).toBe(255);

    // Black: 0
    expect(transformed[16]).toBe(0);
    expect(transformed[17]).toBe(0);
    expect(transformed[18]).toBe(0);
  });

  it('preserves exact (r, g, b) of blue pixels while converting red, yellow, and others to grayscale', () => {
    const pixels: Array<[number, number, number, number]> = [
      [0, 0, 255, 255], // Blue
      [255, 0, 0, 255], // Red
      [255, 255, 0, 255], // Yellow
      [255, 255, 255, 255], // White
    ];
    const buffer = makeBuffer(pixels);
    const transformed = transformFlagPixels(buffer, { revealColorFamily: 'Blue' });

    // Blue pixel preserved verbatim
    expect(transformed[0]).toBe(0);
    expect(transformed[1]).toBe(0);
    expect(transformed[2]).toBe(255);
    expect(transformed[3]).toBe(255);

    // Red pixel converted to grayscale
    expect(transformed[4]).toBe(76);
    expect(transformed[5]).toBe(76);
    expect(transformed[6]).toBe(76);
    expect(transformed[7]).toBe(255);

    // Yellow pixel converted to grayscale: 0.299 * 255 + 0.587 * 255 = 225.93 -> 226
    expect(transformed[8]).toBe(226);
    expect(transformed[9]).toBe(226);
    expect(transformed[10]).toBe(226);
    expect(transformed[11]).toBe(255);

    // White pixel converted to grayscale: 255
    expect(transformed[12]).toBe(255);
    expect(transformed[13]).toBe(255);
    expect(transformed[14]).toBe(255);
    expect(transformed[15]).toBe(255);
  });

  it('returns an unchanged copy when fullColor is true', () => {
    const pixels: Array<[number, number, number, number]> = [
      [255, 0, 0, 255],
      [0, 255, 0, 255],
      [0, 0, 255, 255],
    ];
    const buffer = makeBuffer(pixels);
    const transformed = transformFlagPixels(buffer, { fullColor: true });

    expect(transformed).not.toBe(buffer); // New array
    expect(Array.from(transformed)).toEqual(Array.from(buffer)); // Equal content
  });

  it('preserves alpha channel across all modes', () => {
    const pixels: Array<[number, number, number, number]> = [
      [255, 0, 0, 180],
      [0, 0, 255, 210],
    ];
    const buffer = makeBuffer(pixels);

    const grayTransformed = transformFlagPixels(buffer, { revealColorFamily: null });
    expect(grayTransformed[3]).toBe(180);
    expect(grayTransformed[7]).toBe(210);

    const blueRevealed = transformFlagPixels(buffer, { revealColorFamily: 'Blue' });
    expect(blueRevealed[3]).toBe(180);
    expect(blueRevealed[7]).toBe(210);
  });
});
