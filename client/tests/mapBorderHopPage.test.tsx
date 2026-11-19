import { expect, mock, test } from 'bun:test';
import { act, createElement } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { Window as TestWindow } from 'happy-dom';
import { MemoryRouter } from 'react-router-dom';

type Mode = 'powiaty' | 'us_states';
type VerifyPayload = { mode: Mode; start: string; target: string; path: string[] };
type TestMapProps = { className?: string; interaction: { entityMarkings: Record<string, string> } };
type TestView = {
  dom: TestWindow;
  container: HTMLDivElement;
  root: Root;
  dispose: () => Promise<void>;
};
function nextTurn() {
  const { promise, resolve } = Promise.withResolvers<void>();
  setTimeout(resolve, 0);
  return promise;
}
const challengeCalls: Mode[] = [];
const neighborCalls: Array<{ name: string; mode?: Mode }> = [];
const verificationCalls: VerifyPayload[] = [];
const exploreService = {
  async getBorderHopChallenge(params: { mode?: Mode }) {
    const mode = params.mode ?? 'powiaty';
    challengeCalls.push(mode);
    return {
      mode,
      start: 'Start',
      target: 'Target',
      connected: true,
      is_island: false,
      optimal_hops: 2,
      optimal_path: ['Start', 'Shortcut', 'Target'],
      message: null,
    };
  },
  async getBorderNeighbors(name: string, mode?: Mode) {
    neighborCalls.push({ name, mode });
    const neighbors: Record<string, string[]> = {
      Start: ['Shortcut', 'Detour'],
      Detour: ['Shortcut'],
      Shortcut: ['Target'],
      Target: [],
    };
    const list = neighbors[name] ?? [];
    return { name, neighbors: list, is_island: list.length === 0 };
  },
  async verifyBorderHop(payload: VerifyPayload) {
    verificationCalls.push(payload);
    const hops = payload.path.length - 1;
    return {
      valid: true,
      hops,
      optimal_hops: 2,
      is_optimal: hops === 2,
      rank: hops === 2 ? 'gold' as const : 'silver' as const,
      optimal_path: ['Start', 'Shortcut', 'Target'],
    };
  },
};

function TestMap({ className, interaction }: TestMapProps) {
  return createElement('div', {
    className,
    'data-testid': 'map-canvas',
    'data-markings': JSON.stringify(interaction.entityMarkings),
  });
}

mock.module('../src/services/api', () => ({ exploreService }));
mock.module('../src/components/PowiatyMap', () => ({ ControlledPowiatyMap: TestMap }));
mock.module('../src/components/USStatesMap', () => ({ ControlledUSStatesMap: TestMap }));

function setupDOM(): TestView {
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

async function renderBorderHop(mode: Mode): Promise<TestView> {
  challengeCalls.length = 0;
  neighborCalls.length = 0;
  verificationCalls.length = 0;
  const view = setupDOM();
  try {
    // Import after DOM setup because its map-component imports can initialize Leaflet.
    const { default: Page } = await import('../src/pages/MapBorderHopPage');
    await act(async () => {
      view.root.render(createElement(
        MemoryRouter,
        { initialEntries: [`/map-border-hop?mode=${mode}`] },
        createElement(Page),
      ));
      await nextTurn();
    });
    return view;
  } catch (error) {
    await view.dispose();
    throw error;
  }
}

function readMarkings(container: ParentNode): Record<string, string> {
  const map = container.querySelector('[data-testid="map-canvas"]') as HTMLElement;
  return JSON.parse(map.dataset.markings ?? '{}') as Record<string, string>;
}

async function submitGuess(view: TestView, value: string) {
  const input = view.container.querySelector('#next-region') as HTMLInputElement;
  input.focus();
  Object.getOwnPropertyDescriptor(view.dom.HTMLInputElement.prototype, 'value')!.set!.call(input, value);
  await act(async () => {
    input.dispatchEvent(new view.dom.Event('input', { bubbles: true }));
    input.dispatchEvent(new view.dom.KeyboardEvent('keyup', { bubbles: true, key: 'a' }));
  });
  await act(async () => {
    view.container.querySelector('form')!.dispatchEvent(
      new view.dom.Event('submit', { bubbles: true, cancelable: true }),
    );
    await nextTurn();
  });
}

test('map Border Hop is fullscreen, hides hints, and reveals a suboptimal route for both map modes', async () => {
  for (const mode of ['powiaty', 'us_states'] as const) {
    const view = await renderBorderHop(mode);
    try {
      const main = view.container.querySelector('main');
      const mapLayer = view.container.querySelector('section[aria-label="Border Hop route map"]');
      const map = view.container.querySelector('[data-testid="map-canvas"]') as HTMLElement;
      const statusBar = view.container.querySelector('header[aria-label="Border Hop status"]');
      const controls = view.container.querySelector('section[aria-label="Border Hop controls"]');
      expect(main?.classList.contains('h-full')).toBe(true);
      expect(mapLayer?.className).toContain('absolute inset-0');
      expect(map.className).toContain('h-full');
      expect(statusBar?.className).toContain('pointer-events-auto');
      expect(controls?.className).toContain('max-w-5xl');
      expect(controls?.className).toContain('bg-app-surface/95');
      expect(view.container.textContent?.toLowerCase()).not.toContain('hint');
      expect(challengeCalls).toEqual([mode]);
      expect(readMarkings(view.container)).toMatchObject({ START: 'green', TARGET: 'blue' });
      expect(view.container.textContent).toContain('Start');
      expect(view.container.textContent).toContain('Target');
      expect(view.container.querySelector('#next-region')).not.toBeNull();

      await submitGuess(view, 'Not a neighbor');
      expect(view.container.textContent).toContain('That region is not an unvisited neighbor');
      expect(readMarkings(view.container)).not.toHaveProperty('NOT A NEIGHBOR');

      await submitGuess(view, 'Detour');
      await submitGuess(view, 'Shortcut');
      await submitGuess(view, 'Target');

      expect(verificationCalls).toEqual([{
        mode,
        start: 'Start',
        target: 'Target',
        path: ['Start', 'Detour', 'Shortcut', 'Target'],
      }]);
      expect(readMarkings(view.container)).toMatchObject({
        START: 'green',
        DETOUR: 'orange',
        SHORTCUT: 'yellow',
        TARGET: 'blue',
      });
      expect(view.container.textContent?.toLowerCase()).not.toContain('hint');

      const resetButton = Array.from(view.container.querySelectorAll('button'))
        .find((button) => button.textContent?.trim() === 'Reset');
      expect(resetButton).toBeDefined();
      await act(async () => {
        resetButton!.click();
        await nextTurn();
      });
      await submitGuess(view, 'Shortcut');
      await submitGuess(view, 'Target');
      expect(verificationCalls).toHaveLength(2);
      expect(verificationCalls[1].path).toEqual(['Start', 'Shortcut', 'Target']);
      const optimalMarkings = readMarkings(view.container);
      expect(optimalMarkings).toMatchObject({
        START: 'green',
        SHORTCUT: 'orange',
        TARGET: 'blue',
      });
      expect(Object.values(optimalMarkings)).not.toContain('yellow');
    } finally {
      await view.dispose();
    }
  }
});

