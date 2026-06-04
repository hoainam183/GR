import React, { useCallback, useEffect, useMemo, useRef } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import BottomSheet, {
  BottomSheetScrollView,
  BottomSheetBackdrop,
  type BottomSheetBackdropProps,
} from '@gorhom/bottom-sheet';
import { Ionicons } from '@expo/vector-icons';
import type { RetrievedDocument } from '@rag/shared';
import { useAppTheme, type AppColors } from '../../theme/theme';

interface Props {
  sources: RetrievedDocument[];
  visible: boolean;
  onClose: () => void;
}

const SourceBottomSheet = ({ sources, visible, onClose }: Props) => {
  const { colors } = useAppTheme();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const ref = useRef<BottomSheet>(null);
  const snapPoints = useMemo(() => ['60%'], []);

  useEffect(() => {
    if (visible && sources.length > 0) {
      ref.current?.expand();
    } else {
      ref.current?.close();
    }
  }, [visible, sources.length]);

  const renderBackdrop = useCallback(
    (props: BottomSheetBackdropProps) => (
      <BottomSheetBackdrop
        {...props}
        disappearsOnIndex={-1}
        appearsOnIndex={0}
        onPress={onClose}
      />
    ),
    [onClose],
  );

  return (
    <BottomSheet
      ref={ref}
      index={-1}
      snapPoints={snapPoints}
      onClose={onClose}
      enablePanDownToClose
      backdropComponent={renderBackdrop}
      backgroundStyle={{ backgroundColor: colors.card }}
      handleIndicatorStyle={{ backgroundColor: colors.border }}
    >
      <View style={styles.header}>
        <Text style={styles.title} accessibilityRole="header">
          Nguồn tham khảo ({sources.length})
        </Text>
        <Pressable
          style={styles.closeButton}
          onPress={onClose}
          accessibilityLabel="Đóng nguồn tham khảo"
          accessibilityRole="button"
        >
          <Ionicons name="close" size={20} color={colors.mutedForeground} />
        </Pressable>
      </View>
      <BottomSheetScrollView
        style={styles.scrollArea}
        showsVerticalScrollIndicator={false}
      >
        {sources.map((doc, index) => {
          const rank = Number.isFinite(doc.rank) ? doc.rank : index + 1;
          const content = typeof doc.content === 'string' ? doc.content : '';
          const rawScore = doc.rerank_score ?? doc.score;
          const score =
            typeof rawScore === 'number' && Number.isFinite(rawScore) ? rawScore : 0;
          const scoreLabel =
            score >= 0 && score <= 1 ? `${(score * 100).toFixed(1)}%` : score.toFixed(2);
          const title = typeof doc.metadata?.title === 'string' ? doc.metadata.title : '';
          const labelText = title || content.slice(0, 60) || 'Không có nội dung trích dẫn';
          return (
            <View
              key={`${rank}-${index}`}
              style={styles.sourceCard}
              accessibilityRole="text"
              accessibilityLabel={`Nguồn ${rank}: ${labelText}`}
            >
              <View style={styles.sourceHeader}>
                <Text style={styles.rank}>#{rank}</Text>
                <Text style={styles.score}>{scoreLabel}</Text>
                {doc.collection && (
                  <View style={styles.collectionBadge}>
                    <Text style={styles.collectionText}>{doc.collection}</Text>
                  </View>
                )}
              </View>
              {!!title && (
                <Text style={styles.sourceTitle} numberOfLines={2}>{title}</Text>
              )}
              <Text style={styles.content} numberOfLines={5}>
                {content || 'Không có nội dung trích dẫn.'}
              </Text>
              {typeof doc.metadata?.source_url === 'string' && (
                <Text style={styles.sourceUrl} numberOfLines={1}>{doc.metadata.source_url}</Text>
              )}
            </View>
          );
        })}
        <View style={{ height: 20 }} />
      </BottomSheetScrollView>
    </BottomSheet>
  );
};

const createStyles = (colors: AppColors) =>
  StyleSheet.create({
    header: {
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'space-between',
      paddingHorizontal: 16,
      paddingVertical: 8,
      borderBottomWidth: 1,
      borderBottomColor: colors.border,
    },
    title: { color: colors.foreground, fontSize: 16, fontWeight: '600' },
    closeButton: { padding: 4 },
    scrollArea: { paddingHorizontal: 16 },
    sourceCard: {
      backgroundColor: colors.cardMuted,
      borderRadius: 10,
      padding: 12,
      marginBottom: 8,
      marginTop: 8,
      borderWidth: 1,
      borderColor: colors.border,
    },
    sourceHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 6 },
    rank: { color: colors.primary, fontSize: 13, fontWeight: '700' },
    score: { color: colors.success, fontSize: 12, fontWeight: '600' },
    collectionBadge: {
      backgroundColor: colors.secondary,
      paddingHorizontal: 6,
      paddingVertical: 2,
      borderRadius: 4,
    },
    collectionText: { color: colors.mutedForeground, fontSize: 10, fontWeight: '500' },
    sourceTitle: {
      color: colors.foreground,
      fontSize: 14,
      fontWeight: '600',
      marginBottom: 4,
      lineHeight: 20,
    },
    content: { color: colors.subtleForeground, fontSize: 13, lineHeight: 19 },
    sourceUrl: { color: colors.primary, fontSize: 11, marginTop: 6 },
  });

export default SourceBottomSheet;
