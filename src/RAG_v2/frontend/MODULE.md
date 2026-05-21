# Module: `frontend`

Source-verified: 2026-05-20 from `frontend/chat-companion/src/**`, package files, and API contracts.

## Purpose

`frontend` contains the React/Vite web client under `frontend/chat-companion`. It provides chat, auth/profile, trace/debug, retrieval diagnostics, evaluation dashboard, admin document management, bookmarks, and notifications.

## App Stack

- React 18
- Vite
- React Router
- TanStack Query
- Axios and Fetch/ReadableStream for SSE
- shadcn/Radix UI components
- Tailwind CSS
- `@rag/shared` workspace package is available, while the web app still keeps local service/type modules for several features.

## Main Source Map

```text
frontend/chat-companion/src/
  App.tsx                       Route table.
  pages/                        Top-level screens.
  components/chat/              Chat UI, messages, actions, input.
  components/sidebar/           Conversation sidebar.
  components/admin/             Upload/review/chunk/index admin UI.
  components/trace/             Pipeline/agent trace visualizations.
  components/ui/                shadcn/Radix primitives.
  services/                     chat/auth/session/admin API clients.
  types/                        Local admin/chat types.
  hooks/                        Smart scroll, sidebar resize, toast/mobile hooks.
```

## Routes

`App.tsx` defines:

| Route | Purpose |
| --- | --- |
| `/` | Landing page, redirects/entry. |
| `/chat`, `/chat/:sessionId` | Main chat UI. |
| `/login`, `/register`, `/complete-profile` | Auth/profile flow. |
| `/trace` | Admin-only trace/debug page. |
| `/retrieval` | Admin-only retrieval diagnostic page. |
| `/eval` | Admin-only evaluation dashboard. |
| `/admin` | Admin document list/upload page. |
| `/admin/documents/:id` | Admin document review pipeline page. |
| `/bookmarks` | Saved answers. |
| `/notifications` | Notification inbox. |

`AdminGuard` currently checks `localStorage.user.role === "admin"`.

## API Services

Important local services:

- `services/chatApi.ts`: `/chat/v3`, `/chat/stream`, response normalization, source mapping.
- `services/authApi.ts`: login/register/profile helpers.
- `services/authStorage.ts`: token/user localStorage compatibility.
- `services/sessionApi.ts`: session list/get/create/update/delete.
- `services/adminApi.ts`: upload pipeline actions and polling.

Token behavior:

- New auth should normalize to `localStorage.token`.
- Some helpers also read legacy `localStorage.access_token` for compatibility.

## Chat UI Contract

`ChatContainer` coordinates:

- selected session id
- message send
- streaming token updates
- metadata/debug panel data
- session invalidation
- persisted sidebar size

`PipelineTrace.tsx` expects pipeline metadata such as timings, filters, collection results, route/mode, Tavily details, and agent traces.

## Admin UI Contract

`AdminPage` owns a viewport-height shell with a fixed header/tab rail and a scrollable `main` region because the app root keeps overflow locked for chat. Keep admin tab content inside that scroll region; tab switches reset it to the top.

`OverviewTab` uses compact metric cards plus a usage summary panel rather than a loose page-level stat grid.

## Maintenance Notes

- Keep web response normalization aligned with `api/response_mapper.py` and `packages/shared/src/utils/normalize.ts`.
- When backend chat metadata changes, update `types/chat.ts`, `services/chatApi.ts`, and trace components.
- When admin document schemas change, update `types/admin.ts`, `services/adminApi.ts`, and admin components.
- Avoid adding runtime-only secrets to Vite env; only `VITE_*` values are exposed.

## Useful Checks

```bash
npm run lint --workspace=frontend/chat-companion
npm run build --workspace=frontend/chat-companion
```
