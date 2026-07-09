# Module: `frontend`

Web client (React + TypeScript + Vite) cho chatbot RAG: giao diện chat cho sinh viên, trang admin quản lý tài liệu, và các trang phụ trợ (đăng nhập, hồ sơ, đánh giá). Toàn bộ mã nằm trong app con `chat-companion/`.

## Cấu trúc

### `chat-companion/`
Ứng dụng SPA chính. Build/dev bằng Vite, style bằng Tailwind + shadcn/ui, test E2E bằng Playwright.

### `chat-companion/src/pages/`
Các trang định tuyến cấp cao: `Index.tsx` (màn hình chat chính), `AdminPage.tsx`, `LoginPage.tsx` / `RegisterPage.tsx` / `CompleteProfile.tsx`, `EvalPage.tsx`, `DocumentReview.tsx`, `BookmarksPage.tsx`, `NotificationsPage.tsx`, `LandingPage.tsx`, `NotFound.tsx`.

### `chat-companion/src/components/`
Component theo nhóm chức năng:
- `chat/` — khung hội thoại (`ChatContainer`, `ChatMessage`, `ChatInput`, `TypingIndicator`, `MessageActionsWeb`).
- `admin/` — quản trị tài liệu và thống kê (`FileUploader`, `DocumentList`, `MetadataForm`, `ChunkViewer`, `MarkdownEditor`, các tab `Overview/Analytics/Feedback/AgentAnalytics`).
- `trace/` — hiển thị pipeline/agent (`PipelineTrace`, `AgentTrace`, `DocRow`).
- `sidebar/` — `ConversationSidebar`.
- `ui/` — thư viện primitive shadcn/ui (~49 file).

### `chat-companion/src/services/`
Lớp gọi API và quản lý phiên: `chatApi.ts`, `adminApi.ts`, `sessionApi.ts`, `authApi.ts`, `authSession.ts`, `authStorage.ts`, `notificationDisplay.ts`.

### `chat-companion/src/hooks/`
Hook dùng lại: `useAdminFetch`, `useSmartScroll`, `useResizableSidebar`, `use-mobile`, `use-toast`.

### `chat-companion/src/lib/` và `src/types/`
Tiện ích (`utils.ts`, `pipelineNotify.ts`) và định nghĩa kiểu (`chat.ts`, `admin.ts`, `adminStats.ts`).

### `chat-companion/e2e/`
Test Playwright (backend mock trong `mocks.ts`): luồng chat, admin, streaming, chống rò rỉ phiên, snapshot UI.

### Cấu hình chính
`package.json`, `vite.config.ts`, `tailwind.config.ts`, `tsconfig*.json`, `playwright.config.ts`, `components.json`, `eslint.config.js`.
