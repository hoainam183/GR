# Module: `frontend`

Source-verified: 2026-06-24 from `frontend/chat-companion/package.json`, `vite.config.ts`, `src/App.tsx`, `src/main.tsx`, `src/pages/*`, `src/components/**`, `src/services/*`, `src/types/*`, `src/hooks/*`, `src/lib/utils.ts`, `packages/shared/src/index.ts`, root `package.json`, `turbo.json`.

## Purpose

`frontend` contains the React/Vite web client under `frontend/chat-companion/`. It provides:

- Authenticated chat UI with SSE streaming, conversation history, and session management.
- Auth flow (login, register, complete-profile) backed by JWT + HttpOnly refresh-cookie.
- Admin panel: document upload → pipeline (convert/clean/chunk/index) → review/edit, plus overview/users/analytics/feedback/system dashboard tabs.
- Admin-only debug pages: eval dashboard (`/eval`), per-document review (`/admin/documents/:id`).
- Bookmarks and push-notification pages (using `@rag/shared` API client).

The module does not contain backend logic; it consumes the FastAPI backend at `VITE_API_URL` (default `http://localhost:8000`).

## File Map

```text
frontend/
  MODULE.md
  chat-companion/
    package.json              App manifest; scripts: dev / build / build:dev / lint / preview.
    vite.config.ts            Vite 5 config; alias @ -> src; alias @rag/shared -> ../../packages/shared/src/index.ts.
    tsconfig.json / tsconfig.app.json / tsconfig.node.json
    eslint.config.js          ESLint flat config (react-hooks, react-refresh, typescript-eslint).
    tailwind.config.ts        Tailwind CSS config.
    postcss.config.js
    components.json           shadcn/ui component registry.
    index.html                HTML entry point.
    utils/
      logo.png                Static asset (HUST logo PNG).
    src/
      main.tsx                ReactDOM.createRoot → <App />.
      App.tsx                 BrowserRouter route table + RequireAuth / RequireAdmin / RequireNonAdmin guards.
      App.css / index.css     Global/Tailwind styles.
      pages/
        LandingPage.tsx       Public landing (redirects logged-in users to /chat).
        LoginPage.tsx         Credential login; handles ?next= redirect.
        RegisterPage.tsx      Registration form.
        CompleteProfile.tsx   Post-register profile completion.
        Index.tsx             Chat shell: header, resizable sidebar, ChatContainer.
        EvalPage.tsx          Admin: eval dashboard (TanStack Query, getEvalDashboard). (RequireAdmin)
        AdminPage.tsx         Admin: tabbed shell (overview/users/documents/analytics/feedback/system). (RequireAdmin)
        DocumentReview.tsx    Admin: per-doc pipeline step control + markdown/chunk review. (RequireAdmin)
        BookmarksPage.tsx     User: saved answers (uses @rag/shared bookmark API).
        NotificationsPage.tsx User: push notification list (uses @rag/shared notification API).
        NotFound.tsx          404 catch-all.
      components/
        HustLogo.tsx          Inline SVG + src/utils/logo.png wrapper.
        NavLink.tsx           Styled router link.
        NotificationBell.tsx  Bell icon with unread badge; dropdown preview list; uses @rag/shared.
        chat/
          ChatContainer.tsx   Session coordinator: streaming, token buffering (rAF), pending-turn
                              sessionStorage, history load, session-list invalidation.
          ChatMessage.tsx     Renders one message (Markdown, sources, AgentTrace, MessageActionsWeb).
          ChatInput.tsx       Textarea + send button; Enter-to-send, Shift+Enter newline.
          TypingIndicator.tsx Thinking / streaming phase indicator with optional status label.
          MessageActionsWeb.tsx  Copy / bookmark / feedback actions on assistant messages.
        sidebar/
          ConversationSidebar.tsx  Session list (TanStack Query), rename/delete, new-chat button.
        admin/
          FileUploader.tsx    Drag-drop PDF upload (≤5 files, ≤50 MB each), collection + chunking
                              strategy selection, progress bar; calls adminApi.uploadDocuments.
          DocumentList.tsx    Paginated document table with status badges and pipeline actions.
          PipelineProgress.tsx  Visual step indicator for convert/clean/chunk/index.
          MarkdownEditor.tsx  Textarea editor for converted markdown; PUT /admin/documents/:id/markdown.
          ChunkViewer.tsx     Paginated chunk viewer with inline edit/delete/approve.
          MetadataForm.tsx    metadata_overrides editor.
          EmptyState.tsx      Reusable empty-state UI.
          OverviewTab.tsx     Stats cards, usage band, operations summary; GET /admin/stats/overview.
          UsersTab.tsx        Paginated user table, toggle active; GET /admin/stats/users.
          AnalyticsTab.tsx    Composes QueryAnalyticsSection + AgentAnalyticsSection.
          QueryAnalyticsSection.tsx   Query volume, top questions; GET /admin/stats/queries.
          AgentAnalyticsSection.tsx   Agent usage stats; GET /admin/stats/agent.
          FeedbackTab.tsx     Feedback list/topics; GET /admin/stats/feedback/topics.
          SystemTab.tsx       LLM config, API keys (fingerprint-only), env config, crawler
                              trigger/status/run-preview/index; /admin/config/* + /admin/crawler/*.
        trace/
          PipelineTrace.tsx   Renders timings, routing, filters, collection results, fusion weights,
                              context/rerank traces from ChatV3Response metadata.
          AgentTrace.tsx      Renders agent tool_calls, iterations, sub_questions, executor_results.
          DocRow.tsx          Single retrieved-document row (scores, metadata, content preview).
        ui/                   shadcn/Radix primitives (button, input, dialog, tabs, toast, …).
      services/
        chatApi.ts            sendMessageStream (POST /chat/stream SSE), sendMessageV3 (POST /chat/v3),
                              sendMessage (delegates to V3 'auto'), retrievalSearch (POST /retrieval/search),
                              getEvalDashboard (GET /metrics/eval), checkHealth (GET /health),
                              normalizeV3Response, resolveChatIdentity, apiClient (axios, auth interceptors).
        authApi.ts            loginUser, registerUser, getMe; exports UserPublic / TokenResponse types.
        authSession.ts        Session core: ensureSession, ensureAccessToken, refreshSession (single-flight),
                              applyTokenResponse, logoutSession, clearSession, getCurrentSessionUser,
                              installAuthInterceptors (axios), authFetch (credentialed fetch + 401 retry).
        authStorage.ts        In-memory access token + expiry; user in localStorage; legacy
                              localStorage key migration (token / access_token → memory-only).
        sessionApi.ts         getSessions (/sessions/me), getSession, createSession, deleteSession, renameSession.
        adminApi.ts           Full admin document pipeline (upload, list, detail, convert, clean, chunk, index,
                              full pipeline, rollback, markdown CRUD, cleaned CRUD, chunk CRUD, approve,
                              chunk strategy compare/select, pollDocumentStatus);
                              admin stats (overview, users, breakdown, queries, agent, feedback/topics, system);
                              crawler (trigger, status, run chunks, update chunk, index run);
                              config (toggle, LLM get/update, API keys list/create/activate, env get/update);
                              adminClient (axios, auth interceptors).
        notificationDisplay.ts  Display-layer formatters getNotificationDisplayTitle /
                              getNotificationDisplayBody for crawler_update notifications (source-label
                              humanization). Not a network client.
      types/
        chat.ts               Message, UserContext, ChatRequest, RetrievedDocument, CollectionScore,
                              FilterInfo, CollectionResult, ChatResponse, AgentToolCall, AgentTracePayload,
                              ChatV3Response, Session, Turn.
        admin.ts              DocumentStatus, CollectionName, DocumentDetail, DocumentListResponse,
                              ChunkPreview, ChunksResponse, MarkdownContent, CleanedContent,
                              PipelineStep, ConverterOption, ChunkerOption, ChunkStrategySummary.
                              Also exports COLLECTION_CHUNKER_MAP and CHUNKER_ALTERNATIVES constants.
        adminStats.ts         OverviewStats, AdminUsersResponse, UserBreakdown, QueryAnalytics,
                              AgentAnalytics, FeedbackTopics, SystemStats, CrawlerStatus, LLMConfig,
                              ApiKeyListResponse, EnvConfigResponse, and related sub-types.
      hooks/
        use-mobile.tsx        useIsMobile (window resize breakpoint).
        use-toast.ts          shadcn toast state hook.
        useAdminFetch.ts      Generic data-fetching hook (loading/error/empty, toast on error).
        useResizableSidebar.ts  Persistent sidebar width (localStorage), collapse/expand, ref+callbacks.
        useSmartScroll.ts     Auto-scroll-to-bottom with "scroll button" show/hide logic.
      lib/
        utils.ts              cn() (clsx + twMerge) and parseUtcDate (appends Z for naive UTC timestamps).
      vite-env.d.ts           Vite ImportMeta env type.

packages/shared/src/          @rag/shared workspace package (shared between web + mobile):
  index.ts                    Re-exports types, API helpers, normalizeV3Response, stores.
  api/                        createApiClient, sendMessage/V3, auth, sessions, bookmarks, notifications, lookup.
  types/                      chat.ts, auth.ts, mobile.ts (shared type definitions).
  stores/                     createAuthStore, createChatStore (Zustand-style factory stores).
  utils/                      cleanText, sanitizeUserContext, normalizeV3Response, mapSourceToRetrieved, API_PATHS.
  profileOptions.ts           COHORT_OPTIONS, MAJOR_OPTIONS, findMajorOptionByCode.
```

## Framework / Build / Run Commands

The monorepo root (`RAG_v2/`) uses npm workspaces + Turborepo:

```bash
# From RAG_v2/ root
npm install                        # install all workspace deps (including @rag/shared)
npm run dev:web                    # turbo run dev --filter=chat-companion  (Vite on port 8080)
npm run build                      # turbo run build (builds shared then chat-companion)
npm run lint                       # turbo run lint

# Or from inside frontend/chat-companion/
npm run dev                        # vite --host ::  --port 8080
npm run build                      # vite build (production)
npm run build:dev                  # vite build --mode development
npm run lint                       # eslint .
npm run preview                    # vite preview (serve dist/)
```

`VITE_API_URL` is the only required env var (defaults to `http://localhost:8000`). Only `VITE_*` prefixed values are exposed to the browser bundle.

## Routing / Pages

`App.tsx` defines all routes with `BrowserRouter`:

| Route | Component | Guard |
|---|---|---|
| `/` | `LandingPage` | none |
| `/chat` | `Index` | `RequireNonAdmin` |
| `/chat/:sessionId` | `Index` | `RequireNonAdmin` |
| `/login` | `LoginPage` | none |
| `/register` | `RegisterPage` | none |
| `/complete-profile` | `CompleteProfile` | `RequireAuth` |
| `/eval` | `EvalPage` | `RequireAdmin` |
| `/admin` | `AdminPage` | `RequireAdmin` |
| `/admin/documents/:id` | `DocumentReview` | `RequireAdmin` |
| `/bookmarks` | `BookmarksPage` | `RequireAuth` |
| `/notifications` | `NotificationsPage` | `RequireAuth` |
| `*` | `NotFound` | none |

**Guard logic (`App.tsx`):**

- `RequireAuth`, `RequireAdmin`, and `RequireNonAdmin` call `getCurrentSessionUser()` synchronously for an optimistic render; then `ensureSession()` runs once on mount (guarded by a `verified` ref to prevent repeated calls within the same component lifetime).
- While the first check is in flight and no cached user exists, the guard renders `null` (blank screen).
- No valid session → redirect to `/login?next=<encoded path+search>`.
- `RequireAdmin` additionally checks `user.role !== 'admin'`; non-admin redirects to `/chat`.
- `RequireNonAdmin` additionally checks `user.role === 'admin'`; admin redirects to `/admin`.

## API Client + SSE Streaming Integration

### Axios clients

Three separate axios instances, each installed with `installAuthInterceptors`:

| Instance | Default `baseURL` | Used by |
|---|---|---|
| `apiClient` in `chatApi.ts` | `VITE_API_URL` | chat, retrieval, eval, health |
| `apiClient` in `sessionApi.ts` | `VITE_API_URL` | session CRUD |
| `adminClient` in `adminApi.ts` | `VITE_API_URL` | all admin endpoints |
| `apiClient` in `authApi.ts` | `VITE_API_URL` | login/register/me |

All instances use `withCredentials: true`. The request interceptor calls `ensureAccessToken()` (refreshes via HttpOnly cookie if the memory token is expiring); the response interceptor retries once on 401 after a single-flight `refreshSession()`.

### SSE streaming (`/chat/stream`)

`sendMessageStream` in `chatApi.ts` uses the native Fetch API via `authFetch` (not axios), so it can stream the `ReadableStream` response body. The `authFetch` wrapper attaches the Bearer token and handles one 401-refresh retry.

**SSE event types consumed:**

| `type` field | Payload fields | Action |
|---|---|---|
| `session` | `session_id` | Fires `onSessionId` handler; triggers URL navigation to `/chat/:sessionId`. |
| `token` | `delta` | Appends to answer; buffered in `tokenBufferRef` and flushed via `requestAnimationFrame` in `ChatContainer`. |
| `status` | `stage`, `message` | Updates status label below the typing indicator. |
| `metadata` | Full `ChatV3Response` shape | Fires `onMetadata`; processed by `normalizeV3Response`. |
| `error` | `error` | Fires `onError`; throws after the current event. |
| `done` | — | Fires `onDone`; terminates the read loop. |
| `[DONE]` (raw string) | — | Terminates the read loop. |

Non-JSON payloads are silently skipped (`console.warn`).

### Non-streaming endpoint

`sendMessageV3` calls `POST /chat/v3` via axios with `mode: 'auto' | 'rag' | 'agent'`. `sendMessage` is a thin wrapper that delegates to `sendMessageV3` with `mode: 'auto'`; it is not used by the main chat UI (which always streams), but is used by `TracePage`.

## Response Normalizer (`normalizeV3Response`)

`normalizeV3Response(payload, fallbackSessionId)` in `chatApi.ts` is the canonical shape adapter. It maps a raw backend JSON payload (or an SSE `metadata` event) into `ChatV3Response`. Key normalization points:

- `retrieved_documents` ← `payload.retrieved_documents` or `payload.sources` (both arrays map through `mapSourceToRetrieved`).
- Each `RetrievedDocument.score` is `rerank_score ?? hybrid_score ?? score` (final effective score for display).
- `model_name` ← `payload.model_name` or `payload.mode`.
- `intent` ← `payload.intent` or `payload.route` (fallback `'rag'`).
- `tool_calls` ← `payload.tool_calls` or `payload.agent_trace.tool_calls`.
- `tools_used` ← `payload.tools_used` or `payload.agent_trace.tool_names_sequence`.
- All missing/wrong-type fields default to safe values; no throws.

The `@rag/shared` package has its own copy of `normalizeV3Response` (in `packages/shared/src/utils/`) for use by the mobile client. The web client uses the local copy in `chatApi.ts`.

**`RetrievedDocument` shape contract:**

```ts
interface RetrievedDocument {
  rank: number;
  content: string;
  score: number;           // rerank_score ?? hybrid_score ?? score
  hybrid_score?: number;
  rerank_score?: number;
  vector_score?: number;
  keyword_score?: number;
  collection?: string;
  metadata: Record<string, unknown>;
}
```

## Admin Upload Flow

1. `FileUploader` (`components/admin/FileUploader.tsx`) accepts PDF files (drag-drop or browse; max 5 files, 50 MB each), a collection selector (`ctdt | quydinh | kehoach | stsv | test`), and an optional chunking strategy.  
   Strategy defaults are driven by `COLLECTION_CHUNKER_MAP` and alternatives from `CHUNKER_ALTERNATIVES` in `types/admin.ts`.
2. On submit → `adminApi.uploadDocuments(files, collection, strategy?, undefined, onProgress)` → `POST /admin/documents` (multipart/form-data). Upload progress tracked via axios `onUploadProgress`.
3. Returns `DocumentDetail[]`; the `onUploaded` callback refreshes `AdminPage`'s document list.
4. `DocumentReview` (`/admin/documents/:id`) drives the staged pipeline:
   - **Convert**: `POST /admin/documents/:id/convert?converter=` → polls status.
   - **Clean**: `POST /admin/documents/:id/clean`.
   - **Chunk**: `POST /admin/documents/:id/chunk?strategy=`.
   - **Index**: `POST /admin/documents/:id/index`.
   - **Full pipeline**: `POST /admin/documents/:id/pipeline` (one-shot).
   - **Rollback**: `POST /admin/documents/:id/rollback`.
   - Markdown edit: `GET/PUT /admin/documents/:id/markdown`.
   - Cleaned content edit: `GET/PUT /admin/documents/:id/cleaned`.
   - Chunk review/edit/delete/approve: `GET /admin/documents/:id/chunks`, `PATCH /admin/documents/:id/chunks/:chunkId`, `DELETE /admin/documents/:id/chunks/:chunkId`, `PUT /admin/documents/:id/chunks`.
   - Chunk strategy comparison: `GET /admin/documents/:id/chunk-strategies`, `POST /admin/documents/:id/chunks/select`.
5. `pollDocumentStatus` in `adminApi.ts` polls `GET /admin/documents/:id` every 5 s (max 60 attempts) until the document reaches a target status or `'failed'`.

## State / Auth

**Token storage:**
- Access token in memory (`memoryToken` module-level variable in `authStorage.ts`). Never written to localStorage; legacy `localStorage.token` / `localStorage.access_token` values are read once on first `getStoredToken()` call (migration), then removed.
- User profile object cached in `localStorage` under the key `'user'`.
- Refresh token is an HttpOnly cookie managed by the backend; the frontend never reads it directly.

**Auth state machine:**
- `ensureSession()` — returns cached user if memory token is valid; otherwise calls `POST /auth/refresh` (single-flight via `refreshPromise`) and returns the user from the refresh response (no extra `/auth/me` round-trip).
- `logoutSession()` — calls `POST /auth/logout` (fire-and-forget), then `clearStoredAuth()`.
- Both axios interceptors and `authFetch` perform exactly one refresh+retry on 401. Further failure clears the session.

**Chat state (`ChatContainer`):**
- `messages: Message[]` — rendered message list.
- `chatPhase: 'idle' | 'thinking' | 'streaming'` — controls input disabling and `TypingIndicator`.
- `activeSessionId` — tracks current session; mirrors URL `sessionId` param.
- Pending turns persisted to `sessionStorage` under key `pending-chat:<sessionId>` so in-progress sends survive navigation events. Cleared when `metadata` or `error` events arrive, or when the session history loads saved turns.
- Token deltas are buffered in `tokenBufferRef` and flushed with `requestAnimationFrame` to batch React re-renders during streaming bursts.
- TanStack Query (`queryKey: ['sessions', ownerId]`) caches the sidebar session list; invalidated on new session creation and after each metadata/session event.

**No global state manager.** All state is local React state + TanStack Query cache + module-level `authStorage` vars. The `@rag/shared` package ships Zustand-style store factories (`createAuthStore`, `createChatStore`) for the mobile client; the web app does not use them.

## Maintenance Notes

- **Backend chat schema change** (`schemas/chat.py`, `api/response_mapper.py`): update `types/chat.ts` (local), `chatApi.ts` (`normalizeV3Response`, `mapSourceToRetrieved`), `components/trace/PipelineTrace.tsx` / `AgentTrace.tsx`, and `ChatContainer`'s `applyResponseMetadata`. Also check `packages/shared/src/utils/` if the shared normalizer diverges.
- **New SSE event type**: add a branch in the `sendMessageStream` event loop in `chatApi.ts` and a corresponding handler in `ChatContainer.handleSendMessage`.
- **Admin document schema change** (`schemas/document.py`): update `types/admin.ts` (`DocumentDetail`, `ChunkPreview`, pipeline status strings) and components in `components/admin/`.
- **Admin stats schema change**: update `types/adminStats.ts` and the matching tab component.
- **New backend `/auth/*` endpoint**: update `authApi.ts` and/or `authSession.ts`.
- **New collection**: add to `COLLECTION_CHUNKER_MAP` and `CHUNKER_ALTERNATIVES` in `types/admin.ts`, and to the `COLLECTIONS` constant in `FileUploader.tsx` and `RetrievalPage.tsx`.
- **`@rag/shared` type drift**: `types/chat.ts` duplicates several shared types for local use; keep in sync with `packages/shared/src/types/chat.ts` if either side changes.
- `notificationDisplay.ts` contains display-only string transforms; update it if the backend changes `crawler_update` notification body format.

## Useful Checks

```bash
# From RAG_v2/ root (Turborepo):
npm run dev:web           # start Vite dev server (port 8080)
npm run build             # full workspace build (shared → chat-companion)
npm run lint              # lint all workspaces

# From frontend/chat-companion/ directly:
npm run dev               # Vite dev server
npm run build             # production build → dist/
npm run lint              # ESLint (react-hooks, react-refresh, typescript-eslint)
npm run preview           # serve dist/ for manual inspection
```
