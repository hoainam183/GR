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
  primaryPressed: string;
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

// HUST / Cổng thông tin đào tạo identity per DESIGN.md §2.
// Red (--bk-red) is an *accent* — used for primary actions, the user bubble,
// avatars, the FAB and citation accents — not as a wide background.
const lightColors: AppColors = {
  background: '#ffffff', // --surface: header & input bar
  canvas: '#f5f6f8', // --surface-alt: page / conversation area
  card: '#ffffff', // --surface
  cardMuted: '#f8fafc',
  foreground: '#1f2328', // --ink
  mutedForeground: '#5b6470', // --ink-soft
  subtleForeground: '#475569',
  primary: '#c02430', // --bk-red
  primaryPressed: '#9a1b26', // --bk-red-dark
  primaryForeground: '#ffffff',
  primarySoft: '#fbeaec', // --bk-red-tint
  secondary: '#f3f4f6',
  border: '#e3e6ea', // --border
  input: '#ffffff',
  destructive: '#c0392b', // --error
  destructiveSoft: '#fbeaec',
  success: '#1e7f4e', // --success
  warning: '#b7791f', // --warning
  overlay: 'rgba(31, 35, 40, 0.42)',
  chatUser: '#c02430', // user bubble = --bk-red (white text)
  chatAssistant: '#ffffff', // bot bubble = --surface
  tabBar: '#ffffff',
};

const darkColors: AppColors = {
  background: '#15171a',
  canvas: '#15171a',
  card: '#1f2226',
  cardMuted: '#23272c',
  foreground: '#e8eaed',
  mutedForeground: '#9aa3ad',
  subtleForeground: '#cbd5e1',
  primary: '#e5535e', // --bk-red lifted for dark-mode contrast
  primaryPressed: '#c83d49',
  primaryForeground: '#ffffff',
  primarySoft: '#3a2024',
  secondary: '#252a33',
  border: '#2d333d',
  input: '#1f2226',
  destructive: '#e5535e',
  destructiveSoft: '#3a2024',
  success: '#36b37e',
  warning: '#e0a13c',
  overlay: 'rgba(0, 0, 0, 0.58)',
  chatUser: '#e5535e',
  chatAssistant: '#1f2226',
  tabBar: '#1f2226',
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

