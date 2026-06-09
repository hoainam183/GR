/**
 * Streaming text display with cursor blink.
 */

import React, { useEffect } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withRepeat,
  withSequence,
  withTiming,
} from 'react-native-reanimated';
import { useAppTheme } from '../../theme/theme';

interface Props {
  content: string;
  isStreaming: boolean;
}

// While streaming we render plain Text (cheap) and append an inline blinking
// cursor at the end of the text. MessageBubble swaps to MarkdownDisplay once
// streaming finishes, so the markdown AST is parsed exactly once (on done)
// instead of being rebuilt on every token.
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

  const cursorStyle = useAnimatedStyle(() => ({ opacity: opacity.value }));

  return (
    <View>
      <Text style={[styles.streamText, { color: colors.foreground }]}>
        {content}
        {isStreaming && (
          <Animated.Text style={[styles.cursor, { color: colors.primary }, cursorStyle]}>
            ▍
          </Animated.Text>
        )}
      </Text>
    </View>
  );
};

const styles = StyleSheet.create({
  streamText: {
    fontSize: 15,
    lineHeight: 22,
  },
  cursor: {
    fontSize: 15,
    lineHeight: 22,
  },
});

export default React.memo(StreamingText);
