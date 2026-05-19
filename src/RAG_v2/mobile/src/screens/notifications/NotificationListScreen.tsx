import React, { useCallback } from 'react';
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { NotificationItem } from '@rag/shared';
import {
  listNotifications,
  markNotificationRead,
  markAllNotificationsRead,
  deleteNotification,
  getUnreadCount,
} from '@rag/shared';
import { apiClient } from '../../services/api';
import EmptyState from '../../components/common/EmptyState';

const NotificationListScreen = () => {
  const queryClient = useQueryClient();

  const { data, isLoading, isRefetching, refetch, error } = useQuery({
    queryKey: ['notifications'],
    queryFn: () => listNotifications(apiClient),
    staleTime: 60_000,
  });

  const notifications = data?.notifications ?? [];

  const { data: unreadData } = useQuery({
    queryKey: ['notifications-unread-count'],
    queryFn: () => getUnreadCount(apiClient),
    staleTime: 30_000,
  });

  const unreadCount = unreadData?.unread_count ?? 0;

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: ['notifications'] });
    queryClient.invalidateQueries({ queryKey: ['notifications-unread-count'] });
  };

  const markRead = useMutation({
    mutationFn: (id: string) => markNotificationRead(apiClient, id),
    onSuccess: invalidateAll,
  });

  const markAllRead = useMutation({
    mutationFn: () => markAllNotificationsRead(apiClient),
    onSuccess: invalidateAll,
  });

  const deleteItem = useMutation({
    mutationFn: (id: string) => deleteNotification(apiClient, id),
    onSuccess: invalidateAll,
  });

  const handleLongPress = (item: NotificationItem) => {
    Alert.alert('Xóa thông báo', `Bạn muốn xóa "${item.title}"?`, [
      { text: 'Hủy', style: 'cancel' },
      { text: 'Xóa', style: 'destructive', onPress: () => deleteItem.mutate(item.id) },
    ]);
  };

  const renderItem = useCallback(
    ({ item }: { item: NotificationItem }) => (
      <Pressable
        style={[styles.card, !item.read && styles.cardUnread]}
        onPress={() => {
          if (!item.read) markRead.mutate(item.id);
        }}
        onLongPress={() => handleLongPress(item)}
      >
        <View style={styles.iconBox}>
          <Ionicons
            name={item.read ? 'notifications-outline' : 'notifications'}
            size={18}
            color={item.read ? '#94a3b8' : '#6366f1'}
          />
        </View>
        <View style={styles.cardBody}>
          <Text style={styles.title}>{item.title}</Text>
          <Text style={styles.body} numberOfLines={3}>
            {item.body}
          </Text>
          <Text style={styles.type}>{item.type}</Text>
        </View>
      </Pressable>
    ),
    [markRead, deleteItem],
  );

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <View>
          <Text style={styles.headerTitle}>Thông báo</Text>
          {unreadCount > 0 && (
            <Text style={styles.headerSubtitle}>
              {unreadCount} chưa đọc
            </Text>
          )}
        </View>
        <View style={styles.headerActions}>
          {unreadCount > 0 && (
            <Pressable
              style={styles.markAllButton}
              onPress={() => markAllRead.mutate()}
            >
              <Ionicons name="checkmark-done-outline" size={18} color="#6366f1" />
              <Text style={styles.markAllText}>Đọc tất cả</Text>
            </Pressable>
          )}
          <Pressable style={styles.headerAction} onPress={() => refetch()}>
            <Ionicons name="refresh-outline" size={22} color="#94a3b8" />
          </Pressable>
        </View>
      </View>

      {isLoading ? (
        <View style={styles.center}>
          <ActivityIndicator size="large" color="#6366f1" />
        </View>
      ) : error ? (
        <EmptyState
          icon="cloud-offline-outline"
          title="Không thể tải thông báo"
          subtitle="Kiểm tra kết nối rồi thử lại"
          actionLabel="Thử lại"
          onAction={() => refetch()}
        />
      ) : (
        <FlatList
          data={notifications}
          renderItem={renderItem}
          keyExtractor={(item) => item.id}
          contentContainerStyle={notifications.length === 0 ? styles.empty : styles.list}
          ListEmptyComponent={
            <EmptyState
              icon="notifications-outline"
              title="Chưa có thông báo"
              subtitle="Các quy định hoặc kế hoạch liên quan sẽ xuất hiện tại đây"
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
  headerSubtitle: { color: '#6366f1', fontSize: 12, fontWeight: '600', marginTop: 2 },
  headerActions: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  headerAction: { padding: 6 },
  markAllButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: 'rgba(99, 102, 241, 0.1)',
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
  },
  markAllText: { color: '#6366f1', fontSize: 12, fontWeight: '600' },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  list: { padding: 16, gap: 10 },
  empty: { flexGrow: 1 },
  card: {
    flexDirection: 'row',
    gap: 12,
    backgroundColor: '#1e293b',
    borderWidth: 1,
    borderColor: '#334155',
    borderRadius: 12,
    padding: 14,
  },
  cardUnread: { borderColor: '#6366f1' },
  iconBox: {
    width: 36,
    height: 36,
    borderRadius: 10,
    backgroundColor: '#0f172a',
    alignItems: 'center',
    justifyContent: 'center',
  },
  cardBody: { flex: 1, gap: 4 },
  title: { color: '#f8fafc', fontSize: 15, fontWeight: '700' },
  body: { color: '#cbd5e1', fontSize: 13, lineHeight: 19 },
  type: { color: '#64748b', fontSize: 12, fontWeight: '600' },
});

export default NotificationListScreen;
