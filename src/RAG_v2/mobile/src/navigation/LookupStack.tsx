import React from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import LookupScreen from '../screens/lookup/LookupScreen';

export type LookupStackParamList = {
  LookupHome: undefined;
};

const Stack = createNativeStackNavigator<LookupStackParamList>();

const LookupStack = () => (
  <Stack.Navigator screenOptions={{ headerShown: false }}>
    <Stack.Screen name="LookupHome" component={LookupScreen} />
  </Stack.Navigator>
);

export default LookupStack;
