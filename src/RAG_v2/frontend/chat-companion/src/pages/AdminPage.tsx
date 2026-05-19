import { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { toast } from 'sonner';
import FileUploader from '@/components/admin/FileUploader';
import DocumentList from '@/components/admin/DocumentList';
import { listDocuments, deleteDocument } from '@/services/adminApi';
import type { DocumentDetail } from '@/types/admin';
import { ArrowLeft, ThumbsUp, ThumbsDown, BarChart2 } from 'lucide-react';
import { createApiClient, getFeedbackStats, listAllFeedback } from '@rag/shared';
import type { FeedbackResponse, FeedbackStats } from '@rag/shared';
import { getStoredToken } from '@/services/authStorage';

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

const CATEGORY_LABELS: Record<string, string> = {
  wrong: 'Sai thông tin',
  incomplete: 'Chưa đầy đủ',
  outdated: 'Thông tin cũ',
};

type AdminTab = 'documents' | 'feedback';

function FeedbackTab() {
  const client = useMemo(
    () => createApiClient({
      baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
      getToken: async () => getStoredToken(),
    }),
    [],
  );
  const [stats, setStats] = useState<FeedbackStats | null>(null);
  const [feedbacks, setFeedbacks] = useState<FeedbackResponse[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [ratingFilter, setRatingFilter] = useState<'all' | 'up' | 'down'>('all');
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(true);
  const limit = 20;

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [statsRes, listRes] = await Promise.all([
        getFeedbackStats(client, days),
        listAllFeedback(client, {
          rating: ratingFilter === 'all' ? undefined : ratingFilter,
          days,
          page,
          limit,
        }),
      ]);
      setStats(statsRes);
      setFeedbacks(listRes.feedbacks);
      setTotal(listRes.total);
    } catch {
      toast.error('Không thể tải dữ liệu feedback');
    } finally {
      setLoading(false);
    }
  }, [client, days, ratingFilter, page]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const satisfactionRate = stats
    ? stats.total > 0 ? Math.round((stats.up / stats.total) * 100) : 0
    : null;

  return (
    <div>
      {/* Controls */}
      <div className="flex flex-wrap items-center gap-3 mb-6">
        <Select value={String(days)} onValueChange={(v) => { setDays(Number(v)); setPage(1); }}>
          <SelectTrigger className="w-[130px]"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="7">7 ngày</SelectItem>
            <SelectItem value="30">30 ngày</SelectItem>
            <SelectItem value="90">90 ngày</SelectItem>
            <SelectItem value="365">1 năm</SelectItem>
          </SelectContent>
        </Select>
        <Select value={ratingFilter} onValueChange={(v) => { setRatingFilter(v as 'all' | 'up' | 'down'); setPage(1); }}>
          <SelectTrigger className="w-[130px]"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Tất cả</SelectItem>
            <SelectItem value="up">👍 Hữu ích</SelectItem>
            <SelectItem value="down">👎 Chưa tốt</SelectItem>
          </SelectContent>
        </Select>
        <Button variant="outline" size="sm" onClick={fetchData}>Làm mới</Button>
      </div>

      {/* Stats cards */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
          <div className="rounded-xl border border-border bg-card p-4 text-center">
            <p className="text-2xl font-bold text-foreground">{stats.total}</p>
            <p className="text-xs text-muted-foreground mt-1">Tổng đánh giá</p>
          </div>
          <div className="rounded-xl border border-border bg-card p-4 text-center">
            <p className="text-2xl font-bold text-emerald-600">{stats.up}</p>
            <p className="text-xs text-muted-foreground mt-1">👍 Hữu ích</p>
          </div>
          <div className="rounded-xl border border-border bg-card p-4 text-center">
            <p className="text-2xl font-bold text-red-500">{stats.down}</p>
            <p className="text-xs text-muted-foreground mt-1">👎 Chưa tốt</p>
          </div>
          <div className="rounded-xl border border-border bg-card p-4 text-center">
            <p className="text-2xl font-bold text-primary">{satisfactionRate}%</p>
            <p className="text-xs text-muted-foreground mt-1">Hài lòng</p>
          </div>
        </div>
      )}

      {/* Category breakdown */}
      {stats && Object.keys(stats.by_category).length > 0 && (
        <div className="mb-6 p-4 rounded-xl border border-border bg-card">
          <p className="text-sm font-semibold text-foreground mb-3 flex items-center gap-2">
            <BarChart2 className="h-4 w-4" /> Phân loại lý do 👎
          </p>
          <div className="flex flex-wrap gap-3">
            {Object.entries(stats.by_category).map(([cat, count]) => (
              <div key={cat} className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-muted text-sm">
                <span className="font-medium">{CATEGORY_LABELS[cat] ?? cat}</span>
                <span className="text-muted-foreground">({count})</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Feedback list */}
      {loading ? (
        <div className="text-muted-foreground text-center py-12">Đang tải...</div>
      ) : feedbacks.length === 0 ? (
        <div className="text-muted-foreground text-center py-12">Không có feedback nào</div>
      ) : (
        <>
          <div className="space-y-3">
            {feedbacks.map((fb) => (
              <div key={fb.id} className="rounded-xl border border-border bg-card p-4">
                <div className="flex items-start gap-3">
                  <span className={`mt-0.5 shrink-0 ${fb.rating === 'up' ? 'text-emerald-600' : 'text-red-500'}`}>
                    {fb.rating === 'up' ? <ThumbsUp className="h-4 w-4" /> : <ThumbsDown className="h-4 w-4" />}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-foreground line-clamp-2">{fb.question}</p>
                    <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{fb.answer_snapshot}</p>
                    <div className="flex items-center gap-2 mt-2">
                      {fb.category && (
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-red-500/10 text-red-600 font-medium">
                          {CATEGORY_LABELS[fb.category] ?? fb.category}
                        </span>
                      )}
                      {fb.comment && (
                        <span className="text-[10px] text-muted-foreground italic">"{fb.comment}"</span>
                      )}
                      <span className="text-[10px] text-muted-foreground ml-auto">
                        {new Date(fb.created_at).toLocaleDateString('vi-VN')}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
          {/* Pagination */}
          <div className="flex items-center justify-between mt-4">
            <p className="text-xs text-muted-foreground">
              {(page - 1) * limit + 1}–{Math.min(page * limit, total)} / {total}
            </p>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>
                Trước
              </Button>
              <Button variant="outline" size="sm" disabled={page * limit >= total} onClick={() => setPage(p => p + 1)}>
                Sau
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

export default function AdminPage() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<AdminTab>('documents');
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
    <div className="mx-auto max-w-5xl px-4 py-6">
      <div className="mb-6 flex items-center gap-3">
        <Button variant="ghost" size="icon" onClick={() => navigate('/chat')}>
          <ArrowLeft className="h-5 w-5" />
        </Button>
        <h1 className="text-2xl font-bold">Admin</h1>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 border-b border-border">
        {[
          { id: 'documents' as AdminTab, label: 'Tài liệu' },
          { id: 'feedback' as AdminTab, label: 'Feedback' },
        ].map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
              activeTab === tab.id
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

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
    </div>
  );
}
