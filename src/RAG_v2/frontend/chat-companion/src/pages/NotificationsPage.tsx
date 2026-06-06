import React from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, BookOpen, CheckCheck, ExternalLink, Megaphone, Trash2 } from 'lucide-react';
import {
  createApiClient,
  listNotifications,
  getUnreadCount,
  markNotificationRead,
  markAllNotificationsRead,
  deleteNotification,
} from '@rag/shared';
import type { NotificationItem } from '@rag/shared';
import { clearSession, ensureAccessToken, refreshSession } from '@/services/authSession';
import {
  getNotificationDisplayBody,
  getNotificationDisplayTitle,
} from '@/services/notificationDisplay';

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
    refetchInterval: 30_000,
  });
  const notifications = data?.notifications ?? [];

  const { data: unreadData } = useQuery({
    queryKey: ['notifications-unread-count'],
    queryFn: () => getUnreadCount(client),
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
            className="inline-flex items-center gap-1.5 rounded-lg bg-primary/10 px-3 py-2 text-xs font-medium text-primary transition-colors hover:bg-primary/20"
          >
            <CheckCheck className="h-3.5 w-3.5" />
            Đọc tất cả
          </button>
        )}
      </div>

      {notifications.length === 0 ? (
        <div className="text-muted-foreground text-center py-12">Chưa có thông báo</div>
      ) : (
        <div className="space-y-2">
          {notifications.map((item) => {
            const Icon = item.type === 'crawler_update' ? BookOpen : Megaphone;
            const title = getNotificationDisplayTitle(item);
            const body = getNotificationDisplayBody(item);
            const timeAgo = getRelativeTime(item.created_at);
            const links = item.metadata?.article_links ?? [];
            const newArticles =
              typeof item.metadata?.new_articles === 'number' ? item.metadata.new_articles : null;

            return (
              <div
                key={item.id}
                className={`flex cursor-pointer items-start gap-3 rounded-xl border p-4 transition-colors hover:border-primary/30 hover:bg-muted/40 ${
                  item.read
                    ? 'border-border bg-card'
                    : 'border-primary/30 bg-primary/5'
                }`}
                onClick={() => { if (!item.read) markRead.mutate(item.id); }}
              >
                <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  <Icon className="h-4 w-4" />
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-foreground">{title}</p>
                  <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{body}</p>
                  {newArticles !== null && (
                    <span className="mt-2 inline-flex rounded-md bg-primary/10 px-2 py-0.5 text-[11px] font-medium text-primary">
                      {newArticles} bài viết mới
                    </span>
                  )}

                  {links.length > 0 && (
                    <div className="mt-2 flex flex-col items-start gap-1.5">
                      {links.map((link, i) => (
                        <a
                          key={i}
                          href={link.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex max-w-full items-center gap-1.5 rounded-md bg-primary/10 px-2 py-1 text-xs font-medium text-primary transition-colors hover:bg-primary/15 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                          onClick={(e) => {
                            e.stopPropagation();
                            if (!item.read) markRead.mutate(item.id);
                          }}
                        >
                          <ExternalLink className="h-3 w-3 shrink-0" />
                          <span className="truncate">{link.title}</span>
                        </a>
                      ))}
                    </div>
                  )}

                  <span className="text-[10px] text-muted-foreground mt-1.5 block">{timeAgo}</span>
                </div>
                <button
                  onClick={(e) => { e.stopPropagation(); deleteItem.mutate(item.id); }}
                  className="shrink-0 rounded-md p-2 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
                  aria-label="Xóa thông báo"
                  title="Xóa thông báo"
                >
                  <Trash2 className="h-4 w-4" />
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
