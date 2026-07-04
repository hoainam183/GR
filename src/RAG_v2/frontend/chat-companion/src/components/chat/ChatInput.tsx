import { useState, useRef, useEffect } from 'react';
import { Send, Square } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface ChatInputProps {
  onSend: (message: string) => void;
  /** True while a response is streaming/thinking — the Send button becomes Stop. */
  isBusy?: boolean;
  /** Aborts the in-flight response (Stop button / Escape). */
  onStop?: () => void;
}

const PLACEHOLDERS = [
  'Hỏi về học phí, lịch thi, quy chế…',
  'Điều kiện xét tốt nghiệp là gì?',
  'Các loại học bổng hiện có?',
  'Thủ tục đăng ký học lại?',
];

const ChatInput = ({ onSend, isBusy = false, onStop }: ChatInputProps) => {
  const [input, setInput] = useState('');
  const [placeholderIndex, setPlaceholderIndex] = useState(0);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Rotate the placeholder hint while the field is empty (DESIGN §5.5).
  useEffect(() => {
    if (input) return;
    const id = setInterval(() => {
      setPlaceholderIndex((prev) => (prev + 1) % PLACEHOLDERS.length);
    }, 4000);
    return () => clearInterval(id);
  }, [input]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // Allow composing while busy, but block sending until the response finishes.
    if (input.trim() && !isBusy) {
      onSend(input.trim());
      setInput('');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape' && isBusy) {
      e.preventDefault();
      onStop?.();
      return;
    }
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = `${Math.min(textarea.scrollHeight, 120)}px`;
    }
  }, [input]);

  return (
    <form
      onSubmit={handleSubmit}
      className="flex items-end gap-2 rounded-2xl border border-border bg-chat-input p-2 shadow-lg transition-shadow focus-within:shadow-xl focus-within:ring-2 focus-within:ring-ring/20"
    >
      <textarea
        ref={textareaRef}
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={PLACEHOLDERS[placeholderIndex]}
        aria-label="Nhập câu hỏi"
        rows={1}
        className="max-h-[120px] min-h-[44px] flex-1 resize-none bg-transparent px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none"
      />
      {isBusy ? (
        <Button
          type="button"
          size="icon"
          onClick={onStop}
          className="h-10 w-10 shrink-0 rounded-full transition-all hover:scale-105"
        >
          <Square className="h-4 w-4 fill-current" />
          <span className="sr-only">Dừng phản hồi</span>
        </Button>
      ) : (
        <Button
          type="submit"
          size="icon"
          disabled={!input.trim()}
          className="h-10 w-10 shrink-0 rounded-full transition-all hover:scale-105 disabled:opacity-40"
        >
          <Send className="h-4 w-4" />
          <span className="sr-only">Gửi tin nhắn</span>
        </Button>
      )}
    </form>
  );
};

export default ChatInput;
