import React, {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
} from 'react';
import { useColorScheme } from 'react-native';
import { DarkTheme, DefaultTheme, type Theme } from '@react-navigation/native';
import { getCache, setCache } from '../services/offlineCache';

export type ThemePreference = 'system' | 'light' | 'dark';

export interface AppColors {
  background: string;
  canvas: string;
  card: string;
  cardMuted: string;
  foreground: string;
  mutedForeground: string;
  subtleForeground: string;
  primary: string;
  primaryForeground: string;
  primarySoft: string;
  secondary: string;
  border: string;
  input: string;
  destructive: string;
  destructiveSoft: string;
  success: string;
  warning: string;
  overlay: string;
  chatUser: string;
  chatAssistant: string;
  tabBar: string;
}

const lightColors: AppColors = {
  background: '#fafafa',
  canvas: '#f3f4f6',
  card: '#ffffff',
  cardMuted: '#f8fafc',
  foreground: '#161a1f',
  mutedForeground: '#6b7280',
  subtleForeground: '#475569',
  primary: '#3b82f6',
  primaryForeground: '#ffffff',
  primarySoft: '#eff6ff',
  secondary: '#f3f4f6',
  border: '#e5e7eb',
  input: '#ffffff',
  destructive: '#ef4444',
  destructiveSoft: '#fee2e2',
  success: '#16a34a',
  warning: '#d97706',
  overlay: 'rgba(15, 23, 42, 0.42)',
  chatUser: '#eff6ff',
  chatAssistant: '#ffffff',
  tabBar: '#ffffff',
};

const darkColors: AppColors = {
  background: '#171b22',
  canvas: '#171b22',
  card: '#1c2028',
  cardMuted: '#1f242b',
  foreground: '#fafafa',
  mutedForeground: '#9ca3af',
  subtleForeground: '#cbd5e1',
  primary: '#3b82f6',
  primaryForeground: '#ffffff',
  primarySoft: '#1e3a5f',
  secondary: '#252a33',
  border: '#2d333d',
  input: '#1f242b',
  destructive: '#ef4444',
  destructiveSoft: '#451a1a',
  success: '#22c55e',
  warning: '#f59e0b',
  overlay: 'rgba(0, 0, 0, 0.58)',
  chatUser: '#1e3a5f',
  chatAssistant: '#1f242b',
  tabBar: '#1c2028',
};

const THEME_CACHE_KEY = 'appearance:theme:v1';

interface AppThemeValue {
  colors: AppColors;
  isDark: boolean;
  navigationTheme: Theme;
  preference: ThemePreference;
  setPreference: (next: ThemePreference) => void;
}

const AppThemeContext = createContext<AppThemeValue | null>(null);

const readStoredPreference = (): ThemePreference => {
  const stored = getCache<ThemePreference>(THEME_CACHE_KEY);
  return stored === 'light' || stored === 'dark' || stored === 'system'
    ? stored
    : 'system';
};

const buildNavigationTheme = (isDark: boolean, colors: AppColors): Theme => {
  const base = isDark ? DarkTheme : DefaultTheme;
  return {
    ...base,
    dark: isDark,
    colors: {
      ...base.colors,
      primary: colors.primary,
      background: colors.background,
      card: colors.card,
      text: colors.foreground,
      border: colors.border,
      notification: colors.destructive,
    },
  };
};

export const AppThemeProvider = ({ children }: { children: React.ReactNode }) => {
  const systemScheme = useColorScheme();
  const [preference, setPreferenceState] = useState(readStoredPreference);
  const isDark =
    preference === 'system' ? systemScheme === 'dark' : preference === 'dark';
  const colors = isDark ? darkColors : lightColors;

  const setPreference = useCallback((next: ThemePreference) => {
    setCache(THEME_CACHE_KEY, next);
    setPreferenceState(next);
  }, []);

  const value = useMemo(
    () => ({
      colors,
      isDark,
      navigationTheme: buildNavigationTheme(isDark, colors),
      preference,
      setPreference,
    }),
    [colors, isDark, preference, setPreference],
  );

  return <AppThemeContext.Provider value={value}>{children}</AppThemeContext.Provider>;
};

export const useAppTheme = (): AppThemeValue => {
  const value = useContext(AppThemeContext);
  if (!value) throw new Error('useAppTheme must be used within AppThemeProvider');
  return value;
};

