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
    const response = Promise.withResolvers<unknown>();
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
        expect(useCountryGameStore.getState().gameState).toEqual(state(10));
        await advance(1000);
      }
      expect(timers).toEqual([]);
      expect(useCountryGameStore.getState().isLoading).toBe(false);
      expect(useCountryGameStore.getState().gameState?.questions_asked).toBe(1);
      expect(useCountryGameStore.getState().gameState?.remaining_questions).toBe(9);
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
    spyOn(service, 'getState').mockResolvedValue({ user: null, date, state: state(maximum), questions: [], guesses: [] } as never);
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

  test(`${mode}: restored unresolved legacy entries do not become counted sync history`, async () => {
    initialize();
    localStorage.setItem(key, JSON.stringify({ state: { ...state(maximum), questions_asked: 3, remaining_questions: maximum - 3 },
      questions: [question(1, null), question(2, false, false), question(3, false)], guesses: [] }));
    spyOn(service, 'getState').mockResolvedValue({ user: null, date, state: state(maximum), questions: [], guesses: [] } as never);
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

test('flagdle: read-only storage must still restore guest counters and accepted history', async () => {
  const key = `guess_game_flagdle_${date}`;
  const savedState = { remaining_guesses: 10, guesses_made: 2, revealed_stage: 3, is_game_over: false, won: false, points: 0 };
  localStorage.setItem(key, JSON.stringify({ state: savedState, guesses: [], questions: [question(1, false), question(2, null)] }));
  spyOn(localStorage, 'setItem').mockImplementation(() => { throw new DOMException('Read only', 'QuotaExceededError'); });
  spyOn(flagdleService, 'getState').mockResolvedValue({ user: null, date, guesses: [], state: {
    ...savedState, remaining_guesses: 12, guesses_made: 0, revealed_stage: 1,
  } } as never);
  await useFlagdleGameStore.getState().fetchGameState();
  expect(useFlagdleGameStore.getState().gameState?.remaining_guesses).toBe(10);
  expect(useFlagdleGameStore.getState().gameState?.guesses_made).toBe(2);
  expect(useFlagdleGameStore.getState().questions.map(q => q.answer)).toEqual([false]);
});

for (const [mode, store, service, maximum] of modes.filter(([mode]) =>
  ['country', 'europe', 'asia', 'africa', 'americas'].includes(mode))) {
  test(`${mode}: completed guest history hydrates named explanations by question ID and survives reload`, async () => {
    const key = `guess_game_${mode}_${date}`;
    const completedState = { ...state(maximum), questions_asked: 1, remaining_questions: maximum - 1,
      guesses_made: 1, remaining_guesses: 2, is_game_over: true, won: true };
    const activeQuestion = { ...question(1, true), explanation: '' };
    const completedQuestion = { ...activeQuestion, explanation: 'Poland is in Europe.' };
    localStorage.setItem(key, JSON.stringify({
      state: completedState, questions: [activeQuestion], guesses: [{ id: 1, guess: 'Poland', answer: true }],
    }));
    spyOn(service, 'getState').mockResolvedValue({
      user: null, date, state: completedState, guesses: [], questions: [
        completedQuestion, { ...completedQuestion, id: 999, explanation: 'Unrelated history' },
      ],
    } as never);
    store.setState({ isGuest: true, dailyDate: date, questions: [], guesses: [], isLoading: false });
    await store.getState().fetchGameState();
    expect(store.getState().questions.map(q => q.explanation)).toEqual(['Poland is in Europe.']);
    expect(JSON.parse(localStorage.getItem(key)!).questions[0].explanation).toBe('Poland is in Europe.');
    store.getState().resetGame();
    await store.getState().fetchGameState();
    expect(store.getState().questions.map(q => q.explanation)).toEqual(['Poland is in Europe.']);
  });
}

test('active guest history never hydrates terminal facts from a state response', async () => {
  const key = `guess_game_country_${date}`;
  localStorage.setItem(key, JSON.stringify({
    state: { ...state(10), questions_asked: 1, remaining_questions: 9 },
    questions: [{ ...question(1, true), explanation: '' }], guesses: [],
  }));
  spyOn(gameService, 'getState').mockResolvedValue({
    user: null, date, state: { ...state(10), is_game_over: true }, guesses: [],
    questions: [{ ...question(1, true), explanation: 'Poland is in Europe.' }],
  } as never);
  await useCountryGameStore.getState().fetchGameState();
  expect(useCountryGameStore.getState().questions[0].explanation).toBe('');
});

test('Flagdle completed guest question history hydrates its own factual explanations', async () => {
  const completedState = { remaining_guesses: 11, guesses_made: 1, revealed_stage: 12,
    is_game_over: true, won: true, points: 2000 };
  const activeQuestion = { ...question(1, true), explanation: '' };
  localStorage.setItem(`guess_game_flagdle_${date}`, JSON.stringify({
    state: completedState, questions: [activeQuestion], guesses: [],
  }));
  spyOn(flagdleService, 'getState').mockResolvedValue({
    user: null, date, state: completedState, guesses: [],
    country: { id: 1, name: 'Poland', iso2: 'PL', iso3: 'POL' },
    questions: [{ ...activeQuestion, explanation: "Poland's flag contains red and white." }],
  } as never);
  await useFlagdleGameStore.getState().fetchGameState();
  expect(useFlagdleGameStore.getState().questions.map(q => q.explanation))
    .toEqual(["Poland's flag contains red and white."]);
});
