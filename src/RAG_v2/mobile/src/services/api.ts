/**
 * Mobile API client — configured with SecureStore token provider
 * and automatic 401 refresh interceptor.
 */

import { createApiClient } from '@rag/shared';
import { getToken, clearAll } from './secureStorage';
import { authStore } from '../stores/authStore';
import { API_BASE_URL } from '../utils/constants';

export const apiClient = createApiClient({
  baseURL: API_BASE_URL,
  getToken,
});

// ─── 401 Interceptor — single-token auth reset ──────────────────────────────

apiClient.interceptors.response.use(
  (res) => res,
  async (error) => {
    // Log network errors for easier debugging in Metro / JS Debugger
    if (!error.response) {
      console.error('[API] Network error — check EXPO_PUBLIC_API_BASE_URL and backend is running');
      console.error('[API] URL attempted:', error.config?.baseURL, error.config?.url);
    }
    if (error.response?.status !== 401) throw error;
    authStore.getState().clearAuth();
    await clearAll();
    throw error;
  },
);
