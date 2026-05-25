import axios, {
  AxiosError,
  type AxiosInstance,
  type InternalAxiosRequestConfig,
} from 'axios';
import {
  clearStoredAuth,
  getStoredToken,
  getStoredUser,
  isStoredTokenExpiringSoon,
  setStoredToken,
  setStoredUser,
} from '@/services/authStorage';
import type { TokenResponse, UserPublic } from '@/services/authApi';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

let refreshPromise: Promise<TokenResponse> | null = null;

interface RetryConfig extends InternalAxiosRequestConfig {
  _retry?: boolean;
}

const isAuthRefreshUrl = (url?: string) => Boolean(url?.includes('/auth/refresh'));

const parseErrorDetail = async (response: Response): Promise<string> => {
  const text = await response.text();
  if (!text) return `HTTP ${response.status}`;
  try {
    const parsed = JSON.parse(text) as { detail?: unknown };
    return typeof parsed.detail === 'string' ? parsed.detail : text;
  } catch {
    return text;
  }
};

export const getCurrentSessionUser = (): UserPublic | null =>
  getStoredUser<UserPublic>();

export const applyTokenResponse = (data: TokenResponse): TokenResponse => {
  setStoredToken(data.access_token, data.expires_in);
  setStoredUser(data.user);
  return data;
};

export const clearSession = (): void => {
  clearStoredAuth();
};

export const refreshSession = async (): Promise<TokenResponse> => {
  if (!refreshPromise) {
    refreshPromise = axios
      .post<TokenResponse>(
        `${API_BASE_URL}/auth/refresh`,
        {},
        { withCredentials: true },
      )
      .then((response) => applyTokenResponse(response.data))
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
};

export const ensureAccessToken = async (): Promise<string | null> => {
  const token = getStoredToken();
  if (token && !isStoredTokenExpiringSoon()) {
    return token;
  }

  try {
    const refreshed = await refreshSession();
    return refreshed.access_token;
  } catch {
    clearSession();
    return null;
  }
};

export const ensureSession = async (): Promise<UserPublic | null> => {
  // Fast path: access token is already in memory and not expiring soon.
  // Trust the cached user — the token is still valid.
  const cachedToken = getStoredToken();
  if (cachedToken && !isStoredTokenExpiringSoon()) {
    const cachedUser = getStoredUser<UserPublic>();
    if (cachedUser) return cachedUser;
  }

  // Need a fresh access token. The /auth/refresh response already contains
  // the full user object, so we skip an extra /auth/me round-trip.
  try {
    const refreshed = await refreshSession();
    return refreshed.user;
  } catch {
    clearSession();
    return null;
  }
};

export const logoutSession = async (): Promise<void> => {
  try {
    await fetch(`${API_BASE_URL}/auth/logout`, {
      method: 'POST',
      credentials: 'include',
    });
  } finally {
    clearSession();
  }
};

export const installAuthInterceptors = (client: AxiosInstance): void => {
  client.defaults.withCredentials = true;

  client.interceptors.request.use(async (config) => {
    // Auth endpoints that create or destroy a session don't need a Bearer token.
    const url = config.url ?? '';
    if (url.includes('/auth/login') || url.includes('/auth/register')) {
      return config;
    }

    const token = await ensureAccessToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  });

  client.interceptors.response.use(
    (response) => response,
    async (error: AxiosError) => {
      const response = error.response;
      const original = error.config as RetryConfig | undefined;
      if (
        response?.status !== 401 ||
        !original ||
        original._retry ||
        isAuthRefreshUrl(original.url)
      ) {
        throw error;
      }

      original._retry = true;
      const refreshed = await refreshSession().catch(() => null);
      if (!refreshed) {
        clearSession();
        throw error;
      }

      original.headers.Authorization = `Bearer ${refreshed.access_token}`;
      return client(original);
    },
  );
};

export const authFetch = async (
  input: string,
  init: RequestInit = {},
  retry = true,
): Promise<Response> => {
  const token = await ensureAccessToken();
  const headers = new Headers(init.headers);
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  const url = input.startsWith('http')
    ? input
    : `${API_BASE_URL}${input.startsWith('/') ? input : `/${input}`}`;
  const response = await fetch(url, {
    ...init,
    headers,
    credentials: 'include',
  });

  if (response.status !== 401 || !retry) {
    return response;
  }

  const refreshed = await refreshSession().catch(() => null);
  if (!refreshed) {
    clearSession();
    return response;
  }

  headers.set('Authorization', `Bearer ${refreshed.access_token}`);
  return fetch(url, {
    ...init,
    headers,
    credentials: 'include',
  });
};

export const throwIfNotOk = async (
  response: Response,
  fallback: string,
): Promise<void> => {
  if (response.ok) return;
  throw new Error((await parseErrorDetail(response)) || fallback);
};
