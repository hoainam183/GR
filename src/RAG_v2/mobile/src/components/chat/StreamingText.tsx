/**
 * Streaming text display with cursor blink.
 */

import React, { useEffect, useRef } from 'react';
import { Animated, StyleSheet, View } from 'react-native';
import MarkdownDisplay from './MarkdownDisplay';

interface Props {
  content: string;
  isStreaming: boolean;
}

const StreamingText = ({ content, isStreaming }: Props) => {
  const cursorOpacity = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    if (!isStreaming) {
      cursorOpacity.setValue(0);
      return;
    }

    const blink = Animated.loop(
      Animated.sequence([
        Animated.timing(cursorOpacity, {
          toValue: 0,
          duration: 500,
          useNativeDriver: true,
        }),
        Animated.timing(cursorOpacity, {
          toValue: 1,
          duration: 500,
          useNativeDriver: true,
        }),
      ]),
    );
    blink.start();
    return () => blink.stop();
  }, [isStreaming, cursorOpacity]);

  return (
    <View>
      <MarkdownDisplay content={content} />
      {isStreaming && (
        <Animated.View
          style={[styles.cursor, { opacity: cursorOpacity }]}
        />
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  cursor: {
    width: 2,
    height: 18,
    backgroundColor: '#6366f1',
    marginTop: -4,
    borderRadius: 1,
  },
});

export default StreamingText;
