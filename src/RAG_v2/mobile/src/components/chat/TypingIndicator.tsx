import React, { useEffect, useRef } from 'react';
import { Animated, StyleSheet, Text, View } from 'react-native';
import { useAppTheme, type AppColors } from '../../theme/theme';

interface Props {
  phase?: 'thinking' | 'streaming';
}

const DOT_SIZE = 8;
const DOT_SPACING = 6;

const TypingIndicator = ({ phase = 'thinking' }: Props) => {
  const { colors } = useAppTheme();
  const styles = createStyles(colors);
  const dot1 = useRef(new Animated.Value(0)).current;
  const dot2 = useRef(new Animated.Value(0)).current;
  const dot3 = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const bounce = (anim: Animated.Value, delay: number) =>
      Animated.loop(
        Animated.sequence([
          Animated.delay(delay),
          Animated.timing(anim, { toValue: -8, duration: 300, useNativeDriver: true }),
          Animated.timing(anim, { toValue: 0, duration: 300, useNativeDriver: true }),
        ]),
      );
    const animations = [bounce(dot1, 0), bounce(dot2, 150), bounce(dot3, 300)];
    animations.forEach((animation) => animation.start());
    return () => animations.forEach((animation) => animation.stop());
  }, [dot1, dot2, dot3]);

  return (
    <View style={styles.container}>
      <View style={styles.bubble}>
        <View style={styles.dotsRow}>
          {[dot1, dot2, dot3].map((anim, index) => (
            <Animated.View
              key={index}
              style={[styles.dot, { transform: [{ translateY: anim }] }]}
            />
          ))}
        </View>
        <Text style={styles.label}>
          {phase === 'thinking' ? 'Đang suy nghĩ...' : 'Đang trả lời...'}
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
    dotsRow: { flexDirection: 'row', alignItems: 'center', gap: DOT_SPACING },
    dot: {
      width: DOT_SIZE,
      height: DOT_SIZE,
      borderRadius: DOT_SIZE / 2,
      backgroundColor: colors.primary,
    },
    label: { color: colors.mutedForeground, fontSize: 13, fontStyle: 'italic' },
  });

export default TypingIndicator;
