/**
 * Network status banner — shows when the app is offline.
 */

import React, { useEffect, useState, useMemo } from 'react';
import { Text, StyleSheet } from 'react-native';
import Animated, { useSharedValue, useAnimatedStyle, withTiming } from 'react-native-reanimated';
import { Ionicons } from '@expo/vector-icons';
import NetInfo from '@react-native-community/netinfo';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useAppTheme, type AppColors } from '../../theme/theme';

const NetworkBanner = () => {
  const [isConnected, setIsConnected] = useState<boolean>(true);
  const translateY = useSharedValue(-100);
  const insets = useSafeAreaInsets();
  const { colors } = useAppTheme();
  const styles = useMemo(() => createStyles(colors), [colors]);

  useEffect(() => {
    const unsubscribe = NetInfo.addEventListener((state) => {
      const connected = (state.isConnected && state.isInternetReachable !== false) ?? false;
      setIsConnected(connected);
      translateY.value = withTiming(connected ? -100 : 0, { duration: 300 });
    });

    return unsubscribe;
  }, [translateY]);

  const animatedStyle = useAnimatedStyle(() => ({
    transform: [{ translateY: translateY.value }],
  }));

  if (isConnected) return null;

  return (
    <Animated.View
      style={[
        styles.container,
        { paddingTop: Math.max(insets.top, 20) },
        animatedStyle,
      ]}
      accessibilityLiveRegion="assertive"
      accessibilityLabel="Không có kết nối Internet"
    >
      <Ionicons name="wifi-outline" size={16} color={colors.primaryForeground} />
      <Text style={styles.text}>Không có kết nối Internet</Text>
    </Animated.View>
  );
};

const createStyles = (colors: AppColors) => StyleSheet.create({
  container: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    backgroundColor: colors.destructive,
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
    color: colors.primaryForeground,
    fontSize: 13,
    fontWeight: '600',
  },
});

export default NetworkBanner;
