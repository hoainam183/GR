import React, { useMemo } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import type { Message, RetrievedDocument } from '@rag/shared';
import StreamingText from './StreamingText';
import MarkdownDisplay from './MarkdownDisplay';
import MessageActions from './MessageActions';
import { useAppTheme, type AppColors } from '../../theme/theme';

interface Props {
  message: Message;
  onShowSources?: (sources: RetrievedDocument[]) => void;
}

const MessageBubble = React.memo(({ message, onShowSources }: Props) => {
  const { colors } = useAppTheme();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const isUser = message.role === 'user';
  const isStreaming = message.isStreaming ?? false;

  return (
    <View style={[styles.row, isUser ? styles.rowUser : styles.rowAssistant]}>
      {!isUser && (
        <View style={styles.avatarAssistant}>
          <Ionicons name="school" size={16} color={colors.primary} />
        </View>
      )}
      <View
        style={[styles.bubble, isUser ? styles.bubbleUser : styles.bubbleAssistant]}
        accessibilityRole="text"
        accessibilityLabel={`${isUser ? 'Bạn' : 'Trợ lý'}: ${message.content}`}
      >
        {isUser ? (
          <Text style={styles.userText}>{message.content}</Text>
        ) : isStreaming ? (
          <StreamingText content={message.content} isStreaming />
        ) : (
          <MarkdownDisplay content={message.content} />
        )}
        {!isUser && message.mode && !isStreaming && (
          <View style={styles.metaRow}>
            <View style={styles.badge}>
              <Text style={styles.badgeText}>{message.mode === 'agent' ? 'Agent' : 'RAG'}</Text>
            </View>
            {message.timingsMs?.total != null && (
              <Text style={styles.timing}>{(message.timingsMs.total / 1000).toFixed(1)}s</Text>
            )}
          </View>
        )}
        {!isUser && !isStreaming && (
          <MessageActions
            content={message.content}
            sources={message.sources}
            sessionId={message.sessionId}
            turnId={message.turnId}
            onShowSources={onShowSources}
          />
        )}
      </View>
      {isUser && (
        <View style={styles.avatarUser}>
          <Ionicons name="person" size={15} color={colors.primaryForeground} />
        </View>
      )}
    </View>
  );
});

const createStyles = (colors: AppColors) =>
  StyleSheet.create({
    row: { flexDirection: 'row', marginBottom: 12, paddingHorizontal: 12, gap: 8 },
    rowUser: { justifyContent: 'flex-end' },
    rowAssistant: { justifyContent: 'flex-start' },
    avatarAssistant: {
      width: 32,
      height: 32,
      borderRadius: 16,
      backgroundColor: colors.secondary,
      borderWidth: 1,
      borderColor: colors.border,
      justifyContent: 'center',
      alignItems: 'center',
      alignSelf: 'flex-end',
    },
    avatarUser: {
      width: 32,
      height: 32,
      borderRadius: 16,
      backgroundColor: colors.primary,
      justifyContent: 'center',
      alignItems: 'center',
      alignSelf: 'flex-end',
    },
    bubble: { maxWidth: '82%', padding: 14, borderRadius: 18, borderWidth: 1 },
    bubbleUser: {
      backgroundColor: colors.chatUser,
      borderColor: colors.border,
      borderBottomRightRadius: 4,
    },
    bubbleAssistant: {
      backgroundColor: colors.chatAssistant,
      borderColor: colors.border,
      borderBottomLeftRadius: 4,
    },
    userText: { color: colors.foreground, fontSize: 15, lineHeight: 22 },
    metaRow: { flexDirection: 'row', alignItems: 'center', marginTop: 8, gap: 8 },
    badge: {
      backgroundColor: colors.secondary,
      paddingHorizontal: 8,
      paddingVertical: 3,
      borderRadius: 6,
    },
    badgeText: { color: colors.mutedForeground, fontSize: 11, fontWeight: '600' },
    timing: { color: colors.mutedForeground, fontSize: 11 },
  });

export default MessageBubble;
