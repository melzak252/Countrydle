export type GuestGameType = 'country' | 'powiaty' | 'us_states' | 'wojewodztwa' | 'flagdle';

export interface GuestHistory {
  currentStreak: number;
  solved: number;
  bestScore: number | null;
  days: Array<{ date: string; status: 'won' | 'lost' | 'unplayed' }>;
  storageAvailable: boolean;
}

interface CompletedResult {
  won: boolean;
  questionsAsked: number;
  guessesMade: number;
  points: number | null;
}

export const GUEST_HISTORY_EVENT = 'countrydle:guest-history';
const RESULT_PREFIX = 'countrydle_guest_result_v1_';
const SNAPSHOT_PREFIX = 'guess_game_';
const DAY_MS = 86_400_000;
const limits: Record<GuestGameType, { questions: number; guesses: number }> = {
  country: { questions: 10, guesses: 3 },
  powiaty: { questions: 15, guesses: 3 },
  us_states: { questions: 8, guesses: 3 },
  wojewodztwa: { questions: 5, guesses: 2 },
  flagdle: { questions: 0, guesses: 6 },
};

function isDate(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const time = Date.parse(`${value}T00:00:00Z`);
  return Number.isFinite(time) && new Date(time).toISOString().slice(0, 10) === value;
}

function parse(value: string | null): unknown {
  try {
    return value === null ? null : JSON.parse(value);
  } catch {
    return null;
  }
}

function completion(gameType: GuestGameType, value: unknown): CompletedResult | null {
  if (!value || typeof value !== 'object') return null;
  const state = value as Record<string, unknown>;
  const { questions: maxQuestions, guesses: maxGuesses } = limits[gameType];
  if (state.is_game_over !== true || typeof state.won !== 'boolean'
    || typeof state.questions_asked !== 'number' || !Number.isInteger(state.questions_asked)
    || state.questions_asked < 0 || state.questions_asked > maxQuestions
    || typeof state.guesses_made !== 'number' || !Number.isInteger(state.guesses_made)
    || state.guesses_made < 1 || state.guesses_made > maxGuesses
    || (!state.won && state.guesses_made !== maxGuesses)) return null;

  return {
    won: state.won,
    questionsAsked: state.questions_asked,
    guessesMade: state.guesses_made,
    points: state.won && typeof state.points === 'number' && Number.isSafeInteger(state.points)
      && state.points >= 0 ? state.points : null,
  };
}

function readResult(gameType: GuestGameType, value: unknown): CompletedResult | null {
  if (!value || typeof value !== 'object') return null;
  const result = value as Record<string, unknown>;
  return completion(gameType, {
    is_game_over: true,
    won: result.won,
    questions_asked: result.questionsAsked,
    guesses_made: result.guessesMade,
    points: result.points,
  });
}

export function notifyGuestHistoryChanged(): void {
  if (typeof window !== 'undefined') window.dispatchEvent(new Event(GUEST_HISTORY_EVENT));
}

// One key per mode/day avoids overwriting unrelated results from another tab.
// Existing valid completions are immutable: restores and sync cannot count twice.
export function recordGuestCompletion(
  gameType: GuestGameType,
  date: string,
  state: unknown,
  today: string,
): boolean {
  const result = completion(gameType, state);
  if (!result || !isDate(date) || !isDate(today) || date > today) return false;
  try {
    const key = `${RESULT_PREFIX}${gameType}_${date}`;
    if (readResult(gameType, parse(localStorage.getItem(key)))) return true;
    localStorage.setItem(key, JSON.stringify(result));
    notifyGuestHistoryChanged();
    return true;
  } catch {
    notifyGuestHistoryChanged();
    return false;
  }
}

export function emptyGuestHistory(today: string): GuestHistory {
  const end = isDate(today) ? Date.parse(`${today}T00:00:00Z`) : Date.now();
  return {
    currentStreak: 0,
    solved: 0,
    bestScore: null,
    days: Array.from({ length: 7 }, (_, index) => ({
      date: new Date(end - (6 - index) * DAY_MS).toISOString().slice(0, 10),
      status: 'unplayed',
    })),
    storageAvailable: false,
  };
}

export function getGuestHistory(gameType: GuestGameType, today: string): GuestHistory {
  const history = emptyGuestHistory(today);
  if (!isDate(today)) return history;
  const results: Record<string, CompletedResult> = {};
  const resultPrefix = `${RESULT_PREFIX}${gameType}_`;
  const snapshotPrefix = `${SNAPSHOT_PREFIX}${gameType}_`;
  try {
    const storage = localStorage;
    // Checking reads alone would incorrectly claim persistence in quota-limited browsers.
    try {
      const probe = `${RESULT_PREFIX}storage_check`;
      storage.setItem(probe, '1');
      storage.removeItem(probe);
      history.storageAvailable = true;
    } catch {
      history.storageAvailable = false;
    }

    const legacy: Array<{ date: string; result: CompletedResult }> = [];
    for (let index = 0; index < storage.length; index++) {
      const key = storage.key(index);
      if (!key) continue;
      const isResult = key.startsWith(resultPrefix);
      if (!isResult && !key.startsWith(snapshotPrefix)) continue;
      const date = key.slice(isResult ? resultPrefix.length : snapshotPrefix.length);
      if (!isDate(date) || date > today) continue;
      const value = parse(storage.getItem(key));
      const result = isResult
        ? readResult(gameType, value)
        : completion(gameType, value && typeof value === 'object' ? (value as Record<string, unknown>).state : null);
      if (!result) continue;
      if (isResult) results[date] = result;
      else legacy.push({ date, result });
    }

    // Backfill only locally completed snapshots, never server/account statistics.
    for (const { date, result } of legacy) {
      if (results[date]) continue;
      results[date] = result;
      try {
        storage.setItem(`${resultPrefix}${date}`, JSON.stringify(result));
      } catch {
        history.storageAvailable = false;
      }
    }
  } catch {
    history.storageAvailable = false;
  }

  for (const result of Object.values(results)) {
    if (!result.won) continue;
    history.solved++;
    if (result.points !== null) history.bestScore = Math.max(history.bestScore ?? 0, result.points);
  }
  for (const day of history.days) {
    const result = results[day.date];
    if (result) day.status = result.won ? 'won' : 'lost';
  }

  let cursor = Date.parse(`${today}T00:00:00Z`);
  if (!results[today]) cursor -= DAY_MS;
  while (results[new Date(cursor).toISOString().slice(0, 10)]?.won) {
    history.currentStreak++;
    cursor -= DAY_MS;
  }
  return history;
}
