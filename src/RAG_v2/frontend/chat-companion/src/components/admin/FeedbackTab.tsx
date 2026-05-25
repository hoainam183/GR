import { useState, useMemo, useCallback, useEffect } from 'react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from '@/components/ui/dialog';
import EmptyState from './EmptyState';
import { useAdminFetch } from '@/hooks/useAdminFetch';
import { getFeedbackTopics } from '@/services/adminApi';
import { createApiClient, getFeedbackStats, listAllFeedback } from '@rag/shared';
import type { FeedbackResponse, FeedbackStats } from '@rag/shared';
import type { FeedbackTopics } from '@/types/adminStats';
import { clearSession, ensureAccessToken, refreshSession } from '@/services/authSession';
import { ThumbsUp, ThumbsDown, BarChart2, MessageCircle } from 'lucide-react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table';

const CATEGORY_LABELS: Record<string, string> = {
  wrong: 'Sai thông tin',
  incomplete: 'Chưa đầy đủ',
  outdated: 'Thông tin cũ',
};

export default function FeedbackTab() {
  const client = useMemo(
    () => createApiClient({
      baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
      getToken: ensureAccessToken,
      refreshAuth: async () => (await refreshSession()).access_token,
      onUnauthorized: clearSession,
      withCredentials: true,
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
  const [selectedFeedback, setSelectedFeedback] = useState<FeedbackResponse | null>(null);
  const limit = 20;

  // Feedback topics (disliked)
  const { data: topicsData } = useAdminFetch<FeedbackTopics>(
    () => getFeedbackTopics(days),
    [days],
  );

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

  const responseRate = stats
    ? stats.total > 0 ? Math.round((stats.with_comment ?? 0) / stats.total * 100) : 0
    : null;

  if (loading && !stats) {
    return (
      <div className="space-y-4">
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-20 rounded-xl" />
          ))}
        </div>
        <Skeleton className="h-48 rounded-xl" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Controls */}
      <div className="flex flex-wrap items-center gap-3">
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
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-4">
          <div className="rounded-xl border border-border bg-card p-4 text-center shadow-sm">
            <p className="text-2xl font-bold text-foreground">{stats.total}</p>
            <p className="text-xs text-muted-foreground mt-1">Tổng đánh giá</p>
          </div>
          <div className="rounded-xl border border-border bg-card p-4 text-center shadow-sm">
            <p className="text-2xl font-bold text-emerald-600">{stats.up}</p>
            <p className="text-xs text-muted-foreground mt-1">👍 Hữu ích</p>
          </div>
          <div className="rounded-xl border border-border bg-card p-4 text-center shadow-sm">
            <p className="text-2xl font-bold text-red-500">{stats.down}</p>
            <p className="text-xs text-muted-foreground mt-1">👎 Chưa tốt</p>
          </div>
          <div className="rounded-xl border border-border bg-card p-4 text-center shadow-sm">
            <p className="text-2xl font-bold text-primary">{satisfactionRate}%</p>
            <p className="text-xs text-muted-foreground mt-1">Hài lòng</p>
          </div>
          <div className="rounded-xl border border-border bg-card p-4 text-center shadow-sm">
            <p className="text-2xl font-bold text-amber-500">{responseRate ?? 'N/A'}%</p>
            <p className="text-xs text-muted-foreground mt-1">Có comment</p>
          </div>
        </div>
      )}

      {/* Category breakdown */}
      {stats && Object.keys(stats.by_category).length > 0 && (
        <div className="p-4 rounded-xl border border-border bg-card shadow-sm">
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

      {/* Disliked topics table */}
      {topicsData && topicsData.topics.length > 0 && (
        <div className="rounded-xl border border-border bg-card p-4 shadow-sm">
          <p className="text-sm font-semibold mb-3">Chủ đề bị đánh giá thấp</p>
          <div className="max-h-64 overflow-y-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Câu hỏi</TableHead>
                  <TableHead className="w-[100px]">Danh mục</TableHead>
                  <TableHead className="w-[60px] text-right">Số lần</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {topicsData.topics.map((topic, idx) => (
                  <TableRow key={idx}>
                    <TableCell className="text-sm max-w-md truncate">{topic.question}</TableCell>
                    <TableCell>
                      {topic.category && (
                        <Badge variant="secondary" className="text-[10px]">
                          {CATEGORY_LABELS[topic.category] ?? topic.category}
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-right font-medium">{topic.count}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </div>
      )}

      {/* Feedback list */}
      {loading ? (
        <div className="text-muted-foreground text-center py-12">Đang tải...</div>
      ) : feedbacks.length === 0 ? (
        <EmptyState icon={MessageCircle} title="Chưa có feedback" description="Không có feedback nào trong khoảng thời gian này" />
      ) : (
        <>
          <div className="space-y-3">
            {feedbacks.map((fb) => (
              <div
                key={fb.id}
                className="rounded-xl border border-border bg-card p-4 shadow-sm cursor-pointer hover:bg-accent/50 transition-colors"
                onClick={() => setSelectedFeedback(fb)}
              >
                <div className="flex items-start gap-3">
                  <span className={`mt-0.5 shrink-0 ${fb.rating === 'up' ? 'text-emerald-600' : 'text-red-500'}`}>
                    {fb.rating === 'up' ? <ThumbsUp className="h-4 w-4" /> : <ThumbsDown className="h-4 w-4" />}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-foreground line-clamp-2">{fb.question}</p>
                    <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{fb.answer_snapshot}</p>
                    <div className="flex items-center gap-2 mt-2">
                      {fb.category && (
                        <Badge variant="secondary" className="text-[10px]">
                          {CATEGORY_LABELS[fb.category] ?? fb.category}
                        </Badge>
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

      {/* Detail Dialog */}
      <Dialog open={!!selectedFeedback} onOpenChange={() => setSelectedFeedback(null)}>
        <DialogContent className="max-w-lg max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              {selectedFeedback?.rating === 'up' ? (
                <ThumbsUp className="h-5 w-5 text-emerald-600" />
              ) : (
                <ThumbsDown className="h-5 w-5 text-red-500" />
              )}
              Chi tiết feedback
            </DialogTitle>
          </DialogHeader>
          {selectedFeedback && (
            <div className="space-y-4">
              <div>
                <p className="text-xs font-semibold text-muted-foreground mb-1">Câu hỏi</p>
                <p className="text-sm">{selectedFeedback.question}</p>
              </div>
              <div>
                <p className="text-xs font-semibold text-muted-foreground mb-1">Câu trả lời</p>
                <p className="text-sm whitespace-pre-wrap">{selectedFeedback.answer_snapshot}</p>
              </div>
              {selectedFeedback.comment && (
                <div>
                  <p className="text-xs font-semibold text-muted-foreground mb-1">Comment</p>
                  <p className="text-sm italic">"{selectedFeedback.comment}"</p>
                </div>
              )}
              {selectedFeedback.category && (
                <div>
                  <p className="text-xs font-semibold text-muted-foreground mb-1">Phân loại</p>
                  <Badge variant="secondary">
                    {CATEGORY_LABELS[selectedFeedback.category] ?? selectedFeedback.category}
                  </Badge>
                </div>
              )}
              <div className="text-xs text-muted-foreground">
                {new Date(selectedFeedback.created_at).toLocaleString('vi-VN')}
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
