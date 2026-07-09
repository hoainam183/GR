# Module: `config`

Model cấu hình runtime duy nhất và có thẩm quyền cho toàn hệ thống RAG v2, đọc từ biến môi trường và file `.env` với default có kiểu.

## Files

### `settings.py`
Định nghĩa `Settings(BaseSettings)` gom mọi knob cấu hình (provider LLM, API key, Qdrant/ES/Mongo/Redis, retrieval, reranker, router, agent, reflection, Tavily, crawler, exam schedule, server/CORS...); mọi field override được qua env var (case-insensitive), load `.env` ở gốc RAG_v2 (utf-8, `extra="ignore"`).
- `Settings` — class BaseSettings chứa toàn bộ field và default.

### `__init__.py`
Re-export `Settings` làm symbol công khai duy nhất của module.
