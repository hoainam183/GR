const TOKEN_KEY = 'token';
const LEGACY_TOKEN_KEY = 'access_token';
const USER_KEY = 'user';

let memoryToken: string | null = null;
let memoryTokenExpiresAt = 0;

const decodeJwtExpiry = (token: string): number => {
  const [, payload] = token.split('.');
  if (!payload) return 0;

  try {
    const normalized = payload.replace(/-/g, '+').replace(/_/g, '/');
    const decoded = JSON.parse(window.atob(normalized)) as { exp?: unknown };
    return typeof decoded.exp === 'number' ? decoded.exp * 1000 : 0;
  } catch {
    return 0;
  }
};

const readLegacyToken = (): string | null => {
  const token = localStorage.getItem(TOKEN_KEY) || localStorage.getItem(LEGACY_TOKEN_KEY);
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(LEGACY_TOKEN_KEY);
  return token;
};

export const getStoredToken = (): string | null => {
  if (memoryToken) {
    return memoryToken;
  }

  const legacyToken = readLegacyToken();
  if (legacyToken) {
    memoryToken = legacyToken;
    memoryTokenExpiresAt = decodeJwtExpiry(legacyToken);
  }
  return memoryToken;
};

export const setStoredToken = (token: string, expiresIn?: number): void => {
  memoryToken = token;
  memoryTokenExpiresAt = expiresIn
    ? Date.now() + expiresIn * 1000
    : decodeJwtExpiry(token);
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(LEGACY_TOKEN_KEY);
};

export const getStoredTokenExpiresAt = (): number => memoryTokenExpiresAt;

export const isStoredTokenExpiringSoon = (skewMs = 60_000): boolean =>
  !memoryToken || !memoryTokenExpiresAt || memoryTokenExpiresAt - Date.now() <= skewMs;

export const setStoredUser = (user: unknown): void => {
  localStorage.setItem(USER_KEY, JSON.stringify(user));
};

export const getStoredUser = <T extends object = Record<string, unknown>>(): T | null => {
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) {
    return null;
  }

  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== 'object') {
      localStorage.removeItem(USER_KEY);
      return null;
    }
    return parsed as T;
  } catch {
    localStorage.removeItem(USER_KEY);
    return null;
  }
};

export const clearStoredUser = (): void => {
  localStorage.removeItem(USER_KEY);
};

export const clearStoredAuth = (): void => {
  memoryToken = null;
  memoryTokenExpiresAt = 0;
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(LEGACY_TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
};
