/**
 * Mobile auth store — wires the shared createAuthStore with SecureStore persistence.
 */

import { useStore } from 'zustand';
import { createAuthStore, type AuthState } from '@rag/shared';
import {
  setToken,
  clearTokens,
  setUserProfile,
  clearUserProfile,
} from '../services/secureStorage';

export const authStore = createAuthStore();

// ─── Sync state changes to SecureStore ───────────────────────────────────────
authStore.subscribe(async (state, prev) => {
  // Persist token changes
  if (
    state.accessToken !== prev.accessToken ||
    state.refreshToken !== prev.refreshToken
  ) {
    if (state.accessToken) {
      await setToken(state.accessToken, state.refreshToken ?? undefined);
    } else {
      await clearTokens();
    }
  }

  // Persist user profile changes
  if (state.user !== prev.user) {
    if (state.user) {
      await setUserProfile(state.user);
    } else {
      await clearUserProfile();
    }
  }
});

// ─── React hook wrapper ──────────────────────────────────────────────────────

export function useAuthStore(): AuthState;
export function useAuthStore<T>(selector: (state: AuthState) => T): T;
export function useAuthStore<T>(selector?: (state: AuthState) => T) {
  return useStore(authStore, selector!);
}
