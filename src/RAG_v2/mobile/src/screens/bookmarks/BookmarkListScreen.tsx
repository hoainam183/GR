import React, { useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Modal,
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
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import type { Bookmark, BookmarkFolder } from '@rag/shared';
import {
  createBookmarkFolder,
  deleteBookmarkFolder,
  listBookmarkFolders,
  listBookmarks,
  renameBookmarkFolder,
} from '@rag/shared';
import type { BookmarkStackParamList } from '../../navigation/BookmarkStack';
import { apiClient } from '../../services/api';
import { CACHE_KEYS, setCache } from '../../services/offlineCache';
import EmptyState from '../../components/common/EmptyState';
import { useAppTheme, type AppColors } from '../../theme/theme';

type Props = NativeStackScreenProps<BookmarkStackParamList, 'BookmarkList'>;
type FolderEditor =
  | { mode: 'create'; name: string }
  | { mode: 'rename'; originalName: string; name: string }
  | null;

const DEFAULT_FOLDER = 'Chung';

const BookmarkListScreen = ({ navigation }: Props) => {
  const { colors } = useAppTheme();
  const styles = createStyles(colors);
  const queryClient = useQueryClient();
  const [searchQuery, setSearchQuery] = useState('');
  const [activeFolder, setActiveFolder] = useState<string | null>(null);
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [folderEditor, setFolderEditor] = useState<FolderEditor>(null);
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
      const result = await listBookmarks(apiClient, params);
      setCache(CACHE_KEYS.bookmarks, result.bookmarks);
      return result;
    },
    staleTime: 60_000,
  });

  const invalidateFolders = () => {
    queryClient.invalidateQueries({ queryKey: ['bookmarks'] });
    queryClient.invalidateQueries({ queryKey: ['bookmark-folders'] });
  };
  const createFolder = useMutation({
    mutationFn: (name: string) => createBookmarkFolder(apiClient, name),
    onSuccess: (folder) => {
      invalidateFolders();
      setActiveFolder(folder.name);
      setFolderEditor(null);
    },
    onError: () => Alert.alert('Lỗi', 'Không thể tạo thư mục. Vui lòng thử lại.'),
  });
  const renameFolder = useMutation({
    mutationFn: ({ currentName, nextName }: { currentName: string; nextName: string }) =>
      renameBookmarkFolder(apiClient, currentName, { new_name: nextName }),
    onSuccess: (folder, variables) => {
      invalidateFolders();
      if (activeFolder === variables.currentName) setActiveFolder(folder.name);
      setFolderEditor(null);
    },
    onError: () => Alert.alert('Lỗi', 'Không thể đổi tên thư mục.'),
  });
  const removeFolder = useMutation({
    mutationFn: (name: string) => deleteBookmarkFolder(apiClient, name, DEFAULT_FOLDER),
    onSuccess: (_, name) => {
      invalidateFolders();
      if (activeFolder === name) setActiveFolder(null);
      setFolderEditor(null);
    },
    onError: () => Alert.alert('Lỗi', 'Không thể xóa thư mục.'),
  });

  const submitFolderEditor = () => {
    if (!folderEditor) return;
    const name = folderEditor.name.trim();
    if (!name) {
      Alert.alert('Thiếu tên', 'Nhập tên thư mục trước khi lưu.');
      return;
    }
    if (folderEditor.mode === 'create') createFolder.mutate(name);
    else renameFolder.mutate({ currentName: folderEditor.originalName, nextName: name });
  };
  const confirmDeleteFolder = (name: string) => {
    Alert.alert('Xóa thư mục', `Các mục trong "${name}" sẽ được chuyển về "${DEFAULT_FOLDER}".`, [
      { text: 'Hủy', style: 'cancel' },
      { text: 'Xóa', style: 'destructive', onPress: () => removeFolder.mutate(name) },
    ]);
  };

  const bookmarks = data?.bookmarks ?? [];
  const busy = createFolder.isPending || renameFolder.isPending || removeFolder.isPending;

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <View>
          <Text style={styles.headerTitle}>Đã lưu</Text>
          {!!data?.total && <Text style={styles.headerCount}>{data.total} mục</Text>}
        </View>
        <View style={styles.headerActions}>
          <Pressable style={styles.headerAction} onPress={() => setFolderEditor({ mode: 'create', name: '' })}>
            <Ionicons name="folder-open-outline" size={21} color={colors.primary} />
          </Pressable>
          <Pressable style={styles.headerAction} onPress={() => refetch()}>
            <Ionicons name="refresh-outline" size={22} color={colors.mutedForeground} />
          </Pressable>
        </View>
      </View>
      <View style={styles.searchContainer}>
        <Ionicons name="search-outline" size={16} color={colors.mutedForeground} />
        <TextInput
          style={styles.searchInput}
          placeholder="Tìm trong đã lưu..."
          placeholderTextColor={colors.mutedForeground}
          value={searchQuery}
          onChangeText={handleSearchChange}
          returnKeyType="search"
        />
        {!!searchQuery && (
          <Pressable onPress={() => { setSearchQuery(''); setDebouncedQuery(''); }}>
            <Ionicons name="close-circle" size={16} color={colors.mutedForeground} />
          </Pressable>
        )}
      </View>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chips}>
        <Pressable style={[styles.chip, !activeFolder && styles.chipActive]} onPress={() => setActiveFolder(null)}>
          <Text style={[styles.chipText, !activeFolder && styles.chipTextActive]}>Tất cả</Text>
        </Pressable>
        {folders.map((folder) => {
          const active = activeFolder === folder.name;
          return (
            <Pressable
              key={folder.name}
              style={[styles.chip, active && styles.chipActive]}
              onPress={() => setActiveFolder(active ? null : folder.name)}
              onLongPress={() => {
                if (folder.name !== DEFAULT_FOLDER) {
                  setFolderEditor({ mode: 'rename', originalName: folder.name, name: folder.name });
                }
              }}
            >
              <Text style={[styles.chipText, active && styles.chipTextActive]}>
                {folder.name} ({folder.count})
              </Text>
            </Pressable>
          );
        })}
      </ScrollView>
      {isLoading ? (
        <View style={styles.center}><ActivityIndicator size="large" color={colors.primary} /></View>
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
          keyExtractor={(item) => item.id}
          contentContainerStyle={bookmarks.length ? styles.list : styles.empty}
          renderItem={({ item }) => (
            <Pressable style={styles.card} onPress={() => navigation.navigate('BookmarkDetail', { bookmark: item })}>
              <View style={styles.iconBox}><Ionicons name="bookmark" size={18} color={colors.warning} /></View>
              <View style={styles.cardBody}>
                <Text style={styles.question} numberOfLines={2}>{item.question}</Text>
                <Text style={styles.preview} numberOfLines={2}>{item.answer_preview || item.answer_snapshot}</Text>
                <Text style={styles.folder}>{item.folder || DEFAULT_FOLDER}</Text>
              </View>
              <Ionicons name="chevron-forward" size={18} color={colors.mutedForeground} />
            </Pressable>
          )}
          ListEmptyComponent={
            <EmptyState
              icon="bookmark-outline"
              title={debouncedQuery ? 'Không tìm thấy' : 'Chưa có câu trả lời đã lưu'}
              subtitle={debouncedQuery ? 'Thử từ khóa khác' : 'Bấm biểu tượng lưu dưới câu trả lời để xem lại nhanh tại đây'}
            />
          }
          refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} />}
        />
      )}
      <Modal visible={Boolean(folderEditor)} transparent animationType="fade" onRequestClose={() => setFolderEditor(null)}>
        <Pressable style={styles.modalOverlay} onPress={() => setFolderEditor(null)}>
          <Pressable style={styles.folderModal} onPress={() => {}}>
            <Text style={styles.modalTitle}>{folderEditor?.mode === 'rename' ? 'Quản lý thư mục' : 'Tạo thư mục'}</Text>
            <TextInput
              style={styles.folderInput}
              value={folderEditor?.name ?? ''}
              onChangeText={(name) => folderEditor && setFolderEditor({ ...folderEditor, name })}
              placeholder="Tên thư mục"
              placeholderTextColor={colors.mutedForeground}
              autoFocus
            />
            <View style={styles.modalActions}>
              {folderEditor?.mode === 'rename' && (
                <Pressable style={styles.deleteFolderButton} onPress={() => confirmDeleteFolder(folderEditor.originalName)} disabled={busy}>
                  <Ionicons name="trash-outline" size={16} color={colors.destructive} />
                  <Text style={styles.deleteFolderText}>Xóa</Text>
                </Pressable>
              )}
              <View style={styles.modalSpacer} />
              <Pressable style={styles.cancelButton} onPress={() => setFolderEditor(null)}><Text style={styles.cancelText}>Hủy</Text></Pressable>
              <Pressable style={styles.saveButton} onPress={submitFolderEditor} disabled={busy}>
                {busy ? <ActivityIndicator size="small" color={colors.primaryForeground} /> : <Text style={styles.saveText}>Lưu</Text>}
              </Pressable>
            </View>
          </Pressable>
        </Pressable>
      </Modal>
    </SafeAreaView>
  );
};

const createStyles = (colors: AppColors) => StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 20, paddingVertical: 14, borderBottomWidth: 1, borderBottomColor: colors.border },
  headerTitle: { color: colors.foreground, fontSize: 20, fontWeight: '700' },
  headerCount: { color: colors.mutedForeground, fontSize: 12, marginTop: 2 },
  headerActions: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  headerAction: { padding: 6 },
  searchContainer: { flexDirection: 'row', alignItems: 'center', backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, marginHorizontal: 16, marginTop: 12, paddingHorizontal: 12, borderRadius: 10, gap: 8 },
  searchInput: { flex: 1, color: colors.foreground, fontSize: 14, paddingVertical: 10 },
  chips: { paddingHorizontal: 16, paddingVertical: 10, gap: 8 },
  chip: { paddingHorizontal: 12, paddingVertical: 7, borderRadius: 16, backgroundColor: colors.secondary, borderWidth: 1, borderColor: colors.border },
  chipActive: { backgroundColor: colors.primarySoft, borderColor: colors.primary },
  chipText: { color: colors.mutedForeground, fontSize: 12, fontWeight: '600' },
  chipTextActive: { color: colors.primary },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  list: { padding: 16, gap: 10 },
  empty: { flexGrow: 1 },
  card: { flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, borderRadius: 12, padding: 14 },
  iconBox: { width: 36, height: 36, borderRadius: 10, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.primarySoft },
  cardBody: { flex: 1, gap: 4 },
  question: { color: colors.foreground, fontSize: 15, fontWeight: '600' },
  preview: { color: colors.subtleForeground, fontSize: 13, lineHeight: 18 },
  folder: { color: colors.warning, fontSize: 12, fontWeight: '600' },
  modalOverlay: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.overlay, padding: 24 },
  folderModal: { width: '100%', maxWidth: 360, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, borderRadius: 16, padding: 18 },
  modalTitle: { color: colors.foreground, fontSize: 17, fontWeight: '700', marginBottom: 12 },
  folderInput: { backgroundColor: colors.input, color: colors.foreground, borderWidth: 1, borderColor: colors.border, borderRadius: 10, fontSize: 14, paddingHorizontal: 12, paddingVertical: 10 },
  modalActions: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 14 },
  modalSpacer: { flex: 1 },
  deleteFolderButton: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 8, paddingVertical: 8 },
  deleteFolderText: { color: colors.destructive, fontSize: 14, fontWeight: '600' },
  cancelButton: { paddingHorizontal: 12, paddingVertical: 9 },
  cancelText: { color: colors.mutedForeground, fontSize: 14, fontWeight: '600' },
  saveButton: { minWidth: 64, alignItems: 'center', backgroundColor: colors.primary, borderRadius: 10, paddingHorizontal: 14, paddingVertical: 9 },
  saveText: { color: colors.primaryForeground, fontSize: 14, fontWeight: '600' },
});

export default BookmarkListScreen;
