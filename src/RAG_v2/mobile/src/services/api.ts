/**
 * Mobile API client with SecureStore tokens and refresh-on-401 retry.
 */

import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios';
import { createApiClient, type UserPublic } from '@rag/shared';
import { getRefreshToken, getToken, setToken, clearAll } from './secureStorage';
import { authStore } from '../stores/authStore';
import { API_BASE_URL } from '../utils/constants';

interface RetryConfig extends InternalAxiosRequestConfig {
  _retry?: boolean;
}

export const apiClient = createApiClient({
  baseURL: API_BASE_URL,
  getToken,
});

let refreshPromise: Promise<string | null> | null = null;

const clearAuthState = async () => {
  authStore.getState().clearAuth();
  await clearAll();
};

export const refreshAccessToken = async (): Promise<string | null> => {
  if (!refreshPromise) {
    refreshPromise = (async () => {
      const refreshToken = await getRefreshToken();
      if (!refreshToken) return null;

      const response = await axios.post<{
        access_token: string;
        refresh_token?: string | null;
        user: UserPublic;
      }>(`${API_BASE_URL}/auth/refresh`, {
        refresh_token: refreshToken,
        client_type: 'mobile',
      });

      const nextRefresh = response.data.refresh_token ?? refreshToken;
      await setToken(response.data.access_token, nextRefresh);
      authStore.getState().setAuth(
        response.data.access_token,
        response.data.user,
        nextRefresh,
      );
      return response.data.access_token;
    })().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
};

apiClient.interceptors.response.use(
  (res) => res,
  async (error: AxiosError) => {
    if (!error.response) {
      console.error('[API] Network error - check EXPO_PUBLIC_API_BASE_URL and backend is running');
      console.error('[API] URL attempted:', error.config?.baseURL, error.config?.url);
    }

    const original = error.config as RetryConfig | undefined;
    if (error.response?.status !== 401 || !original) {
      throw error;
    }

    if (original._retry || original.url?.includes('/auth/refresh')) {
      await clearAuthState();
      throw error;
    }

    original._retry = true;
    const token = await refreshAccessToken().catch(() => null);
    if (!token) {
      await clearAuthState();
      throw error;
    }

    original.headers.Authorization = `Bearer ${token}`;
    return apiClient(original);
  },
);
