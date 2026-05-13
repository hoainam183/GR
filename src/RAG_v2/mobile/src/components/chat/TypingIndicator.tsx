/**
 * Typing indicator — three bouncing dots animation.
 * Shows "Thinking" or "Streaming" phase.
 */

import React, { useEffect, useRef } from 'react';
import { Animated, View, Text, StyleSheet } from 'react-native';

interface Props {
  phase?: 'thinking' | 'streaming';
}

const DOT_SIZE = 8;
const DOT_SPACING = 6;

const TypingIndicator = ({ phase = 'thinking' }: Props) => {
  const dot1 = useRef(new Animated.Value(0)).current;
  const dot2 = useRef(new Animated.Value(0)).current;
  const dot3 = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const createBounce = (anim: Animated.Value, delay: number) =>
      Animated.loop(
        Animated.sequence([
          Animated.delay(delay),
          Animated.timing(anim, {
            toValue: -8,
            duration: 300,
            useNativeDriver: true,
          }),
          Animated.timing(anim, {
            toValue: 0,
            duration: 300,
            useNativeDriver: true,
          }),
        ]),
      );

    const a1 = createBounce(dot1, 0);
    const a2 = createBounce(dot2, 150);
    const a3 = createBounce(dot3, 300);

    a1.start();
    a2.start();
    a3.start();

    return () => {
      a1.stop();
      a2.stop();
      a3.stop();
    };
  }, [dot1, dot2, dot3]);

  return (
    <View style={styles.container}>
      <View style={styles.bubble}>
        <View style={styles.dotsRow}>
          {[dot1, dot2, dot3].map((anim, i) => (
            <Animated.View
              key={i}
              style={[
                styles.dot,
                { transform: [{ translateY: anim }] },
              ]}
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

const styles = StyleSheet.create({
  container: {
    paddingHorizontal: 16,
    paddingVertical: 4,
    alignItems: 'flex-start',
  },
  bubble: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1e293b',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderRadius: 16,
    borderTopLeftRadius: 4,
    gap: 10,
  },
  dotsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: DOT_SPACING,
  },
  dot: {
    width: DOT_SIZE,
    height: DOT_SIZE,
    borderRadius: DOT_SIZE / 2,
    backgroundColor: '#6366f1',
  },
  label: {
    color: '#94a3b8',
    fontSize: 13,
    fontStyle: 'italic',
  },
});

export default TypingIndicator;
