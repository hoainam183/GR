/**
 * Authentication hook — login, logout, and session restoration.
 */

import { useCallback, useEffect, useState } from 'react';
import { loginUser, getMe, type LoginRequest, type UserPublic } from '@rag/shared';
import { apiClient } from '../services/api';
import {
  getToken,
  setToken,
  clearAll,
  setUserProfile,
  getUserProfile,
} from '../services/secureStorage';
import { useAuthStore } from '../stores/authStore';

let hasBootstrappedAuth = false;

export const useAuth = () => {
  const { isAuthenticated, user, setAuth, clearAuth } = useAuthStore();
  const [isLoading, setIsLoading] = useState(true);

  // ─── Restore session on app launch ───────────────────────────────────────
  useEffect(() => {
    const restore = async () => {
      if (hasBootstrappedAuth) {
        setIsLoading(false);
        return;
      }
      hasBootstrappedAuth = true;
      try {
        const token = await getToken();
        if (!token) {
          setIsLoading(false);
          return;
        }

        // Try to get user from cache first
        const cachedUser = await getUserProfile<UserPublic>();
        if (cachedUser) {
          setAuth(token, cachedUser);
        }

        // Validate token against server (may fail if offline — that's ok)
        try {
          const freshUser = await getMe(apiClient, token);
          setAuth(token, freshUser);
          await setUserProfile(freshUser);
        } catch {
          // Token expired or server unreachable — use cached if available
          if (!cachedUser) {
            clearAuth();
            await clearAll();
          }
        }
      } catch {
        clearAuth();
      } finally {
        setIsLoading(false);
      }
    };

    restore();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ─── Login ───────────────────────────────────────────────────────────────
  const login = useCallback(
    async (data: LoginRequest) => {
      const result = await loginUser(apiClient, data);
      await setToken(result.access_token);
      await setUserProfile(result.user);
      setAuth(result.access_token, result.user);
      return result;
    },
    [setAuth],
  );

  // ─── Logout ──────────────────────────────────────────────────────────────
  const logout = useCallback(async () => {
    clearAuth();
    await clearAll();
  }, [clearAuth]);

  return {
    isAuthenticated,
    user,
    isLoading,
    login,
    logout,
  };
};
