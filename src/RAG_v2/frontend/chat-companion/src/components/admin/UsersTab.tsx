import { useState, useCallback } from 'react';
import { Users, Search, UserX, UserCheck as UserCheckIcon } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { Skeleton } from '@/components/ui/skeleton';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import EmptyState from './EmptyState';
import { useAdminFetch } from '@/hooks/useAdminFetch';
import { getAdminUsers, getUserBreakdown, toggleUserStatus } from '@/services/adminApi';
import type { AdminUsersResponse, UserBreakdown } from '@/types/adminStats';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell,
} from 'recharts';

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'];

export default function UsersTab() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [sortBy, setSortBy] = useState('created_at');
  const [order, setOrder] = useState('desc');
  const limit = 20;

  const { data: usersData, loading, error, refetch } = useAdminFetch<AdminUsersResponse>(
    () => getAdminUsers({ page, limit, search, sort_by: sortBy, order }),
    [page, limit, search, sortBy, order],
  );

  const { data: breakdown } = useAdminFetch<UserBreakdown>(
    () => getUserBreakdown(30),
    [],
  );

  const handleSearch = useCallback(() => {
    setSearch(searchInput);
    setPage(1);
  }, [searchInput]);

  const handleToggleStatus = async (userId: string, currentActive: boolean) => {
    const action = currentActive ? 'vô hiệu hóa' : 'kích hoạt';
    if (!window.confirm(`Bạn có chắc muốn ${action} tài khoản này?`)) return;
    try {
      await toggleUserStatus(userId, !currentActive);
      toast.success(`Đã ${action} tài khoản`);
      refetch();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : `Không thể ${action} tài khoản`;
      toast.error(msg);
    }
  };

  if (loading && !usersData) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-64 w-full rounded-xl" />
      </div>
    );
  }

  if (error && !usersData) {
    return (
      <Alert variant="destructive">
        <AlertDescription className="flex items-center justify-between">
          <span>Không thể tải danh sách người dùng</span>
          <Button variant="outline" size="sm" onClick={refetch}>Thử lại</Button>
        </AlertDescription>
      </Alert>
    );
  }

  const roleData = breakdown
    ? Object.entries(breakdown.by_role).map(([role, count]) => ({ name: role, value: count }))
    : [];

  return (
    <div className="space-y-6">
      {/* Charts row */}
      {breakdown && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Role distribution */}
          {roleData.length > 0 && (
            <div className="rounded-xl border border-border bg-card p-4">
              <p className="text-sm font-semibold mb-3">Phân bố vai trò</p>
              <ResponsiveContainer width="100%" height={180}>
                <PieChart>
                  <Pie
                    data={roleData}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    outerRadius={70}
                    label={({ name, value }) => `${name}: ${value}`}
                  >
                    {roleData.map((_, idx) => (
                      <Cell key={idx} fill={COLORS[idx % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </div>
          )}
          {/* Registration trend */}
          {breakdown.registrations.length > 0 && (
            <div className="rounded-xl border border-border bg-card p-4">
              <p className="text-sm font-semibold mb-3">Đăng ký mới (30 ngày)</p>
              <ResponsiveContainer width="100%" height={180}>
                <BarChart data={breakdown.registrations}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                  <YAxis allowDecimals={false} />
                  <Tooltip />
                  <Bar dataKey="count" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      )}

      {/* Search & Sort controls */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex gap-2 flex-1 min-w-[200px]">
          <Input
            placeholder="Tìm theo tên, email, MSSV..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            className="max-w-xs"
          />
          <Button variant="outline" size="icon" onClick={handleSearch}>
            <Search className="h-4 w-4" />
          </Button>
        </div>
        <Select value={sortBy} onValueChange={(v) => { setSortBy(v); setPage(1); }}>
          <SelectTrigger className="w-[140px]"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="created_at">Ngày tạo</SelectItem>
            <SelectItem value="last_login_at">Đăng nhập cuối</SelectItem>
            <SelectItem value="session_count">Số phiên</SelectItem>
            <SelectItem value="query_count">Số câu hỏi</SelectItem>
            <SelectItem value="full_name">Tên</SelectItem>
          </SelectContent>
        </Select>
        <Select value={order} onValueChange={(v) => { setOrder(v); setPage(1); }}>
          <SelectTrigger className="w-[100px]"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="desc">Giảm dần</SelectItem>
            <SelectItem value="asc">Tăng dần</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* User table */}
      {!usersData || usersData.users.length === 0 ? (
        <EmptyState icon={Users} title="Không tìm thấy người dùng" description="Thử thay đổi bộ lọc tìm kiếm" />
      ) : (
        <>
          <div className="rounded-xl border border-border overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Người dùng</TableHead>
                  <TableHead>MSSV</TableHead>
                  <TableHead>Vai trò</TableHead>
                  <TableHead className="text-center">Phiên</TableHead>
                  <TableHead className="text-center">Câu hỏi</TableHead>
                  <TableHead className="text-center">Trạng thái</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {usersData.users.map((user) => (
                  <TableRow key={user._id}>
                    <TableCell>
                      <div>
                        <p className="font-medium text-sm">{user.full_name}</p>
                        <p className="text-xs text-muted-foreground">{user.email || '—'}</p>
                      </div>
                    </TableCell>
                    <TableCell className="text-sm">{user.student_id}</TableCell>
                    <TableCell>
                      <Badge variant={user.role === 'admin' ? 'default' : 'secondary'}>
                        {user.role}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-center text-sm">{user.session_count}</TableCell>
                    <TableCell className="text-center text-sm">{user.query_count}</TableCell>
                    <TableCell className="text-center">
                      <div className="flex items-center justify-center gap-2">
                        {user.is_active ? (
                          <UserCheckIcon className="h-4 w-4 text-emerald-500" />
                        ) : (
                          <UserX className="h-4 w-4 text-red-500" />
                        )}
                        <Switch
                          checked={user.is_active}
                          onCheckedChange={() => handleToggleStatus(user._id, user.is_active)}
                        />
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between">
            <p className="text-xs text-muted-foreground">
              {(page - 1) * limit + 1}–{Math.min(page * limit, usersData.total)} / {usersData.total}
            </p>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>
                Trước
              </Button>
              <Button variant="outline" size="sm" disabled={page * limit >= usersData.total} onClick={() => setPage(p => p + 1)}>
                Sau
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
