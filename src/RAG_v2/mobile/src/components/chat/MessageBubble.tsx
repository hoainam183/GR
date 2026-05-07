/**
 * Message bubble — user or assistant message display.
 * Includes action bar (sources, feedback, copy) for assistant messages.
 */

import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import type { Message, RetrievedDocument } from '@rag/shared';
import StreamingText from './StreamingText';
import MarkdownDisplay from './MarkdownDisplay';
import MessageActions from './MessageActions';

interface Props {
  message: Message;
  onShowSources?: (sources: RetrievedDocument[]) => void;
}

const MessageBubble = ({ message, onShowSources }: Props) => {
  const isUser = message.role === 'user';
  const isStreaming = message.isStreaming ?? false;
  const hasSources = !isUser && (message.sources?.length ?? 0) > 0;

  return (
    <View
      style={[
        styles.row,
        isUser ? styles.rowUser : styles.rowAssistant,
      ]}
    >
      {/* Avatar */}
      {!isUser && (
        <View style={styles.avatarAssistant}>
          <Text style={styles.avatarText}>🎓</Text>
        </View>
      )}

      {/* Bubble */}
      <View
        style={[
          styles.bubble,
          isUser ? styles.bubbleUser : styles.bubbleAssistant,
        ]}
      >
        {isUser ? (
          <Text style={styles.userText}>{message.content}</Text>
        ) : isStreaming ? (
          <StreamingText content={message.content} isStreaming={true} />
        ) : (
          <MarkdownDisplay content={message.content} />
        )}

        {/* Mode badge + timing for assistant messages */}
        {!isUser && message.mode && !isStreaming && (
          <View style={styles.metaRow}>
            <View style={styles.badge}>
              <Text style={styles.badgeText}>
                {message.mode === 'agent' ? '🤖 Agent' : '📚 RAG'}
              </Text>
            </View>
            {message.timingsMs?.total != null && (
              <Text style={styles.timing}>
                {(message.timingsMs.total / 1000).toFixed(1)}s
              </Text>
            )}
          </View>
        )}

        {/* Action bar for completed assistant messages */}
        {!isUser && !isStreaming && (
          <MessageActions
            content={message.content}
            sources={message.sources}
            onShowSources={onShowSources}
          />
        )}
      </View>

      {/* User avatar */}
      {isUser && (
        <View style={styles.avatarUser}>
          <Text style={styles.avatarText}>👤</Text>
        </View>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    marginBottom: 12,
    paddingHorizontal: 12,
    gap: 8,
  },
  rowUser: {
    justifyContent: 'flex-end',
  },
  rowAssistant: {
    justifyContent: 'flex-start',
  },
  avatarAssistant: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: '#1e293b',
    justifyContent: 'center',
    alignItems: 'center',
    alignSelf: 'flex-end',
  },
  avatarUser: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: '#6366f1',
    justifyContent: 'center',
    alignItems: 'center',
    alignSelf: 'flex-end',
  },
  avatarText: {
    fontSize: 16,
  },
  bubble: {
    maxWidth: '78%',
    padding: 14,
    borderRadius: 18,
  },
  bubbleUser: {
    backgroundColor: '#6366f1',
    borderBottomRightRadius: 4,
  },
  bubbleAssistant: {
    backgroundColor: '#1e293b',
    borderBottomLeftRadius: 4,
  },
  userText: {
    color: '#ffffff',
    fontSize: 15,
    lineHeight: 22,
  },
  metaRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 8,
    gap: 8,
  },
  badge: {
    backgroundColor: '#0f172a',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  badgeText: {
    color: '#94a3b8',
    fontSize: 11,
    fontWeight: '600',
  },
  timing: {
    color: '#64748b',
    fontSize: 11,
  },
});

export default MessageBubble;
