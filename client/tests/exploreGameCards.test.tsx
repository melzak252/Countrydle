import { afterAll, expect, mock, test } from 'bun:test';
import { act, createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createRoot } from 'react-dom/client';
import { MemoryRouter } from 'react-router-dom';
import { Window as TestWindow } from 'happy-dom';
import type { FeatureCollection } from 'geojson';

const sampleMap: FeatureCollection = {
  type: 'FeatureCollection',
  features: [
    {
      type: 'Feature',
      properties: { NAME: 'France', CONTINENT: 'Europe' },
      geometry: {
        type: 'MultiPolygon',
        coordinates: [
          [[[5, 40], [25, 40], [25, 50], [5, 50], [5, 40]]],
          [[[-65, 15], [-60, 15], [-60, 20], [-65, 20], [-65, 15]]],
        ],
      },
    },
    {
      type: 'Feature',
      properties: { NAME: 'Russia', CONTINENT: 'Europe' },
      geometry: {
        type: 'MultiPolygon',
        coordinates: [
          [[[20, 50], [24, 50], [24, 54], [20, 54], [20, 50]]],
          [[[100, 50], [110, 50], [110, 60], [100, 60], [100, 50]]],
        ],
      },
    },
    {
      type: 'Feature',
      properties: { NAME: 'China', CONTINENT: 'Asia' },
      geometry: { type: 'Polygon', coordinates: [[[60, 10], [80, 10], [80, 20], [60, 20], [60, 10]]] },
    },
    {
      type: 'Feature',
      properties: { NAME: 'Guam', CONTINENT: 'Oceania' },
      geometry: { type: 'Polygon', coordinates: [[[144, 13], [145, 13], [145, 14], [144, 14], [144, 13]]] },
    },
    {
      type: 'Feature',
      properties: { NAME: 'South Africa', CONTINENT: 'Africa' },
      geometry: {
        type: 'MultiPolygon',
        coordinates: [
          [[[16, -34], [32, -34], [32, -22], [16, -22], [16, -34]]],
          [[[37, -47], [38, -47], [38, -46], [37, -46], [37, -47]]],
        ],
      },
    },
    {
      type: 'Feature',
      properties: { NAME: 'United States', CONTINENT: 'North America' },
      geometry: { type: 'Polygon', coordinates: [[[-124, 25], [-66, 25], [-66, 49], [-124, 49], [-124, 25]]] },
    },
    {
      type: 'Feature',
      properties: { NAME: 'Argentina', CONTINENT: 'South America' },
      geometry: { type: 'Polygon', coordinates: [[[-70, -55], [-60, -55], [-60, -35], [-70, -35], [-70, -55]]] },
    },
    {
      type: 'Feature',
      properties: { NAME: 'American Samoa', CONTINENT: 'Oceania' },
      geometry: { type: 'Polygon', coordinates: [[[-170, -14], [-169, -14], [-169, -13], [-170, -13], [-170, -14]]] },
    },
    {
      type: 'Feature',
      properties: { CONTINENT: 'Seven seas (open ocean)' },
      geometry: { type: 'Polygon', coordinates: [[[150, -10], [151, -10], [151, -9], [150, -9], [150, -10]]] },
    },
    {
      type: 'Feature',
      properties: { NAME: 'Frame edge test polygon', CONTINENT: 'Europe' },
      geometry: { type: 'Polygon', coordinates: [[[60, 35], [100, 35], [100, 45], [60, 45], [60, 35]]] },
    },
  ],
};
const requestedMapUrls: string[] = [];
const availableRegionalGames = [
  { scope: 'voivodeships', flags: false },
  { scope: 'voivodeships', flags: true },
  { scope: 'london_boroughs', flags: false },
  { scope: 'england_counties', flags: false },
  { scope: 'england_counties', flags: true },
] as const;

mock.module('../src/hooks/useMapData', () => ({
  useMapData: (url: string) => {
    requestedMapUrls.push(url);
    return { data: sampleMap, error: false, retry: () => undefined };
  },
}));
mock.module('../src/components/AdSenseUnit', () => ({ default: () => null }));
mock.module('../src/advertising', () => ({ setPageEditorialEligibility: () => undefined }));
const configuredApiUrl = 'https://api.countrydle.test/api';
const londonCoatThumbnailUrl = '/regional-symbols/london_boroughs/coat/thumbnails/1?v=westminster-v1';
const londonCoatAssetUrl = '/regional-symbols/london_boroughs/coat/assets/1?v=westminster-v1';
mock.module('../src/services/api', () => ({
  exploreService: {},
  assetUrl: (url: string) => url.startsWith('/')
    ? `${configuredApiUrl.replace(/\/$/, '')}${url.replace(/^\/api(?=\/)/, '')}`
    : url,
  regionalSymbolGames: availableRegionalGames,
  regionalSymbolLabels: {
    voivodeships: 'Voivodeship',
    london_boroughs: 'London Borough',
    england_counties: 'English Ceremonial County',
  },
  regionalSymbolPath: (scope: string, flags: boolean) => `/regional-symbols/${scope}/${flags ? 'flag' : 'coat'}`,
  regionalSymbolsService: (scope: string, flags: boolean) => ({
    getCatalog: async () => {
      const mode = flags ? 'flag' : 'coat';
      const fullAssetUrl = scope === 'london_boroughs' && !flags
        ? londonCoatAssetUrl
        : `/regional-symbols/${scope}/${mode}/assets/1?v=westminster-v1`;
      const thumbnailAssetUrl = scope === 'england_counties' && flags
        ? undefined
        : scope === 'london_boroughs' && !flags
          ? londonCoatThumbnailUrl
          : `/regional-symbols/${scope}/${mode}/thumbnails/1?v=westminster-v1`;
      return [
        { id: 1, name: 'Westminster', voivodeship: 'London', flag_asset_url: fullAssetUrl, ...(thumbnailAssetUrl ? { thumbnail_asset_url: thumbnailAssetUrl } : {}) },
        { id: 2, name: 'Camden', voivodeship: 'London', flag_asset_url: `/regional-symbols/${scope}/${mode}/assets/2?v=camden-v1`, thumbnail_asset_url: `/regional-symbols/${scope}/${mode}/thumbnails/2?v=camden-v1` },
      ];
    },
  }),
}));

const dom = new TestWindow({ url: 'http://localhost/explore' });
Object.defineProperty(dom, '__COUNTRYDLE_PRERENDER__', { configurable: true, value: true });
const previousGlobals = new Map<string, PropertyDescriptor | undefined>();
for (const [name, value] of Object.entries({
  window: dom,
  document: dom.document,
  navigator: dom.navigator,
  localStorage: dom.localStorage,
  IS_REACT_ACT_ENVIRONMENT: true,
})) {
  previousGlobals.set(name, Object.getOwnPropertyDescriptor(globalThis, name));
  Object.defineProperty(globalThis, name, { configurable: true, writable: true, value });
}

// The page reads browser globals during module evaluation; install happy-dom before importing it.
const { default: ExplorePage } = await import('../src/pages/ExplorePage');
afterAll(async () => {
  await dom.happyDOM.close();
  for (const [name, descriptor] of previousGlobals) {
    if (descriptor) Object.defineProperty(globalThis, name, descriptor);
    else Reflect.deleteProperty(globalThis, name);
  }
});

function renderExplore() {
  requestedMapUrls.length = 0;
  const container = dom.document.createElement('div');
  container.innerHTML = renderToStaticMarkup(createElement(MemoryRouter, null, createElement(ExplorePage)));
  return container;
}
function pathBounds(path: string | null | undefined) {
  const points = [...(path ?? '').matchAll(/[ML](-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)/g)]
    .map((match) => [Number(match[1]), Number(match[2])] as const);
  const xs = points.map(([x]) => x);
  const ys = points.map(([, y]) => y);
  return {
    left: Math.min(...xs),
    top: Math.min(...ys),
    width: Math.max(...xs) - Math.min(...xs),
    height: Math.max(...ys) - Math.min(...ys),
  };
}

test('world and duel map artwork fits natural landscape frames without stretching', () => {
  const container = renderExplore();
  const worldMap = container.querySelector('a[href="/game"] svg[data-game-artwork="map"]');
  const worldBounds = pathBounds(worldMap?.querySelector('path')?.getAttribute('d'));
  expect(worldMap?.getAttribute('data-map-frame')).toBe('worldwide');
  expect(worldMap?.getAttribute('viewBox')).toBe('0 0 160 160');
  expect(worldMap?.getAttribute('preserveAspectRatio')).toBe('xMidYMid meet');
  expect(worldBounds.width / worldBounds.height).toBeCloseTo(2.1, 1);
  expect(worldBounds.left).toBeGreaterThanOrEqual(5);
  expect(worldBounds.top).toBeGreaterThanOrEqual(5);
  expect(worldBounds.left + worldBounds.width).toBeLessThanOrEqual(155);
  expect(worldBounds.top + worldBounds.height).toBeLessThanOrEqual(155);
  expect(worldBounds.left + worldBounds.width / 2).toBeCloseTo(80, 1);
  expect(worldBounds.top + worldBounds.height / 2).toBeCloseTo(80, 1);

  const duelMap = container.querySelector('a[aria-label="Play Friend duels"] svg[data-game-artwork="duel-map"]');
  const duelPanels = [...(duelMap?.querySelectorAll('path[data-map-panel]') ?? [])];
  expect(duelPanels).toHaveLength(2);
  for (const [index, panel] of duelPanels.entries()) {
    const bounds = pathBounds(panel.getAttribute('d'));
    expect(bounds.width).toBeGreaterThan(135);
    expect(bounds.width / bounds.height).toBeCloseTo(321 / 115, 1);
    expect(bounds.left + bounds.width / 2).toBeCloseTo(80, 1);
    expect(bounds.top + bounds.height / 2).toBeCloseTo(index === 0 ? 38 : 122, 1);
  }
});


test('featured game cards use distinct mode labels and the Countrydle title', () => {
  const container = renderExplore();
  const quickStart = container.querySelector('[aria-labelledby="quick-start-heading"]');
  const cards = [...(quickStart?.querySelectorAll('a') ?? [])];
  const expectedGames = [
    ['/game', 'Countrydle', 'Ask yes-or-no questions to identify a country or region.'],
    ['/border-hop', 'Border Hop · Countries', 'Type neighboring places to continue a border chain.'],
    ['/flagdle', 'Flagdle', 'Identify a flag or regional symbol from visual clues.'],
    ['/quiz-herbow', 'Coats of Arms Quiz', 'Answer a quiz about flags, heraldry, and regional symbols.'],
    ['/friends', 'Friend duels', 'Invite a friend to a geography duel.'],
    ['/powiat-map-quiz', 'Powiat Map Quiz', 'Click the current Powiat or State target on its map.'],
    ['/us-state-map-quiz', 'US State Map Quiz', 'Click the current Powiat or State target on its map.'],
  ] as const;

  expect(cards.map((card) => {
    const title = card.querySelector('[data-game-title]');
    const descriptor = card.querySelector('[data-game-descriptor]');
    expect(card.querySelectorAll('[data-game-title]')).toHaveLength(1);
    expect(card.querySelectorAll('[data-game-descriptor]')).toHaveLength(1);
    expect(title?.nextElementSibling).toBe(descriptor);
    expect(title?.parentElement?.children).toHaveLength(2);
    return [
      card.getAttribute('href'),
      title?.textContent?.trim(),
      descriptor?.textContent?.trim(),
    ];
  })).toEqual(expectedGames);

  const borderCard = cards.find((card) => card.getAttribute('href') === '/border-hop');
  const duelCard = cards.find((card) => card.getAttribute('href') === '/friends');
  expect(borderCard?.querySelector('[data-game-artwork]')?.getAttribute('data-game-artwork')).toBe('border-map');
  expect(duelCard?.querySelector('[data-game-artwork]')?.getAttribute('data-game-artwork')).toBe('duel-map');
});

test('game cards use square artwork without game-card icon glyphs', () => {
  const container = renderExplore();
  const quickStart = container.querySelector('[aria-labelledby="quick-start-heading"]');
  const cards = [...(quickStart?.querySelectorAll('a') ?? [])];
  const catalogCards = [...(container.querySelectorAll('#game-mode-results li a'))];
  const allCards = [...cards, ...catalogCards];

  expect(allCards.length).toBeGreaterThan(0);
  expect(allCards.every((card) => card.querySelector('[data-game-artwork]'))).toBe(true);
  expect(allCards.every((card) => card.querySelector('[data-game-artwork-frame]')?.classList.contains('aspect-square'))).toBe(true);
  expect(allCards.every((card) => card.querySelectorAll('svg:not([data-game-artwork])').length === 0)).toBe(true);
  expect(catalogCards.every((card) => card.classList.contains('flex-row') && card.classList.contains('text-left') && !card.classList.contains('text-center'))).toBe(true);
  expect(container.querySelector('img[data-game-artwork="coat"][src="/coats/1.png"]')).not.toBeNull();
  const fallbackCoat = container.querySelector('img[data-game-artwork="coat"][src="/coats/1.png"]');
  const fallbackCoatFrame = fallbackCoat?.parentElement;
  expect(Boolean(fallbackCoatFrame?.classList.contains('p-3'))).toBe(true);
  expect(Boolean(fallbackCoatFrame?.classList.contains('place-items-center'))).toBe(true);
  expect(Boolean(fallbackCoat?.classList.contains('max-h-full'))).toBe(true);
  expect(Boolean(fallbackCoat?.classList.contains('max-w-full'))).toBe(true);
  expect(Boolean(fallbackCoat?.classList.contains('object-center'))).toBe(true);
  expect(Boolean(fallbackCoat?.classList.contains('min-h-0'))).toBe(true);
  const flagdleCard = catalogCards.find((card) => card.getAttribute('href') === '/flagdle');
  const flagdleArtwork = flagdleCard?.querySelector('[data-game-artwork="flag-montage"]');
  const flagImages = [...(flagdleArtwork?.querySelectorAll('img') ?? [])];
  const flagSources = flagImages.map((image) => image.getAttribute('src'));
  expect(flagSources).toHaveLength(4);
  expect(flagSources.every((src) => /^https:\/\/flagcdn\.com\/w320\/[a-z]{2}\.png$/.test(src ?? ''))).toBe(true);
  expect(new Set(flagSources).size).toBe(4);
  expect(flagSources).not.toContain('https://flagcdn.com/w320/pl.png');
  expect(flagImages.every((image) => image.getAttribute('alt') === '')).toBe(true);
  expect(flagdleArtwork?.getAttribute('aria-hidden')).toBe('true');
  expect(flagdleCard?.querySelector('[data-game-artwork="map"]')).toBeNull();
  const shadesCard = catalogCards.find((card) => card.getAttribute('href') === '/flag-shades');
  const shadesArtwork = shadesCard?.querySelector('[data-game-artwork="flag-shades"]');
  const grayscaleFlags = [...(shadesArtwork?.querySelectorAll('img') ?? [])];
  expect(grayscaleFlags).toHaveLength(4);
  expect(grayscaleFlags.every((image) => image.classList.contains('grayscale'))).toBe(true);
  expect(grayscaleFlags.every((image) => image.getAttribute('alt') === '')).toBe(true);
  expect(shadesArtwork?.getAttribute('aria-hidden')).toBe('true');
  expect(shadesCard?.querySelector('[data-game-artwork="map"]')).toBeNull();
  const sampleCountyFlagUrl = `${configuredApiUrl}/powiatdle/flags/thumbnails/1?v=bed7cd48ef9547b227dd942429cee042ef10e7279d5cf367a3640857ab9770e3`;
  for (const route of ['/flagi-powiatow', '/quiz-flag-powiatow']) {
    const countyFlagCard = catalogCards.find((card) => card.getAttribute('href') === route);
    const countyFlag = countyFlagCard?.querySelector('img[data-game-artwork="flag"]');
    expect(countyFlag?.getAttribute('src')).toBe(sampleCountyFlagUrl);
    expect(countyFlag?.getAttribute('alt')).toBe('');
    expect(countyFlagCard?.querySelector('[data-game-artwork="map"]')).toBeNull();
  }
  const duelCard = cards.find((card) => card.getAttribute('aria-label') === 'Play Friend duels');
  const duelArt = duelCard?.querySelector('svg[data-game-artwork="duel-map"]');
  expect(duelArt?.querySelectorAll('path[data-map-panel]')).toHaveLength(2);
  expect(duelArt?.textContent).toContain('VS');
  expect(requestedMapUrls).toContain('/countries_50m.geojson');
  expect(requestedMapUrls).toContain('/powiaty-min.geojson');
  expect(requestedMapUrls).toContain('/us-states.geojson');
});

test('continent artwork filters outlying territories and keeps map geometry proportional', () => {
  const container = renderExplore();
  const regions = [
    { route: '/europe', frame: 'europe', parts: 3 },
    { route: '/asia', frame: 'asia', parts: 2 },
    { route: '/americas', frame: 'americas', parts: 2 },
    { route: '/africa', frame: 'africa', parts: 1 },
  ] as const;

  for (const region of regions) {
    const map = container.querySelector(`a[href="${region.route}"] svg[data-game-artwork="map"]`);
    expect(map?.getAttribute('data-map-frame')).toBe(region.frame);
    expect(map?.getAttribute('viewBox')).toBe('0 0 160 160');
    expect(map?.getAttribute('preserveAspectRatio')).toBe('xMidYMid meet');
    const path = map?.querySelector('path')?.getAttribute('d') ?? '';
    expect((path.match(/M/g) ?? []).length).toBe(region.parts);
  }

});
test('continent artwork clips projected map geometry to each regional frame', () => {
  const container = renderExplore();
  for (const route of ['/europe', '/asia', '/americas', '/africa']) {
    const path = container.querySelector(`a[href="${route}"] path`)?.getAttribute('d') ?? '';
    const points = [...path.matchAll(/[ML](-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)/g)]
      .map((match) => [Number(match[1]), Number(match[2])] as const);
    expect(points.length).toBeGreaterThan(0);
    expect(points.every(([x, y]) => x >= 5 && x <= 155 && y >= 5 && y <= 155)).toBe(true);
  }
});


test('continent artwork uses local natural proportions', () => {
  const container = renderExplore();
  const ringAspectRatio = (route: string) => {
    const path = container.querySelector(`a[href="${route}"] path`)?.getAttribute('d') ?? '';
    const points = [...path.split('Z')[0].matchAll(/[ML](-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)/g)]
      .map((match) => [Number(match[1]), Number(match[2])] as const);
    const xs = points.map(([x]) => x);
    const ys = points.map(([, y]) => y);
    return (Math.max(...xs) - Math.min(...xs)) / (Math.max(...ys) - Math.min(...ys));
  };

  expect(ringAspectRatio('/europe')).toBeCloseTo(1.12, 2);
  expect(ringAspectRatio('/asia')).toBeCloseTo(0.83, 2);
  expect(ringAspectRatio('/americas')).toBeCloseTo(2.35, 2);
});
test('the complete 31-mode catalog shows compact card copy by default', async () => {
  requestedMapUrls.length = 0;
  Object.defineProperty(dom, '__COUNTRYDLE_PRERENDER__', { configurable: true, value: false });
  const container = dom.document.createElement('div');
  dom.document.body.appendChild(container);
  const root = createRoot(container as unknown as HTMLElement);

  try {
    await act(async () => {
      root.render(createElement(MemoryRouter, null, createElement(ExplorePage)));
      await Promise.resolve();
      await Promise.resolve();
    });

    const cards = [...container.querySelectorAll('#game-mode-results li a')];
    const borderGroup = container.querySelector('#play-modes-typed-chain');
    const borderCard = borderGroup?.querySelector('li a');
    const countrydleGroup = container.querySelector('#play-modes-true-false');
    const playableModes = container.querySelector('#playable-modes');
    const dailyGroup = container.querySelector('#play-modes-daily');
    const fullQuizzesGroup = container.querySelector('#play-modes-quizzes');
    expect(cards).toHaveLength(31);
    expect(container.querySelector('button[aria-controls="game-mode-results"]')).toBeNull();
    expect(countrydleGroup?.querySelector('h3')?.textContent).toBe('True / False games');
    expect(Boolean(playableModes?.querySelector('#game-mode-search'))).toBe(false);
    expect(Boolean(playableModes?.querySelector('#game-format-filter-heading'))).toBe(false);
    expect(Boolean(playableModes?.querySelector('#game-region-filter-heading'))).toBe(false);
    expect(Boolean(playableModes?.querySelector('[aria-live="polite"]'))).toBe(false);
    expect(playableModes?.textContent).not.toContain('Clear filters');
    expect(playableModes?.textContent).not.toContain(' matches');
    expect(dailyGroup?.querySelector('h3')?.textContent).toBe('Daily games');
    expect(fullQuizzesGroup?.querySelector('h3')?.textContent).toBe('Full quizzes');
    expect(dailyGroup?.querySelector('p')?.textContent).toBe('Identify a flag or regional symbol from visual clues.');
    expect(fullQuizzesGroup?.querySelector('p')?.textContent).toBe('Answer a quiz about flags, heraldry, and regional symbols.');
    const cardPaths = cards.map((card) => card.getAttribute('href'));
    expect(new Set(cardPaths).size).toBe(31);
    const dailyPaths = [...(dailyGroup?.querySelectorAll('li a') ?? [])].map((card) => card.getAttribute('href'));
    const fullQuizPaths = [...(fullQuizzesGroup?.querySelectorAll('li a') ?? [])].map((card) => card.getAttribute('href'));
    expect(dailyPaths).toContain('/flagdle');
    expect(dailyPaths).not.toContain('/quiz-herbow');
    expect(fullQuizPaths).toContain('/quiz-herbow');
    expect(fullQuizPaths).toContain('/quiz-flag-powiatow');
    const atlasFacts = container.querySelector('section[aria-labelledby="atlas-facts-heading"]');
    expect(atlasFacts?.querySelector('nav[aria-label="Atlas fact collections"]')).not.toBeNull();
    const countrydleCard = container.querySelector('#play-modes-true-false li a[href="/game"]');
    expect(countrydleCard?.textContent?.match(/Countrydle/g) ?? []).toHaveLength(1);
    const title = countrydleCard?.querySelector('[data-game-title]');
    const descriptor = countrydleCard?.querySelector('[data-game-descriptor]');
    expect(title?.classList.contains('line-clamp-2')).toBe(true);
    expect(title?.nextElementSibling).toBe(descriptor);
    expect(descriptor?.classList.contains('text-sm')).toBe(true);
    expect(descriptor?.textContent?.trim().length).toBeGreaterThan(0);
    expect(descriptor?.textContent?.trim().length).toBeLessThan(100);
    expect(borderGroup?.textContent?.match(/Follow borders/g) ?? []).toHaveLength(1);
    expect(borderCard?.textContent?.match(/Follow borders/g) ?? []).toHaveLength(0);
    expect(cards.every((card) => card.querySelector('[data-game-artwork]'))).toBe(true);
    expect(cards.every((card) => card.querySelector('[data-game-artwork-frame]')?.classList.contains('aspect-square'))).toBe(true);
    expect(cards.every((card) => card.querySelectorAll('svg:not([data-game-artwork])').length === 0)).toBe(true);
    const { assetUrl } = await import('../src/services/api');
    const londonCoatCard = cards.find((card) => card.getAttribute('href') === '/regional-symbols/london_boroughs/coat');
    expect(londonCoatCard?.querySelector('img[data-game-artwork="coat"]')?.getAttribute('src')).toBe(`${configuredApiUrl}${londonCoatThumbnailUrl}`);
    const londonCoatImage = londonCoatCard?.querySelector('img[data-game-artwork="coat"]');
    expect(Boolean(londonCoatImage?.parentElement?.classList.contains('p-3'))).toBe(true);
    expect(Boolean(londonCoatImage?.classList.contains('max-h-full'))).toBe(true);
    expect(Boolean(londonCoatImage?.classList.contains('max-w-full'))).toBe(true);
    expect(Boolean(londonCoatImage?.classList.contains('object-center'))).toBe(true);
    const flagdleCard = cards.find((card) => card.getAttribute('href') === '/flagdle');
    const flagdleArtwork = flagdleCard?.querySelector('[data-game-artwork="flag-montage"]');
    expect([...flagdleArtwork?.querySelectorAll('img') ?? []].map((image) => image.getAttribute('src'))).toEqual([
      'https://flagcdn.com/w320/jp.png',
      'https://flagcdn.com/w320/br.png',
      'https://flagcdn.com/w320/za.png',
      'https://flagcdn.com/w320/se.png',
    ]);
    const regionalFlagCard = cards.find((card) => card.getAttribute('href') === '/regional-symbols/voivodeships/flag');
    expect(regionalFlagCard?.querySelector('img[data-game-artwork="flag"]')?.getAttribute('src')).toBe(`${configuredApiUrl}/regional-symbols/voivodeships/flag/thumbnails/1?v=westminster-v1`);
    expect(assetUrl(londonCoatThumbnailUrl)).toBe(`${configuredApiUrl}${londonCoatThumbnailUrl}`);
    const fallbackFlagCard = cards.find((card) => card.getAttribute('href') === '/regional-symbols/england_counties/flag');
    expect(fallbackFlagCard?.querySelector('img[data-game-artwork="flag"]')?.getAttribute('src')).toBe(`${configuredApiUrl}/regional-symbols/england_counties/flag/assets/1?v=westminster-v1`);
    expect(londonCoatCard?.querySelector('svg[data-game-artwork="map"]')).toBeNull();
    const visibleCopy = [...container.querySelectorAll('#game-mode-results a [title], [aria-labelledby="quick-start-heading"] a [title]')];
    expect(visibleCopy.length).toBeGreaterThan(0);
    expect(visibleCopy.every((copy) => !copy.classList.contains('truncate'))).toBe(true);
    for (const url of [
      '/countries_50m.geojson',
      '/europe.geojson',
      '/asia.geojson',
      '/africa.geojson',
      '/americas.geojson',
      '/powiaty-min.geojson',
      '/wojewodztwa.geojson',
      '/us-states.geojson',
    ]) {
      expect(requestedMapUrls).toContain(url);
    }
  } finally {
    await act(async () => root.unmount());
    Object.defineProperty(dom, '__COUNTRYDLE_PRERENDER__', { configurable: true, value: true });
    container.remove();
  }
});
