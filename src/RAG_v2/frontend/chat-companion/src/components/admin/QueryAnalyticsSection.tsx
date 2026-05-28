import { useState } from 'react';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import EmptyState from './EmptyState';
import { useAdminFetch } from '@/hooks/useAdminFetch';
import { getQueryAnalytics } from '@/services/adminApi';
import type { QueryAnalytics } from '@/types/adminStats';
import { BarChart3, AlertCircle } from 'lucide-react';
import {
  AreaChart, Area, BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table';

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16'];

export default function QueryAnalyticsSection() {
  const [days, setDays] = useState(30);

  const { data, loading, error, refetch } = useAdminFetch<QueryAnalytics>(
    () => getQueryAnalytics(days),
    [days],
  );

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-32" />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <Skeleton className="h-64 rounded-xl" />
          <Skeleton className="h-64 rounded-xl" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertDescription className="flex items-center justify-between">
          <span>Không thể tải dữ liệu phân tích câu hỏi</span>
          <Button variant="outline" size="sm" onClick={refetch}>Thử lại</Button>
        </AlertDescription>
      </Alert>
    );
  }

  if (!data || data.volume.length === 0) {
    return <EmptyState icon={BarChart3} title="Chưa có dữ liệu câu hỏi" description="Hệ thống chưa ghi nhận câu hỏi nào" />;
  }

  const totalQueries = data.volume.reduce((sum, d) => sum + d.count, 0);
  const avgLatency = data.latency.length
    ? Math.round(data.latency.reduce((sum, d) => sum + (d.avg_ms ?? 0), 0) / data.latency.length)
    : 0;
  const queriesPerDay = data.volume.length ? Math.round(totalQueries / data.volume.length) : 0;

  return (
    <div className="space-y-6">
      {/* KPI Summary */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="rounded-lg border border-border bg-card p-3 text-center">
          <p className="text-xs text-muted-foreground">Tổng queries</p>
          <p className="text-xl font-semibold text-foreground">{totalQueries.toLocaleString()}</p>
        </div>
        <div className="rounded-lg border border-border bg-card p-3 text-center">
          <p className="text-xs text-muted-foreground">Avg Latency</p>
          <p className="text-xl font-semibold text-foreground">{avgLatency}ms</p>
        </div>
        <div className="rounded-lg border border-border bg-card p-3 text-center">
          <p className="text-xs text-muted-foreground">Queries/ngày</p>
          <p className="text-xl font-semibold text-foreground">{queriesPerDay}</p>
        </div>
        <div className="rounded-lg border border-border bg-card p-3 text-center">
          <p className="text-xs text-muted-foreground">Error Rate</p>
          <p className={`text-xl font-semibold ${data.error_count > 0 ? 'text-destructive' : 'text-emerald-600'}`}>
            {totalQueries > 0 ? ((data.error_count / totalQueries) * 100).toFixed(1) : '0'}%
          </p>
        </div>
      </div>

      {/* Controls */}
      <div className="flex items-center gap-3">
        <Select value={String(days)} onValueChange={(v) => setDays(Number(v))}>
          <SelectTrigger className="w-[120px]"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="7">7 ngày</SelectItem>
            <SelectItem value="30">30 ngày</SelectItem>
            <SelectItem value="90">90 ngày</SelectItem>
          </SelectContent>
        </Select>
        {data.error_count > 0 && (
          <Badge variant="destructive" className="flex items-center gap-1">
            <AlertCircle className="h-3 w-3" />
            {data.error_count} lỗi
          </Badge>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Query Volume */}
        <div className="rounded-xl border border-border bg-card p-4 shadow-sm">
          <p className="text-sm font-semibold mb-3">Lượng câu hỏi theo ngày</p>
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={data.volume}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} />
              <YAxis allowDecimals={false} />
              <Tooltip />
              <Area type="monotone" dataKey="count" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.2} />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Latency Trend */}
        <div className="rounded-xl border border-border bg-card p-4 shadow-sm">
          <p className="text-sm font-semibold mb-3">Độ trễ (ms)</p>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={data.latency}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} />
              <YAxis />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="avg_ms" stroke="#10b981" name="Trung bình" dot={false} />
              {data.latency.some(l => l.p95_ms != null) && (
                <Line type="monotone" dataKey="p95_ms" stroke="#f59e0b" name="P95" dot={false} strokeDasharray="5 5" />
              )}
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Route distribution */}
        <div className="rounded-xl border border-border bg-card p-4 shadow-sm">
          <p className="text-sm font-semibold mb-3">Phân bố theo route</p>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie
                data={data.by_route}
                dataKey="count"
                nameKey="route"
                cx="50%"
                cy="50%"
                outerRadius={80}
                label={({ route, count }) => `${route}: ${count}`}
              >
                {data.by_route.map((_, idx) => (
                  <Cell key={idx} fill={COLORS[idx % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* Mode distribution */}
        <div className="rounded-xl border border-border bg-card p-4 shadow-sm">
          <p className="text-sm font-semibold mb-3">Phân bố theo mode</p>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={data.by_mode} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" />
              <YAxis dataKey="mode" type="category" width={80} tick={{ fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="count" fill="#8b5cf6" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Top Questions */}
      {data.top_questions.length > 0 && (
        <div className="rounded-xl border border-border bg-card p-4 shadow-sm">
          <p className="text-sm font-semibold mb-3">Câu hỏi phổ biến</p>
          <div className="max-h-80 overflow-y-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[50px]">#</TableHead>
                  <TableHead>Câu hỏi</TableHead>
                  <TableHead className="w-[80px] text-right">Số lần</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.top_questions.map((q, idx) => (
                  <TableRow key={idx}>
                    <TableCell className="text-muted-foreground">{idx + 1}</TableCell>
                    <TableCell className="text-sm max-w-md truncate">{q.question}</TableCell>
                    <TableCell className="text-right font-medium">{q.count}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </div>
      )}
    </div>
  );
}
