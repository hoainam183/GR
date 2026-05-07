/**
 * Shared constants — API path segments and sentinel values.
 */

/** API path constants */
export const API_PATHS = {
  CHAT: '/chat',
  CHAT_V3: '/chat/v3',
  CHAT_STREAM: '/chat/stream',
  HEALTH: '/health',
  AUTH_LOGIN: '/auth/login',
  AUTH_REGISTER: '/auth/register',
  AUTH_ME: '/auth/me',
  AUTH_REFRESH: '/auth/refresh',
  SESSIONS: '/sessions',
  SESSION: '/session',
} as const;

/** Sentinel value used to signal clarification requests */
export const CLARIFY_SENTINEL = '[CLARIFY]';
