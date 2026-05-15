/**
 * Session list screen — shows chat history and allows starting new conversations.
 */

import React, { useCallback, useState } from 'react';
import {
  View,
  Text,
  FlatList,
  Pressable,
  StyleSheet,
  RefreshControl,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import type { ChatStackParamList } from '../../navigation/ChatStack';
import type { Session } from '@rag/shared';
import { getMySessions } from '@rag/shared';
import { apiClient } from '../../services/api';
import { CACHE_KEYS, getCache, setCache } from '../../services/offlineCache';
import { useChatStore } from '../../stores/chatStore';
import EmptyState from '../../components/common/EmptyState';

type Props = NativeStackScreenProps<ChatStackParamList, 'SessionList'>;

/**
 * Generate a display title from the session data.
 * Uses the first question as title if no explicit title is set.
 */
const getSessionTitle = (session: Session): string => {
  if (session.title) return session.title;
  return `Hội thoại ${formatDate(session.created_at)}`;
};

/**
 * Format an ISO date string to a human-readable relative time or date.
 */
const formatDate = (isoString: string): string => {
  const date = new Date(isoString);
  const now = new Date();
  const diff = now.getTime() - date.getTime();
  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);

  if (minutes < 1) return 'Vừa xong';
  if (minutes < 60) return `${minutes} phút trước`;
  if (hours < 24) return `${hours} giờ trước`;
  if (days < 7) return `${days} ngày trước`;
  return date.toLocaleDateString('vi-VN', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  });
};

const SessionListScreen = ({ navigation }: Props) => {
  const resetChat = useChatStore((s) => s.reset);
  const queryClient = useQueryClient();
  const [refreshing, setRefreshing] = useState(false);

  // Fetch sessions for the current user
  const {
    data: sessions,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ['sessions', 'me'],
    queryFn: async () => {
      const result = await getMySessions(apiClient);
      setCache(CACHE_KEYS.sessions, result);
      return result;
    },
    initialData: () => getCache<Session[]>(CACHE_KEYS.sessions),
    staleTime: 30_000, // 30 seconds
  });

  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    await refetch();
    setRefreshing(false);
  }, [refetch]);

  const handleNewChat = useCallback(() => {
    resetChat();
    navigation.navigate('Chat', undefined);
  }, [navigation, resetChat]);

  const handleOpenSession = useCallback(
    (sessionId: string) => {
      navigation.navigate('Chat', { sessionId });
    },
    [navigation],
  );

  // ─── Render helpers ────────────────────────────────────────────────────────

  const renderSessionItem = useCallback(
    ({ item }: { item: Session }) => (
      <Pressable
        style={({ pressed }) => [
          styles.sessionCard,
          pressed && styles.sessionCardPressed,
        ]}
        onPress={() => handleOpenSession(item.session_id)}
      >
        <View style={styles.sessionIcon}>
          <Ionicons name="chatbubble-outline" size={20} color="#6366f1" />
        </View>
        <View style={styles.sessionContent}>
          <Text style={styles.sessionTitle} numberOfLines={2}>
            {getSessionTitle(item)}
          </Text>
          <View style={styles.sessionMeta}>
            <Text style={styles.sessionTime}>
              {formatDate(item.updated_at || item.created_at)}
            </Text>
            {item.turn_count > 0 && (
              <Text style={styles.sessionTurns}>
                {item.turn_count} tin nhắn
              </Text>
            )}
          </View>
        </View>
        <Ionicons name="chevron-forward" size={18} color="#475569" />
      </Pressable>
    ),
    [handleOpenSession],
  );

  const renderEmpty = () => (
    <EmptyState
      icon="chatbubbles-outline"
      title="Chưa có hội thoại nào"
      subtitle="Bắt đầu hỏi về quy chế, học bổng, CTĐT và các quy định của BKHN"
      actionLabel="Bắt đầu chat"
      onAction={handleNewChat}
    />
  );

  const renderError = () => (
    <EmptyState
      icon="cloud-offline-outline"
      title="Không thể tải lịch sử"
      subtitle={error instanceof Error ? error.message : 'Đã xảy ra lỗi'}
      actionLabel="Thử lại"
      onAction={handleRefresh}
    />
  );

  // ─── Main render ───────────────────────────────────────────────────────────

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Lịch sử hội thoại</Text>
        <Pressable
          style={styles.headerAction}
          onPress={() =>
            queryClient.invalidateQueries({ queryKey: ['sessions'] })
          }
        >
          <Ionicons name="refresh-outline" size={22} color="#94a3b8" />
        </Pressable>
      </View>

      {/* Content */}
      {isLoading && !refreshing ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#6366f1" />
          <Text style={styles.loadingText}>Đang tải...</Text>
        </View>
      ) : error ? (
        renderError()
      ) : (
        <FlatList
          data={sessions ?? []}
          renderItem={renderSessionItem}
          keyExtractor={(item) => item.session_id}
          contentContainerStyle={
            (sessions?.length ?? 0) === 0
              ? styles.emptyList
              : styles.listContent
          }
          ListEmptyComponent={renderEmpty}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={handleRefresh}
              tintColor="#6366f1"
              colors={['#6366f1']}
            />
          }
          ItemSeparatorComponent={() => <View style={styles.separator} />}
        />
      )}

      {/* FAB — New Chat */}
      <Pressable
        style={({ pressed }) => [
          styles.fab,
          pressed && styles.fabPressed,
        ]}
        onPress={handleNewChat}
      >
        <Ionicons name="add" size={28} color="#ffffff" />
      </Pressable>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0f172a',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: '#1e293b',
  },
  headerTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: '#f8fafc',
  },
  headerAction: {
    padding: 6,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    gap: 12,
  },
  loadingText: {
    color: '#94a3b8',
    fontSize: 14,
  },
  listContent: {
    paddingVertical: 8,
  },
  emptyList: {
    flexGrow: 1,
  },
  separator: {
    height: 1,
    backgroundColor: '#1e293b',
    marginHorizontal: 20,
  },
  // Session card
  sessionCard: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 14,
    paddingHorizontal: 20,
    gap: 12,
  },
  sessionCardPressed: {
    backgroundColor: '#1e293b',
  },
  sessionIcon: {
    width: 40,
    height: 40,
    borderRadius: 12,
    backgroundColor: 'rgba(99, 102, 241, 0.12)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  sessionContent: {
    flex: 1,
    gap: 4,
  },
  sessionTitle: {
    fontSize: 15,
    fontWeight: '600',
    color: '#e2e8f0',
    lineHeight: 20,
  },
  sessionMeta: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  sessionTime: {
    fontSize: 12,
    color: '#64748b',
  },
  sessionTurns: {
    fontSize: 12,
    color: '#475569',
  },

  // FAB
  fab: {
    position: 'absolute',
    bottom: 24,
    right: 20,
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: '#6366f1',
    justifyContent: 'center',
    alignItems: 'center',
    elevation: 8,
    shadowColor: '#6366f1',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.35,
    shadowRadius: 8,
  },
  fabPressed: {
    backgroundColor: '#4f46e5',
    transform: [{ scale: 0.95 }],
  },
});

export default SessionListScreen;
