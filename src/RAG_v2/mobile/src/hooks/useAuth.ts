/**
 * Authentication hook - login, logout, and session restoration.
 */

import { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { loginUser, getMe, type LoginRequest, type UserPublic } from '@rag/shared';
import { apiClient, refreshAccessToken } from '../services/api';
import {
  getRefreshToken,
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

  useEffect(() => {
    const restore = async () => {
      if (hasBootstrappedAuth) {
        setIsLoading(false);
        return;
      }
      hasBootstrappedAuth = true;

      try {
        const token = await getToken();
        const refreshToken = await getRefreshToken();
        const cachedUser = await getUserProfile<UserPublic>();

        if (!token && !refreshToken) {
          setIsLoading(false);
          return;
        }

        if (token && cachedUser) {
          setAuth(token, cachedUser, refreshToken);
        }

        try {
          if (!token) throw new Error('missing access token');
          const freshUser = await getMe(apiClient, token);
          setAuth(token, freshUser, refreshToken);
          await setUserProfile(freshUser);
        } catch (error) {
          if (axios.isAxiosError(error) && !error.response && cachedUser && token) {
            return;
          }

          const refreshedToken = await refreshAccessToken().catch(() => null);
          if (!refreshedToken) {
            clearAuth();
            await clearAll();
            return;
          }

          const freshUser = await getMe(apiClient, refreshedToken);
          const nextRefresh = await getRefreshToken();
          setAuth(refreshedToken, freshUser, nextRefresh);
          await setUserProfile(freshUser);
        }
      } catch {
        clearAuth();
        await clearAll();
      } finally {
        setIsLoading(false);
      }
    };

    restore();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const login = useCallback(
    async (data: LoginRequest) => {
      const result = await loginUser(apiClient, { ...data, client_type: 'mobile' });
      await setToken(result.access_token, result.refresh_token ?? undefined);
      await setUserProfile(result.user);
      setAuth(result.access_token, result.user, result.refresh_token ?? null);
      return result;
    },
    [setAuth],
  );

  const logout = useCallback(async () => {
    const refreshToken = await getRefreshToken();
    if (refreshToken) {
      await apiClient
        .post('/auth/logout', {
          refresh_token: refreshToken,
          client_type: 'mobile',
        })
        .catch(() => undefined);
    }
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
