import React, { useCallback, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useQuery } from '@tanstack/react-query';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import type { BookmarkStackParamList } from '../../navigation/BookmarkStack';
import type { Bookmark, BookmarkFolder } from '@rag/shared';
import { listBookmarks, listBookmarkFolders } from '@rag/shared';
import { apiClient } from '../../services/api';
import { CACHE_KEYS, setCache } from '../../services/offlineCache';
import EmptyState from '../../components/common/EmptyState';

type Props = NativeStackScreenProps<BookmarkStackParamList, 'BookmarkList'>;

const BookmarkListScreen = ({ navigation }: Props) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [activeFolder, setActiveFolder] = useState<string | null>(null);
  const [debouncedQuery, setDebouncedQuery] = useState('');

  // Debounce search
  const searchTimerRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);
  const handleSearchChange = (text: string) => {
    setSearchQuery(text);
    if (searchTimerRef.current) clearTimeout(searchTimerRef.current);
    searchTimerRef.current = setTimeout(() => setDebouncedQuery(text), 300);
  };

  const { data: foldersData } = useQuery({
    queryKey: ['bookmark-folders'],
    queryFn: () => listBookmarkFolders(apiClient),
    staleTime: 120_000,
  });
  const folders: BookmarkFolder[] = foldersData ?? [];

  const { data, isLoading, isRefetching, refetch, error } = useQuery({
    queryKey: ['bookmarks', activeFolder, debouncedQuery],
    queryFn: async () => {
      const params: Record<string, string | number> = {};
      if (activeFolder) params.folder = activeFolder;
      if (debouncedQuery) params.q = debouncedQuery;
      const result = await listBookmarks(apiClient, params as any);
      setCache(CACHE_KEYS.bookmarks, result.bookmarks);
      return result;
    },
    staleTime: 60_000,
  });

  const bookmarks = data?.bookmarks ?? [];
  const total = data?.total ?? 0;

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
        <View>
          <Text style={styles.headerTitle}>Đã lưu</Text>
          {total > 0 && (
            <Text style={styles.headerCount}>{total} mục</Text>
          )}
        </View>
        <Pressable style={styles.headerAction} onPress={() => refetch()}>
          <Ionicons name="refresh-outline" size={22} color="#94a3b8" />
        </Pressable>
      </View>

      {/* Search bar */}
      <View style={styles.searchContainer}>
        <Ionicons name="search-outline" size={16} color="#64748b" />
        <TextInput
          style={styles.searchInput}
          placeholder="Tìm trong đã lưu..."
          placeholderTextColor="#64748b"
          value={searchQuery}
          onChangeText={handleSearchChange}
          returnKeyType="search"
        />
        {searchQuery.length > 0 && (
          <Pressable onPress={() => { setSearchQuery(''); setDebouncedQuery(''); }}>
            <Ionicons name="close-circle" size={16} color="#64748b" />
          </Pressable>
        )}
      </View>

      {/* Folder chips */}
      {folders.length > 0 && (
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.chips}
        >
          <Pressable
            style={[styles.chip, !activeFolder && styles.chipActive]}
            onPress={() => setActiveFolder(null)}
          >
            <Text style={[styles.chipText, !activeFolder && styles.chipTextActive]}>
              Tất cả
            </Text>
          </Pressable>
          {folders.map((f) => (
            <Pressable
              key={f.name}
              style={[styles.chip, activeFolder === f.name && styles.chipActive]}
              onPress={() => setActiveFolder(activeFolder === f.name ? null : f.name)}
            >
              <Text style={[styles.chipText, activeFolder === f.name && styles.chipTextActive]}>
                {f.name} ({f.count})
              </Text>
            </Pressable>
          ))}
        </ScrollView>
      )}

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
          data={bookmarks}
          renderItem={renderItem}
          keyExtractor={(item) => item.id}
          contentContainerStyle={bookmarks.length === 0 ? styles.empty : styles.list}
          ListEmptyComponent={
            <EmptyState
              icon="bookmark-outline"
              title={debouncedQuery ? 'Không tìm thấy' : 'Chưa có câu trả lời đã lưu'}
              subtitle={
                debouncedQuery
                  ? 'Thử từ khóa khác'
                  : 'Bấm biểu tượng lưu dưới câu trả lời để xem lại nhanh tại đây'
              }
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
  headerCount: { color: '#64748b', fontSize: 12, marginTop: 2 },
  headerAction: { padding: 6 },
  searchContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1e293b',
    marginHorizontal: 16,
    marginTop: 12,
    paddingHorizontal: 12,
    borderRadius: 10,
    gap: 8,
  },
  searchInput: {
    flex: 1,
    color: '#f8fafc',
    fontSize: 14,
    paddingVertical: 10,
  },
  chips: {
    paddingHorizontal: 16,
    paddingVertical: 10,
    gap: 8,
  },
  chip: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
    backgroundColor: '#1e293b',
    borderWidth: 1,
    borderColor: '#334155',
  },
  chipActive: {
    backgroundColor: 'rgba(99, 102, 241, 0.15)',
    borderColor: '#6366f1',
  },
  chipText: { color: '#94a3b8', fontSize: 12, fontWeight: '600' },
  chipTextActive: { color: '#6366f1' },
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
