import React from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
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
  const styles = createStyles(colors);
  if (!visible || sources.length === 0) return null;

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <Pressable style={styles.backdrop} onPress={onClose} />
      <View style={styles.container}>
        <View style={styles.handleRow}><View style={styles.handle} /></View>
        <View style={styles.header}>
          <Text style={styles.title}>Nguồn tham khảo ({sources.length})</Text>
          <Pressable style={styles.closeButton} onPress={onClose}>
            <Ionicons name="close" size={20} color={colors.mutedForeground} />
          </Pressable>
        </View>
        <ScrollView style={styles.scrollArea} showsVerticalScrollIndicator={false}>
          {sources.map((doc, index) => {
            const score = doc.rerank_score ?? doc.score;
            const scoreLabel =
              score >= 0 && score <= 1 ? `${(score * 100).toFixed(1)}%` : score.toFixed(2);
            return (
              <View key={`${doc.rank}-${index}`} style={styles.sourceCard}>
                <View style={styles.sourceHeader}>
                  <Text style={styles.rank}>#{doc.rank}</Text>
                  <Text style={styles.score}>{scoreLabel}</Text>
                  {doc.collection && (
                    <View style={styles.collectionBadge}>
                      <Text style={styles.collectionText}>{doc.collection}</Text>
                    </View>
                  )}
                </View>
                {typeof doc.metadata?.title === 'string' && (
                  <Text style={styles.sourceTitle} numberOfLines={2}>{doc.metadata.title}</Text>
                )}
                <Text style={styles.content} numberOfLines={5}>{doc.content}</Text>
                {typeof doc.metadata?.source_url === 'string' && (
                  <Text style={styles.sourceUrl} numberOfLines={1}>{doc.metadata.source_url}</Text>
                )}
              </View>
            );
          })}
          <View style={{ height: 20 }} />
        </ScrollView>
      </View>
    </Modal>
  );
};

const createStyles = (colors: AppColors) =>
  StyleSheet.create({
    backdrop: { flex: 1, backgroundColor: colors.overlay },
    container: {
      backgroundColor: colors.card,
      borderTopLeftRadius: 20,
      borderTopRightRadius: 20,
      borderTopWidth: 1,
      borderColor: colors.border,
      maxHeight: '60%',
      paddingBottom: 20,
    },
    handleRow: { alignItems: 'center', paddingTop: 8, paddingBottom: 4 },
    handle: { width: 36, height: 4, borderRadius: 2, backgroundColor: colors.border },
    header: {
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'space-between',
      paddingHorizontal: 16,
      paddingVertical: 8,
    },
    title: { color: colors.foreground, fontSize: 16, fontWeight: '600' },
    closeButton: { padding: 4 },
    scrollArea: { paddingHorizontal: 16 },
    sourceCard: {
      backgroundColor: colors.cardMuted,
      borderRadius: 10,
      padding: 12,
      marginBottom: 8,
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
