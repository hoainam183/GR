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
  BookmarkUpdateRequest,
  BookmarkFolderRenameRequest,
  FeedbackCreateRequest,
  FeedbackResponse,
  FeedbackStats,
  LookupDocument,
  SuggestedQuestion,
  NotificationItem,
  NotificationSubscribeRequest,
  NotificationUnsubscribeRequest,
  NotificationUnreadCount,
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
  getBookmarkByTurn,
  updateBookmark,
  deleteBookmark,
  listBookmarkFolders,
  createBookmarkFolder,
  renameBookmarkFolder,
  deleteBookmarkFolder,
  submitFeedback,
  deleteFeedback,
  getFeedback,
  getFeedbackStats,
  listAllFeedback,
  lookupCTDT,
  lookupRegulations,
  lookupCalendar,
  lookupCompare,
  getSuggestedQuestions,
  listNotifications,
  getUnreadCount,
  markNotificationRead,
  markAllNotificationsRead,
  deleteNotification,
  subscribeNotifications,
  unsubscribeNotifications,
} from './api';
export type { ApiClientConfig, ResolvedChatIdentity } from './api';

// ─── Utils ───────────────────────────────────────────────────────────────────
export {
  cleanText,
  sanitizeUserContext,
  normalizeV3Response,
  mapSourceToRetrieved,
  normalizeRetrievedDocuments,
  isDisplayableRetrievedDocument,
  API_PATHS,
  CLARIFY_SENTINEL,
} from './utils';

export {
  COHORT_OPTIONS,
  MAJOR_OPTIONS,
  findMajorOptionByCode,
} from './profileOptions';
export type { MajorOption } from './profileOptions';

// ─── Stores ──────────────────────────────────────────────────────────────────
export { createAuthStore, createChatStore } from './stores';
export type {
  AuthState,
  AuthStore,
  ChatState,
  ChatStore,
  ChatPhase,
} from './stores';
