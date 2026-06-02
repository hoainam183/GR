import React, { useEffect, useState } from 'react';
import {
  Alert,
  Modal,
  Pressable,
  Share,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import type { RetrievedDocument } from '@rag/shared';
import {
  createBookmark,
  deleteBookmark,
  getBookmarkByTurn,
  getFeedback,
  submitFeedback,
} from '@rag/shared';
import { apiClient } from '../../services/api';
import { useAppTheme, type AppColors } from '../../theme/theme';

interface Props {
  content: string;
  sources?: RetrievedDocument[];
  sessionId?: string;
  turnId?: number;
  onShowSources?: (sources: RetrievedDocument[]) => void;
}

type FeedbackCategory = 'wrong' | 'incomplete' | 'outdated';

const CATEGORIES: Array<{
  key: FeedbackCategory;
  label: string;
  icon: keyof typeof Ionicons.glyphMap;
}> = [
  { key: 'wrong', label: 'Sai', icon: 'close-circle-outline' },
  { key: 'incomplete', label: 'Thiếu', icon: 'remove-circle-outline' },
  { key: 'outdated', label: 'Cũ', icon: 'time-outline' },
];

const MessageActions = ({ content, sources, sessionId, turnId, onShowSources }: Props) => {
  const { colors } = useAppTheme();
  const styles = createStyles(colors);
  const [feedback, setFeedback] = useState<'up' | 'down' | null>(null);
  const [shared, setShared] = useState(false);
  const [bookmarked, setBookmarked] = useState(false);
  const [bookmarkId, setBookmarkId] = useState<string | null>(null);
  const [showFeedbackModal, setShowFeedbackModal] = useState(false);
  const [selectedCategory, setSelectedCategory] =
    useState<FeedbackCategory>('incomplete');
  const [comment, setComment] = useState('');

  useEffect(() => {
    if (!sessionId || !turnId) return;
    let cancelled = false;
    getFeedback(apiClient, sessionId, turnId)
      .then((existing) => {
        if (!cancelled && existing?.rating) setFeedback(existing.rating);
      })
      .catch(() => {});
    getBookmarkByTurn(apiClient, sessionId, turnId)
      .then((existing) => {
        if (!cancelled) {
          setBookmarked(Boolean(existing));
          setBookmarkId(existing?.id ?? null);
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [sessionId, turnId]);

  const requireTurn = (action: string) => {
    if (sessionId && turnId) return true;
    Alert.alert(
      `Chưa thể ${action}`,
      'Mở lại hội thoại sau khi câu trả lời được lưu vào lịch sử rồi thử lại.',
    );
    return false;
  };

  const handleShare = async () => {
    try {
      await Share.share({ message: content });
      setShared(true);
      setTimeout(() => setShared(false), 2000);
    } catch {
      // Ignore platform share cancellation.
    }
  };

  const handleThumbsUp = async () => {
    if (!requireTurn('gửi đánh giá')) return;
    const next = feedback === 'up' ? null : 'up';
    setFeedback(next);
    if (next !== 'up' || !sessionId || !turnId) return;
    try {
      await submitFeedback(apiClient, { session_id: sessionId, turn_id: turnId, rating: 'up' });
    } catch {
      setFeedback(null);
      Alert.alert('Lỗi', 'Không thể gửi đánh giá. Vui lòng thử lại.');
    }
  };

  const handleThumbsDown = () => {
    if (!requireTurn('báo cáo')) return;
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
      setComment('');
    } catch {
      setFeedback(null);
      Alert.alert('Lỗi', 'Không thể gửi báo cáo. Vui lòng thử lại.');
    }
  };

  const handleBookmark = async () => {
    if (!requireTurn('lưu') || !sessionId || !turnId) return;

    if (bookmarked && bookmarkId) {
      setBookmarked(false);
      const previousId = bookmarkId;
      setBookmarkId(null);
      try {
        await deleteBookmark(apiClient, previousId);
      } catch {
        setBookmarked(true);
        setBookmarkId(previousId);
        Alert.alert('Lỗi', 'Không thể bỏ lưu câu trả lời. Vui lòng thử lại.');
      }
      return;
    }

    if (bookmarked) return;

    setBookmarked(true);
    try {
      const created = await createBookmark(apiClient, { session_id: sessionId, turn_id: turnId, folder: 'Chung' });
      setBookmarkId(created.id);
    } catch {
      setBookmarked(false);
      setBookmarkId(null);
      Alert.alert('Lỗi', 'Không thể lưu câu trả lời. Vui lòng thử lại.');
    }
  };

  return (
    <>
      <View style={styles.container}>
        {!!sources?.length && (
          <>
            <Pressable style={styles.sourcesButton} onPress={() => onShowSources?.(sources)}>
              <Ionicons name="document-text-outline" size={13} color={colors.primary} />
              <Text style={styles.sourcesText}>{sources.length} nguồn</Text>
            </Pressable>
            <View style={styles.divider} />
          </>
        )}
        <ActionButton
          icon={feedback === 'up' ? 'thumbs-up' : 'thumbs-up-outline'}
          color={feedback === 'up' ? colors.success : colors.mutedForeground}
          active={feedback === 'up'}
          onPress={handleThumbsUp}
          styles={styles}
        />
        <ActionButton
          icon={feedback === 'down' ? 'thumbs-down' : 'thumbs-down-outline'}
          color={feedback === 'down' ? colors.destructive : colors.mutedForeground}
          active={feedback === 'down'}
          onPress={handleThumbsDown}
          styles={styles}
        />
        <ActionButton
          icon={shared ? 'checkmark' : 'share-social-outline'}
          color={shared ? colors.success : colors.mutedForeground}
          onPress={handleShare}
          styles={styles}
        />
        <ActionButton
          icon={bookmarked ? 'bookmark' : 'bookmark-outline'}
          color={bookmarked ? colors.warning : colors.mutedForeground}
          active={bookmarked}
          onPress={handleBookmark}
          styles={styles}
        />
      </View>

      <Modal visible={showFeedbackModal} transparent animationType="fade">
        <Pressable style={styles.modalOverlay} onPress={() => setShowFeedbackModal(false)}>
          <Pressable style={styles.modalContent} onPress={() => {}}>
            <Text style={styles.modalTitle}>Báo cáo câu trả lời</Text>
            <Text style={styles.modalSubtitle}>
              Chọn vấn đề để gửi feedback cho câu trả lời này.
            </Text>
            <View style={styles.categoryRow}>
              {CATEGORIES.map((category) => {
                const active = category.key === selectedCategory;
                return (
                  <Pressable
                    key={category.key}
                    style={[styles.categoryChip, active && styles.categoryChipActive]}
                    onPress={() => setSelectedCategory(category.key)}
                  >
                    <Ionicons
                      name={category.icon}
                      size={14}
                      color={active ? colors.primary : colors.mutedForeground}
                    />
                    <Text style={[styles.categoryText, active && styles.categoryTextActive]}>
                      {category.label}
                    </Text>
                  </Pressable>
                );
              })}
            </View>
            <TextInput
              style={styles.commentInput}
              placeholder="Mô tả thêm (tùy chọn)..."
              placeholderTextColor={colors.mutedForeground}
              value={comment}
              onChangeText={setComment}
              multiline
              maxLength={1000}
            />
            <View style={styles.modalActions}>
              <Pressable style={styles.cancelButton} onPress={() => setShowFeedbackModal(false)}>
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

const ActionButton = ({
  icon,
  color,
  active = false,
  onPress,
  styles,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  color: string;
  active?: boolean;
  onPress: () => void;
  styles: ReturnType<typeof createStyles>;
}) => (
  <Pressable
    style={({ pressed }) => [
      styles.actionButton,
      active && styles.actionActive,
      pressed && styles.buttonPressed,
    ]}
    onPress={onPress}
  >
    <Ionicons name={icon} size={14} color={color} />
  </Pressable>
);

const createStyles = (colors: AppColors) =>
  StyleSheet.create({
    container: { flexDirection: 'row', alignItems: 'center', marginTop: 8, gap: 2 },
    sourcesButton: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 4,
      backgroundColor: colors.primarySoft,
      paddingHorizontal: 8,
      paddingVertical: 4,
      borderRadius: 6,
    },
    sourcesText: { color: colors.primary, fontSize: 11, fontWeight: '600' },
    divider: { width: 1, height: 16, backgroundColor: colors.border, marginHorizontal: 4 },
    actionButton: { padding: 6, borderRadius: 6 },
    actionActive: { backgroundColor: colors.secondary },
    buttonPressed: { opacity: 0.6 },
    modalOverlay: {
      flex: 1,
      backgroundColor: colors.overlay,
      justifyContent: 'center',
      alignItems: 'center',
      padding: 24,
    },
    modalContent: {
      backgroundColor: colors.card,
      borderRadius: 16,
      padding: 20,
      width: '100%',
      maxWidth: 360,
      borderWidth: 1,
      borderColor: colors.border,
    },
    modalTitle: { color: colors.foreground, fontSize: 17, fontWeight: '700', marginBottom: 6 },
    modalSubtitle: {
      color: colors.mutedForeground,
      fontSize: 13,
      lineHeight: 18,
      marginBottom: 14,
    },
    categoryRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 14 },
    categoryChip: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 4,
      paddingHorizontal: 12,
      paddingVertical: 8,
      borderRadius: 8,
      backgroundColor: colors.secondary,
      borderWidth: 1,
      borderColor: colors.border,
    },
    categoryChipActive: { borderColor: colors.primary, backgroundColor: colors.primarySoft },
    categoryText: { color: colors.mutedForeground, fontSize: 13, fontWeight: '600' },
    categoryTextActive: { color: colors.primary },
    commentInput: {
      backgroundColor: colors.input,
      color: colors.foreground,
      borderWidth: 1,
      borderColor: colors.border,
      borderRadius: 8,
      paddingHorizontal: 12,
      paddingVertical: 10,
      fontSize: 14,
      minHeight: 72,
      textAlignVertical: 'top',
      marginBottom: 14,
    },
    modalActions: { flexDirection: 'row', justifyContent: 'flex-end', gap: 10 },
    cancelButton: { paddingHorizontal: 16, paddingVertical: 8, borderRadius: 8 },
    cancelText: { color: colors.mutedForeground, fontSize: 14, fontWeight: '600' },
    submitButton: {
      backgroundColor: colors.primary,
      paddingHorizontal: 20,
      paddingVertical: 8,
      borderRadius: 8,
    },
    submitText: { color: colors.primaryForeground, fontSize: 14, fontWeight: '600' },
  });

export default MessageActions;
