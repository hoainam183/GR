export { createApiClient } from './client';
export type { ApiClientConfig } from './client';
export {
  sendMessage,
  sendMessageV3,
  checkHealth,
  resolveChatIdentity,
} from './chatApi';
export type { ResolvedChatIdentity } from './chatApi';
export { loginUser, registerUser, getMe } from './authApi';
export { getSessions, getMySessions, getSession, createSession } from './sessionApi';
export {
  createBookmark,
  listBookmarks,
  deleteBookmark,
  listBookmarkFolders,
  createBookmarkFolder,
} from './bookmarkApi';
export { submitFeedback } from './feedbackApi';
export {
  lookupCTDT,
  lookupRegulations,
  lookupCalendar,
  lookupCompare,
  getSuggestedQuestions,
} from './lookupApi';
export {
  listNotifications,
  markNotificationRead,
  subscribeNotifications,
} from './notificationApi';
