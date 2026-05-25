/**
 * Platform-agnostic API client factory.
 *
 * Both web and mobile create their own client instance by calling
 * `createApiClient()` and providing a platform-specific `getToken`
 * callback (localStorage on web, expo-secure-store on mobile).
 */

import axios, {
  type AxiosError,
  type AxiosInstance,
  type InternalAxiosRequestConfig,
} from 'axios';

export interface ApiClientConfig {
  /** Base URL of the backend API (e.g. http://localhost:8000) */
  baseURL: string;
  /** Async callback that returns the current access token, or null */
  getToken?: () => Promise<string | null>;
  /** Optional refresh callback used once after a 401 response */
  refreshAuth?: () => Promise<string | null>;
  /** Optional callback when refresh fails or auth is rejected */
  onUnauthorized?: () => void | Promise<void>;
  /** Whether cross-site credentials/cookies are sent */
  withCredentials?: boolean;
  /** Request timeout in ms (default: 120_000) */
  timeout?: number;
}

interface RetryRequestConfig extends InternalAxiosRequestConfig {
  _retry?: boolean;
}

/**
 * Create a configured Axios instance with automatic Bearer token injection.
 */
export const createApiClient = (config: ApiClientConfig): AxiosInstance => {
  const client = axios.create({
    baseURL: config.baseURL,
    timeout: config.timeout ?? 120_000,
    headers: { 'Content-Type': 'application/json' },
    withCredentials: config.withCredentials,
  });

  // Inject Authorization header on every request
  client.interceptors.request.use(async (req) => {
    if (config.getToken) {
      const token = await config.getToken();
      if (token) req.headers.Authorization = `Bearer ${token}`;
    }
    return req;
  });

  client.interceptors.response.use(
    (response) => response,
    async (error: AxiosError) => {
      const original = error.config as RetryRequestConfig | undefined;
      if (
        error.response?.status !== 401 ||
        !original ||
        original._retry ||
        !config.refreshAuth
      ) {
        throw error;
      }

      original._retry = true;
      const token = await config.refreshAuth().catch(() => null);
      if (!token) {
        await config.onUnauthorized?.();
        throw error;
      }

      original.headers.Authorization = `Bearer ${token}`;
      return client(original);
    },
  );

  return client;
};
