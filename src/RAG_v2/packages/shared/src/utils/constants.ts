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
  SESSIONS_ME: '/sessions/me',
  SESSION: '/session',
  BOOKMARKS: '/bookmarks',
  BOOKMARK_FOLDERS: '/bookmark-folders',
  FEEDBACK: '/feedback',
  LOOKUP_CTDT: '/lookup/ctdt',
  LOOKUP_REGULATIONS: '/lookup/regulations',
  LOOKUP_CALENDAR: '/lookup/calendar',
  LOOKUP_COMPARE: '/lookup/compare',
  CHAT_SUGGEST: '/chat/suggest',
  NOTIFICATIONS: '/notifications',
  NOTIFICATION_SUBSCRIBE: '/notifications/subscribe',
} as const;

/** Sentinel value used to signal clarification requests */
export const CLARIFY_SENTINEL = '[CLARIFY]';
