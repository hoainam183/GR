import React, { useState, useEffect } from 'react';
import { ThumbsUp, ThumbsDown, Bookmark, Copy, Check } from 'lucide-react';
import { createApiClient, submitFeedback, getFeedback, createBookmark } from '@rag/shared';

const getClient = () => createApiClient({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  getToken: async () => localStorage.getItem('access_token'),
});

interface Props {
  sessionId: string;
  turnId: number;
  content: string;
}

const MessageActionsWeb = ({ sessionId, turnId, content }: Props) => {
  const [feedback, setFeedback] = useState<'up' | 'down' | null>(null);
  const [bookmarked, setBookmarked] = useState(false);
  const [copied, setCopied] = useState(false);
  const client = getClient();

  useEffect(() => {
    getFeedback(client, sessionId, turnId)
      .then((existing) => {
        if (existing?.rating) setFeedback(existing.rating);
      })
      .catch(() => {});
  }, [sessionId, turnId]);

  const handleFeedback = async (rating: 'up' | 'down') => {
    const newRating = feedback === rating ? null : rating;
    setFeedback(newRating);
    if (newRating) {
      try {
        await submitFeedback(client, {
          session_id: sessionId,
          turn_id: turnId,
          rating: newRating,
          category: newRating === 'down' ? 'incomplete' : undefined,
        });
      } catch {
        setFeedback(null);
      }
    }
  };

  const handleBookmark = async () => {
    setBookmarked(true);
    try {
      await createBookmark(client, { session_id: sessionId, turn_id: turnId });
    } catch {
      setBookmarked(false);
    }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="flex items-center gap-1 mt-2 pt-2 border-t border-border/50">
      <button
        onClick={() => handleFeedback('up')}
        className={`p-1.5 rounded-md transition-colors ${feedback === 'up' ? 'bg-emerald-500/10 text-emerald-600' : 'text-muted-foreground hover:text-foreground hover:bg-muted'}`}
        title="Hữu ích"
      >
        <ThumbsUp className="h-3.5 w-3.5" />
      </button>
      <button
        onClick={() => handleFeedback('down')}
        className={`p-1.5 rounded-md transition-colors ${feedback === 'down' ? 'bg-red-500/10 text-red-500' : 'text-muted-foreground hover:text-foreground hover:bg-muted'}`}
        title="Chưa tốt"
      >
        <ThumbsDown className="h-3.5 w-3.5" />
      </button>
      <button
        onClick={handleCopy}
        className={`p-1.5 rounded-md transition-colors ${copied ? 'text-emerald-600' : 'text-muted-foreground hover:text-foreground hover:bg-muted'}`}
        title="Sao chép"
      >
        {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
      </button>
      <button
        onClick={handleBookmark}
        className={`p-1.5 rounded-md transition-colors ${bookmarked ? 'bg-amber-500/10 text-amber-500' : 'text-muted-foreground hover:text-foreground hover:bg-muted'}`}
        title="Lưu"
      >
        <Bookmark className={`h-3.5 w-3.5 ${bookmarked ? 'fill-current' : ''}`} />
      </button>
    </div>
  );
};

export default MessageActionsWeb;
