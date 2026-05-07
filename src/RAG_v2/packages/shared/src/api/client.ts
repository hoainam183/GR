/**
 * Platform-agnostic API client factory.
 *
 * Both web and mobile create their own client instance by calling
 * `createApiClient()` and providing a platform-specific `getToken`
 * callback (localStorage on web, expo-secure-store on mobile).
 */

import axios, { type AxiosInstance } from 'axios';

export interface ApiClientConfig {
  /** Base URL of the backend API (e.g. http://localhost:8000) */
  baseURL: string;
  /** Async callback that returns the current access token, or null */
  getToken?: () => Promise<string | null>;
  /** Request timeout in ms (default: 120_000) */
  timeout?: number;
}

/**
 * Create a configured Axios instance with automatic Bearer token injection.
 */
export const createApiClient = (config: ApiClientConfig): AxiosInstance => {
  const client = axios.create({
    baseURL: config.baseURL,
    timeout: config.timeout ?? 120_000,
    headers: { 'Content-Type': 'application/json' },
  });

  // Inject Authorization header on every request
  client.interceptors.request.use(async (req) => {
    if (config.getToken) {
      const token = await config.getToken();
      if (token) req.headers.Authorization = `Bearer ${token}`;
    }
    return req;
  });

  return client;
};
