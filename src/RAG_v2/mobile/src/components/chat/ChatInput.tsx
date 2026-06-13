/**
 * Chat input — multiline text input with send button.
 */

import React, { useState, useRef, useMemo, useEffect } from 'react';
import {
  View,
  TextInput,
  Pressable,
  StyleSheet,
  type NativeSyntheticEvent,
  type TextInputContentSizeChangeEventData,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import { useAppTheme, type AppColors } from '../../theme/theme';

interface Props {
  onSend: (message: string) => void;
  disabled?: boolean;
  placeholder?: string;
  bottomInset?: number;
  onFocus?: () => void;
}

const MAX_INPUT_HEIGHT = 120;
const MIN_INPUT_HEIGHT = 44;

// DESIGN §5.5: placeholder xoay vòng theo chủ đề sinh viên hay hỏi.
const ROTATING_PLACEHOLDERS = [
  'Hỏi về học phí, lịch thi, quy chế…',
  'Thủ tục đăng ký học lại?',
  'Điều kiện xét học bổng KKHT?',
  'Lịch nộp học phí kỳ này?',
];

const ChatInput = ({
  onSend,
  disabled = false,
  placeholder,
  bottomInset = 0,
  onFocus,
}: Props) => {
  const { colors } = useAppTheme();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [text, setText] = useState('');
  const [inputHeight, setInputHeight] = useState(MIN_INPUT_HEIGHT);
  const [placeholderIndex, setPlaceholderIndex] = useState(0);
  const inputRef = useRef<TextInput>(null);

  // Rotate the hint only while the field is empty; a fixed `placeholder` prop
  // (if supplied by the caller) always wins.
  useEffect(() => {
    if (placeholder || text.length > 0) return;
    const timer = setInterval(
      () => setPlaceholderIndex((i) => (i + 1) % ROTATING_PLACEHOLDERS.length),
      3500,
    );
    return () => clearInterval(timer);
  }, [placeholder, text.length]);

  const activePlaceholder =
    placeholder ?? ROTATING_PLACEHOLDERS[placeholderIndex];

  const handleSend = () => {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    onSend(trimmed);
    setText('');
    setInputHeight(MIN_INPUT_HEIGHT);
  };

  const handleContentSizeChange = (
    e: NativeSyntheticEvent<TextInputContentSizeChangeEventData>,
  ) => {
    const newHeight = Math.min(
      Math.max(e.nativeEvent.contentSize.height, MIN_INPUT_HEIGHT),
      MAX_INPUT_HEIGHT,
    );
    setInputHeight(newHeight);
  };

  const canSend = text.trim().length > 0 && !disabled;
  // Hug the bottom edge: keep just enough clearance for the gesture pill rather
  // than the full safe-area inset (which left the bar floating too high).
  const containerPaddingBottom =
    bottomInset > 0 ? Math.max(8, Math.round(bottomInset * 0.5)) : 8;

  return (
    <View style={[styles.container, { paddingBottom: containerPaddingBottom }]}>
      <View style={styles.inputWrapper}>
        <TextInput
          ref={inputRef}
          style={[styles.input, { height: inputHeight }]}
          value={text}
          onChangeText={setText}
          placeholder={activePlaceholder}
          placeholderTextColor={colors.mutedForeground}
          multiline
          editable={!disabled}
          onFocus={onFocus}
          onContentSizeChange={handleContentSizeChange}
          returnKeyType="default"
          blurOnSubmit={false}
          accessibilityLabel="Nhập câu hỏi"
        />
        <Pressable
          style={[styles.sendButton, canSend && styles.sendButtonActive]}
          onPress={handleSend}
          disabled={!canSend}
          accessibilityLabel="Gửi"
          accessibilityRole="button"
          accessibilityState={{ disabled: !canSend }}
        >
          <Ionicons
            name="send"
            size={20}
            color={canSend ? colors.primaryForeground : colors.mutedForeground}
          />
        </Pressable>
      </View>
    </View>
  );
};

const createStyles = (colors: AppColors) => StyleSheet.create({
  container: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    backgroundColor: colors.background,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  inputWrapper: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    backgroundColor: colors.input,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 24,
    paddingLeft: 16,
    paddingRight: 4,
    paddingVertical: 4,
  },
  input: {
    flex: 1,
    color: colors.foreground,
    fontSize: 15,
    lineHeight: 21,
    paddingTop: 10,
    paddingBottom: 10,
    maxHeight: MAX_INPUT_HEIGHT,
  },
  sendButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: colors.secondary,
    marginBottom: 2,
  },
  sendButtonActive: {
    backgroundColor: colors.primary,
  },
});

export default ChatInput;
