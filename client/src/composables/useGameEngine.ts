import { ref } from 'vue';
import type { GameState } from '../types/game';

export function useGameEngine<TQuestion, TGuess, TResult>(
  initialConfig: {
    maxQuestions: number;
    maxGuesses: number;
  }
) {
  const state = ref<GameState<TQuestion, TGuess, TResult>>({
    questionsHistory: [],
    guessHistory: [],
    remainingQuestions: initialConfig.maxQuestions,
    remainingGuesses: initialConfig.maxGuesses,
    isGameOver: false,
    won: false,
    result: null,
    loading: false,
    error: null,
    gameDate: '',
    points: 0,
  });

  const executeAction = async (actionName: string, action: () => Promise<void>) => {
    if (state.value.isGameOver && 
        actionName !== 'loadGameState' && 
        actionName !== 'getHistory' && 
        actionName !== 'getLeaderboard' &&
        actionName !== 'endGame' // Allow ending the game to fetch results
       ) return;
    
    state.value.loading = true;
    state.value.error = null;
    try {
      await action();
    } catch (err) {
      state.value.error = `Failed to ${actionName}`;
      console.error(err);
    } finally {
      state.value.loading = false;
    }
  };

  const addQuestion = (question: TQuestion) => {
    state.value.questionsHistory.push(question);
    if (state.value.remainingQuestions > 0) {
      state.value.remainingQuestions--;
    }
  };

  const addGuess = (guess: TGuess) => {
    state.value.guessHistory.push(guess);
    if (state.value.remainingGuesses > 0) {
      state.value.remainingGuesses--;
    }
  };

  const setGameOver = (won: boolean, result?: TResult) => {
    state.value.isGameOver = true;
    state.value.won = won;
    if (result) {
      state.value.result = result;
    }
  };

  const resetState = (defaults: Partial<GameState<TQuestion, TGuess, TResult>> = {}) => {
    state.value = {
      ...state.value,
      questionsHistory: [],
      guessHistory: [],
      remainingQuestions: initialConfig.maxQuestions,
      remainingGuesses: initialConfig.maxGuesses,
      isGameOver: false,
      won: false,
      result: null,
      error: null,
      points: 0,
      ...defaults
    };
  };

  const updateStateFromApi = (data: any) => {
    if (data.questions) state.value.questionsHistory = data.questions;
    if (data.guesses) state.value.guessHistory = data.guesses;
    if (data.state) {
      state.value.remainingQuestions = data.state.remaining_questions;
      state.value.remainingGuesses = data.state.remaining_guesses;
      state.value.isGameOver = data.state.is_game_over;
      state.value.won = data.state.won;
      state.value.points = data.state.points;
    }
    if (data.date) state.value.gameDate = data.date;
    if (data.country) state.value.result = data.country; // Default mapping, can be overridden
  };

  return {
    state,
    executeAction,
    addQuestion,
    addGuess,
    setGameOver,
    resetState,
    updateStateFromApi
  };
}
