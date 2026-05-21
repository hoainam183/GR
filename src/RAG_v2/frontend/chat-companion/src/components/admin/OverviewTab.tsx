import { Users, MessageSquare, Activity, ThumbsUp, BarChart3, UserCheck } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import EmptyState from './EmptyState';
import { useAdminFetch } from '@/hooks/useAdminFetch';
import { getOverviewStats } from '@/services/adminApi';
import type { OverviewStats } from '@/types/adminStats';

function StatCard({
  label,
  value,
  icon: Icon,
  helper,
}: {
  label: string;
  value: string | number;
  icon: React.ElementType;
  helper: string;
}) {
  return (
    <article className="rounded-lg border border-border bg-card p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-medium text-muted-foreground">{label}</p>
          <p className="mt-2 truncate text-2xl font-semibold text-foreground">{value}</p>
        </div>
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10">
          <Icon className="h-4 w-4 text-primary" />
        </div>
      </div>
      <p className="mt-3 text-xs text-muted-foreground">{helper}</p>
    </article>
  );
}

export default function OverviewTab() {
  const { data, loading, error, refetch } = useAdminFetch<OverviewStats>(
    () => getOverviewStats(),
    [],
  );

  if (loading) {
    return (
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-32 rounded-lg" />
          ))}
        </div>
        <Skeleton className="h-72 rounded-lg" />
      </div>
    );
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertDescription className="flex items-center justify-between">
          <span>Không thể tải dữ liệu tổng quan</span>
          <Button variant="outline" size="sm" onClick={refetch}>Thử lại</Button>
        </AlertDescription>
      </Alert>
    );
  }

  if (!data) {
    return (
      <EmptyState
        icon={BarChart3}
        title="Chưa có dữ liệu"
        description="Hệ thống chưa ghi nhận hoạt động nào"
      />
    );
  }

  const activeShare = data.total_users
    ? Math.round((data.active_users_7d / data.total_users) * 100)
    : 0;
  const queriesPerSession = data.total_sessions
    ? (data.total_queries / data.total_sessions).toFixed(1)
    : '0';
  const satisfaction = data.satisfaction_rate != null ? `${data.satisfaction_rate}%` : 'N/A';

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_20rem]">
      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3" aria-label="Admin metrics">
        <StatCard
          label="Tổng người dùng"
          value={data.total_users.toLocaleString()}
          icon={Users}
          helper="Tài khoản trong hệ thống"
        />
        <StatCard
          label="Phiên chat"
          value={data.total_sessions.toLocaleString()}
          icon={MessageSquare}
          helper="Lượt hội thoại đã tạo"
        />
        <StatCard
          label="Câu hỏi"
          value={data.total_queries.toLocaleString()}
          icon={Activity}
          helper="Truy vấn đã xử lý"
        />
        <StatCard
          label="Hoạt động 7 ngày"
          value={data.active_users_7d.toLocaleString()}
          icon={UserCheck}
          helper="Người dùng quay lại gần đây"
        />
        <StatCard
          label="Feedback"
          value={data.total_feedback.toLocaleString()}
          icon={ThumbsUp}
          helper="Phản hồi cho câu trả lời"
        />
        <StatCard
          label="Hài lòng"
          value={satisfaction}
          icon={BarChart3}
          helper="Tỉ lệ feedback hữu ích"
        />
      </section>

      <aside className="rounded-lg border border-border bg-card p-5 shadow-sm">
        <div className="flex items-start gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-secondary">
            <BarChart3 className="h-4 w-4 text-foreground" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-foreground">Nhịp sử dụng</h2>
            <p className="mt-1 text-xs text-muted-foreground">Tổng hợp từ các chỉ số chính.</p>
          </div>
        </div>

        <dl className="mt-5 divide-y divide-border rounded-lg border border-border bg-background">
          <div className="px-4 py-3">
            <dt className="text-xs text-muted-foreground">Người dùng active 7 ngày</dt>
            <dd className="mt-1 flex items-baseline justify-between gap-3">
              <span className="text-lg font-semibold text-foreground">
                {data.active_users_7d.toLocaleString()}
              </span>
              <span className="text-xs font-medium text-primary">{activeShare}%</span>
            </dd>
          </div>
          <div className="px-4 py-3">
            <dt className="text-xs text-muted-foreground">Câu hỏi mỗi phiên</dt>
            <dd className="mt-1 text-lg font-semibold text-foreground">{queriesPerSession}</dd>
          </div>
          <div className="px-4 py-3">
            <dt className="text-xs text-muted-foreground">Feedback hữu ích</dt>
            <dd className="mt-1 text-lg font-semibold text-foreground">{satisfaction}</dd>
          </div>
        </dl>
      </aside>
    </div>
  );
}
