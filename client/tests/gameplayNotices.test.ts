import { afterAll, afterEach, beforeEach, describe, expect, spyOn, test } from 'bun:test';
import { gameService } from '../src/services/api';
import { useCountryGameStore } from '../src/stores/gameStore';

const state = { remaining_questions: 10, remaining_guesses: 3, questions_asked: 0, guesses_made: 0, is_game_over: false, won: false };
const ask = spyOn(gameService, 'askQuestion');
const fetchState = spyOn(gameService, 'getState');
const guess = spyOn(gameService, 'makeGuess');

beforeEach(() => {
  useCountryGameStore.getState().resetGame();
  useCountryGameStore.setState({ gameState: { ...state }, dailyDate: '2026-09-26', isGuest: true });
});
afterEach(() => { ask.mockReset(); fetchState.mockReset(); guess.mockReset(); });
afterAll(() => { ask.mockRestore(); fetchState.mockRestore(); guess.mockRestore(); useCountryGameStore.getState().resetGame(); });

describe('Rejected gameplay submissions', () => {
  test('retains rejection context without consuming a question or adding syncable history', async () => {
    ask.mockResolvedValue({ id: 0, original_question: 'What is its capital?', valid: false, explanation: 'This is not a yes-or-no question.', user_id: 0, day_id: 1, asked_at: '2026-09-26T10:00:00Z' });
    const result = await useCountryGameStore.getState().askQuestion('What is its capital?');
    const current = useCountryGameStore.getState();
    expect(result).toBe(false);
    expect(current.gameState).toEqual(state);
    expect(current.questions).toEqual([]);
    expect(current.notices[0].input).toBe('What is its capital?');
    expect(current.notices[0].reason).toBe('This is not a yes-or-no question.');
  });

  test('keeps distinct failed guesses without consuming attempts or losing earlier warnings', async () => {
    guess.mockRejectedValue({ response: { status: 400, data: { detail: 'This location is not eligible in this mode.' } } });
    expect(await useCountryGameStore.getState().makeGuess('Atlantis', 0)).toBe(false);
    expect(await useCountryGameStore.getState().makeGuess('Another place', 0)).toBe(false);
    const current = useCountryGameStore.getState();
    expect(current.gameState).toEqual(state);
    expect(current.guesses).toEqual([]);
    expect(current.notices.map(notice => notice.input)).toEqual(['Atlantis', 'Another place']);
    expect(new Set(current.notices.map(notice => notice.id)).size).toBe(2);
    useCountryGameStore.getState().resetGame();
    expect(useCountryGameStore.getState().notices).toEqual([]);
  });

  test('keeps notices on same-day refresh, clears them on a new puzzle', async () => {
    ask.mockRejectedValue({ response: { status: 429, data: { detail: 'Too many requests' } } });
    await useCountryGameStore.getState().askQuestion('Is it in Europe?');
    const notice = useCountryGameStore.getState().notices[0];
    fetchState.mockResolvedValue({ user: null, date: '2026-09-26', state, questions: [], guesses: [] });
    await useCountryGameStore.getState().fetchGameState();
    expect(useCountryGameStore.getState().notices).toEqual([notice]);
    fetchState.mockResolvedValue({ user: null, date: '2026-09-27', state, questions: [], guesses: [] });
    await useCountryGameStore.getState().fetchGameState();
    expect(useCountryGameStore.getState().notices).toEqual([]);
  });
});
