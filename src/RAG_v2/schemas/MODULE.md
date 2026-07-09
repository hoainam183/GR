# Module: `schemas`

Các model Pydantic dùng cho request/response của API (tách biệt với model lưu MongoDB ở `models.*`). Gom theo nhóm nghiệp vụ: chat, user/auth, tài liệu upload, lịch thi, tính năng mobile, và các hằng số dùng chung.

## Files

### `__init__.py`
Docstring package; re-export các schema chat và user chính (`ChatRequest`, `ChatResponse`, `UserPublic`, `TokenResponse`, ...) để import gọn từ `schemas`.

### `chat.py`
Định nghĩa các model request/response cho endpoint chat và health, gồm cả các trường trace mở rộng (routing, rerank, agent).
- `ChatRequest` — body cho `/chat` và `/chat/stream` (question, mode, top_k, history, session/user context).
- `ChatResponse` — phản hồi đầy đủ: câu trả lời, tài liệu truy hồi, timings và telemetry agent/route.
- `RetrievedDocument` — một tài liệu truy hồi kèm breakdown điểm (hybrid/rerank/vector/keyword).
- `AgentTracePayload` / `AgentToolCall` — trace thực thi và bản ghi lời gọi tool của agent.
- `HealthResponse` — trạng thái service, MongoDB, Redis.

### `user.py`
Các model cho user và luồng xác thực (OAuth Microsoft + username/password), tách khỏi document lưu DB.
- `UserCreate` — tạo user sau OAuth, có validator bắt buộc email `@sis.hust.edu.vn`.
- `UserUpdate` — body PATCH toàn optional; `to_update_dict()` chỉ lấy field đã set và thêm `updated_at`.
- `UserPublic` — dạng trả về an toàn (ẩn `microsoft_id`, `password_hash`); `from_document()` dựng từ dict Mongo.
- `UserManualCreate` / `UserLoginRequest` / `RefreshRequest` / `TokenResponse` — đăng ký, đăng nhập, rotate refresh token, và phản hồi token.
- `AdminCreateRequest` — body tạo tài khoản admin (superadmin dùng).

### `document.py`
Schema cho luồng upload/xử lý tài liệu admin, kèm danh sách collection/converter/chunker hợp lệ.
- `DocumentUploadRequest` — form data upload, validator kiểm tra `collection`.
- `DocumentDetail` — chi tiết một tài liệu; `from_document()` map từ document Mongo.
- `DocumentListResponse` — danh sách tài liệu có phân trang.
- `ChunkPreview` / `ChunksResponse` — preview chunk và listing kèm thống kê cho UI review.
- `ChunkUpdateRequest` — body sửa nội dung chunk, validator chặn nội dung rỗng.
- `MarkdownContent` / `CleanedContent` / `LLMCleanedContent` — nội dung markdown ở các bước review.

### `exam_schedule.py`
DTO cho endpoint và tool lịch thi (giữa/cuối kỳ), tách khỏi record lưu trữ để hợp đồng HTTP tiến hóa độc lập.
- `ExamScheduleUploadResponse` — kết quả upload: số dòng parse/skip, có thay thế cũ không, số bản index.
- `ExamScheduleSummary` / `ExamScheduleSourceSummary` — snapshot collection và thống kê theo file nguồn.
- `ParseReport` / `SkippedRow` — báo cáo parse từng file và lý do bỏ dòng.
- `ExamScheduleQuery` — DTO truy vấn có cấu trúc dùng nội bộ trong tool (không thuộc HTTP surface).

### `mobile.py`
Các schema cho tính năng riêng của app mobile: bookmark, feedback, đăng ký nhận thông báo.
- `BookmarkCreate` / `BookmarkUpdate` — tạo/sửa bookmark một turn hội thoại.
- `BookmarkFolderCreate` / `BookmarkFolderRename` — quản lý thư mục bookmark.
- `FeedbackCreate` — gửi đánh giá up/down kèm category tùy chọn.
- `NotificationSubscribe` / `NotificationUnsubscribe` — đăng ký/hủy topic kèm Expo push token.
- `LookupDocument` / `NotificationCreateInternal` — DTO kết quả lookup và tạo notification nội bộ.

### `constants.py`
Tập trung các magic string về route/mode trước đây rải rác ở nhiều nơi.
- `RouteMode` — giá trị `mode` của `ChatRequest` (`auto`/`rag`/`agent`).
- `PipelineMode` — giá trị `mode` trong dict kết quả pipeline (`rag_v2`, `rag_v2_fallback`, `agent`).
- `AgentRoute` — giá trị `route`/`intent` cho kết quả agent (`complex`, `simple`, `chitchat`, `agent_forced`).
