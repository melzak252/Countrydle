import { createElement } from 'react';
import { describe, expect, test } from 'bun:test';
import { renderToStaticMarkup } from 'react-dom/server';
import type { Feature } from 'geojson';
import MapLoading from '../src/components/MapLoading';
import { getCountryFeatureStyle, MAP_THEME } from '../src/lib/mapTheme';

const poland: Feature = {
  type: 'Feature',
  properties: { SOVEREIGNT: 'Poland' },
  geometry: null,
};

const eligible = new Set(['POLAND']);

function style(marking?: 'green' | 'red', correctName?: string, isEligible = true) {
  return getCountryFeatureStyle(
    poland,
    isEligible ? eligible : new Set(),
    marking ? { POLAND: marking } : {},
    correctName,
  );
}

describe('antique map theme', () => {
  test('uses distinct styles for ordinary, candidate, eliminated, correct, and ineligible countries', () => {
    const ordinary = style();
    const candidate = style('green');
    const eliminated = style('red');
    const correct = style(undefined, 'Poland');
    const ineligible = style(undefined, undefined, false);

    expect(ordinary.fillColor).toBe(MAP_THEME.countries.available.fillColor);
    expect(candidate.fillColor).toBe(MAP_THEME.countries.markers.green.fillColor);
    expect(eliminated.fillColor).toBe(MAP_THEME.countries.markers.red.fillColor);
    expect(correct.fillColor).toBe(MAP_THEME.countries.correct.fillColor);
    expect(ineligible.fillColor).toBe(MAP_THEME.countries.unavailable.fillColor);
    expect(new Set([
      ordinary.fillColor,
      candidate.fillColor,
      eliminated.fillColor,
      correct.fillColor,
      ineligible.fillColor,
    ]).size).toBe(5);
    expect(correct.weight).toBeGreaterThan(candidate.weight);
  });
});
test('map loading frame uses the palette and keeps retry keyboard focus visible', () => {
  const html = renderToStaticMarkup(createElement(MapLoading, {
    className: 'h-80',
    error: true,
    onRetry: () => {},
  }));

  expect(html).toContain('bg-[var(--map-ocean)]');
  expect(html).toContain('focus-visible:outline-[var(--map-control-focus)]');
  expect(html).toContain('role="alert"');
});
