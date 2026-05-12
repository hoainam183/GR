# Module: `models` — Database & Persistence Layer

## Tổng quan

Module `models` chịu trách nhiệm **quản lý kết nối database** và **lưu trữ dữ liệu** cho hệ thống RAG v2. Bao gồm Motor client initialization, index management, user models, và conversation logging.

---

## Cấu trúc file

```
models/
├── __init__.py        # Module init
├── database.py        # Motor client initialization + MongoDB index management
├── user.py            # User-related database operations
└── mongo_logger.py    # MongoLogger — ghi log hội thoại, traces, analytics vào MongoDB
```

---

## Nhiệm vụ chi tiết

### `database.py` — Database Client & Indexes

**Nhiệm vụ:** Quản lý Motor (async MongoDB) client initialization và database index setup.

- `get_motor_client()`: Singleton Motor client
- `create_indexes()`: Tạo indexes cho sessions, turns, query_logs, agent_traces
- `get_database()`: Trả về database instance

---

### `mongo_logger.py` — `MongoLogger`

**Nhiệm vụ:** Ghi log hội thoại, agent traces, và analytics vào MongoDB.

> Di chuyển từ `pipeline/mongo_logger.py` sang đây vì bản chất là infrastructure/persistence, không phải pipeline orchestration.

**Methods chính:**
- `new_session()`: Tạo session mới, trả về UUID
- `log_turn()`: Ghi một lượt hội thoại (question, answer, sources, timings, latency)
- `get_history()`: Lấy lịch sử hội thoại cho session
- `get_turns()`: Lấy danh sách turns
- `log_agent_trace()`: Ghi toàn bộ trace của agent (tool calls, iterations)
- `get_agent_stats()`: Thống kê agent performance

**Schema MongoDB:**
```json
{
  "session_id": "...",
  "question": "...",
  "answer": "...",
  "reflected_question": "...",
  "sources": [...],
  "latency_ms": 4500,
  "timings_ms": {"reflection": 800, "search": 200, "rerank": 150, "generate": 3200},
  "timestamp": "2026-04-26T..."
}
```

---

### `user.py` — User Document Model

**Nhiệm vụ:** Định nghĩa `UserDocument` model cho MongoDB `users` collection.

- `PyObjectId`: Pydantic v2 annotation cho MongoDB ObjectId
- `UserDocument`: Full MongoDB document model
  - Identity: `id`, `microsoft_id`, `username`, `password_hash`
  - Contact: `email`
  - Profile: `full_name`, `student_id`, `cohort`, `major`, `major_code`, `avatar_url`
  - **Role**: `role: str = "student"` — values: `"student"` | `"admin"` (Phase 1 Admin)
  - Status: `is_profile_complete`, `is_active`
  - Timestamps: `created_at`, `updated_at`, `last_login_at`

> **Backward compatibility:** Existing users without a `role` field default to `"student"` via Pydantic default.

---

## LLM involvement

Module `models` **không sử dụng LLM** — chỉ quản lý database I/O.
