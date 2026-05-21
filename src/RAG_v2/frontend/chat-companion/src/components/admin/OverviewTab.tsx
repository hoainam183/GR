import { Users, MessageSquare, Activity, ThumbsUp, BarChart3, UserCheck } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import EmptyState from './EmptyState';
import { useAdminFetch } from '@/hooks/useAdminFetch';
import { getOverviewStats } from '@/services/adminApi';
import type { OverviewStats } from '@/types/adminStats';

function StatCard({ label, value, icon: Icon, color }: {
  label: string;
  value: string | number;
  icon: React.ElementType;
  color: string;
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="flex items-center gap-3">
        <div className={`rounded-lg p-2.5 ${color}`}>
          <Icon className="h-5 w-5 text-white" />
        </div>
        <div>
          <p className="text-2xl font-bold text-foreground">{value}</p>
          <p className="text-xs text-muted-foreground mt-0.5">{label}</p>
        </div>
      </div>
    </div>
  );
}

export default function OverviewTab() {
  const { data, loading, error, refetch } = useAdminFetch<OverviewStats>(
    () => getOverviewStats(),
    [],
  );

  if (loading) {
    return (
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-24 rounded-xl" />
        ))}
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
    return <EmptyState icon={BarChart3} title="Chưa có dữ liệu" description="Hệ thống chưa ghi nhận hoạt động nào" />;
  }

  return (
    <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
      <StatCard
        label="Tổng người dùng"
        value={data.total_users.toLocaleString()}
        icon={Users}
        color="bg-blue-500"
      />
      <StatCard
        label="Tổng phiên chat"
        value={data.total_sessions.toLocaleString()}
        icon={MessageSquare}
        color="bg-emerald-500"
      />
      <StatCard
        label="Tổng câu hỏi"
        value={data.total_queries.toLocaleString()}
        icon={Activity}
        color="bg-purple-500"
      />
      <StatCard
        label="Hoạt động 7 ngày"
        value={data.active_users_7d.toLocaleString()}
        icon={UserCheck}
        color="bg-amber-500"
      />
      <StatCard
        label="Tổng feedback"
        value={data.total_feedback.toLocaleString()}
        icon={ThumbsUp}
        color="bg-pink-500"
      />
      <StatCard
        label="Tỉ lệ hài lòng"
        value={data.satisfaction_rate != null ? `${data.satisfaction_rate}%` : 'N/A'}
        icon={BarChart3}
        color="bg-indigo-500"
      />
    </div>
  );
}
