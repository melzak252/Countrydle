export interface User {
  id: number;
  username: string | null;
  email: string;
  verified: boolean;
  is_admin: boolean;
  avatar_url?: string;
}
export type LeaderboardPeriod = 'monthly' | 'average';

export interface LeaderboardEntry {
  id: number;
  username: string;
  points: number;
  wins: number;
  games_played: number;
  average_points: number;
}

export interface Country {
  id: number;
  name: string;
  official_name?: string | null;
  iso2: string;
  iso3: string;
}

export type FactProvenanceRelation = 'membership' | 'hemisphere';

export interface FactProvenance {
  status: 'unknown' | 'cited';
  citation: string | null;
  source_url: string | null;
  effective_from: string | null;
  effective_to: string | null;
  retrieved_at: string | null;
  updated_at: string | null;
  convention: string | null;
}

export interface FactProvenanceRecord {
  relation: FactProvenanceRelation;
  // Null is evidence for the complete relation/absence, never a list value.
  value: string | null;
  provenance: FactProvenance;
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
  fact_provenance?: FactProvenanceRecord[];
}

export type AnswerReportMode = 'countrydle' | 'us_statedle' | 'powiatdle' | 'wojewodztwodle' | 'continental';
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
    fact_provenance?: FactProvenanceRecord[];
  };
}

export type TemplateDivergenceStatus = 'open' | 'reviewed' | 'all';

export interface TemplateDivergence {
  id: number;
  mode: string;
  question: string;
  template_plan: any;
  gemini_plan: any | null;
  divergence_type: string;
  details: {
    template_relation?: string;
    gemini_relation?: string;
    template_operator?: string;
    gemini_operator?: string;
    template_value?: any;
    gemini_value?: any;
    template_improved_question?: string | null;
    gemini_improved_question?: string | null;
    gemini_explanation?: string | null;
    reason?: string;
  } | null;
  created_at: string;
  reviewed_at: string | null;
}

export type QuestionTestMode = 'countrydle' | 'us_statedle' | 'powiatdle' | 'wojewodztwodle' | 'europe' | 'asia' | 'africa' | 'americas' | 'flagdle';

export interface QuestionTestEntity {
  id: number;
  name: string;
}

export interface QuestionTestRequest {
  mode: QuestionTestMode;
  entity_id: number;
  question: string;
}

export interface QuestionModelDiagnostics {
  provider: string | null;
  model: string | null;
  model_version: string | null;
  contract_version: string | null;
  duration_ms: number | null;
  cache_hit: boolean | null;
  usage: {
    input_tokens: number | null;
    output_tokens: number | null;
    thought_tokens: number | null;
    cached_input_tokens: number | null;
    total_tokens: number | null;
  } | null;
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
  fact_provenance: FactProvenanceRecord[];
  diagnostics: {
    planner: QuestionModelDiagnostics | null;
    local_duration_ms: number | null;
    retrieval_duration_ms: number | null;
    fallback: QuestionModelDiagnostics | null;
  };
}

export interface CacheStats {
  hits: number;
  misses: number;
  size: number;
  max_size: number;
  hit_ratio_percent: number;
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
  elapsed_seconds?: number | null;
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
  elapsed_seconds?: number | null;
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
  questions: Question[];
  guesses: FlagdleGuess[];
  flag_asset_url?: string | null;
  country?: Country | null;
}

export interface PatchNote {
  id: number;
  version: string;
  title: string;
  body: string;
  published_at: string;
}

export interface PatchNotesResponse {
  items: PatchNote[];
  total: number;
  page: number;
  limit: number;
}
export type SuggestionTopic = 'feedback' | 'bug' | 'feature' | 'data';

export interface SuggestionSubmission {
  topic: SuggestionTopic;
  message: string;
  name: string | null;
  email: string | null;
}

export interface Suggestion {
  id: number;
  topic: SuggestionTopic;
  message: string;
  name: string | null;
  email: string | null;
  created_at: string;
  reporter_username: string | null;
}

export interface AdminSuggestionsResponse {
  items: Suggestion[];
  total: number;
}

export type AdminQuestionSource = 'local_kb' | 'fallback' | 'invalid';

export interface AdminQuestionItem {
  id: number;
  mode: string;
  day_id: number;
  game_date: string;
  target_id: number;
  target_name: string;
  target_subtitle?: string | null;
  user_id?: number | null;
  username: string;
  is_guest: boolean;
  original_question: string;
  question?: string | null;
  valid: boolean;
  answer?: boolean | null;
  explanation: string;
  context?: string | null;
  source: AdminQuestionSource;
  relation?: string | null;
  asked_at?: string | null;
  fact_provenance?: FactProvenanceRecord[];
  has_report: boolean;
  report_id?: number | null;
}

export interface AdminQuestionsListResponse {
  items: AdminQuestionItem[];
  total: number;
  page: number;
  limit: number;
}

export interface AdminGameSessionTimelineEvent {
  event_type: 'question' | 'guess';
  id: number;
  timestamp?: string | null;
  question?: string | null;
  original_question?: string | null;
  valid?: boolean | null;
  answer?: boolean | null;
  explanation?: string | null;
  source?: AdminQuestionSource | null;
  relation?: string | null;
  context?: string | null;
  guess?: string | null;
  correct?: boolean | null;
}

export interface AdminGameSessionItem {
  session_id: string;
  mode: string;
  day_id: number;
  game_date: string;
  target_name: string;
  target_subtitle?: string | null;
  user_id?: number | null;
  username: string;
  is_guest: boolean;
  status: 'won' | 'lost' | 'in_progress';
  questions_asked: number;
  guesses_made: number;
  duration_seconds?: number | null;
  started_at?: string | null;
  completed_at?: string | null;
  timeline: AdminGameSessionTimelineEvent[];
}

export interface AdminGameSessionsResponse {
  items: AdminGameSessionItem[];
  total: number;
  page: number;
  limit: number;
}

export interface AdminTopQuestionStat {
  text: string;
  count: number;
  yes_pct: number;
  win_correlation: number;
}

export interface AdminTopGuessStat {
  guess: string;
  count: number;
  correct_pct: number;
}

export interface AdminTargetStrategyStats {
  target_name: string;
  target_subtitle?: string | null;
  game_date: string;
  total_players: number;
  win_rate_pct: number;
  top_questions: AdminTopQuestionStat[];
  top_guesses: AdminTopGuessStat[];
  avg_questions_winners: number;
  avg_questions_losers: number;
}

export interface AdminInvalidateFallbackResponse {
  success: boolean;
  mode: string;
  question_id: number;
  message: string;
}

export interface LiveQuestionItem {
  id: number;
  mode: string;
  username: string;
  question: string;
  valid: boolean;
  answer?: boolean | null;
  explanation?: string | null;
  asked_at?: string | null;
  target_name?: string | null;
  target_subtitle?: string | null;
  source?: string | null;
}

export interface LiveGuessItem {
  id: number;
  mode: string;
  username: string;
  guess: string;
  answer: boolean;
  guessed_at?: string | null;
  target_name?: string | null;
  target_subtitle?: string | null;
}

export interface LiveFeedData {
  recent_questions: LiveQuestionItem[];
  recent_guesses: LiveGuessItem[];
}
