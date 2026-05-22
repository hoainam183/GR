/**
 * Root navigator — switches between Auth and Main flows based on auth state.
 */

import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { ActivityIndicator, View, StyleSheet } from 'react-native';
import AuthStack from './AuthStack';
import MainTabNavigator from './MainTabNavigator';
import { useAuth } from '../hooks/useAuth';
import { useAppTheme, type AppColors } from '../theme/theme';

const RootNavigator = () => {
  const { isAuthenticated, isLoading } = useAuth();
  const { colors, navigationTheme } = useAppTheme();
  const styles = createStyles(colors);

  // Show loading spinner while restoring auth session
  if (isLoading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color={colors.primary} />
      </View>
    );
  }

  return (
    <NavigationContainer theme={navigationTheme}>
      {isAuthenticated ? <MainTabNavigator /> : <AuthStack />}
    </NavigationContainer>
  );
};

const createStyles = (colors: AppColors) => StyleSheet.create({
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: colors.background,
  },
});

export default RootNavigator;
