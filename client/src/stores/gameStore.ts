import { create } from 'zustand';
import type { GameState, Question, Guess } from '../types';
import { gameService, powiatService, usStateService, wojewodztwoService } from '../services/api';
import { useAuthStore } from './authStore';
import { notifyGuestHistoryChanged, recordGuestCompletion } from '../lib/guestHistory';
import type { GuestGameType } from '../lib/guestHistory';
import toast from 'react-hot-toast';

interface GameData {
  gameState: GameState | null;
  questions: Question[];
  guesses: Guess[];
  entities: any[]; // General entities (countries, powiaty, etc.)
  correctEntity: any | null;
  dailyDate: string | null;
  selectedEntityNames: string[];
  isLoading: boolean;
  isGuest: boolean;
  error: string | null;
  gameStartTime: number | null;
}

interface GameActions {
  fetchGameState: () => Promise<void>;
  fetchEntities: () => Promise<void>;
  askQuestion: (questionText: string) => Promise<void>;
  makeGuess: (guessText: string, entityId?: number) => Promise<void>;
  syncGuestData: () => Promise<void>;
  resetGame: () => void;
  toggleEntitySelection: (name: string) => void;
  clearSelection: () => void;
}

const getLocalStateKey = (gameType: string, date: string) => `guess_game_${gameType}_${date}`;

interface GuestSnapshot {
  state: Partial<GameState>;
  questions: Question[];
  guesses: Guess[];
  correctEntity?: unknown;
}

const readGuestSnapshot = (key: string): GuestSnapshot | null => {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object' || !parsed.state || typeof parsed.state !== 'object'
      || !Array.isArray(parsed.questions) || !Array.isArray(parsed.guesses)
      || !parsed.questions.every((q: unknown) => q !== null && typeof q === 'object')
      || !parsed.guesses.every((g: unknown) => g !== null && typeof g === 'object')) return null;
    const state = parsed.state;
    for (const field of ['questions_asked', 'guesses_made', 'remaining_questions', 'remaining_guesses']) {
      if (state[field] !== undefined && (!Number.isInteger(state[field]) || state[field] < 0)) return null;
    }
    if (typeof state.is_game_over !== 'boolean' || typeof state.won !== 'boolean') return null;
    return parsed as GuestSnapshot;
  } catch {
    return null;
  }
};

const saveGuestSnapshot = (key: string, snapshot: GuestSnapshot): void => {
  try {
    localStorage.setItem(key, JSON.stringify(snapshot));
  } catch {
    // A blocked or full browser store must not discard an in-memory move.
    notifyGuestHistoryChanged();
  }
};

const removeGuestSnapshot = (key: string): boolean => {
  try {
    localStorage.removeItem(key);
    return true;
  } catch {
    notifyGuestHistoryChanged();
    return false;
  }
};

const gameLimits = {
    country: { maxQuestions: 10, maxGuesses: 3 },
    powiaty: { maxQuestions: 15, maxGuesses: 3 },
    us_states: { maxQuestions: 8, maxGuesses: 3 },
    wojewodztwa: { maxQuestions: 5, maxGuesses: 2 },
} as const;

const createGuestGameState = (gameType: keyof typeof gameLimits) => ({
    remaining_questions: gameLimits[gameType].maxQuestions,
    remaining_guesses: gameLimits[gameType].maxGuesses,
    questions_asked: 0,
    guesses_made: 0,
    is_game_over: false,
    won: false,
});

const normalizeGameState = (
    gameType: keyof typeof gameLimits,
    state: any,
    questions: Question[],
    guesses: Guess[]
) => {
    const limits = gameLimits[gameType];
    const questionsAsked = questions.length || state?.questions_asked || 0;
    const guessesMade = guesses.length || state?.guesses_made || 0;

    return {
        ...createGuestGameState(gameType),
        ...state,
        questions_asked: questionsAsked,
        guesses_made: guessesMade,
        remaining_questions: Math.max(0, limits.maxQuestions - questionsAsked),
        remaining_guesses: Math.max(0, limits.maxGuesses - guessesMade),
    };
};

const guessMapping: any = {
    country: (g: any) => ({ guess: g.guess, country_id: g.country_id }),
    powiaty: (g: any) => ({ guess: g.guess, powiat_id: g.powiat_id }),
    us_states: (g: any) => ({ guess: g.guess, us_state_id: g.us_state_id }),
    wojewodztwa: (g: any) => ({ guess: g.guess, wojewodztwo_id: g.wojewodztwo_id })
};

// Factory to create stores for different game types
const createGameStore = (gameType: GuestGameType) => {
  const service: any = {
    country: gameService,
    powiaty: powiatService,
    us_states: usStateService,
    wojewodztwa: wojewodztwoService
  }[gameType];

  return create<GameData & GameActions>((set, get) => ({
    gameState: null,
    questions: [],
    guesses: [],
    entities: [],
    correctEntity: null,
    dailyDate: null,
    selectedEntityNames: [],
    isLoading: false,
    isGuest: false,
    error: null,
    gameStartTime: null,
    fetchGameState: async () => {
      set({ isLoading: true, error: null });
      try {
        const data = await service.getState(); 
        
        // Check if the server's idea of the user matches our client's idea
        const clientUser = useAuthStore.getState().user;
        // If client says we are guest, we ARE guest, regardless of what server says (stale cookie protection)
        const isActuallyGuest = data.user === null || clientUser === null;
        
        const localKey = getLocalStateKey(gameType, data.date);
        const localData = readGuestSnapshot(localKey);
        if (localData && data.date) {
            recordGuestCompletion(gameType, data.date, localData.state, data.date);
        }

        // If we are logged in and have guest data, sync it FIRST
        if (!isActuallyGuest && data.date && localData && service.syncGuestData) {
            const parsed = localData;
            if (parsed.questions.length > 0 || parsed.guesses.length > 0) {
                try {
                    // Clear local storage BEFORE calling sync to prevent race conditions
                    // if fetchGameState is called again while sync is in progress
                    if (!removeGuestSnapshot(localKey)) throw new Error('Guest snapshot could not be cleared for sync');
                    
                    await service.syncGuestData({
                        state: normalizeGameState(
                            gameType,
                            parsed.state,
                            parsed.questions,
                            parsed.guesses
                        ),
                        questions: parsed.questions.map((q: any) => q.id),
                        guesses: parsed.guesses.map(guessMapping[gameType]),
                        date: data.date
                    });
                    
                    // Fetch the state again to get the merged data
                    const syncedData = await service.getState();
                    set({
                        gameState: syncedData.state,
                        questions: syncedData.questions,
                        guesses: syncedData.guesses,
                        dailyDate: syncedData.date,
                        isGuest: false,
                        correctEntity: syncedData.country || syncedData.powiat || syncedData.us_state || syncedData.wojewodztwo || null,
                        isLoading: false,
                    });
                    return;
                } catch (syncError) {
                    console.error(`[${gameType}] Failed to sync guest data during fetchGameState:`, syncError);
                    // If sync failed, we might want to restore localData, but usually it's safer to just let it be
                }
            } else {
                removeGuestSnapshot(localKey);
            }
        }

        // Normal flow (guest or already synced user)
        let gameState = data.state;
        let questions = data.questions;
        let guesses = data.guesses;
        let correctEntity = data.country || data.powiat || data.us_state || data.wojewodztwo || null;

        gameState = normalizeGameState(gameType, gameState, questions, guesses) as any;

        if (isActuallyGuest) {
            // If we are guest, we ignore server's questions/guesses (they might belong to a stale session)
            // and load from local storage instead.
            gameState = createGuestGameState(gameType) as any;
            questions = [];
            guesses = [];
            // correctEntity is already set from data.country || ... at line 109

            if (data.date && localData) {
                const parsed = localData;
                questions = parsed.questions || [];
                guesses = parsed.guesses || [];
                gameState = normalizeGameState(gameType, parsed.state, questions, guesses) as any;
                if (parsed.correctEntity) {
                    correctEntity = parsed.correctEntity;
                }

                // Persist the migrated state so old 10/3 guest entries do not stay in localStorage.
                saveGuestSnapshot(localKey, {
                    ...parsed,
                    state: gameState,
                    questions,
                    guesses,
                    correctEntity: parsed.correctEntity || correctEntity,
                });
            }
        }
        
        const currentStartTime = get().gameStartTime;
        const newStartTime = currentStartTime || (!gameState?.is_game_over ? Date.now() : null);

        set({
          gameState,
          questions,
          guesses,
          dailyDate: data.date,
          isGuest: isActuallyGuest,
          correctEntity,
          isLoading: false,
          gameStartTime: newStartTime,
        });
      } catch (e: any) {
        console.error(e);
        set({ error: e.message || 'Failed to load game state', isLoading: false });
      }
    },

    fetchEntities: async () => {
      try {
        let entities = [];
        if (gameType === 'country') entities = await gameService.getCountries();
        else if (gameType === 'powiaty') entities = await powiatService.getPowiaty();
        else if (gameType === 'us_states') entities = await usStateService.getStates();
        else if (gameType === 'wojewodztwa') entities = await wojewodztwoService.getWojewodztwa();
        
        set({ entities });
      } catch (e) {
        console.error(e);
      }
    },

    askQuestion: async (questionText: string) => {
      set({ isLoading: true, error: null });
      try {
        const question = await service.askQuestion(questionText);
        
        if (question && question.valid === false) {
          toast.error(question.explanation || 'Please ask a valid yes/no question.');
          set({ isLoading: false });
          return;
        }
        const { isGuest, dailyDate, gameState, questions, guesses, correctEntity } = get();
        
        if (isGuest && dailyDate && gameState) {
          const newQuestions = [...questions, question];
          const newGameState = {
            ...gameState,
            remaining_questions: gameState.remaining_questions - 1,
            questions_asked: gameState.questions_asked + 1,
          };
          
          saveGuestSnapshot(getLocalStateKey(gameType, dailyDate), {
            state: newGameState,
            questions: newQuestions,
            guesses,
            correctEntity
          });
          
          set({
            questions: newQuestions,
            gameState: newGameState,
            isLoading: false
          });
        } else {
          await get().fetchGameState();
        }
      } catch (e: any) {
         console.error(e);
         if (e.response?.status === 400 && e.response?.data?.detail?.includes("over")) {
             await get().fetchGameState();
         } else {
             set({ error: e.response?.data?.detail || 'Failed to ask question', isLoading: false });
         }
      }
    },

    makeGuess: async (guessText: string, entityId?: number) => {
      set({ isLoading: true, error: null });
      try {
        const elapsed_seconds = get().gameStartTime
          ? Math.max(1, Math.round((Date.now() - (get().gameStartTime as number)) / 1000))
          : undefined;

        const guess = await service.makeGuess(guessText, entityId, elapsed_seconds);
        
        const { isGuest, dailyDate, gameState, questions, guesses, entities } = get();

        if (isGuest && dailyDate && gameState) {
          const guessWithElapsed = { ...guess, elapsed_seconds };
          const newGuesses = [...guesses, guessWithElapsed];
          const isCorrect = guess.answer;
          const newGameState = {
            ...gameState,
            remaining_guesses: gameState.remaining_guesses - 1,
            guesses_made: gameState.guesses_made + 1,
            won: isCorrect || false,
            is_game_over: isCorrect || gameState.remaining_guesses <= 1
          };

          let correctEntity = get().correctEntity;
          if (isCorrect) {
            if (entityId) {
              correctEntity = entities.find(e => e.id === entityId) || null;
            }
            if (!correctEntity) {
              const q = guessText.trim().toLowerCase();
              correctEntity = entities.find(e => (e.name || (e as any).nazwa || '').toLowerCase() === q) || null;
            }
            const maxQ = gameLimits[gameType].maxQuestions;
            const maxG = gameLimits[gameType].maxGuesses;
            const qRatio = Math.max(0, (maxQ - newGameState.questions_asked) / maxQ);
            const qBonus = Math.round(1500 * Math.pow(qRatio, 1.5));
            const gRatio = Math.max(0, (maxG - newGameState.guesses_made + 1) / maxG);
            const gBonus = Math.round(500 * gRatio);
            const speedBonus = elapsed_seconds !== undefined ? Math.max(0, Math.min(300, 300 - elapsed_seconds)) : 0;
            const difficultyBonus = gameType === 'powiaty' ? 500 : gameType === 'us_states' ? 200 : 0;
            newGameState.points = 500 + qBonus + gBonus + speedBonus + 50 + difficultyBonus;
          } else if (newGameState.is_game_over && service.reveal) {
            try {
              correctEntity = await service.reveal();
            } catch (e) {
              console.error("Failed to reveal correct entity", e);
            }
          }

          saveGuestSnapshot(getLocalStateKey(gameType, dailyDate), {
            state: newGameState,
            questions,
            guesses: newGuesses,
            correctEntity
          });
          recordGuestCompletion(gameType, dailyDate, newGameState, dailyDate);

          set({
            guesses: newGuesses,
            gameState: newGameState,
            correctEntity,
            isLoading: false
          });

          // We don't need to fetchGameState here anymore because we already revealed the entity
        } else {
          await get().fetchGameState();
        }
      } catch (e: any) {
          console.error(e);
          if (e.response?.status === 400 && e.response?.data?.detail?.includes("over")) {
              await get().fetchGameState();
          } else {
              set({ error: e.response?.data?.detail || 'Failed to make guess', isLoading: false });
          }
      }
    },
    
    syncGuestData: async () => {
        try {
            const clientUser = useAuthStore.getState().user;
            const { dailyDate } = get();
            
            if (!clientUser || !dailyDate) {
                return;
            }

            const localKey = getLocalStateKey(gameType, dailyDate);
            const localData = readGuestSnapshot(localKey);
            
            if (localData && service.syncGuestData) {
                const parsed = localData;
                recordGuestCompletion(gameType, dailyDate, parsed.state, dailyDate);
                if (parsed.questions.length > 0 || parsed.guesses.length > 0) {
                    // Clear local storage BEFORE calling sync to prevent double sync
                    if (!removeGuestSnapshot(localKey)) return;
                    
                    await service.syncGuestData({
                        state: normalizeGameState(
                            gameType,
                            parsed.state,
                            parsed.questions,
                            parsed.guesses
                        ),
                        questions: parsed.questions.map((q: any) => q.id),
                        guesses: parsed.guesses.map(guessMapping[gameType]),
                        date: dailyDate
                    });
                    await get().fetchGameState();
                } else {
                    removeGuestSnapshot(localKey);
                }
            }
        } catch (e) {
            console.error(`[${gameType}] Failed to sync guest data:`, e);
        }
    },

    resetGame: () => set({ 
        gameState: null, 
        questions: [], 
        guesses: [], 
        selectedEntityNames: [], 
        correctEntity: null, 
        isGuest: false,
        error: null 
    }),
    
    toggleEntitySelection: (name: string) => {
      const { selectedEntityNames } = get();
      if (selectedEntityNames.includes(name)) {
        set({ selectedEntityNames: selectedEntityNames.filter(n => n !== name) });
        return;
      }
      set({ selectedEntityNames: [...selectedEntityNames, name] });
    },
    
    clearSelection: () => set({ selectedEntityNames: [] })
  }));
};

// Export specialized stores
export const useCountryGameStore = createGameStore('country');
export const usePowiatyGameStore = createGameStore('powiaty');
export const useUSStatesGameStore = createGameStore('us_states');
export const useWojewodztwaGameStore = createGameStore('wojewodztwa');

// Default export for backward compatibility (pointing to country store)
export const useGameStore = useCountryGameStore;
