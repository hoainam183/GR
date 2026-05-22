import { Users, MessageSquare, Activity, ThumbsUp, BarChart3, UserCheck } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import EmptyState from './EmptyState';
import { useAdminFetch } from '@/hooks/useAdminFetch';
import { getOverviewStats } from '@/services/adminApi';
import type { OverviewStats } from '@/types/adminStats';

const TONE_STYLES = {
  sky: 'bg-sky-100 text-sky-700',
  emerald: 'bg-emerald-100 text-emerald-700',
  amber: 'bg-amber-100 text-amber-700',
  rose: 'bg-rose-100 text-rose-700',
  violet: 'bg-violet-100 text-violet-700',
  slate: 'bg-slate-200 text-slate-700',
};

function StatCard({
  label,
  value,
  icon: Icon,
  helper,
  tone,
}: {
  label: string;
  value: string | number;
  icon: React.ElementType;
  helper: string;
  tone: keyof typeof TONE_STYLES;
}) {
  return (
    <article className="rounded-lg border border-border bg-card p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-medium text-muted-foreground">{label}</p>
          <p className="mt-2 truncate text-2xl font-semibold text-foreground">{value}</p>
        </div>
        <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${TONE_STYLES[tone]}`}>
          <Icon className="h-4 w-4" />
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
      <div className="space-y-4">
        <Skeleton className="h-28 rounded-lg" />
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
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
    <div className="space-y-6">
      <section className="border-b border-border pb-5">
        <p className="text-xs font-medium uppercase text-primary">Tổng quan</p>
        <h2 className="mt-2 text-2xl font-semibold tracking-normal text-foreground md:text-3xl">
          Dashboard quản trị
        </h2>
        <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
          Theo dõi người dùng, phiên chat, truy vấn và phản hồi mới nhất của hệ thống.
        </p>
      </section>

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3" aria-label="Admin metrics">
        <StatCard
          label="Tổng người dùng"
          value={data.total_users.toLocaleString()}
          icon={Users}
          helper="Tài khoản trong hệ thống"
          tone="sky"
        />
        <StatCard
          label="Phiên chat"
          value={data.total_sessions.toLocaleString()}
          icon={MessageSquare}
          helper="Lượt hội thoại đã tạo"
          tone="emerald"
        />
        <StatCard
          label="Câu hỏi"
          value={data.total_queries.toLocaleString()}
          icon={Activity}
          helper="Truy vấn đã xử lý"
          tone="amber"
        />
        <StatCard
          label="Hoạt động 7 ngày"
          value={data.active_users_7d.toLocaleString()}
          icon={UserCheck}
          helper="Người dùng quay lại gần đây"
          tone="violet"
        />
        <StatCard
          label="Feedback"
          value={data.total_feedback.toLocaleString()}
          icon={ThumbsUp}
          helper="Phản hồi cho câu trả lời"
          tone="rose"
        />
        <StatCard
          label="Hài lòng"
          value={satisfaction}
          icon={BarChart3}
          helper="Tỷ lệ feedback hữu ích"
          tone="slate"
        />
      </section>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.3fr)_minmax(20rem,1fr)]">
        <section className="rounded-lg border border-border bg-card p-5 shadow-sm">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-start gap-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-secondary">
                <BarChart3 className="h-4 w-4 text-foreground" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-foreground">Nhịp sử dụng</h3>
                <p className="mt-1 text-xs text-muted-foreground">Tỷ lệ hoạt động và chất lượng phản hồi.</p>
              </div>
            </div>
            <span className="rounded-lg bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700">
              {activeShare}% active
            </span>
          </div>

          <div className="mt-5 space-y-4">
            <div>
              <div className="mb-2 flex items-center justify-between gap-3 text-xs">
                <span className="text-muted-foreground">Người dùng active 7 ngày</span>
                <span className="font-medium text-foreground">{data.active_users_7d.toLocaleString()}</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-secondary">
                <div className="h-full rounded-full bg-sky-500" style={{ width: `${Math.min(activeShare, 100)}%` }} />
              </div>
            </div>
            <div>
              <div className="mb-2 flex items-center justify-between gap-3 text-xs">
                <span className="text-muted-foreground">Feedback hữu ích</span>
                <span className="font-medium text-foreground">{satisfaction}</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-secondary">
                <div
                  className="h-full rounded-full bg-emerald-500"
                  style={{ width: `${Math.min(data.satisfaction_rate ?? 0, 100)}%` }}
                />
              </div>
            </div>
          </div>
        </section>

        <aside className="rounded-lg border border-border bg-card p-5 shadow-sm">
          <h3 className="text-sm font-semibold text-foreground">Tóm tắt vận hành</h3>
          <dl className="mt-4 divide-y divide-border rounded-lg border border-border bg-background">
            <div className="px-4 py-3">
              <dt className="text-xs text-muted-foreground">Câu hỏi mỗi phiên</dt>
              <dd className="mt-1 text-lg font-semibold text-foreground">{queriesPerSession}</dd>
            </div>
            <div className="px-4 py-3">
              <dt className="text-xs text-muted-foreground">Tổng feedback</dt>
              <dd className="mt-1 text-lg font-semibold text-foreground">{data.total_feedback.toLocaleString()}</dd>
            </div>
            <div className="px-4 py-3">
              <dt className="text-xs text-muted-foreground">Phiên chat đã ghi nhận</dt>
              <dd className="mt-1 text-lg font-semibold text-foreground">{data.total_sessions.toLocaleString()}</dd>
            </div>
          </dl>
        </aside>
      </div>
    </div>
  );
}
