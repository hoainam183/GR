/**
 * Reusable loading spinner with pulsing animation.
 */

import React, { useEffect } from 'react';
import { StyleSheet, View } from 'react-native';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withRepeat,
  withSequence,
  withTiming,
} from 'react-native-reanimated';
import { useAppTheme } from '../../theme/theme';

interface Props {
  size?: number;
  color?: string;
}

const LoadingSpinner = ({ size = 40, color }: Props) => {
  const { colors } = useAppTheme();
  const scale = useSharedValue(1);

  useEffect(() => {
    scale.value = withRepeat(
      withSequence(
        withTiming(1.2, { duration: 600 }),
        withTiming(1, { duration: 600 }),
      ),
      -1,
      false,
    );
    return () => { scale.value = 1; };
  }, [scale]);

  const animatedStyle = useAnimatedStyle(() => ({
    transform: [{ scale: scale.value }],
    width: size,
    height: size,
    borderRadius: size / 2,
    backgroundColor: color ?? colors.primary,
    opacity: 0.3,
  }));

  return (
    <View style={styles.container}>
      <Animated.View style={animatedStyle} />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    justifyContent: 'center',
    alignItems: 'center',
    padding: 16,
  },
});

export default LoadingSpinner;
