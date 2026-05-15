/**
 * Source bottom sheet — displays retrieved documents for an answer.
 * Shown as a modal overlay from the bottom of the screen.
 */

import React from 'react';
import {
  View,
  Text,
  ScrollView,
  Pressable,
  StyleSheet,
  Modal,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import type { RetrievedDocument } from '@rag/shared';

interface Props {
  sources: RetrievedDocument[];
  visible: boolean;
  onClose: () => void;
}

const SourceBottomSheet = ({ sources, visible, onClose }: Props) => {
  if (!visible || sources.length === 0) return null;

  return (
    <Modal
      visible={visible}
      transparent
      animationType="slide"
      onRequestClose={onClose}
    >
      {/* Backdrop */}
      <Pressable style={styles.backdrop} onPress={onClose} />

      {/* Sheet */}
      <View style={styles.container}>
        {/* Handle */}
        <View style={styles.handleRow}>
          <View style={styles.handle} />
        </View>

        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.title}>
            📄 Nguồn tham khảo ({sources.length})
          </Text>
          <Pressable style={styles.closeButton} onPress={onClose}>
            <Ionicons name="close" size={20} color="#94a3b8" />
          </Pressable>
        </View>

        {/* Sources list */}
        <ScrollView
          style={styles.scrollArea}
          showsVerticalScrollIndicator={false}
        >
          {sources.map((doc, idx) => {
            const title =
              (doc.metadata?.title as string) ??
              (doc.metadata?.source_url as string) ??
              `Nguồn #${doc.rank}`;
            const score = doc.rerank_score ?? doc.score;
            const scoreLabel =
              score >= 0 && score <= 1
                ? `${(score * 100).toFixed(1)}%`
                : score.toFixed(2);

            return (
              <View key={idx} style={styles.sourceCard}>
                <View style={styles.sourceHeader}>
                  <Text style={styles.rank}>#{doc.rank}</Text>
                  <Text style={styles.score}>{scoreLabel}</Text>
                  {doc.collection && (
                    <View style={styles.collectionBadge}>
                      <Text style={styles.collectionText}>
                        {doc.collection}
                      </Text>
                    </View>
                  )}
                </View>
                {typeof doc.metadata?.title === 'string' && (
                  <Text style={styles.sourceTitle} numberOfLines={2}>
                    {doc.metadata.title}
                  </Text>
                )}
                <Text style={styles.content} numberOfLines={5}>
                  {doc.content}
                </Text>
                {typeof doc.metadata?.source_url === 'string' && (
                  <Text style={styles.sourceUrl} numberOfLines={1}>
                    🔗 {doc.metadata.source_url}
                  </Text>
                )}
              </View>
            );
          })}
          {/* Bottom padding for safe area */}
          <View style={{ height: 20 }} />
        </ScrollView>
      </View>
    </Modal>
  );
};

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
  },
  container: {
    backgroundColor: '#1e293b',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    maxHeight: '60%',
    paddingBottom: 20,
  },
  handleRow: {
    alignItems: 'center',
    paddingTop: 8,
    paddingBottom: 4,
  },
  handle: {
    width: 36,
    height: 4,
    borderRadius: 2,
    backgroundColor: '#475569',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 8,
  },
  title: {
    color: '#f8fafc',
    fontSize: 16,
    fontWeight: '600',
  },
  closeButton: {
    padding: 4,
  },
  scrollArea: {
    paddingHorizontal: 16,
  },
  sourceCard: {
    backgroundColor: '#0f172a',
    borderRadius: 10,
    padding: 12,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: '#334155',
  },
  sourceHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 6,
  },
  rank: {
    color: '#6366f1',
    fontSize: 13,
    fontWeight: '700',
  },
  score: {
    color: '#22c55e',
    fontSize: 12,
    fontWeight: '600',
  },
  collectionBadge: {
    backgroundColor: '#334155',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  collectionText: {
    color: '#94a3b8',
    fontSize: 10,
    fontWeight: '500',
  },
  sourceTitle: {
    color: '#e2e8f0',
    fontSize: 14,
    fontWeight: '600',
    marginBottom: 4,
    lineHeight: 20,
  },
  content: {
    color: '#cbd5e1',
    fontSize: 13,
    lineHeight: 19,
  },
  sourceUrl: {
    color: '#6366f1',
    fontSize: 11,
    marginTop: 6,
  },
});

export default SourceBottomSheet;
