/**
 * Main tab navigator — authenticated screens.
 */

import React from 'react';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { getFocusedRouteNameFromRoute } from '@react-navigation/native';
import { Ionicons } from '@expo/vector-icons';
import { useQuery } from '@tanstack/react-query';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { getUnreadCount } from '@rag/shared';
import { apiClient } from '../services/api';
import ChatStack from './ChatStack';
import ProfileStack from './ProfileStack';
import LookupStack from './LookupStack';
import BookmarkStack from './BookmarkStack';
import NotificationStack from './NotificationStack';
import { useAppTheme } from '../theme/theme';

export type MainTabParamList = {
  ChatTab: undefined;
  LookupTab: undefined;
  BookmarkTab: undefined;
  NotificationTab: undefined;
  ProfileTab: undefined;
};

const Tab = createBottomTabNavigator<MainTabParamList>();

const MainTabNavigator = () => {
  const { colors } = useAppTheme();
  const insets = useSafeAreaInsets();
  const { data: unreadData } = useQuery({
    queryKey: ['notifications-unread-count'],
    queryFn: () => getUnreadCount(apiClient),
    staleTime: 30_000,
  });
  const unreadCount = unreadData?.unread_count ?? 0;
  const bottomPadding = Math.max(insets.bottom, 8);
  const tabBarBaseStyle = {
    backgroundColor: colors.tabBar,
    borderTopColor: colors.border,
    borderTopWidth: 1,
    height: 58 + bottomPadding,
    paddingTop: 6,
    paddingBottom: bottomPadding,
  };

  return (
  <Tab.Navigator
    screenOptions={{
      headerShown: false,
      tabBarActiveTintColor: colors.primary,
      tabBarInactiveTintColor: colors.mutedForeground,
      tabBarStyle: tabBarBaseStyle,
      tabBarLabelStyle: {
        fontSize: 11,
        fontWeight: '600',
        lineHeight: 13,
      },
      tabBarItemStyle: {
        paddingVertical: 2,
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
            ...tabBarBaseStyle,
            display,
          },
        };
      }}
    />
    <Tab.Screen
      name="LookupTab"
      component={LookupStack}
      options={{
        tabBarLabel: 'Tra cứu',
        tabBarIcon: ({ color, size }) => (
          <Ionicons name="search-outline" size={size} color={color} />
        ),
      }}
    />
    <Tab.Screen
      name="BookmarkTab"
      component={BookmarkStack}
      options={{
        tabBarLabel: 'Đã lưu',
        tabBarIcon: ({ color, size }) => (
          <Ionicons name="bookmark-outline" size={size} color={color} />
        ),
      }}
    />
    <Tab.Screen
      name="NotificationTab"
      component={NotificationStack}
      options={{
        tabBarLabel: 'Thông báo',
        tabBarIcon: ({ color, size }) => (
          <Ionicons name="notifications-outline" size={size} color={color} />
        ),
        tabBarBadge: unreadCount > 0 ? unreadCount : undefined,
        tabBarBadgeStyle: {
          backgroundColor: colors.destructive,
          color: colors.primaryForeground,
          fontSize: 10,
        },
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
            ...tabBarBaseStyle,
            display,
          },
        };
      }}
    />
  </Tab.Navigator>
  );
};

export default MainTabNavigator;
