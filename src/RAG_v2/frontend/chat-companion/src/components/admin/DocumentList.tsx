import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import type { DocumentDetail, DocumentStatus } from '@/types/admin';
import { parseUtcDate } from '@/lib/utils';
import { Trash2, Eye } from 'lucide-react';

const STATUS_BADGE: Record<string, { label: string; variant: 'default' | 'secondary' | 'destructive' | 'outline' }> = {
  uploaded: { label: 'Đã upload', variant: 'outline' },
  converting: { label: 'Đang chuyển đổi', variant: 'secondary' },
  converted: { label: 'Đã chuyển đổi', variant: 'default' },
  cleaning: { label: 'Đang làm sạch', variant: 'secondary' },
  cleaned: { label: 'Đã làm sạch', variant: 'default' },
  chunking: { label: 'Đang chia chunk', variant: 'secondary' },
  chunked: { label: 'Đã chia chunk', variant: 'default' },
  embedding: { label: 'Đang nhúng', variant: 'secondary' },
  indexed: { label: 'Đã lưu trữ', variant: 'default' },
  failed: { label: 'Lỗi', variant: 'destructive' },
};

interface DocumentListProps {
  documents: DocumentDetail[];
  loading: boolean;
  total: number;
  page: number;
  limit: number;
  onPageChange: (page: number) => void;
  onView: (id: string) => void;
  onDelete: (id: string) => void;
}

function StatusBadge({ status }: { status: DocumentStatus }) {
  const info = STATUS_BADGE[status] || { label: status, variant: 'outline' as const };
  return <Badge variant={info.variant}>{info.label}</Badge>;
}

export default function DocumentList({
  documents,
  loading,
  total,
  page,
  limit,
  onPageChange,
  onView,
  onDelete,
}: DocumentListProps) {
  const totalPages = Math.max(1, Math.ceil(total / limit));

  if (loading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    );
  }

  if (documents.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
        <p className="text-lg font-medium">Chưa có tài liệu</p>
        <p className="text-sm">Upload tài liệu PDF ở phần trên để bắt đầu</p>
      </div>
    );
  }

  return (
    <div>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Tên file</TableHead>
            <TableHead>Collection</TableHead>
            <TableHead>Trạng thái</TableHead>
            <TableHead>Chunks</TableHead>
            <TableHead>Ngày upload</TableHead>
            <TableHead className="text-right">Thao tác</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {documents.map((doc) => (
            <TableRow key={doc.id}>
              <TableCell className="max-w-[200px] truncate font-medium">{doc.filename}</TableCell>
              <TableCell>
                <Badge variant="outline">{doc.collection}</Badge>
              </TableCell>
              <TableCell>
                <StatusBadge status={doc.status} />
                {doc.error_message && (
                  <p className="mt-1 max-w-[200px] truncate text-xs text-destructive">{doc.error_message}</p>
                )}
              </TableCell>
              <TableCell>{doc.chunk_count ?? '—'}</TableCell>
              <TableCell className="text-sm text-muted-foreground">
                {parseUtcDate(doc.uploaded_at).toLocaleDateString('vi-VN')}
              </TableCell>
              <TableCell className="text-right">
                <div className="flex items-center justify-end gap-1">
                  <Button variant="ghost" size="icon" onClick={() => onView(doc.id)} title="Xem chi tiết">
                    <Eye className="h-4 w-4" />
                  </Button>
                  <Button variant="ghost" size="icon" onClick={() => onDelete(doc.id)} title="Xóa">
                    <Trash2 className="h-4 w-4 text-destructive" />
                  </Button>
                </div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between px-2 py-3">
          <p className="text-sm text-muted-foreground">
            Trang {page}/{totalPages} — {total} tài liệu
          </p>
          <div className="flex gap-1">
            <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>
              Trước
            </Button>
            <Button size="sm" variant="outline" disabled={page >= totalPages} onClick={() => onPageChange(page + 1)}>
              Sau
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
