# Module: `models` — Database & Persistence Layer

## Tổng quan

Module `models` chịu trách nhiệm **quản lý kết nối database** và **lưu trữ dữ liệu** cho hệ thống RAG v2. Bao gồm Motor client initialization, index management, user models, document models, và conversation logging.

---

## Cấu trúc file

```
models/
├── __init__.py          # Module init
├── database.py          # Motor client initialization + MongoDB index management
├── user.py              # User-related database operations
├── document.py          # DocumentRecord model — admin upload pipeline tracking
├── document_chunk.py    # DocumentChunk model — processed text chunks
└── mongo_logger.py      # MongoLogger — ghi log hội thoại, traces, analytics vào MongoDB
```

---

## Nhiệm vụ chi tiết

### `database.py` — Database Client & Indexes

**Nhiệm vụ:** Quản lý Motor (async MongoDB) client initialization và database index setup.

- `get_motor_client()`: Singleton Motor client
- `create_indexes()`: Tạo indexes cho sessions, turns, query_logs, agent_traces, documents, document_chunks
- `get_database()`: Trả về database instance

**Collections:**
- `users`, `sessions`, `turns`, `query_logs` — existing
- `documents` — admin-uploaded document records (Phase 2)
- `document_chunks` — processed text chunks (Phase 2)

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

### `document.py` — Document Record Model (Phase 2)

**Nhiệm vụ:** Định nghĩa `DocumentRecord` model cho MongoDB `documents` collection — tracking admin-uploaded documents qua pipeline.

- `AuditEntry`: Embedded audit log entry (action, user_id, timestamp, details)
- `DocumentRecord`: Full document record
  - Identity: `id`, `filename`, `file_size`, `file_path`
  - Classification: `collection` (ctdt | quydinh | kehoach | stsv)
  - Pipeline status: `status` (uploaded → converting → converted → cleaning → cleaned → chunking → chunked → embedding → indexed | failed)
  - Ownership: `uploaded_by`, `uploaded_at`
  - Artifact paths: `markdown_path`, `cleaned_path`
  - Chunks: `chunk_count`, `chunk_ids`, `chunking_strategy`
  - Review flags: `markdown_reviewed`, `cleaned_reviewed`, `chunks_reviewed`
  - Metadata: `metadata_overrides` (optional: major_code, cohort, date_str)
  - Error: `error_message`
  - Timestamps: `converted_at`, `cleaned_at`, `chunked_at`, `indexed_at`
  - Audit: `audit_log` (append-only list of AuditEntry)

---

### `document_chunk.py` — Document Chunk Model (Phase 2)

**Nhiệm vụ:** Định nghĩa `DocumentChunk` model cho MongoDB `document_chunks` collection.

- `DocumentChunk`: Single chunk of a processed document
  - `document_id`: FK to documents collection
  - `chunk_index`: Order within document
  - `content`: Chunk text
  - `metadata`: Chunk-level metadata (strategy, document_id, filename, collection)
  - **NO embedding vectors** — those live in Qdrant/ES only

---

## LLM involvement

Module `models` **không sử dụng LLM** — chỉ quản lý database I/O.
