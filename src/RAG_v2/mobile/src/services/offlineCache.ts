import Constants, { ExecutionEnvironment } from 'expo-constants';

type CacheStorage = {
  set: (key: string, value: string) => void;
  getString: (key: string) => string | undefined;
  remove: (key: string) => unknown;
};

const memoryCache = new Map<string, string>();

const memoryStorage: CacheStorage = {
  set: (key, value) => {
    memoryCache.set(key, value);
  },
  getString: (key) => memoryCache.get(key),
  remove: (key) => memoryCache.delete(key),
};

const createCacheStorage = (): CacheStorage => {
  if (Constants.executionEnvironment === ExecutionEnvironment.StoreClient) {
    return memoryStorage;
  }

  try {
    const { createMMKV } = require('react-native-mmkv') as {
      createMMKV: (config: { id: string }) => CacheStorage;
    };
    return createMMKV({ id: 'rag-mobile-cache' });
  } catch (error) {
    console.warn('MMKV cache unavailable; using in-memory cache.', error);
    return memoryStorage;
  }
};

const storage = createCacheStorage();

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
