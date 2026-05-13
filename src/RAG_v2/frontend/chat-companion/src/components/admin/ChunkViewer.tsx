import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { getChunks, approveChunks } from '@/services/adminApi';
import type { ChunksResponse, ChunkPreview } from '@/types/admin';
import { toast } from 'sonner';
import { Check } from 'lucide-react';

interface ChunkViewerProps {
  documentId: string;
  approved: boolean;
  onApproved: () => void;
  /** Optional strategy filter for viewing a specific chunk set */
  strategy?: string;
}

export default function ChunkViewer({ documentId, approved, onApproved, strategy }: ChunkViewerProps) {
  const [data, setData] = useState<ChunksResponse | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [approving, setApproving] = useState(false);
  const limit = 20;

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setPage(1); // Reset page when strategy changes
    getChunks(documentId, 1, limit, strategy)
      .then((res) => { if (!cancelled) setData(res); })
      .catch(() => { if (!cancelled) toast.error('Không thể tải chunks'); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [documentId, strategy]);

  // Separate effect for page changes (don't reset page)
  useEffect(() => {
    if (page === 1) return; // Already handled by the strategy effect
    let cancelled = false;
    setLoading(true);
    getChunks(documentId, page, limit, strategy)
      .then((res) => { if (!cancelled) setData(res); })
      .catch(() => { if (!cancelled) toast.error('Không thể tải chunks'); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [documentId, page, strategy]);

  const handleApprove = async () => {
    setApproving(true);
    try {
      await approveChunks(documentId);
      toast.success('Đã duyệt chunks');
      onApproved();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Duyệt thất bại');
    } finally {
      setApproving(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-24 w-full" />
        ))}
      </div>
    );
  }

  if (!data || data.chunks.length === 0) {
    return (
      <div className="py-8 text-center text-muted-foreground">
        <p>Chưa có chunks{strategy ? ` cho strategy "${strategy}"` : ''}. Hãy chạy bước &quot;Chia chunk&quot; trước.</p>
      </div>
    );
  }

  const totalPages = Math.max(1, Math.ceil(data.total / limit));

  return (
    <div className="space-y-4">
      {/* Stats */}
      <div className="flex flex-wrap gap-3">
        <Badge variant="outline">Tổng: {data.total} chunks</Badge>
        <Badge variant="outline">Strategy: {data.strategy}</Badge>
        {data.stats.avg_size != null && <Badge variant="outline">TB: {Math.round(data.stats.avg_size)} ký tự</Badge>}
        {data.stats.min_size != null && <Badge variant="outline">Min: {data.stats.min_size}</Badge>}
        {data.stats.max_size != null && <Badge variant="outline">Max: {data.stats.max_size}</Badge>}
        {approved && (
          <Badge variant="default" className="bg-green-600">
            <Check className="mr-1 h-3 w-3" /> Đã duyệt
          </Badge>
        )}
      </div>

      {/* Chunks */}
      {data.chunks.map((chunk: ChunkPreview) => (
        <Card key={chunk.chunk_id}>
          <CardHeader className="py-2">
            <CardTitle className="flex items-center gap-2 text-sm">
              <Badge variant="secondary">#{chunk.chunk_index}</Badge>
              <span className="text-xs text-muted-foreground">{chunk.content.length} ký tự</span>
              {chunk.metadata?.level && (
                <Badge variant="outline" className="text-xs">
                  {chunk.metadata.level as string}
                </Badge>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent className="py-2">
            <pre className="max-h-40 overflow-auto whitespace-pre-wrap text-xs">{chunk.content}</pre>
          </CardContent>
        </Card>
      ))}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">Trang {page}/{totalPages}</p>
          <div className="flex gap-1">
            <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage(page - 1)}>Trước</Button>
            <Button size="sm" variant="outline" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>Sau</Button>
          </div>
        </div>
      )}

      {/* Approve button */}
      {!approved && (
        <Button onClick={handleApprove} disabled={approving}>
          <Check className="mr-1 h-4 w-4" />
          {approving ? 'Đang duyệt…' : 'Duyệt chunks'}
        </Button>
      )}
    </div>
  );
}
