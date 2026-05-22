/**
 * App entry point — wraps the app with all required providers.
 */

import React from 'react';
import { StatusBar } from 'expo-status-bar';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import ErrorBoundary from './src/components/common/ErrorBoundary';
import RootNavigator from './src/navigation/RootNavigator';
import NetworkBanner from './src/components/common/NetworkBanner';
import { AppThemeProvider, useAppTheme } from './src/theme/theme';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      staleTime: 5 * 60 * 1000, // 5 minutes
    },
  },
});

const AppChrome = () => {
  const { isDark } = useAppTheme();

  return (
    <ErrorBoundary>
      <StatusBar style={isDark ? 'light' : 'dark'} />
      <NetworkBanner />
      <RootNavigator />
    </ErrorBoundary>
  );
};

export default function App() {
  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <QueryClientProvider client={queryClient}>
          <AppThemeProvider>
            <AppChrome />
          </AppThemeProvider>
        </QueryClientProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}
