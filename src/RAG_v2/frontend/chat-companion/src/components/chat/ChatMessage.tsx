import React, { useState } from 'react';
import type { ChatV3Response, Message, RetrievedDocument } from '@/types/chat';
import { cn } from '@/lib/utils';
import ReactMarkdown, { Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Bot, ChevronDown, ChevronUp, ExternalLink, FileText, User } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { DocRow } from '../trace/DocRow';
import MessageActionsWeb from './MessageActionsWeb';
import AgentTrace from '../trace/AgentTrace';

interface ChatMessageProps {
  message: Message;
  showDebug?: boolean;
}

const COLLECTION_LABELS: Record<string, string> = {
  quydinh: 'Quy định',
  ctdt: 'Chương trình đào tạo',
  kehoach: 'Kế hoạch',
  stsv: 'Công tác sinh viên',
};

const metadataText = (
  metadata: Record<string, unknown> | undefined,
  keys: string[],
): string | undefined => {
  if (!metadata) {
    return undefined;
  }

  for (const key of keys) {
    const value = metadata[key];
    if (typeof value === 'string' && value.trim()) {
      return value.trim();
    }
    if (Array.isArray(value) && value.length > 0) {
      return value.map((item) => String(item)).join(', ');
    }
  }

  return undefined;
};

const normalizeText = (value: string) => value.replace(/\s+/g, ' ').trim();

const truncateText = (value: string, maxLength: number) => {
  if (value.length <= maxLength) {
    return value;
  }
  return `${value.slice(0, maxLength).trim()}...`;
};

const sourceText = (source: RetrievedDocument) => {
  const rawText = (source as RetrievedDocument & { text?: unknown }).text;
  return source.content || (typeof rawText === 'string' ? rawText : '');
};

const normalizeSourceForDisplay = (
  source: RetrievedDocument,
  index: number,
): RetrievedDocument => ({
  ...source,
  rank: source.rank ?? index + 1,
  content: sourceText(source),
  collection:
    source.collection ||
    (typeof source.metadata?.collection === 'string'
      ? source.metadata.collection
      : undefined),
  score:
    typeof source.score === 'number'
      ? source.score
      : typeof source.rerank_score === 'number'
      ? source.rerank_score
      : 0,
});

// Build a "Điều 14, tr. 12–13" style locator line from whatever the
// metadata happens to expose, so students can verify against the source.
const citationLocator = (
  metadata: Record<string, unknown> | undefined,
): string | undefined => {
  const article = metadataText(metadata, ['dieu', 'article', 'section', 'muc', 'chuong']);
  const page = metadataText(metadata, [
    'page',
    'page_number',
    'page_start',
    'pages',
    'page_label',
  ]);
  const parts: string[] = [];
  if (article) parts.push(/^\d/.test(article) ? `Điều ${article}` : article);
  if (page) parts.push(/^\d/.test(page) ? `tr. ${page}` : page);
  return parts.length > 0 ? parts.join(', ') : undefined;
};

// Find a link to the original document (CTT article or downloadable file).
const citationLink = (
  metadata: Record<string, unknown> | undefined,
): string | undefined =>
  metadataText(metadata, ['url', 'source_url', 'link', 'href', 'file_url', 'pdf_url']);

function FriendlySourceCard({
  source,
  index,
}: {
  source: RetrievedDocument;
  index: number;
}) {
  const [open, setOpen] = useState(false);
  const collection =
    source.collection || metadataText(source.metadata, ['collection']) || '';
  const collectionLabel = collection
    ? COLLECTION_LABELS[collection] || collection
    : 'Tài liệu tham khảo';
  const title =
    metadataText(source.metadata, [
      'title',
      'doc_title',
      'document_title',
      'source',
      'file_name',
      'filename',
    ]) || `Nguồn ${index + 1}`;
  const locator = citationLocator(source.metadata);
  const link = citationLink(source.metadata);
  const content = normalizeText(sourceText(source));
  const excerpt = content
    ? truncateText(content, open ? 900 : 260)
    : 'Không có đoạn trích hiển thị.';

  return (
    <div className="overflow-hidden rounded-lg border border-border border-l-[3px] border-l-primary bg-background/80 p-3">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className="flex w-full items-start gap-3 rounded-sm text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
          <FileText className="h-3.5 w-3.5" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-xs font-semibold text-foreground">
            {title}
          </span>
          <span className="mt-1 flex flex-wrap items-center gap-2">
            <Badge variant="secondary" className="max-w-full truncate text-[10px] font-medium">
              {collectionLabel}
            </Badge>
            {locator && (
              <span className="font-mono text-[10px] text-muted-foreground">{locator}</span>
            )}
            <span className="text-[10px] text-muted-foreground">Nguồn {index + 1}</span>
          </span>
        </span>
        {open ? (
          <ChevronUp className="mt-1 h-4 w-4 shrink-0 text-muted-foreground" />
        ) : (
          <ChevronDown className="mt-1 h-4 w-4 shrink-0 text-muted-foreground" />
        )}
      </button>
      <p className="mt-2 break-words text-xs leading-relaxed text-muted-foreground">
        {excerpt}
      </p>
      {link && (
        <a
          href={link}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-2 inline-flex items-center gap-1 text-[11px] font-medium text-primary hover:underline"
        >
          <ExternalLink className="h-3 w-3" />
          Xem tài liệu gốc
        </a>
      )}
    </div>
  );
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

const ChatMessage = ({ message, showDebug = false }: ChatMessageProps) => {
  const isUser = message.role === 'user';
  const [showSources, setShowSources] = useState(false);
  const hasSources = message.sources && message.sources.length > 0;

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
  const showAgentTrace = showDebug && !isUser && Boolean(message.agentTrace);
  const agentTraceQuestion =
    message.agentTrace?.query || message.reflectedQuestion || 'Agent query';
  const agentTraceResponse: ChatV3Response | null = showAgentTrace
    ? {
        question: agentTraceQuestion,
        answer: message.content,
        retrieved_documents: message.sources ?? [],
        num_documents: message.sources?.length ?? 0,
        model_name: message.modelName ?? 'agent',
        intent: message.route ?? message.agentTrace?.route ?? 'complex',
        session_id: message.sessionId ?? message.agentTrace?.session_id ?? '',
        turn_id: message.turnId,
        mode: message.mode ?? 'agent',
        route: message.route ?? message.agentTrace?.route,
        tools_used: message.toolsUsed,
        tool_calls: message.toolCalls,
        iterations: message.iterations,
        error: message.error ?? null,
        agent_error: message.agentError ?? null,
        agent_trace: message.agentTrace,
      }
    : null;

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
    showDebug &&
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
        'flex min-w-0 items-start gap-2 animate-fade-in sm:gap-3',
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
          <User className="h-4 w-4 text-secondary-foreground" />
        ) : (
          <Bot className="h-4 w-4 text-primary-foreground" />
        )}
      </div>

      {/* Message Bubble */}
      <div
        className={cn(
          'min-w-0 max-w-[92%] rounded-2xl px-3 py-3 shadow-sm sm:max-w-[85%] sm:px-4 md:max-w-[75%]',
          isUser
            ? 'rounded-tr-sm bg-chat-user text-foreground'
            : 'rounded-tl-sm bg-chat-assistant border border-border text-foreground'
        )}
      >
        {showInfoPanel && (
          <div className="mb-3 space-y-1 rounded-md border border-border/50 bg-muted/30 p-2 text-[11px] text-muted-foreground">
            {(modeLabel || routeLabel || typeof iterationCount === 'number' || agentLatencyMs !== undefined) && (
              <div className="flex flex-wrap items-center gap-1.5">
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
              <div className="flex flex-wrap items-center gap-1.5">
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
              <div className="flex flex-wrap items-center gap-1.5">
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
                        'rounded-sm px-1.5',
                        isSelected
                          ? 'bg-primary/20 font-semibold text-primary'
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
              <div className="flex flex-wrap items-center gap-1.5">
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
                <div className="flex flex-wrap items-center gap-1.5">
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
                <div className="flex flex-wrap items-center gap-1.5">
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
                <span className="shrink-0 font-semibold text-primary/70">Reflected:</span>
                <span className="break-words italic">"{message.reflectedQuestion}"</span>
              </div>
            )}

            {topTimingEntries.length > 0 && (
              <div className="space-y-1">
                <div className="font-semibold text-primary/70">Timing (s):</div>
                <div className="flex flex-wrap items-center gap-1.5">
                  {topTimingEntries.map(([stage, value]) => (
                    <span
                      key={stage}
                      className="rounded-sm bg-amber-500/10 px-1.5 text-amber-700"
                    >
                      {formatTimingLabel(stage)}: {formatTimingSeconds(value)}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        <div className="prose prose-sm max-w-none break-words text-sm leading-relaxed dark:prose-invert">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={markdownComponents}
          >
            {message.content}
          </ReactMarkdown>
          {message.isStreaming && (
            <span className="inline-block w-1.5 h-3.5 bg-current opacity-70 animate-pulse rounded-sm align-middle ml-0.5" />
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

        <span className="mt-1 block text-xs text-muted-foreground opacity-70">
          {message.timestamp.toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
          })}
        </span>

        {agentTraceResponse && (
          <details className="mt-3 rounded-lg border border-border bg-background/70 p-3" open>
            <summary className="cursor-pointer select-none text-xs font-semibold text-primary">
              Agent path log
            </summary>
            <div className="mt-3">
              <AgentTrace response={agentTraceResponse} question={agentTraceQuestion} />
            </div>
          </details>
        )}

        {/* Sources Button */}
        {hasSources && (
          <button
            onClick={() => setShowSources(!showSources)}
            className="mt-3 flex items-center gap-1.5 text-xs font-medium text-primary hover:underline"
          >
            <FileText className="h-3.5 w-3.5" />
            {showSources ? 'Ẩn' : 'Xem'} nguồn ({message.sources?.length})
          </button>
        )}

        {/* Sources Display */}
        {showSources && hasSources && (
          <div className="mt-3 space-y-2 border-t border-border pt-3">
            {!showDebug && (
              <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                Nguồn tham khảo
              </p>
            )}
            {message.sources?.map((source, index) => {
              const displaySource = normalizeSourceForDisplay(source, index);
              return (
              showDebug ? (
                <DocRow
                  key={source.rank ?? index + 1}
                  doc={displaySource}
                  rank={displaySource.rank ?? index + 1}
                  showRerank={displaySource.rerank_score !== undefined}
                />
              ) : (
                <FriendlySourceCard
                  key={`${source.rank ?? index + 1}-${index}`}
                  source={displaySource}
                  index={index}
                />
              )
              );
            })}
          </div>
        )}

        {/* Message Actions (assistant only) */}
        {!isUser && message.sessionId && message.turnId && (
          <MessageActionsWeb
            sessionId={message.sessionId}
            turnId={message.turnId}
            content={message.content}
          />
        )}
      </div>
    </div>
  );
};

export default React.memo(ChatMessage);
