/**
 * Main tab navigator — authenticated screens.
 */

import React from 'react';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { getFocusedRouteNameFromRoute } from '@react-navigation/native';
import { Ionicons } from '@expo/vector-icons';
import ChatStack from './ChatStack';
import ProfileStack from './ProfileStack';

export type MainTabParamList = {
  ChatTab: undefined;
  ProfileTab: undefined;
};

const Tab = createBottomTabNavigator<MainTabParamList>();

const MainTabNavigator = () => (
  <Tab.Navigator
    screenOptions={{
      headerShown: false,
      tabBarActiveTintColor: '#6366f1',
      tabBarInactiveTintColor: '#94a3b8',
      tabBarStyle: {
        backgroundColor: '#0f172a',
        borderTopColor: '#1e293b',
        borderTopWidth: 1,
        paddingBottom: 4,
        height: 56,
      },
      tabBarLabelStyle: {
        fontSize: 11,
        fontWeight: '600',
      },
    }}
  >
    <Tab.Screen
      name="ChatTab"
      component={ChatStack}
      options={({ route }) => {
        const routeName = getFocusedRouteNameFromRoute(route) ?? 'SessionList';
        const display = routeName === 'Chat' ? 'none' : 'flex';
        return {
          tabBarLabel: 'Chat',
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="chatbubbles-outline" size={size} color={color} />
          ),
          tabBarStyle: {
            display,
            backgroundColor: '#0f172a',
            borderTopColor: '#1e293b',
            borderTopWidth: 1,
            paddingBottom: 4,
            height: 56,
          },
        };
      }}
    />
    <Tab.Screen
      name="ProfileTab"
      component={ProfileStack}
      options={({ route }) => {
        const routeName = getFocusedRouteNameFromRoute(route) ?? 'Profile';
        const display = routeName === 'EditProfile' ? 'none' : 'flex';
        return {
          tabBarLabel: 'Hồ sơ',
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="person-outline" size={size} color={color} />
          ),
          tabBarStyle: {
            display,
            backgroundColor: '#0f172a',
            borderTopColor: '#1e293b',
            borderTopWidth: 1,
            paddingBottom: 4,
            height: 56,
          },
        };
      }}
    />
  </Tab.Navigator>
);

export default MainTabNavigator;
