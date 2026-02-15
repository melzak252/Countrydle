import axios from 'axios';
import type { CountryDisplay, GameResponse, Question, Guess } from '../types';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_URL,
  withCredentials: true, // Important for cookies
});

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
};

export default api;
