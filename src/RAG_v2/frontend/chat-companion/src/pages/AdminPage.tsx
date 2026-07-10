import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { toast } from 'sonner';
import FileUploader from '@/components/admin/FileUploader';
import DocumentList from '@/components/admin/DocumentList';
import { listDocuments, deleteDocument } from '@/services/adminApi';
import type { DocumentDetail, DocumentStatus } from '@/types/admin';
import {
  PROCESSING_STATUSES,
  didPipelineFinish,
  notifyPipelineDone,
  requestNotifyPermission,
} from '@/lib/pipelineNotify';
import { ArrowLeft, Bot, ThumbsUp, LayoutDashboard, Users, MessageSquare, FileText, Settings, LogOut, Loader2 } from 'lucide-react';
import { logoutSession } from '@/services/authSession';
import OverviewTab from '@/components/admin/OverviewTab';
import UsersTab from '@/components/admin/UsersTab';
import AnalyticsTab from '@/components/admin/AnalyticsTab';
import SystemTab from '@/components/admin/SystemTab';
import FeedbackTab from '@/components/admin/FeedbackTab';

const STATUS_OPTIONS = [
  { value: '__all__', label: 'Tất cả' },
  { value: 'uploaded', label: 'Đã upload' },
  { value: 'converted', label: 'Đã chuyển đổi' },
  { value: 'cleaned', label: 'Đã làm sạch' },
  { value: 'llm_cleaned', label: 'Đã LLM reformat' },
  { value: 'chunked', label: 'Đã chia chunk' },
  { value: 'indexed', label: 'Đã lưu trữ' },
  { value: 'failed', label: 'Lỗi' },
];

const COLLECTION_OPTIONS = [
  { value: '__all__', label: 'Tất cả' },
  { value: 'ctdt', label: 'ctdt' },
  { value: 'quydinh', label: 'quydinh' },
  { value: 'kehoach', label: 'kehoach' },
  { value: 'stsv', label: 'stsv' },
];

type AdminTab = 'overview' | 'users' | 'documents' | 'analytics' | 'feedback' | 'system';

const TABS: Array<{ id: AdminTab; label: string; icon: React.ElementType }> = [
  { id: 'overview', label: 'Tổng quan', icon: LayoutDashboard },
  { id: 'users', label: 'Người dùng', icon: Users },
  { id: 'documents', label: 'Tài liệu', icon: FileText },
  { id: 'analytics', label: 'Phân tích', icon: MessageSquare },
  { id: 'feedback', label: 'Feedback', icon: ThumbsUp },
  { id: 'system', label: 'Hệ thống', icon: Settings },
];

// Persist the selected tab so a page reload (or coming back from a document
// detail page) restores where the admin was instead of snapping to "Tổng quan".
const ACTIVE_TAB_STORAGE_KEY = 'admin.activeTab';

function loadInitialTab(): AdminTab {
  try {
    const saved = window.localStorage.getItem(ACTIVE_TAB_STORAGE_KEY);
    if (saved && TABS.some((tab) => tab.id === saved)) {
      return saved as AdminTab;
    }
  } catch {
    // localStorage may be unavailable (private mode / SSR) — fall back silently.
  }
  return 'overview';
}

function getAdminApiError(error: unknown) {
  if (!error || typeof error !== 'object' || !('response' in error)) {
    return {};
  }
  const response = (error as {
    response?: { status?: number; data?: { detail?: string } };
  }).response;
  return { detail: response?.data?.detail, status: response?.status };
}

export default function AdminPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<AdminTab>(loadInitialTab);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [documents, setDocuments] = useState<DocumentDetail[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('__all__');
  const [collectionFilter, setCollectionFilter] = useState('__all__');
  const scrollAreaRef = useRef<HTMLElement>(null);
  // Last seen status per document — used to toast/notify on pipeline completion.
  const prevStatusRef = useRef<Map<string, DocumentStatus>>(new Map());
  const limit = 20;

  // Apply a fresh document list, notifying on any processing -> terminal transition.
  const applyDocuments = useCallback((docs: DocumentDetail[]) => {
    const prev = prevStatusRef.current;
    for (const doc of docs) {
      if (!didPipelineFinish(prev.get(doc.id), doc.status)) continue;
      if (doc.status === 'indexed') {
        toast.success(`Đã index xong: ${doc.filename}`);
      } else {
        toast.error(
          `Index thất bại: ${doc.filename}${doc.error_message ? ` — ${doc.error_message}` : ''}`,
        );
      }
      notifyPipelineDone(doc.filename, doc.status);
    }
    prevStatusRef.current = new Map(docs.map((d) => [d.id, d.status]));
    setDocuments(docs);
  }, []);

  const fetchDocuments = useCallback(async () => {
    setLoading(true);
    try {
      const res = await listDocuments(
        page,
        limit,
        statusFilter === '__all__' ? undefined : statusFilter,
        collectionFilter === '__all__' ? undefined : collectionFilter,
      );
      applyDocuments(res.documents);
      setTotal(res.total);
    } catch (err: unknown) {
      if (getAdminApiError(err).status === 403) {
        toast.error('Bạn không có quyền truy cập trang admin');
        navigate('/');
        return;
      }
      toast.error('Không thể tải danh sách tài liệu');
    } finally {
      setLoading(false);
    }
  }, [page, statusFilter, collectionFilter, navigate, applyDocuments]);

  useEffect(() => {
    if (activeTab === 'documents') {
      requestNotifyPermission();
      fetchDocuments();
    }
  }, [fetchDocuments, activeTab]);

  // Auto-poll document list when any document is still processing
  const hasProcessing = documents.some((d) => PROCESSING_STATUSES.includes(d.status));

  useEffect(() => {
    if (activeTab !== 'documents' || !hasProcessing) return;
    const interval = setInterval(async () => {
      try {
        const res = await listDocuments(
          page,
          limit,
          statusFilter === '__all__' ? undefined : statusFilter,
          collectionFilter === '__all__' ? undefined : collectionFilter,
        );
        applyDocuments(res.documents);
        setTotal(res.total);
      } catch {
        // silently ignore errors during background polling
      }
    }, 5000);
    return () => clearInterval(interval);
  }, [activeTab, hasProcessing, page, statusFilter, collectionFilter, applyDocuments]);

  const handleUploaded = () => {
    setPage(1);
    fetchDocuments();
  };

  const handleDelete = async (id: string) => {
    if (!window.confirm('Bạn có chắc muốn xóa tài liệu này? Dữ liệu sẽ bị xóa khỏi tất cả vector stores.')) return;
    try {
      await deleteDocument(id);
      toast.success('Đã xóa tài liệu');
      fetchDocuments();
    } catch (err: unknown) {
      toast.error(getAdminApiError(err).detail || 'Xóa thất bại');
    }
  };

  const handleLogout = async () => {
    setIsLoggingOut(true);
    try {
      await logoutSession();
    } catch (error) {
      console.warn('Logout request failed, clearing local session anyway:', error);
    } finally {
      queryClient.clear();
      navigate('/login', { replace: true });
    }
  };

  const handleView = (id: string) => navigate(`/admin/documents/${id}`);
  const handleTabChange = (tab: AdminTab) => {
    setActiveTab(tab);
    try {
      window.localStorage.setItem(ACTIVE_TAB_STORAGE_KEY, tab);
    } catch {
      // Ignore persistence failures — tab still switches for this session.
    }
    scrollAreaRef.current?.scrollTo({ top: 0 });
  };
  const activeTabInfo = TABS.find((tab) => tab.id === activeTab) ?? TABS[0];
  const ActiveTabIcon = activeTabInfo.icon;

  return (
    <div className="flex h-dvh min-h-0 overflow-hidden bg-background text-foreground">
      <aside className="hidden w-64 shrink-0 flex-col border-r border-border bg-background lg:flex">
        <div className="border-b border-border px-5 py-5">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
              <Bot className="h-5 w-5 text-primary" />
            </div>
            <div className="min-w-0">
              <p className="text-xs font-medium uppercase text-muted-foreground">RAG</p>
              <p className="truncate text-lg font-semibold">Admin Console</p>
            </div>
          </div>
        </div>

        <nav className="scrollbar-thin flex-1 overflow-y-auto px-3 py-4" aria-label="Admin">
          <div className="space-y-1" role="tablist" aria-label="Admin sections">
            {TABS.map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  id={`admin-tab-${tab.id}`}
                  type="button"
                  role="tab"
                  aria-controls="admin-tab-panel"
                  aria-selected={isActive}
                  onClick={() => handleTabChange(tab.id)}
                  className={`flex h-10 w-full items-center gap-3 rounded-lg border px-3 text-left text-sm font-medium transition-colors ${
                    isActive
                      ? 'border-primary/25 bg-primary/10 text-primary shadow-sm'
                      : 'border-transparent text-muted-foreground hover:bg-secondary hover:text-foreground'
                  }`}
                >
                  <Icon className="h-4 w-4 shrink-0" />
                  <span className="truncate">{tab.label}</span>
                </button>
              );
            })}
          </div>
        </nav>

        <div className="space-y-2 border-t border-border p-3">
          <Button variant="outline" className="w-full justify-start gap-2" onClick={() => navigate('/')}>
            <ArrowLeft className="h-4 w-4" />
            Trang chủ
          </Button>
          <Button
            variant="ghost"
            className="w-full justify-start gap-2 text-destructive hover:bg-destructive/10 hover:text-destructive"
            onClick={handleLogout}
            disabled={isLoggingOut}
          >
            {isLoggingOut ? <Loader2 className="h-4 w-4 animate-spin" /> : <LogOut className="h-4 w-4" />}
            Đăng xuất
          </Button>
        </div>
      </aside>

      <section className="flex min-w-0 flex-1 flex-col">
        <header className="shrink-0 border-b border-border bg-background/90 backdrop-blur-sm">
          <div className="flex h-16 items-center justify-between gap-4 px-4 md:px-6 lg:px-8">
            <div className="flex min-w-0 items-center gap-3">
              <Button
                variant="ghost"
                size="icon"
                className="h-9 w-9 shrink-0 lg:hidden"
                onClick={() => navigate('/')}
                title="Trang chủ"
              >
                <ArrowLeft className="h-4 w-4" />
              </Button>
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                <ActiveTabIcon className="h-4 w-4 text-primary" />
              </div>
              <div className="min-w-0">
                <p className="truncate text-xs font-medium uppercase text-muted-foreground">Admin</p>
                <h1 className="truncate text-lg font-semibold sm:text-xl">{activeTabInfo.label}</h1>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <span className="hidden rounded-lg border border-border bg-background px-3 py-2 text-sm text-muted-foreground md:inline-flex">
                Khu vực quản trị
              </span>
              <Button variant="outline" size="sm" className="hidden gap-2 sm:inline-flex" onClick={() => navigate('/')}>
                <ArrowLeft className="h-4 w-4" />
                Trang chủ
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="gap-2 text-destructive hover:bg-destructive/10 hover:text-destructive"
                onClick={handleLogout}
                disabled={isLoggingOut}
                title="Đăng xuất"
              >
                {isLoggingOut ? <Loader2 className="h-4 w-4 animate-spin" /> : <LogOut className="h-4 w-4" />}
                <span className="hidden sm:inline">Đăng xuất</span>
              </Button>
            </div>
          </div>
        </header>

        <nav className="shrink-0 border-b border-border bg-background lg:hidden" aria-label="Admin">
          <div className="scrollbar-thin overflow-x-auto px-4">
            <div className="flex min-w-max gap-1 py-2" role="tablist" aria-label="Admin sections">
              {TABS.map((tab) => {
                const Icon = tab.icon;
                const isActive = activeTab === tab.id;
                return (
                  <button
                    key={tab.id}
                    id={`admin-tab-mobile-${tab.id}`}
                    type="button"
                    role="tab"
                    aria-controls="admin-tab-panel"
                    aria-selected={isActive}
                    onClick={() => handleTabChange(tab.id)}
                    className={`inline-flex h-9 items-center gap-2 whitespace-nowrap rounded-lg border px-3 text-sm font-medium transition-colors ${
                      isActive
                        ? 'border-primary/30 bg-primary/10 text-primary'
                        : 'border-transparent text-muted-foreground hover:bg-secondary hover:text-foreground'
                    }`}
                  >
                    <Icon className="h-4 w-4" />
                    {tab.label}
                  </button>
                );
              })}
            </div>
          </div>
        </nav>

        <main ref={scrollAreaRef} className="scrollbar-thin min-h-0 flex-1 overflow-y-auto overscroll-contain">
          <div
            id="admin-tab-panel"
            role="tabpanel"
            aria-labelledby={`admin-tab-${activeTab}`}
            className="mx-auto w-full max-w-[1440px] px-4 py-5 md:px-6 lg:px-8 lg:py-7"
          >
            {activeTab === 'overview' && <OverviewTab />}

            {activeTab === 'users' && <UsersTab />}

            {activeTab === 'documents' && (
              <>
                <FileUploader onUploaded={handleUploaded} />
                <div className="mt-6 flex flex-wrap items-center gap-3">
                  <Select value={statusFilter} onValueChange={(v) => { setStatusFilter(v); setPage(1); }}>
                    <SelectTrigger className="w-[160px]"><SelectValue placeholder="Trạng thái" /></SelectTrigger>
                    <SelectContent>
                      {STATUS_OPTIONS.map((o) => (
                        <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Select value={collectionFilter} onValueChange={(v) => { setCollectionFilter(v); setPage(1); }}>
                    <SelectTrigger className="w-[140px]"><SelectValue placeholder="Collection" /></SelectTrigger>
                    <SelectContent>
                      {COLLECTION_OPTIONS.map((o) => (
                        <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Button variant="outline" size="sm" onClick={fetchDocuments}>Làm mới</Button>
                </div>
                <div className="mt-4">
                  <DocumentList
                    documents={documents}
                    loading={loading}
                    total={total}
                    page={page}
                    limit={limit}
                    onPageChange={setPage}
                    onView={handleView}
                    onDelete={handleDelete}
                  />
                </div>
              </>
            )}

            {activeTab === 'feedback' && <FeedbackTab />}

            {activeTab === 'analytics' && <AnalyticsTab />}

            {activeTab === 'system' && <SystemTab />}
          </div>
        </main>
      </section>
    </div>
  );
}
