import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { apiService } from '../services/api';
import { useGameEngine } from '../composables/useGameEngine';
import type { GameState } from '../types/game';

export interface Question {
  original_question: string;
  question: string;
  answer: boolean | null;
  valid: boolean;
  explanation?: string;
}

export interface Country { 
  name: string;
  official_name: string;
}

export interface Guess {
  guess: string;
  answer: boolean | null;
}

export const useCountrydleStore = defineStore('countrydle', () => {
  // Initialize Game Engine
  const { 
    state: gameState, 
    executeAction, 
    updateStateFromApi, 
    resetState: resetEngineState 
  } = useGameEngine<Question, Guess, Country>({
    maxQuestions: 10,
    maxGuesses: 3
  });

  // Specific State
  const selectedCountries = ref<string[]>([]);
  const leaderboard = ref<any[]>([]);
  const countrydleHistory = ref<any[]>([]);
  const countriesCount = ref<any[]>([]);

  // Computed properties for backward compatibility and ease of use
  const questionsHistory = computed(() => gameState.value.questionsHistory);
  const guessHistory = computed(() => gameState.value.guessHistory);
  const remainingQuestions = computed(() => gameState.value.remainingQuestions);
  const remainingGuesses = computed(() => gameState.value.remainingGuesses);
  const isGameOver = computed(() => gameState.value.isGameOver);
  const won = computed(() => gameState.value.won);
  const correctCountry = computed(() => gameState.value.result);
  const loading = computed(() => gameState.value.loading);
  const error = computed(() => gameState.value.error);
  const gameDate = computed(() => gameState.value.gameDate);
  const points = computed(() => gameState.value.points);
  
  const questionLimitReached = computed(() => gameState.value.remainingQuestions <= 0);
  const guessLimitReached = computed(() => gameState.value.remainingGuesses <= 0);

  // Actions
  const resetState = () => {
    resetEngineState();
    selectedCountries.value = [];
    // Don't reset history/leaderboard as they are separate data
  };

  const resetCorrect = () => {
    gameState.value.isGameOver = false;
    gameState.value.won = false;
    gameState.value.result = null;
  };

  const loadGameState = async () => {
    resetCorrect();
    const today = new Date().toISOString().split('T')[0];
    if (gameState.value.gameDate !== today) {
      resetState();
    }

    await executeAction('loadGameState', async () => {
      const response = await apiService.getGameState();
      updateStateFromApi(response.data);
      if (response.data.state.is_game_over) {
        // If game is over, ensure we have the result (country)
        if (!gameState.value.result) {
           // Call API directly to avoid nested executeAction state conflicts
           const endResponse = await apiService.endGame();
           updateStateFromApi(endResponse.data);
        }
      }
    });
  };

  const askQuestion = async (question: string) => {
    await executeAction('askQuestion', async () => {
      const response = await apiService.askQuestion(question);
      // Manually update state or re-fetch? 
      // Original code pushed to history and decremented.
      // useGameEngine has addQuestion helper but we can also just push to state.
      gameState.value.questionsHistory.push(response.data);
      gameState.value.remainingQuestions--;
    });
  };

  const makeGuess = async (guess: string, country_id?: number) => {
    await executeAction('makeGuess', async () => {
      const response = await apiService.makeGuess(guess, country_id);
      gameState.value.guessHistory.push({ guess, answer: response.data.answer });
      gameState.value.remainingGuesses--;

      if (response.data.answer || gameState.value.remainingGuesses <= 0) {
        await endGame();
      }
    });
  };

  const endGame = async () => {
    await executeAction('endGame', async () => {
      const response = await apiService.endGame();
      // The API returns full state in endGame, so we can use updateStateFromApi
      // But we need to make sure 'country' is mapped to 'result'
      updateStateFromApi(response.data);
      // Explicitly set result if updateStateFromApi didn't catch it (it does map .country to .result)
    });
  };

  const handleCountryClick = (countryName: string) => {
    const index = selectedCountries.value.indexOf(countryName);
    if (index === -1) {
      selectedCountries.value.push(countryName);
      return true;
    } else {
      selectedCountries.value.splice(index, 1);
      return false;
    }
  };

  const getCountrydleHistory = async () => {
    await executeAction('getHistory', async () => {
      const response = await apiService.getCountrydleHistory();
      countrydleHistory.value = response.data.daily_countries;
      countriesCount.value = response.data.countries_count;
    });
  };

  const getLeaderboard = async () => {
    await executeAction('getLeaderboard', async () => {
      const response = await apiService.getLeaderboard();
      leaderboard.value = response.data;
    });
  };

  return {
    // State & Computed
    questionsHistory,
    guessHistory,
    remainingQuestions,
    remainingGuesses,
    isGameOver,
    won,
    correctCountry,
    loading,
    error,
    gameDate,
    points,
    selectedCountries,
    leaderboard,
    countrydleHistory,
    countriesCount,
    questionLimitReached,
    guessLimitReached,

    // Actions
    loadGameState,
    askQuestion,
    makeGuess,
    endGame,
    handleCountryClick,
    resetState,
    resetCorrect,
    getCountrydleHistory,
    getLeaderboard,
    gameState // Expose internal state for persistence
  };
}, {
  persist: {
    storage: localStorage,
    paths: ['gameState', 'selectedCountries'],
  },
});

