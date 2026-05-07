/**
 * Root navigator — switches between Auth and Main flows based on auth state.
 */

import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { ActivityIndicator, View, StyleSheet } from 'react-native';
import AuthStack from './AuthStack';
import MainTabNavigator from './MainTabNavigator';
import { useAuth } from '../hooks/useAuth';

const RootNavigator = () => {
  const { isAuthenticated, isLoading } = useAuth();

  // Show loading spinner while restoring auth session
  if (isLoading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#6366f1" />
      </View>
    );
  }

  return (
    <NavigationContainer>
      {isAuthenticated ? <MainTabNavigator /> : <AuthStack />}
    </NavigationContainer>
  );
};

const styles = StyleSheet.create({
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#0f172a',
  },
});

export default RootNavigator;
