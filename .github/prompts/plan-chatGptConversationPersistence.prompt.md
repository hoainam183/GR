# Plan: ChatGPT-style Conversation Persistence

## TL;DR
Add a persistent conversation sidebar (like ChatGPT) so users can start new chats, see all past conversations, click to reload any conversation, and have the URL reflect the active session (e.g., `/chat/{session_id}`). Backend infrastructure (MongoDB sessions/turns, list/get endpoints) is **already built**; gaps are: user_id not flowing through chat requests, and the entire frontend sidebar + routing is missing.

---

## Phase 1 — Backend: Link sessions to the authenticated user

**Goal:** Every chat turn created by a user gets stored under their user_id so the sidebar can filter by user.

1. **Add `user_id` field to `ChatRequest`** in `src/RAG_v2/schemas/chat.py`  
   Add `user_id: Optional[str] = None` field (the frontend will send `user.email`).

2. **Thread `user_id` into session creation in `api/routes/chat.py`**  
   When the chat route calls `rag_pipeline.query(...)`, pass `user_id=request_body.user_id`.

3. **Pass `user_id` to `mongo_logger.new_session()`** inside `pipeline/rag_pipeline.py`  
   The `query()` method accepts `session_id` already. When it auto-creates a new session (no session_id provided), call `mongo_logger.new_session(user_id=user_id)` instead of `new_session()`. The MongoLogger already accepts user_id.  
   _Locate the auto-create branch in `rag_pipeline.py` — search for `new_session` call._

4. **`GET /sessions` already returns by user_id** (`api/routes/session.py` line 63–75) — no change needed. `GET /session/{session_id}` already returns turns — no change needed.

---

## Phase 2 — Frontend: Types + Session API service

**Goal:** Typed data layer for all session operations.

5. **Add session types to `src/RAG_v2/frontend/chat-companion/src/types/chat.ts`**  
   Add `Session { session_id, title, created_at, updated_at, turn_count }` and `Turn { turn_id, question, answer, intent, reflected_question, timestamp, sources? }`.

6. **Create `src/RAG_v2/frontend/chat-companion/src/services/sessionApi.ts`**  
   Three functions using the existing `apiClient` (re-export or re-instantiate from `chatApi.ts`):
   - `getSessions(userId: string): Promise<Session[]>` → `GET /sessions?user_id=X`
   - `getSession(sessionId: string): Promise<{ session: Session, turns: Turn[] }>` → `GET /session/{sessionId}`
   - `createSession(userId: string): Promise<{ session_id: string }>` → `POST /session` with body `{ user_id }`

---

## Phase 3 — Frontend: URL routing

**Goal:** Each conversation has its own URL so it survives page refresh.

7. **Update `src/RAG_v2/frontend/chat-companion/src/App.tsx`**  
   Add a second route: `/chat/:sessionId` → renders the same `<Index>` page.  
   Both `/chat` and `/chat/:sessionId` render Index.

---

## Phase 4 — Frontend: ConversationSidebar component

**Goal:** Left sidebar listing all past conversations with a "New Chat" button.

8. **Create `src/RAG_v2/frontend/chat-companion/src/components/sidebar/ConversationSidebar.tsx`**  
   - Uses `useSidebar()` from `ui/sidebar.tsx` (already exists in the project)
   - Uses React Query `useQuery(['sessions', userId], () => getSessions(userId))` to fetch and cache session list
   - "New Chat" button → `navigate('/chat')`
   - Each session item shows: `session.title` (truncated to 40 chars) + relative time (`updated_at`)
   - Active session (matching URL param) gets a highlighted background
   - Click on session → `navigate('/chat/' + session.session_id)`
   - Auto-refetch after each new message (invalidate `['sessions', userId]` from ChatContainer)

---

## Phase 5 — Frontend: ChatContainer updates

**Goal:** Load persisted history when opening an existing session; bind to URL session_id; send user_id with every request.

9. **Update `src/RAG_v2/frontend/chat-companion/src/components/chat/ChatContainer.tsx`**  
   - Add prop `sessionId?: string` (from URL param via `useParams` in Index.tsx, passed down)
   - On mount *when `sessionId` is truthy*: call `getSession(sessionId)` → convert `turns[]` to `Message[]` and set state
   - When `sessionId` prop changes (user clicks different conversation): reload history
   - In `handleSendMessage`: pass `user_id: user?.email` to `sendMessage()` call (update `chatApi.sendMessage` signature to accept `userId?: string`)
   - After successful response: if `response.session_id` differs from current URL, call `navigate('/chat/' + response.session_id)` to update the URL (uses `useNavigate`)
   - After successful response: call `queryClient.invalidateQueries(['sessions', userId])` to refresh sidebar

10. **Update `src/RAG_v2/frontend/chat-companion/src/services/chatApi.ts`**  
    Add optional `userId?: string` param to `sendMessage()`; include it in the POST body as `user_id`.

---

## Phase 6 — Frontend: Index.tsx + App layout wiring

**Goal:** Compose sidebar + chat pane into a single layout.

11. **Update `src/RAG_v2/frontend/chat-companion/src/pages/Index.tsx`**  
    - Import and render `<ConversationSidebar>` on the left
    - Wrap the entire page with `<SidebarProvider>` from `ui/sidebar.tsx`
    - Use `useParams<{ sessionId?: string }>()` to get active session ID from URL
    - Pass `sessionId` down to `<ChatContainer sessionId={sessionId} user={user} />`
    - The sidebar toggle button (hamburger) uses `useSidebar().toggleSidebar()`

---

## Relevant files

| File | Action |
|------|--------|
| `src/RAG_v2/schemas/chat.py` | Add `user_id: Optional[str] = None` to ChatRequest |
| `src/RAG_v2/api/routes/chat.py` | Pass `user_id` to pipeline query |
| `src/RAG_v2/pipeline/rag_pipeline.py` | Pass `user_id` to `new_session()` in auto-create branch |
| `src/RAG_v2/api/routes/session.py` | No changes needed |
| `src/RAG_v2/pipeline/mongo_logger.py` | No changes needed |
| `frontend/src/types/chat.ts` | Add Session + Turn types |
| `frontend/src/services/chatApi.ts` | Add `userId` param to `sendMessage` |
| `frontend/src/services/sessionApi.ts` | **Create new** — getSessions, getSession, createSession |
| `frontend/src/components/sidebar/ConversationSidebar.tsx` | **Create new** |
| `frontend/src/components/chat/ChatContainer.tsx` | Add sessionId prop, history load, URL update, query invalidation |
| `frontend/src/pages/Index.tsx` | Add SidebarProvider, sidebar component, url params |
| `frontend/src/App.tsx` | Add `/chat/:sessionId` route |

---

## Verification

1. **Unit check — backend**: Start FastAPI server, call `POST /chat` with `user_id="test@example.com"` → subsequent `GET /sessions?user_id=test@example.com` returns the session with correct title set from the first question.
2. **Manual — new chat**: Open `/chat`, send a message, verify URL changes to `/chat/{session_id}`, reload page — messages persist (loaded from API).
3. **Manual — sidebar**: After 2+ conversations, sidebar shows all conversations with titles; clicking a past one loads its history.
4. **Manual — continue chat**: Open a past conversation from the sidebar, send a new message — it continues the thread (RAG pipeline receives the loaded history).
5. **Manual — new chat button**: Click "New Chat", URL resets to `/chat`, empty state shown.
6. **Cross-user isolation**: Log in as user B — only user B's sessions appear in the sidebar.

---

## Decisions

- **user_id = `user.email`**: The frontend User object has `email`; this is the identifier used for `user_id` in MongoDB sessions. (Student ID could also work but email is always present.)
- **History loading**: When loading a past session, `ChatContainer` maps `Turn.question → { role: "user" }` and `Turn.answer → { role: "assistant" }` to reconstruct the `Message[]` state. These messages are display-only; the RAG pipeline receives the authoritative persisted history.
- **No delete/rename**: Out of scope for this iteration (not selected by user).
- **No JWT middleware on session routes**: User_id flows via request body/query param for simplicity; full JWT enforcement on session routes is deferred.
