import { expect, mock, test } from 'bun:test';
import { act, createElement, type ComponentType } from 'react';
import { createRoot } from 'react-dom/client';
import { Window as TestWindow } from 'happy-dom';
import { MemoryRouter } from 'react-router-dom';
import POWIAT_CATALOG from '../src/data/powiats_quiz_catalog.json';
import { normalizeMapRegionName } from '../src/lib/mapGameMode';

const powiatCatalog = POWIAT_CATALOG as Array<{ id: number; name: string; voivodeship: string; seat: string | null; registration_plates: string[] }>;
const powiatNames = powiatCatalog.slice(0, 12).map(({ name }) => name);
const stateNames = ['Alabama', 'Alaska', 'Arizona', 'Arkansas', 'California', 'Colorado', 'Connecticut', 'Delaware', 'Florida', 'Georgia', 'Hawaii', 'Idaho'];
const powiatEntities = powiatNames.map((nazwa, index) => ({ id: 700 + index, nazwa }));
const powiatMap = {
  type: 'FeatureCollection',
  features: powiatNames.map((name, index) => ({
    type: 'Feature',
    properties: { id: index + 1, nazwa: name },
    geometry: { type: 'Point', coordinates: [0, 0] },
  })),
};
const statesMap = {
  type: 'FeatureCollection',
  features: stateNames.map((name) => ({
    type: 'Feature',
    properties: { name },
    geometry: { type: 'Point', coordinates: [0, 0] },
  })),
};

type DailyAnswer = { round: number; target_name: string; guess_id: number; correct: boolean };
type DailyMapState = {
  date: string;
  round_count: number;
  expected_round: number;
  current_target: string | null;
  score: number;
  is_complete: boolean;
  answers: DailyAnswer[];
  last_answer: { round: number; guess_id: number; correct: boolean } | null;
};

function makeDailyState(overrides: Partial<DailyMapState> = {}): DailyMapState {
  return {
    date: '2026-06-01',
    round_count: 10,
    expected_round: 0,
    current_target: powiatNames[0],
    score: 0,
    is_complete: false,
    answers: [],
    last_answer: null,
    ...overrides,
  };
}

let activeDailyState = makeDailyState();
let apiCalls: Array<{ method: string; payload?: unknown }> = [];
let failHistory = false;
let failStats = false;
let claimStatus: number | null = null;
let testIsAuthenticated = false;
let testAuthIsLoading = false;
const historyResponse = {
  items: [{
    date: '2026-05-31',
    score: 8,
    round_count: 10,
    completed_at: '2026-05-31T12:00:00Z',
    answers: [],
  }],
  total: 1,
};
const statsResponse = {
  date: '2026-06-01',
  completed_count: 12,
  average_score: 6.5,
  score_distribution: { '5': 2, '6': 4, '8': 6 },
};

const mapQuizServiceMock = {
  getDaily: async () => {
    apiCalls.push({ method: 'getDaily' });
    return activeDailyState;
  },
  submitAnswer: async (payload: { guess_id: number; expected_round: number }) => {
    apiCalls.push({ method: 'submitAnswer', payload });
    const target = activeDailyState.current_target;
    const targetId = powiatEntities.find((powiat) => powiat.nazwa === target)?.id;
    const correct = payload.guess_id === targetId;
    const answer: DailyAnswer = {
      round: payload.expected_round,
      target_name: target ?? '',
      guess_id: payload.guess_id,
      correct,
    };
    const nextRound = activeDailyState.expected_round + 1;
    activeDailyState = {
      ...activeDailyState,
      expected_round: nextRound,
      current_target: powiatNames[nextRound] ?? null,
      score: activeDailyState.score + Number(correct),
      is_complete: nextRound === 10,
      answers: [...activeDailyState.answers, answer],
      last_answer: { round: answer.round, guess_id: answer.guess_id, correct },
    };
    return activeDailyState;
  },
  claimDaily: async () => {
    apiCalls.push({ method: 'claimDaily' });
    if (claimStatus !== null) throw { response: { status: claimStatus } };
    return activeDailyState;
  },
  getHistory: async () => {
    apiCalls.push({ method: 'getHistory' });
    if (failHistory) throw new Error('history unavailable');
    return historyResponse;
  },
  getDailyStats: async () => {
    apiCalls.push({ method: 'getDailyStats' });
    if (failStats) throw new Error('stats unavailable');
    return statsResponse;
  },
};

const stateFactDetails: Record<string, { neighboring_states?: string[]; water_access?: string[] }> = {
  Alabama: { neighboring_states: ['Georgia'] },
  Alaska: { water_access: ['Arctic Ocean', 'Pacific Ocean'] },
  Arizona: { neighboring_states: ['New Mexico'] },
  Arkansas: { neighboring_states: ['Missouri'] },
  California: { neighboring_states: ['Oregon'] },
  Colorado: { neighboring_states: ['Wyoming'] },
  Connecticut: { neighboring_states: ['New York'] },
  Delaware: { neighboring_states: ['Pennsylvania'] },
  Florida: { neighboring_states: ['Georgia'] },
  Georgia: { neighboring_states: ['Florida'] },
  Hawaii: { water_access: ['Pacific Ocean'] },
  Idaho: { neighboring_states: ['Washington'] },
};


type TestMapProps = {
  className?: string;
  interaction: { entityMarkings: Record<string, string> };
  visibleRegionNames?: readonly string[];
  regionHints?: Readonly<Record<string, string>>;
  activeHintName?: string | null;
  onPowiatClick?: (name: string) => void;
  onStateClick?: (name: string) => void;
};

function TestMap({
  className,
  interaction,
  visibleRegionNames = [],
  regionHints = {},
  activeHintName,
  onPowiatClick,
  onStateClick,
}: TestMapProps) {
  const names = onPowiatClick ? powiatNames : stateNames;
  const onRegionClick = onPowiatClick ?? onStateClick;
  return createElement(
    'div',
    { className, 'data-testid': 'map-canvas', 'data-markings': JSON.stringify(interaction.entityMarkings) },
    names.map((name) => {
      const hint = regionHints[normalizeMapRegionName(name).toUpperCase()];
      const isMarked = visibleRegionNames.includes(name.toUpperCase());
      return createElement(
        'button',
        {
          type: 'button',
          key: name,
          'data-map-region': name,
          'data-hint': hint,
          'aria-label': isMarked && hint ? `${name}. ${hint}` : name,
          onClick: () => onRegionClick?.(name),
        },
        name,
        activeHintName === name && hint
          ? createElement('span', { role: 'tooltip' }, `${name}: ${hint}`)
          : null,
      );
    }),
  );
}

mock.module('../src/hooks/useMapData', () => ({
  useMapData: (url: string) => ({
    data: url === '/powiaty-min.geojson' ? powiatMap : statesMap,
    error: false,
    retry: () => undefined,
  }),
}));
mock.module('../src/components/PowiatyMap', () => ({ ControlledPowiatyMap: TestMap }));
mock.module('../src/components/USStatesMap', () => ({ ControlledUSStatesMap: TestMap }));
mock.module('../src/services/api', () => ({
  exploreService: {
    getUSStateDetail: async (name: string) => stateFactDetails[name],
  },
  powiatService: {
    getPowiaty: async () => {
      apiCalls.push({ method: 'getPowiaty' });
      return powiatEntities;
    },
  },
  powiatMapQuizService: mapQuizServiceMock,
}));
mock.module('../src/stores/authStore', () => ({
  useAuthStore: (selector: (state: { isAuthenticated: boolean; isLoading: boolean }) => unknown) =>
    selector({ isAuthenticated: testIsAuthenticated, isLoading: testAuthIsLoading }),
}));

function setupDOM() {
  const dom = new TestWindow({ url: 'http://localhost/' });
  Object.defineProperty(dom.HTMLElement.prototype, 'attachEvent', { configurable: true, value: () => undefined });
  Object.defineProperty(dom.HTMLElement.prototype, 'detachEvent', { configurable: true, value: () => undefined });
  const previous = new Map<string, PropertyDescriptor | undefined>();
  for (const [name, value] of Object.entries({
    window: dom,
    document: dom.document,
    navigator: dom.navigator,
    localStorage: dom.localStorage,
    HTMLElement: dom.HTMLElement,
    Element: dom.Element,
    Node: dom.Node,
    IS_REACT_ACT_ENVIRONMENT: true,
  })) {
    previous.set(name, Object.getOwnPropertyDescriptor(globalThis, name));
    Object.defineProperty(globalThis, name, { configurable: true, writable: true, value });
  }
  const container = dom.document.createElement('div');
  dom.document.body.appendChild(container);
  const root = createRoot(container as unknown as HTMLElement);
  return {
    dom,
    container,
    root,
    async dispose() {
      await act(async () => root.unmount());
      await dom.happyDOM.close();
      for (const [name, descriptor] of previous) {
        if (descriptor) Object.defineProperty(globalThis, name, descriptor);
        else Reflect.deleteProperty(globalThis, name);
      }
    },
  };
}

async function renderQuiz(
  mode: 'powiaty' | 'us_states',
  options: {
    dailyState?: DailyMapState;
    authenticated?: boolean;
    claimStatus?: number | null;
    failHistory?: boolean;
    failStats?: boolean;
  } = {},
) {
  const previousRandom = Math.random;
  Math.random = () => 0;
  activeDailyState = options.dailyState ?? makeDailyState();
  apiCalls = [];
  failHistory = options.failHistory ?? false;
  failStats = options.failStats ?? false;
  claimStatus = options.claimStatus ?? null;
  testIsAuthenticated = options.authenticated ?? false;
  testAuthIsLoading = false;
  const view = setupDOM();
  try {
    // The map page imports Leaflet through its map components; install DOM before loading it.
    const { default: Page } = await import('../src/pages/MapChallengePage');
    const QuizPage = Page as ComponentType<{ mode: 'powiaty' | 'us_states' }>;
    await act(async () => {
      view.root.render(
        createElement(
          MemoryRouter,
          { initialEntries: [mode === 'powiaty' ? '/powiat-map-quiz' : '/us-state-map-quiz'] },
          createElement(QuizPage, { mode }),
        ),
      );
      await Promise.resolve();
      await Promise.resolve();
    });
    const dispose = view.dispose;
    view.dispose = async () => {
      await dispose();
      Math.random = previousRandom;
    };
    return view;
  } catch (error) {
    await view.dispose();
    Math.random = previousRandom;
    throw error;
  }
}

function readTarget(container: ParentNode): string | null {
  return container.querySelector('header h1')?.textContent?.trim() ?? null;
}

function readScore(container: ParentNode): string | null {
  const scoreLine = Array.from(container.querySelectorAll('p')).find((node) => node.textContent?.trim().startsWith('Score'));
  return scoreLine?.textContent?.trim() ?? null;
}

function findRegionButton(container: ParentNode, name: string): HTMLButtonElement {
  return container.querySelector(`[data-map-region="${name}"]`) as HTMLButtonElement;
}
function wait(ms: number): Promise<void> {
  const { promise, resolve } = Promise.withResolvers<void>();
  setTimeout(resolve, ms);
  return promise;
}

test('Powiat quiz restores the API run and progress instead of creating a fresh run', async () => {
  const dailyState = makeDailyState({
    expected_round: 2,
    current_target: powiatNames[2],
    score: 1,
    answers: [
      { round: 0, target_name: powiatNames[0], guess_id: powiatEntities[0].id, correct: true },
      { round: 1, target_name: powiatNames[1], guess_id: powiatEntities[2].id, correct: false },
    ],
  });
  const view = await renderQuiz('powiaty', { dailyState });
  try {
    expect(readTarget(view.container)).toBe(powiatNames[2]);
    expect(readScore(view.container)).toContain('Score 1 / 10 · Powiat 3 of 10');
    expect(JSON.parse(view.container.querySelector('[data-testid="map-canvas"]')?.getAttribute('data-markings') ?? '{}')).toMatchObject({
      [powiatNames[0].toUpperCase()]: 'green',
      [powiatNames[1].toUpperCase()]: 'red',
    });
    expect(apiCalls.some((call) => call.method === 'getDaily')).toBe(true);
    expect(apiCalls.some((call) => call.method === 'getPowiaty')).toBe(true);
  } finally {
    await view.dispose();
  }
});
test('Powiat map quiz has a centered target, right-side rules, and one compact full-screen HUD', async () => {
  const view = await renderQuiz('powiaty');
  try {
    const main = view.container.querySelector('main');
    const mapLayer = view.container.querySelector('section[aria-label="Clickable region map"]');
    const status = view.container.querySelector('header');
    const target = status?.querySelector('h1');
    const metrics = Array.from(status?.querySelectorAll('p') ?? []).find((node) =>
      node.textContent?.trim().startsWith('Score'),
    );
    const infoButton = status?.querySelector('button[aria-label="Map quiz rules"]');
    const mainClasses = Array.from(main?.classList ?? []);
    const statusClasses = Array.from(status?.classList ?? []);
    const hudText = status?.textContent?.replace(/\s+/g, ' ').trim() ?? '';

    expect(main?.className).toContain('h-full');
    expect(mainClasses.some((className) => className.startsWith('border'))).toBe(false);
    expect(mapLayer?.className).toContain('absolute inset-0');
    expect(status).not.toBeNull();
    expect(statusClasses).toContain('border');
    expect(statusClasses).toContain('bg-app-surface/95');
    expect(statusClasses).toContain('px-3');
    expect(statusClasses).toContain('py-2');
    expect(statusClasses.some((className) => className.startsWith('rounded'))).toBe(false);
    expect(statusClasses).toContain('md:grid-cols-[auto_minmax(0,1fr)_auto]');
    expect(target?.classList).toContain('text-center');
    expect(target?.textContent).toBeTruthy();
    expect(hudText).toContain('Powiat Map Quiz');
    expect(hudText).not.toContain('Find this');
    expect(hudText).not.toContain('Prompt');
    expect(hudText).toContain('Score 0 / 10 · Powiat 1 of 10');
    expect(metrics?.className).toContain('whitespace-nowrap');
    expect(infoButton).not.toBeNull();
    expect(infoButton?.parentElement?.className).toContain('justify-self-end');
    expect(view.container.querySelector('[aria-label="Map challenge mode"]')).toBeNull();

    await act(async () => (infoButton as HTMLButtonElement).click());
    const dialog = view.container.querySelector('[role="dialog"]');
    const rules = dialog?.textContent?.toLowerCase() ?? '';
    expect(dialog).not.toBeNull();
    expect(rules).toContain('10 powiats');
    expect(rules).toContain('00:00 utc');
    expect(rules).toContain('one point');
    expect(rules).toContain('red');
    expect(rules).toContain('history');
    expect(rules).toContain('performance');
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    const aggregate = dialog?.querySelector('[aria-label="Daily aggregate performance"]');
    const ownHistory = dialog?.querySelector('[aria-label="Your private score history"]');
    expect(aggregate?.textContent).toContain('12 completed');
    expect(aggregate?.textContent).toContain('6.5');
    expect(aggregate?.textContent).toContain('8: 6');
    expect(ownHistory?.textContent).toContain('2026-05-31');
    expect(ownHistory?.textContent).toContain('8 / 10');
    expect(dialog?.textContent?.toLowerCase()).not.toContain('leaderboard');
    expect(apiCalls.some((call) => call.method === 'getDailyStats')).toBe(true);
    expect(apiCalls.some((call) => call.method === 'getHistory')).toBe(true);
    await act(async () => (dialog?.querySelector('button[aria-label="Close map quiz rules"]') as HTMLButtonElement).click());
    expect(view.container.querySelector('[role="dialog"]')).toBeNull();
  } finally {
    await view.dispose();
  }
});

test('map answers reveal feedback briefly and automatically advance to the next round', async () => {
  const view = await renderQuiz('powiaty');
  try {
    const firstTarget = readTarget(view.container);
    expect(firstTarget).toBeTruthy();

    const wrongName = powiatNames.find((name) => name !== firstTarget)!;
    await act(async () => findRegionButton(view.container, wrongName).click());
    const submission = apiCalls.find((call) => call.method === 'submitAnswer');
    const submittedGuess = (submission?.payload as { guess_id: number } | undefined)?.guess_id;
    expect(submission?.payload).toEqual({
      guess_id: powiatEntities.find((powiat) => powiat.nazwa === wrongName)?.id,
      expected_round: 0,
    });
    expect(submittedGuess).not.toBe(powiatMap.features.find((feature) => feature.properties.nazwa === wrongName)?.properties.id);
    expect(submittedGuess).not.toBe(powiatCatalog.find((powiat) => powiat.name === wrongName)?.id);
    expect(view.container.textContent).toContain('Not quite. No point added');
    expect(readTarget(view.container)).toBe(firstTarget);
    expect(JSON.parse(view.container.querySelector('[data-testid="map-canvas"]')?.getAttribute('data-markings') ?? '{}')[firstTarget!.toUpperCase()]).toBe('red');
    await act(async () => wait(800));

    const secondTarget = readTarget(view.container);
    expect(secondTarget).not.toBe(firstTarget);
    expect(view.container.textContent).not.toContain('Not quite. No point added');
    expect(Array.from(view.container.querySelectorAll('button')).some((button) => /next/i.test(button.textContent ?? ''))).toBe(false);
    expect(readScore(view.container)).toContain('0');

    await act(async () => findRegionButton(view.container, secondTarget!).click());
    expect(view.container.textContent).toContain('Correct — one point added.');
    await act(async () => wait(800));
    expect(readTarget(view.container)).not.toBe(secondTarget);
    expect(readScore(view.container)).toContain('1');
  } finally {
    await view.dispose();
  }
});

test('authenticated entry claims a guest daily run before loading account-owned state', async () => {
  const view = await renderQuiz('powiaty', { authenticated: true, claimStatus: 404 });
  try {
    const methods = apiCalls.map((call) => call.method);
    expect(methods.indexOf('claimDaily')).toBeGreaterThanOrEqual(0);
    expect(methods.indexOf('claimDaily')).toBeLessThan(methods.indexOf('getDaily'));
    expect(readTarget(view.container)).toBe(powiatNames[0]);
  } finally {
    await view.dispose();
  }
});

test('auth-login claims before reloading and safely continues after a conflict', async () => {
  const view = await renderQuiz('powiaty', { claimStatus: 409 });
  try {
    apiCalls = [];
    await act(async () => {
      testIsAuthenticated = true;
      view.dom.dispatchEvent(new view.dom.Event('auth-login'));
      await Promise.resolve();
      await Promise.resolve();
    });
    const methods = apiCalls.map((call) => call.method);
    expect(methods.indexOf('claimDaily')).toBeGreaterThanOrEqual(0);
    expect(methods.indexOf('claimDaily')).toBeLessThan(methods.indexOf('getDaily'));
    expect(readTarget(view.container)).toBe(powiatNames[0]);
  } finally {
    await view.dispose();
  }
});

test('performance request errors do not block the Powiat daily game', async () => {
  const view = await renderQuiz('powiaty', { failHistory: true, failStats: true });
  try {
    const target = readTarget(view.container)!;
    const infoButton = view.container.querySelector('button[aria-label="Map quiz rules"]') as HTMLButtonElement | null;
    expect(infoButton).not.toBeNull();
    await act(async () => {
      infoButton?.click();
      await Promise.resolve();
      await Promise.resolve();
    });
    const dialog = view.container.querySelector('[role="dialog"]');
    expect(dialog?.textContent).toContain('Your history is temporarily unavailable');
    expect(dialog?.textContent).toContain('Aggregate performance is temporarily unavailable');
    expect(readTarget(view.container)).toBe(target);
    await act(async () => (dialog?.querySelector('button[aria-label="Close map quiz rules"]') as HTMLButtonElement).click());
    await act(async () => findRegionButton(view.container, target).click());
    expect(apiCalls.some((call) => call.method === 'submitAnswer')).toBe(true);
  } finally {
    await view.dispose();
  }
});

test('tapping a marked Powiat shows its catalog fact without answering the next round', async () => {
  const view = await renderQuiz('powiaty');
  try {
    const firstTarget = powiatNames[0];
    const firstFact = powiatCatalog.find((powiat) => powiat.name === firstTarget)!;
    expect(readTarget(view.container)).toBe(firstTarget);
    const wrongName = powiatNames.find((name) => name !== firstTarget)!;
    await act(async () => findRegionButton(view.container, wrongName).click());
    await act(async () => wait(800));
    const nextTarget = readTarget(view.container);

    await act(async () => findRegionButton(view.container, firstTarget).click());
    expect(readTarget(view.container)).toBe(nextTarget);
    expect(readScore(view.container)).toContain('0');
    const tooltip = view.container.querySelector('[role="tooltip"]');
    expect(tooltip?.textContent).toContain(firstFact.voivodeship);
    expect(tooltip?.textContent).toContain(firstFact.registration_plates[0]);
    expect(view.container.textContent).not.toContain('Not quite. No point added');
  } finally {
    await view.dispose();
  }
});
test('tapping a marked State shows its detail fact without answering the next round', async () => {
  const view = await renderQuiz('us_states');
  try {
    const firstTarget = readTarget(view.container)!;
    const targetFacts = stateFactDetails[firstTarget];
    expect(targetFacts).toBeDefined();
    const expectedFact = targetFacts.neighboring_states?.[0] ?? targetFacts.water_access?.[0];
    expect(expectedFact).toBeTruthy();
    const wrongName = stateNames.find((name) => name !== firstTarget)!;
    await act(async () => findRegionButton(view.container, wrongName).click());
    await act(async () => wait(800));
    const nextTarget = readTarget(view.container);

    await act(async () => findRegionButton(view.container, firstTarget).click());
    expect(readTarget(view.container)).toBe(nextTarget);
    expect(readScore(view.container)).toContain('0');
    const tooltip = view.container.querySelector('[role="tooltip"]');
    expect(tooltip).not.toBeNull();
    expect(tooltip?.textContent).toContain(expectedFact!);
    expect(view.container.textContent).not.toContain('Not quite. No point added');
  } finally {
    await view.dispose();
  }
});


test('US state quiz centers the target and remains a repeatable separate game', async () => {
  const view = await renderQuiz('us_states');
  try {
    const status = view.container.querySelector('header');
    const target = status?.querySelector('h1');
    expect(view.container.textContent).toContain('US State Map Quiz');
    expect(view.container.textContent).not.toContain('Find this');
    expect(view.container.textContent).not.toContain('Prompt');
    expect(view.container.textContent).toMatch(/State \d+ of 10/);
    expect(target?.classList).toContain('text-center');
    expect(status?.querySelector('button[aria-label="Map quiz rules"]')).not.toBeNull();
    expect(view.container.querySelector('[aria-label="Map challenge mode"]')).toBeNull();

    await act(async () => (status?.querySelector('button[aria-label="Map quiz rules"]') as HTMLButtonElement).click());
    const rules = view.container.querySelector('[role="dialog"]')?.textContent?.toLowerCase() ?? '';
    expect(rules).toContain('repeatable');
    expect(rules).toContain('start another run');
    expect(rules).not.toContain('utc');
  } finally {
    await view.dispose();
  }
});
