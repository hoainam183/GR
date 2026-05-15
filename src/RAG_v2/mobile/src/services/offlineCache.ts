import { createMMKV } from 'react-native-mmkv';

const storage = createMMKV({ id: 'rag-mobile-cache' });

export const setCache = <T>(key: string, value: T): void => {
  storage.set(key, JSON.stringify(value));
};

export const getCache = <T>(key: string): T | undefined => {
  const raw = storage.getString(key);
  if (!raw) return undefined;
  try {
    return JSON.parse(raw) as T;
  } catch {
    storage.remove(key);
    return undefined;
  }
};

export const CACHE_KEYS = {
  bookmarks: 'bookmarks:v1',
  sessions: 'sessions:v1',
  suggestions: 'suggestions:v1',
} as const;
