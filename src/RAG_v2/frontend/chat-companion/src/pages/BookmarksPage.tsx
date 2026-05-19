import React, { useState } from 'react';
import ReactMarkdown, { type Components } from 'react-markdown';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import remarkGfm from 'remark-gfm';
import {
  ArrowLeft,
  Bookmark,
  BookmarkX,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  Search,
  Trash2,
} from 'lucide-react';
import { createApiClient, listBookmarks, listBookmarkFolders, deleteBookmark } from '@rag/shared';
import type { Bookmark as BookmarkType, BookmarkFolder } from '@rag/shared';
import { getStoredToken } from '@/services/authStorage';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';

const bookmarkMarkdownComponents: Components = {
  p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
  ul: ({ children }) => <ul className="mb-2 ml-4 list-disc space-y-1">{children}</ul>,
  ol: ({ children }) => <ol className="mb-2 ml-4 list-decimal space-y-1">{children}</ol>,
  li: ({ children }) => <li className="ml-2">{children}</li>,
  strong: ({ children }) => <strong className="font-semibold text-foreground">{children}</strong>,
  em: ({ children }) => <em className="italic">{children}</em>,
  h1: ({ children }) => <h1 className="mb-2 mt-3 text-lg font-bold first:mt-0">{children}</h1>,
  h2: ({ children }) => <h2 className="mb-2 mt-3 text-base font-bold first:mt-0">{children}</h2>,
  h3: ({ children }) => <h3 className="mb-1 mt-2 text-sm font-bold first:mt-0">{children}</h3>,
  code: ({ children, className }) => {
    const isInline = !className;
    return isInline ? (
      <code className="rounded bg-muted px-1 py-0.5 text-xs">{children}</code>
    ) : (
      <code className={className}>{children}</code>
    );
  },
  pre: ({ children }) => (
    <pre className="my-2 overflow-x-auto rounded bg-muted p-2 text-xs">{children}</pre>
  ),
  blockquote: ({ children }) => (
    <blockquote className="my-2 border-l-4 border-primary pl-3 italic">{children}</blockquote>
  ),
  a: ({ children, href }) => (
    <a href={href} className="text-primary hover:underline" target="_blank" rel="noopener noreferrer">
      {children}
    </a>
  ),
};

const bookmarkPreviewMarkdownComponents: Components = {
  ...bookmarkMarkdownComponents,
  p: ({ children }) => <span>{children}</span>,
  h1: ({ children }) => <span>{children}</span>,
  h2: ({ children }) => <span>{children}</span>,
  h3: ({ children }) => <span>{children}</span>,
  h4: ({ children }) => <span>{children}</span>,
  h5: ({ children }) => <span>{children}</span>,
  h6: ({ children }) => <span>{children}</span>,
  ul: ({ children }) => <span>{children}</span>,
  ol: ({ children }) => <span>{children}</span>,
  li: ({ children }) => <span>{children} </span>,
  pre: ({ children }) => <span>{children}</span>,
  blockquote: ({ children }) => <span>{children}</span>,
  a: ({ children }) => <span>{children}</span>,
  table: ({ children }) => <span>{children}</span>,
  thead: ({ children }) => <span>{children}</span>,
  tbody: ({ children }) => <span>{children}</span>,
  tr: ({ children }) => <span>{children} </span>,
  th: ({ children }) => <span>{children} </span>,
  td: ({ children }) => <span>{children} </span>,
  img: ({ alt }) => <span>{alt}</span>,
};

// ─── Skeleton loading card ─────────────────────────────────────────────────
function BookmarkSkeleton() {
  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-sm space-y-3">
      <Skeleton className="h-4 w-3/4" />
      <Skeleton className="h-3 w-full" />
      <Skeleton className="h-3 w-2/3" />
      <div className="flex items-center justify-between pt-1">
        <Skeleton className="h-5 w-16 rounded-full" />
        <div className="flex gap-2">
          <Skeleton className="h-7 w-7 rounded-md" />
          <Skeleton className="h-7 w-7 rounded-md" />
        </div>
      </div>
    </div>
  );
}

// ─── Empty state ───────────────────────────────────────────────────────────
function EmptyState({ hasSearch }: { hasSearch: boolean }) {
  const navigate = useNavigate();
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-muted">
        {hasSearch ? (
          <Search className="h-7 w-7 text-muted-foreground" />
        ) : (
          <BookmarkX className="h-7 w-7 text-muted-foreground" />
        )}
      </div>
      <p className="text-base font-semibold text-foreground">
        {hasSearch ? 'Không tìm thấy kết quả' : 'Chưa có mục đã lưu'}
      </p>
      <p className="mt-1 text-sm text-muted-foreground max-w-xs">
        {hasSearch
          ? 'Thử tìm kiếm với từ khoá khác'
          : 'Nhấn vào biểu tượng 🔖 dưới câu trả lời để lưu lại'}
      </p>
      {!hasSearch && (
        <Button
          variant="default"
          size="sm"
          className="mt-6"
          onClick={() => navigate('/chat')}
        >
          Bắt đầu trò chuyện
        </Button>
      )}
    </div>
  );
}

// ─── Single bookmark card ──────────────────────────────────────────────────
function BookmarkCard({
  bm,
  isExpanded,
  onToggleExpand,
  onNavigate,
  onDelete,
  isDeleting,
}: {
  bm: BookmarkType;
  isExpanded: boolean;
  onToggleExpand: () => void;
  onNavigate: () => void;
  onDelete: () => void;
  isDeleting: boolean;
}) {
  return (
    <div className="rounded-xl border border-border bg-card shadow-sm overflow-hidden transition-shadow hover:shadow-md">
      {/* Card header — clickable area */}
      <button
        type="button"
        onClick={onToggleExpand}
        className="w-full text-left px-5 pt-5 pb-4 focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset"
      >
        <p className="text-sm font-semibold text-foreground line-clamp-2 leading-snug">
          {bm.question}
        </p>
        <div className="mt-1.5 text-xs text-muted-foreground line-clamp-2 leading-relaxed">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={bookmarkPreviewMarkdownComponents}
          >
            {bm.answer_preview}
          </ReactMarkdown>
        </div>
      </button>

      {/* Expanded answer */}
      {isExpanded && (
        <div className="prose prose-sm mx-5 mb-4 max-w-none rounded-lg border border-border/50 bg-muted/60 px-4 py-3 text-sm leading-relaxed text-foreground dark:prose-invert">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={bookmarkMarkdownComponents}
          >
            {bm.answer_snapshot}
          </ReactMarkdown>
        </div>
      )}

      {/* Card footer */}
      <div className="flex items-center justify-between gap-3 px-5 pb-4">
        <div className="flex items-center gap-2 min-w-0">
          <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/10 px-2.5 py-0.5 text-[11px] font-medium text-amber-600 shrink-0">
            <Bookmark className="h-3 w-3" />
            {bm.folder}
          </span>
          {bm.note && (
            <span className="text-[11px] text-muted-foreground italic truncate">
              {bm.note}
            </span>
          )}
        </div>

        <div className="flex items-center gap-1 shrink-0">
          {/* Expand/collapse */}
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 text-muted-foreground hover:text-foreground"
            onClick={onToggleExpand}
            title={isExpanded ? 'Thu gọn' : 'Xem đầy đủ'}
          >
            {isExpanded ? (
              <ChevronUp className="h-3.5 w-3.5" />
            ) : (
              <ChevronDown className="h-3.5 w-3.5" />
            )}
          </Button>
          {/* Jump to chat */}
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 text-muted-foreground hover:text-foreground"
            onClick={onNavigate}
            title="Xem cuộc trò chuyện gốc"
          >
            <ExternalLink className="h-3.5 w-3.5" />
          </Button>
          {/* Delete */}
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 text-muted-foreground hover:text-destructive"
            onClick={onDelete}
            disabled={isDeleting}
            title="Xóa"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    </div>
  );
}

// ─── Main page ─────────────────────────────────────────────────────────────
const BookmarksPage = () => {
  const isAuthenticated = Boolean(getStoredToken());
  const navigate = useNavigate();
  const client = React.useMemo(
    () =>
      createApiClient({
        baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
        getToken: async () => getStoredToken(),
      }),
    [],
  );
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [activeFolder, setActiveFolder] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const { data: foldersData } = useQuery({
    queryKey: ['bookmark-folders'],
    queryFn: () => listBookmarkFolders(client),
    enabled: isAuthenticated,
  });
  const folders: BookmarkFolder[] = foldersData ?? [];

  const { data, isLoading } = useQuery({
    queryKey: ['bookmarks', activeFolder, search],
    queryFn: () =>
      listBookmarks(client, {
        folder: activeFolder || undefined,
        q: search || undefined,
      }),
    enabled: isAuthenticated,
  });
  const bookmarks = data?.bookmarks ?? [];
  const total = data?.total ?? 0;

  const deleteMut = useMutation({
    mutationFn: (id: string) => deleteBookmark(client, id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bookmarks'] });
      queryClient.invalidateQueries({ queryKey: ['bookmark-folders'] });
    },
  });

  if (!isAuthenticated) {
    navigate('/login', { replace: true });
    return null;
  }

  return (
    <div className="flex h-dvh flex-col bg-background">
      {/* ── Sticky header ── */}
      <header className="shrink-0 border-b border-border bg-background/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="flex h-14 items-center gap-3 px-4 max-w-3xl mx-auto">
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 shrink-0"
            onClick={() => navigate('/chat')}
            title="Quay lại chat"
          >
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-amber-500/10 shrink-0">
            <Bookmark className="h-3.5 w-3.5 text-amber-600" />
          </div>
          <h1 className="text-base font-semibold text-foreground truncate flex-1">
            Đã lưu
            {total > 0 && (
              <span className="ml-2 text-xs font-normal text-muted-foreground">
                ({total})
              </span>
            )}
          </h1>
        </div>
      </header>

      {/* ── Scrollable content ── */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-4 py-6 space-y-4">

          {/* Search */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
            <Input
              type="text"
              placeholder="Tìm theo câu hỏi hoặc câu trả lời..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9"
            />
          </div>

          {/* Folder filter pills */}
          {folders.length > 0 && (
            <div className="flex gap-2 flex-wrap">
              <button
                type="button"
                onClick={() => setActiveFolder(null)}
                className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                  !activeFolder
                    ? 'bg-primary text-primary-foreground border-primary'
                    : 'bg-background text-muted-foreground border-border hover:text-foreground hover:border-foreground/30'
                }`}
              >
                Tất cả
              </button>
              {folders.map((f) => (
                <button
                  key={f.name}
                  type="button"
                  onClick={() => setActiveFolder(activeFolder === f.name ? null : f.name)}
                  className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                    activeFolder === f.name
                      ? 'bg-primary text-primary-foreground border-primary'
                      : 'bg-background text-muted-foreground border-border hover:text-foreground hover:border-foreground/30'
                  }`}
                >
                  {f.name}
                  <span className={`text-[10px] ${activeFolder === f.name ? 'text-primary-foreground/70' : 'text-muted-foreground'}`}>
                    {f.count}
                  </span>
                </button>
              ))}
            </div>
          )}

          {/* Content */}
          {isLoading ? (
            <div className="space-y-3">
              {[...Array(4)].map((_, i) => <BookmarkSkeleton key={i} />)}
            </div>
          ) : bookmarks.length === 0 ? (
            <EmptyState hasSearch={Boolean(search)} />
          ) : (
            <div className="space-y-3">
              {bookmarks.map((bm) => (
                <BookmarkCard
                  key={bm.id}
                  bm={bm}
                  isExpanded={expandedId === bm.id}
                  onToggleExpand={() =>
                    setExpandedId(expandedId === bm.id ? null : bm.id)
                  }
                  onNavigate={() => navigate(`/chat/${bm.session_id}`)}
                  onDelete={() => deleteMut.mutate(bm.id)}
                  isDeleting={deleteMut.isPending}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default BookmarksPage;
