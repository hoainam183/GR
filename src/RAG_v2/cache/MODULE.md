# Module: `cache`

Hạ tầng Redis tùy chọn cho 4 mối quan tâm: metadata session, lịch sử hội thoại gần đây, cache câu trả lời LLM, và rate limiting. Mọi thao tác Redis đều `try/except` và degrade an toàn (fallback MongoDB, cho qua request, hoặc trả `None`).

## Files

### `__init__.py`
Docstring package, không export gì.

### `redis_client.py`
Quản lý kết nối Redis dạng singleton (một `ConnectionPool` cho cả process), có ping và đóng kết nối.
- `RedisManager.from_settings()` — tạo/lấy singleton từ `Settings`.
- `RedisManager.get_client()` — trả về client Redis dùng chung.
- `RedisManager.ping()` — kiểm tra Redis sống trước khi tạo tài nguyên.
- `RedisManager.close()` — đóng client, reset singleton (gọi khi shutdown).

### `session_store.py`
Lưu metadata session trong Redis Hash + ZSet theo user, dual-write và fallback sang MongoDB.
- `new_session()` — tạo session mới, ghi Redis + MongoDB.
- `get_session()` / `list_sessions()` — đọc một/nhiều session (newest-first, dọn zombie).
- `update_session_on_turn()` — cập nhật turn count, set title từ câu hỏi đầu.
- `sync_from_mongo()` — làm ấm lại metadata Redis từ MongoDB.

### `history_cache.py`
Cache các lượt chat gần đây trong Redis List (LPUSH + LTRIM).
- `get_history()` — trả lịch sử oldest-first, `None` nếu miss (để fallback Mongo).
- `add_message()` — thêm một message.
- `warm_history()` — nạp lại lịch sử từ nguồn ngoài.

### `llm_cache.py`
Cache câu trả lời LLM hai lớp (pre-retrieval theo query, post-retrieval theo doc_ids), key có trộn `profile` để tránh rò câu trả lời giữa các sinh viên, có invalidation theo doc-tag.
- `get()` / `put()` — cache post-retrieval (đã biết doc_ids).
- `get_by_query()` / `put_by_query()` — cache pre-retrieval (chỉ theo query).
- `invalidate_by_docs()` — xóa cache liên quan tới doc bị đổi.
- `invalidate_all()` — xóa toàn bộ (dùng khi đổi model / reindex).

### `rate_limiter.py`
Rate limit sliding-window theo phút và theo ngày bằng ZSet.
- `check()` — kiểm tra có được phép không (không ghi; cho qua nếu Redis lỗi).
- `record()` — ghi nhận request (gọi sau khi gọi LLM thành công).
- `get_usage()` — trả mức dùng hiện tại.
