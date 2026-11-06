import { expect, spyOn, test } from 'bun:test';
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { MemoryRouter } from 'react-router-dom';
import { Window as TestWindow } from 'happy-dom';
import PowiatCoatsQuizPage from '../src/pages/PowiatCoatsQuizPage';
import { coatsQuizService, countyFlagsService, countyFlagsQuizService } from '../src/services/api';
import type { CountyFlagCatalogEntry } from '../src/lib/countyFlagCatalog';

test('flag quiz retries an unavailable catalog and uses only verified entries', async () => {
  const dom = new TestWindow({ url: 'http://localhost/quiz-flag-powiatow' });
  const globals: Record<string, unknown> = { window: dom, document: dom.document, navigator: dom.navigator, HTMLElement: dom.HTMLElement, Element: dom.Element, Node: dom.Node, IS_REACT_ACT_ENVIRONMENT: true };
  const previous = new Map<string, PropertyDescriptor | undefined>();
  for (const [name, value] of Object.entries(globals)) {
    previous.set(name, Object.getOwnPropertyDescriptor(globalThis, name));
    Object.defineProperty(globalThis, name, { configurable: true, writable: true, value });
  }
  const catalog = spyOn(countyFlagsService, 'getCatalog');
  catalog.mockRejectedValueOnce(new Error('offline'));
  catalog.mockResolvedValueOnce([{ id: 1, name: 'Biała Podlaska', voivodeship: 'lubelskie', is_city_county: true, flag_asset_url: '/powiatdle/flags/assets/1', source_attribution: { author: 'Example Artist', license: 'CC BY-SA 4.0', source_url: 'https://commons.wikimedia.org/wiki/File:Example.svg', license_url: 'https://creativecommons.org/licenses/by-sa/4.0/', description: 'Namespace added' } }]);
  const stats = spyOn(countyFlagsQuizService, 'stats').mockResolvedValue({ finished_runs: 0, tracking_started_at: null, coats: [] });
  const coatStats = spyOn(coatsQuizService, 'stats').mockResolvedValue({ finished_runs: 0, tracking_started_at: null, coats: [] });
  const start = spyOn(countyFlagsQuizService, 'start').mockRejectedValue(new Error('offline'));
  const container = dom.document.createElement('div');
  dom.document.body.appendChild(container);
  const root = createRoot(container as unknown as HTMLElement);
  try {
    await act(async () => { root.render(<MemoryRouter><PowiatCoatsQuizPage flags /></MemoryRouter>); });
    expect(container.querySelector('[role=alert]')?.textContent).toContain('unavailable');
    await act(async () => { Array.from(container.querySelectorAll('button')).find((button) => button.textContent === 'Retry')!.click(); });
    expect(container.textContent).toContain('Polish County Flags Quiz');
    expect(container.querySelectorAll('img[alt="County flag"]')).toHaveLength(1);
    expect(container.textContent).toContain('/1');
    await act(async () => { (container.querySelector('[aria-label="Fullscreen flag"]') as HTMLElement).click(); });
    const inspector = dom.document.querySelector('[aria-label="Flag preview"]')!;
    expect(inspector.textContent).toContain('Example Artist');
    expect(inspector.textContent).toContain('CC BY-SA 4.0');
    expect(inspector.textContent).toContain('Namespace added');
    expect(inspector.querySelector('a[href="https://commons.wikimedia.org/wiki/File:Example.svg"]')).not.toBeNull();
    expect(inspector.querySelector('a[href="https://creativecommons.org/licenses/by-sa/4.0/"]')).not.toBeNull();
    await act(async () => { (inspector.querySelector('[aria-label="Close"]') as HTMLButtonElement).click(); });
    await act(async () => { (container.querySelector('[aria-label="Start"]') as HTMLButtonElement).click(); });
    await act(async () => { (container.querySelector('[aria-label="Give Up"]') as HTMLButtonElement).click(); });
    expect(container.textContent).toContain('Your run could not be saved');
    await act(async () => { (container.querySelector('[aria-label="Reset quiz"]') as HTMLButtonElement).click(); });
    expect(container.textContent).not.toContain('Your run could not be saved');
    const deferred = Promise.withResolvers<{ run_id: string }>();
    start.mockImplementationOnce(() => deferred.promise);
    await act(async () => { (container.querySelector('[aria-label="Start"]') as HTMLButtonElement).click(); });
    await act(async () => { (container.querySelector('[aria-label="Give Up"]') as HTMLButtonElement).click(); });
    await act(async () => { (container.querySelector('[aria-label="Reset quiz"]') as HTMLButtonElement).click(); });
    await act(async () => { deferred.reject(new Error('late failure')); });
    expect(container.textContent).not.toContain('Your run could not be saved');
    await act(async () => { root.render(<MemoryRouter><PowiatCoatsQuizPage /></MemoryRouter>); });
    expect(container.querySelectorAll('img[alt="Coat of arms"]')).toHaveLength(380);
    const pending = Promise.withResolvers<CountyFlagCatalogEntry[]>();
    catalog.mockImplementationOnce(() => pending.promise);
    await act(async () => { root.render(<MemoryRouter><PowiatCoatsQuizPage flags /></MemoryRouter>); });
    expect(container.textContent).toContain('Loading verified county flags');
    expect(container.querySelectorAll('img')).toHaveLength(0);
    await act(async () => { pending.resolve([{ id: 1, name: 'Biała Podlaska', voivodeship: 'lubelskie', is_city_county: true, flag_asset_url: '/powiatdle/flags/assets/1' }]); });
    expect(container.querySelectorAll('img[alt="County flag"]')).toHaveLength(1);
    await act(async () => { root.render(<MemoryRouter><PowiatCoatsQuizPage /></MemoryRouter>); });
    expect(container.querySelectorAll('img[alt="Coat of arms"]')).toHaveLength(380);
    const lateCatalog = Promise.withResolvers<CountyFlagCatalogEntry[]>();
    catalog.mockImplementationOnce(() => lateCatalog.promise);
    await act(async () => { root.render(<MemoryRouter><PowiatCoatsQuizPage flags /></MemoryRouter>); });
    await act(async () => { root.render(<MemoryRouter><PowiatCoatsQuizPage /></MemoryRouter>); });
    await act(async () => { lateCatalog.resolve([{ id: 1, name: 'Biała Podlaska', voivodeship: 'lubelskie', is_city_county: true, flag_asset_url: '/powiatdle/flags/assets/1' }]); });
    expect(container.querySelectorAll('img[alt="Coat of arms"]')).toHaveLength(380);
  } finally {
    await act(async () => root.unmount());
    catalog.mockRestore(); stats.mockRestore(); coatStats.mockRestore(); start.mockRestore();
    await dom.happyDOM.close();
    for (const [name, descriptor] of previous) {
      if (descriptor) Object.defineProperty(globalThis, name, descriptor);
      else Reflect.deleteProperty(globalThis, name);
    }
  }
});
