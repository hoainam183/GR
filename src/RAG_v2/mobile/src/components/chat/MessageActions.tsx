/**
 * Message actions bar — feedback, sources, and copy actions for assistant messages.
 */

import React, { useEffect, useState } from 'react';
import {
  View,
  Pressable,
  Text,
  StyleSheet,
  Share,
  Alert,
  Modal,
  TextInput,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import type { RetrievedDocument } from '@rag/shared';
import { createBookmark, submitFeedback, getFeedback } from '@rag/shared';
import { apiClient } from '../../services/api';

interface Props {
  content: string;
  sources?: RetrievedDocument[];
  sessionId?: string;
  turnId?: number;
  onShowSources?: (sources: RetrievedDocument[]) => void;
}

type FeedbackCategory = 'wrong' | 'incomplete' | 'outdated';

const CATEGORIES: { key: FeedbackCategory; label: string; icon: string }[] = [
  { key: 'wrong', label: 'Sai', icon: 'close-circle-outline' },
  { key: 'incomplete', label: 'Thiếu', icon: 'remove-circle-outline' },
  { key: 'outdated', label: 'Cũ', icon: 'time-outline' },
];

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
  const [showFeedbackModal, setShowFeedbackModal] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState<FeedbackCategory>('incomplete');
  const [comment, setComment] = useState('');

  // Load existing feedback state
  useEffect(() => {
    if (!sessionId || !turnId) return;
    let cancelled = false;
    getFeedback(apiClient, sessionId, turnId)
      .then((existing) => {
        if (!cancelled && existing?.rating) {
          setFeedback(existing.rating);
        }
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [sessionId, turnId]);

  const handleCopy = async () => {
    try {
      await Share.share({ message: content });
    } catch {
      // Ignore share cancellation
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleThumbsUp = async () => {
    if (!sessionId || !turnId) {
      Alert.alert('Chưa thể gửi đánh giá', 'Vui lòng mở lại hội thoại sau khi câu trả lời được lưu.');
      return;
    }
    const newRating = feedback === 'up' ? null : 'up';
    setFeedback(newRating as 'up' | null);
    if (newRating === 'up') {
      try {
        await submitFeedback(apiClient, {
          session_id: sessionId,
          turn_id: turnId,
          rating: 'up',
        });
      } catch {
        setFeedback(null);
        Alert.alert('Lỗi', 'Không thể gửi đánh giá. Vui lòng thử lại.');
      }
    }
  };

  const handleThumbsDown = () => {
    if (!sessionId || !turnId) {
      Alert.alert('Chưa thể gửi đánh giá', 'Vui lòng mở lại hội thoại sau khi câu trả lời được lưu.');
      return;
    }
    if (feedback === 'down') {
      setFeedback(null);
      return;
    }
    setShowFeedbackModal(true);
  };

  const submitNegativeFeedback = async () => {
    if (!sessionId || !turnId) return;
    setShowFeedbackModal(false);
    setFeedback('down');
    try {
      await submitFeedback(apiClient, {
        session_id: sessionId,
        turn_id: turnId,
        rating: 'down',
        category: selectedCategory,
        comment: comment.trim() || undefined,
      });
    } catch {
      setFeedback(null);
      Alert.alert('Lỗi', 'Không thể gửi đánh giá. Vui lòng thử lại.');
    }
    setComment('');
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
    <>
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

        {/* Feedback - Thumbs Up */}
        <Pressable
          style={({ pressed }) => [
            styles.actionButton,
            feedback === 'up' && styles.actionActive,
            pressed && styles.buttonPressed,
          ]}
          onPress={handleThumbsUp}
        >
          <Ionicons
            name={feedback === 'up' ? 'thumbs-up' : 'thumbs-up-outline'}
            size={14}
            color={feedback === 'up' ? '#22c55e' : '#64748b'}
          />
        </Pressable>

        {/* Feedback - Thumbs Down */}
        <Pressable
          style={({ pressed }) => [
            styles.actionButton,
            feedback === 'down' && styles.actionActive,
            pressed && styles.buttonPressed,
          ]}
          onPress={handleThumbsDown}
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

      {/* Negative Feedback Modal */}
      <Modal
        visible={showFeedbackModal}
        transparent
        animationType="fade"
        onRequestClose={() => setShowFeedbackModal(false)}
      >
        <Pressable
          style={styles.modalOverlay}
          onPress={() => setShowFeedbackModal(false)}
        >
          <Pressable style={styles.modalContent} onPress={() => {}}>
            <Text style={styles.modalTitle}>Vấn đề là gì?</Text>

            {/* Category selection */}
            <View style={styles.categoryRow}>
              {CATEGORIES.map((cat) => (
                <Pressable
                  key={cat.key}
                  style={[
                    styles.categoryChip,
                    selectedCategory === cat.key && styles.categoryChipActive,
                  ]}
                  onPress={() => setSelectedCategory(cat.key)}
                >
                  <Ionicons
                    name={cat.icon as any}
                    size={14}
                    color={selectedCategory === cat.key ? '#6366f1' : '#94a3b8'}
                  />
                  <Text
                    style={[
                      styles.categoryText,
                      selectedCategory === cat.key && styles.categoryTextActive,
                    ]}
                  >
                    {cat.label}
                  </Text>
                </Pressable>
              ))}
            </View>

            {/* Comment input */}
            <TextInput
              style={styles.commentInput}
              placeholder="Mô tả thêm (tùy chọn)..."
              placeholderTextColor="#64748b"
              value={comment}
              onChangeText={setComment}
              multiline
              maxLength={1000}
            />

            {/* Actions */}
            <View style={styles.modalActions}>
              <Pressable
                style={styles.cancelButton}
                onPress={() => setShowFeedbackModal(false)}
              >
                <Text style={styles.cancelText}>Hủy</Text>
              </Pressable>
              <Pressable style={styles.submitButton} onPress={submitNegativeFeedback}>
                <Text style={styles.submitText}>Gửi</Text>
              </Pressable>
            </View>
          </Pressable>
        </Pressable>
      </Modal>
    </>
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
  // Modal styles
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.6)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  modalContent: {
    backgroundColor: '#1e293b',
    borderRadius: 16,
    padding: 20,
    width: '100%',
    maxWidth: 340,
    borderWidth: 1,
    borderColor: '#334155',
  },
  modalTitle: {
    color: '#f8fafc',
    fontSize: 17,
    fontWeight: '700',
    marginBottom: 14,
  },
  categoryRow: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 14,
  },
  categoryChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 8,
    backgroundColor: '#0f172a',
    borderWidth: 1,
    borderColor: '#334155',
  },
  categoryChipActive: {
    borderColor: '#6366f1',
    backgroundColor: 'rgba(99, 102, 241, 0.1)',
  },
  categoryText: { color: '#94a3b8', fontSize: 13, fontWeight: '600' },
  categoryTextActive: { color: '#6366f1' },
  commentInput: {
    backgroundColor: '#0f172a',
    color: '#f8fafc',
    borderWidth: 1,
    borderColor: '#334155',
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 14,
    minHeight: 60,
    textAlignVertical: 'top',
    marginBottom: 14,
  },
  modalActions: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: 10,
  },
  cancelButton: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 8,
  },
  cancelText: { color: '#94a3b8', fontSize: 14, fontWeight: '600' },
  submitButton: {
    backgroundColor: '#6366f1',
    paddingHorizontal: 20,
    paddingVertical: 8,
    borderRadius: 8,
  },
  submitText: { color: '#fff', fontSize: 14, fontWeight: '600' },
});

export default MessageActions;
