const TOKEN_KEY = 'token';
const LEGACY_TOKEN_KEY = 'access_token';
const USER_KEY = 'user';

export const getStoredToken = (): string | null =>
  localStorage.getItem(TOKEN_KEY) || localStorage.getItem(LEGACY_TOKEN_KEY);

export const setStoredToken = (token: string): void => {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.removeItem(LEGACY_TOKEN_KEY);
};

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
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(LEGACY_TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
};
