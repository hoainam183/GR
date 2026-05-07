/**
 * Platform-agnostic auth store factory.
 *
 * Storage persistence is injected per-platform:
 *   - Web:    localStorage
 *   - Mobile: expo-secure-store
 */

import { createStore } from 'zustand/vanilla';
import type { UserPublic } from '../types/auth';

export interface AuthState {
  isAuthenticated: boolean;
  accessToken: string | null;
  user: UserPublic | null;

  setAuth: (token: string, user: UserPublic) => void;
  clearAuth: () => void;
  setUser: (user: UserPublic) => void;
}

/**
 * Create a vanilla Zustand store (framework-agnostic).
 * Each platform wraps this with `useStore()` or React bindings.
 */
export const createAuthStore = () =>
  createStore<AuthState>((set) => ({
    isAuthenticated: false,
    accessToken: null,
    user: null,

    setAuth: (token, user) =>
      set({ isAuthenticated: true, accessToken: token, user }),

    clearAuth: () =>
      set({ isAuthenticated: false, accessToken: null, user: null }),

    setUser: (user) => set({ user }),
  }));

export type AuthStore = ReturnType<typeof createAuthStore>;
