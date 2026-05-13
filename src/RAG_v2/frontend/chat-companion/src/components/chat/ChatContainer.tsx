import { useState, useRef, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import type { ChatResponse, Message, UserContext } from '@/types/chat';
import { sendMessage, sendMessageStream, resolveChatIdentity } from '@/services/chatApi';
import type { ChatV3Response } from '@/types/chat';
import { getSession } from '@/services/sessionApi';
import ChatMessage from './ChatMessage';
import ChatInput from './ChatInput';
import TypingIndicator from './TypingIndicator';
import { useSmartScroll } from '@/hooks/useSmartScroll';
import type { UserPublic } from '@/services/authApi';
import { parseUtcDate } from '@/lib/utils';

interface ChatContainerProps {
  user?: UserPublic | null;
  sessionId?: string;
}

const buildUserContextFromUser = (
  currentUser?: UserPublic | null,
): UserContext | undefined => {
  if (!currentUser) {
    return undefined;
  }

  return {
    student_id: currentUser.student_id || undefined,
    cohort: currentUser.cohort || undefined,
    major: currentUser.major || undefined,
    major_code: currentUser.major_code || undefined,
    full_name: currentUser.full_name || undefined,
  };
};

const ChatContainer = ({ user, sessionId: sessionIdProp }: ChatContainerProps) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [chatPhase, setChatPhase] = useState<'idle' | 'thinking' | 'streaming'>('idle');
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [lastResponsePayload, setLastResponsePayload] = useState<ChatResponse | null>(null);
  // activeSessionId tracks the current session; initialised from the URL param
  const [activeSessionId, setActiveSessionId] = useState<string | undefined>(sessionIdProp);
  // Ref mirror — always current even inside stale async closures
  const activeSessionIdRef = useRef<string | undefined>(sessionIdProp);
  // Guards async callbacks after component unmount (e.g. logout)
  const isMountedRef = useRef(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  // Set to true before calling navigate() from within handleSendMessage so the
  // resulting sessionIdProp change does NOT clear messages or reload history.
  const suppressNextHistoryLoad = useRef(false);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const explicitUserContext = buildUserContextFromUser(user);
  const explicitUserId = user?.email ?? user?.username ?? undefined;
  const resolvedIdentity = resolveChatIdentity(explicitUserContext, explicitUserId);

  const debugPayload = {
    source: resolvedIdentity.source,
    user_id: resolvedIdentity.userId ?? null,
    user_context: resolvedIdentity.userContext ?? null,
    active_session_id: activeSessionId ?? null,
    last_response: lastResponsePayload
      ? {
          mode: lastResponsePayload.mode ?? null,
          route: lastResponsePayload.route ?? lastResponsePayload.intent ?? null,
          model_name: lastResponsePayload.model_name ?? null,
          iterations: lastResponsePayload.iterations ?? null,
          tools_used: lastResponsePayload.tools_used ?? [],
          timings_ms: lastResponsePayload.timings_ms ?? null,
          routing_probabilities: lastResponsePayload.routing_probabilities ?? null,
          agent_error: lastResponsePayload.agent_error ?? null,
          error: lastResponsePayload.error ?? null,
        }
      : null,
    last_response_raw: lastResponsePayload,
    raw_user: user ?? null,
  };

  // Keep ref in sync with state
  useEffect(() => {
    activeSessionIdRef.current = activeSessionId;
  }, [activeSessionId]);

  // Mark unmounted on cleanup
  useEffect(() => {
    isMountedRef.current = true;
    return () => { isMountedRef.current = false; };
  }, []);

  const { showScrollButton, forceScrollToBottom, isNearBottom } = useSmartScroll(messagesEndRef, [messages, chatPhase]);

  // When the URL session param changes (user clicks sidebar item or New Chat),
  // reset state and optionally load history from the backend.
  useEffect(() => {
    setActiveSessionId(sessionIdProp);

    // Navigation triggered internally by handleSendMessage — don't reset or reload
    if (suppressNextHistoryLoad.current) {
      suppressNextHistoryLoad.current = false;
      return;
    }

    // New session selected — reset chat state
    setMessages([]);
    setChatPhase('idle');
    setLastResponsePayload(null);

    if (!sessionIdProp) return;

    setIsLoadingHistory(true);
    getSession(sessionIdProp)
      .then(({ turns }) => {
        const loaded: Message[] = turns.flatMap((t) => [
          {
            id: `user-${t.turn_id}`,
            role: 'user' as const,
            content: t.question,
            timestamp: parseUtcDate(t.timestamp),
          },
          {
            id: `assistant-${t.turn_id}`,
            role: 'assistant' as const,
            content: t.answer,
            timestamp: parseUtcDate(t.timestamp),
            modelName: t.model_name,
            mode: t.mode,
            route: t.route ?? t.intent,
            toolsUsed: t.tools_used,
            toolCalls: t.tool_calls,
            iterations: t.iterations,
            error: t.error ?? undefined,
            agentError: t.agent_error ?? undefined,
            agentTrace: t.agent_trace,
            reflectedQuestion: t.reflected_question ?? undefined,
            timingsMs: t.timings_ms,
            sources: t.sources,
            collectionScores: t.collection_scores,
            targetCollections: t.target_collections,
            routingProbabilities: t.routing_probabilities,
            appliedFilters: t.applied_filters,
            collectionResults: t.collection_results,
          },
        ]);
        setMessages(loaded);
      })
      .catch((err) => {
        console.error('Failed to load session history:', err);
      })
      .finally(() => setIsLoadingHistory(false));
  }, [sessionIdProp]);

  const handleSendMessage = async (content: string) => {
    // Snapshot the session at call time — this is the "owner" of this request.
    // All async callbacks check this against the current session before mutating state.
    const capturedSessionId = activeSessionId;

    // Add user message
    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setChatPhase('thinking');
    forceScrollToBottom();

    let responseSessionId = capturedSessionId;
    let hasReceivedFirstToken = false;
    const assistantMessageId = `assistant-${Date.now()}`;

    try {
      // Build history from existing messages (last 6 turns)
      const historyForApi = messages.slice(-6).map((m) => ({
        role: m.role,
        content: m.content,
      }));
      
      const response = await sendMessageStream(
        content,
        historyForApi,
        5,
        capturedSessionId,
        explicitUserContext,
        explicitUserId,
        {
          onSessionId: (sid) => {
            responseSessionId = sid;
            if (sid && sid !== capturedSessionId) {
              suppressNextHistoryLoad.current = true;
              setActiveSessionId(sid);
              navigate(`/chat/${sid}`, { replace: true });
            }
          },
          onToken: (delta) => {
            if (!isMountedRef.current) return;

            if (!hasReceivedFirstToken) {
              hasReceivedFirstToken = true;
              setChatPhase('streaming');
              setMessages((prev) => [
                ...prev,
                {
                  id: assistantMessageId,
                  role: 'assistant',
                  content: delta,
                  timestamp: new Date(),
                  isStreaming: true,
                }
              ]);
            } else {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantMessageId
                    ? { ...m, content: m.content + delta }
                    : m
                )
              );
            }
          },
          onMetadata: (meta: Partial<ChatV3Response>) => {
            if (!isMountedRef.current) return;
            // Attach all log fields to the assistant message
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMessageId
                  ? {
                      ...m,
                      mode: meta.mode,
                      route: meta.route ?? meta.intent,
                      modelName: meta.model_name,
                      timingsMs: meta.timings_ms,
                      reflectedQuestion: meta.reflected_question,
                      targetCollections: meta.target_collections,
                      collectionScores: meta.collection_scores,
                      routingProbabilities: meta.routing_probabilities,
                      appliedFilters: meta.applied_filters,
                      collectionResults: meta.collection_results,
                      toolsUsed: meta.tools_used,
                      toolCalls: meta.tool_calls,
                      iterations: meta.iterations,
                      agentTrace: meta.agent_trace,
                      sources: meta.retrieved_documents,
                    }
                  : m
              )
            );
            // Update debug panel payload
            setLastResponsePayload(meta as ChatResponse);
          },
        }
      );

      // Component was unmounted (e.g. logout) — bail out entirely
      if (!isMountedRef.current) return;

      // User navigated to a different session while this request was in flight.
      if (activeSessionIdRef.current !== capturedSessionId &&
          capturedSessionId !== undefined) {
        return;
      }

      // Refresh the sidebar conversation list
      if (resolvedIdentity.userId) {
        queryClient.invalidateQueries({ queryKey: ['sessions', resolvedIdentity.userId] });
      }

      // Finalize the assistant message
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantMessageId
            ? { ...m, isStreaming: false }
            : m
        )
      );
      
    } catch (error) {
      // Only show error in the session that initiated the request
      if (isMountedRef.current && activeSessionIdRef.current === capturedSessionId) {
        console.error('Failed to get response:', error);
        const errorMessage: Message = {
          id: `error-${Date.now()}`,
          role: 'assistant',
          content: error instanceof Error
            ? error.message
            : 'Sorry, I encountered an error. Please try again.',
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, errorMessage]);
      }
    } finally {
      // Only clear the loading indicator for the session that set it.
      const shouldClearLoading =
        activeSessionIdRef.current === capturedSessionId ||
        (
          capturedSessionId === undefined &&
          responseSessionId !== undefined &&
          activeSessionIdRef.current === responseSessionId
        );

      if (isMountedRef.current && shouldClearLoading) {
        setChatPhase('idle');
      }
    }
  };

  const greeting = user ? `Xin chào, ${user.full_name.split(' ').pop()}!` : 'Bắt đầu trò chuyện';

  return (
    <div className="flex h-full flex-col">
      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto scrollbar-thin p-4 md:p-6">
        {isLoadingHistory ? (
          <div className="flex h-full items-center justify-center">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          </div>
        ) : messages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center text-center">
            <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-primary/10">
              <svg
                className="h-8 w-8 text-primary"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
                />
              </svg>
            </div>
            <h3 className="mb-2 text-lg font-semibold text-foreground">{greeting}</h3>
            <p className="max-w-sm text-sm text-muted-foreground">
              {user
                ? `Tôi có thể tư vấn về quy chế học tập, học bổng và các quy định của BKHN.`
                : 'Ask me anything! I\'m here to help with your questions.'}
            </p>
            {user && (user.major || user.cohort) && (
              <p className="mt-1.5 text-xs text-muted-foreground/70">
                {[user.major, user.cohort ? `Khoá ${user.cohort}` : null]
                  .filter(Boolean)
                  .join(' · ')}
              </p>
            )}
          </div>
        ) : (
          <div className="mx-auto max-w-3xl space-y-4">
            {messages.map((message) => (
              <ChatMessage key={message.id} message={message} />
            ))}
            {chatPhase !== 'idle' && !messages[messages.length - 1]?.isStreaming && <TypingIndicator phase={chatPhase as 'thinking' | 'streaming'} />}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Floating Scroll to Bottom Button */}
      {showScrollButton && (
        <button
          onClick={forceScrollToBottom}
          className="absolute bottom-32 left-1/2 -translate-x-1/2 rounded-full bg-background/80 p-2 text-foreground shadow-md backdrop-blur border border-border transition-all hover:bg-muted animate-in fade-in slide-in-from-bottom-4 z-10"
          aria-label="Scroll to bottom"
        >
          <svg
            className="h-5 w-5 text-primary"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
          </svg>
        </button>
      )}

      {/* Input Area */}
      <div className="border-t border-border bg-background/80 backdrop-blur-sm p-4 md:p-6 relative z-20">
        <div className="mx-auto max-w-3xl">
          <ChatInput onSend={handleSendMessage} disabled={chatPhase !== 'idle'} />
          <details className="mt-3 rounded-md border border-border/80 bg-muted/20 px-3 py-2 text-xs">
            <summary className="cursor-pointer select-none text-muted-foreground">
              Debug runtime info
            </summary>
            <pre className="mt-2 max-h-56 overflow-auto rounded bg-background p-2 text-[11px] text-foreground">
              {JSON.stringify(debugPayload, null, 2)}
            </pre>
          </details>
          <p className="mt-2 text-center text-xs text-muted-foreground">
            Press Enter to send, Shift + Enter for new line
          </p>
        </div>
      </div>
    </div>
  );
};

export default ChatContainer;
