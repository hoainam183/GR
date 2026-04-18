import { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams, useSearchParams, Link } from 'react-router-dom';
import ChatContainer from '@/components/chat/ChatContainer';
import { ConversationSidebar } from '@/components/sidebar/ConversationSidebar';
import { SidebarProvider, SidebarTrigger } from '@/components/ui/sidebar';
import { getMe, type UserPublic } from '@/services/authApi';
import { Activity } from 'lucide-react';

// ── UserMenu drop-down ──────────────────────────────────────────────────────

interface UserMenuProps {
  user: UserPublic;
  onLogout: () => void;
}

const UserMenu = ({ user, onLogout }: UserMenuProps) => {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Close when clicking outside
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const initials = user.full_name
    .split(' ')
    .map((w) => w[0])
    .slice(-2)
    .join('')
    .toUpperCase();

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground ring-2 ring-primary/30 transition hover:ring-4 focus:outline-none"
        aria-label="User menu"
      >
        {initials}
      </button>

      {open && (
        <div className="absolute right-0 top-10 z-50 w-64 rounded-xl border border-border bg-card p-4 shadow-lg">
          {/* Name + email */}
          <div className="mb-3 border-b border-border pb-3">
            <p className="text-sm font-semibold text-foreground">{user.full_name}</p>
            {user.email && (
              <p className="mt-0.5 truncate text-xs text-muted-foreground">{user.email}</p>
            )}
            {user.username && !user.email && (
              <p className="mt-0.5 text-xs text-muted-foreground">@{user.username}</p>
            )}
          </div>

          {/* Profile details */}
          <div className="mb-3 space-y-1.5 text-xs text-muted-foreground">
            <div className="flex justify-between">
              <span>Mã SV</span>
              <span className="font-medium text-foreground">{user.student_id || '—'}</span>
            </div>
            <div className="flex justify-between">
              <span>Ngành</span>
              <span className="max-w-[140px] truncate text-right font-medium text-foreground">
                {user.major || '—'}
              </span>
            </div>
            <div className="flex justify-between">
              <span>Khoá</span>
              <span className="font-medium text-foreground">{user.cohort || '—'}</span>
            </div>
          </div>

          {/* Logout */}
          <button
            onClick={onLogout}
            className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-xs text-destructive hover:bg-destructive/10 transition"
          >
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
            </svg>
            Đăng xuất
          </button>
        </div>
      )}
    </div>
  );
};

// ── Page ────────────────────────────────────────────────────────────────────

const Index = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { sessionId } = useParams<{ sessionId?: string }>();
  const [user, setUser] = useState<UserPublic | null>(null);

  // On mount: handle OAuth ?token= param OR read from localStorage
  useEffect(() => {
    let cancelled = false;

    const bootstrapUser = async () => {
      const urlToken = searchParams.get('token');
      if (urlToken) {
        localStorage.setItem('token', urlToken);
        // Remove token from URL without a reload
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

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    navigate('/login', { replace: true });
  };

  return (
    <SidebarProvider defaultOpen={true}>
      <div className="flex h-screen w-full overflow-hidden bg-chat-container">
        {/* Sidebar — only rendered when user is logged in */}
        {user && (
          <ConversationSidebar
            userId={user.email ?? user.username ?? user.student_id}
            onLogout={handleLogout}
          />
        )}

        {/* Main area */}
        <main className="flex flex-1 flex-col overflow-hidden">
          {/* Header */}
          <header className="shrink-0 border-b border-border bg-background/80 backdrop-blur-sm">
            <div className="flex h-14 items-center justify-between px-4 md:px-6">
              {/* Sidebar toggle + logo */}
              <div className="flex items-center gap-2">
                {user && <SidebarTrigger className="mr-1" />}
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
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
                <h1 className="text-lg font-semibold text-foreground">HUST Assistant</h1>
              </div>

              {/* Right side: status + trace link + user menu */}
              <div className="flex items-center gap-3">
                <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <span className="h-2 w-2 rounded-full bg-green-500"></span>
                  Online
                </span>
                <Link
                  to="/trace"
                  className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground border rounded-full px-3 py-1 hover:bg-muted transition-colors"
                  title="Pipeline Trace Debugger"
                >
                  <Activity className="w-3.5 h-3.5" />
                  Trace
                </Link>
                {user && <UserMenu user={user} onLogout={handleLogout} />}
              </div>
            </div>
          </header>

          {/* Chat Area */}
          <div className="flex-1 overflow-hidden">
            <ChatContainer user={user} sessionId={sessionId} />
          </div>
        </main>
      </div>
    </SidebarProvider>
  );
};

export default Index;
