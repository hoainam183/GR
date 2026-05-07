/**
 * Mobile API client — configured with SecureStore token provider
 * and automatic 401 refresh interceptor.
 */

import { createApiClient } from '@rag/shared';
import {
  getToken,
  getRefreshToken,
  setToken,
  clearTokens,
} from './secureStorage';
import { API_BASE_URL } from '../utils/constants';

export const apiClient = createApiClient({
  baseURL: API_BASE_URL,
  getToken,
});

// ─── 401 Interceptor — automatic token refresh ──────────────────────────────

apiClient.interceptors.response.use(
  (res) => res,
  async (error) => {
    // Only handle 401 Unauthorized
    if (error.response?.status !== 401) throw error;

    const refresh = await getRefreshToken();
    if (!refresh) {
      await clearTokens();
      throw error;
    }

    try {
      const { data } = await apiClient.post('/auth/refresh', {
        refresh_token: refresh,
      });
      await setToken(data.access_token, data.refresh_token || refresh);
      // Retry original request with new token
      error.config.headers.Authorization = `Bearer ${data.access_token}`;
      return apiClient.request(error.config);
    } catch {
      await clearTokens();
      throw error;
    }
  },
);
