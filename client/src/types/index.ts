export interface User {
  id: number;
  username: string | null;
  email: string;
  verified: boolean;
  avatar_url?: string;
}


export interface Country {
  id: number;
  name: string;
  iso2: string;
  iso3: string;
}

export interface Question {
  id: number;
  original_question: string;
  question?: string;
  valid: boolean;
  answer?: boolean;
  user_id: number;
  day_id: number;
  asked_at: string;
  explanation?: string;
}

export interface Guess {
  id: number;
  guess: string;
  country_id?: number;
  answer?: boolean;
  guessed_at: string;
}

export interface GameState {
  remaining_questions: number;
  remaining_guesses: number;
  questions_asked: number;
  guesses_made: number;
  is_game_over: boolean;
  won: boolean;
  points?: number;
}

export interface GameResponse {
  user: User;
  date: string;
  state: GameState;
  questions: Question[];
  guesses: Guess[];
  country?: Country; // Only present in end state
}

export interface CountryDisplay {
    id: number;
    name: string;
    iso2: string;
    iso3: string;
}
