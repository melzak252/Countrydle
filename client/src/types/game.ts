export interface GameState<TQuestion, TGuess, TResult> {
  questionsHistory: TQuestion[];
  guessHistory: TGuess[];
  remainingQuestions: number;
  remainingGuesses: number;
  isGameOver: boolean;
  won: boolean;
  result: TResult | null;
  loading: boolean;
  error: string | null;
  gameDate: string;
  points: number;
}

export interface GameActions {
  loadGameState(): Promise<void>;
  askQuestion(question: string): Promise<void>;
  makeGuess(guess: string, id?: number): Promise<void>;
  endGame(): Promise<void>;
  resetState(): void;
}

export interface GameConfig {
  maxQuestions: number;
  maxGuesses: number;
}
