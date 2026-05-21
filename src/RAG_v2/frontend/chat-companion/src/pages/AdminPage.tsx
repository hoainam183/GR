import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { toast } from 'sonner';
import FileUploader from '@/components/admin/FileUploader';
import DocumentList from '@/components/admin/DocumentList';
import { listDocuments, deleteDocument } from '@/services/adminApi';
import type { DocumentDetail } from '@/types/admin';
import { ArrowLeft, ThumbsUp, LayoutDashboard, Users, MessageSquare, FileText, Settings } from 'lucide-react';
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

export default function AdminPage() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<AdminTab>('overview');
  const [documents, setDocuments] = useState<DocumentDetail[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('__all__');
  const [collectionFilter, setCollectionFilter] = useState('__all__');
  const limit = 20;

  const fetchDocuments = useCallback(async () => {
    setLoading(true);
    try {
      const res = await listDocuments(
        page,
        limit,
        statusFilter === '__all__' ? undefined : statusFilter,
        collectionFilter === '__all__' ? undefined : collectionFilter,
      );
      setDocuments(res.documents);
      setTotal(res.total);
    } catch (err: any) {
      if (err?.response?.status === 403) {
        toast.error('Bạn không có quyền truy cập trang admin');
        navigate('/chat');
        return;
      }
      toast.error('Không thể tải danh sách tài liệu');
    } finally {
      setLoading(false);
    }
  }, [page, statusFilter, collectionFilter, navigate]);

  useEffect(() => {
    if (activeTab === 'documents') fetchDocuments();
  }, [fetchDocuments, activeTab]);

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
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Xóa thất bại');
    }
  };

  const handleView = (id: string) => navigate(`/admin/documents/${id}`);

  return (
    <div className="mx-auto max-w-6xl px-4 py-6">
      <div className="mb-6 flex items-center gap-3">
        <Button variant="ghost" size="icon" onClick={() => navigate('/chat')}>
          <ArrowLeft className="h-5 w-5" />
        </Button>
        <h1 className="text-2xl font-bold">Admin</h1>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 border-b border-border overflow-x-auto">
        {TABS.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-1.5 px-3 py-2 text-sm font-medium border-b-2 -mb-px transition-colors whitespace-nowrap ${
                activeTab === tab.id
                  ? 'border-primary text-primary'
                  : 'border-transparent text-muted-foreground hover:text-foreground'
              }`}
            >
              <Icon className="h-4 w-4" />
              {tab.label}
            </button>
          );
        })}
      </div>

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
  );
}
