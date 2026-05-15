import React from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import type { Bookmark } from '@rag/shared';
import BookmarkListScreen from '../screens/bookmarks/BookmarkListScreen';
import BookmarkDetailScreen from '../screens/bookmarks/BookmarkDetailScreen';

export type BookmarkStackParamList = {
  BookmarkList: undefined;
  BookmarkDetail: { bookmark: Bookmark };
};

const Stack = createNativeStackNavigator<BookmarkStackParamList>();

const BookmarkStack = () => (
  <Stack.Navigator screenOptions={{ headerShown: false }}>
    <Stack.Screen name="BookmarkList" component={BookmarkListScreen} />
    <Stack.Screen name="BookmarkDetail" component={BookmarkDetailScreen} />
  </Stack.Navigator>
);

export default BookmarkStack;
