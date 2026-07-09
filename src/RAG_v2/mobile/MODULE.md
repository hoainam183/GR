# Module: `mobile`

Ứng dụng di động (React Native + Expo, TypeScript) cho chatbot RAG. Dùng lại API/store/type từ package `@rag/shared`; hỗ trợ chat streaming, tra cứu, bookmark, thông báo đẩy và hồ sơ sinh viên.

## Cấu trúc

### `App.tsx`, `index.ts`
Điểm vào Expo: ráp provider (React Query, theme, gesture handler) và gắn `RootNavigator`.

### `src/navigation/`
Cấu trúc điều hướng React Navigation: `RootNavigator` (chọn Auth vs Main theo trạng thái đăng nhập), `MainTabNavigator` (tab dưới), và các stack `AuthStack`, `ChatStack`, `LookupStack`, `BookmarkStack`, `NotificationStack`, `ProfileStack`.

### `src/screens/`
Màn hình theo miền: `chat/` (`ChatScreen`, `SessionListScreen`), `auth/` (`LoginScreen`, `RegisterScreen`), `bookmarks/`, `notifications/`, `lookup/` (`LookupScreen`), `profile/` (`ProfileScreen`, `EditProfileScreen`).

### `src/components/`
- `chat/` — UI hội thoại (`MessageBubble`, `ChatInput`, `StreamingText`, `MarkdownDisplay`, `SourceBottomSheet`, `MessageActions`, `TypingIndicator`).
- `common/` — dùng chung (`ErrorBoundary`, `LoadingSpinner`, `EmptyState`, `NetworkBanner`).

### `src/hooks/`
`useStreamChat` (nhận SSE streaming), `useAuth`, `useProfile`.

### `src/services/`
`api.ts` (client HTTP), `offlineCache.ts` (cache MMKV), `pushNotifications.ts` (Expo notifications), `secureStorage.ts` (expo-secure-store).

### `src/stores/`, `src/theme/`, `src/utils/`
Store Zustand cục bộ (`authStore`, `chatStore`), theme (`theme.tsx`), tiện ích (`constants`, `haptics`, `sourceText`).

### Cấu hình chính
`package.json` (Expo SDK 54, RN 0.81, `@rag/shared`), `app.json`, `eas.json`, `metro.config.js`, `babel.config.js`, `tsconfig.json`, `.env.example`.
