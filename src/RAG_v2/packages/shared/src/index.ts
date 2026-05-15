/**
 * @rag/shared — shared code between web and mobile.
 *
 * Re-exports types, API client, utilities, and store factories.
 */

// ─── Types ───────────────────────────────────────────────────────────────────
export type {
  Message,
  UserContext,
  ChatRequest,
  RetrievedDocument,
  CollectionScore,
  FilterInfo,
  CollectionResult,
  ChatResponse,
  AgentToolCall,
  AgentTracePayload,
  ChatV3Response,
  Session,
  Turn,
} from './types';

export type {
  RegisterRequest,
  UserPublic,
  LoginRequest,
  TokenResponse,
  Bookmark,
  BookmarkFolder,
  BookmarkCreateRequest,
  FeedbackCreateRequest,
  LookupDocument,
  SuggestedQuestion,
  NotificationItem,
  NotificationSubscribeRequest,
} from './types';

// ─── API ─────────────────────────────────────────────────────────────────────
export {
  createApiClient,
  sendMessage,
  sendMessageV3,
  checkHealth,
  resolveChatIdentity,
  loginUser,
  registerUser,
  getMe,
  getSessions,
  getMySessions,
  getSession,
  createSession,
  createBookmark,
  listBookmarks,
  deleteBookmark,
  listBookmarkFolders,
  createBookmarkFolder,
  submitFeedback,
  lookupCTDT,
  lookupRegulations,
  lookupCalendar,
  lookupCompare,
  getSuggestedQuestions,
  listNotifications,
  markNotificationRead,
  subscribeNotifications,
} from './api';
export type { ApiClientConfig, ResolvedChatIdentity } from './api';

// ─── Utils ───────────────────────────────────────────────────────────────────
export {
  cleanText,
  sanitizeUserContext,
  normalizeV3Response,
  mapSourceToRetrieved,
  API_PATHS,
  CLARIFY_SENTINEL,
} from './utils';

// ─── Stores ──────────────────────────────────────────────────────────────────
export { createAuthStore, createChatStore } from './stores';
export type {
  AuthState,
  AuthStore,
  ChatState,
  ChatStore,
  ChatPhase,
} from './stores';
