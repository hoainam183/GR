/**
 * Streaming text display with cursor blink.
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
import MarkdownDisplay from './MarkdownDisplay';
import { useAppTheme } from '../../theme/theme';

interface Props {
  content: string;
  isStreaming: boolean;
}

const StreamingText = ({ content, isStreaming }: Props) => {
  const { colors } = useAppTheme();
  const opacity = useSharedValue(1);

  useEffect(() => {
    if (!isStreaming) {
      opacity.value = 0;
      return;
    }
    opacity.value = withRepeat(
      withSequence(
        withTiming(0, { duration: 500 }),
        withTiming(1, { duration: 500 }),
      ),
      -1,
      false,
    );
    return () => { opacity.value = 0; };
  }, [isStreaming, opacity]);

  const cursorStyle = useAnimatedStyle(() => ({
    opacity: opacity.value,
    backgroundColor: colors.primary,
  }));

  return (
    <View>
      <MarkdownDisplay content={content} />
      {isStreaming && <Animated.View style={[styles.cursor, cursorStyle]} />}
    </View>
  );
};

const styles = StyleSheet.create({
  cursor: {
    width: 2,
    height: 18,
    marginTop: -4,
    borderRadius: 1,
  },
});

export default StreamingText;
