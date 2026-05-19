import React from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Navigate } from 'react-router-dom';
import {
  createApiClient,
  listNotifications,
  getUnreadCount,
  markNotificationRead,
  markAllNotificationsRead,
  deleteNotification,
} from '@rag/shared';
import type { NotificationItem } from '@rag/shared';

const getClient = () => createApiClient({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  getToken: async () => localStorage.getItem('access_token'),
});

const NotificationsPage = () => {
  const token = localStorage.getItem('access_token');
  if (!token) return <Navigate to="/login" replace />;

  const client = getClient();
  const queryClient = useQueryClient();

  const { data } = useQuery({
    queryKey: ['notifications'],
    queryFn: () => listNotifications(client),
  });
  const notifications = data?.notifications ?? [];

  const { data: unreadData } = useQuery({
    queryKey: ['notifications-unread-count'],
    queryFn: () => getUnreadCount(client),
  });
  const unreadCount = unreadData?.unread_count ?? 0;

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['notifications'] });
    queryClient.invalidateQueries({ queryKey: ['notifications-unread-count'] });
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

  return (
    <div className="min-h-screen bg-background p-6 max-w-3xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Thông báo</h1>
          {unreadCount > 0 && (
            <p className="text-xs text-primary font-medium mt-1">{unreadCount} chưa đọc</p>
          )}
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
          {notifications.map((item) => (
            <div
              key={item.id}
              className={`rounded-xl border p-4 flex gap-3 items-start cursor-pointer transition-colors ${
                item.read
                  ? 'border-border bg-card'
                  : 'border-primary/30 bg-primary/5'
              }`}
              onClick={() => { if (!item.read) markRead.mutate(item.id); }}
            >
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-foreground">{item.title}</p>
                <p className="text-xs text-muted-foreground mt-1 line-clamp-3">{item.body}</p>
                <span className="text-[10px] text-muted-foreground mt-1 block">{item.type}</span>
              </div>
              <button
                onClick={(e) => { e.stopPropagation(); deleteItem.mutate(item.id); }}
                className="shrink-0 p-1 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive text-xs"
                title="Xóa"
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default NotificationsPage;
