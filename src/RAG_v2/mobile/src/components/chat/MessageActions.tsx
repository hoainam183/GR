/**
 * Message actions bar — feedback, sources, and copy actions for assistant messages.
 */

import React, { useState } from 'react';
import { View, Pressable, Text, StyleSheet, Share, Alert } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import type { RetrievedDocument } from '@rag/shared';
import { createBookmark, submitFeedback } from '@rag/shared';
import { apiClient } from '../../services/api';

interface Props {
  content: string;
  sources?: RetrievedDocument[];
  sessionId?: string;
  turnId?: number;
  onShowSources?: (sources: RetrievedDocument[]) => void;
}

const MessageActions = ({
  content,
  sources,
  sessionId,
  turnId,
  onShowSources,
}: Props) => {
  const [feedback, setFeedback] = useState<'up' | 'down' | null>(null);
  const [copied, setCopied] = useState(false);
  const [bookmarked, setBookmarked] = useState(false);

  const handleCopy = async () => {
    try {
      await Share.share({ message: content });
    } catch {
      // Ignore share cancellation
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleFeedback = async (type: 'up' | 'down') => {
    if (!sessionId || !turnId) {
      Alert.alert('Chưa thể gửi đánh giá', 'Vui lòng mở lại hội thoại sau khi câu trả lời được lưu.');
      return;
    }
    setFeedback((prev) => (prev === type ? null : type));
    try {
      await submitFeedback(apiClient, {
        session_id: sessionId,
        turn_id: turnId,
        rating: type,
        category: type === 'down' ? 'incomplete' : undefined,
      });
    } catch {
      Alert.alert('Lỗi', 'Không thể gửi đánh giá. Vui lòng thử lại.');
    }
  };

  const handleBookmark = async () => {
    if (!sessionId || !turnId) {
      Alert.alert('Chưa thể lưu', 'Vui lòng thử lại sau khi câu trả lời được ghi vào lịch sử.');
      return;
    }
    setBookmarked(true);
    try {
      await createBookmark(apiClient, {
        session_id: sessionId,
        turn_id: turnId,
        folder: 'Chung',
      });
    } catch {
      setBookmarked(false);
      Alert.alert('Lỗi', 'Không thể lưu câu trả lời. Vui lòng thử lại.');
    }
  };

  const handleSources = () => {
    if (sources && sources.length > 0 && onShowSources) {
      onShowSources(sources);
    }
  };

  return (
    <View style={styles.container}>
      {/* Sources button */}
      {sources && sources.length > 0 && (
        <Pressable
          style={({ pressed }) => [
            styles.sourcesButton,
            pressed && styles.buttonPressed,
          ]}
          onPress={handleSources}
        >
          <Ionicons name="document-text-outline" size={13} color="#6366f1" />
          <Text style={styles.sourcesText}>
            {sources.length} nguồn
          </Text>
        </Pressable>
      )}

      {/* Divider */}
      {sources && sources.length > 0 && <View style={styles.divider} />}

      {/* Feedback */}
      <Pressable
        style={({ pressed }) => [
          styles.actionButton,
          feedback === 'up' && styles.actionActive,
          pressed && styles.buttonPressed,
        ]}
        onPress={() => handleFeedback('up')}
      >
        <Ionicons
          name={feedback === 'up' ? 'thumbs-up' : 'thumbs-up-outline'}
          size={14}
          color={feedback === 'up' ? '#22c55e' : '#64748b'}
        />
      </Pressable>

      <Pressable
        style={({ pressed }) => [
          styles.actionButton,
          feedback === 'down' && styles.actionActive,
          pressed && styles.buttonPressed,
        ]}
        onPress={() => handleFeedback('down')}
      >
        <Ionicons
          name={feedback === 'down' ? 'thumbs-down' : 'thumbs-down-outline'}
          size={14}
          color={feedback === 'down' ? '#ef4444' : '#64748b'}
        />
      </Pressable>

      {/* Copy */}
      <Pressable
        style={({ pressed }) => [
          styles.actionButton,
          pressed && styles.buttonPressed,
        ]}
        onPress={handleCopy}
      >
        <Ionicons
          name={copied ? 'checkmark' : 'copy-outline'}
          size={14}
          color={copied ? '#22c55e' : '#64748b'}
        />
      </Pressable>

      {/* Bookmark */}
      <Pressable
        style={({ pressed }) => [
          styles.actionButton,
          bookmarked && styles.actionActive,
          pressed && styles.buttonPressed,
        ]}
        onPress={handleBookmark}
      >
        <Ionicons
          name={bookmarked ? 'bookmark' : 'bookmark-outline'}
          size={14}
          color={bookmarked ? '#f59e0b' : '#64748b'}
        />
      </Pressable>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 8,
    gap: 2,
  },
  sourcesButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: 'rgba(99, 102, 241, 0.1)',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
  },
  sourcesText: {
    color: '#6366f1',
    fontSize: 11,
    fontWeight: '600',
  },
  divider: {
    width: 1,
    height: 16,
    backgroundColor: '#334155',
    marginHorizontal: 4,
  },
  actionButton: {
    padding: 6,
    borderRadius: 6,
  },
  actionActive: {
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
  },
  buttonPressed: {
    opacity: 0.6,
  },
});

export default MessageActions;
