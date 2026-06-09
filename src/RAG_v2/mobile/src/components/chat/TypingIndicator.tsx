import React, { useEffect, useMemo } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withRepeat,
  withSequence,
  withDelay,
  withTiming,
} from 'react-native-reanimated';
import { useAppTheme, type AppColors } from '../../theme/theme';

interface Props {
  phase?: 'thinking' | 'streaming';
  label?: string;
}

const DOT_SIZE = 8;
const DOT_SPACING = 6;

const AnimatedDot = ({ delay }: { delay: number }) => {
  const { colors } = useAppTheme();
  const translateY = useSharedValue(0);

  useEffect(() => {
    translateY.value = withDelay(
      delay,
      withRepeat(
        withSequence(
          withTiming(-8, { duration: 300 }),
          withTiming(0, { duration: 300 }),
        ),
        -1,
        false,
      ),
    );
    return () => { translateY.value = 0; };
  }, [translateY, delay]);

  const animatedStyle = useAnimatedStyle(() => ({
    transform: [{ translateY: translateY.value }],
  }));

  return (
    <Animated.View
      style={[
        {
          width: DOT_SIZE,
          height: DOT_SIZE,
          borderRadius: DOT_SIZE / 2,
          backgroundColor: colors.primary,
          marginHorizontal: DOT_SPACING / 2,
        },
        animatedStyle,
      ]}
    />
  );
};

const TypingIndicator = ({ phase = 'thinking', label }: Props) => {
  const { colors } = useAppTheme();
  const styles = useMemo(() => createStyles(colors), [colors]);

  return (
    <View style={styles.container}>
      <View style={styles.bubble}>
        <View style={styles.dotsRow}>
          <AnimatedDot delay={0} />
          <AnimatedDot delay={150} />
          <AnimatedDot delay={300} />
        </View>
        <Text style={styles.label}>
          {label ?? (phase === 'thinking' ? 'Đang suy nghĩ...' : 'Đang trả lời...')}
        </Text>
      </View>
    </View>
  );
};

const createStyles = (colors: AppColors) =>
  StyleSheet.create({
    container: { paddingHorizontal: 16, paddingVertical: 4, alignItems: 'flex-start' },
    bubble: {
      flexDirection: 'row',
      alignItems: 'center',
      backgroundColor: colors.chatAssistant,
      borderWidth: 1,
      borderColor: colors.border,
      paddingHorizontal: 16,
      paddingVertical: 12,
      borderRadius: 16,
      borderTopLeftRadius: 4,
      gap: 10,
    },
    dotsRow: { flexDirection: 'row', alignItems: 'center' },
    label: { color: colors.mutedForeground, fontSize: 13, fontStyle: 'italic' },
  });

export default TypingIndicator;
