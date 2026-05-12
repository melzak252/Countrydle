import axios from 'axios';
import type { CountryDisplay, GameResponse, Question, Guess } from '../types';

export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8080';


const api = axios.create({
  baseURL: API_URL,
  withCredentials: true, // Important for cookies
});

api.interceptors.request.use((config) => {
  if (localStorage.getItem('user')) {
    config.headers['X-Client-Authenticated'] = 'true';
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      localStorage.removeItem('user');
      if (window.location.pathname !== '/login') {
        localStorage.setItem('session_expired', 'true');
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
  googleLogin: async (credential: string) => {
    const response = await api.post('/google-signin', { credential });
    return response.data;
  },
  updateProfile: async (data: { username: string; email?: string }) => {
    const response = await api.post('/users/update', data);
    return response.data;
  }
};


export const gameService = {
  getLeaderboard: async (type: 'monthly' | 'average' = 'monthly'): Promise<any[]> => {
    const response = await api.get(`/countrydle/statistics/leaderboard?type=${type}`);
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
    return response.data;
  },
  askQuestion: async (question: string): Promise<Question> => {
    const response = await api.post('/countrydle/question', { question });
    return response.data;
  },
  makeGuess: async (guess: string, country_id?: number): Promise<Guess> => {
    const response = await api.post('/countrydle/guess', { guess, country_id });
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
  reveal: async (): Promise<CountryDisplay> => {
    const response = await api.get('/countrydle/reveal');
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
  makeGuess: async (guess: string, powiat_id?: number): Promise<any> => {
    const response = await api.post('/powiatdle/guess', { guess, powiat_id });
    return response.data;
  },
  getLeaderboard: async (type: 'monthly' | 'average' = 'monthly'): Promise<any[]> => {
    const response = await api.get(`/powiatdle/leaderboard?type=${type}`);
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
  reveal: async (): Promise<any> => {
    const response = await api.get('/powiatdle/reveal');
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
  makeGuess: async (guess: string, us_state_id?: number): Promise<any> => {
    const response = await api.post('/us_statedle/guess', { guess, us_state_id });
    return response.data;
  },
  getLeaderboard: async (type: 'monthly' | 'average' = 'monthly'): Promise<any[]> => {
    const response = await api.get(`/us_statedle/leaderboard?type=${type}`);
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
  reveal: async (): Promise<any> => {
    const response = await api.get('/us_statedle/reveal');
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
  makeGuess: async (guess: string, wojewodztwo_id?: number): Promise<any> => {
    const response = await api.post('/wojewodztwodle/guess', { guess, wojewodztwo_id });
    return response.data;
  },
  getLeaderboard: async (type: 'monthly' | 'average' = 'monthly'): Promise<any[]> => {
    const response = await api.get(`/wojewodztwodle/leaderboard?type=${type}`);
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
  reveal: async (): Promise<any> => {
    const response = await api.get('/wojewodztwodle/reveal');
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

export const adminService = {
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

export default api;
