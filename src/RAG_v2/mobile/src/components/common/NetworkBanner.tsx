/**
 * Network status banner — shows when the app is offline.
 */

import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, Animated } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import NetInfo from '@react-native-community/netinfo';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

const NetworkBanner = () => {
  const [isConnected, setIsConnected] = useState<boolean>(true);
  const translateY = useState(new Animated.Value(-100))[0];
  const insets = useSafeAreaInsets();

  useEffect(() => {
    const unsubscribe = NetInfo.addEventListener((state) => {
      const connected = (state.isConnected && state.isInternetReachable !== false) ?? false;
      setIsConnected(connected);

      Animated.timing(translateY, {
        toValue: connected ? -100 : 0,
        duration: 300,
        useNativeDriver: true,
      }).start();
    });

    return unsubscribe;
  }, [translateY]);

  if (isConnected) return null;

  return (
    <Animated.View
      style={[
        styles.container,
        {
          paddingTop: Math.max(insets.top, 20),
          transform: [{ translateY }],
        },
      ]}
    >
      <Ionicons name="wifi-outline" size={16} color="#ffffff" />
      <Text style={styles.text}>Không có kết nối Internet</Text>
    </Animated.View>
  );
};

const styles = StyleSheet.create({
  container: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    backgroundColor: '#ef4444',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingBottom: 10,
    paddingHorizontal: 16,
    gap: 8,
    zIndex: 9999,
    elevation: 10,
  },
  text: {
    color: '#ffffff',
    fontSize: 13,
    fontWeight: '600',
  },
});

export default NetworkBanner;
