import React, { useState } from 'react';
import type { Message } from '@/types/chat';
import { cn } from '@/lib/utils';
import ReactMarkdown, { Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { DocRow } from '../trace/DocRow';

interface ChatMessageProps {
  message: Message;
}

const markdownComponents: Components = {
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
};

const ChatMessage = ({ message }: ChatMessageProps) => {
  const isUser = message.role === 'user';
  const [showSources, setShowSources] = useState(false);
  const hasSources = message.sources && message.sources.length > 0;

  const modeLabel = message.mode;
  const routeLabel = message.route;
  const iterationCount = message.iterations ?? message.agentTrace?.iterations;
  const toolsUsed =
    message.toolsUsed ?? message.agentTrace?.tool_names_sequence ?? [];
  const agentLatencyMs =
    typeof message.agentTrace?.latency_ms === 'number'
      ? message.agentTrace.latency_ms
      : undefined;
  const debugError =
    message.agentError ?? message.error ?? message.agentTrace?.error ?? null;

  const clarifyToolCall = (message.toolCalls ?? []).find(
    (toolCall) => toolCall.tool === 'clarify_question'
  );
  const clarifyPrompt =
    clarifyToolCall && typeof clarifyToolCall.args?.message === 'string'
      ? clarifyToolCall.args.message
      : null;
  const clarifyOptions = Array.isArray(clarifyToolCall?.args?.options)
    ? clarifyToolCall.args.options
        .map((item) => String(item).trim())
        .filter(Boolean)
        .slice(0, 3)
    : [];
  const contentHasClarifyOptions =
    clarifyOptions.length > 0 &&
    clarifyOptions.every((option, index) => {
      const ordinal = `${index + 1}.`;
      return message.content.includes(option) || message.content.includes(ordinal);
    });
  const showClarifyFallback =
    !isUser && clarifyOptions.length > 0 && !contentHasClarifyOptions;

  const timingEntries = Object.entries(message.timingsMs ?? {}).filter(
    ([, value]) => Number.isFinite(value)
  );

  const routingEntries = Object.entries(message.routingProbabilities ?? {}).filter(
    ([, value]) => Number.isFinite(value)
  );

  const targetCollectionSet = new Set(message.targetCollections ?? []);
  const rankedCollectionScores = [...(message.collectionScores ?? [])].sort(
    (a, b) => b.score - a.score
  );

  const filterEntries = message.appliedFilters ?? [];
  const collectionResultEntries = message.collectionResults ?? [];

  const displayCollectionScores =
    rankedCollectionScores.length > 0
      ? rankedCollectionScores
      : (message.targetCollections ?? []).map((collection) => ({
          collection,
          score: Number.NaN,
        }));

  const topRoutingEntries = [...routingEntries]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 4);

  const topTimingEntries = [...timingEntries]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6);

  const showInfoPanel =
    !isUser &&
    (
      Boolean(modeLabel) ||
      Boolean(routeLabel) ||
      typeof iterationCount === 'number' ||
      toolsUsed.length > 0 ||
      displayCollectionScores.length > 0 ||
      topRoutingEntries.length > 0 ||
      filterEntries.length > 0 ||
      collectionResultEntries.length > 0 ||
      Boolean(message.reflectedQuestion) ||
      topTimingEntries.length > 0 ||
      Boolean(debugError)
    );

  const formatTimingLabel = (stage: string) =>
    stage
      .replace(/_/g, ' ')
      .replace(/\b\w/g, (char) => char.toUpperCase());

  const formatTimingSeconds = (milliseconds: number) =>
    `${(milliseconds / 1000).toFixed(2)}s`;

  const formatLatency = (milliseconds: number) => {
    if (milliseconds < 1000) {
      return `${Math.round(milliseconds)}ms`;
    }
    return `${(milliseconds / 1000).toFixed(2)}s`;
  };

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
        {showInfoPanel && (
          <div className="mb-3 space-y-1 text-[11px] text-muted-foreground bg-muted/30 p-2 rounded-md border border-border/50">
            {(modeLabel || routeLabel || typeof iterationCount === 'number' || agentLatencyMs !== undefined) && (
              <div className="flex items-center gap-1.5 flex-wrap">
                {modeLabel && (
                  <span className="rounded-sm bg-emerald-500/10 px-1.5 text-emerald-700">
                    Mode: {modeLabel}
                  </span>
                )}
                {routeLabel && (
                  <span className="rounded-sm bg-primary/10 px-1.5 text-primary">
                    Route: {routeLabel}
                  </span>
                )}
                {typeof iterationCount === 'number' && (
                  <span className="rounded-sm bg-sky-500/10 px-1.5 text-sky-700">
                    Iterations: {iterationCount}
                  </span>
                )}
                {agentLatencyMs !== undefined && (
                  <span className="rounded-sm bg-amber-500/10 px-1.5 text-amber-700">
                    Agent Latency: {formatLatency(agentLatencyMs)}
                  </span>
                )}
              </div>
            )}

            {toolsUsed.length > 0 && (
              <div className="flex items-center gap-1.5 flex-wrap">
                <span className="font-semibold text-primary/70">Tools:</span>
                {toolsUsed.map((toolName, index) => (
                  <span
                    key={`${toolName}-${index}`}
                    className="rounded-sm bg-indigo-500/10 px-1.5 text-indigo-700"
                  >
                    #{index + 1} {toolName}
                  </span>
                ))}
              </div>
            )}

            {debugError && (
              <div className="rounded-sm border border-amber-500/30 bg-amber-500/10 px-1.5 py-1 text-amber-700">
                Error: {debugError}
              </div>
            )}

            {displayCollectionScores.length > 0 && (
              <div className="flex items-center gap-1.5 flex-wrap">
                <span className="font-semibold text-primary/70">Collection Ranking:</span>
                {displayCollectionScores.map(({ collection, score }) => {
                  const scoreText = Number.isFinite(score)
                    ? ` (${score.toFixed(3)})`
                    : '';
                  const isSelected = targetCollectionSet.has(collection);
                  return (
                    <span
                      key={collection}
                      className={cn(
                        'px-1.5 rounded-sm',
                        isSelected
                          ? 'bg-primary/20 text-primary font-semibold'
                          : 'bg-primary/10 text-primary'
                      )}
                    >
                      {collection}
                      {scoreText}
                    </span>
                  );
                })}
              </div>
            )}

            {topRoutingEntries.length > 0 && (
              <div className="flex items-center gap-1.5 flex-wrap">
                <span className="font-semibold text-primary/70">Routing Prob:</span>
                {topRoutingEntries.map(([intent, prob]) => (
                  <span
                    key={intent}
                    className="rounded-sm bg-cyan-500/10 px-1.5 text-cyan-700"
                  >
                    {intent}: {Number(prob).toFixed(3)}
                  </span>
                ))}
              </div>
            )}

            {filterEntries.length > 0 && (
              <div className="space-y-1">
                <div className="font-semibold text-primary/70">Applied Filters:</div>
                <div className="flex items-center gap-1.5 flex-wrap">
                  {filterEntries.map((filter) => (
                    <span
                      key={filter.collection}
                      className={cn(
                        'rounded-sm px-1.5',
                        filter.applied
                          ? 'bg-emerald-500/10 text-emerald-700'
                          : 'bg-muted text-muted-foreground'
                      )}
                    >
                      {filter.collection}: {filter.matched_ids}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {collectionResultEntries.length > 0 && (
              <div className="space-y-1">
                <div className="font-semibold text-primary/70">Collection Hits:</div>
                <div className="flex items-center gap-1.5 flex-wrap">
                  {collectionResultEntries.map((entry) => (
                    <span
                      key={entry.collection}
                      className="rounded-sm bg-fuchsia-500/10 px-1.5 text-fuchsia-700"
                    >
                      {entry.collection}: v{entry.vector_count} / k{entry.keyword_count}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {message.reflectedQuestion && (
              <div className="flex items-start gap-1.5">
                <span className="font-semibold text-primary/70 shrink-0">Reflected:</span>
                <span className="italic break-words">"{message.reflectedQuestion}"</span>
              </div>
            )}
            {topTimingEntries.length > 0 && (
              <div className="space-y-1">
                <div className="font-semibold text-primary/70">Timing (s):</div>
                <div className="flex items-center gap-1.5 flex-wrap">
                  {topTimingEntries.map(([stage, value]) => (
                    <span
                      key={stage}
                      className="bg-amber-500/10 text-amber-700 px-1.5 rounded-sm"
                    >
                      {formatTimingLabel(stage)}: {formatTimingSeconds(value)}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        <div className="text-sm leading-relaxed prose prose-sm max-w-none dark:prose-invert">
          {message.isStreaming ? (
            <div className="whitespace-pre-wrap">{message.content}</div>
          ) : (
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={markdownComponents}
            >
              {message.content}
            </ReactMarkdown>
          )}
        </div>

        {showClarifyFallback && (
          <div className="mt-3 rounded-md border border-primary/20 bg-primary/5 p-3 text-xs">
            <div className="mb-1 font-semibold text-primary/80">
              {clarifyPrompt ?? 'Vui lòng chọn một lựa chọn để tiếp tục:'}
            </div>
            <ol className="ml-4 list-decimal space-y-1 text-foreground">
              {clarifyOptions.map((option, index) => (
                <li key={`${option}-${index}`}>{option}</li>
              ))}
            </ol>
          </div>
        )}

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
              <DocRow
                key={source.rank ?? index + 1}
                doc={source}
                rank={source.rank ?? index + 1}
                showRerank={source.rerank_score !== undefined}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default React.memo(ChatMessage);
