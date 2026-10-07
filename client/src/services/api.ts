import axios from 'axios';
import type {
  AdminGameSessionsResponse,
  AdminInvalidateFallbackResponse,
  AdminQuestionsListResponse,
  AdminSuggestionsResponse,
  AdminTargetStrategyStats,
  AnswerReport,
  AnswerReportMode,
  AnswerReportStatus,
  CacheStats,
  CountryDisplay,
  FactProvenanceRecord,
  FlagdleCountry,
  FlagdleGuess,
  FlagdleStateResponse,
  GameResponse,
  Guess,
  LeaderboardEntry,
  LeaderboardPeriod,
  LiveFeedData,
  PatchNotesResponse,
  Question,
  QuestionTestEntity,
  QuestionTestMode,
  QuestionTestRequest,
  QuestionTestResult,
  SuggestionSubmission,
  TemplateDivergence,
  TemplateDivergenceStatus,
} from '../types';
import type { CountryCostReport } from '../types/countryCostReport';
import { isCountryAvailable } from '../lib/countryEligibility';

export const API_URL = import.meta.env.VITE_API_URL || '/api';


const api = axios.create({
  baseURL: API_URL,
  withCredentials: true, // Important for cookies
});

api.interceptors.request.use((config) => {
  try {
    if (localStorage.getItem('user')) {
      config.headers['X-Client-Authenticated'] = 'true';
    }
  } catch {
    // HttpOnly-cookie requests still work when browser storage is unavailable.
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      try {
        localStorage.removeItem('user');
        if (window.location.pathname !== '/login') {
          localStorage.setItem('session_expired', 'true');
        }
      } catch {
        // A denied storage API must not prevent session recovery.
      }
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

export const authService = {

  login: async (formData: FormData) => {
    const response = await api.post('/login', formData);
    return response.data;
  },
  logout: async () => {
    const response = await api.post('/logout');
    return response.data;
  },
  register: async (userData: any) => {
    const response = await api.post('/register', userData);
    return response.data;
  },
  verifyEmail: async (token: string) => {
    const response = await api.get(`/verify-email?token=${token}`);
    return response.data;
  },
  googleLogin: async (credential: string, rememberMe = false) => {
    const response = await api.post('/google-signin', { credential, remember_me: rememberMe });
    return response.data;
  },
  updateProfile: async (data: { username: string; email?: string }) => {
    const response = await api.post('/users/update', data);
    return response.data;
  }
};


export const gameService = {
  getLeaderboard: async (type: LeaderboardPeriod = 'monthly'): Promise<LeaderboardEntry[]> => {
    const response = await api.get<LeaderboardEntry[]>('/countrydle/statistics/leaderboard', { params: { type } });
    return response.data;
  },
  getUserStats: async (username: string): Promise<any> => {
    const response = await api.get(`/countrydle/statistics/users/${username}`);
    return response.data;
  },
  getUserProfileStats: async (username: string): Promise<any> => {
    const response = await api.get(`/users/${username}/stats`);
    return response.data;
  },
  getState: async (): Promise<GameResponse> => {
    const response = await api.get('/countrydle/state');
    return response.data;
  },
  getCountries: async (): Promise<CountryDisplay[]> => {
    const response = await api.get('/countrydle/countries');
    return response.data.filter((country: CountryDisplay) => isCountryAvailable(country.name));
  },
  askQuestion: async (question: string): Promise<Question> => {
    const response = await api.post('/countrydle/question', { question });
    return response.data;
  },
  makeGuess: async (guess: string, country_id?: number, elapsed_seconds?: number): Promise<Guess> => {
    const response = await api.post('/countrydle/guess', { guess, country_id, elapsed_seconds });
    return response.data;
  },
  getHistory: async (): Promise<any> => {
    const response = await api.get('/countrydle/statistics/history');
    return response.data;
  },
  syncGuestData: async (data: any): Promise<GameResponse> => {
    const response = await api.post('/countrydle/sync', data);
    return response.data;
  },
};

export const powiatService = {
  getState: async (): Promise<any> => {
    const response = await api.get('/powiatdle/state');
    return response.data;
  },
  getPowiaty: async (): Promise<any[]> => {
    const response = await api.get('/powiatdle/powiaty');
    return response.data;
  },
  askQuestion: async (question: string): Promise<any> => {
    const response = await api.post('/powiatdle/question', { question });
    return response.data;
  },
  makeGuess: async (guess: string, powiat_id?: number, elapsed_seconds?: number): Promise<any> => {
    const response = await api.post('/powiatdle/guess', { guess, powiat_id, elapsed_seconds });
    return response.data;
  },
  getLeaderboard: async (type: LeaderboardPeriod = 'monthly'): Promise<LeaderboardEntry[]> => {
    const response = await api.get<LeaderboardEntry[]>('/powiatdle/leaderboard', { params: { type } });
    return response.data;
  },
  getHistory: async (): Promise<any[]> => {
    const response = await api.get('/powiatdle/history');
    return response.data;
  },
  syncGuestData: async (data: any): Promise<any> => {
    const response = await api.post('/powiatdle/sync', data);
    return response.data;
  },
};

export const usStateService = {
  getState: async (): Promise<any> => {
    const response = await api.get('/us_statedle/state');
    return response.data;
  },
  getStates: async (): Promise<any[]> => {
    const response = await api.get('/us_statedle/states');
    return response.data;
  },
  askQuestion: async (question: string): Promise<any> => {
    const response = await api.post('/us_statedle/question', { question });
    return response.data;
  },
  makeGuess: async (guess: string, us_state_id?: number, elapsed_seconds?: number): Promise<any> => {
    const response = await api.post('/us_statedle/guess', { guess, us_state_id, elapsed_seconds });
    return response.data;
  },
  getLeaderboard: async (type: LeaderboardPeriod = 'monthly'): Promise<LeaderboardEntry[]> => {
    const response = await api.get<LeaderboardEntry[]>('/us_statedle/leaderboard', { params: { type } });
    return response.data;
  },
  getHistory: async (): Promise<any[]> => {
    const response = await api.get('/us_statedle/history');
    return response.data;
  },
  syncGuestData: async (data: any): Promise<any> => {
    const response = await api.post('/us_statedle/sync', data);
    return response.data;
  },
};

export const wojewodztwoService = {
  getState: async (): Promise<any> => {
    const response = await api.get('/wojewodztwodle/state');
    return response.data;
  },
  getWojewodztwa: async (): Promise<any[]> => {
    const response = await api.get('/wojewodztwodle/wojewodztwa');
    return response.data;
  },
  askQuestion: async (question: string): Promise<any> => {
    const response = await api.post('/wojewodztwodle/question', { question });
    return response.data;
  },
  makeGuess: async (guess: string, wojewodztwo_id?: number, elapsed_seconds?: number): Promise<any> => {
    const response = await api.post('/wojewodztwodle/guess', { guess, wojewodztwo_id, elapsed_seconds });
    return response.data;
  },
  getLeaderboard: async (type: LeaderboardPeriod = 'monthly'): Promise<LeaderboardEntry[]> => {
    const response = await api.get<LeaderboardEntry[]>('/wojewodztwodle/leaderboard', { params: { type } });
    return response.data;
  },
  getHistory: async (): Promise<any[]> => {
    const response = await api.get('/wojewodztwodle/history');
    return response.data;
  },
  syncGuestData: async (data: any): Promise<any> => {
    const response = await api.post('/wojewodztwodle/sync', data);
    return response.data;
  },
};

export const createContinentalService = (continent: string) => ({
  getState: async (): Promise<GameResponse> => {
    const response = await api.get(`/continental/${continent}/state`);
    return response.data;
  },
  getCountries: async (): Promise<CountryDisplay[]> => {
    const response = await api.get(`/continental/${continent}/countries`);
    return response.data.filter((country: CountryDisplay) => isCountryAvailable(country.name, continent));
  },
  askQuestion: async (question: string): Promise<Question> => {
    const response = await api.post(`/continental/${continent}/question`, { question });
    return response.data;
  },
  makeGuess: async (guess: string, country_id?: number, elapsed_seconds?: number): Promise<Guess> => {
    const response = await api.post(`/continental/${continent}/guess`, { guess, country_id, elapsed_seconds });
    return response.data;
  },
  getLeaderboard: async (type: LeaderboardPeriod = 'monthly'): Promise<LeaderboardEntry[]> => {
    const response = await api.get<LeaderboardEntry[]>(`/continental/${continent}/leaderboard`, { params: { type } });
    return response.data;
  },
  getHistory: async (): Promise<unknown[]> => {
    const response = await api.get(`/continental/${continent}/history`);
    return response.data;
  },
  syncGuestData: async (data: unknown): Promise<GameResponse> => {
    const response = await api.post(`/continental/${continent}/sync`, data);
    return response.data;
  },
});

export const europeService = createContinentalService('europe');
export const asiaService = createContinentalService('asia');
export const africaService = createContinentalService('africa');
export const americasService = createContinentalService('americas');
export const flagdleService = {
  getLeaderboard: async (type: LeaderboardPeriod = 'monthly'): Promise<LeaderboardEntry[]> => {
    const response = await api.get<LeaderboardEntry[]>('/flagdle/leaderboard', { params: { type } });
    return response.data;
  },
  getHistory: async (): Promise<unknown[]> => {
    const response = await api.get('/flagdle/history');
    return response.data;
  },
  getState: async (): Promise<FlagdleStateResponse> => {
    const response = await api.get('/flagdle/state');
    return response.data;
  },
  getCountries: async (): Promise<FlagdleCountry[]> => {
    const response = await api.get('/flagdle/countries');
    return response.data.filter((country: FlagdleCountry) => isCountryAvailable(country.name));
  },
  makeGuess: async (data: { guess: string; country_id?: number; elapsed_seconds?: number }): Promise<FlagdleGuess> => {
    const response = await api.post('/flagdle/guess', data);
    return response.data;
  },
  askQuestion: async (question: string): Promise<Question> => {
    const response = await api.post('/flagdle/question', { question });
    return response.data;
  },
  syncGuestData: async (data: unknown): Promise<FlagdleStateResponse> => {
    const response = await api.post('/flagdle/sync', data);
    return response.data;
  },
};

export const blogService = {
  getPosts: async (page = 1, limit = 12, search?: string) => {
    const params = new URLSearchParams({ page: page.toString(), limit: limit.toString() });
    if (search && search.trim()) params.append('search', search.trim());
    const response = await api.get(`/blog?${params.toString()}`);
    return response.data;
  },
  getPostBySlug: async (slugOrDate: string) => {
    const response = await api.get(`/blog/${slugOrDate}`);
    return response.data;
  },
  getLatestPost: async () => {
    const response = await api.get('/blog/latest');
    return response.data;
  },
};

export interface BorderHopChallenge {
  mode: string;
  start: string | null;
  target: string;
  connected: boolean;
  is_island: boolean;
  optimal_hops: number | null;
  optimal_path: string[] | null;
  message?: string | null;
}

export interface BorderHopVerification {
  valid: boolean;
  hops: number;
  optimal_hops: number | null;
  is_optimal: boolean;
  rank: 'gold' | 'silver' | 'bronze' | null;
  optimal_path?: string[] | null;
  error_step?: string[] | null;
  message?: string | null;
}

export interface BorderNeighborResponse {
  name: string;
  neighbors: string[];
  is_island: boolean;
}

export const exploreService = {
  getModes: async () => {
    const response = await api.get('/explore/modes');
    return response.data;
  },
  getCountries: async (params?: { search?: string; region?: string; limit?: number }) => {
    const p = new URLSearchParams();
    if (params?.search) p.append('search', params.search);
    if (params?.region) p.append('region', params.region);
    if (params?.limit) p.append('limit', params.limit.toString());
    const response = await api.get(`/explore/countries?${p.toString()}`);
    return response.data;
  },
  getCountryDetail: async (identifier: string) => {
    const response = await api.get(`/explore/countries/${encodeURIComponent(identifier)}`);
    return response.data;
  },
  getUSStates: async (params?: { search?: string; region?: string }) => {
    const p = new URLSearchParams();
    if (params?.search) p.append('search', params.search);
    if (params?.region) p.append('region', params.region);
    const response = await api.get(`/explore/us-states?${p.toString()}`);
    return response.data;
  },
  getUSStateDetail: async (name: string) => {
    const response = await api.get(`/explore/us-states/${encodeURIComponent(name)}`);
    return response.data;
  },
  getVoivodeships: async (search?: string) => {
    const p = new URLSearchParams();
    if (search) p.append('search', search);
    const response = await api.get(`/explore/voivodeships?${p.toString()}`);
    return response.data;
  },
  getVoivodeshipDetail: async (name: string) => {
    const response = await api.get(`/explore/voivodeships/${encodeURIComponent(name)}`);
    return response.data;
  },
  getPowiatDetail: async (name: string) => {
    const response = await api.get(`/explore/powiats/${encodeURIComponent(name)}`);
    return response.data;
  },
  getBorderHopChallenge: async (params?: { mode?: string; target?: string; origin?: string; seed?: string }) => {
    const p = new URLSearchParams();
    if (params?.mode) p.append('mode', params.mode);
    if (params?.target) p.append('target', params.target);
    if (params?.origin) p.append('origin', params.origin);
    if (params?.seed) p.append('seed', params.seed);
    const qs = p.toString();
    const response = await api.get<BorderHopChallenge>(`/explore/border-hop/challenge${qs ? `?${qs}` : ''}`);
    return response.data;
  },
  getBorderNeighbors: async (name: string, mode?: string) => {
    const p = new URLSearchParams({ name });
    if (mode) p.append('mode', mode);
    const response = await api.get<BorderNeighborResponse>(`/explore/border-hop/neighbors?${p.toString()}`);
    return response.data;
  },
  verifyBorderHop: async (payload: { mode: string; start: string; target: string; path: string[] }) => {
    const response = await api.post<BorderHopVerification>('/explore/border-hop/verify', payload);
    return response.data;
  },
};

export type AdminQuestionsResponse = {
  items: any[];
  total: number;
  limit: number;
  offset: number;
};

export type CountryFactsResponse = {
  game_type?: string | null;
  entity?: { id: number; name: string } | null;
  country: { id: number; name: string; official_name?: string | null };
  scalar_facts: Array<{ relation: string; column: string; value_type: string; value: any }>;
  list_facts: Array<{
    relation: string;
    table: string;
    value_column: string;
    metadata_columns: string[];
    values: Array<{ value: string; metadata: Record<string, any> }>;
  }>;
  fact_provenance: FactProvenanceRecord[];
};

export type CountryFactChangeLogEntry = {
  id: number;
  user_id: number | null;
  game_type?: string;
  entity_id?: number | null;
  entity_name?: string | null;
  country_id: number;
  country_name: string;
  relation: string;
  operation: string;
  old_value: string | null;
  new_value: string | null;
  sqlite_table: string;
  sqlite_column: string;
  note: string | null;
  server_version: string | null;
  created_at: string;
  user?: { username?: string | null; email?: string | null } | null;
};

const normalizeAdminQuestionsResponse = (data: any, limit: number, offset: number): AdminQuestionsResponse => {
  if (Array.isArray(data)) {
    return { items: data, total: data.length, limit, offset };
  }
  return data;
};

export const reportService = {
  submit: async (
    mode: AnswerReportMode,
    questionId: number,
    comment: string,
    reportToken?: string | null,
  ): Promise<{ id: number }> => {
    const response = await api.post<{ id: number }>('/answer-reports', {
      mode,
      question_id: questionId,
      comment,
      report_token: reportToken,
    });
    return response.data;
  },
};
export const suggestionService = {
  submit: async (suggestion: SuggestionSubmission): Promise<{ id: number }> => {
    const response = await api.post<{ id: number }>('/suggestions', suggestion);
    return response.data;
  },
};

export const adminSuggestionService = {
  getSuggestions: async (page = 1, limit = 25, signal?: AbortSignal): Promise<AdminSuggestionsResponse> => {
    const response = await api.get<AdminSuggestionsResponse>('/admin/suggestions', {
      params: { page, limit },
      signal,
    });
    return response.data;
  },
};


export const adminService = {
  getCountrydleCosts: async (days = 7, signal?: AbortSignal): Promise<CountryCostReport> => {
    const response = await api.get<CountryCostReport>('/admin/countrydle-costs', { params: { days }, signal });
    return response.data;
  },
  getCacheStats: async (signal?: AbortSignal): Promise<CacheStats> => {
    const response = await api.get<CacheStats>('/cache-stats', { signal, timeout: 10_000 });
    return response.data;
  },
  getQuestionTestEntities: async (mode: QuestionTestMode, signal?: AbortSignal): Promise<QuestionTestEntity[]> => {
    const response = await api.get<QuestionTestEntity[]>('/admin/question-tests/entities', { params: { mode }, signal });
    return response.data;
  },
  testQuestion: async (request: QuestionTestRequest): Promise<QuestionTestResult> => {
    const response = await api.post<QuestionTestResult>('/admin/question-tests', request);
    return response.data;
  },
  getAnswerReports: async (
    status: AnswerReportStatus,
    page: number,
    limit = 25,
    mode?: AnswerReportMode,
  ): Promise<{ items: AnswerReport[]; total: number }> => {
    const response = await api.get<{ items: AnswerReport[]; total: number }>('/admin/answer-reports', {
      params: { status, page, limit, mode },
    });
    return response.data;
  },
  reviewAnswerReport: async (id: number, reviewed: boolean): Promise<AnswerReport> => {
    const response = await api.patch<AnswerReport>(`/admin/answer-reports/${id}`, { reviewed });
    return response.data;
  },
  getTemplateDivergences: async (
    status: TemplateDivergenceStatus = 'open',
    page = 1,
    limit = 25,
    mode?: string,
  ): Promise<{ items: TemplateDivergence[]; total: number }> => {
    const response = await api.get<{ items: TemplateDivergence[]; total: number }>('/admin/template-divergences', {
      params: { status, page, limit, mode },
    });
    return response.data;
  },
  reviewTemplateDivergence: async (id: number, reviewed: boolean): Promise<TemplateDivergence> => {
    const response = await api.patch<TemplateDivergence>(`/admin/template-divergences/${id}`, { reviewed });
    return response.data;
  },
  getOverview: async () => {
    const response = await api.get('/admin/overview');
    return response.data;
  },
  getUsers: async (page = 1, limit = 25, search?: string) => {
    const params = new URLSearchParams({ page: page.toString(), limit: limit.toString() });
    if (search && search.trim()) params.append('search', search.trim());
    const response = await api.get(`/admin/users?${params.toString()}`);
    return response.data;
  },
  getLiveFeed: async (mode?: string): Promise<LiveFeedData> => {
    const params = new URLSearchParams();
    if (mode && mode !== 'all') params.append('mode', mode);
    const qs = params.toString();
    const response = await api.get<LiveFeedData>(`/admin/live-feed${qs ? `?${qs}` : ''}`);
    return response.data;
  },
  getQuestions: async (params: {
    mode?: string;
    search?: string;
    date?: string;
    source?: string;
    answer?: string;
    target_name?: string;
    has_report?: boolean;
    page?: number;
    limit?: number;
  }): Promise<AdminQuestionsListResponse> => {
    const qp = new URLSearchParams();
    if (params.mode && params.mode !== 'all') qp.append('mode', params.mode);
    if (params.search?.trim()) qp.append('search', params.search.trim());
    if (params.date) qp.append('date', params.date);
    if (params.source && params.source !== 'all') qp.append('source', params.source);
    if (params.answer && params.answer !== 'all') qp.append('answer', params.answer);
    if (params.target_name?.trim()) qp.append('target_name', params.target_name.trim());
    if (typeof params.has_report === 'boolean') qp.append('has_report', String(params.has_report));
    if (params.page) qp.append('page', params.page.toString());
    if (params.limit) qp.append('limit', params.limit.toString());
    const response = await api.get<AdminQuestionsListResponse>(`/admin/questions?${qp.toString()}`);
    return response.data;
  },
  getGameSessions: async (params: {
    mode?: string;
    date?: string;
    status?: string;
    player_type?: string;
    page?: number;
    limit?: number;
  }): Promise<AdminGameSessionsResponse> => {
    const qp = new URLSearchParams();
    if (params.mode && params.mode !== 'all') qp.append('mode', params.mode);
    if (params.date) qp.append('date', params.date);
    if (params.status && params.status !== 'all') qp.append('status', params.status);
    if (params.player_type && params.player_type !== 'all') qp.append('player_type', params.player_type);
    if (params.page) qp.append('page', params.page.toString());
    if (params.limit) qp.append('limit', params.limit.toString());
    const response = await api.get<AdminGameSessionsResponse>(`/admin/game-sessions?${qp.toString()}`);
    return response.data;
  },
  getTargetStrategyStats: async (params: {
    mode?: string;
    date?: string;
  }): Promise<AdminTargetStrategyStats> => {
    const qp = new URLSearchParams();
    if (params.mode && params.mode !== 'all') qp.append('mode', params.mode);
    if (params.date) qp.append('date', params.date);
    const response = await api.get<AdminTargetStrategyStats>(`/admin/game-sessions/stats?${qp.toString()}`);
    return response.data;
  },
  invalidateQuestionFallback: async (mode: string, questionId: number): Promise<AdminInvalidateFallbackResponse> => {
    const response = await api.post<AdminInvalidateFallbackResponse>('/admin/questions/invalidate-fallback', {
      mode,
      question_id: questionId,
    });
    return response.data;
  },
  getCountrydleQuestions: async (limit = 50, offset = 0): Promise<AdminQuestionsResponse> => {
    const response = await api.get('/countrydle/admin/questions', { params: { limit, offset } });
    return normalizeAdminQuestionsResponse(response.data, limit, offset);
  },
  getPowiatdleQuestions: async (limit = 50, offset = 0): Promise<AdminQuestionsResponse> => {
    const response = await api.get('/powiatdle/admin/questions', { params: { limit, offset } });
    return normalizeAdminQuestionsResponse(response.data, limit, offset);
  },
  getUSStatedleQuestions: async (limit = 50, offset = 0): Promise<AdminQuestionsResponse> => {
    const response = await api.get('/us_statedle/admin/questions', { params: { limit, offset } });
    return normalizeAdminQuestionsResponse(response.data, limit, offset);
  },
  getWojewodztwodleQuestions: async (limit = 50, offset = 0): Promise<AdminQuestionsResponse> => {
    const response = await api.get('/wojewodztwodle/admin/questions', { params: { limit, offset } });
    return normalizeAdminQuestionsResponse(response.data, limit, offset);
  },
  getContinentalQuestions: async (limit = 50, offset = 0, continent?: string): Promise<AdminQuestionsResponse> => {
    const params: Record<string, any> = { limit, offset };
    if (continent && continent !== 'all') params.continent = continent;
    const response = await api.get('/continental/admin/questions', { params });
    return normalizeAdminQuestionsResponse(response.data, limit, offset);
  },
  getCountryFacts: async (countryIdOrName: number | string, gameType = 'countrydle'): Promise<CountryFactsResponse> => {
    const params = typeof countryIdOrName === 'number'
      ? { game_type: gameType, entity_id: countryIdOrName, country_id: countryIdOrName }
      : { game_type: gameType, entity_name: countryIdOrName, country_name: countryIdOrName };
    const response = await api.get('/countrydle/admin/country-facts', { params });
    return response.data;
  },
  updateCountryScalarFact: async (countryId: number, relation: string, value: any, note?: string, gameType = 'countrydle'): Promise<CountryFactsResponse> => {
    const response = await api.patch('/countrydle/admin/country-facts/scalar', { game_type: gameType, entity_id: countryId, country_id: countryId, relation, value, note });
    return response.data;
  },
  addCountryListFact: async (countryId: number, relation: string, value: string, metadata: Record<string, any> = {}, note?: string, gameType = 'countrydle'): Promise<CountryFactsResponse> => {
    const response = await api.post('/countrydle/admin/country-facts/list-values', { game_type: gameType, entity_id: countryId, country_id: countryId, relation, value, metadata, note });
    return response.data;
  },
  deleteCountryListFact: async (countryId: number, relation: string, value: string, note?: string, gameType = 'countrydle'): Promise<CountryFactsResponse> => {
    const response = await api.delete('/countrydle/admin/country-facts/list-values', { data: { game_type: gameType, entity_id: countryId, country_id: countryId, relation, value, note } });
    return response.data;
  },
  updateCountryFactProvenance: async (countryId: number, record: FactProvenanceRecord, note?: string): Promise<CountryFactsResponse> => {
    const response = await api.patch<CountryFactsResponse>('/countrydle/admin/country-facts/provenance', {
      country_id: countryId,
      relation: record.relation,
      value: record.value,
      provenance: record.provenance,
      ...(note === undefined ? {} : { note }),
    });
    return response.data;
  },
  getCountryFactChangeLog: async (limit = 50, offset = 0): Promise<CountryFactChangeLogEntry[]> => {
    const response = await api.get('/countrydle/admin/country-facts/change-log', { params: { limit, offset } });
    return response.data;
  },
};


export const timeService = {
  getServerTime: async (): Promise<{ server_time: string; next_game_at: string }> => {
    const response = await api.get('/time');
    return response.data;
  }
};

export const patchNotesService = {
  getPatchNotes: async (
    page = 1,
    limit = 10,
    signal?: AbortSignal,
  ): Promise<PatchNotesResponse> => {
    const response = await api.get<PatchNotesResponse>('/patch-notes', {
      params: { page, limit },
      signal,
    });
    return response.data;
  },
};

export default api;
