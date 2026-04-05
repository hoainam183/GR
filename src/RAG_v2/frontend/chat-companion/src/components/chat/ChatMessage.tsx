import { useState } from 'react';
import type { Message } from '@/types/chat';
import { cn } from '@/lib/utils';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface ChatMessageProps {
  message: Message;
}

const ChatMessage = ({ message }: ChatMessageProps) => {
  const isUser = message.role === 'user';
  const [showSources, setShowSources] = useState(false);
  const hasSources = message.sources && message.sources.length > 0;

  return (
    <div
      className={cn(
        'flex items-start gap-3 animate-fade-in',
        isUser && 'flex-row-reverse'
      )}
    >
      {/* Avatar */}
      <div
        className={cn(
          'flex h-8 w-8 shrink-0 items-center justify-center rounded-full',
          isUser ? 'bg-secondary' : 'bg-primary'
        )}
      >
        {isUser ? (
          <svg
            className="h-4 w-4 text-secondary-foreground"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
            />
          </svg>
        ) : (
          <svg
            className="h-4 w-4 text-primary-foreground"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 00-6.23-.693L5 14.5m14.8.8l1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0112 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.61L5 14.5"
            />
          </svg>
        )}
      </div>

      {/* Message Bubble */}
      <div
        className={cn(
          'max-w-[75%] rounded-2xl px-4 py-3 shadow-sm',
          isUser
            ? 'rounded-tr-sm bg-chat-user text-foreground'
            : 'rounded-tl-sm bg-chat-assistant border border-border text-foreground'
        )}
      >
        {/* Info Area (Target Collections & Reflected Query) */}
        {!isUser && ((message.targetCollections && message.targetCollections.length > 0) || message.reflectedQuery) && (
          <div className="mb-3 space-y-1 text-[11px] text-muted-foreground bg-muted/30 p-2 rounded-md border border-border/50">
            {message.targetCollections && message.targetCollections.length > 0 && (
              <div className="flex items-center gap-1.5 flex-wrap">
                <span className="font-semibold text-primary/70">Collections:</span>
                {message.targetCollections.map(col => (
                  <span key={col} className="bg-primary/10 text-primary px-1.5 rounded-sm">{col}</span>
                ))}
              </div>
            )}
            {message.reflectedQuery && (
              <div className="flex items-start gap-1.5">
                <span className="font-semibold text-primary/70 shrink-0">Reflected:</span>
                <span className="italic break-words">"{message.reflectedQuery}"</span>
              </div>
            )}
          </div>
        )}

        <div className="text-sm leading-relaxed prose prose-sm max-w-none dark:prose-invert">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              // Styling cho các elements
              p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
              ul: ({ children }) => <ul className="mb-2 ml-4 list-disc space-y-1">{children}</ul>,
              ol: ({ children }) => <ol className="mb-2 ml-4 list-decimal space-y-1">{children}</ol>,
              li: ({ children }) => <li className="ml-2">{children}</li>,
              strong: ({ children }) => <strong className="font-semibold text-foreground">{children}</strong>,
              em: ({ children }) => <em className="italic">{children}</em>,
              h1: ({ children }) => <h1 className="text-lg font-bold mb-2 mt-3 first:mt-0">{children}</h1>,
              h2: ({ children }) => <h2 className="text-base font-bold mb-2 mt-3 first:mt-0">{children}</h2>,
              h3: ({ children }) => <h3 className="text-sm font-bold mb-1 mt-2 first:mt-0">{children}</h3>,
              code: ({ children, className }) => {
                const isInline = !className;
                return isInline ? (
                  <code className="bg-muted px-1 py-0.5 rounded text-xs">{children}</code>
                ) : (
                  <code className={className}>{children}</code>
                );
              },
              pre: ({ children }) => (
                <pre className="bg-muted p-2 rounded my-2 overflow-x-auto text-xs">{children}</pre>
              ),
              blockquote: ({ children }) => (
                <blockquote className="border-l-4 border-primary pl-3 italic my-2">{children}</blockquote>
              ),
              a: ({ children, href }) => (
                <a href={href} className="text-primary hover:underline" target="_blank" rel="noopener noreferrer">
                  {children}
                </a>
              ),
            }}
          >
            {message.content}
          </ReactMarkdown>
        </div>
        <span className="mt-1 block text-[10px] text-muted-foreground opacity-70">
          {message.timestamp.toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
          })}
        </span>

        {/* Sources Button */}
        {hasSources && (
          <button
            onClick={() => setShowSources(!showSources)}
            className="mt-2 flex items-center gap-1 text-xs text-primary hover:underline"
          >
            <svg
              className="h-3 w-3"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
              />
            </svg>
            {showSources ? 'Ẩn' : 'Xem'} nguồn ({message.sources?.length})
          </button>
        )}

        {/* Sources Display */}
        {showSources && hasSources && (
          <div className="mt-3 space-y-2 border-t border-border pt-3">
            {message.sources?.map((source, index) => (
              <div
                key={index}
                className="rounded-lg bg-background/50 p-3 text-xs"
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="font-semibold text-primary">
                    Nguồn {source.rank}
                  </span>
                  <span className="text-muted-foreground">
                    Score: {source.score.toFixed(3)}
                  </span>
                </div>
                <p className="text-muted-foreground line-clamp-3">
                  {source.content}
                </p>
                {source.metadata && Object.keys(source.metadata).length > 0 && (
                  <div className="mt-2 text-[10px] text-muted-foreground">
                    {source.metadata.file_path && (
                      <div>📄 {source.metadata.file_path}</div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default ChatMessage;
