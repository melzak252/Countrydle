export interface User {
  id: number;
  username: string | null;
  email: string;
  verified: boolean;
  is_admin: boolean;
  avatar_url?: string;
}


export interface Country {
  id: number;
  name: string;
  official_name?: string | null;
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
  report_token?: string | null;
}

export type AnswerReportMode = 'countrydle' | 'us_statedle' | 'powiatdle' | 'wojewodztwodle';
export type AnswerReportStatus = 'open' | 'reviewed' | 'all';

export interface AnswerReport {
  id: number;
  mode: AnswerReportMode;
  question_id: number;
  comment: string;
  created_at: string;
  reviewed_at: string | null;
  reporter_username: string | null;
  details: {
    original_question: string;
    question: string | null;
    valid: boolean;
    answer: boolean | null;
    explanation: string;
    context: string | null;
    day_id: number;
    game_date: string;
    target_name: string;
    server_version: string | null;
  };
}

export type QuestionTestMode = AnswerReportMode | 'europe' | 'asia' | 'africa' | 'americas' | 'flagdle';

export interface QuestionTestEntity {
  id: number;
  name: string;
}

export interface QuestionTestRequest {
  mode: QuestionTestMode;
  entity_id: number;
  question: string;
}

export interface QuestionTestResult {
  mode: QuestionTestMode;
  entity: QuestionTestEntity;
  original_question: string;
  question: string | null;
  valid: boolean;
  answer: boolean | null;
  explanation: string;
  context: string | null;
  source: 'local_kb' | 'local_planner' | 'fallback' | 'flag_kb';
  server_version: string;
  duration_ms: number;
  plan: Record<string, unknown> | null;
}

export interface Guess {
  id: number;
  guess: string;
  country_id?: number;
  us_state_id?: number;
  wojewodztwo_id?: number;
  powiat_id?: number;
  answer?: boolean;
  guessed_at: string;
  elapsed_seconds?: number;
  distance_km?: number | null;
  bearing_degrees?: number | null;
  bearing_direction?: string | null;
  bearing_arrow?: string | null;
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
  user: User | null;
  date: string;
  state: GameState;
  questions: Question[];
  guesses: Guess[];
  country?: Country;
  powiat?: any;
  us_state?: any;
  wojewodztwo?: any;
}

export interface CountryDisplay {
    id: number;
    name: string;
    iso2: string;
    iso3: string;
}

export interface FlagdleCountry {
  id: number;
  name: string;
  official_name?: string | null;
  iso2: string;
}

export interface FlagdleGuess {
  id: number;
  guess: string;
  country_id?: number | null;
  answer: boolean;
  distance_km?: number | null;
  bearing_degrees?: number | null;
  bearing_direction?: string | null;
  bearing_arrow?: string | null;
  matched_colors: string[];
  missed_colors: string[];
  remaining_colors_count?: number | null;
  matched_symbols: string[];
  revealed_tile?: number | null;
  guessed_at: string;
}

export interface FlagdleState {
  remaining_guesses: number;
  guesses_made: number;
  revealed_stage: number;
  is_game_over: boolean;
  won: boolean;
  points: number;
}

export interface FlagdleStateResponse {
  user: User | null;
  date: string;
  state: FlagdleState;
  guesses: FlagdleGuess[];
  flag_asset_url?: string | null;
  country?: Country | null;
}
