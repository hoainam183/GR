# Module: `packages`

Chứa các package TypeScript dùng chung giữa web và mobile trong monorepo. Hiện có `shared/` (`@rag/shared`).

## Cấu trúc

### `shared/` (`@rag/shared`)
Package nội bộ export client API, store và type dùng lại cho cả frontend web và app mobile (main/types trỏ trực tiếp vào `src/index.ts`).

### `shared/src/api/`
Các client gọi backend theo miền: `client.ts` (axios cơ sở), `authApi.ts`, `chatApi.ts`, `sessionApi.ts`, `bookmarkApi.ts`, `feedbackApi.ts`, `lookupApi.ts`, `notificationApi.ts`; gom lại ở `index.ts`.

### `shared/src/stores/`
Store Zustand dùng chung: `authStore.ts`, `chatStore.ts` (export qua `index.ts`).

### `shared/src/types/`
Định nghĩa kiểu chia sẻ: `auth.ts`, `chat.ts`, `mobile.ts` (gom ở `index.ts`).

### `shared/src/utils/`
Tiện ích chung: `constants.ts`, `normalize.ts`, `sanitize.ts`.

### `shared/src/profileOptions.ts`
Danh mục lựa chọn hồ sơ (ngành, khóa...) dùng chung khi đăng ký/hoàn thiện hồ sơ.

### Cấu hình chính
`shared/package.json` (deps: axios, zustand, zod), `shared/tsconfig.json`.
