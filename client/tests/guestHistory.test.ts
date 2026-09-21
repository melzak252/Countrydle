import assert from 'node:assert/strict';
import { beforeEach, test } from 'node:test';
import { getGuestHistory, recordGuestCompletion } from '../src/lib/guestHistory.ts';

class MemoryStorage {
  data = new Map<string, string>();
  get length() { return this.data.size; }
  key(index: number) { return [...this.data.keys()][index] ?? null; }
  getItem(key: string) { return this.data.get(key) ?? null; }
  setItem(key: string, value: string) { this.data.set(key, value); }
  removeItem(key: string) { this.data.delete(key); }
}

let storage: MemoryStorage;
beforeEach(() => {
  storage = new MemoryStorage();
  Object.defineProperty(globalThis, 'localStorage', { configurable: true, value: storage });
});

const win = { is_game_over: true, won: true, questions_asked: 2, guesses_made: 1, points: 1200 };
const loss = { ...win, won: false, guesses_made: 3, points: undefined };

test('yesterday keeps a streak alive, today loss breaks it, and a gap resets it', () => {
  recordGuestCompletion('country', '2026-09-19', win, '2026-09-21');
  recordGuestCompletion('country', '2026-09-20', win, '2026-09-21');
  assert.equal(getGuestHistory('country', '2026-09-21').currentStreak, 2);
  recordGuestCompletion('country', '2026-09-21', loss, '2026-09-21');
  assert.equal(getGuestHistory('country', '2026-09-21').currentStreak, 0);
  recordGuestCompletion('country', '2026-09-23', win, '2026-09-23');
  assert.equal(getGuestHistory('country', '2026-09-23').currentStreak, 1);
});

test('restored snapshots backfill once and survive snapshot removal independently per mode', () => {
  const key = 'guess_game_country_2026-09-20';
  storage.setItem(key, JSON.stringify({ state: win, questions: [], guesses: [] }));
  assert.equal(getGuestHistory('country', '2026-09-21').solved, 1);
  storage.removeItem(key);
  recordGuestCompletion('country', '2026-09-20', { ...win, points: 9999 }, '2026-09-21');
  recordGuestCompletion('us_states', '2026-09-20', { ...win, points: 1500 }, '2026-09-21');
  const history = getGuestHistory('country', '2026-09-21');
  assert.equal(history.solved, 1);
  assert.equal(history.bestScore, 1200);
  assert.equal(getGuestHistory('us_states', '2026-09-21').bestScore, 1500);
  assert.equal(history.days.length, 7);
  assert.deepEqual(history.days.at(-1), { date: '2026-09-21', status: 'unplayed' });
});

test('corrupt, unfinished, impossible and future results cannot earn history', () => {
  storage.setItem('guess_game_country_2026-09-17', '{broken');
  storage.setItem('guess_game_country_2026-09-18', JSON.stringify({ state: { ...win, won: 'true' } }));
  recordGuestCompletion('country', '2026-09-19', { ...win, is_game_over: false }, '2026-09-21');
  recordGuestCompletion('country', '2026-09-20', { ...win, guesses_made: -1 }, '2026-09-21');
  recordGuestCompletion('country', '2026-09-22', win, '2026-09-21');
  recordGuestCompletion('country', '2026-02-30', win, '2026-09-21');
  assert.equal(getGuestHistory('country', '2026-09-21').solved, 0);
});

test('unavailable storage reports no durable history without throwing', () => {
  Object.defineProperty(globalThis, 'localStorage', { configurable: true, get() { throw new Error('blocked'); } });
  assert.equal(recordGuestCompletion('country', '2026-09-21', win, '2026-09-21'), false);
  assert.equal(getGuestHistory('country', '2026-09-21').storageAvailable, false);
  assert.equal(getGuestHistory('country', '2026-09-21').solved, 0);
});

test('readable but unwritable storage does not promise persistence', () => {
  storage.setItem('guess_game_country_2026-09-20', JSON.stringify({ state: win }));
  storage.setItem = () => { throw new Error('quota exceeded'); };
  const history = getGuestHistory('country', '2026-09-21');
  assert.equal(history.storageAvailable, false);
  assert.equal(history.solved, 1);
});
