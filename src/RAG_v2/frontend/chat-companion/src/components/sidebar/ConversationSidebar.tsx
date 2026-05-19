import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  LogOut,
  MessageSquare,
  MoreHorizontal,
  Pencil,
  Plus,
  Search,
  Trash2,
} from 'lucide-react';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { deleteSession, getSessions, renameSession } from '@/services/sessionApi';
import type { Session } from '@/types/chat';
import { cn, parseUtcDate } from '@/lib/utils';

interface ConversationSidebarProps {
  userId: string | null | undefined;
  onLogout: () => void;
  isMobile?: boolean;
  onCloseMobile?: () => void;
}

interface SessionGroup {
  label: string;
  sessions: Session[];
}

const FALLBACK_TITLE = 'Cuộc trò chuyện mới';
const DAY_MS = 86_400_000;

function sessionTitle(session: Session): string {
  return session.title?.trim() || FALLBACK_TITLE;
}

function relativeTime(iso: string): string {
  const diff = Math.max(0, Date.now() - parseUtcDate(iso).getTime());
  const minutes = Math.floor(diff / 60_000);
  if (minutes < 1) return 'vừa xong';
  if (minutes < 60) return `${minutes} phút trước`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} giờ trước`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days} ngày trước`;
  return parseUtcDate(iso).toLocaleDateString('vi-VN');
}

function groupSessionsByDate(sessions: Session[]): SessionGroup[] {
  const now = Date.now();
  const buckets: Record<string, Session[]> = {
    'Hôm nay': [],
    'Hôm qua': [],
    '7 ngày trước': [],
    '30 ngày trước': [],
    'Cũ hơn': [],
  };

  for (const session of sessions) {
    const diff = Math.max(0, now - parseUtcDate(session.updated_at).getTime());
    if (diff < DAY_MS) {
      buckets['Hôm nay'].push(session);
    } else if (diff < 2 * DAY_MS) {
      buckets['Hôm qua'].push(session);
    } else if (diff < 7 * DAY_MS) {
      buckets['7 ngày trước'].push(session);
    } else if (diff < 30 * DAY_MS) {
      buckets['30 ngày trước'].push(session);
    } else {
      buckets['Cũ hơn'].push(session);
    }
  }

  return Object.entries(buckets)
    .filter(([, items]) => items.length > 0)
    .map(([label, items]) => ({ label, sessions: items }));
}

export function ConversationSidebar({
  userId,
  onLogout,
  isMobile = false,
  onCloseMobile,
}: ConversationSidebarProps) {
  const navigate = useNavigate();
  const { sessionId: activeSessionId } = useParams<{ sessionId?: string }>();
  const queryClient = useQueryClient();
  const [searchQuery, setSearchQuery] = useState('');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [deleteTarget, setDeleteTarget] = useState<Session | null>(null);
  const skipBlurCommitRef = useRef(false);
  const editInputRef = useRef<HTMLInputElement>(null);

  const { data: sessions = [], isLoading } = useQuery<Session[]>({
    queryKey: ['sessions', userId],
    queryFn: () => getSessions(userId!),
    staleTime: 30_000,
    enabled: !!userId,
  });

  const renameMutation = useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) =>
      renameSession(id, title),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sessions', userId] });
      setEditingId(null);
      setEditTitle('');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteSession(id),
    onSuccess: (_data, deletedId) => {
      queryClient.invalidateQueries({ queryKey: ['sessions', userId] });
      setDeleteTarget(null);
      if (deletedId === activeSessionId) {
        navigate('/chat');
      }
      if (isMobile) {
        onCloseMobile?.();
      }
    },
  });

  useEffect(() => {
    if (editingId) {
      editInputRef.current?.focus();
      editInputRef.current?.select();
    }
  }, [editingId]);

  const filteredSessions = useMemo(() => {
    const normalized = searchQuery.trim().toLowerCase();
    if (!normalized) return sessions;
    return sessions.filter((session) =>
      sessionTitle(session).toLowerCase().includes(normalized),
    );
  }, [searchQuery, sessions]);

  const groups = useMemo(
    () => groupSessionsByDate(filteredSessions),
    [filteredSessions],
  );

  const handleNewChat = () => {
    queryClient.invalidateQueries({ queryKey: ['sessions', userId] });
    navigate('/chat');
    if (isMobile) {
      onCloseMobile?.();
    }
  };

  const handleOpenSession = (sessionId: string) => {
    navigate(`/chat/${sessionId}`);
    if (isMobile) {
      onCloseMobile?.();
    }
  };

  const startRename = (session: Session) => {
    setEditingId(session.session_id);
    setEditTitle(session.title?.trim() ?? '');
  };

  const cancelRename = () => {
    skipBlurCommitRef.current = true;
    setEditingId(null);
    setEditTitle('');
  };

  const commitRename = (session: Session) => {
    if (skipBlurCommitRef.current) {
      skipBlurCommitRef.current = false;
      return;
    }
    const title = editTitle.trim();
    if (!title || title === (session.title?.trim() ?? '')) {
      setEditingId(null);
      setEditTitle('');
      return;
    }
    renameMutation.mutate({ id: session.session_id, title });
  };

  return (
    <div className="flex h-full flex-col bg-sidebar text-sidebar-foreground">
      {/* Branding */}
      <div className="flex shrink-0 items-center gap-2.5 border-b border-sidebar-border px-3 py-3">
        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-primary">
          <svg className="h-3.5 w-3.5 text-primary-foreground" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
          </svg>
        </div>
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-foreground leading-tight">HUST Assistant</p>
          <p className="truncate text-[10px] text-muted-foreground leading-tight">Trợ lý học thuật BKHN</p>
        </div>
      </div>

      <div className="shrink-0 space-y-2 border-b border-sidebar-border px-3 py-3">
        <button
          onClick={handleNewChat}
          className="flex h-9 w-full items-center justify-center gap-2 rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground transition hover:bg-primary/90"
        >
          <Plus className="h-4 w-4" />
          Cuộc trò chuyện mới
        </button>

        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <input
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
            placeholder="Tìm kiếm..."
            className="h-8 w-full rounded-md border border-sidebar-border bg-background pl-8 pr-3 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
          />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto scrollbar-thin px-2 py-2">
        {isLoading ? (
          <div className="space-y-1 px-1 py-2">
            {[...Array(6)].map((_, index) => (
              <div key={index} className="h-10 animate-pulse rounded-md bg-muted" />
            ))}
          </div>
        ) : sessions.length === 0 ? (
          <p className="px-3 py-4 text-center text-xs text-muted-foreground">
            Chưa có cuộc trò chuyện
          </p>
        ) : groups.length === 0 ? (
          <p className="px-3 py-4 text-center text-xs text-muted-foreground">
            Không tìm thấy cuộc trò chuyện
          </p>
        ) : (
          <div className="space-y-4">
            {groups.map((group) => (
              <section key={group.label}>
                <h2 className="mb-1 px-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                  {group.label}
                </h2>
                <div className="space-y-1">
                  {group.sessions.map((session) => {
                    const isActive = session.session_id === activeSessionId;
                    const isEditing = editingId === session.session_id;
                    return (
                      <div
                        key={session.session_id}
                        className={cn(
                          'conversation-item group relative flex min-h-11 items-center gap-1 rounded-md px-2 py-1.5 transition-colors',
                          isActive
                            ? 'bg-sidebar-accent text-sidebar-accent-foreground'
                            : 'hover:bg-sidebar-accent/70',
                        )}
                      >
                        <MessageSquare className="h-4 w-4 shrink-0 text-muted-foreground" />
                        {isEditing ? (
                          <input
                            ref={editInputRef}
                            value={editTitle}
                            onChange={(event) => setEditTitle(event.target.value)}
                            onBlur={() => commitRename(session)}
                            onKeyDown={(event) => {
                              if (event.key === 'Enter') {
                                event.preventDefault();
                                commitRename(session);
                              } else if (event.key === 'Escape') {
                                event.preventDefault();
                                cancelRename();
                              }
                            }}
                            disabled={renameMutation.isPending}
                            placeholder={FALLBACK_TITLE}
                            className="min-w-0 flex-1 rounded-sm border border-border bg-background px-2 py-1 text-sm text-foreground outline-none focus:ring-1 focus:ring-ring"
                          />
                        ) : (
                          <button
                            onClick={() => handleOpenSession(session.session_id)}
                            className="min-w-0 flex-1 text-left"
                          >
                            <span className="block truncate text-sm leading-tight">
                              {sessionTitle(session)}
                            </span>
                            <span className="block text-[10px] text-muted-foreground">
                              {relativeTime(session.updated_at)}
                            </span>
                          </button>
                        )}

                        {!isEditing && (
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <button
                                className="action-trigger flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-muted-foreground hover:bg-background hover:text-foreground focus:opacity-100 focus:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                aria-label="Tuỳ chọn cuộc trò chuyện"
                                onClick={(event) => event.stopPropagation()}
                              >
                                <MoreHorizontal className="h-4 w-4" />
                              </button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end" sideOffset={6}>
                              <DropdownMenuItem onSelect={() => startRename(session)}>
                                <Pencil className="mr-2 h-4 w-4" />
                                Đổi tên
                              </DropdownMenuItem>
                              <DropdownMenuItem
                                className="text-destructive focus:text-destructive"
                                onSelect={() => setDeleteTarget(session)}
                              >
                                <Trash2 className="mr-2 h-4 w-4" />
                                Xoá
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        )}
                      </div>
                    );
                  })}
                </div>
              </section>
            ))}
          </div>
        )}
      </div>

      <div className="shrink-0 border-t border-sidebar-border px-3 py-2">
        <button
          onClick={onLogout}
          className="flex h-9 w-full items-center gap-2 rounded-md px-3 text-xs text-destructive transition hover:bg-destructive/10"
        >
          <LogOut className="h-4 w-4" />
          Đăng xuất
        </button>
      </div>

      <AlertDialog open={!!deleteTarget} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Xoá cuộc trò chuyện?</AlertDialogTitle>
            <AlertDialogDescription>
              &quot;{deleteTarget ? sessionTitle(deleteTarget) : FALLBACK_TITLE}&quot; sẽ bị xoá vĩnh viễn.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Huỷ</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              disabled={deleteMutation.isPending}
              onClick={() => deleteTarget && deleteMutation.mutate(deleteTarget.session_id)}
            >
              Xoá
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
