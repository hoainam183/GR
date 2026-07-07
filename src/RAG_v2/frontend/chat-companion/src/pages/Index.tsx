import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import ChatContainer from '@/components/chat/ChatContainer';
import { ConversationSidebar } from '@/components/sidebar/ConversationSidebar';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from '@/components/ui/resizable';
import { Sheet, SheetContent, SheetTitle } from '@/components/ui/sheet';
import { useIsMobile } from '@/hooks/use-mobile';
import { useResizableSidebar } from '@/hooks/useResizableSidebar';
import {
  getStoredUser,
  setStoredUser,
} from '@/services/authStorage';
import { type UserPublic } from '@/services/authApi';
import { ensureSession, logoutSession } from '@/services/authSession';
import { getSessions } from '@/services/sessionApi';
import { Bookmark, Bug, Loader2, LogOut, Moon, PanelLeft, Sun } from 'lucide-react';
import { NotificationBell } from '@/components/NotificationBell';
import HustLogo from '@/components/HustLogo';

interface UserMenuProps {
  user: UserPublic;
  onLogout: () => Promise<void> | void;
}

const userOwnerId = (user?: UserPublic | null): string | undefined =>
  user?._id ?? user?.email ?? user?.username ?? user?.student_id ?? undefined;

const UserMenu = ({ user, onLogout }: UserMenuProps) => {
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  const initials = user.full_name
    .split(' ')
    .map((word) => word[0])
    .slice(-2)
    .join('')
    .toUpperCase();

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
      <button
        className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground ring-2 ring-primary/30 transition hover:ring-4 focus:outline-none focus-visible:ring-4 focus-visible:ring-ring"
        aria-label="User menu"
      >
        {initials}
      </button>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="end" className="w-64 rounded-lg p-4">
        <div>
          <div className="mb-3 border-b border-border pb-3">
            <p className="text-sm font-semibold text-foreground">{user.full_name}</p>
            {user.email && (
              <p className="mt-0.5 truncate text-xs text-muted-foreground">{user.email}</p>
            )}
            {user.username && !user.email && (
              <p className="mt-0.5 text-xs text-muted-foreground">@{user.username}</p>
            )}
          </div>

          <div className="mb-3 space-y-1.5 text-xs text-muted-foreground">
            <div className="flex justify-between gap-4">
              <span>Mã SV</span>
              <span className="truncate font-medium text-foreground">
                {user.student_id || '-'}
              </span>
            </div>
            <div className="flex justify-between gap-4">
              <span>Ngành</span>
              <span className="max-w-[140px] truncate text-right font-medium text-foreground">
                {user.major || '-'}
              </span>
            </div>
            <div className="flex justify-between gap-4">
              <span>Khoá</span>
              <span className="font-medium text-foreground">{user.cohort || '-'}</span>
            </div>
          </div>

          <DropdownMenuItem
            className="cursor-pointer gap-2 text-destructive focus:bg-destructive/10 focus:text-destructive"
            disabled={isLoggingOut}
            onSelect={(event) => {
              event.preventDefault();
              setIsLoggingOut(true);
              Promise.resolve(onLogout()).finally(() => setIsLoggingOut(false));
            }}
          >
            {isLoggingOut ? <Loader2 className="h-4 w-4 animate-spin" /> : <LogOut className="h-4 w-4" />}
            Đăng xuất
          </DropdownMenuItem>
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  );
};

const Index = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { sessionId } = useParams<{ sessionId?: string }>();
  // Initialise synchronously from localStorage so ownerId is available on
  // the first render and the sessions query fires without waiting for an effect.
  const [user, setUser] = useState<UserPublic | null>(() => getStoredUser<UserPublic>());
  const isMobile = useIsMobile();
  const [isDark, setIsDark] = useState(() => {
    const saved = localStorage.getItem('theme');
    if (saved === 'dark') return true;
    if (saved === 'light') return false;
    return window.matchMedia('(prefers-color-scheme: dark)').matches;
  });
  // Debug view: reveals the pipeline/agent trace and raw source ranking on each
  // answer. Off by default so students see a clean chat; persisted per browser.
  const [showDebug, setShowDebug] = useState(() => localStorage.getItem('chat-debug') === 'on');

  useEffect(() => {
    localStorage.setItem('chat-debug', showDebug ? 'on' : 'off');
  }, [showDebug]);

  useEffect(() => {
    if (isDark) {
      document.documentElement.classList.add('dark');
      localStorage.setItem('theme', 'dark');
    } else {
      document.documentElement.classList.remove('dark');
      localStorage.setItem('theme', 'light');
    }
  }, [isDark]);
  const [mobileOpen, setMobileOpen] = useState(false);
  const {
    panelRef,
    isCollapsed,
    toggle,
    onCollapse,
    onExpand,
    persistSize,
    getDefaultSize,
  } = useResizableSidebar();

  const ownerId = userOwnerId(user);
  const { data: sessions = [] } = useQuery({
    queryKey: ['sessions', ownerId],
    queryFn: () => getSessions(ownerId!),
    enabled: !!ownerId,
    staleTime: 30_000,
  });

  const activeSessionTitle = useMemo(() => {
    if (!sessionId) return 'Trợ Lý Học Vụ BK';
    const session = sessions.find((item) => item.session_id === sessionId);
    return session?.title?.trim() || 'Trợ Lý Học Vụ BK';
  }, [sessionId, sessions]);

  useEffect(() => {
    let cancelled = false;

    const bootstrapUser = async () => {
      const storedUser = getStoredUser<UserPublic>();
      if (storedUser) {
        if (!cancelled) {
          setUser(storedUser);
        }
        return;
      }

      try {
        const profile = await ensureSession();
        if (cancelled) {
          return;
        }
        if (!profile) {
          navigate('/login', { replace: true });
          return;
        }
        setUser(profile);
        setStoredUser(profile);
      } catch {
        if (cancelled) {
          return;
        }
        navigate('/login', { replace: true });
      }
    };

    bootstrapUser();

    return () => {
      cancelled = true;
    };
  }, [navigate]);

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() === 'b' && (event.metaKey || event.ctrlKey)) {
        event.preventDefault();
        if (isMobile) {
          setMobileOpen((value) => !value);
        } else {
          toggle();
        }
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [isMobile, toggle]);

  const handleLogout = async () => {
    try {
      await logoutSession();
    } catch (error) {
      console.warn('Logout request failed, clearing local session anyway:', error);
    } finally {
      setUser(null);
      setMobileOpen(false);
      queryClient.clear();
      navigate('/login', { replace: true });
    }
  };

  const openSidebar = () => {
    if (isMobile) {
      setMobileOpen(true);
    } else {
      toggle();
    }
  };

  const header = (
    <header className="relative z-[1100] shrink-0 border-b border-border bg-background/80 backdrop-blur-sm">
      <div className="flex h-14 items-center justify-between px-4 md:px-6">
        <div className="flex min-w-0 items-center gap-2">
          {user && (
            <Button
              variant="ghost"
              size="icon"
              onClick={openSidebar}
              aria-label={isMobile || isCollapsed ? 'Mở sidebar' : 'Thu gọn sidebar'}
              title={isMobile || isCollapsed ? 'Mở sidebar' : 'Thu gọn sidebar'}
              className="h-8 w-8 shrink-0"
            >
              <PanelLeft className="h-4 w-4" />
            </Button>
          )}
          <HustLogo size="md" />
          <h1 className="truncate text-base font-semibold text-foreground sm:text-lg">
            {activeSessionTitle}
          </h1>
        </div>

        <div className="flex shrink-0 items-center gap-2 sm:gap-3">
          {user && (
            <Button
              variant="ghost"
              size="icon"
              onClick={() => navigate('/bookmarks')}
              aria-label="Câu trả lời đã lưu"
              title="Đã lưu"
              className="h-8 w-8"
            >
              <Bookmark className="h-4 w-4" />
            </Button>
          )}
          {user && <NotificationBell />}
          {user && (
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setShowDebug((prev) => !prev)}
              aria-label={showDebug ? 'Tắt chế độ gỡ lỗi' : 'Bật chế độ gỡ lỗi'}
              aria-pressed={showDebug}
              title={showDebug ? 'Tắt debug' : 'Bật debug'}
              className={`h-8 w-8 ${showDebug ? 'text-primary bg-primary/10' : ''}`}
            >
              <Bug className="h-4 w-4" />
            </Button>
          )}
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setIsDark((prev) => !prev)}
            aria-label={isDark ? 'Chuyển sang chế độ sáng' : 'Chuyển sang chế độ tối'}
            title={isDark ? 'Chế độ sáng' : 'Chế độ tối'}
            className="h-8 w-8"
          >
            {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </Button>
          {user && <UserMenu user={user} onLogout={handleLogout} />}
        </div>
      </div>
    </header>
  );

  const main = (
    <main className="flex h-full min-h-0 flex-1 flex-col overflow-hidden overscroll-none">
      {header}
      <div className="min-h-0 flex-1 overflow-hidden">
        <ChatContainer user={user} sessionId={sessionId} showDebug={showDebug} />
      </div>
    </main>
  );

  if (!user) {
    return <div className="flex h-dvh w-full overflow-hidden overscroll-none bg-chat-container">{main}</div>;
  }

  if (isMobile) {
    return (
      <div className="flex h-dvh w-full overflow-hidden overscroll-none bg-chat-container">
        <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
          <SheetContent side="left" className="w-[18rem] p-0 [&>button]:hidden">
            <SheetTitle className="sr-only">Cuộc trò chuyện</SheetTitle>
            <ConversationSidebar
              userId={ownerId}
              onLogout={handleLogout}
              isMobile
              onCloseMobile={() => setMobileOpen(false)}
            />
          </SheetContent>
        </Sheet>
        {main}
      </div>
    );
  }

  const sidebarDefaultSize = getDefaultSize();

  return (
    <div className="flex h-dvh w-full overflow-hidden overscroll-none bg-chat-container">
      <ResizablePanelGroup direction="horizontal" className="h-full">
        <ResizablePanel
          ref={panelRef}
          defaultSize={sidebarDefaultSize}
          minSize={16}
          maxSize={32}
          collapsible
          collapsedSize={0}
          onCollapse={onCollapse}
          onExpand={onExpand}
          onResize={persistSize}
          className="border-r border-border"
        >
          <ConversationSidebar userId={ownerId} onLogout={handleLogout} />
        </ResizablePanel>

        <ResizableHandle className="w-1 bg-transparent transition-colors hover:bg-primary/20" />

        <ResizablePanel defaultSize={100 - sidebarDefaultSize} minSize={50}>
          {main}
        </ResizablePanel>
      </ResizablePanelGroup>
    </div>
  );
};

export default Index;
