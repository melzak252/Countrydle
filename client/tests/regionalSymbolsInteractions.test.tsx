import { expect, spyOn, test } from 'bun:test';
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { Window as TestWindow } from 'happy-dom';
import PowiatHeraldryPage from '../src/pages/PowiatHeraldryPage';
import PowiatCoatsQuizPage from '../src/pages/PowiatCoatsQuizPage';
import HomePage from '../src/pages/HomePage';
import { regionalSymbolGames } from '../src/services/api';
import { useGameCatalog } from '../src/lib/gameCatalog';
import { regionalSymbolsService } from '../src/services/api';
import { useAuthStore } from '../src/stores/authStore';
import type { PowiatHeraldryChallenge } from '../src/types';

function setup() {
  const dom = new TestWindow({ url: 'http://localhost/' });
  // React DOM can be imported before a DOM exists in Bun's test runner, in
  // which case its legacy input-event fallback listens for keyboard events.
  Object.defineProperty(dom.HTMLElement.prototype, 'attachEvent', { configurable: true, value: () => {} });
  Object.defineProperty(dom.HTMLElement.prototype, 'detachEvent', { configurable: true, value: () => {} });
  const previous = new Map<string, PropertyDescriptor | undefined>();
  for (const [name, value] of Object.entries({ window: dom, document: dom.document, navigator: dom.navigator, localStorage: dom.localStorage, HTMLElement: dom.HTMLElement, Element: dom.Element, Node: dom.Node, IS_REACT_ACT_ENVIRONMENT: true })) {
    previous.set(name, Object.getOwnPropertyDescriptor(globalThis, name));
    Object.defineProperty(globalThis, name, { configurable: true, writable: true, value });
  }
  const container = dom.document.createElement('div');
  dom.document.body.appendChild(container);
  const root = createRoot(container as unknown as HTMLElement);
  return { dom, container, root, async dispose() {
    await act(async () => root.unmount());
    await dom.happyDOM.close();
    for (const [name, descriptor] of previous) {
      if (descriptor) Object.defineProperty(globalThis, name, descriptor);
      else Reflect.deleteProperty(globalThis, name);
    }
  } };
}

function type(dom: TestWindow, input: HTMLInputElement, value: string) {
  input.focus();
  Object.getOwnPropertyDescriptor(dom.HTMLInputElement.prototype, 'value')!.set!.call(input, value);
  input.dispatchEvent(new dom.Event('input', { bubbles: true }));
  input.dispatchEvent(new dom.KeyboardEvent('keyup', { bubbles: true, key: 'a' }));
}

test('regional daily games isolate scope and symbol tokens and autocomplete all entities', async () => {
  const { dom, container, root, dispose } = setup();
  const date = new Date().toISOString().slice(0, 10);
  const boroughs = regionalSymbolsService('london_boroughs', false);
  const flags = regionalSymbolsService('london_boroughs', true);
  const counties = regionalSymbolsService('england_counties', false);
  const services = [boroughs, flags, counties];
  const keys = ['london_boroughs_coat', 'london_boroughs_flag', 'england_counties_coat'];
  const auth = useAuthStore.getState();
  useAuthStore.setState({ isLoading: false, isAuthenticated: false });
  const mocks = services.flatMap((service, index) => {
    dom.localStorage.setItem(`regional_symbols_${keys[index]}_daily_token_${date}`, `token-${index}`);
    dom.localStorage.setItem(`regional_symbols_${keys[index]}_guide_seen`, 'true');
    const challenge: PowiatHeraldryChallenge = { seed: 'daily', is_daily: true, date, max_guesses: 8, hint_unlock_guesses: 5, token: `token-${index}`, points: null, ranked: false, coat_asset_url: '/symbol.svg' };
    return [spyOn(service, 'getChallenge').mockResolvedValue(challenge), spyOn(service, 'getCounties').mockResolvedValue([{ id: 42, name: 'Greenwich', voivodeship: '', is_city_county: false, aliases: ['Royal Greenwich'] }])];
  });
  const catalogs = services.map((service) => spyOn(service, 'getCatalog').mockResolvedValue([{ id: 42, name: 'Greenwich', voivodeship: '', flag_asset_url: '/symbol.svg' }]));
  const countyStats = spyOn(counties.quiz, 'stats').mockResolvedValue({ finished_runs: 0, tracking_started_at: null, coats: [] });
  const submit = spyOn(boroughs, 'submitGuess').mockResolvedValue({ answer: false, guess: 'Greenwich', powiat_id: 42, voivodeship: '', distance_km: 10, bearing_degrees: 0, bearing_direction: 'N', bearing_arrow: '↑', same_voivodeship: false, guesses_made: 1, remaining_guesses: 7, is_game_over: false, won: false, points: null, ranked: false, token: 'updated' });
  function Location() {
    const location = useLocation();
    return <output data-testid="location">{location.pathname}</output>;
  }
  try {
    await act(async () => { root.render(<MemoryRouter><PowiatHeraldryPage scope="london_boroughs" /><Location /></MemoryRouter>); });
    expect(mocks[0]).toHaveBeenCalledWith({ token: 'token-0' });
    expect(container.textContent).not.toContain('Registration plate');
    expect(container.textContent).toContain('Identify the London borough');
    expect(container.textContent).toContain('Enter a London borough name');
    expect(container.querySelector('[aria-label="Geography data credit"]')?.textContent).toContain('Contains National Statistics data © Crown copyright and database right 2026');
    expect(container.querySelector('[aria-label="Geography data credit"] a')?.getAttribute('href')).toBe('https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/');
    const mobileQuiz = Array.from(container.querySelectorAll('a')).find((link) => link.className.includes('sm:hidden'))!;
    expect(mobileQuiz.textContent).toContain('All Symbols Quiz');
    await act(async () => { mobileQuiz.dispatchEvent(new dom.MouseEvent('click', { bubbles: true, cancelable: true, button: 0 })); });
    expect(container.querySelector('[data-testid="location"]')?.textContent).toBe('/regional-symbols/london_boroughs/coat/quiz');
    await act(async () => type(dom, container.querySelector('input') as HTMLInputElement, 'Royal Greenwich'));
    expect(container.querySelector('[role=option]')?.textContent).toContain('Greenwich');
    await act(async () => { (container.querySelector('[role=option]') as HTMLElement).click(); });
    await act(async () => { Array.from(container.querySelectorAll('button')).find((b) => b.textContent === 'Guess')!.click(); });
    expect(submit).toHaveBeenCalledWith({ token: 'token-0', guess: 'Greenwich', powiat_id: 42 });
    expect(dom.localStorage.getItem(`regional_symbols_london_boroughs_coat_daily_token_${date}`)).toBe('updated');
    await act(async () => { Array.from(container.querySelectorAll('button')).find((b) => b.textContent?.includes('Random Challenge'))!.click(); });
    expect(mocks[0]).toHaveBeenCalledWith({ seed: expect.stringMatching(/^challenge-/) });
    await act(async () => { root.render(<MemoryRouter><PowiatHeraldryPage scope="london_boroughs" flags /></MemoryRouter>); });
    expect(mocks[2]).toHaveBeenCalledWith({ token: 'token-1' });
    await act(async () => { root.render(<MemoryRouter><PowiatHeraldryPage scope="england_counties" /></MemoryRouter>); });
    expect(mocks[4]).toHaveBeenCalledWith({ token: 'token-2' });
    expect(container.querySelector('[aria-label="Geography data credit"]')?.textContent).toContain('OS Boundary-Line, October 2026');
    expect(container.textContent).toContain('English Ceremonial County Coats of Arms');
    expect(container.textContent).toContain('Enter an English ceremonial county name');
    expect(container.textContent).toContain('Council arms associated with these counties; not necessarily arms of the ceremonial county or a current authority.');
    await act(async () => { root.render(<MemoryRouter><PowiatCoatsQuizPage scope="england_counties" /></MemoryRouter>); });
    expect(container.textContent).toContain('Council arms associated with these counties; not necessarily arms of the ceremonial county or a current authority.');
  } finally {
    submit.mockRestore(); mocks.forEach((mock) => mock.mockRestore()); catalogs.forEach((mock) => mock.mockRestore()); countyStats.mockRestore(); useAuthStore.setState(auth); await dispose();
  }
});

test('regional quiz displays only eligible catalog entries, accepts aliases and finishes at its actual pool size', async () => {
  const { dom, container, root, dispose } = setup();
  const service = regionalSymbolsService('voivodeships', false);
  const catalog = spyOn(service, 'getCatalog').mockResolvedValue([
    { id: 1, name: 'Łódzkie', voivodeship: '', aliases: ['Lodz'], flag_asset_url: '/one.svg', source_attribution: { author: 'Artist', license: 'CC BY-SA 4.0', license_url: 'https://creativecommons.org/licenses/by-sa/4.0/', source_url: 'https://commons.wikimedia.org/wiki/File:Example.svg', description: 'Cropped and converted to SVG', context: 'Community design selected by local vote' } },
    { id: 2, name: 'Śląskie', voivodeship: '', flag_asset_url: '/two.svg' },
  ]);
  const stats = spyOn(service.quiz, 'stats').mockResolvedValue({ finished_runs: 0, tracking_started_at: null, coats: [] });
  const start = spyOn(service.quiz, 'start').mockResolvedValue({ run_id: 'run' });
  const finish = spyOn(service.quiz, 'finish').mockResolvedValue();
  try {
    await act(async () => { root.render(<MemoryRouter><PowiatCoatsQuizPage scope="voivodeships" /></MemoryRouter>); });
    expect(container.querySelectorAll('img[alt="Coat of arms"]')).toHaveLength(2);
    expect(container.querySelector('[aria-label="Geography data credit"]')?.textContent).toContain('GUGiK Geoportal, August 2025');
    expect(container.querySelector('[aria-label="Geography data credit"] a')?.getAttribute('href')).toBe('https://github.com/waszkiewiczja/GeoJSON-Polska-Wojewodztwa-Powiaty-Gminy');
    await act(async () => { (container.querySelector('[aria-label="Fullscreen coat of arms"]') as HTMLElement).click(); });
    const inspector = dom.document.querySelector('[aria-label="Coat of arms preview"]')!;
    expect(inspector.textContent).toContain('Author: Artist');
    expect(inspector.textContent).toContain('CC BY-SA 4.0');
    expect(inspector.textContent).toContain('Modification: Cropped and converted to SVG');
    expect(inspector.textContent).toContain('Context: Community design selected by local vote');
    expect(inspector.querySelector('a[href="https://commons.wikimedia.org/wiki/File:Example.svg"]')).not.toBeNull();
    expect(inspector.querySelector('a[href="https://creativecommons.org/licenses/by-sa/4.0/"]')).not.toBeNull();
    await act(async () => { (dom.document.querySelector('[aria-label="Close"]') as HTMLElement).click(); });
    const input = container.querySelector('input') as HTMLInputElement;
    await act(async () => type(dom, input, 'Lodz'));
    await act(async () => type(dom, input, 'Slaskie'));
    expect(container.textContent).toContain('Congratulations! You solved all 2');
    expect(finish).toHaveBeenCalledWith('run', expect.objectContaining({ status: 'completed', solves: expect.arrayContaining([expect.objectContaining({ powiat_ids: [1] }), expect.objectContaining({ powiat_ids: [2] })]) }));
  } finally {
    catalog.mockRestore(); stats.mockRestore(); start.mockRestore(); finish.mockRestore(); await dispose();
  }
});

test('the directory separates game styles and geographic areas', async () => {
  const { dom, container, root, dispose } = setup();
  Object.defineProperty(dom, '__COUNTRYDLE_PRERENDER__', { configurable: true, value: true });
  try {
    await act(async () => { root.render(<MemoryRouter><HomePage /></MemoryRouter>); });
    const country = container.querySelector('#maps a[href="/game"]')!;
    const europe = container.querySelector('#maps a[href="/europe"]')!;
    const flag = container.querySelector('#maps a[href="/flagdle"]')!;
    const asia = container.querySelector('#maps a[href="/asia"]')!;
    const poland = container.querySelector('#maps a[href="/powiaty"]')!;
    expect(europe.closest('section')).toBe(asia.closest('section'));
    expect(europe.closest('section')).not.toBe(poland.closest('section'));
    expect(country.closest('section')).not.toBe(europe.closest('section'));
    expect(country.closest('section[aria-labelledby^="games-"]')).not.toBe(flag.closest('section[aria-labelledby^="games-"]'));
  } finally {
    await dispose();
  }
});

test('the games menu exposes only catalogs with verified targets', async () => {
  const { container, root, dispose } = setup();
  const auth = useAuthStore.getState();
  useAuthStore.setState({ isLoading: true });
  const mocks = regionalSymbolGames.map(({ scope, flags }) => {
    const mock = spyOn(regionalSymbolsService(scope, flags), 'getCatalog');
    if (scope === 'england_counties' && flags) {
      mock.mockResolvedValue([{ id: 1, name: 'Cumbria', voivodeship: '', flag_asset_url: '/cumbria.svg' }, { id: 2, name: 'Devon', voivodeship: '', flag_asset_url: '/devon.svg' }]);
    } else {
      mock.mockRejectedValue(new Error('unavailable'));
    }
    return mock;
  });
  try {
    await act(async () => { root.render(<MemoryRouter><HomePage /></MemoryRouter>); });
    const daily = container.querySelector('#maps a[href="/regional-symbols/england_counties/flag"]');
    const quiz = container.querySelector('#maps a[href="/regional-symbols/england_counties/flag/quiz"]');
    const polish = container.querySelector('#maps a[href="/flagi-powiatow"]');
    expect(daily).not.toBeNull();
    expect(quiz).not.toBeNull();
    expect(daily?.closest('section')).not.toBe(polish?.closest('section'));
    expect(daily?.closest('section[aria-labelledby^="games-"]')).toBe(polish?.closest('section[aria-labelledby^="games-"]'));
    expect(container.querySelector('#maps a[href="/regional-symbols/london_boroughs/flag"]')).toBeNull();
    expect(container.querySelector('#maps a[href="/regional-symbols/voivodeships/coat"]')).toBeNull();
  } finally {
    mocks.forEach((mock) => mock.mockRestore()); useAuthStore.setState(auth); await dispose();
  }
});

test('desktop game chooser returns focus on Escape and closes when navigating', async () => {
  const { dom, container, root, dispose } = setup();
  Object.defineProperty(dom, '__COUNTRYDLE_PRERENDER__', { configurable: true, value: true });
  try {
    // Header's advertising dependency reads document at module load.
    const { default: Header } = await import('../src/components/Header');
    await act(async () => { root.render(<MemoryRouter><Header /></MemoryRouter>); });
    const nav = container.querySelector('nav[aria-label="Main navigation"]')!;
    const details = nav.querySelector('summary[aria-label="Choose a game"]')!.closest('details')!;
    const summary = details.querySelector('summary')!;
    details.open = true;
    summary.focus();
    await act(async () => { summary.dispatchEvent(new dom.KeyboardEvent('keydown', { bubbles: true, key: 'Escape' })); });
    expect(details.open).toBe(false);
    expect(dom.document.activeElement).toBe(summary);
    details.open = true;
    const link = details.querySelector('a[href="/flagdle"]')!;
    await act(async () => { link.dispatchEvent(new dom.MouseEvent('click', { bubbles: true, cancelable: true, button: 0 })); });
    expect(details.open).toBe(false);
  } finally {
    await dispose();
  }
});

test('English county flags explain community status and distinguish design context from modification', async () => {
  const { dom, container, root, dispose } = setup();
  const auth = useAuthStore.getState();
  useAuthStore.setState({ isLoading: false, isAuthenticated: false });
  const service = regionalSymbolsService('england_counties', true);
  const attribution = {
    context: 'Registered community flag', description: 'Colours adjusted',
    component_credits: [
      { title: 'First emblem', url: 'https://example.org/first', author: 'First artist', license: 'CC BY-SA 4.0', license_url: 'https://creativecommons.org/licenses/by-sa/4.0/' },
      { title: 'Second emblem', url: 'https://example.org/second', author: 'Second artist', license: 'CC BY 3.0', license_url: 'https://creativecommons.org/licenses/by/3.0/' },
    ],
  };
  const entries = [
    { id: 1, name: 'Cumbria', voivodeship: '', flag_asset_url: '/cumbria.svg', source_attribution: attribution },
    { id: 2, name: 'Devon', voivodeship: '', flag_asset_url: '/devon.svg' },
  ];
  const catalog = spyOn(service, 'getCatalog').mockResolvedValue(entries);
  const counties = spyOn(service, 'getCounties').mockResolvedValue([]);
  const challenge = spyOn(service, 'getChallenge').mockResolvedValue({
    seed: 'daily', is_daily: true, date: '2026-11-06', max_guesses: 8, hint_unlock_guesses: 5,
    token: 'token', points: null, ranked: false, coat_asset_url: '/symbol.svg', is_game_over: true,
    won: true, target_powiat: { id: 1, name: 'Cumbria', voivodeship: '' }, source_attribution: attribution,
  });
  const stats = spyOn(service.quiz, 'stats').mockResolvedValue({ finished_runs: 0, tracking_started_at: null, coats: [] });
  try {
    await act(async () => { root.render(<MemoryRouter><PowiatHeraldryPage scope="england_counties" flags /></MemoryRouter>); });
    expect(container.textContent).toContain('Community flags with historic and cultural associations to present-day ceremonial counties; historic boundaries may differ. These are not flags of modern ceremonial authority.');
    expect(container.textContent).toContain('Verified Flag');
    expect(container.textContent).toContain('Context: Registered community flag');
    expect(container.textContent).toContain('Modification: Colours adjusted');
    const resultCredits = container.querySelector('[aria-label="Game Results"] details') as HTMLDetailsElement;
    await act(async () => { (resultCredits.querySelector('summary') as HTMLElement).click(); });
    expect(resultCredits.open).toBe(true);
    expect(resultCredits.textContent).toContain('First artist');
    expect(resultCredits.textContent).toContain('Second artist');
    expect(resultCredits.querySelector('a[href="https://example.org/first"]')?.textContent).toBe('First emblem');
    expect(resultCredits.querySelector('a[href="https://example.org/second"]')?.textContent).toBe('Second emblem');
    expect(resultCredits.querySelector('a[href="https://creativecommons.org/licenses/by/3.0/"]')?.textContent).toBe('CC BY 3.0');
    await act(async () => { root.render(<MemoryRouter><PowiatCoatsQuizPage scope="england_counties" flags /></MemoryRouter>); });
    expect(container.textContent).toContain('Community flags with historic and cultural associations to present-day ceremonial counties; historic boundaries may differ. These are not flags of modern ceremonial authority.');
    await act(async () => { (container.querySelector('[aria-label="Fullscreen flag"]') as HTMLElement).click(); });
    const preview = dom.document.querySelector('[aria-label="Flag preview"]')!;
    expect(preview.textContent).toContain('Context: Registered community flag');
    expect(preview.textContent).toContain('Modification: Colours adjusted');
    const quizCredits = preview.querySelector('details') as HTMLDetailsElement;
    await act(async () => { (quizCredits.querySelector('summary') as HTMLElement).click(); });
    expect(quizCredits.open).toBe(true);
    expect(quizCredits.querySelectorAll('li')).toHaveLength(2);
    expect(quizCredits.textContent).toContain('First artist');
    expect(quizCredits.textContent).toContain('Second artist');
    expect(quizCredits.querySelector('a[href="https://example.org/first"]')?.textContent).toBe('First emblem');
    expect(quizCredits.querySelector('a[href="https://creativecommons.org/licenses/by-sa/4.0/"]')?.textContent).toBe('CC BY-SA 4.0');
  } finally {
    catalog.mockRestore(); counties.mockRestore(); challenge.mockRestore(); stats.mockRestore();
    useAuthStore.setState(auth); await dispose();
  }
});

test('legal policies disclose regional browser storage and quiz records', async () => {
  const { container, root, dispose } = setup();
  try {
    // The cookie policy loads advertising code that reads document at module initialization.
    const { default: CookiePolicyPage } = await import('../src/pages/CookiePolicyPage');
    const { default: PrivacyPolicyPage } = await import('../src/pages/PrivacyPolicyPage');
    await act(async () => { root.render(<CookiePolicyPage />); });
    let text = container.textContent!.replace(/\s+/g, ' ');
    expect(text).toContain('regional_symbols_{scope}_{coat|flag}_daily_token_{date}');
    expect(text).toContain('regional_symbols_{scope}_{coat|flag}_guide_seen');
    expect(text).toContain('These date-keyed values do not automatically expire or get deleted');
    await act(async () => { root.render(<PrivacyPolicyPage />); });
    text = container.textContent!.replace(/\s+/g, ' ');
    expect(text).toContain('Regional symbol quizzes store a started run under your account or a pseudonymous guest identifier');
    expect(text).toContain('client-reported elapsed time');
    expect(text).toContain('Community statistics include completed and given-up runs, not abandoned runs');
    expect(text).toContain('regional symbol quiz runs and solves');
    expect(text).toContain('no general automatic time-based deletion');
  } finally {
    await dispose();
  }
});

test('publisher capture does not request regional games, catalogs or quiz statistics', async () => {
  const { dom, container, root, dispose } = setup();
  Object.defineProperty(dom, '__COUNTRYDLE_PRERENDER__', { configurable: true, value: true });
  const auth = useAuthStore.getState();
  useAuthStore.setState({ isLoading: false, isAuthenticated: true });
  const catalogs = regionalSymbolGames.map(({ scope, flags }) =>
    spyOn(regionalSymbolsService(scope, flags), 'getCatalog').mockResolvedValue([]));
  const service = regionalSymbolsService('london_boroughs', false);
  const counties = spyOn(service, 'getCounties').mockResolvedValue([]);
  const challenge = spyOn(service, 'getChallenge');
  const sync = spyOn(service, 'sync');
  const stats = spyOn(service.quiz, 'stats');
  const start = spyOn(service.quiz, 'start');
  function Menu() {
    const groups = useGameCatalog();
    return <div>{groups.map((group) => <span key={group.title}>{group.title}</span>)}</div>;
  }
  try {
    await act(async () => { root.render(<MemoryRouter><Menu /><PowiatHeraldryPage scope="london_boroughs" /></MemoryRouter>); });
    expect(container.textContent).toContain('London Borough Coats of Arms');
    expect(container.querySelector('button')).toBeNull();
    await act(async () => { root.render(<MemoryRouter><Menu /><PowiatCoatsQuizPage scope="london_boroughs" /></MemoryRouter>); });
    expect(container.textContent).toContain('London Borough Coats of Arms Quiz');
    expect(container.querySelector('button')).toBeNull();
    catalogs.forEach((mock) => expect(mock).not.toHaveBeenCalled());
    expect(counties).not.toHaveBeenCalled();
    expect(challenge).not.toHaveBeenCalled();
    expect(sync).not.toHaveBeenCalled();
    expect(stats).not.toHaveBeenCalled();
    expect(start).not.toHaveBeenCalled();
  } finally {
    catalogs.forEach((mock) => mock.mockRestore());
    counties.mockRestore(); challenge.mockRestore(); sync.mockRestore(); stats.mockRestore(); start.mockRestore();
    useAuthStore.setState(auth); await dispose();
  }
});
