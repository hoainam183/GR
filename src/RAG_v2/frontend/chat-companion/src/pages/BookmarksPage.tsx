import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Navigate } from 'react-router-dom';
import { createApiClient, listBookmarks, listBookmarkFolders, deleteBookmark } from '@rag/shared';
import type { Bookmark, BookmarkFolder } from '@rag/shared';

const getClient = () => createApiClient({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  getToken: async () => localStorage.getItem('access_token'),
});

const BookmarksPage = () => {
  const token = localStorage.getItem('access_token');
  if (!token) return <Navigate to="/login" replace />;

  const client = getClient();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [activeFolder, setActiveFolder] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const { data: foldersData } = useQuery({
    queryKey: ['bookmark-folders'],
    queryFn: () => listBookmarkFolders(client),
  });
  const folders: BookmarkFolder[] = foldersData ?? [];

  const { data, isLoading } = useQuery({
    queryKey: ['bookmarks', activeFolder, search],
    queryFn: () => listBookmarks(client, {
      folder: activeFolder || undefined,
      q: search || undefined,
    }),
  });
  const bookmarks = data?.bookmarks ?? [];

  const deleteMut = useMutation({
    mutationFn: (id: string) => deleteBookmark(client, id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bookmarks'] });
      queryClient.invalidateQueries({ queryKey: ['bookmark-folders'] });
    },
  });

  return (
    <div className="min-h-screen bg-background p-6 max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold text-foreground mb-6">Đã lưu</h1>

      {/* Search + Filter */}
      <div className="flex flex-col sm:flex-row gap-3 mb-4">
        <input
          type="text"
          placeholder="Tìm kiếm..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="flex-1 px-3 py-2 rounded-lg border border-border bg-muted text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-primary"
        />
        <div className="flex gap-2 flex-wrap">
          <button
            onClick={() => setActiveFolder(null)}
            className={`px-3 py-1.5 rounded-full text-xs font-medium border ${!activeFolder ? 'bg-primary text-primary-foreground border-primary' : 'bg-muted text-muted-foreground border-border'}`}
          >
            Tất cả
          </button>
          {folders.map((f) => (
            <button
              key={f.name}
              onClick={() => setActiveFolder(activeFolder === f.name ? null : f.name)}
              className={`px-3 py-1.5 rounded-full text-xs font-medium border ${activeFolder === f.name ? 'bg-primary text-primary-foreground border-primary' : 'bg-muted text-muted-foreground border-border'}`}
            >
              {f.name} ({f.count})
            </button>
          ))}
        </div>
      </div>

      {/* Bookmarks List */}
      {isLoading ? (
        <div className="text-muted-foreground text-center py-12">Đang tải...</div>
      ) : bookmarks.length === 0 ? (
        <div className="text-muted-foreground text-center py-12">
          {search ? 'Không tìm thấy kết quả' : 'Chưa có mục đã lưu'}
        </div>
      ) : (
        <div className="space-y-3">
          {bookmarks.map((bm) => (
            <div key={bm.id} className="rounded-xl border border-border bg-card p-4">
              <div className="flex items-start justify-between gap-3">
                <button
                  className="flex-1 text-left"
                  onClick={() => setExpandedId(expandedId === bm.id ? null : bm.id)}
                >
                  <p className="text-sm font-semibold text-foreground line-clamp-2">{bm.question}</p>
                  <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{bm.answer_preview}</p>
                  <div className="flex items-center gap-2 mt-2">
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-600 font-medium">
                      {bm.folder}
                    </span>
                  </div>
                </button>
                <button
                  onClick={() => deleteMut.mutate(bm.id)}
                  className="shrink-0 p-1.5 rounded-md hover:bg-destructive/10 text-muted-foreground hover:text-destructive"
                  title="Xóa"
                >
                  ✕
                </button>
              </div>
              {expandedId === bm.id && (
                <div className="mt-3 pt-3 border-t border-border text-sm text-foreground whitespace-pre-wrap">
                  {bm.answer_snapshot}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default BookmarksPage;
