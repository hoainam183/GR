import React from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import NotificationListScreen from '../screens/notifications/NotificationListScreen';

export type NotificationStackParamList = {
  NotificationList: undefined;
};

const Stack = createNativeStackNavigator<NotificationStackParamList>();

const NotificationStack = () => (
  <Stack.Navigator screenOptions={{ headerShown: false }}>
    <Stack.Screen name="NotificationList" component={NotificationListScreen} />
  </Stack.Navigator>
);

export default NotificationStack;
