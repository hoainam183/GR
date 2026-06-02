import { useState, useRef, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Bell } from 'lucide-react';
import {
  createApiClient,
  listNotifications,
  getUnreadCount,
  markNotificationRead,
  markAllNotificationsRead,
} from '@rag/shared';
import type { NotificationItem } from '@rag/shared';
import { ensureAccessToken, refreshSession, clearSession } from '@/services/authSession';

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

function NotificationRow({ item, onRead }: { item: NotificationItem; onRead: () => void }) {
  const icon = item.type === 'crawler_update' ? '📚' : '📢';
  const timeAgo = getRelativeTime(item.created_at);
  const links = item.metadata?.article_links ?? [];

  return (
    <div
      onClick={onRead}
      className={`px-4 py-3 cursor-pointer hover:bg-muted/50 transition-colors ${
        item.read ? '' : 'bg-primary/5'
      }`}
    >
      <div className="grid grid-cols-[1.75rem_minmax(0,1fr)_0.5rem] gap-3">
        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-primary/10 text-base">{icon}</span>
        <div className="min-w-0 flex-1">
          <p className="break-words text-sm font-semibold leading-snug text-foreground">{item.title}</p>
          <p className="mt-1 line-clamp-3 break-words text-xs leading-relaxed text-muted-foreground">{item.body}</p>

          {links.length > 0 && (
            <div className="mt-1.5 space-y-0.5">
              {links.slice(0, 3).map((link, i) => (
                <a
                  key={i}
                  href={link.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block truncate text-xs text-primary hover:underline"
                  onClick={(e) => e.stopPropagation()}
                >
                  🔗 {link.title}
                </a>
              ))}
            </div>
          )}

          <span className="mt-1.5 block text-[10px] text-muted-foreground">{timeAgo}</span>
        </div>
        <span className="pt-1.5">
          {!item.read && <span className="block h-2 w-2 rounded-full bg-primary" />}
        </span>
      </div>
    </div>
  );
}

export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const prevCountRef = useRef(0);

  const client = useMemo(
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

  // Polling unread count mỗi 30s
  const { data: unreadData } = useQuery({
    queryKey: ['notifications-unread-count'],
    queryFn: () => getUnreadCount(client),
    refetchInterval: 30_000,
  });
  const unreadCount = unreadData?.unread_count ?? 0;

  // Fetch notifications khi dropdown mở
  const { data: notifData } = useQuery({
    queryKey: ['notifications-bell'],
    queryFn: () => listNotifications(client, { limit: 10 }),
    enabled: open,
    refetchInterval: open ? 30_000 : false,
  });
  const notifications = notifData?.notifications ?? [];

  // Bell shake animation khi count tăng
  const [shaking, setShaking] = useState(false);
  useEffect(() => {
    if (unreadCount > prevCountRef.current && prevCountRef.current !== 0) {
      setShaking(true);
      const timer = setTimeout(() => setShaking(false), 600);
      return () => clearTimeout(timer);
    }
    prevCountRef.current = unreadCount;
  }, [unreadCount]);

  // Click outside → đóng dropdown
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  // Mark read mutation
  const markRead = useMutation({
    mutationFn: (id: string) => markNotificationRead(client, id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications-unread-count'] });
      queryClient.invalidateQueries({ queryKey: ['notifications-bell'] });
    },
  });

  const markAllRead = useMutation({
    mutationFn: () => markAllNotificationsRead(client),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications-unread-count'] });
      queryClient.invalidateQueries({ queryKey: ['notifications-bell'] });
    },
  });

  return (
    <div className="relative" ref={ref}>
      {/* Bell button */}
      <button
        onClick={() => setOpen((v) => !v)}
        className={`relative flex h-8 w-8 items-center justify-center rounded-md hover:bg-muted transition-colors ${shaking ? 'animate-bell-shake' : ''}`}
        aria-label="Thông báo"
        title="Thông báo"
      >
        <Bell className="h-4 w-4" />
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-bold text-destructive-foreground">
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>

      {/* Dropdown panel */}
      {open && (
        <div className="fixed right-3 top-14 z-[100] w-[calc(100vw-1.5rem)] max-w-sm overflow-hidden rounded-xl border bg-card shadow-2xl ring-1 ring-black/5 sm:right-6 sm:w-96">
          {/* Header */}
          <div className="flex items-center justify-between gap-3 border-b bg-card px-4 py-3">
            <h3 className="font-semibold text-sm text-foreground">Thông báo</h3>
            {unreadCount > 0 && (
              <button
                onClick={() => markAllRead.mutate()}
                className="shrink-0 text-xs font-medium text-primary hover:underline"
              >
                Đọc tất cả
              </button>
            )}
          </div>

          {/* Notification list */}
          <div className="max-h-[min(420px,calc(100vh-8rem))] divide-y divide-border overflow-y-auto overscroll-contain scrollbar-thin">
            {notifications.map((item) => (
              <NotificationRow
                key={item.id}
                item={item}
                onRead={() => {
                  if (!item.read) markRead.mutate(item.id);
                }}
              />
            ))}
            {notifications.length === 0 && (
              <p className="text-center py-8 text-sm text-muted-foreground">Chưa có thông báo</p>
            )}
          </div>

          {/* Footer */}
          <div className="border-t bg-card px-4 py-2.5 text-center">
            <button
              onClick={() => {
                navigate('/notifications');
                setOpen(false);
              }}
              className="text-xs text-primary hover:underline font-medium"
            >
              Xem tất cả thông báo →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
