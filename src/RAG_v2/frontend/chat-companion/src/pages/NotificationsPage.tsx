import React from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Navigate, useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import {
  createApiClient,
  listNotifications,
  getUnreadCount,
  markNotificationRead,
  markAllNotificationsRead,
  deleteNotification,
} from '@rag/shared';
import type { NotificationItem } from '@rag/shared';
import { getStoredToken } from '@/services/authStorage';
import { clearSession, ensureAccessToken, refreshSession } from '@/services/authSession';

function getRelativeTime(dateStr: string): string {
  const now = Date.now();
  const date = new Date(dateStr).getTime();
  const diff = Math.max(0, now - date);
  const seconds = Math.floor(diff / 1000);
  if (seconds < 60) return 'Vừa xong';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} phút trước`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} giờ trước`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days} ngày trước`;
  return new Date(dateStr).toLocaleDateString('vi-VN');
}

const NotificationsPage = () => {
  const isAuthenticated = Boolean(getStoredToken());
  const navigate = useNavigate();
  const client = React.useMemo(
    () =>
      createApiClient({
        baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
        getToken: ensureAccessToken,
        refreshAuth: async () => (await refreshSession()).access_token,
        onUnauthorized: clearSession,
        withCredentials: true,
      }),
    [],
  );
  const queryClient = useQueryClient();

  const { data } = useQuery({
    queryKey: ['notifications'],
    queryFn: () => listNotifications(client),
    enabled: isAuthenticated,
    refetchInterval: 30_000,
  });
  const notifications = data?.notifications ?? [];

  const { data: unreadData } = useQuery({
    queryKey: ['notifications-unread-count'],
    queryFn: () => getUnreadCount(client),
    enabled: isAuthenticated,
    refetchInterval: 30_000,
  });
  const unreadCount = unreadData?.unread_count ?? 0;

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['notifications'] });
    queryClient.invalidateQueries({ queryKey: ['notifications-unread-count'] });
    queryClient.invalidateQueries({ queryKey: ['notifications-bell'] });
  };

  const markRead = useMutation({
    mutationFn: (id: string) => markNotificationRead(client, id),
    onSuccess: invalidate,
  });
  const markAllRead = useMutation({
    mutationFn: () => markAllNotificationsRead(client),
    onSuccess: invalidate,
  });
  const deleteItem = useMutation({
    mutationFn: (id: string) => deleteNotification(client, id),
    onSuccess: invalidate,
  });

  if (!isAuthenticated) return <Navigate to="/login" replace />;

  return (
    <div className="min-h-screen bg-background p-6 max-w-3xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/chat')}
            className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft className="h-4 w-4" />
            Quay lại
          </button>
          <div>
            <h1 className="text-2xl font-bold text-foreground">Thông báo</h1>
            {unreadCount > 0 && (
              <p className="text-xs text-primary font-medium mt-1">{unreadCount} chưa đọc</p>
            )}
          </div>
        </div>
        {unreadCount > 0 && (
          <button
            onClick={() => markAllRead.mutate()}
            className="px-3 py-1.5 rounded-lg bg-primary/10 text-primary text-xs font-medium hover:bg-primary/20"
          >
            Đọc tất cả
          </button>
        )}
      </div>

      {notifications.length === 0 ? (
        <div className="text-muted-foreground text-center py-12">Chưa có thông báo</div>
      ) : (
        <div className="space-y-2">
          {notifications.map((item) => {
            const icon = item.type === 'crawler_update' ? '📚' : '📢';
            const timeAgo = getRelativeTime(item.created_at);
            const links = item.metadata?.article_links ?? [];

            return (
              <div
                key={item.id}
                className={`rounded-xl border p-4 flex gap-3 items-start cursor-pointer transition-colors ${
                  item.read
                    ? 'border-border bg-card'
                    : 'border-primary/30 bg-primary/5'
                }`}
                onClick={() => { if (!item.read) markRead.mutate(item.id); }}
              >
                <span className="text-lg shrink-0 mt-0.5">{icon}</span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-foreground">{item.title}</p>
                  <p className="text-xs text-muted-foreground mt-1 line-clamp-3">{item.body}</p>

                  {links.length > 0 && (
                    <div className="mt-2 space-y-1">
                      {links.map((link, i) => (
                        <a
                          key={i}
                          href={link.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="block text-xs text-primary hover:underline truncate"
                          onClick={(e) => e.stopPropagation()}
                        >
                          🔗 {link.title}
                        </a>
                      ))}
                    </div>
                  )}

                  <span className="text-[10px] text-muted-foreground mt-1.5 block">{timeAgo}</span>
                </div>
                <button
                  onClick={(e) => { e.stopPropagation(); deleteItem.mutate(item.id); }}
                  className="shrink-0 p-1 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive text-xs"
                  title="Xóa"
                >
                  ✕
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default NotificationsPage;
