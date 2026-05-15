import React from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import type { BookmarkStackParamList } from '../../navigation/BookmarkStack';
import MarkdownDisplay from '../../components/chat/MarkdownDisplay';

type Props = NativeStackScreenProps<BookmarkStackParamList, 'BookmarkDetail'>;

const BookmarkDetailScreen = ({ route, navigation }: Props) => {
  const { bookmark } = route.params;

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <Pressable style={styles.headerBack} onPress={() => navigation.goBack()}>
          <Ionicons name="chevron-back" size={24} color="#94a3b8" />
        </Pressable>
        <Text style={styles.headerTitle}>Chi tiết đã lưu</Text>
        <View style={{ width: 40 }} />
      </View>
      <ScrollView contentContainerStyle={styles.content}>
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
            <Text style={styles.label}>Nguồn tham khảo</Text>
            {bookmark.sources_snapshot.map((source) => (
              <Text key={`${source.rank}-${source.collection}`} style={styles.source}>
                #{source.rank} {source.collection ?? ''} {source.content.slice(0, 120)}
              </Text>
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
  content: { padding: 16, gap: 14 },
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
  source: { color: '#cbd5e1', fontSize: 13, lineHeight: 19, marginBottom: 8 },
});

export default BookmarkDetailScreen;
