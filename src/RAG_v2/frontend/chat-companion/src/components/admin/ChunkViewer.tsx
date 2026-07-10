import { useCallback, useEffect, useRef, useState } from 'react';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Textarea } from '@/components/ui/textarea';
import {
  approveChunks,
  deleteDocumentChunk,
  getChunks,
  updateDocumentChunk,
} from '@/services/adminApi';
import type { ChunksResponse, ChunkPreview } from '@/types/admin';
import { Check, Edit3, Save, Trash2, X } from 'lucide-react';
import { toast } from 'sonner';

const CHUNK_PAGE_LIMIT = 20;

function apiErrorMessage(error: unknown, fallback: string): string {
  const response = (error as { response?: { data?: { detail?: unknown } } })?.response;
  return typeof response?.data?.detail === 'string' ? response.data.detail : fallback;
}

interface ChunkViewerProps {
  documentId: string;
  approved: boolean;
  onApproved: () => void;
  onChanged?: () => void;
  /** Optional strategy filter for viewing a specific chunk set */
  strategy?: string;
}

export default function ChunkViewer({
  documentId,
  approved,
  onApproved,
  onChanged,
  strategy,
}: ChunkViewerProps) {
  const [data, setData] = useState<ChunksResponse | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [approving, setApproving] = useState(false);
  const [editingChunkId, setEditingChunkId] = useState<string | null>(null);
  const [draftContent, setDraftContent] = useState('');
  const [savingChunkId, setSavingChunkId] = useState<string | null>(null);
  const [deletingChunkId, setDeletingChunkId] = useState<string | null>(null);
  // Monotonic request id — only the most recent load is allowed to commit its
  // result, so overlapping loads (e.g. page change + reload-after-delete) can't
  // race and paint a stale page.
  const requestIdRef = useRef(0);

  const loadChunks = useCallback(
    // `silent` skips the full-screen skeleton so an in-place refresh (after a
    // delete) doesn't collapse the list height and yank the scroll to the top.
    async (targetPage: number, { silent = false }: { silent?: boolean } = {}) => {
      const requestId = ++requestIdRef.current;
      if (!silent) setLoading(true);
      try {
        const res = await getChunks(documentId, targetPage, CHUNK_PAGE_LIMIT, strategy);
        if (requestId === requestIdRef.current) setData(res);
      } catch {
        if (requestId === requestIdRef.current) toast.error('Không thể tải chunks');
      } finally {
        if (requestId === requestIdRef.current) setLoading(false);
      }
    },
    [documentId, strategy],
  );

  // Reset to the first page whenever the document or strategy changes.
  useEffect(() => {
    setPage(1);
  }, [documentId, strategy]);

  // Load whenever the page (or the document/strategy, via loadChunks) changes.
  // Driving every load from a single effect — including page 1 — is what lets
  // "Trước" navigate back to page 1 (the old code skipped page 1 here).
  useEffect(() => {
    void loadChunks(page);
  }, [loadChunks, page]);

  const beginEdit = (chunk: ChunkPreview) => {
    setEditingChunkId(chunk.chunk_id);
    setDraftContent(chunk.content);
  };

  const cancelEdit = () => {
    setEditingChunkId(null);
    setDraftContent('');
  };

  const handleSave = async (chunk: ChunkPreview) => {
    if (!draftContent.trim()) {
      toast.error('Nội dung chunk không được rỗng');
      return;
    }

    setSavingChunkId(chunk.chunk_id);
    try {
      const updated = await updateDocumentChunk(documentId, chunk.chunk_id, draftContent);
      setData((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          chunks: prev.chunks.map((item) =>
            item.chunk_id === updated.chunk_id ? updated : item,
          ),
        };
      });
      cancelEdit();
      toast.success('Đã lưu chunk');
      onChanged?.();
    } catch (error: unknown) {
      toast.error(apiErrorMessage(error, 'Không thể lưu chunk'));
    } finally {
      setSavingChunkId(null);
    }
  };

  const handleDelete = async (chunk: ChunkPreview) => {
    setDeletingChunkId(chunk.chunk_id);
    try {
      await deleteDocumentChunk(documentId, chunk.chunk_id);
      toast.success('Đã xóa chunk');
      if (data && data.chunks.length === 1 && page > 1) {
        // Removed the last chunk on this page — step back; the page effect reloads.
        setPage(page - 1);
      } else {
        // Refresh the current page in place (no skeleton) so the scroll position
        // is preserved instead of jumping to the top.
        await loadChunks(page, { silent: true });
      }
      onChanged?.();
    } catch (error: unknown) {
      toast.error(apiErrorMessage(error, 'Không thể xóa chunk'));
    } finally {
      setDeletingChunkId(null);
    }
  };

  const handleApprove = async () => {
    setApproving(true);
    try {
      await approveChunks(documentId);
      toast.success('Đã duyệt chunks');
      onApproved();
    } catch (error: unknown) {
      toast.error(apiErrorMessage(error, 'Duyệt thất bại'));
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
        <p>
          Chưa có chunks{strategy ? ` cho strategy "${strategy}"` : ''}. Hãy chạy bước
          &quot;Chia chunk&quot; trước.
        </p>
      </div>
    );
  }

  const totalPages = Math.max(1, Math.ceil(data.total / CHUNK_PAGE_LIMIT));

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-3">
        <Badge variant="outline">Tổng: {data.total} chunks</Badge>
        <Badge variant="outline">Strategy: {data.strategy}</Badge>
        {data.stats.avg_size != null && (
          <Badge variant="outline">TB: {Math.round(data.stats.avg_size)} ký tự</Badge>
        )}
        {data.stats.min_size != null && <Badge variant="outline">Min: {data.stats.min_size}</Badge>}
        {data.stats.max_size != null && <Badge variant="outline">Max: {data.stats.max_size}</Badge>}
        {approved && (
          <Badge variant="default" className="bg-green-600">
            <Check className="mr-1 h-3 w-3" /> Đã duyệt
          </Badge>
        )}
      </div>

      {data.chunks.map((chunk: ChunkPreview) => {
        const isEditing = editingChunkId === chunk.chunk_id;
        const isSaving = savingChunkId === chunk.chunk_id;
        const isDeleting = deletingChunkId === chunk.chunk_id;

        return (
          <Card key={chunk.chunk_id}>
            <CardHeader className="py-2">
              <CardTitle className="flex flex-wrap items-center gap-2 text-sm">
                <Badge variant="secondary">#{chunk.chunk_index}</Badge>
                <span className="text-xs text-muted-foreground">
                  {chunk.content.length} ký tự
                </span>
                {chunk.metadata?.level && (
                  <Badge variant="outline" className="text-xs">
                    {chunk.metadata.level as string}
                  </Badge>
                )}
                {chunk.edited && (
                  <Badge variant="outline" className="text-xs">
                    Đã sửa
                  </Badge>
                )}
                <span className="ml-auto flex gap-1">
                  {isEditing ? (
                    <>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleSave(chunk)}
                        disabled={isSaving}
                      >
                        <Save className="mr-1 h-4 w-4" />
                        {isSaving ? 'Đang lưu' : 'Lưu'}
                      </Button>
                      <Button size="sm" variant="ghost" onClick={cancelEdit} disabled={isSaving}>
                        <X className="mr-1 h-4 w-4" />
                        Hủy
                      </Button>
                    </>
                  ) : (
                    <>
                      <Button size="sm" variant="outline" onClick={() => beginEdit(chunk)}>
                        <Edit3 className="mr-1 h-4 w-4" />
                        Sửa
                      </Button>
                      <AlertDialog>
                        <AlertDialogTrigger asChild>
                          <Button size="sm" variant="outline" disabled={isDeleting}>
                            <Trash2 className="mr-1 h-4 w-4" />
                            Xóa
                          </Button>
                        </AlertDialogTrigger>
                        <AlertDialogContent>
                          <AlertDialogHeader>
                            <AlertDialogTitle>Xóa chunk #{chunk.chunk_index}?</AlertDialogTitle>
                            <AlertDialogDescription>
                              Chunk này sẽ bị xóa khỏi danh sách staged chunks trước khi index.
                              Thao tác này không xóa dữ liệu trong Qdrant hoặc Elasticsearch.
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel>Hủy</AlertDialogCancel>
                            <AlertDialogAction
                              onClick={() => handleDelete(chunk)}
                              disabled={isDeleting}
                            >
                              {isDeleting ? 'Đang xóa' : 'Xóa chunk'}
                            </AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                    </>
                  )}
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent className="py-2">
              {isEditing ? (
                <Textarea
                  value={draftContent}
                  onChange={(event) => setDraftContent(event.target.value)}
                  className="min-h-40 text-xs"
                />
              ) : (
                <pre className="max-h-40 overflow-auto whitespace-pre-wrap text-xs">
                  {chunk.content}
                </pre>
              )}
            </CardContent>
          </Card>
        );
      })}

      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            Trang {page}/{totalPages}
          </p>
          <div className="flex gap-1">
            <Button
              size="sm"
              variant="outline"
              disabled={page <= 1}
              onClick={() => setPage(page - 1)}
            >
              Trước
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={page >= totalPages}
              onClick={() => setPage(page + 1)}
            >
              Sau
            </Button>
          </div>
        </div>
      )}

      {!approved && (
        <Button onClick={handleApprove} disabled={approving}>
          <Check className="mr-1 h-4 w-4" />
          {approving ? 'Đang duyệt...' : 'Duyệt chunks'}
        </Button>
      )}
    </div>
  );
}
