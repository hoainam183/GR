import { useState } from 'react';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import EmptyState from './EmptyState';
import { useAdminFetch } from '@/hooks/useAdminFetch';
import { getAgentAnalytics } from '@/services/adminApi';
import type { AgentAnalytics } from '@/types/adminStats';
import { Bot } from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';

export default function AgentAnalyticsSection() {
  const [days, setDays] = useState(30);

  const { data, loading, error, refetch } = useAdminFetch<AgentAnalytics>(
    () => getAgentAnalytics(days),
    [days],
  );

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-32" />
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-20 rounded-xl" />
          ))}
        </div>
        <Skeleton className="h-48 rounded-xl" />
      </div>
    );
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertDescription className="flex items-center justify-between">
          <span>Không thể tải dữ liệu agent</span>
          <Button variant="outline" size="sm" onClick={refetch}>Thử lại</Button>
        </AlertDescription>
      </Alert>
    );
  }

  if (!data || data.total_calls === 0) {
    return <EmptyState icon={Bot} title="Chưa có dữ liệu agent" description="Agent chưa được sử dụng trong khoảng thời gian này" />;
  }

  return (
    <div className="space-y-6">
      {/* Controls */}
      <div className="flex items-center gap-3">
        <p className="text-sm font-semibold">Agent Analytics</p>
        <Select value={String(days)} onValueChange={(v) => setDays(Number(v))}>
          <SelectTrigger className="w-[120px]"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="7">7 ngày</SelectItem>
            <SelectItem value="30">30 ngày</SelectItem>
            <SelectItem value="90">90 ngày</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="rounded-xl border border-border bg-card p-4 text-center shadow-sm">
          <p className="text-2xl font-bold text-foreground">{data.total_calls}</p>
          <p className="text-xs text-muted-foreground mt-1">Tổng lần gọi</p>
        </div>
        <div className="rounded-xl border border-border bg-card p-4 text-center shadow-sm">
          <p className="text-2xl font-bold text-foreground">{data.avg_iterations}</p>
          <p className="text-xs text-muted-foreground mt-1">Trung bình iterations</p>
        </div>
        <div className="rounded-xl border border-border bg-card p-4 text-center shadow-sm">
          <p className="text-2xl font-bold text-red-500">{data.error_rate}%</p>
          <p className="text-xs text-muted-foreground mt-1">Tỉ lệ lỗi</p>
        </div>
        <div className="rounded-xl border border-border bg-card p-4 text-center shadow-sm">
          <p className="text-2xl font-bold text-blue-500">{data.tavily_triggers}</p>
          <p className="text-xs text-muted-foreground mt-1">Tavily triggers</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Tool Frequency */}
        {data.tool_frequency.length > 0 && (
          <div className="rounded-xl border border-border bg-card p-4 shadow-sm">
            <p className="text-sm font-semibold mb-3">Tần suất tool</p>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={data.tool_frequency} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" />
                <YAxis dataKey="tool" type="category" width={100} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="count" fill="#10b981" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Daily Agent Usage */}
        {data.daily_usage.length > 0 && (
          <div className="rounded-xl border border-border bg-card p-4 shadow-sm">
            <p className="text-sm font-semibold mb-3">Sử dụng agent theo ngày</p>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={data.daily_usage}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                <YAxis allowDecimals={false} />
                <Tooltip />
                <Bar dataKey="count" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  );
}
