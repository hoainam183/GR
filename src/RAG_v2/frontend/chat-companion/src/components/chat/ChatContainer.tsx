import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import type { ChatResponse, ChatV3Response, Message, Turn, UserContext } from '@/types/chat';
import { sendMessageStream, resolveChatIdentity } from '@/services/chatApi';
import { getSession, getSessions } from '@/services/sessionApi';
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
  RotateCcw,
  ScrollText,
  type LucideIcon,
} from 'lucide-react';

interface ChatContainerProps {
  user?: UserPublic | null;
  sessionId?: string;
}

interface PendingChatTurn {
  sessionId: string;
  userMessageId: string;
  assistantMessageId: string;
  question: string;
  startedAt: string;
}

// Sentinel session id for a turn sent before the server returned a real
// session_id (brand-new chat). Lets us recover it after a very fast refresh.
const NEW_SESSION_SENTINEL = 'new';

// Typewriter reveal pacing (see revealTick). Each animation frame reveals at
// least REVEAL_MIN_CHARS characters; when the buffer is large it reveals
// ceil(len / REVEAL_CATCHUP_DIVISOR) so a backlog drains quickly and the UI
// never falls behind a fast stream.
const REVEAL_MIN_CHARS = 2;
const REVEAL_CATCHUP_DIVISOR = 6;

const pendingKey = (sessionId: string) => `pending-chat:${sessionId}`;

const readPendingTurn = (sessionId: string): PendingChatTurn | null => {
  try {
    const raw = sessionStorage.getItem(pendingKey(sessionId));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as PendingChatTurn;
    return parsed?.question ? parsed : null;
  } catch {
    return null;
  }
};

const writePendingTurn = (pending: PendingChatTurn) => {
  sessionStorage.setItem(pendingKey(pending.sessionId), JSON.stringify(pending));
};

const clearPendingTurn = (sessionId?: string) => {
  if (sessionId) sessionStorage.removeItem(pendingKey(sessionId));
};

const messagesFromTurns = (turns: Turn[], sessionId: string): Message[] =>
  turns.flatMap((t) => [
    {
      id: `user-${t.turn_id}`,
      role: 'user' as const,
      content: t.question,
      timestamp: parseUtcDate(t.timestamp),
      sessionId,
      turnId: t.turn_id,
    },
    {
      id: `assistant-${t.turn_id}`,
      role: 'assistant' as const,
      content: t.answer,
      timestamp: parseUtcDate(t.timestamp),
      question: t.question,
      sessionId,
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

const pendingMessages = (pending: PendingChatTurn): Message[] => [
  {
    id: pending.userMessageId,
    role: 'user',
    content: pending.question,
    timestamp: parseUtcDate(pending.startedAt),
    sessionId: pending.sessionId,
  },
  {
    id: pending.assistantMessageId,
    role: 'assistant',
    content: '',
    timestamp: parseUtcDate(pending.startedAt),
    sessionId: pending.sessionId,
    isStreaming: true,
  },
];

const applyResponseMetadata = (
  message: Message,
  response: Partial<ChatV3Response>,
  sessionId?: string,
): Message => ({
  ...message,
  sessionId: response.session_id || sessionId || message.sessionId,
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
  error: response.error ?? undefined,
  agentError: response.agent_error ?? undefined,
  isStreaming: false,
});

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
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [lastResponsePayload, setLastResponsePayload] = useState<ChatResponse | null>(null);
  // activeSessionId tracks the current session; initialised from the URL param
  const [activeSessionId, setActiveSessionId] = useState<string | undefined>(sessionIdProp);
  // Ref mirror — always current even inside stale async closures
  const activeSessionIdRef = useRef<string | undefined>(sessionIdProp);
  // Guards async callbacks after component unmount (e.g. logout)
  const isMountedRef = useRef(true);
  // Token batching (B3): buffer deltas, flush via rAF to cut re-renders per token.
  const tokenBufferRef = useRef('');
  const flushRafRef = useRef<number | null>(null);
  // Controls the in-flight /chat/stream fetch so the user can Stop a response.
  const abortControllerRef = useRef<AbortController | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
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
    return () => {
      isMountedRef.current = false;
      if (flushRafRef.current !== null) {
        cancelAnimationFrame(flushRafRef.current);
        flushRafRef.current = null;
      }
      tokenBufferRef.current = '';
      // NOTE: intentionally do NOT abort the in-flight request here. This
      // component keeps the stream alive across unmount so the backend still
      // persists the turn and the sessionStorage-polling recovery works.
      // Aborting is only ever user-initiated via the Stop button.
    };
  }, []);

  const { showScrollButton, forceScrollToBottom } = useSmartScroll(
    messagesEndRef,
    [messages, chatPhase],
    messagesContainerRef,
    chatPhase === 'streaming',
  );

  // When the URL session param changes (user clicks sidebar item or New Chat),
  // reset state and optionally load history from the backend.
  useEffect(() => {
    let cancelled = false;
    let pollId: ReturnType<typeof setInterval> | undefined;

    setActiveSessionId(sessionIdProp);

    // Navigation triggered internally by handleSendMessage — don't reset or reload
    if (suppressNextHistoryLoad.current) {
      suppressNextHistoryLoad.current = false;
      return () => {};
    }

    // New session selected — reset chat state
    setMessages([]);
    setChatPhase('idle');
    setLastResponsePayload(null);

    if (!sessionIdProp) {
      // Base /chat route. If we sent a turn but refreshed before the server
      // returned a session_id, recover it: show the question, then poll the
      // session list for the freshly-created session and hand off to the
      // normal per-session recovery by re-keying the pending turn.
      const pending = readPendingTurn(NEW_SESSION_SENTINEL);
      if (!pending) return () => {};

      const ageMs = Date.now() - parseUtcDate(pending.startedAt).getTime();
      if (ageMs > 60_000) {
        clearPendingTurn(NEW_SESSION_SENTINEL);
        return () => {};
      }

      setMessages(pendingMessages(pending));
      setChatPhase('thinking');

      const startedAtMs = parseUtcDate(pending.startedAt).getTime();
      pollId = setInterval(() => {
        getSessions(resolvedIdentity.userId)
          .then((sessions) => {
            if (cancelled) return;
            const match = sessions
              .filter(
                (s) =>
                  s.turn_count >= 1 &&
                  parseUtcDate(s.created_at).getTime() >= startedAtMs - 5000,
              )
              .sort(
                (a, b) =>
                  parseUtcDate(b.created_at).getTime() - parseUtcDate(a.created_at).getTime(),
              )[0];
            if (match && pollId) {
              clearInterval(pollId);
              pollId = undefined;
              writePendingTurn({ ...pending, sessionId: match.session_id });
              clearPendingTurn(NEW_SESSION_SENTINEL);
              navigate(`/chat/${match.session_id}`, { replace: true });
            }
          })
          .catch((err) => {
            console.error('Failed to reconcile pending turn:', err);
          });
      }, 2500);

      return () => {
        cancelled = true;
        if (pollId) clearInterval(pollId);
      };
    }

    setIsLoadingHistory(true);

    const applyTurns = (turns: Turn[]) => {
      if (turns.length > 0) {
        clearPendingTurn(sessionIdProp);
        setMessages(messagesFromTurns(turns, sessionIdProp));
        setChatPhase('idle');
        return true;
      }

      const pending = readPendingTurn(sessionIdProp);
      if (pending) {
        setMessages(pendingMessages(pending));
        setChatPhase('thinking');
      }
      return false;
    };

    const pollUntilTurnSaved = () => {
      pollId = setInterval(() => {
        getSession(sessionIdProp)
          .then(({ turns }) => {
            if (cancelled) return;
            if (applyTurns(turns) && pollId) {
              clearInterval(pollId);
              pollId = undefined;
              if (resolvedIdentity.userId) {
                queryClient.invalidateQueries({ queryKey: ['sessions', resolvedIdentity.userId] });
              }
            }
          })
          .catch((err) => {
            console.error('Failed to poll pending session:', err);
          });
      }, 2500);
    };

    getSession(sessionIdProp)
      .then(({ turns }) => {
        if (cancelled) return;
        const hasSavedTurn = applyTurns(turns);
        if (!hasSavedTurn && readPendingTurn(sessionIdProp)) {
          pollUntilTurnSaved();
        }
      })
      .catch((err) => {
        console.error('Failed to load session history:', err);
      })
      .finally(() => {
        if (!cancelled) setIsLoadingHistory(false);
      });

    return () => {
      cancelled = true;
      if (pollId) clearInterval(pollId);
    };
  }, [sessionIdProp, queryClient, resolvedIdentity.userId, navigate]);

  const handleSendMessage = async (
    content: string,
    options: { isRetry?: boolean } = {},
  ) => {
    const { isRetry = false } = options;
    // Snapshot the session at call time — this is the "owner" of this request.
    // All async callbacks check this against the current session before mutating state.
    const capturedSessionId = activeSessionId;
    const startedAt = new Date();
    const userMessageId = `user-${startedAt.getTime()}`;
    const assistantMessageId = `assistant-${startedAt.getTime()}`;

    // Add user message (on retry the original user bubble is still on screen,
    // so we skip echoing the question a second time).
    if (!isRetry) {
      const userMessage: Message = {
        id: userMessageId,
        role: 'user',
        content,
        timestamp: startedAt,
        sessionId: capturedSessionId,
      };
      setMessages((prev) => [...prev, userMessage]);
    }
    setChatPhase('thinking');
    setStatusMessage(null);
    forceScrollToBottom();

    // Fresh AbortController per request so the user can Stop this response.
    const controller = new AbortController();
    abortControllerRef.current = controller;

    let responseSessionId = capturedSessionId;
    let receivedMetadata: Partial<ChatV3Response> | undefined;

    const isCurrentRequest = () =>
      !capturedSessionId || activeSessionIdRef.current === capturedSessionId || activeSessionIdRef.current === responseSessionId;

    // Append a slice of text to the assistant message in a single state update.
    const appendToAssistant = (slice: string) => {
      setMessages((prev) => {
        const existing = prev.find((message) => message.id === assistantMessageId);
        if (!existing) {
          return [
            ...prev,
            {
              id: assistantMessageId,
              role: 'assistant',
              content: slice,
              timestamp: new Date(),
              sessionId: responseSessionId,
              isStreaming: true,
            },
          ];
        }
        return prev.map((message) =>
          message.id === assistantMessageId
            ? { ...message, content: `${message.content}${slice}`, isStreaming: true }
            : message,
        );
      });
    };

    // Paced typewriter reveal, aligned to the display refresh via rAF. Each frame
    // reveals a slice of the buffer so tokens flow evenly instead of arriving in
    // jerky bursts; a large backlog drains faster so we never lag behind the stream.
    const revealTick = () => {
      flushRafRef.current = null;
      const buffered = tokenBufferRef.current;
      if (!buffered) return;
      if (!isMountedRef.current || !isCurrentRequest()) {
        tokenBufferRef.current = '';
        return;
      }
      const take = Math.max(REVEAL_MIN_CHARS, Math.ceil(buffered.length / REVEAL_CATCHUP_DIVISOR));
      tokenBufferRef.current = buffered.slice(take);
      appendToAssistant(buffered.slice(0, take));
      if (tokenBufferRef.current) {
        flushRafRef.current = requestAnimationFrame(revealTick) as unknown as number;
      }
    };

    // Dump everything remaining immediately (on metadata / done / stop) so the
    // final text never lags behind the paced reveal.
    const drainTokenBuffer = () => {
      if (flushRafRef.current !== null) {
        cancelAnimationFrame(flushRafRef.current);
        flushRafRef.current = null;
      }
      const buffered = tokenBufferRef.current;
      tokenBufferRef.current = '';
      if (!buffered || !isMountedRef.current || !isCurrentRequest()) return;
      appendToAssistant(buffered);
    };

    const persistPending = (sessionId: string) => {
      writePendingTurn({
        sessionId,
        userMessageId,
        assistantMessageId,
        question: content,
        startedAt: startedAt.toISOString(),
      });
    };

    // Persist immediately — even before the server assigns a session_id — so a
    // refresh in the tiny window before onSessionId doesn't lose the question.
    persistPending(capturedSessionId ?? NEW_SESSION_SENTINEL);

    try {
      // Build history from existing messages (last 6 turns)
      const historyForApi = messages.slice(-6).map((m) => ({
        role: m.role,
        content: m.content,
      }));

      const response = await sendMessageStream(
        content,
        historyForApi,
        7,
        capturedSessionId,
        explicitUserContext,
        explicitUserId,
        {
          onSessionId: (sid) => {
            responseSessionId = sid;
            persistPending(sid);
            // Re-key from the sentinel to the real session id.
            if (!capturedSessionId) clearPendingTurn(NEW_SESSION_SENTINEL);
            if (!isMountedRef.current) return;
            suppressNextHistoryLoad.current = true;
            setActiveSessionId(sid);
            activeSessionIdRef.current = sid;
            setMessages((prev) =>
              prev.map((message) =>
                message.id === userMessageId || message.id === assistantMessageId
                  ? { ...message, sessionId: sid }
                  : message,
              ),
            );
            if (sid !== capturedSessionId) {
              navigate(`/chat/${sid}`, { replace: true });
            }
            if (resolvedIdentity.userId) {
              queryClient.invalidateQueries({ queryKey: ['sessions', resolvedIdentity.userId] });
            }
          },
          onStatus: (status) => {
            if (!isMountedRef.current || !isCurrentRequest()) return;
            setStatusMessage(status.message);
          },
          onToken: (delta) => {
            if (!isMountedRef.current || !isCurrentRequest()) return;
            setChatPhase('streaming');
            setStatusMessage(null);
            // Buffer the delta and flush shortly after so a burst
            // of tokens coalesces into a single React update.
            tokenBufferRef.current += delta;
            if (flushRafRef.current === null) {
              flushRafRef.current = requestAnimationFrame(revealTick) as unknown as number;
            }
          },
          onMetadata: (meta) => {
            receivedMetadata = meta;
            if (!isMountedRef.current || !isCurrentRequest()) return;
            drainTokenBuffer();
            responseSessionId = meta.session_id || responseSessionId;
            setMessages((prev) =>
              prev.map((message) =>
                message.id === assistantMessageId
                  ? applyResponseMetadata(
                      {
                        ...message,
                        content: message.content || meta.answer || 'Tôi chưa có câu trả lời cho câu hỏi này.',
                        question: content,
                      },
                      meta,
                      responseSessionId,
                    )
                  : message,
              ),
            );
            setLastResponsePayload(meta as ChatResponse);
            clearPendingTurn(responseSessionId);
            if (resolvedIdentity.userId) {
              queryClient.invalidateQueries({ queryKey: ['sessions', resolvedIdentity.userId] });
            }
          },
          onError: () => {
            drainTokenBuffer();
            clearPendingTurn(responseSessionId);
          },
          signal: controller.signal,
        },
      );

      // Component was unmounted (e.g. logout) — bail out entirely
      if (!isMountedRef.current) return;

      // Flush any tokens still buffered before applying final metadata.
      drainTokenBuffer();

      responseSessionId = response.sessionId || responseSessionId;
      if (!isCurrentRequest()) {
        return;
      }

      const finalMetadata = receivedMetadata || response.metadata;
      setMessages((prev) => {
        const existing = prev.find((message) => message.id === assistantMessageId);
        if (existing) {
          return prev.map((message) =>
            message.id === assistantMessageId
              ? finalMetadata
                ? applyResponseMetadata(
                    {
                      ...message,
                      content: message.content || response.answer || 'Tôi chưa có câu trả lời cho câu hỏi này.',
                      question: content,
                    },
                    finalMetadata,
                    responseSessionId,
                  )
                : { ...message, content: message.content || response.answer, isStreaming: false }
              : message,
          );
        }
        return [
          ...prev,
          finalMetadata
            ? applyResponseMetadata(
                {
                  id: assistantMessageId,
                  role: 'assistant',
                  content: response.answer || finalMetadata.answer || 'Tôi chưa có câu trả lời cho câu hỏi này.',
                  timestamp: new Date(),
                  sessionId: responseSessionId,
                  question: content,
                },
                finalMetadata,
                responseSessionId,
              )
            : {
                id: assistantMessageId,
                role: 'assistant',
                content: response.answer || 'Tôi chưa có câu trả lời cho câu hỏi này.',
                timestamp: new Date(),
                sessionId: responseSessionId,
              },
        ];
      });
      if (finalMetadata) {
        setLastResponsePayload(finalMetadata as ChatResponse);
      }
      clearPendingTurn(responseSessionId);

      // Refresh the sidebar conversation list
      if (resolvedIdentity.userId) {
        queryClient.invalidateQueries({ queryKey: ['sessions', resolvedIdentity.userId] });
      }
    } catch (error) {
      drainTokenBuffer();
      // User pressed Stop (or the component unmounted): keep whatever text has
      // already streamed in, finalise the bubble, and skip the error message.
      const isAbort = error instanceof Error && error.name === 'AbortError';
      if (isAbort) {
        clearPendingTurn(responseSessionId);
        if (!capturedSessionId) clearPendingTurn(NEW_SESSION_SENTINEL);
        if (isMountedRef.current && isCurrentRequest()) {
          setMessages((prev) =>
            prev.map((message) =>
              message.id === assistantMessageId
                ? { ...message, isStreaming: false }
                : message,
            ),
          );
        }
        return;
      }
      // Only show error in the session that initiated the request
      if (isMountedRef.current && isCurrentRequest()) {
        console.error('Failed to get response:', error);
        clearPendingTurn(responseSessionId);
        if (!capturedSessionId) clearPendingTurn(NEW_SESSION_SENTINEL);
        const errorMessage: Message = {
          id: `error-${Date.now()}`,
          role: 'assistant',
          content: 'Không gửi được tin nhắn. Vui lòng kiểm tra kết nối và thử lại.',
          timestamp: new Date(),
          sessionId: responseSessionId,
          isError: true,
          retryQuestion: content,
        };
        // Drop any partial/streaming assistant bubble before showing the error.
        setMessages((prev) => [
          ...prev.filter((message) => message.id !== assistantMessageId),
          errorMessage,
        ]);
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
        setStatusMessage(null);
      }
    }
  };

  const handleStop = () => {
    abortControllerRef.current?.abort();
  };

  const handleRetry = (question: string, errorMessageId: string) => {
    setMessages((prev) => prev.filter((message) => message.id !== errorMessageId));
    handleSendMessage(question, { isRetry: true });
  };

  const lastMessage = messages[messages.length - 1];
  const showFollowUps =
    chatPhase === 'idle' &&
    lastMessage?.role === 'assistant' &&
    !lastMessage.isStreaming &&
    !lastMessage.isError;
  // Accent-fold + lowercase so "Học phí" and "hoc phi" compare equal.
  const foldText = (value: string) =>
    value
      .normalize('NFD')
      .replace(/[̀-ͯ]/g, '')
      .replace(/đ/gi, 'd')
      .toLowerCase()
      .trim();
  const lastUserQuestion = [...messages].reverse().find((m) => m.role === 'user')?.content ?? '';
  const foldedLastQuestion = foldText(lastUserQuestion);
  // Drop any suggestion the user just asked so it doesn't reappear right after.
  const followUpChips = [
    'Học phí kỳ này',
    'Lịch thi cuối kỳ',
    'Điều kiện tốt nghiệp',
    'Học bổng KKHT',
  ].filter((chip) => foldText(chip) !== foldedLastQuestion);

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
      query: 'Lịch học kỳ mới nhất?',
    },
  ];

  return (
    <div className="relative flex h-full min-h-0 flex-col overscroll-none">
      {/* Messages Area */}
      <div
        ref={messagesContainerRef}
        className="min-h-0 flex-1 overflow-y-auto overscroll-contain scrollbar-thin p-3 sm:p-4 md:p-6"
        role="log"
        aria-live="polite"
        aria-relevant="additions text"
        aria-label="Lịch sử hội thoại"
      >
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
            {messages.map((message) =>
              message.isError ? (
                <div
                  key={message.id}
                  role="alert"
                  className="flex items-start gap-2 sm:gap-3"
                >
                  <div className="rounded-2xl rounded-tl-sm border border-border bg-muted px-4 py-3 text-sm text-muted-foreground">
                    <p>{message.content}</p>
                    {message.retryQuestion && (
                      <button
                        type="button"
                        onClick={() => handleRetry(message.retryQuestion!, message.id)}
                        className="mt-2 inline-flex items-center gap-1.5 rounded-md font-medium text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      >
                        <RotateCcw className="h-3.5 w-3.5" />
                        Thử lại
                      </button>
                    )}
                  </div>
                </div>
              ) : (
                <ChatMessage key={message.id} message={message} showDebug={true} />
              ),
            )}
            {chatPhase !== 'idle' && !messages[messages.length - 1]?.isStreaming && <TypingIndicator phase={chatPhase as 'thinking' | 'streaming'} label={statusMessage ?? undefined} />}
            {showFollowUps && followUpChips.length > 0 && (
              <div className="flex flex-wrap gap-2 pl-10 sm:pl-11" aria-label="Gợi ý câu hỏi tiếp theo">
                {followUpChips.map((chip) => (
                  <button
                    key={chip}
                    type="button"
                    onClick={() => handleSendMessage(chip)}
                    className="rounded-full border border-border bg-card px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:border-primary hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    {chip}
                  </button>
                ))}
              </div>
            )}
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
      <div className="relative z-20 shrink-0 overscroll-contain border-t border-border bg-background/90 p-3 backdrop-blur-sm sm:p-4 md:p-6">
        <div className="mx-auto w-full max-w-3xl">
          <ChatInput onSend={handleSendMessage} isBusy={chatPhase !== 'idle'} onStop={handleStop} />
          {isAdmin && (
            <details className="mt-3 rounded-md border border-border/80 bg-muted/20 px-3 py-2 text-xs">
              <summary className="cursor-pointer select-none text-muted-foreground">
                Debug runtime info
              </summary>
              <pre className="mt-2 max-h-56 overflow-auto rounded bg-background p-2 text-[11px] text-foreground">
                {JSON.stringify(debugPayload, null, 2)}
              </pre>
            </details>
          )}
          <p className="mt-2 text-center text-[11px] leading-relaxed text-muted-foreground">
            Thông tin do AI tổng hợp từ tài liệu, quy chế và thông báo của Nhà trường, có thể chưa
            đầy đủ. Vui lòng đối chiếu văn bản gốc.
          </p>
        </div>
      </div>
    </div>
  );
};

export default ChatContainer;
