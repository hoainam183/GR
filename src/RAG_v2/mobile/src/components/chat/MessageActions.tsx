import React, { useEffect, useMemo, useState } from 'react';
import {
  Modal,
  Pressable,
  Share,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useQuery } from '@tanstack/react-query';
import type { RetrievedDocument } from '@rag/shared';
import {
  createBookmark,
  deleteBookmark,
  getBookmarkByTurn,
  getFeedback,
  submitFeedback,
} from '@rag/shared';
import * as Haptics from 'expo-haptics';
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
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [feedback, setFeedback] = useState<'up' | 'down' | null>(null);
  const [shared, setShared] = useState(false);
  const [bookmarked, setBookmarked] = useState(false);
  const [bookmarkId, setBookmarkId] = useState<string | null>(null);
  const [showFeedbackModal, setShowFeedbackModal] = useState(false);
  const [selectedCategory, setSelectedCategory] =
    useState<FeedbackCategory>('incomplete');
  const [comment, setComment] = useState('');

  // React Query — deduplicates requests; same queryKey across all MessageBubbles
  // sharing a turn will hit cache instead of making N API calls.
  const { data: existingFeedback } = useQuery({
    queryKey: ['feedback', sessionId, turnId],
    queryFn: () => getFeedback(apiClient, sessionId!, turnId!),
    enabled: Boolean(sessionId && turnId),
    staleTime: Infinity,
  });

  const { data: existingBookmark } = useQuery({
    queryKey: ['bookmark-by-turn', sessionId, turnId],
    queryFn: () => getBookmarkByTurn(apiClient, sessionId!, turnId!),
    enabled: Boolean(sessionId && turnId),
    staleTime: Infinity,
  });

  useEffect(() => {
    if (existingFeedback?.rating) setFeedback(existingFeedback.rating);
  }, [existingFeedback]);

  useEffect(() => {
    setBookmarked(Boolean(existingBookmark));
    setBookmarkId(existingBookmark?.id ?? null);
  }, [existingBookmark]);

  const requireTurn = (action: string) => {
    if (sessionId && turnId) return true;
    // Non-blocking info toast instead of Alert
    import('react-native-toast-message').then(({ default: Toast }) => {
      Toast.show({ type: 'info', text1: `Chưa thể ${action}`, text2: 'Câu trả lời chưa được lưu vào lịch sử.' });
    });
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
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    const next = feedback === 'up' ? null : 'up';
    setFeedback(next);
    if (next !== 'up' || !sessionId || !turnId) return;
    try {
      await submitFeedback(apiClient, { session_id: sessionId, turn_id: turnId, rating: 'up' });
    } catch {
      setFeedback(null);
      import('react-native-toast-message').then(({ default: Toast }) => {
        Toast.show({ type: 'error', text1: 'Lỗi', text2: 'Không thể gửi đánh giá. Vui lòng thử lại.' });
      });
    }
  };

  const handleThumbsDown = () => {
    if (!requireTurn('báo cáo')) return;
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
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
      import('react-native-toast-message').then(({ default: Toast }) => {
        Toast.show({ type: 'error', text1: 'Lỗi', text2: 'Không thể gửi báo cáo. Vui lòng thử lại.' });
      });
    }
  };

  const handleBookmark = async () => {
    if (!requireTurn('lưu') || !sessionId || !turnId) return;
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);

    if (bookmarked && bookmarkId) {
      setBookmarked(false);
      const previousId = bookmarkId;
      setBookmarkId(null);
      try {
        await deleteBookmark(apiClient, previousId);
      } catch {
        setBookmarked(true);
        setBookmarkId(previousId);
        import('react-native-toast-message').then(({ default: Toast }) => {
          Toast.show({ type: 'error', text1: 'Lỗi', text2: 'Không thể bỏ lưu câu trả lời. Vui lòng thử lại.' });
        });
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
      import('react-native-toast-message').then(({ default: Toast }) => {
        Toast.show({ type: 'error', text1: 'Lỗi', text2: 'Không thể lưu câu trả lời. Vui lòng thử lại.' });
      });
    }
  };

  return (
    <>
      <View style={styles.container}>
        {!!sources?.length && (
          <>
            <Pressable
              style={styles.sourcesButton}
              onPress={() => onShowSources?.(sources)}
              accessibilityLabel={`Xem ${sources.length} nguồn tham khảo`}
              accessibilityRole="button"
            >
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
          label="Hữu ích"
          onPress={handleThumbsUp}
          styles={styles}
        />
        <ActionButton
          icon={feedback === 'down' ? 'thumbs-down' : 'thumbs-down-outline'}
          color={feedback === 'down' ? colors.destructive : colors.mutedForeground}
          active={feedback === 'down'}
          label="Báo cáo vấn đề"
          hint="Mở hộp thoại báo cáo"
          onPress={handleThumbsDown}
          styles={styles}
        />
        <ActionButton
          icon={shared ? 'checkmark' : 'share-social-outline'}
          color={shared ? colors.success : colors.mutedForeground}
          label="Chia sẻ"
          onPress={handleShare}
          styles={styles}
        />
        <ActionButton
          icon={bookmarked ? 'bookmark' : 'bookmark-outline'}
          color={bookmarked ? colors.warning : colors.mutedForeground}
          active={bookmarked}
          label={bookmarked ? 'Bỏ lưu' : 'Lưu câu trả lời'}
          onPress={handleBookmark}
          styles={styles}
        />
      </View>

      <Modal
        visible={showFeedbackModal}
        transparent
        animationType="fade"
        accessibilityViewIsModal
      >
        <Pressable style={styles.modalOverlay} onPress={() => setShowFeedbackModal(false)}>
          <Pressable style={styles.modalContent} onPress={() => {}}>
            <Text style={styles.modalTitle} accessibilityRole="header">Báo cáo câu trả lời</Text>
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
                    accessibilityRole="radio"
                    accessibilityState={{ selected: active }}
                    accessibilityLabel={category.label}
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
              <Pressable
                style={styles.cancelButton}
                onPress={() => setShowFeedbackModal(false)}
                accessibilityLabel="Hủy báo cáo"
                accessibilityRole="button"
              >
                <Text style={styles.cancelText}>Hủy</Text>
              </Pressable>
              <Pressable
                style={styles.submitButton}
                onPress={submitNegativeFeedback}
                accessibilityLabel="Gửi báo cáo"
                accessibilityRole="button"
              >
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
  label,
  hint,
  onPress,
  styles,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  color: string;
  active?: boolean;
  label: string;
  hint?: string;
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
    accessibilityLabel={label}
    accessibilityRole="button"
    accessibilityState={{ selected: active }}
    accessibilityHint={hint}
    hitSlop={8}
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
    actionButton: { padding: 12, borderRadius: 8 },
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
