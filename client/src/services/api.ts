import axios from 'axios';
import type { CountryDisplay, GameResponse, Question, Guess } from '../types';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_URL,
  withCredentials: true, // Important for cookies
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      // Clear local storage and redirect to login
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
  getLeaderboard: async (): Promise<any[]> => {
    const response = await api.get('/countrydle/statistics/leaderboard');
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
  getLeaderboard: async (): Promise<any[]> => {
    const response = await api.get('/powiatdle/leaderboard');
    return response.data;
  },
  getHistory: async (): Promise<any[]> => {
    const response = await api.get('/powiatdle/history');
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
  getLeaderboard: async (): Promise<any[]> => {
    const response = await api.get('/us_statedle/leaderboard');
    return response.data;
  },
  getHistory: async (): Promise<any[]> => {
    const response = await api.get('/us_statedle/history');
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
  getLeaderboard: async (): Promise<any[]> => {
    const response = await api.get('/wojewodztwodle/leaderboard');
    return response.data;
  },
  getHistory: async (): Promise<any[]> => {
    const response = await api.get('/wojewodztwodle/history');
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

