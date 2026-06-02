import React from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import type { NotificationItem } from '@rag/shared';
import NotificationListScreen from '../screens/notifications/NotificationListScreen';
import NotificationDetailScreen from '../screens/notifications/NotificationDetailScreen';

export type NotificationStackParamList = {
  NotificationList: undefined;
  NotificationDetail: { notification: NotificationItem };
};

const Stack = createNativeStackNavigator<NotificationStackParamList>();

const NotificationStack = () => (
  <Stack.Navigator screenOptions={{ headerShown: false }}>
    <Stack.Screen name="NotificationList" component={NotificationListScreen} />
    <Stack.Screen name="NotificationDetail" component={NotificationDetailScreen} />
  </Stack.Navigator>
);

export default NotificationStack;
