import { afterEach, beforeEach, expect, mock, spyOn, test } from 'bun:test';
import toast from 'react-hot-toast';
import {
  useCountryGameStore, usePowiatyGameStore, useUSStatesGameStore, useWojewodztwaGameStore,
  useEuropeGameStore, useAsiaGameStore, useAfricaGameStore, useAmericasGameStore, useFlagdleGameStore,
} from '../src/stores/gameStore';
import {
  gameService, powiatService, usStateService, wojewodztwoService,
  europeService, asiaService, africaService, americasService, flagdleService,
} from '../src/services/api';
import { useAuthStore } from '../src/stores/authStore';

class MemoryStorage {
  data = new Map<string, string>();
  get length() { return this.data.size; }
  key(index: number) { return [...this.data.keys()][index] ?? null; }
  getItem(key: string) { return this.data.get(key) ?? null; }
  setItem(key: string, value: string) { this.data.set(key, value); }
  removeItem(key: string) { this.data.delete(key); }
}
const modes = [
  ['country', useCountryGameStore, gameService, 10],
  ['powiaty', usePowiatyGameStore, powiatService, 15],
  ['us_states', useUSStatesGameStore, usStateService, 8],
  ['wojewodztwa', useWojewodztwaGameStore, wojewodztwoService, 5],
  ['europe', useEuropeGameStore, europeService, 8],
  ['asia', useAsiaGameStore, asiaService, 8],
  ['africa', useAfricaGameStore, africaService, 8],
  ['americas', useAmericasGameStore, americasService, 8],
] as const;
const date = '2026-09-25';
const question = (id: number, answer: boolean | null, valid = true) => ({
  id, answer, valid, original_question: 'Is it in Europe?', question: 'Is it in Europe?',
  explanation: 'Not enough evidence', asked_at: `${date}T12:00:00`, day_id: 1, user_id: null,
});
const state = (maximum: number) => ({
  questions_asked: 0, remaining_questions: maximum, guesses_made: 0,
  remaining_guesses: 3, is_game_over: false, won: false,
});

beforeEach(() => {
  Object.defineProperty(globalThis, 'localStorage', { configurable: true, value: new MemoryStorage() });
  spyOn(toast, 'error').mockImplementation(() => 'toast');
  spyOn(console, 'error').mockImplementation(() => {});
  useAuthStore.setState({ user: null });
});
afterEach(() => mock.restore());

for (const responseTime of [25, 1000, 1500]) {
  test(`thinking animation: a ${responseTime}ms response completes at max(response time, 1000ms)`, async () => {
    let now = 0;
    const timers: { at: number; run: () => void }[] = [];
    spyOn(Date, 'now').mockImplementation(() => now);
    spyOn(globalThis, 'setTimeout').mockImplementation(((run: () => void, delay = 0) => {
      timers.push({ at: now + delay, run });
      return 0;
    }) as typeof setTimeout);
    const flush = async () => { await Promise.resolve(); await Promise.resolve(); };
    const advance = async (time: number) => {
      now = time;
      for (const timer of timers.splice(0)) {
        if (timer.at <= now) timer.run();
        else timers.push(timer);
      }
      await flush();
    };
    useCountryGameStore.setState({ gameState: state(10), questions: [], guesses: [],
      dailyDate: date, isGuest: true, isLoading: false, correctEntity: null });
    const response = Promise.withResolvers<ReturnType<typeof question>>();
    spyOn(gameService, 'askQuestion').mockImplementation(() => response.promise as never);
    const pending = useCountryGameStore.getState().askQuestion('Is it in Europe?');
    try {
      expect(useCountryGameStore.getState().isLoading).toBe(true);
      now = responseTime;
      response.resolve(question(1, true));
      await flush();
      if (responseTime < 1000) {
        await advance(999);
        expect(useCountryGameStore.getState().isLoading).toBe(true);
        expect(useCountryGameStore.getState().questions).toEqual([]);
        await advance(1000);
      }
      expect(useCountryGameStore.getState().isLoading).toBe(false);
      expect(useCountryGameStore.getState().gameState?.questions_asked).toBe(1);
      expect(useCountryGameStore.getState().questions.map(q => q.id)).toEqual([1]);
    } finally {
      for (const timer of timers.splice(0)) timer.run();
      await pending;
    }
  });
}

for (const [mode, store, service, maximum] of modes) {
  const key = `guess_game_${mode}_${date}`;
  const initialize = () => store.setState({ gameState: state(maximum), questions: [], guesses: [],
    dailyDate: date, isGuest: true, isLoading: false, correctEntity: null });

  test(`${mode}: unresolved and failed answers never enter guest history or consume quota`, async () => {
    initialize();
    const ask = spyOn(service, 'askQuestion');
    for (const result of [question(1, null), question(2, false, false), undefined]) {
      ask.mockResolvedValueOnce(result as never);
      await store.getState().askQuestion('Is it in Europe?');
      expect(store.getState().questions).toEqual([]);
      expect(store.getState().gameState).toEqual(state(maximum));
      expect(localStorage.getItem(key)).toBeNull();
    }
    ask.mockRejectedValueOnce(new Error('network unavailable'));
    await store.getState().askQuestion('Is it in Europe?');
    expect(store.getState().gameState?.questions_asked).toBe(0);
    expect(localStorage.getItem(key)).toBeNull();
  });

  test(`${mode}: True and False each consume once and survive reload`, async () => {
    initialize();
    spyOn(service, 'askQuestion').mockResolvedValueOnce(question(1, true) as never)
      .mockResolvedValueOnce(question(2, false) as never);
    await store.getState().askQuestion('First?');
    await store.getState().askQuestion('Second?');
    expect(store.getState().gameState?.questions_asked).toBe(2);
    expect(store.getState().gameState?.remaining_questions).toBe(maximum - 2);
    const saved = JSON.parse(localStorage.getItem(key)!);
    expect(saved.questions.map((q: { answer: boolean }) => q.answer)).toEqual([true, false]);
    spyOn(service, 'getState').mockResolvedValue({ user: null, date,
      state: { ...state(maximum), questions_asked: 2, remaining_questions: maximum - 2 },
      questions: [question(1, true), question(2, false)], guesses: [],
    } as never);
    store.getState().resetGame();
    await store.getState().fetchGameState();
    expect(store.getState().gameState?.remaining_questions).toBe(maximum - 2);
    expect(store.getState().questions.map(q => q.answer)).toEqual([true, false]);
  });

  test(`${mode}: a pending last-slot request cannot submit a second answer`, async () => {
    initialize();
    store.setState({ gameState: { ...state(maximum), questions_asked: maximum - 1, remaining_questions: 1 } });
    const { promise, resolve } = Promise.withResolvers<unknown>();
    const ask = spyOn(service, 'askQuestion').mockImplementation(() => promise as never);
    const pending = store.getState().askQuestion('First?');
    await store.getState().askQuestion('Overlapping?');
    resolve(question(1, false));
    await pending;
    await store.getState().askQuestion('No slots left?');
    expect(ask).toHaveBeenCalledTimes(1);
    expect(store.getState().gameState?.remaining_questions).toBe(0);
    expect(store.getState().gameState?.questions_asked).toBe(maximum);
  });

  test(`${mode}: canonical restored history excludes unresolved legacy entries from counted sync history`, async () => {
    initialize();
    localStorage.setItem(key, JSON.stringify({ state: { ...state(maximum), questions_asked: 3, remaining_questions: maximum - 3 },
      questions: [question(1, null), question(2, false, false), question(3, false)], guesses: [] }));
    spyOn(service, 'getState').mockResolvedValue({ user: null, date,
      state: { ...state(maximum), questions_asked: 1, remaining_questions: maximum - 1 },
      questions: [question(3, false)], guesses: [],
    } as never);
    await store.getState().fetchGameState();
    expect(store.getState().questions.map(q => q.id)).toEqual([3]);
    expect(store.getState().gameState?.remaining_questions).toBe(maximum - 1);
    const saved = JSON.parse(localStorage.getItem(key)!);
    expect(saved.state.questions_asked).toBe(1);
    expect(saved.questions.map((q: { id: number }) => q.id)).toEqual([3]);
  });

  test(`${mode}: authenticated unresolved responses preserve authoritative state`, async () => {
    initialize();
    store.setState({ isGuest: false });
    spyOn(service, 'askQuestion').mockResolvedValue(question(1, null) as never);
    await store.getState().askQuestion('Unknown?');
    expect(store.getState().gameState).toEqual(state(maximum));
    expect(store.getState().questions).toEqual([]);
    expect(localStorage.getItem(key)).toBeNull();
  });
}

test('flagdle: only boolean answers enter its unlimited local question history', async () => {
  const store = useFlagdleGameStore;
  store.setState({ gameState: { remaining_guesses: 12, guesses_made: 0, revealed_stage: 1,
    is_game_over: false, won: false, points: 0 }, questions: [], guesses: [], dailyDate: date, isGuest: true, isLoading: false });
  const ask = spyOn(flagdleService, 'askQuestion');
  ask.mockResolvedValueOnce(question(1, null) as never);
  await store.getState().askQuestion('Unknown?');
  expect(store.getState().questions).toEqual([]);
  expect(localStorage.getItem(`guess_game_flagdle_${date}`)).toBeNull();
  ask.mockResolvedValueOnce(question(2, false) as never);
  await store.getState().askQuestion('Known false?');
  expect(store.getState().questions.map(q => q.answer)).toEqual([false]);
  expect(JSON.parse(localStorage.getItem(`guess_game_flagdle_${date}`)!).questions.map((q: { answer: boolean }) => q.answer)).toEqual([false]);
});

test('authenticated False reloads authoritative counters without creating guest history', async () => {
  const user = { id: 1, username: 'player', email: 'player@example.com', verified: true, is_admin: false };
  useAuthStore.setState({ user });
  useCountryGameStore.setState({ gameState: state(10), questions: [], guesses: [], dailyDate: date,
    isGuest: false, isLoading: false });
  spyOn(gameService, 'askQuestion').mockResolvedValue(question(1, false) as never);
  spyOn(gameService, 'getState').mockResolvedValue({ user, date, guesses: [], questions: [question(1, false)],
    state: { ...state(10), questions_asked: 1, remaining_questions: 9 } } as never);
  await useCountryGameStore.getState().askQuestion('Known false?');
  expect(useCountryGameStore.getState().gameState?.remaining_questions).toBe(9);
  expect(useCountryGameStore.getState().questions.map(q => q.answer)).toEqual([false]);
  expect(localStorage.getItem(`guess_game_country_${date}`)).toBeNull();
});

test('failed guest sync keeps the saved counted answers available for retry', async () => {
  const user = { id: 1, username: 'player', email: 'player@example.com', verified: true, is_admin: false };
  useAuthStore.setState({ user });
  const key = `guess_game_country_${date}`;
  const snapshot = { state: { ...state(10), questions_asked: 1, remaining_questions: 9 },
    questions: [question(1, false)], guesses: [] };
  localStorage.setItem(key, JSON.stringify(snapshot));
  useCountryGameStore.setState({ gameState: snapshot.state, questions: snapshot.questions as never, guesses: [],
    dailyDate: date, isGuest: true, isLoading: false });
  spyOn(gameService, 'syncGuestData').mockRejectedValue(new Error('Network unavailable'));
  await useCountryGameStore.getState().syncGuestData();
  expect(JSON.parse(localStorage.getItem(key)!)).toEqual(snapshot);
  expect(useCountryGameStore.getState().gameState?.questions_asked).toBe(1);
});

test('all-unresolved legacy snapshot restores the full guest quota, not its stale counter', async () => {
  const key = `guess_game_country_${date}`;
  localStorage.setItem(key, JSON.stringify({
    state: { ...state(10), questions_asked: 1, remaining_questions: 9 },
    questions: [question(1, null)], guesses: [],
  }));
  spyOn(gameService, 'getState').mockResolvedValue({ user: null, date, state: state(10), questions: [], guesses: [] } as never);
  await useCountryGameStore.getState().fetchGameState();
  expect(useCountryGameStore.getState().gameState?.remaining_questions).toBe(10);
  expect(JSON.parse(localStorage.getItem(key)!).state.questions_asked).toBe(0);
});

for (const entry of ['fetchGameState', 'syncGuestData'] as const) {
  test(`country: ${entry} cannot delete a newer guest answer saved during sync`, async () => {
    const store = useCountryGameStore;
    const key = `guess_game_country_${date}`;
    const first = { state: { ...state(10), questions_asked: 1, remaining_questions: 9 },
      questions: [question(1, false)], guesses: [] };
    const newer = { state: { ...state(10), questions_asked: 2, remaining_questions: 8 },
      questions: [question(1, false), question(2, true)], guesses: [] };
    localStorage.setItem(key, JSON.stringify(first));
    store.setState({ dailyDate: date, isGuest: true, gameState: first.state, questions: first.questions as never, guesses: [], isLoading: false });
    const user = { id: 1, username: 'accounting' };
    useAuthStore.setState({ user: user as never });
    spyOn(gameService, 'getState').mockResolvedValue({ ...first, user, date } as never);
    const entered = Promise.withResolvers<void>();
    const pendingResponse = Promise.withResolvers<unknown>();
    const sync = spyOn(gameService, 'syncGuestData').mockImplementation(async () => {
      entered.resolve();
      return await pendingResponse.promise as never;
    });
    const pending = store.getState()[entry]();
    await entered.promise;
    localStorage.setItem(key, JSON.stringify(newer));
    pendingResponse.resolve({ ...first, user, date });
    await pending;
    expect(JSON.parse(localStorage.getItem(key)!).questions.map((q: { id: number }) => q.id)).toEqual([1, 2]);
    expect(sync).toHaveBeenCalledTimes(1);
  });
}

test('flagdle: read-only storage cannot discard canonical guest counters and accepted history', async () => {
  const key = `guess_game_flagdle_${date}`;
  const savedState = { remaining_guesses: 10, guesses_made: 2, revealed_stage: 3, is_game_over: false, won: false, points: 0 };
  localStorage.setItem(key, JSON.stringify({ state: savedState, guesses: [], questions: [question(1, false), question(2, null)] }));
  spyOn(localStorage, 'setItem').mockImplementation(() => { throw new DOMException('Read only', 'QuotaExceededError'); });
  spyOn(flagdleService, 'getState').mockResolvedValue({ user: null, date, guesses: [],
    state: savedState, questions: [question(1, false), question(2, null)],
  } as never);
  await useFlagdleGameStore.getState().fetchGameState();
  expect(useFlagdleGameStore.getState().gameState?.remaining_guesses).toBe(10);
  expect(useFlagdleGameStore.getState().gameState?.guesses_made).toBe(2);
  expect(useFlagdleGameStore.getState().questions.map(q => q.answer)).toEqual([false]);
});

const terminalEvidence = [{
  relation: 'membership' as const, value: 'NATO',
  provenance: { status: 'unknown' as const, citation: 'Answer-used membership snapshot', source_url: null,
    effective_from: null, effective_to: null, retrieved_at: null, updated_at: null, convention: null },
}];

test('country: terminal guest reload restores canonical owned originals even when local IDs are obsolete', async () => {
  const key = `guess_game_country_${date}`;
  const terminal = { ...state(10), is_game_over: true, won: true, questions_asked: 2, remaining_questions: 8, guesses_made: 1, remaining_guesses: 2 };
  localStorage.setItem(key, JSON.stringify({ state: terminal, questions: [question(1, true), question(2, false)], guesses: [] }));
  spyOn(gameService, 'getState').mockResolvedValue({ user: null, date, state: terminal,
    guesses: [{ id: 81, answer: true, guess: 'Poland', elapsed_seconds: null }], questions: [
    { ...question(1, true), fact_provenance: terminalEvidence },
    { ...question(999, false), fact_provenance: terminalEvidence },
  ] } as never);
  await useCountryGameStore.getState().fetchGameState();
  expect(useCountryGameStore.getState().questions.map(q => q.id)).toEqual([1, 999]);
  expect(useCountryGameStore.getState().gameState).toEqual({ ...terminal, points: 2123 });
  expect(useCountryGameStore.getState().questions[0].fact_provenance).toEqual(terminalEvidence);
  expect(useCountryGameStore.getState().questions[1].fact_provenance).toEqual(terminalEvidence);
  expect(JSON.parse(localStorage.getItem(key)!).questions[0].fact_provenance).toEqual(terminalEvidence);
});

test('country: an active server strips stale local evidence even when local storage says terminal', async () => {
  const key = `guess_game_country_${date}`;
  localStorage.setItem(key, JSON.stringify({ state: { ...state(10), is_game_over: true, won: true },
    questions: [{ ...question(1, true), fact_provenance: terminalEvidence }], guesses: [] }));
  spyOn(gameService, 'getState').mockResolvedValue({ user: null, date, state: state(10), guesses: [], questions: [] } as never);
  await useCountryGameStore.getState().fetchGameState();
  expect(useCountryGameStore.getState().gameState).toEqual(state(10));
  expect(useCountryGameStore.getState().questions).toEqual([]);
  expect(JSON.parse(localStorage.getItem(key)!).questions).toEqual([]);
});

test('country: a terminal guest guess fetches the now-unredacted answer-used history', async () => {
  const store = useCountryGameStore;
  const accepted = question(1, true);
  const initial = { ...state(10), questions_asked: 1, remaining_questions: 9 };
  store.setState({ gameState: initial, questions: [accepted] as never, guesses: [], dailyDate: date,
    isGuest: true, isLoading: false, correctEntity: null, entities: [{ id: 1, name: 'Poland' }] });
  spyOn(gameService, 'makeGuess').mockResolvedValue({ id: 1, answer: true, guess: 'Poland' } as never);
  const terminal = { ...initial, guesses_made: 1, remaining_guesses: 2, is_game_over: true, won: true, points: 2000 };
  spyOn(gameService, 'getState').mockResolvedValue({ user: null, date,
    state: terminal, guesses: [{ id: 1, answer: true, guess: 'Poland', elapsed_seconds: null }],
    questions: [{ ...accepted, fact_provenance: terminalEvidence }],
  } as never);
  await store.getState().makeGuess('Poland', 1);
  expect(store.getState().gameState).toEqual(terminal);
  expect(store.getState().questions[0].fact_provenance).toEqual(terminalEvidence);
  expect(JSON.parse(localStorage.getItem(`guess_game_country_${date}`)!).questions[0].fact_provenance).toEqual(terminalEvidence);
});

test('country: stale authenticated-cookie history cannot hydrate guest evidence even for a matching local ID', async () => {
  const key = `guess_game_country_${date}`;
  const terminal = { ...state(10), is_game_over: true, won: true };
  localStorage.setItem(key, JSON.stringify({ state: terminal,
    questions: [{ ...question(1, true), fact_provenance: terminalEvidence }], guesses: [] }));
  spyOn(gameService, 'getState').mockResolvedValue({ user: { id: 99 }, date, state: terminal, guesses: [],
    questions: [{ ...question(1, true), fact_provenance: terminalEvidence }],
  } as never);
  await useCountryGameStore.getState().fetchGameState();
  expect(useCountryGameStore.getState().isGuest).toBe(true);
  expect(useCountryGameStore.getState().questions[0].fact_provenance).toEqual([]);
});

test('country: cleared local storage cannot discard canonical signed-guest counters, originals, reveal or evidence', async () => {
  const store = useCountryGameStore;
  store.getState().resetGame();
  const terminal = { ...state(10), questions_asked: 1, remaining_questions: 9, guesses_made: 1,
    remaining_guesses: 2, is_game_over: true, won: true, points: 2123 };
  const original = { ...question(71, true), fact_provenance: terminalEvidence };
  const guess = { id: 83, answer: true, guess: 'Poland', country_id: 1 };
  const country = { id: 1, name: 'Poland', iso2: 'PL', iso3: 'POL' };
  spyOn(gameService, 'getState').mockResolvedValue({ user: null, date, state: terminal,
    questions: [original], guesses: [guess], country,
  } as never);
  await store.getState().fetchGameState();
  expect(store.getState().gameState).toEqual(terminal);
  expect(store.getState().questions).toEqual([original]);
  expect(store.getState().guesses).toEqual([guess]);
  expect(store.getState().correctEntity).toEqual(country);
  const saved = JSON.parse(localStorage.getItem(`guess_game_country_${date}`)!);
  expect(saved.state).toEqual(terminal);
  expect(saved.questions).toEqual([original]);
  expect(saved.guesses).toEqual([guess]);
});

test('flagdle: cleared storage restores canonical signed-guest counters and accepted original evidence history', async () => {
  const store = useFlagdleGameStore;
  store.getState().resetGame();
  const canonical = { remaining_guesses: 7, guesses_made: 5, revealed_stage: 6, is_game_over: false, won: false, points: 0 };
  const original = { ...question(71, true), fact_provenance: [] };
  const guess = { id: 81, answer: false, guess: 'Poland' };
  spyOn(flagdleService, 'getState').mockResolvedValue({ user: null, date, state: canonical,
    questions: [original], guesses: [guess], country: null,
  } as never);
  await store.getState().fetchGameState();
  expect(store.getState().gameState).toEqual(canonical);
  expect(store.getState().questions).toEqual([original]);
  expect(store.getState().guesses).toEqual([guess] as never);
  const saved = JSON.parse(localStorage.getItem(`guess_game_flagdle_${date}`)!);
  expect(saved.state).toEqual(canonical);
  expect(saved.questions).toEqual([original]);
});

test('flagdle: terminal guest guess hydrates canonical answer-used evidence instead of retaining redacted POST history', async () => {
  const store = useFlagdleGameStore;
  const original = { ...question(71, true), fact_provenance: [] };
  store.setState({ gameState: { remaining_guesses: 1, guesses_made: 11, revealed_stage: 12,
    is_game_over: false, won: false, points: 0 }, questions: [original] as never,
    guesses: [], dailyDate: date, isGuest: true, isLoading: false });
  spyOn(flagdleService, 'makeGuess').mockResolvedValue({ id: 81, answer: true, guess: 'Poland' } as never);
  const terminal = { remaining_guesses: 0, guesses_made: 12, revealed_stage: 12, is_game_over: true, won: true, points: 1000 };
  const snapshot = { ...original, fact_provenance: terminalEvidence };
  spyOn(flagdleService, 'getState').mockResolvedValue({ user: null, date, state: terminal,
    questions: [snapshot], guesses: [], country: { id: 1, name: 'Poland', iso2: 'PL', iso3: 'POL' },
  } as never);
  await store.getState().makeGuess('Poland', 1);
  expect(store.getState().gameState).toEqual(terminal);
  expect(store.getState().questions).toEqual([snapshot]);
  expect(JSON.parse(localStorage.getItem(`guess_game_flagdle_${date}`)!).questions).toEqual([snapshot]);
});

test('flagdle: unlimited postgame accepted questions hydrate terminal evidence without consuming a guess', async () => {
  const store = useFlagdleGameStore;
  const terminal = { remaining_guesses: 0, guesses_made: 12, revealed_stage: 12, is_game_over: true, won: false, points: 0 };
  store.setState({ gameState: terminal, questions: [], guesses: [], dailyDate: date, isGuest: true, isLoading: false });
  const accepted = question(91, false);
  spyOn(flagdleService, 'askQuestion').mockResolvedValue({ ...accepted, fact_provenance: [] } as never);
  spyOn(flagdleService, 'getState').mockResolvedValue({ user: null, date, state: terminal,
    questions: [{ ...accepted, fact_provenance: terminalEvidence }], guesses: [],
    country: { id: 1, name: 'Poland', iso2: 'PL', iso3: 'POL' },
  } as never);
  await store.getState().askQuestion('Was the answer a NATO member?');
  expect(store.getState().gameState).toEqual(terminal);
  expect(store.getState().questions[0].fact_provenance).toEqual(terminalEvidence);
  expect(JSON.parse(localStorage.getItem(`guess_game_flagdle_${date}`)!).questions[0].fact_provenance).toEqual(terminalEvidence);
});

test('flagdle: stale authenticated-cookie state cannot attach private history, reveal or evidence to guest display', async () => {
  const savedState = { remaining_guesses: 10, guesses_made: 2, revealed_stage: 3, is_game_over: false, won: false, points: 0 };
  localStorage.setItem(`guess_game_flagdle_${date}`, JSON.stringify({ state: savedState, guesses: [],
    questions: [{ ...question(1, false), fact_provenance: terminalEvidence }],
  }));
  spyOn(flagdleService, 'getState').mockResolvedValue({ user: { id: 99 }, date,
    state: { ...savedState, is_game_over: true, won: true }, guesses: [],
    questions: [{ ...question(99, true), fact_provenance: terminalEvidence }],
    country: { id: 1, name: 'Private authenticated target', iso2: 'PL', iso3: 'POL' },
  } as never);
  await useFlagdleGameStore.getState().fetchGameState();
  expect(useFlagdleGameStore.getState().isGuest).toBe(true);
  expect(useFlagdleGameStore.getState().gameState).toEqual(savedState);
  expect(useFlagdleGameStore.getState().questions.map(q => q.id)).toEqual([1]);
  expect(useFlagdleGameStore.getState().questions[0].fact_provenance).toEqual([]);
  expect(useFlagdleGameStore.getState().correctCountry).toBeNull();
});

for (const [elapsed_seconds, apiPoints, expected] of [[60, 0, 2196], [null, undefined, 1956], [undefined, 0, 1956]] as const) {
  test(`country: display estimate uses canonical accepted history and nullable elapsed ${elapsed_seconds}, not stored points`, async () => {
    const store = useCountryGameStore;
    const key = `guess_game_country_${date}`;
    const canonical = { ...state(10), questions_asked: 2, remaining_questions: 8, guesses_made: 2,
      remaining_guesses: 1, is_game_over: true, won: true, points: apiPoints };
    localStorage.setItem(key, JSON.stringify({ state: { ...canonical, points: 999999 }, questions: [], guesses: [] }));
    const guesses = [{ id: 80, answer: false, guess: 'Japan' },
      { id: 81, answer: true, guess: 'Poland', elapsed_seconds }];
    spyOn(gameService, 'getState').mockResolvedValue({ user: null, date, state: canonical,
      questions: [question(71, true), question(72, false)], guesses,
    } as never);
    await store.getState().fetchGameState();
    expect(store.getState().gameState?.points).toBe(expected);
    expect(store.getState().guesses.map(guess => guess.id)).toEqual([80, 81]);
    expect(JSON.parse(localStorage.getItem(key)!).state.points).toBe(expected);
    store.getState().resetGame();
    await store.getState().fetchGameState();
    expect(store.getState().gameState?.points).toBe(expected);
  });
}

for (const [elapsed_seconds, expected] of [[60, 2013], [null, 1850], [undefined, 1850]] as const) {
  test(`flagdle: display estimate uses canonical accepted history and nullable elapsed ${elapsed_seconds}, not stored points`, async () => {
    const store = useFlagdleGameStore;
    const key = `guess_game_flagdle_${date}`;
    const canonical = { remaining_guesses: 10, guesses_made: 2, revealed_stage: 3,
      is_game_over: true, won: true, points: 0 };
    localStorage.setItem(key, JSON.stringify({ state: { ...canonical, points: 999999 }, questions: [], guesses: [] }));
    spyOn(flagdleService, 'getState').mockResolvedValue({ user: null, date, state: canonical,
      questions: [question(71, true)], guesses: [
        { id: 80, answer: false, guess: 'Japan' }, { id: 81, answer: true, guess: 'Poland', elapsed_seconds },
      ], country: { id: 1, name: 'Poland', iso2: 'PL', iso3: 'POL' },
    } as never);
    await store.getState().fetchGameState();
    expect(store.getState().gameState?.points).toBe(expected);
    expect(store.getState().guesses.map(guess => guess.id)).toEqual([80, 81]);
    expect(JSON.parse(localStorage.getItem(key)!).state.points).toBe(expected);
    store.getState().resetGame();
    await store.getState().fetchGameState();
    expect(store.getState().gameState?.points).toBe(expected);
  });
}

test('authenticated canonical winnings preserve the awarded server points rather than a guest display estimate', async () => {
  const user = { id: 1, username: 'player', email: 'player@example.com', verified: true, is_admin: false };
  useAuthStore.setState({ user });
  const awarded = { ...state(10), questions_asked: 2, remaining_questions: 8, guesses_made: 2,
    remaining_guesses: 1, is_game_over: true, won: true, points: 1743 };
  spyOn(gameService, 'getState').mockResolvedValue({ user, date, state: awarded,
    questions: [question(71, true), question(72, false)],
    guesses: [{ id: 81, answer: true, guess: 'Poland', elapsed_seconds: 1 }],
  } as never);
  await useCountryGameStore.getState().fetchGameState();
  expect(useCountryGameStore.getState().gameState).toEqual(awarded);
  expect(localStorage.getItem(`guess_game_country_${date}`)).toBeNull();
});
