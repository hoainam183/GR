import React, { useMemo, useState, useEffect } from 'react';
import { ThumbsUp, ThumbsDown, Bookmark, Copy, Check } from 'lucide-react';
import {
  createApiClient,
  submitFeedback,
  deleteFeedback,
  getFeedback,
  createBookmark,
  deleteBookmark,
  getBookmarkByTurn,
} from '@rag/shared';
import { toast } from 'sonner';
import { getStoredToken } from '@/services/authStorage';
import { clearSession, ensureAccessToken, refreshSession } from '@/services/authSession';

interface Props {
  sessionId: string;
  turnId: number;
  content: string;
}

const CATEGORIES = [
  { value: 'wrong' as const, label: 'Sai thông tin' },
  { value: 'incomplete' as const, label: 'Chưa đầy đủ' },
  { value: 'outdated' as const, label: 'Thông tin cũ' },
];

const MessageActionsWeb = ({ sessionId, turnId, content }: Props) => {
  const [feedback, setFeedback] = useState<'up' | 'down' | null>(null);
  const [showCategoryPicker, setShowCategoryPicker] = useState(false);
  const [bookmarked, setBookmarked] = useState(false);
  const [bookmarkId, setBookmarkId] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const client = useMemo(
    () =>
      createApiClient({
        baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
        getToken: ensureAccessToken,
        refreshAuth: async () => (await refreshSession()).access_token,
        onUnauthorized: clearSession,
        withCredentials: true,
      }),
    [],
  );

  useEffect(() => {
    if (!getStoredToken()) return;
    getFeedback(client, sessionId, turnId)
      .then((existing) => {
        if (existing?.rating) setFeedback(existing.rating);
      })
      .catch(() => {});
  }, [client, sessionId, turnId]);

  useEffect(() => {
    if (!getStoredToken()) return;
    getBookmarkByTurn(client, sessionId, turnId)
      .then((bm) => {
        if (bm) {
          setBookmarked(true);
          setBookmarkId(bm.id);
        }
      })
      .catch(() => {});
  }, [client, sessionId, turnId]);

  const handleFeedback = async (rating: 'up' | 'down') => {
    if (!getStoredToken()) {
      toast.error('Vui lòng đăng nhập để gửi đánh giá.');
      return;
    }
    const previous = feedback;
    const newRating = previous === rating ? null : rating;
    setFeedback(newRating);
    setShowCategoryPicker(false);

    if (newRating === 'down') {
      setShowCategoryPicker(true);
      return;
    }

    if (newRating === 'up') {
      try {
        await submitFeedback(client, { session_id: sessionId, turn_id: turnId, rating: 'up' });
        toast.success('Cảm ơn bạn đã đánh giá!');
      } catch {
        setFeedback(previous);
        toast.error('Không thể lưu đánh giá. Vui lòng thử lại.');
      }
      return;
    }

    // Toggling an already-selected rating off (newRating === null): clear the
    // persisted feedback too, otherwise a reload re-fetches the old rating
    // and the icon "un-toggles itself" back on.
    try {
      await deleteFeedback(client, sessionId, turnId);
    } catch {
      setFeedback(previous);
      toast.error('Không thể bỏ đánh giá. Vui lòng thử lại.');
    }
  };

  const handleCategorySelect = async (category?: 'wrong' | 'incomplete' | 'outdated') => {
    setShowCategoryPicker(false);
    try {
      await submitFeedback(client, {
        session_id: sessionId,
        turn_id: turnId,
        rating: 'down',
        category,
      });
      toast.success('Cảm ơn bạn đã đánh giá!');
    } catch {
      setFeedback(null);
      toast.error('Không thể lưu đánh giá. Vui lòng thử lại.');
    }
  };

  const handleBookmark = async () => {
    if (!getStoredToken()) {
      toast.error('Vui lòng đăng nhập để lưu câu trả lời.');
      return;
    }
    if (bookmarked && bookmarkId) {
      setBookmarked(false);
      setBookmarkId(null);
      try {
        await deleteBookmark(client, bookmarkId);
      } catch {
        setBookmarked(true);
        setBookmarkId(bookmarkId);
        toast.error('Không thể bỏ lưu. Vui lòng thử lại.');
      }
    } else {
      setBookmarked(true);
      try {
        const bm = await createBookmark(client, { session_id: sessionId, turn_id: turnId });
        setBookmarkId(bm.id);
        toast.success('Đã lưu câu trả lời!');
      } catch {
        setBookmarked(false);
        toast.error('Không thể lưu câu trả lời. Vui lòng thử lại.');
      }
    }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="mt-2 pt-2 border-t border-border/50">
      <div className="flex items-center gap-1">
        <button
          type="button"
          onClick={() => handleFeedback('up')}
          className={`p-1.5 rounded-md transition-colors ${feedback === 'up' ? 'bg-emerald-500/10 text-emerald-600' : 'text-muted-foreground hover:text-foreground hover:bg-muted'}`}
          title="Hữu ích"
        >
          <ThumbsUp className="h-3.5 w-3.5" />
        </button>
        <button
          type="button"
          onClick={() => handleFeedback('down')}
          className={`p-1.5 rounded-md transition-colors ${feedback === 'down' ? 'bg-red-500/10 text-red-500' : 'text-muted-foreground hover:text-foreground hover:bg-muted'}`}
          title="Chưa tốt"
        >
          <ThumbsDown className="h-3.5 w-3.5" />
        </button>
        <button
          type="button"
          onClick={handleCopy}
          className={`p-1.5 rounded-md transition-colors ${copied ? 'text-emerald-600' : 'text-muted-foreground hover:text-foreground hover:bg-muted'}`}
          title="Sao chép"
        >
          {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
        </button>
        <button
          type="button"
          onClick={handleBookmark}
          className={`p-1.5 rounded-md transition-colors ${bookmarked ? 'bg-amber-500/10 text-amber-500' : 'text-muted-foreground hover:text-foreground hover:bg-muted'}`}
          title={bookmarked ? 'Bỏ lưu' : 'Lưu'}
        >
          <Bookmark className={`h-3.5 w-3.5 ${bookmarked ? 'fill-current' : ''}`} />
        </button>
      </div>

      {showCategoryPicker && (
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          <span className="text-[11px] text-muted-foreground">Lý do:</span>
          {CATEGORIES.map((opt) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => handleCategorySelect(opt.value)}
              className="px-2 py-0.5 text-[11px] rounded-full border border-border hover:bg-muted transition-colors"
            >
              {opt.label}
            </button>
          ))}
          <button
            type="button"
            onClick={() => handleCategorySelect(undefined)}
            className="px-2 py-0.5 text-[11px] rounded-full border border-border text-muted-foreground hover:bg-muted transition-colors"
          >
            Bỏ qua
          </button>
        </div>
      )}
    </div>
  );
};

export default MessageActionsWeb;
