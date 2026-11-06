import { expect, spyOn, test } from 'bun:test';
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { MemoryRouter } from 'react-router-dom';
import { Window as TestWindow } from 'happy-dom';
import PowiatHeraldryPage from '../src/pages/PowiatHeraldryPage';
import { countyFlagsService, powiatHeraldryService } from '../src/services/api';
import { useAuthStore } from '../src/stores/authStore';
import type { PowiatHeraldryChallenge, PowiatHeraldryGuessResult } from '../src/types';

test('switching daily county modes isolates tokens and challenge state', async () => {
  const dom = new TestWindow({ url: 'http://localhost/herby-powiatow' });
  const globals: Record<string, unknown> = { window: dom, document: dom.document, navigator: dom.navigator, localStorage: dom.localStorage, HTMLElement: dom.HTMLElement, Element: dom.Element, Node: dom.Node, IS_REACT_ACT_ENVIRONMENT: true };
  const previous = new Map<string, PropertyDescriptor | undefined>();
  for (const [name, value] of Object.entries(globals)) {
    previous.set(name, Object.getOwnPropertyDescriptor(globalThis, name));
    Object.defineProperty(globalThis, name, { configurable: true, writable: true, value });
  }
  const date = new Date().toISOString().slice(0, 10);
  dom.localStorage.setItem(`powiat_heraldry_daily_token_${date}`, 'coat-token');
  dom.localStorage.setItem(`county_flags_daily_token_${date}`, 'flag-token');
  dom.localStorage.setItem('powiat_heraldry_guide_seen', 'true');
  dom.localStorage.setItem('county_flags_guide_seen', 'true');
  const auth = useAuthStore.getState();
  useAuthStore.setState({ isLoading: false, isAuthenticated: false });
  const guess = (name: string, id: number): PowiatHeraldryGuessResult => ({
    answer: true, guess: name, powiat_id: id, voivodeship: 'lubelskie',
    distance_km: 0, bearing_degrees: null, bearing_direction: null, bearing_arrow: null,
    same_voivodeship: true, guesses_made: 1, remaining_guesses: 7,
    is_game_over: true, won: true, points: 512, ranked: true,
  });
  const base: PowiatHeraldryChallenge = {
    seed: 'daily', is_daily: true, date, max_guesses: 8, hint_unlock_guesses: 5,
    token: 'coat-token', points: 512, ranked: true, coat_asset_url: '/coats/example',
    guesses: [guess('Coat County', 11)], is_game_over: true, won: true,
    target_powiat: { id: 11, name: 'Coat County', voivodeship: 'lubelskie' },
  };
  const flagResult: PowiatHeraldryChallenge = {
    ...base, token: 'flag-token', points: 927, max_guesses: 6,
    coat_asset_url: '/powiatdle/flags/example',
    guesses: [guess('Flag First', 12), guess('Flag County', 13)],
    target_powiat: { id: 13, name: 'Flag County', voivodeship: 'lubelskie' },
  };
  const coats = spyOn(powiatHeraldryService, 'getChallenge').mockResolvedValue(base);
  const flags = spyOn(countyFlagsService, 'getChallenge').mockResolvedValue(flagResult);
  const coatCounties = spyOn(powiatHeraldryService, 'getCounties').mockResolvedValue([]);
  const flagCounties = spyOn(countyFlagsService, 'getCounties').mockResolvedValue([]);
  const container = dom.document.createElement('div'); dom.document.body.appendChild(container);
  const root = createRoot(container as unknown as HTMLElement);
  try {
    await act(async () => { root.render(<MemoryRouter><PowiatHeraldryPage /></MemoryRouter>); });
    let history = container.querySelector('[aria-label="Guess history"]')?.textContent || '';
    expect(history).toContain('Coat County');
    expect(history).toContain('(1/8)');
    expect(container.querySelector('[aria-label="Game summary"]')?.textContent).toContain('512 points');
    await act(async () => { root.render(<MemoryRouter><PowiatHeraldryPage flags /></MemoryRouter>); });
    history = container.querySelector('[aria-label="Guess history"]')?.textContent || '';
    expect(history).toContain('Flag First');
    expect(history).toContain('Flag County');
    expect(history).toContain('(2/6)');
    expect(history).not.toContain('Coat County');
    expect(container.querySelector('[aria-label="Game summary"]')?.textContent).toContain('927 points');
    await act(async () => { root.render(<MemoryRouter><PowiatHeraldryPage /></MemoryRouter>); });
    history = container.querySelector('[aria-label="Guess history"]')?.textContent || '';
    expect(history).toContain('Coat County');
    expect(history).not.toContain('Flag County');
    expect(history).toContain('(1/8)');
    expect(container.querySelector('[aria-label="Game summary"]')?.textContent).toContain('512 points');
    expect(dom.localStorage.getItem(`powiat_heraldry_daily_token_${date}`)).toBe('coat-token');
    expect(dom.localStorage.getItem(`county_flags_daily_token_${date}`)).toBe('flag-token');
  } finally {
    await act(async () => root.unmount());
    coats.mockRestore(); flags.mockRestore(); coatCounties.mockRestore(); flagCounties.mockRestore();
    useAuthStore.setState(auth);
    await dom.happyDOM.close();
    for (const [name, descriptor] of previous) {
      if (descriptor) Object.defineProperty(globalThis, name, descriptor);
      else Reflect.deleteProperty(globalThis, name);
    }
  }
});
