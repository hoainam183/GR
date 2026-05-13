/**
 * Chat API functions — platform-agnostic (no SSE streaming).
 *
 * SSE streaming is implemented per-platform:
 *   - Web:    ReadableStream in frontend/chat-companion
 *   - Mobile: react-native-sse in mobile/src/hooks/useStreamChat.ts
 */

import type { AxiosInstance } from 'axios';
import type { ChatRequest, ChatV3Response, UserContext } from '../types/chat';
import { normalizeV3Response } from '../utils/normalize';
import { sanitizeUserContext, cleanText } from '../utils/sanitize';
import { API_PATHS } from '../utils/constants';

// ─── Identity resolution ─────────────────────────────────────────────────────

type StoredUserShape = UserContext & {
  email?: string | null;
  username?: string | null;
};

export interface ResolvedChatIdentity {
  userContext?: UserContext;
  userId?: string;
  source: 'explicit' | 'stored' | 'mixed' | 'none';
}

/**
 * Resolve chat identity from explicit params + optional stored user.
 * `storedUser` is injected by the platform (localStorage / SecureStore).
 */
export const resolveChatIdentity = (
  userContext?: UserContext,
  userId?: string,
  storedUser?: StoredUserShape | null,
): ResolvedChatIdentity => {
  const explicitContext = sanitizeUserContext(userContext);
  const explicitUserId = cleanText(userId);

  const fallbackContext = storedUser
    ? sanitizeUserContext({
        student_id: storedUser.student_id,
        cohort: storedUser.cohort,
        major: storedUser.major,
        major_code: storedUser.major_code,
        full_name: storedUser.full_name,
      })
    : undefined;
  const fallbackUserId =
    cleanText(storedUser?.email) ||
    cleanText(storedUser?.username) ||
    cleanText(storedUser?.student_id);

  const resolvedContext = explicitContext || fallbackContext;
  const resolvedUserId = explicitUserId || fallbackUserId;

  const hasExplicit = Boolean(explicitContext || explicitUserId);
  const hasFallback = Boolean(fallbackContext || fallbackUserId);

  let source: ResolvedChatIdentity['source'] = 'none';
  if (hasExplicit && hasFallback && (!explicitContext || !explicitUserId)) {
    source = 'mixed';
  } else if (hasExplicit) {
    source = 'explicit';
  } else if (hasFallback) {
    source = 'stored';
  }

  return { userContext: resolvedContext, userId: resolvedUserId, source };
};

// ─── Chat endpoints ──────────────────────────────────────────────────────────

/**
 * Send a message via /chat/v3 (non-streaming, smart routing).
 */
export const sendMessageV3 = async (
  client: AxiosInstance,
  question: string,
  history: Array<{ role: 'user' | 'assistant'; content: string }> = [],
  topK: number = 5,
  mode: 'auto' | 'rag' | 'agent' = 'auto',
  sessionId?: string,
  userContext?: UserContext,
  userId?: string,
  storedUser?: StoredUserShape | null,
): Promise<ChatV3Response> => {
  const identity = resolveChatIdentity(userContext, userId, storedUser);

  const response = await client.post(API_PATHS.CHAT_V3, {
    question,
    mode,
    top_k: topK,
    history,
    session_id: sessionId,
    user_context: identity.userContext,
    user_id: identity.userId,
  } as ChatRequest);

  return normalizeV3Response(
    response.data as Record<string, unknown>,
    sessionId,
  );
};

/**
 * Send a message via /chat/v3 with auto routing (convenience wrapper).
 */
export const sendMessage = async (
  client: AxiosInstance,
  question: string,
  history: Array<{ role: 'user' | 'assistant'; content: string }> = [],
  topK: number = 5,
  sessionId?: string,
  userContext?: UserContext,
  userId?: string,
  storedUser?: StoredUserShape | null,
): Promise<ChatV3Response> => {
  return sendMessageV3(
    client,
    question,
    history,
    topK,
    'auto',
    sessionId,
    userContext,
    userId,
    storedUser,
  );
};

/**
 * Health check — GET /health
 */
export const checkHealth = async (client: AxiosInstance): Promise<boolean> => {
  try {
    const response = await client.get(API_PATHS.HEALTH);
    return response.data.status === 'healthy';
  } catch {
    return false;
  }
};
