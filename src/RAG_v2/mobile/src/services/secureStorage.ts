/**
 * Secure storage wrapper for sensitive data (tokens, user profile).
 *
 * Uses expo-secure-store which encrypts values in the OS keychain (iOS)
 * or Keystore (Android).
 */

import * as SecureStore from 'expo-secure-store';

const KEYS = {
  ACCESS_TOKEN: 'auth_access_token',
  REFRESH_TOKEN: 'auth_refresh_token',
  USER_PROFILE: 'user_profile',
  SESSION_ID: 'current_session_id',
} as const;

// ─── Token management ────────────────────────────────────────────────────────

export const setToken = async (
  access: string,
  refresh?: string,
): Promise<void> => {
  await SecureStore.setItemAsync(KEYS.ACCESS_TOKEN, access);
  if (refresh) {
    await SecureStore.setItemAsync(KEYS.REFRESH_TOKEN, refresh);
  }
};

export const getToken = async (): Promise<string | null> =>
  SecureStore.getItemAsync(KEYS.ACCESS_TOKEN);

export const getRefreshToken = async (): Promise<string | null> =>
  SecureStore.getItemAsync(KEYS.REFRESH_TOKEN);

export const clearTokens = async (): Promise<void> => {
  await SecureStore.deleteItemAsync(KEYS.ACCESS_TOKEN);
  await SecureStore.deleteItemAsync(KEYS.REFRESH_TOKEN);
};

// ─── User profile cache ──────────────────────────────────────────────────────

export const setUserProfile = async (profile: object): Promise<void> =>
  SecureStore.setItemAsync(KEYS.USER_PROFILE, JSON.stringify(profile));

export const getUserProfile = async <T = object>(): Promise<T | null> => {
  const raw = await SecureStore.getItemAsync(KEYS.USER_PROFILE);
  return raw ? (JSON.parse(raw) as T) : null;
};

export const clearUserProfile = async (): Promise<void> =>
  SecureStore.deleteItemAsync(KEYS.USER_PROFILE);

// ─── Session ID ──────────────────────────────────────────────────────────────

export const setCurrentSessionId = async (sessionId: string): Promise<void> =>
  SecureStore.setItemAsync(KEYS.SESSION_ID, sessionId);

export const getCurrentSessionId = async (): Promise<string | null> =>
  SecureStore.getItemAsync(KEYS.SESSION_ID);

export const clearCurrentSessionId = async (): Promise<void> =>
  SecureStore.deleteItemAsync(KEYS.SESSION_ID);

// ─── Clear all ───────────────────────────────────────────────────────────────

export const clearAll = async (): Promise<void> => {
  await clearTokens();
  await clearUserProfile();
  await clearCurrentSessionId();
};
