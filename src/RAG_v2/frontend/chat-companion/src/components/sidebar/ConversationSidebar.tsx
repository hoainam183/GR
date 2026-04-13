import { useNavigate, useParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from '@/components/ui/sidebar';
import { getSessions } from '@/services/sessionApi';
import type { Session } from '@/types/chat';

interface ConversationSidebarProps {
  userId: string | null | undefined;
  onLogout: () => void;
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const minutes = Math.floor(diff / 60_000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(iso).toLocaleDateString();
}

export function ConversationSidebar({ userId, onLogout }: ConversationSidebarProps) {
  const navigate = useNavigate();
  const { sessionId: activeSessionId } = useParams<{ sessionId?: string }>();
  const queryClient = useQueryClient();

  const { data: sessions = [], isLoading } = useQuery<Session[]>({
    queryKey: ['sessions', userId],
    queryFn: () => getSessions(userId!),
    staleTime: 30_000,
    enabled: !!userId,
  });

  const handleNewChat = () => {
    queryClient.invalidateQueries({ queryKey: ['sessions', userId] });
    navigate('/chat');
  };

  return (
    <Sidebar collapsible="offcanvas">
      {/* Header */}
      <SidebarHeader className="px-3 py-3">
        <button
          onClick={handleNewChat}
          className="flex w-full items-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground transition hover:bg-primary/90"
        >
          <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          New Chat
        </button>
      </SidebarHeader>

      {/* Conversation list */}
      <SidebarContent className="overflow-y-auto px-2">
        {isLoading ? (
          <div className="space-y-1 px-1 py-2">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-9 animate-pulse rounded-md bg-muted" />
            ))}
          </div>
        ) : sessions.length === 0 ? (
          <p className="px-3 py-4 text-center text-xs text-muted-foreground">No conversations yet</p>
        ) : (
          <SidebarMenu>
            {sessions.map((session: Session) => {
              const isActive = session.session_id === activeSessionId;
              const title = session.title
                ? session.title.length > 40
                  ? session.title.slice(0, 40) + '…'
                  : session.title
                : 'New conversation';
              return (
                <SidebarMenuItem key={session.session_id}>
                  <SidebarMenuButton
                    isActive={isActive}
                    onClick={() => navigate(`/chat/${session.session_id}`)}
                    className="flex h-auto w-full flex-col items-start gap-0.5 rounded-md px-3 py-2 text-left"
                  >
                    <span className="truncate text-sm leading-tight">{title}</span>
                    <span className="text-[10px] text-muted-foreground">
                      {relativeTime(session.updated_at)}
                    </span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              );
            })}
          </SidebarMenu>
        )}
      </SidebarContent>

      {/* Footer */}
      <SidebarFooter className="border-t border-border px-3 py-2">
        <button
          onClick={onLogout}
          className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-xs text-destructive hover:bg-destructive/10 transition"
        >
          <svg className="h-3.5 w-3.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
          </svg>
          Đăng xuất
        </button>
      </SidebarFooter>
    </Sidebar>
  );
}
