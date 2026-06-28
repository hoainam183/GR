# Module: `mobile`

Source-verified: 2026-06-24 from `mobile/App.tsx`, `mobile/index.ts`, `mobile/package.json`, `mobile/app.json`, `mobile/babel.config.js`, `mobile/tsconfig.json`, `mobile/src/navigation/**`, `mobile/src/screens/**`, `mobile/src/hooks/**`, `mobile/src/services/**`, `mobile/src/stores/**`, `mobile/src/components/**`, `mobile/src/theme/theme.tsx`, `mobile/src/utils/constants.ts`.

## Purpose

`mobile` is the Expo/React Native app for HUST Assistant. It provides a student-facing chat interface (streaming RAG answers), a document lookup tool, bookmarks, push notifications, and a profile editor. It consumes `@rag/shared` for API client factories, type definitions, normalizers, and Zustand store factories; all native storage, navigation, and UX belong to this module.

The app targets HUST students: chat answers are framed around BKHN regulations, academic calendars, and curricula (`quydinh`, `ctdt`).

## File Map

```text
mobile/
  App.tsx                  Root component: GestureHandlerRootView > SafeAreaProvider >
                             QueryClientProvider > AppThemeProvider > AppChrome (ErrorBoundary,
                             StatusBar, NetworkBanner, RootNavigator) + Toast.
  index.ts                 registerRootComponent(App) — Expo entry point.
  app.json                 Expo SDK config: slug "mobile", newArchEnabled, portrait,
                           plugins: [expo-secure-store, expo-notifications].
  package.json             Scripts: start / android / ios / web / typecheck.
  babel.config.js          babel-preset-expo + react-native-worklets/plugin.
  tsconfig.json            Extends expo/tsconfig.base, strict: true.
  .env.example             Documents EXPO_PUBLIC_API_BASE_URL (LAN IP).
  MOBILE_PLAN.md           Planning notes (non-runtime).
  assets/                  icon.png, adaptive-icon.png, splash-icon.png, favicon.png.
  src/
    navigation/
      RootNavigator.tsx    Auth-gate: loading spinner → AuthStack or MainTabNavigator.
      MainTabNavigator.tsx Bottom-tabs: ChatTab, LookupTab, BookmarkTab,
                           NotificationTab (unread badge), ProfileTab.
      AuthStack.tsx        Login → Register (native-stack, no header).
      ChatStack.tsx        SessionList (home) → Chat (slide_from_right).
      LookupStack.tsx      Single-screen stack for LookupScreen.
      BookmarkStack.tsx    BookmarkList → BookmarkDetail.
      NotificationStack.tsx NotificationList → NotificationDetail.
      ProfileStack.tsx     Profile → EditProfile.
    screens/
      auth/
        LoginScreen.tsx    react-hook-form + zod; calls useAuth().login with client_type 'mobile'.
        RegisterScreen.tsx Registration form.
      chat/
        SessionListScreen.tsx  Lists sessions via getMySessions(@rag/shared); offline cache
                               via CACHE_KEYS.sessions; FAB navigates to Chat.
        ChatScreen.tsx     Main chat UI: FlatList (inverted), useStreamChat, token-buffer
                           flush (50 ms timer), SourceBottomSheet, suggested questions
                           from getSuggestedQuestions (cached). Loads history via
                           getSession + normalizeRetrievedDocuments.
      lookup/
        LookupScreen.tsx   Mode tabs (ctdt/regulations/calendar/compare); calls
                           lookupCTDT, lookupRegulations, lookupCalendar, lookupCompare
                           from @rag/shared; compare mode has cohort1/cohort2 selectors.
      bookmarks/
        BookmarkListScreen.tsx
        BookmarkDetailScreen.tsx
      notifications/
        NotificationListScreen.tsx  Lists notifications; manages Expo push toggle
                                    (subscribeNotifications / unsubscribeNotifications);
                                    mark-read, mark-all-read, delete via @rag/shared helpers.
        NotificationDetailScreen.tsx
      profile/
        ProfileScreen.tsx   Shows user info + appearance (system/light/dark) picker;
                            logout.
        EditProfileScreen.tsx
    components/
      chat/
        ChatInput.tsx       Compose bar with send button.
        MessageBubble.tsx   User/assistant bubbles; taps sources → SourceBottomSheet.
        MessageActions.tsx  Long-press actions on assistant messages.
        MarkdownDisplay.tsx react-native-markdown-display wrapper.
        StreamingText.tsx   Animated text for live token display.
        TypingIndicator.tsx Animated dots for "thinking"/"streaming" phases.
        SourceBottomSheet.tsx @gorhom/bottom-sheet panel listing retrieved documents.
      common/
        ErrorBoundary.tsx
        EmptyState.tsx
        LoadingSpinner.tsx
        NetworkBanner.tsx   @react-native-community/netinfo offline banner.
    hooks/
      useAuth.ts           Session restore (getMe → cached profile → refresh → clear);
                           login (client_type 'mobile'); logout (POST /auth/logout).
      useProfile.ts        Derives displayName (last word of full_name), subtitle
                           (major · cohort), studentId, majorCode from authStore.
      useStreamChat.ts     Opens POST /chat/stream via react-native-sse; parses typed SSE
                           events (session/token/status/metadata/done/error); on pre-first-
                           token error: refresh + retry once, then fallback to
                           sendMessageV3 (/chat/v3).
    services/
      api.ts               createApiClient(@rag/shared, baseURL, getToken); single-flight
                           refreshAccessToken (POST /auth/refresh, client_type 'mobile');
                           401-interceptor retries once then clears auth.
      secureStorage.ts     expo-secure-store: access_token, refresh_token, user_profile,
                           current_session_id (setToken, getToken, getRefreshToken,
                           clearTokens, setUserProfile, getUserProfile, clearAll).
      offlineCache.ts      react-native-mmkv (id 'rag-mobile-cache'); falls back to
                           in-memory Map in Expo Go (ExecutionEnvironment.StoreClient)
                           or on MMKV init failure. CACHE_KEYS: bookmarks:v1,
                           sessions:v1, suggestions:v1. Also used by theme (appearance:theme:v1)
                           and pushNotifications (notifications:expo-push-token:v1,
                           notifications:push-enabled:v1).
      pushNotifications.ts expo-notifications; unsupported on web and Android Expo Go.
                           registerDeviceForPushNotifications: sets Android channel,
                           requests permission, calls getExpoPushTokenAsync (EAS projectId
                           from Constants.easConfig?.projectId). Exports
                           PushPermissionDeniedError, PushNotificationsUnavailableError.
    stores/
      authStore.ts         createAuthStore(@rag/shared); subscribe syncs token/profile
                           changes to SecureStore. Exports authStore (vanilla) +
                           useAuthStore (React hook).
      chatStore.ts         createChatStore(@rag/shared); no persistence. Exports
                           chatStore + useChatStore.
    theme/
      theme.tsx            AppThemeProvider + useAppTheme. ThemePreference: system/light/dark
                           (persisted via MMKV). AppColors interface (23 tokens: background,
                           canvas, card, foreground, primary, destructive, chatUser,
                           chatAssistant, tabBar, …). Builds navigationTheme for
                           NavigationContainer.
    utils/
      constants.ts         API_BASE_URL: EXPO_PUBLIC_API_BASE_URL (env) → 10.0.2.2:8000
                           (Android) → localhost:8000.
      haptics.ts           expo-haptics thin wrappers.
```

## Framework / Build / Run

- **Expo SDK ~54**, React Native 0.81.5, React 19.1 (`newArchEnabled: true`)
- **React Navigation 7**: `@react-navigation/native-stack` + `@react-navigation/bottom-tabs`
- **TanStack Query v5** (`QueryClient` in `App.tsx`: retry 2, staleTime 5 min default)
- **Zustand v5** stores wired from `@rag/shared` factories
- **Styling**: React Native `StyleSheet` + custom `AppThemeProvider` (light/dark, `AppColors` tokens). No NativeWind, no Tailwind — `tailwind.config.ts` was deleted and is confirmed absent; there is no `nativewind` dependency.
- **Icons**: `@expo/vector-icons` (Ionicons — note: not listed in `package.json` devDependencies; it ships with `expo`)

```bash
# Run dev server (choose platform):
npm run start        # Expo Go / dev client (QR)
npm run android      # Android emulator
npm run ios          # iOS simulator
npm run web          # browser

# Type-check:
npm run typecheck
# or from workspace root:
npm run typecheck --workspace=mobile
```

Set `EXPO_PUBLIC_API_BASE_URL` in `mobile/.env` (copy from `.env.example`) for physical devices.

## Navigation / Screens

```
RootNavigator (NavigationContainer + theme)
  ├── AuthStack (unauthenticated)
  │     Login → Register
  └── MainTabNavigator (authenticated, bottom tabs)
        ChatTab     → ChatStack:  SessionList → Chat
        LookupTab   → LookupStack: LookupScreen
        BookmarkTab → BookmarkStack: BookmarkList → BookmarkDetail
        NotificationTab → NotificationStack: NotificationList → NotificationDetail
        ProfileTab  → ProfileStack: Profile → EditProfile
```

Tab bar is hidden (display: 'none') when focused route is `Chat` (inside ChatTab) or `EditProfile` (inside ProfileTab), via `getFocusedRouteNameFromRoute`.

`RootNavigator` shows an `ActivityIndicator` while `useAuth().isLoading` is true (session restore).

`ChatStack` param list: `SessionList: undefined`, `Chat: { sessionId?: string } | undefined`.

`LookupScreen` modes: `ctdt` (lookupCTDT), `regulations` (lookupRegulations), `calendar` (lookupCalendar), `compare` (lookupCompare with cohort1/cohort2 pickers using `COHORT_OPTIONS` from `@rag/shared`).

## API Client + Streaming Integration

### REST (`src/services/api.ts`)

`apiClient` = `createApiClient({ baseURL: API_BASE_URL, getToken })` from `@rag/shared`.

**401 interceptor** (single-flight refresh):
1. Skip if already retried (`_retry`) or if failing URL includes `/auth/refresh` → call `clearAuthState()`.
2. Otherwise: set `_retry = true`, call `refreshAccessToken()`, retry original request with new bearer token.
3. If refresh returns `null`, call `clearAuthState()` and rethrow.

`refreshAccessToken()` is single-flight (module-level `refreshPromise`):
- POSTs `{ refresh_token, client_type: 'mobile' }` to `/auth/refresh`.
- Persists rotated tokens via `setToken`; updates `authStore`.
- Returns new access token or `null`.

### SSE streaming (`src/hooks/useStreamChat.ts`)

`useStreamChat()` returns `{ startStream, stopStream }`.

`startStream(request: ChatRequest, handlers: StreamChatHandlers)`:
- Opens `POST /chat/stream` via `react-native-sse` `EventSource` with bearer token.
- Parses typed SSE `message` events by `data.type`:
  - `session` → `handlers.onSessionId(data.session_id)`
  - `token` → `handlers.onToken(data.delta)` (sets `receivedFirstToken = true`)
  - `status` → `handlers.onStatus({ stage, message })`
  - `metadata` → `handlers.onMetadata(normalizeV3Response(data, session_id))`
  - `done` → `handlers.onDone()` + close
  - `error` → `handlers.onError(data.error)` + close
  - Non-JSON / heartbeat lines (starts with `:`) are skipped; other plain-text lines are treated as raw token deltas.
- On SSE `error` event **before** first token:
  - If `retryOnAuthError=true`: call `refreshAccessToken()`, then retry `openStream(false)`.
  - If refresh fails or second attempt: `fallbackToNonStreaming()`.
- `fallbackToNonStreaming()` calls `sendMessageV3(apiClient, ...)` → `/chat/v3`, dispatches `onSessionId`/`onToken`/`onMetadata`/`onDone` or `onError`.

**Token batching** in `ChatScreen`: deltas are buffered in `tokenBufferRef` and flushed every ~50 ms via `drainTokenBuffer` to reduce re-renders.

### Auth flow (`src/hooks/useAuth.ts`)

Session restore order (module-level `hasBootstrappedAuth` flag ensures single run):
1. Read SecureStore tokens + cached profile.
2. If both missing → unauthenticated.
3. If token + cached user → set auth immediately (avoids blank screen).
4. Call `getMe(apiClient, token)` to validate and refresh user data.
5. On network error (no `error.response`) with cached user → keep cached auth (offline).
6. On 401 → `refreshAccessToken()` → `getMe` with new token.
7. On any failure → `clearAuth()` + `clearAll()`.

`login`: calls `loginUser(apiClient, { ...data, client_type: 'mobile' })`.
`logout`: POSTs `/auth/logout` (best-effort, swallows errors), then `clearAuth()` + `clearAll()`.

## Response Normalizer — Shape Contract with Backend

`normalizeV3Response` and `normalizeRetrievedDocuments` come from `@rag/shared`. Used in:

- `useStreamChat`: metadata SSE frame → `normalizeV3Response(data, session_id)` → `Partial<ChatV3Response>`.
- `ChatScreen.handleSend`: `onMetadata` callback calls `normalizeRetrievedDocuments(meta.retrieved_documents)` to get `RetrievedDocument[]` for `SourceBottomSheet`.
- `ChatScreen` session load: `normalizeRetrievedDocuments(t.sources)` on each turn.

`ChatV3Response` fields consumed by `ChatScreen`:
- `session_id`, `turn_id`, `answer`, `mode`, `route` (falls back to `intent`), `model_name`, `timings_ms`, `retrieved_documents`.

`Message` (from `@rag/shared`) extended fields written by mobile: `isStreaming: boolean`, `error?: string`, `sources: RetrievedDocument[]`, `sessionId`, `turnId`, `modelName`, `mode`, `route`, `toolsUsed`, `timingsMs`.

## State / Auth

| Store | Factory | Persistence |
|-------|---------|-------------|
| `authStore` | `createAuthStore(@rag/shared)` | SecureStore (subscribe syncs access/refresh tokens + user profile) |
| `chatStore` | `createChatStore(@rag/shared)` | None (in-memory only) |

`authStore` subscription (in `src/stores/authStore.ts`) calls `setToken`/`clearTokens` and `setUserProfile`/`clearUserProfile` whenever `accessToken`, `refreshToken`, or `user` changes.

Theme preference (`system`/`light`/`dark`) is persisted to MMKV key `appearance:theme:v1`.

## Maintenance Notes

- **Backend schema changes**: Update `@rag/shared` types (`ChatV3Response`, `Message`, `Session`, `NotificationItem`, `LookupDocument`, `SuggestedQuestion`). The normalizers (`normalizeV3Response`, `normalizeRetrievedDocuments`) and API helpers (`getSession`, `getMySessions`, `getSuggestedQuestions`, `lookupCTDT`, etc.) live in `@rag/shared`, not in `mobile/src`.
- **New SSE event types**: Add a branch in `useStreamChat.ts` `message` listener.
- **Auth endpoints**: All login/refresh/logout calls must include `client_type: 'mobile'` to get JSON refresh tokens (not web cookies). If the backend rotates the refresh token, the new value comes back as `refresh_token` in the `/auth/refresh` response and must be persisted via `setToken`.
- **Push notifications**: Subscription POSTs `{ expo_push_token, topics: [] }` to `/notifications/subscribe` (via `subscribeNotifications` from `@rag/shared`). The EAS `projectId` must be present in `app.json` (`expo.extra.eas.projectId`) or `eas.json` for production push to work.
- **Styling**: Styling is `StyleSheet` + `AppThemeProvider` only. `AppColors` has 23 named tokens — add new tokens to both `lightColors` and `darkColors` in `src/theme/theme.tsx`. Palette follows the HUST / CTT identity in `DESIGN.md` §2 (`primary` = `--bk-red` `#c02430`, `primaryPressed` = `--bk-red-dark`, `primarySoft` = `--bk-red-tint`); red is an accent (primary actions, user bubble, avatars, FAB, citation left-border), not a wide background. There is no Tailwind/NativeWind setup; `tailwind.config.ts` has been deleted and must not be recreated without also installing `nativewind` and wiring its babel plugin.
- **Offline cache keys**: `CACHE_KEYS` in `offlineCache.ts` are versioned (`v1`). Bump the version (e.g. `v2`) when the cached shape changes to avoid stale-parse errors.
- **MMKV in Expo Go**: `offlineCache.ts` falls back to an in-memory `Map` in `ExecutionEnvironment.StoreClient` (Expo Go). Test MMKV persistence only in a development build.

## Useful Checks

```bash
# Type-check the mobile workspace:
npm run typecheck --workspace=mobile

# Start Expo dev server:
npm run start --workspace=mobile

# Android / iOS:
npm run android --workspace=mobile
npm run ios --workspace=mobile
```
