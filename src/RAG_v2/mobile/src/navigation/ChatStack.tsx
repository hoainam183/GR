/**
 * Chat stack — SessionList as home, ChatScreen as detail.
 */

import React from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import ChatScreen from '../screens/chat/ChatScreen';
import SessionListScreen from '../screens/chat/SessionListScreen';

export type ChatStackParamList = {
  SessionList: undefined;
  Chat: { sessionId?: string } | undefined;
};

const Stack = createNativeStackNavigator<ChatStackParamList>();

const ChatStack = () => (
  <Stack.Navigator
    screenOptions={{
      headerShown: false,
      animation: 'slide_from_right',
    }}
    initialRouteName="SessionList"
  >
    <Stack.Screen name="SessionList" component={SessionListScreen} />
    <Stack.Screen name="Chat" component={ChatScreen} />
  </Stack.Navigator>
);

export default ChatStack;
