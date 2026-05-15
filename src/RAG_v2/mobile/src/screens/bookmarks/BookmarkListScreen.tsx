import React, { useCallback } from 'react';
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useQuery } from '@tanstack/react-query';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import type { BookmarkStackParamList } from '../../navigation/BookmarkStack';
import type { Bookmark } from '@rag/shared';
import { listBookmarks } from '@rag/shared';
import { apiClient } from '../../services/api';
import { CACHE_KEYS, getCache, setCache } from '../../services/offlineCache';
import EmptyState from '../../components/common/EmptyState';

type Props = NativeStackScreenProps<BookmarkStackParamList, 'BookmarkList'>;

const BookmarkListScreen = ({ navigation }: Props) => {
  const { data = [], isLoading, isRefetching, refetch, error } = useQuery({
    queryKey: ['bookmarks'],
    queryFn: async () => {
      const result = await listBookmarks(apiClient);
      setCache(CACHE_KEYS.bookmarks, result);
      return result;
    },
    initialData: () => getCache<Bookmark[]>(CACHE_KEYS.bookmarks),
    staleTime: 60_000,
  });

  const renderItem = useCallback(
    ({ item }: { item: Bookmark }) => (
      <Pressable
        style={({ pressed }) => [styles.card, pressed && styles.cardPressed]}
        onPress={() => navigation.navigate('BookmarkDetail', { bookmark: item })}
      >
        <View style={styles.iconBox}>
          <Ionicons name="bookmark" size={18} color="#f59e0b" />
        </View>
        <View style={styles.cardBody}>
          <Text style={styles.question} numberOfLines={2}>
            {item.question}
          </Text>
          <Text style={styles.preview} numberOfLines={2}>
            {item.answer_preview || item.answer_snapshot}
          </Text>
          <Text style={styles.folder}>{item.folder || 'Chung'}</Text>
        </View>
        <Ionicons name="chevron-forward" size={18} color="#475569" />
      </Pressable>
    ),
    [navigation],
  );

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Đã lưu</Text>
        <Pressable style={styles.headerAction} onPress={() => refetch()}>
          <Ionicons name="refresh-outline" size={22} color="#94a3b8" />
        </Pressable>
      </View>

      {isLoading ? (
        <View style={styles.center}>
          <ActivityIndicator size="large" color="#6366f1" />
        </View>
      ) : error ? (
        <EmptyState
          icon="cloud-offline-outline"
          title="Không thể tải mục đã lưu"
          subtitle="Kiểm tra kết nối rồi thử lại"
          actionLabel="Thử lại"
          onAction={() => refetch()}
        />
      ) : (
        <FlatList
          data={data}
          renderItem={renderItem}
          keyExtractor={(item) => item.id}
          contentContainerStyle={data.length === 0 ? styles.empty : styles.list}
          ListEmptyComponent={
            <EmptyState
              icon="bookmark-outline"
              title="Chưa có câu trả lời đã lưu"
              subtitle="Bấm biểu tượng lưu dưới câu trả lời để xem lại nhanh tại đây"
            />
          }
          refreshControl={
            <RefreshControl refreshing={isRefetching} onRefresh={refetch} />
          }
        />
      )}
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0f172a' },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: '#1e293b',
  },
  headerTitle: { color: '#f8fafc', fontSize: 20, fontWeight: '700' },
  headerAction: { padding: 6 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  list: { padding: 16, gap: 10 },
  empty: { flexGrow: 1 },
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    backgroundColor: '#1e293b',
    borderWidth: 1,
    borderColor: '#334155',
    borderRadius: 12,
    padding: 14,
  },
  cardPressed: { opacity: 0.75 },
  iconBox: {
    width: 36,
    height: 36,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(245, 158, 11, 0.12)',
  },
  cardBody: { flex: 1, gap: 4 },
  question: { color: '#e2e8f0', fontSize: 15, fontWeight: '600' },
  preview: { color: '#94a3b8', fontSize: 13, lineHeight: 18 },
  folder: { color: '#f59e0b', fontSize: 12, fontWeight: '600' },
});

export default BookmarkListScreen;
