import React, { useState } from 'react';
import {
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import type { BookmarkStackParamList } from '../../navigation/BookmarkStack';
import { updateBookmark, deleteBookmark } from '@rag/shared';
import { apiClient } from '../../services/api';
import MarkdownDisplay from '../../components/chat/MarkdownDisplay';

type Props = NativeStackScreenProps<BookmarkStackParamList, 'BookmarkDetail'>;

const BookmarkDetailScreen = ({ route, navigation }: Props) => {
  const { bookmark } = route.params;
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [folder, setFolder] = useState(bookmark.folder || 'Chung');
  const [note, setNote] = useState(bookmark.note || '');

  const updateMutation = useMutation({
    mutationFn: () => updateBookmark(apiClient, bookmark.id, { folder, note: note || undefined }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bookmarks'] });
      queryClient.invalidateQueries({ queryKey: ['bookmark-folders'] });
      setEditing(false);
    },
    onError: () => Alert.alert('Lỗi', 'Không thể cập nhật. Vui lòng thử lại.'),
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteBookmark(apiClient, bookmark.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bookmarks'] });
      navigation.goBack();
    },
    onError: () => Alert.alert('Lỗi', 'Không thể xóa. Vui lòng thử lại.'),
  });

  const handleDelete = () => {
    Alert.alert('Xóa bookmark', 'Bạn chắc chắn muốn xóa mục này?', [
      { text: 'Hủy', style: 'cancel' },
      { text: 'Xóa', style: 'destructive', onPress: () => deleteMutation.mutate() },
    ]);
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <Pressable style={styles.headerBack} onPress={() => navigation.goBack()}>
          <Ionicons name="chevron-back" size={24} color="#94a3b8" />
        </Pressable>
        <Text style={styles.headerTitle}>Chi tiết đã lưu</Text>
        <View style={styles.headerRight}>
          <Pressable style={styles.headerBtn} onPress={() => setEditing(!editing)}>
            <Ionicons name={editing ? 'close' : 'create-outline'} size={20} color="#94a3b8" />
          </Pressable>
          <Pressable style={styles.headerBtn} onPress={handleDelete}>
            <Ionicons name="trash-outline" size={20} color="#ef4444" />
          </Pressable>
        </View>
      </View>

      <ScrollView contentContainerStyle={styles.content}>
        {/* Folder & Note editing */}
        {editing ? (
          <View style={styles.section}>
            <Text style={styles.label}>Thư mục</Text>
            <TextInput
              style={styles.input}
              value={folder}
              onChangeText={setFolder}
              placeholder="Tên thư mục"
              placeholderTextColor="#64748b"
            />
            <Text style={[styles.label, { marginTop: 12 }]}>Ghi chú</Text>
            <TextInput
              style={[styles.input, styles.noteInput]}
              value={note}
              onChangeText={setNote}
              placeholder="Thêm ghi chú..."
              placeholderTextColor="#64748b"
              multiline
            />
            <Pressable style={styles.saveButton} onPress={() => updateMutation.mutate()}>
              <Ionicons name="checkmark" size={16} color="#fff" />
              <Text style={styles.saveText}>Lưu thay đổi</Text>
            </Pressable>
          </View>
        ) : (
          <View style={styles.metaRow}>
            <View style={styles.folderBadge}>
              <Ionicons name="folder-outline" size={12} color="#f59e0b" />
              <Text style={styles.folderText}>{bookmark.folder || 'Chung'}</Text>
            </View>
            {bookmark.note && (
              <Text style={styles.noteText}>📝 {bookmark.note}</Text>
            )}
          </View>
        )}

        <View style={styles.section}>
          <Text style={styles.label}>Câu hỏi</Text>
          <Text style={styles.question}>{bookmark.question}</Text>
        </View>

        <View style={styles.section}>
          <Text style={styles.label}>Câu trả lời</Text>
          <MarkdownDisplay content={bookmark.answer_snapshot} />
        </View>

        {bookmark.sources_snapshot?.length > 0 && (
          <View style={styles.section}>
            <Text style={styles.label}>Nguồn tham khảo ({bookmark.sources_snapshot.length})</Text>
            {bookmark.sources_snapshot.map((source, idx) => (
              <View key={`${source.rank}-${idx}`} style={styles.sourceCard}>
                <View style={styles.sourceHeader}>
                  <Text style={styles.sourceRank}>#{source.rank}</Text>
                  {source.collection && (
                    <View style={styles.collectionBadge}>
                      <Text style={styles.collectionText}>{source.collection}</Text>
                    </View>
                  )}
                  {source.score > 0 && (
                    <Text style={styles.scoreText}>
                      {(source.score * 100).toFixed(0)}%
                    </Text>
                  )}
                </View>
                <Text style={styles.sourceContent} numberOfLines={4}>
                  {source.content}
                </Text>
              </View>
            ))}
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0f172a' },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 4,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#1e293b',
  },
  headerBack: { padding: 8 },
  headerTitle: {
    flex: 1,
    color: '#f8fafc',
    fontSize: 17,
    fontWeight: '600',
    textAlign: 'center',
  },
  headerRight: { flexDirection: 'row', gap: 4 },
  headerBtn: { padding: 8 },
  content: { padding: 16, gap: 14 },
  metaRow: { flexDirection: 'row', alignItems: 'center', gap: 12, flexWrap: 'wrap' },
  folderBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: 'rgba(245, 158, 11, 0.12)',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
  },
  folderText: { color: '#f59e0b', fontSize: 12, fontWeight: '600' },
  noteText: { color: '#94a3b8', fontSize: 13, fontStyle: 'italic' },
  section: {
    backgroundColor: '#1e293b',
    borderWidth: 1,
    borderColor: '#334155',
    borderRadius: 12,
    padding: 14,
  },
  label: {
    color: '#94a3b8',
    fontSize: 12,
    fontWeight: '700',
    textTransform: 'uppercase',
    marginBottom: 8,
  },
  question: { color: '#f8fafc', fontSize: 16, lineHeight: 23 },
  input: {
    backgroundColor: '#0f172a',
    color: '#f8fafc',
    borderWidth: 1,
    borderColor: '#334155',
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
    fontSize: 14,
  },
  noteInput: { minHeight: 60, textAlignVertical: 'top' },
  saveButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    backgroundColor: '#6366f1',
    borderRadius: 8,
    paddingVertical: 10,
    marginTop: 12,
  },
  saveText: { color: '#fff', fontSize: 14, fontWeight: '600' },
  sourceCard: {
    backgroundColor: '#0f172a',
    borderWidth: 1,
    borderColor: '#334155',
    borderRadius: 8,
    padding: 10,
    marginBottom: 8,
  },
  sourceHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 6 },
  sourceRank: { color: '#6366f1', fontSize: 12, fontWeight: '700' },
  collectionBadge: {
    backgroundColor: 'rgba(99, 102, 241, 0.1)',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  collectionText: { color: '#6366f1', fontSize: 10, fontWeight: '600' },
  scoreText: { color: '#64748b', fontSize: 11 },
  sourceContent: { color: '#cbd5e1', fontSize: 13, lineHeight: 19 },
});

export default BookmarkDetailScreen;
