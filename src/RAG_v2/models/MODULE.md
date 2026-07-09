# Module: `models`

Tầng persistence với MongoDB: client Motor (async) + PyMongo (sync), các model Pydantic cho user/document/chunk/crawler/lịch thi, logger phiên hội thoại, và helper cấu hình hệ thống do admin quản lý.

## Files

### `database.py`
Quản lý client Motor (async) dạng singleton, khai báo hằng số tên collection và tạo toàn bộ index lúc khởi động.
- `get_motor_client()` — tạo/lấy singleton `AsyncIOMotorClient`.
- `get_database()` — dependency FastAPI yield database handle.
- `close_motor_client()` — đóng client khi shutdown.
- `create_indexes()` — tạo tất cả index cần thiết (bọc `safe_create` để bỏ qua xung đột code 85).

### `mongo_logger.py`
Logger sync (PyMongo) ghi phiên, lượt hội thoại, query log và agent trace vào MongoDB; đồng bộ với history cache.
- `MongoLogger.new_session()` — tạo phiên mới, trả `session_id`.
- `MongoLogger.log_turn()` — ghi một lượt (turn + query_log), tăng `turn_count`, tự đặt tiêu đề phiên.
- `MongoLogger.get_history()` — lấy lịch sử gần đây, ưu tiên cache rồi fallback aggregate.
- `MongoLogger.log_agent_trace()` — ghi trace agent best-effort (nuốt lỗi DB).
- `MongoLogger.get_agent_stats()` — tổng hợp số liệu từ các trace gần đây.

### `user.py`
Định nghĩa helper `PyObjectId` và model tài liệu người dùng trong collection `users`.
- `PyObjectId.validate()` — validate/serialise MongoDB ObjectId cho Pydantic v2.
- `UserDocument` — model tài khoản (identity, profile, role, status, timestamps).

### `document.py`
Model tài liệu do admin upload và các bước xử lý trong pipeline, kèm audit log.
- `AuditEntry` — một dòng audit (action, user_id, timestamp).
- `DocumentRecord` — bản ghi tài liệu (trạng thái pipeline, đường dẫn artifact, cờ review).
- `DocumentRecord.from_mongo()` — dựng model từ dict MongoDB.

### `document_chunk.py`
Model một chunk văn bản do bước chunking sinh ra (vector embedding KHÔNG lưu ở đây, chỉ ở Qdrant/ES).
- `DocumentChunk` — chunk tham chiếu `document_id`, chứa content và metadata.
- `DocumentChunk.from_mongo()` — dựng model từ dict MongoDB.

### `exam_schedule.py`
Model một dòng lịch thi đã parse, lưu ở Mongo + Elasticsearch; thuần data + transform, không I/O.
- `ExamScheduleRecord.from_parsed_row()` — dựng record từ dict field đã chuẩn hoá bởi parser.
- `ExamScheduleRecord.to_mongo()` — serialise cho `insert_many` (giữ datetime gốc).
- `ExamScheduleRecord.to_es()` — serialise cho ES index (date ISO + `search_text`).

### `crawler.py`
Model cho các lần crawl staged chờ admin duyệt/index, kèm hằng số trạng thái.
- `CrawlerRun` — metadata một lần crawl (status, counters, file output).
- `CrawlerChunk` — một chunk crawl có thể review/sửa (content + original_content + index_status).

### `system_config.py`
Helper async trên document cấu hình duy nhất (`_id="llm_config"`): override LLM và registry API key do admin quản lý.
- `filter_llm_config_updates()` — lọc các field override an toàn để lưu.
- `get_llm_config()` / `upsert_llm_config()` — đọc/ghi cấu hình LLM (tự migrate key legacy khi đọc).
- `merge_llm_config_into_settings()` — áp override và secret key active lên object `Settings`.
- `create_api_key()` / `activate_api_key()` / `list_api_keys()` — quản lý registry API key.
- `fingerprint_api_key()` — che secret (first4+***+last4) cho response admin.

### `__init__.py`
Package marker rỗng (chỉ một dòng comment).
