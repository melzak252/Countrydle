import { create } from 'zustand';
import type { User } from '../types';
import { authService } from '../services/api';

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  login: (user: User) => void;
  logout: () => Promise<void>;
  setUser: (user: User | null) => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: false,
  isLoading: true,
  error: null,
  login: (user) => {
    localStorage.setItem('user', JSON.stringify(user));
    set({ user, isAuthenticated: true, error: null, isLoading: false });
    // Dispatch a custom event to notify other stores that login happened
    window.dispatchEvent(new Event('auth-login'));
  },
  logout: async () => {
    try {
      await authService.logout();
      localStorage.removeItem('user');
      set({ user: null, isAuthenticated: false, error: null });
      // Dispatch a custom event to notify other stores that logout happened
      window.dispatchEvent(new Event('auth-logout'));
    } catch (e) {
      console.error(e);
      // Force logout on client even if server fails
      localStorage.removeItem('user');
      set({ user: null, isAuthenticated: false, error: 'Logout failed' });
      window.dispatchEvent(new Event('auth-logout'));
    }
  },
  setUser: (user) => {
    if (user) {
        localStorage.setItem('user', JSON.stringify(user));
        set({ user, isAuthenticated: true, isLoading: false });
    } else {
        localStorage.removeItem('user');
        set({ user: null, isAuthenticated: false, isLoading: false });
    }
  },
}));
