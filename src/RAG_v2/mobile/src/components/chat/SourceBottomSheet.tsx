import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Linking, Pressable, StyleSheet, Text, View } from 'react-native';
import BottomSheet, {
  BottomSheetScrollView,
  BottomSheetBackdrop,
  type BottomSheetBackdropProps,
} from '@gorhom/bottom-sheet';
import { Ionicons } from '@expo/vector-icons';
import type { RetrievedDocument } from '@rag/shared';
import { useAppTheme, type AppColors } from '../../theme/theme';
import { friendlyCollection, stripMarkdown } from '../../utils/sourceText';

interface Props {
  sources: RetrievedDocument[];
  visible: boolean;
  onClose: () => void;
}

const PREVIEW_LINES = 6;

const getMetaString = (
  metadata: Record<string, unknown> | undefined,
  ...keys: string[]
): string => {
  if (!metadata) return '';
  for (const key of keys) {
    const value = metadata[key];
    if (typeof value === 'string' && value.trim()) return value.trim();
  }
  return '';
};

const SourceCard = ({
  doc,
  rank,
  styles,
  colors,
}: {
  doc: RetrievedDocument;
  rank: number;
  styles: ReturnType<typeof createStyles>;
  colors: AppColors;
}) => {
  const [expanded, setExpanded] = useState(false);
  const title = getMetaString(doc.metadata, 'title', 'heading', 'doc_title', 'article_title');
  const sourceUrl = getMetaString(doc.metadata, 'source_url', 'url');
  const collectionLabel = friendlyCollection(doc.collection);
  const cleaned = useMemo(
    () => stripMarkdown(typeof doc.content === 'string' ? doc.content : ''),
    [doc.content],
  );

  return (
    <View style={styles.sourceCard}>
      <View style={styles.sourceHeader}>
        <Text style={styles.rank}>#{rank}</Text>
        {!!collectionLabel && (
          <View style={styles.collectionBadge}>
            <Text style={styles.collectionText}>{collectionLabel}</Text>
          </View>
        )}
      </View>
      {!!title && <Text style={styles.sourceTitle}>{title}</Text>}
      <Text style={styles.content} numberOfLines={expanded ? undefined : PREVIEW_LINES}>
        {cleaned || 'Không có nội dung trích dẫn.'}
      </Text>
      {cleaned.length > 180 && (
        <Pressable
          onPress={() => setExpanded((prev) => !prev)}
          hitSlop={6}
          accessibilityRole="button"
          accessibilityLabel={expanded ? 'Thu gọn nội dung nguồn' : 'Xem đầy đủ nội dung nguồn'}
        >
          <Text style={styles.expandText}>{expanded ? 'Thu gọn' : 'Xem đầy đủ'}</Text>
        </Pressable>
      )}
      {!!sourceUrl && (
        <Pressable
          style={styles.linkRow}
          onPress={() => Linking.openURL(sourceUrl).catch(() => undefined)}
          accessibilityRole="link"
          accessibilityLabel="Mở văn bản gốc"
        >
          <Ionicons name="open-outline" size={13} color={colors.primary} />
          <Text style={styles.linkText} numberOfLines={1}>Mở văn bản gốc</Text>
        </Pressable>
      )}
    </View>
  );
};

const SourceBottomSheet = ({ sources, visible, onClose }: Props) => {
  const { colors } = useAppTheme();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const ref = useRef<BottomSheet>(null);
  const snapPoints = useMemo(() => ['60%', '90%'], []);

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
      // v5 defaults enableDynamicSizing to true, which renders a content-sized
      // sheet at the bottom on mount even at index -1. Disable it so the sheet
      // stays fully hidden until the user taps "nguồn".
      enableDynamicSizing={false}
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
          return (
            <SourceCard
              key={`${rank}-${index}`}
              doc={doc}
              rank={rank}
              styles={styles}
              colors={colors}
            />
          );
        })}
        <View style={{ height: 24 }} />
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
      // DESIGN §5.2: citation card has a 3px red left accent.
      borderLeftWidth: 3,
      borderLeftColor: colors.primary,
    },
    sourceHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 6 },
    rank: { color: colors.primary, fontSize: 13, fontWeight: '700' },
    collectionBadge: {
      backgroundColor: colors.secondary,
      paddingHorizontal: 8,
      paddingVertical: 2,
      borderRadius: 4,
    },
    collectionText: { color: colors.mutedForeground, fontSize: 11, fontWeight: '600' },
    sourceTitle: {
      color: colors.foreground,
      fontSize: 14,
      fontWeight: '600',
      marginBottom: 4,
      lineHeight: 20,
    },
    content: { color: colors.subtleForeground, fontSize: 13, lineHeight: 20 },
    expandText: { color: colors.primary, fontSize: 12, fontWeight: '600', marginTop: 6 },
    linkRow: { flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 8 },
    linkText: { color: colors.primary, fontSize: 12, fontWeight: '600', flex: 1 },
  });

export default SourceBottomSheet;
