import { useState, useRef, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import type { Message, UserContext } from '@/types/chat';
import { sendMessage, resolveChatIdentity } from '@/services/chatApi';
import { getSession } from '@/services/sessionApi';
import ChatMessage from './ChatMessage';
import ChatInput from './ChatInput';
import TypingIndicator from './TypingIndicator';
import type { UserPublic } from '@/services/authApi';

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
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
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

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading, scrollToBottom]);

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
    setIsLoading(false);

    if (!sessionIdProp) return;

    setIsLoadingHistory(true);
    getSession(sessionIdProp)
      .then(({ turns }) => {
        const loaded: Message[] = turns.flatMap((t) => [
          {
            id: `user-${t.turn_id}`,
            role: 'user' as const,
            content: t.question,
            timestamp: new Date(t.timestamp),
          },
          {
            id: `assistant-${t.turn_id}`,
            role: 'assistant' as const,
            content: t.answer,
            timestamp: new Date(t.timestamp),
            reflectedQuestion: t.reflected_question ?? undefined,
            timingsMs: t.timings_ms,
            sources: t.sources,
            collectionScores: t.collection_scores,
            targetCollections: t.target_collections,
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
    setIsLoading(true);

    try {
      // Build history from existing messages (last 6 turns)
      const historyForApi = messages.slice(-6).map((m) => ({
        role: m.role,
        content: m.content,
      }));
      const response = await sendMessage(
        content,
        historyForApi,
        5,
        capturedSessionId,
        explicitUserContext,
        explicitUserId,
      );

      // Component was unmounted (e.g. logout) — bail out entirely
      if (!isMountedRef.current) return;

      // User navigated to a different session while this request was in flight.
      // The backend already persisted the turn; it will show on next refresh/visit.
      // Do NOT touch the current session's UI.
      if (activeSessionIdRef.current !== capturedSessionId &&
          // Exception: capturedSessionId was undefined (new chat) and the URL
          // has not yet been updated — let the navigate below handle it.
          capturedSessionId !== undefined) {
        return;
      }

      // Update session state + URL if this is the first turn (new chat)
      if (response.session_id && response.session_id !== capturedSessionId) {
        // Suppress the history-reload effect that would otherwise clear messages
        suppressNextHistoryLoad.current = true;
        setActiveSessionId(response.session_id);
        navigate(`/chat/${response.session_id}`, { replace: true });
      }

      // Refresh the sidebar conversation list
      if (resolvedIdentity.userId) {
        queryClient.invalidateQueries({ queryKey: ['sessions', resolvedIdentity.userId] });
      }

      // Add assistant message with sources
      const assistantMessage: Message = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: response.answer,
        timestamp: new Date(),
        sources: response.retrieved_documents,
        targetCollections: response.target_collections,
        collectionScores: response.collection_scores,
        reflectedQuestion: response.reflected_question,
        timingsMs: response.timings_ms,
      };

      setMessages((prev) => [...prev, assistantMessage]);
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
      // If the user has switched sessions, their new session manages its own loading state.
      if (isMountedRef.current && activeSessionIdRef.current === capturedSessionId) {
        setIsLoading(false);
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
            {isLoading && <TypingIndicator />}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input Area */}
      <div className="border-t border-border bg-background/80 backdrop-blur-sm p-4 md:p-6">
        <div className="mx-auto max-w-3xl">
          <ChatInput onSend={handleSendMessage} disabled={isLoading} />
          <details className="mt-3 rounded-md border border-border/80 bg-muted/20 px-3 py-2 text-xs">
            <summary className="cursor-pointer select-none text-muted-foreground">
              Debug user info
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
