import { create } from 'zustand';
import type { GameState, Question, Guess, FlagdleCountry, FlagdleGuess, FlagdleState, Country } from '../types';
import {
  gameService,
  powiatService,
  usStateService,
  wojewodztwoService,
  europeService,
  asiaService,
  africaService,
  americasService,
  flagdleService,
} from '../services/api';
import { useAuthStore } from './authStore';
import { notifyGuestHistoryChanged, recordGuestCompletion } from '../lib/guestHistory';
import { mapClickColor, toggleMapMarking } from '../lib/mapMarkings';
import { gameplayFailure, type GameplayNotice, type GameplayNoticeInput } from '../lib/gameplayNotices';
import toast from 'react-hot-toast';

export type MapMarkerColor = 'green' | 'red' | 'blue' | 'orange';

interface GameData {
  notices: GameplayNotice[];
  gameState: GameState | null;
  questions: Question[];
  guesses: Guess[];
  entities: any[]; // General entities (countries, powiaty, etc.)
  correctEntity: any | null;
  dailyDate: string | null;
  entityMarkings: Record<string, MapMarkerColor>;
  activeMarkerColor: MapMarkerColor;
  selectedEntityNames: string[];
  candidateEntities: string[];
  eliminatedEntities: string[];
  mapInteractionMode: 'candidate' | 'eliminate';
  isLoading: boolean;
  isGuest: boolean;
  error: string | null;
  gameStartTime: number | null;
}

interface GameActions {
  fetchGameState: () => Promise<void>;
  fetchEntities: () => Promise<void>;
  askQuestion: (questionText: string) => Promise<void | boolean>;
  makeGuess: (guessText: string, entityId?: number) => Promise<void | boolean>;
  addNotice: (notice: GameplayNoticeInput) => void;
  syncGuestData: () => Promise<void>;
  resetGame: () => void;
  toggleEntitySelection: (name: string) => void;
  clearSelection: () => void;
  setActiveMarkerColor: (color: MapMarkerColor) => void;
  toggleEntityMarker: (name: string, color?: MapMarkerColor) => void;
  setMapInteractionMode: (mode: 'candidate' | 'eliminate') => void;
  toggleEntityCandidate: (name: string) => void;
  toggleEntityEliminated: (name: string) => void;
  handleEntityMapClick: (name: string, isSecondary?: boolean) => void;
  clearMapMarkings: () => void;
}
const getLocalStateKey = (gameType: string, date: string) => `guess_game_${gameType}_${date}`;

const isAnsweredQuestion = (question: Question | null | undefined): question is Question & { valid: true; answer: boolean } =>
  question?.valid === true && typeof question.answer === 'boolean';

interface GuestSnapshot {
  state: Partial<GameState>;
  questions: Question[];
  guesses: Guess[];
  correctEntity?: unknown;
}

const readGuestSnapshot = (key: string): { raw: string; snapshot: GuestSnapshot } | null => {
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
    parsed.questions = parsed.questions.filter(isAnsweredQuestion);
    return { raw, snapshot: parsed as GuestSnapshot };
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

const removeGuestSnapshot = (key: string, expectedRaw: string): boolean => {
  try {
    if (localStorage.getItem(key) !== expectedRaw) return false;
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
    europe: { maxQuestions: 8, maxGuesses: 3 },
    asia: { maxQuestions: 8, maxGuesses: 3 },
    africa: { maxQuestions: 8, maxGuesses: 3 },
    americas: { maxQuestions: 8, maxGuesses: 3 },
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
    const questionsAsked = questions.filter(isAnsweredQuestion).length;
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

type SyncedGuess = Pick<Guess, 'guess' | 'country_id' | 'powiat_id' | 'us_state_id' | 'wojewodztwo_id' | 'elapsed_seconds'>;
const guessMapping: Record<MapGameType, (guess: Guess) => SyncedGuess> = {
    country: (g: Guess) => ({ guess: g.guess, country_id: g.country_id, elapsed_seconds: g.elapsed_seconds }),
    powiaty: (g: Guess) => ({ guess: g.guess, powiat_id: g.powiat_id, elapsed_seconds: g.elapsed_seconds }),
    us_states: (g: Guess) => ({ guess: g.guess, us_state_id: g.us_state_id, elapsed_seconds: g.elapsed_seconds }),
    wojewodztwa: (g: Guess) => ({ guess: g.guess, wojewodztwo_id: g.wojewodztwo_id, elapsed_seconds: g.elapsed_seconds }),
    europe: (g: Guess) => ({ guess: g.guess, country_id: g.country_id, elapsed_seconds: g.elapsed_seconds }),
    asia: (g: Guess) => ({ guess: g.guess, country_id: g.country_id, elapsed_seconds: g.elapsed_seconds }),
    africa: (g: Guess) => ({ guess: g.guess, country_id: g.country_id, elapsed_seconds: g.elapsed_seconds }),
    americas: (g: Guess) => ({ guess: g.guess, country_id: g.country_id, elapsed_seconds: g.elapsed_seconds }),
};

type MapGameType = 'country' | 'powiaty' | 'us_states' | 'wojewodztwa' | 'europe' | 'asia' | 'africa' | 'americas';

// Factory to create stores for different game types
const createGameStore = (gameType: MapGameType) => {
  const service: any = {
    country: gameService,
    powiaty: powiatService,
    us_states: usStateService,
    wojewodztwa: wojewodztwoService,
    europe: europeService,
    asia: asiaService,
    africa: africaService,
    americas: americasService,
  }[gameType];

  return create<GameData & GameActions>((set, get) => ({
    notices: [],
    addNotice: (notice: GameplayNoticeInput) => set(state => ({
      notices: [...state.notices, { ...notice, id: crypto.randomUUID(), createdAt: new Date().toISOString() }],
    })),
    gameState: null,
    questions: [],
    guesses: [],
    entities: [],
    correctEntity: null,
    dailyDate: null,
    entityMarkings: {},
    activeMarkerColor: 'green',
    selectedEntityNames: [],
    candidateEntities: [],
    eliminatedEntities: [],
    mapInteractionMode: 'candidate',
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
        const stored = readGuestSnapshot(localKey);
        const localData = stored?.snapshot;
        if (localData && data.date) {
            recordGuestCompletion(gameType, data.date, normalizeGameState(
                gameType, localData.state, localData.questions, localData.guesses
            ), data.date);
        }

        // If we are logged in and have guest data, sync it FIRST
        if (!isActuallyGuest && data.date && localData && service.syncGuestData) {
            const parsed = localData;
            if (parsed.questions.length > 0 || parsed.guesses.length > 0) {
                try {
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
                    removeGuestSnapshot(localKey, stored.raw);
                    
                    // Fetch the state again to get the merged data
                    const syncedData = await service.getState();
                    set(state => ({
                        gameState: syncedData.state,
                        questions: syncedData.questions.filter(isAnsweredQuestion),
                        guesses: syncedData.guesses,
                        dailyDate: syncedData.date,
                        notices: state.dailyDate === syncedData.date ? state.notices : [],
                        isGuest: false,
                        correctEntity: syncedData.country || syncedData.powiat || syncedData.us_state || syncedData.wojewodztwo || null,
                        isLoading: false,
                    }));
                    return;
                } catch (syncError) {
                    console.error(`[${gameType}] Failed to sync guest data during fetchGameState:`, syncError);
                }
            } else {
                removeGuestSnapshot(localKey, stored.raw);
            }
        }

        // Normal flow (guest or already synced user)
        let gameState = data.state;
        let questions = data.questions.filter(isAnsweredQuestion);
        let guesses = data.guesses;
        let correctEntity = data.country || data.powiat || data.us_state || data.wojewodztwo || null;


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

        set(state => ({
          gameState,
          questions,
          guesses,
          dailyDate: data.date,
          notices: state.dailyDate === data.date ? state.notices : [],
          isGuest: isActuallyGuest,
          correctEntity,
          isLoading: false,
          gameStartTime: newStartTime,
        }));
      } catch (e: any) {
        console.error(e);
        set({ error: e.message || 'Failed to load game state', isLoading: false });
      }
    },

    fetchEntities: async () => {
      try {
        let entities: any[] = [];
        if (gameType === 'country') entities = await gameService.getCountries();
        else if (gameType === 'powiaty') entities = await powiatService.getPowiaty();
        else if (gameType === 'us_states') entities = await usStateService.getStates();
        else if (gameType === 'wojewodztwa') entities = await wojewodztwoService.getWojewodztwa();
        else if (['europe', 'asia', 'africa', 'americas'].includes(gameType)) {
          entities = await service.getCountries();
        }
        set({ entities });
      } catch (e) {
        console.error(e);
      }
    },

    askQuestion: async (questionText: string) => {
      const current = get();
      if (current.isLoading || !current.gameState || current.gameState.is_game_over
        || current.gameState.remaining_questions <= 0) return;
      set({ isLoading: true, error: null });
      try {
        const question = await service.askQuestion(questionText);
        
        if (!isAnsweredQuestion(question)) {
          get().addNotice({
            action: 'question',
            input: questionText,
            title: 'Question not answered',
            reason: typeof question?.explanation === 'string' && question.explanation.trim()
              ? question.explanation
              : 'The game could not produce a reliable yes-or-no answer to this question.',
            nextStep: 'Try a more specific yes-or-no question about a geographic fact, such as location, borders, or coastline.',
          });
          set({ isLoading: false });
          return false;
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
      } catch (e: unknown) {
         console.error(e);
         get().addNotice(gameplayFailure('question', questionText, e));
         if (typeof e === 'object' && e !== null && 'response' in e) {
           const response = e.response;
           if (typeof response === 'object' && response !== null && 'status' in response &&
             response.status === 400 && 'data' in response &&
             typeof response.data === 'object' && response.data !== null && 'detail' in response.data &&
             typeof response.data.detail === 'string' && response.data.detail.includes('over')) {
             await get().fetchGameState();
             return false;
           }
         }
         set({ error: e instanceof Error ? e.message : 'Failed to ask question', isLoading: false });
         return false;
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
      } catch (e: unknown) {
          console.error(e);
          get().addNotice(gameplayFailure('guess', guessText, e));
          if (typeof e === 'object' && e !== null && 'response' in e) {
            const response = e.response;
            if (typeof response === 'object' && response !== null && 'status' in response &&
              response.status === 400 && 'data' in response &&
              typeof response.data === 'object' && response.data !== null && 'detail' in response.data &&
              typeof response.data.detail === 'string' && response.data.detail.includes('over')) {
              await get().fetchGameState();
              return false;
            }
          }
          set({ error: e instanceof Error ? e.message : 'Failed to make guess', isLoading: false });
          return false;
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
            const stored = readGuestSnapshot(localKey);
            const localData = stored?.snapshot;
            
            if (localData && service.syncGuestData) {
                const parsed = localData;
                recordGuestCompletion(gameType, dailyDate, normalizeGameState(
                    gameType, parsed.state, parsed.questions, parsed.guesses
                ), dailyDate);
                if (parsed.questions.length > 0 || parsed.guesses.length > 0) {
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
                    if (removeGuestSnapshot(localKey, stored.raw)) {
                        await get().fetchGameState();
                    }
                } else {
                    removeGuestSnapshot(localKey, stored.raw);
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
        notices: [],
        entityMarkings: {},
        activeMarkerColor: 'green',
        selectedEntityNames: [], 
        candidateEntities: [],
        eliminatedEntities: [],
        correctEntity: null, 
        isGuest: false,
        error: null 
    }),

    setActiveMarkerColor: (color: MapMarkerColor) => set({
      activeMarkerColor: color,
      mapInteractionMode: color === 'red' ? 'eliminate' : 'candidate',
    }),

    setMapInteractionMode: (mode: 'candidate' | 'eliminate') => set({
      mapInteractionMode: mode,
      activeMarkerColor: mode === 'eliminate' ? 'red' : 'green',
    }),

    toggleEntityMarker: (name: string, color?: MapMarkerColor) => {
      const { entityMarkings } = get();
      const targetColor = color || get().activeMarkerColor;
      const nextMarkings = toggleMapMarking(entityMarkings, name, targetColor);

      const nextCandidate = Object.keys(nextMarkings).filter(k => nextMarkings[k] === 'green');
      const nextEliminated = Object.keys(nextMarkings).filter(k => nextMarkings[k] === 'red');

      set({
        entityMarkings: nextMarkings,
        candidateEntities: nextCandidate,
        eliminatedEntities: nextEliminated,
        selectedEntityNames: nextCandidate,
      });
    },

    toggleEntityCandidate: (name: string) => {
      get().toggleEntityMarker(name, 'green');
    },

    toggleEntityEliminated: (name: string) => {
      get().toggleEntityMarker(name, 'red');
    },

    handleEntityMapClick: (name: string, isSecondary = false) => {
      const { activeMarkerColor } = get();
      get().toggleEntityMarker(name, mapClickColor(activeMarkerColor, isSecondary));
    },
    
    toggleEntitySelection: (name: string) => {
      get().handleEntityMapClick(name, false);
    },
    
    clearMapMarkings: () => set({
      entityMarkings: {},
      candidateEntities: [],
      eliminatedEntities: [],
      selectedEntityNames: [],
    }),

    clearSelection: () => get().clearMapMarkings(),
  }));
};

// Export specialized stores
export const useCountryGameStore = createGameStore('country');
export const usePowiatyGameStore = createGameStore('powiaty');
export const useUSStatesGameStore = createGameStore('us_states');
export const useWojewodztwaGameStore = createGameStore('wojewodztwa');


export const useEuropeGameStore = createGameStore('europe');
export const useAsiaGameStore = createGameStore('asia');
export const useAfricaGameStore = createGameStore('africa');
export const useAmericasGameStore = createGameStore('americas');

export const getContinentalStore = (continent: 'europe' | 'asia' | 'africa' | 'americas') => {
  switch (continent) {
    case 'europe': return useEuropeGameStore;
    case 'asia': return useAsiaGameStore;
    case 'africa': return useAfricaGameStore;
    case 'americas': return useAmericasGameStore;
  }
};
interface FlagdleStateData {
  gameState: FlagdleState | null;
  guesses: FlagdleGuess[];
  questions: Question[];
  stage: number;
  flagAssetUrl: string | null;
  correctCountry: Country | null;
  countries: FlagdleCountry[];
  dailyDate: string | null;
  isLoading: boolean;
  isGuest: boolean;
  error: string | null;
  startTime: number | null;

  fetchGameState: () => Promise<void>;
  fetchCountries: () => Promise<void>;
  askQuestion: (questionText: string) => Promise<void>;
  makeGuess: (countryName: string, countryId?: number) => Promise<void>;
  syncGuestData: () => Promise<void>;
  resetGame: () => void;
}

export const useFlagdleGameStore = create<FlagdleStateData>((set, get) => ({
  gameState: null,
  guesses: [],
  questions: [],
  stage: 1,
  flagAssetUrl: null,
  correctCountry: null,
  countries: [],
  dailyDate: null,
  isLoading: false,
  isGuest: false,
  error: null,
  startTime: null,

  fetchCountries: async () => {
    try {
      const countries = await flagdleService.getCountries();
      set({ countries });
    } catch (err) {
      console.error('Failed to fetch Flagdle countries', err);
    }
  },

  fetchGameState: async () => {
    set({ isLoading: true, error: null });
    try {
      const data = await flagdleService.getState();
      const localKey = `guess_game_flagdle_${data.date}`;
      const localRaw = localStorage.getItem(localKey);
      let localGuesses: FlagdleGuess[] = [];
      let localQuestions: Question[] = [];
      let effectiveState = data.state;
      const isGuest = !data.user;

      if (localRaw) {
        try {
          const parsed = JSON.parse(localRaw);
          if (isGuest && parsed && Array.isArray(parsed.guesses)) {
            localGuesses = parsed.guesses;
          }
          if (parsed && Array.isArray(parsed.questions)) {
            localQuestions = parsed.questions.filter(isAnsweredQuestion);
            saveGuestSnapshot(localKey, { ...parsed, questions: localQuestions });
          }
          if (isGuest && parsed && parsed.state) {
            effectiveState = { ...effectiveState, ...parsed.state };
          }
          if (effectiveState.is_game_over) {
            recordGuestCompletion('flagdle', data.date, effectiveState, data.date);
            notifyGuestHistoryChanged();
          }
        } catch {
          // ignore invalid local storage
        }
      }

      const combinedGuesses = isGuest && localGuesses.length > 0 ? localGuesses : data.guesses;
      const calculatedStage = effectiveState.is_game_over
        ? 12
        : Math.min(12, Math.max(effectiveState.revealed_stage, combinedGuesses.length + 1));

      let revealedCountry = data.country || null;
      if (effectiveState.is_game_over && !revealedCountry) {
        try {
          const endRes = await flagdleService.getEndState();
          revealedCountry = endRes.country || null;
        } catch {
          // silent fallback
        }
      }

      set({
        gameState: effectiveState,
        guesses: combinedGuesses,
        questions: localQuestions,
        stage: calculatedStage,
        flagAssetUrl: data.flag_asset_url || null,
        correctCountry: revealedCountry,
        dailyDate: data.date,
        isGuest,
        isLoading: false,
        startTime: Date.now(),
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to fetch Flagdle game state.';
      set({ error: msg, isLoading: false });
    }
  },

  askQuestion: async (questionText: string) => {
    if (get().isLoading || get().gameState?.is_game_over) return;
    set({ isLoading: true, error: null });
    try {
      const q = await flagdleService.askQuestion(questionText);
      if (!isAnsweredQuestion(q)) {
        toast.error(q?.explanation || 'Could not verify this question. Your turn was not deducted.');
        set({ isLoading: false });
        return;
      }
      const nextQuestions = [...get().questions, q];
      const { dailyDate, gameState } = get();
      if (dailyDate && gameState) {
        const localKey = `guess_game_flagdle_${dailyDate}`;
        const existing = localStorage.getItem(localKey);
        const parsed = existing ? JSON.parse(existing) : {};
        localStorage.setItem(localKey, JSON.stringify({ ...parsed, state: gameState, questions: nextQuestions }));
      }
      set({ questions: nextQuestions, isLoading: false });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to evaluate question.';
      toast.error(msg);
      set({ isLoading: false });
    }
  },
  makeGuess: async (countryName: string, countryId?: number) => {
    const { gameState, startTime, dailyDate, isGuest } = get();
    if (!gameState || gameState.is_game_over || gameState.remaining_guesses <= 0) return;

    set({ isLoading: true });
    try {
      const elapsed = startTime ? Math.round((Date.now() - startTime) / 1000) : 0;
      const guessRes = await flagdleService.makeGuess({
        guess: countryName,
        country_id: countryId,
        elapsed_seconds: elapsed,
      });
      if (!isGuest && (guessRes.answer || get().guesses.length + 1 >= 12)) {
        await get().fetchGameState();
        return;
      }

      const nextGuesses = [...get().guesses, { ...guessRes, elapsed_seconds: elapsed }];
      const isWon = guessRes.answer;
      const isGameOver = isWon || nextGuesses.length >= 12;
      const nextStage = isGameOver ? 12 : Math.min(12, nextGuesses.length + 1);

      const nextState: FlagdleState = {
        ...gameState,
        guesses_made: nextGuesses.length,
        remaining_guesses: Math.max(0, 12 - nextGuesses.length),
        revealed_stage: nextStage,
        is_game_over: isGameOver,
        won: isWon,
      };
      if (isWon) {
        const guessBonuses = [1500, 1300, 1100, 950, 800, 650, 500, 400, 300, 200, 100, 50];
        const speedBonus = elapsed > 0
          ? Math.floor(300 * Math.pow(Math.max(0, (180 - elapsed) / 180), 1.5))
          : 0;
        nextState.points = 500 + guessBonuses[nextGuesses.length - 1] + speedBonus + 50;
      } else {
        nextState.points = 0;
      }

      if (dailyDate) {
        localStorage.setItem(
          `guess_game_flagdle_${dailyDate}`,
          JSON.stringify({ state: nextState, guesses: nextGuesses })
        );
      }

      let revealedCountry = get().correctCountry;
      if (isWon) {
        const found = get().countries.find(
          (c) => c.name.toLowerCase() === countryName.trim().toLowerCase()
        );
        revealedCountry = (found as any) || { id: countryId || 0, name: countryName };
      } else if (isGameOver) {
        try {
          const endState = await flagdleService.getEndState();
          revealedCountry = (endState.country as any) || null;
        } catch {
          try {
            const rev = await flagdleService.reveal();
            revealedCountry = (rev as any) || null;
          } catch {
            // fallback
          }
        }
      }

      if (isGameOver && isGuest && dailyDate) {
        recordGuestCompletion('flagdle', dailyDate, nextState, dailyDate);
        notifyGuestHistoryChanged();
      }

      set({
        gameState: nextState,
        guesses: nextGuesses,
        stage: nextStage,
        correctCountry: revealedCountry,
        isLoading: false,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Error submitting guess.';
      toast.error(msg);
      set({ isLoading: false });
    }
  },

  syncGuestData: async () => {
    const { dailyDate } = get();
    if (!dailyDate) return;
    const localKey = `guess_game_flagdle_${dailyDate}`;
    const localRaw = localStorage.getItem(localKey);
    if (!localRaw) return;

    try {
      const snapshot = JSON.parse(localRaw);
      await flagdleService.syncGuestData({
        date: dailyDate,
        state: snapshot.state,
        guesses: (snapshot.guesses || []).map((g: FlagdleGuess) => ({
          guess: g.guess,
          country_id: g.country_id,
          elapsed_seconds: g.elapsed_seconds,
        })),
      });
      localStorage.removeItem(localKey);
      await get().fetchGameState();
    } catch (err) {
      console.error('Failed to sync Flagdle guest data', err);
    }
  },

  resetGame: () => {
    set({
      gameState: null,
      guesses: [],
      questions: [],
      stage: 1,
      flagAssetUrl: null,
      correctCountry: null,
      isLoading: false,
      error: null,
    });
  },
}));
// Default export for backward compatibility (pointing to country store)
export const useGameStore = useCountryGameStore;
