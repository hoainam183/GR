import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import ChatContainer from '@/components/chat/ChatContainer';
import { ConversationSidebar } from '@/components/sidebar/ConversationSidebar';
import { Button } from '@/components/ui/button';
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from '@/components/ui/resizable';
import { Sheet, SheetContent, SheetTitle } from '@/components/ui/sheet';
import { useIsMobile } from '@/hooks/use-mobile';
import { useResizableSidebar } from '@/hooks/useResizableSidebar';
import { getMe, type UserPublic } from '@/services/authApi';
import { getSessions } from '@/services/sessionApi';
import { Activity, PanelLeft } from 'lucide-react';

interface UserMenuProps {
  user: UserPublic;
  onLogout: () => void;
}

const userOwnerId = (user?: UserPublic | null): string | undefined =>
  user?._id ?? user?.email ?? user?.username ?? user?.student_id ?? undefined;

const UserMenu = ({ user, onLogout }: UserMenuProps) => {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const initials = user.full_name
    .split(' ')
    .map((word) => word[0])
    .slice(-2)
    .join('')
    .toUpperCase();

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((value) => !value)}
        className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground ring-2 ring-primary/30 transition hover:ring-4 focus:outline-none"
        aria-label="User menu"
      >
        {initials}
      </button>

      {open && (
        <div className="absolute right-0 top-10 z-50 w-64 rounded-xl border border-border bg-card p-4 shadow-lg">
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

          <button
            onClick={onLogout}
            className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-xs text-destructive transition hover:bg-destructive/10"
          >
            Đăng xuất
          </button>
        </div>
      )}
    </div>
  );
};

const Index = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { sessionId } = useParams<{ sessionId?: string }>();
  const [user, setUser] = useState<UserPublic | null>(null);
  const isAdmin = user?.role === 'admin';
  const isMobile = useIsMobile();
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
    if (!sessionId) return 'HUST Assistant';
    const session = sessions.find((item) => item.session_id === sessionId);
    return session?.title?.trim() || 'HUST Assistant';
  }, [sessionId, sessions]);

  useEffect(() => {
    let cancelled = false;

    const bootstrapUser = async () => {
      const urlToken = searchParams.get('token');
      if (urlToken) {
        localStorage.setItem('token', urlToken);
        navigate('/chat', { replace: true });
      }

      const storedToken = urlToken || localStorage.getItem('token');
      if (!storedToken) {
        navigate('/login', { replace: true });
        return;
      }

      const storedUser = localStorage.getItem('user');
      if (storedUser) {
        try {
          if (!cancelled) {
            setUser(JSON.parse(storedUser) as UserPublic);
          }
          return;
        } catch {
          localStorage.removeItem('user');
        }
      }

      try {
        const profile = await getMe(storedToken);
        if (cancelled) {
          return;
        }
        setUser(profile);
        localStorage.setItem('user', JSON.stringify(profile));
      } catch {
        if (cancelled) {
          return;
        }
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        navigate('/login', { replace: true });
      }
    };

    bootstrapUser();

    return () => {
      cancelled = true;
    };
  }, [navigate, searchParams]);

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

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    navigate('/login', { replace: true });
  };

  const openSidebar = () => {
    if (isMobile) {
      setMobileOpen(true);
    } else {
      toggle();
    }
  };

  const header = (
    <header className="shrink-0 border-b border-border bg-background/80 backdrop-blur-sm">
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
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary">
            <svg
              className="h-4 w-4 text-primary-foreground"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
              />
            </svg>
          </div>
          <h1 className="truncate text-base font-semibold text-foreground sm:text-lg">
            {activeSessionTitle}
          </h1>
        </div>

        <div className="flex shrink-0 items-center gap-2 sm:gap-3">
          {isAdmin && (
            <Link
              to="/trace"
              className="flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              title="Pipeline Trace Debugger"
            >
              <Activity className="h-3.5 w-3.5" />
              Trace
            </Link>
          )}
          {user && <UserMenu user={user} onLogout={handleLogout} />}
        </div>
      </div>
    </header>
  );

  const main = (
    <main className="flex h-full flex-1 flex-col overflow-hidden">
      {header}
      <div className="flex-1 overflow-hidden">
        <ChatContainer user={user} sessionId={sessionId} />
      </div>
    </main>
  );

  if (!user) {
    return <div className="flex h-screen w-full overflow-hidden bg-chat-container">{main}</div>;
  }

  if (isMobile) {
    return (
      <div className="flex h-screen w-full overflow-hidden bg-chat-container">
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
    <div className="flex h-screen w-full overflow-hidden bg-chat-container">
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
