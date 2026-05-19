import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import type { ChatResponse, Message, UserContext } from '@/types/chat';
import { sendMessageV3, resolveChatIdentity } from '@/services/chatApi';
import { getSession } from '@/services/sessionApi';
import ChatMessage from './ChatMessage';
import ChatInput from './ChatInput';
import TypingIndicator from './TypingIndicator';
import { useSmartScroll } from '@/hooks/useSmartScroll';
import type { UserPublic } from '@/services/authApi';
import { parseUtcDate } from '@/lib/utils';
import {
  BookOpen,
  Bot,
  CalendarDays,
  GraduationCap,
  ScrollText,
  type LucideIcon,
} from 'lucide-react';

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
  const explicitUserId = user?.email ?? user?.username ?? user?.student_id ?? undefined;
  const resolvedIdentity = resolveChatIdentity(explicitUserContext, explicitUserId);
  const isAdmin = user?.role === 'admin';

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
          num_documents: lastResponsePayload.num_documents ?? null,
          target_collections: lastResponsePayload.target_collections ?? [],
          collection_scores: lastResponsePayload.collection_scores ?? [],
          applied_filters: lastResponsePayload.applied_filters ?? null,
          collection_results: lastResponsePayload.collection_results ?? null,
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

  const { showScrollButton, forceScrollToBottom } = useSmartScroll(messagesEndRef, [messages, chatPhase]);

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
            sessionId: sessionIdProp,
            turnId: t.turn_id,
          },
          {
            id: `assistant-${t.turn_id}`,
            role: 'assistant' as const,
            content: t.answer,
            timestamp: parseUtcDate(t.timestamp),
            sessionId: sessionIdProp,
            turnId: t.turn_id,
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

    try {
      // Build history from existing messages (last 6 turns)
      const historyForApi = messages.slice(-6).map((m) => ({
        role: m.role,
        content: m.content,
      }));

      const response = await sendMessageV3(
        content,
        historyForApi,
        5,
        'auto',
        capturedSessionId,
        explicitUserContext,
        explicitUserId,
      );

      // Component was unmounted (e.g. logout) — bail out entirely
      if (!isMountedRef.current) return;

      responseSessionId = response.session_id || capturedSessionId;
      if (responseSessionId && responseSessionId !== capturedSessionId) {
        suppressNextHistoryLoad.current = true;
        setActiveSessionId(responseSessionId);
        navigate(`/chat/${responseSessionId}`, { replace: true });
      }

      // User navigated to a different session while this request was in flight.
      if (activeSessionIdRef.current !== capturedSessionId &&
          capturedSessionId !== undefined) {
        return;
      }

      const assistantMessage: Message = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: response.answer || 'Tôi chưa có câu trả lời cho câu hỏi này.',
        timestamp: new Date(),
        sessionId: responseSessionId,
        turnId: response.turn_id,
        mode: response.mode,
        route: response.route ?? response.intent,
        modelName: response.model_name,
        timingsMs: response.timings_ms,
        reflectedQuestion: response.reflected_question,
        targetCollections: response.target_collections,
        collectionScores: response.collection_scores,
        routingProbabilities: response.routing_probabilities,
        appliedFilters: response.applied_filters,
        collectionResults: response.collection_results,
        toolsUsed: response.tools_used,
        toolCalls: response.tool_calls,
        iterations: response.iterations,
        agentTrace: response.agent_trace,
        sources: response.retrieved_documents,
      };

      setMessages((prev) => [...prev, assistantMessage]);
      setLastResponsePayload(response as ChatResponse);

      // Refresh the sidebar conversation list
      if (resolvedIdentity.userId) {
        queryClient.invalidateQueries({ queryKey: ['sessions', resolvedIdentity.userId] });
      }
    } catch (error) {
      // Only show error in the session that initiated the request
      if (isMountedRef.current && activeSessionIdRef.current === capturedSessionId) {
        console.error('Failed to get response:', error);
        const errorMessage: Message = {
          id: `error-${Date.now()}`,
          role: 'assistant',
          content: 'Xin lỗi, hệ thống đang gặp sự cố. Vui lòng thử lại sau ít phút.',
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
  const suggestions: Array<{ icon: LucideIcon; label: string; query: string }> = [
    {
      icon: ScrollText,
      label: 'Quy chế đào tạo',
      query: 'Quy chế đào tạo tín chỉ mới nhất của BKHN là gì?',
    },
    {
      icon: GraduationCap,
      label: 'CTĐT ngành tôi',
      query: `Chương trình đào tạo ngành ${user?.major || 'của tôi'} gồm những gì?`,
    },
    {
      icon: BookOpen,
      label: 'Chính sách học bổng',
      query: 'Các loại học bổng hiện có tại BKHN?',
    },
    {
      icon: CalendarDays,
      label: 'Lịch học kỳ mới',
      query: 'Lịch trình học kỳ mới nhất?',
    },
  ];

  return (
    <div className="relative flex h-full flex-col">
      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto scrollbar-thin p-3 sm:p-4 md:p-6">
        {isLoadingHistory ? (
          <div className="flex h-full items-center justify-center">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          </div>
        ) : messages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center px-4 text-center">
            <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10">
              <Bot className="h-8 w-8 text-primary" />
            </div>
            <h3 className="mb-1 text-xl font-semibold text-foreground">{greeting}</h3>
            <p className="mb-8 max-w-md text-sm text-muted-foreground">
              Tôi có thể tư vấn về quy chế, CTĐT, học bổng và các quy định của BKHN.
            </p>
            <div className="grid w-full max-w-lg grid-cols-1 gap-3 xs:grid-cols-2 sm:grid-cols-2">
              {suggestions.map((suggestion) => {
                const Icon = suggestion.icon;
                return (
                  <button
                    key={suggestion.label}
                    onClick={() => handleSendMessage(suggestion.query)}
                    className="flex min-h-[72px] items-start gap-3 rounded-lg border border-border bg-card p-4 text-left transition-all hover:bg-secondary hover:shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    <Icon className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
                    <span className="text-sm font-medium leading-snug text-foreground">
                      {suggestion.label}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        ) : (
          <div className="mx-auto w-full max-w-3xl space-y-4">
            {messages.map((message) => (
              <ChatMessage key={message.id} message={message} showDebug={true} />
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
      <div className="relative z-20 shrink-0 border-t border-border bg-background/90 p-3 backdrop-blur-sm sm:p-4 md:p-6">
        <div className="mx-auto w-full max-w-3xl">
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
            Nhấn Enter để gửi, Shift + Enter để xuống dòng.
          </p>
        </div>
      </div>
    </div>
  );
};

export default ChatContainer;
