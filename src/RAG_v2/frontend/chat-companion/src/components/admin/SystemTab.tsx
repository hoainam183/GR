import { useState, useEffect, useRef } from 'react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Progress } from '@/components/ui/progress';
import EmptyState from './EmptyState';
import { useAdminFetch } from '@/hooks/useAdminFetch';
import { getSystemStats, triggerCrawler, getCrawlerStatus } from '@/services/adminApi';
import type { SystemStats, CrawlerStatus } from '@/types/adminStats';
import { Settings, Loader2, PlayCircle, CheckCircle2, XCircle } from 'lucide-react';
import {
  BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'];

export default function SystemTab() {
  const { data, loading, error, refetch } = useAdminFetch<SystemStats>(
    () => getSystemStats(),
    [],
  );

  const [crawlerStatus, setCrawlerStatus] = useState<CrawlerStatus | null>(null);
  const [crawlTarget, setCrawlTarget] = useState('all');
  const [triggering, setTriggering] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Fetch crawler status
  useEffect(() => {
    getCrawlerStatus().then(setCrawlerStatus).catch(() => {});
  }, []);

  // Poll while crawling
  useEffect(() => {
    if (crawlerStatus?.is_running) {
      pollRef.current = setInterval(async () => {
        try {
          const status = await getCrawlerStatus();
          setCrawlerStatus(status);
          if (!status.is_running) {
            if (pollRef.current) clearInterval(pollRef.current);
            toast.success('Crawl hoàn tất');
          }
        } catch { /* ignore */ }
      }, 5000);
    }
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [crawlerStatus?.is_running]);

  const handleTrigger = async () => {
    setTriggering(true);
    try {
      await triggerCrawler(crawlTarget);
      toast.success('Đã khởi động crawl');
      const status = await getCrawlerStatus();
      setCrawlerStatus(status);
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { status?: number; data?: { detail?: string } } };
        if (axiosErr.response?.status === 429) {
          toast.error(axiosErr.response.data?.detail || 'Vui lòng đợi trước khi trigger lại');
        } else if (axiosErr.response?.status === 409) {
          toast.error('Crawl đang chạy');
        } else {
          toast.error(axiosErr.response?.data?.detail || 'Không thể trigger crawl');
        }
      } else {
        toast.error('Không thể trigger crawl');
      }
    } finally {
      setTriggering(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-16 rounded-xl" />
          ))}
        </div>
        <Skeleton className="h-64 rounded-xl" />
      </div>
    );
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertDescription className="flex items-center justify-between">
          <span>Không thể tải thông tin hệ thống</span>
          <Button variant="outline" size="sm" onClick={refetch}>Thử lại</Button>
        </AlertDescription>
      </Alert>
    );
  }

  if (!data) {
    return <EmptyState icon={Settings} title="Không có dữ liệu hệ thống" />;
  }

  const docStatusData = Object.entries(data.documents_by_status).map(([status, count]) => ({ name: status, value: count }));
  const docCollData = Object.entries(data.documents_by_collection).map(([coll, count]) => ({ name: coll, value: count }));

  return (
    <div className="space-y-6">
      {/* Config grid */}
      <div>
        <p className="text-sm font-semibold mb-3">Cấu hình hệ thống</p>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {Object.entries(data.config).map(([key, val]) => (
            <div key={key} className="rounded-lg border border-border bg-card px-3 py-2 flex items-center justify-between">
              <span className="text-xs text-muted-foreground">{key.replace(/_/g, ' ')}</span>
              <Badge variant={val ? 'default' : 'secondary'} className="text-[10px]">
                {val ? 'ON' : 'OFF'}
              </Badge>
            </div>
          ))}
        </div>
      </div>

      {/* Service status */}
      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-lg border border-border bg-card px-3 py-2 flex items-center justify-between">
          <span className="text-xs">MongoDB</span>
          <Badge variant={data.mongo_status === 'ok' ? 'default' : 'destructive'}>
            {data.mongo_status}
          </Badge>
        </div>
        <div className="rounded-lg border border-border bg-card px-3 py-2 flex items-center justify-between">
          <span className="text-xs">Redis</span>
          <Badge variant={data.redis_status === 'ok' ? 'default' : 'secondary'}>
            {data.redis_status}
          </Badge>
        </div>
      </div>

      {/* Documents charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {docStatusData.length > 0 && (
          <div className="rounded-xl border border-border bg-card p-4">
            <p className="text-sm font-semibold mb-3">Tài liệu theo trạng thái</p>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={docStatusData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" tick={{ fontSize: 10 }} />
                <YAxis allowDecimals={false} />
                <Tooltip />
                <Bar dataKey="value" fill="#3b82f6" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {docCollData.length > 0 && (
          <div className="rounded-xl border border-border bg-card p-4">
            <p className="text-sm font-semibold mb-3">Tài liệu theo collection</p>
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie
                  data={docCollData}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  outerRadius={70}
                  label={({ name, value }) => `${name}: ${value}`}
                >
                  {docCollData.map((_, idx) => (
                    <Cell key={idx} fill={COLORS[idx % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Crawler management */}
      <div className="rounded-xl border border-border bg-card p-5">
        <p className="text-sm font-semibold mb-4">Crawler</p>
        <div className="flex flex-wrap items-center gap-3 mb-4">
          <Select value={crawlTarget} onValueChange={setCrawlTarget}>
            <SelectTrigger className="w-[140px]"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Tất cả</SelectItem>
              <SelectItem value="kehoach">Kế hoạch</SelectItem>
              <SelectItem value="quydinh">Quy định</SelectItem>
            </SelectContent>
          </Select>
          <Button
            onClick={handleTrigger}
            disabled={triggering || crawlerStatus?.is_running}
            className="gap-2"
          >
            {crawlerStatus?.is_running ? (
              <><Loader2 className="h-4 w-4 animate-spin" /> Đang chạy...</>
            ) : (
              <><PlayCircle className="h-4 w-4" /> Chạy Crawl</>
            )}
          </Button>
          {data.crawler.enabled && (
            <span className="text-xs text-muted-foreground">
              Lịch tự động: {String(data.crawler.schedule_hour).padStart(2, '0')}:{String(data.crawler.schedule_minute).padStart(2, '0')} hàng ngày
            </span>
          )}
        </div>

        {/* Crawler status */}
        {crawlerStatus?.is_running && (
          <div className="flex items-center gap-2 p-3 rounded-lg bg-blue-50 dark:bg-blue-950 mb-3">
            <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
            <span className="text-sm text-blue-700 dark:text-blue-300">Crawler đang chạy...</span>
          </div>
        )}

        {crawlerStatus?.last_result && !crawlerStatus.is_running && (
          <div className={`flex items-center gap-2 p-3 rounded-lg ${
            crawlerStatus.last_result.status === 'success'
              ? 'bg-emerald-50 dark:bg-emerald-950'
              : 'bg-red-50 dark:bg-red-950'
          }`}>
            {crawlerStatus.last_result.status === 'success' ? (
              <CheckCircle2 className="h-4 w-4 text-emerald-500" />
            ) : (
              <XCircle className="h-4 w-4 text-red-500" />
            )}
            <div className="text-sm">
              <span className="font-medium">
                {crawlerStatus.last_result.status === 'success' ? 'Thành công' : 'Lỗi'}
              </span>
              {crawlerStatus.last_result.error && (
                <span className="ml-2 text-muted-foreground">{crawlerStatus.last_result.error}</span>
              )}
              {crawlerStatus.last_result.completed_at && (
                <span className="ml-2 text-xs text-muted-foreground">
                  {new Date(crawlerStatus.last_result.completed_at).toLocaleString('vi-VN')}
                </span>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
