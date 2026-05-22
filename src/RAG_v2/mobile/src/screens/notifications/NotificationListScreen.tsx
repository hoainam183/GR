import React, { useState } from 'react';
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
  deleteNotification,
  getUnreadCount,
  listNotifications,
  markAllNotificationsRead,
  markNotificationRead,
  subscribeNotifications,
  unsubscribeNotifications,
} from '@rag/shared';
import { apiClient } from '../../services/api';
import EmptyState from '../../components/common/EmptyState';
import {
  clearStoredPushRegistration,
  getStoredPushToken,
  isPushEnabledLocally,
  PushPermissionDeniedError,
  registerDeviceForPushNotifications,
} from '../../services/pushNotifications';
import { useAppTheme, type AppColors } from '../../theme/theme';

type PushState = 'disabled' | 'enabled' | 'busy' | 'blocked';

const NotificationListScreen = () => {
  const { colors } = useAppTheme();
  const styles = createStyles(colors);
  const queryClient = useQueryClient();
  const [pushToken, setPushToken] = useState(getStoredPushToken);
  const [pushState, setPushState] = useState<PushState>(() =>
    isPushEnabledLocally() && getStoredPushToken() ? 'enabled' : 'disabled',
  );
  const { data, isLoading, isRefetching, refetch, error } = useQuery({
    queryKey: ['notifications'],
    queryFn: () => listNotifications(apiClient),
    staleTime: 60_000,
  });
  const { data: unreadData } = useQuery({
    queryKey: ['notifications-unread-count'],
    queryFn: () => getUnreadCount(apiClient),
    staleTime: 30_000,
  });
  const notifications = data?.notifications ?? [];
  const unreadCount = unreadData?.unread_count ?? 0;
  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: ['notifications'] });
    queryClient.invalidateQueries({ queryKey: ['notifications-unread-count'] });
  };
  const markRead = useMutation({ mutationFn: (id: string) => markNotificationRead(apiClient, id), onSuccess: invalidateAll });
  const markAllRead = useMutation({ mutationFn: () => markAllNotificationsRead(apiClient), onSuccess: invalidateAll });
  const deleteItem = useMutation({ mutationFn: (id: string) => deleteNotification(apiClient, id), onSuccess: invalidateAll });

  const handleEnablePush = async () => {
    setPushState('busy');
    try {
      const token = await registerDeviceForPushNotifications();
      await subscribeNotifications(apiClient, { expo_push_token: token, topics: [] });
      setPushToken(token);
      setPushState('enabled');
    } catch (pushError) {
      if (pushError instanceof PushPermissionDeniedError) {
        setPushState('blocked');
        return;
      }
      clearStoredPushRegistration();
      setPushToken(null);
      setPushState('disabled');
      Alert.alert('Lỗi', 'Không thể bật push notification lúc này.');
    }
  };
  const handleDisablePush = async () => {
    if (!pushToken) {
      clearStoredPushRegistration();
      setPushState('disabled');
      return;
    }
    setPushState('busy');
    try {
      await unsubscribeNotifications(apiClient, { expo_push_token: pushToken });
      clearStoredPushRegistration();
      setPushToken(null);
      setPushState('disabled');
    } catch {
      setPushState('enabled');
      Alert.alert('Lỗi', 'Không thể tắt push notification lúc này.');
    }
  };
  const handleDelete = (item: NotificationItem) => Alert.alert('Xóa thông báo', `Bạn muốn xóa "${item.title}"?`, [
    { text: 'Hủy', style: 'cancel' },
    { text: 'Xóa', style: 'destructive', onPress: () => deleteItem.mutate(item.id) },
  ]);

  const pushCard = (
    <View style={styles.pushCard}>
      <View style={styles.pushIcon}><Ionicons name="phone-portrait-outline" size={18} color={colors.primary} /></View>
      <View style={styles.pushBody}>
        <Text style={styles.pushTitle}>Push notification</Text>
        <Text style={styles.pushText}>
          {pushState === 'blocked'
            ? 'Cần cấp quyền thông báo trong cài đặt thiết bị để nhận broadcast.'
            : pushState === 'enabled'
              ? 'Thiết bị này đã đăng ký nhận thông báo broadcast.'
              : 'Bật để nhận thông báo broadcast ngoài app.'}
        </Text>
      </View>
      <Pressable
        style={[styles.pushButton, pushState === 'enabled' && styles.pushButtonMuted]}
        onPress={pushState === 'enabled' ? handleDisablePush : handleEnablePush}
        disabled={pushState === 'busy'}
      >
        {pushState === 'busy'
          ? <ActivityIndicator size="small" color={colors.primaryForeground} />
          : <Text style={styles.pushButtonText}>{pushState === 'enabled' ? 'Tắt' : 'Bật'}</Text>}
      </Pressable>
    </View>
  );

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <View>
          <Text style={styles.headerTitle}>Thông báo</Text>
          {!!unreadCount && <Text style={styles.headerSubtitle}>{unreadCount} chưa đọc</Text>}
        </View>
        <View style={styles.headerActions}>
          {!!unreadCount && (
            <Pressable style={styles.markAllButton} onPress={() => markAllRead.mutate()}>
              <Ionicons name="checkmark-done-outline" size={18} color={colors.primary} />
              <Text style={styles.markAllText}>Đọc tất cả</Text>
            </Pressable>
          )}
          <Pressable style={styles.headerAction} onPress={() => refetch()}>
            <Ionicons name="refresh-outline" size={22} color={colors.mutedForeground} />
          </Pressable>
        </View>
      </View>
      {isLoading ? (
        <View style={styles.center}><ActivityIndicator size="large" color={colors.primary} /></View>
      ) : error ? (
        <>
          <View style={styles.pushPad}>{pushCard}</View>
          <EmptyState icon="cloud-offline-outline" title="Không thể tải thông báo" subtitle="Kiểm tra kết nối rồi thử lại" actionLabel="Thử lại" onAction={() => refetch()} />
        </>
      ) : (
        <FlatList
          data={notifications}
          ListHeaderComponent={pushCard}
          keyExtractor={(item) => item.id}
          contentContainerStyle={notifications.length ? styles.list : styles.empty}
          renderItem={({ item }) => (
            <Pressable
              style={[styles.card, !item.read && styles.cardUnread]}
              onPress={() => !item.read && markRead.mutate(item.id)}
              onLongPress={() => handleDelete(item)}
            >
              <View style={styles.iconBox}>
                <Ionicons name={item.read ? 'notifications-outline' : 'notifications'} size={18} color={item.read ? colors.mutedForeground : colors.primary} />
              </View>
              <View style={styles.cardBody}>
                <Text style={styles.title}>{item.title}</Text>
                <Text style={styles.body} numberOfLines={3}>{item.body}</Text>
                <Text style={styles.type}>{item.type}</Text>
              </View>
            </Pressable>
          )}
          ListEmptyComponent={<EmptyState icon="notifications-outline" title="Chưa có thông báo" subtitle="Các quy định hoặc kế hoạch liên quan sẽ xuất hiện tại đây" />}
          refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} />}
        />
      )}
    </SafeAreaView>
  );
};

const createStyles = (colors: AppColors) => StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 20, paddingVertical: 14, borderBottomWidth: 1, borderBottomColor: colors.border },
  headerTitle: { color: colors.foreground, fontSize: 20, fontWeight: '700' },
  headerSubtitle: { color: colors.primary, fontSize: 12, fontWeight: '600', marginTop: 2 },
  headerActions: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  headerAction: { padding: 6 },
  markAllButton: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: colors.primarySoft, paddingHorizontal: 10, paddingVertical: 6, borderRadius: 8 },
  markAllText: { color: colors.primary, fontSize: 12, fontWeight: '600' },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  list: { padding: 16, gap: 10 },
  empty: { flexGrow: 1, padding: 16, gap: 10 },
  pushPad: { padding: 16 },
  pushCard: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, borderRadius: 12, padding: 12 },
  pushIcon: { width: 36, height: 36, alignItems: 'center', justifyContent: 'center', borderRadius: 10, backgroundColor: colors.primarySoft },
  pushBody: { flex: 1, gap: 2 },
  pushTitle: { color: colors.foreground, fontSize: 14, fontWeight: '700' },
  pushText: { color: colors.mutedForeground, fontSize: 12, lineHeight: 17 },
  pushButton: { minWidth: 50, minHeight: 36, alignItems: 'center', justifyContent: 'center', borderRadius: 9, paddingHorizontal: 10, backgroundColor: colors.primary },
  pushButtonMuted: { backgroundColor: colors.destructive },
  pushButtonText: { color: colors.primaryForeground, fontSize: 13, fontWeight: '700' },
  card: { flexDirection: 'row', gap: 12, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, borderRadius: 12, padding: 14 },
  cardUnread: { borderColor: colors.primary, backgroundColor: colors.primarySoft },
  iconBox: { width: 36, height: 36, borderRadius: 10, backgroundColor: colors.secondary, alignItems: 'center', justifyContent: 'center' },
  cardBody: { flex: 1, gap: 4 },
  title: { color: colors.foreground, fontSize: 15, fontWeight: '700' },
  body: { color: colors.subtleForeground, fontSize: 13, lineHeight: 19 },
  type: { color: colors.mutedForeground, fontSize: 12, fontWeight: '600' },
});

export default NotificationListScreen;
