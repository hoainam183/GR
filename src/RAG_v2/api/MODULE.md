# Module: `api` — REST API Layer

## Tổng quan

Module `api` là **lớp giao tiếp HTTP** giữa frontend/client và hệ thống RAG v2 backend. Được xây dựng bằng **FastAPI**, module này tiếp nhận các request từ người dùng, định tuyến đến pipeline xử lý phù hợp, và trả về response theo định dạng chuẩn (JSON hoặc SSE streaming).

---

## Cấu trúc file

```
api/
├── main.py          # Khởi tạo FastAPI app, đăng ký router, CORS, Redis và Middleware
├── schemas.py       # Pydantic schemas cho request/response
├── middleware/
│   └── rate_limit.py # Middleware giới hạn tần suất Sliding Window Rate Limiting (Redis)
└── routes/
    ├── chat.py      # Endpoint xử lý câu hỏi chính (/chat, /stream)
    ├── session.py   # Quản lý session lịch sử hội thoại (Redis + MongoDB)
    ├── metrics.py   # Endpoint thu thập metrics latency và cache stats
    └── health.py    # Health check endpoint (bao gồm Redis status)
```

---

## Nhiệm vụ chi tiết

### `main.py`
- Tạo FastAPI application instance
- Cấu hình CORS middleware (cho phép frontend React/mobile gọi)
- Đăng ký tất cả routers (`/chat`, `/session`, `/metrics`, `/health`)
- Khởi tạo và inject `RAGPipeline` singleton vào app state
- Xử lý startup/shutdown events (kết nối DB, warm-up embedder)

### `routes/chat.py` — Endpoint xử lý câu hỏi
**Đây là route quan trọng nhất của hệ thống.**

| Endpoint | Method | Mô tả |
|---|---|---|
| `/chat` | POST | Non-streaming: nhận question, trả về JSON đầy đủ |
| `/chat/stream` | POST | Streaming: trả về SSE token-by-token |
| `/chat/agent` | POST | Bắt buộc dùng agent LangGraph |
| `/chat/v3` | POST | Smart routing: chitchat / simple RAG / complex agent |

**Luồng xử lý trong `chat.py`:**
1. Validate request body (Pydantic)
2. Extract `session_id`, `user_context` từ JWT/header
3. Gọi `pipeline.query()` hoặc `pipeline.query_stream()`
4. Format và trả về response (bao gồm `timings_ms`, `sources`, `agent_trace`)

### `routes/session.py`
- `GET /session/{session_id}/history` — lấy lịch sử hội thoại từ Redis (fallback MongoDB)
- `DELETE /session/{session_id}` — xóa session từ cả Redis và MongoDB

### `routes/metrics.py`
- `GET /metrics/usage` — trả về thống kê latency, số request, intent distribution và tỉ lệ hit/miss của LLM Cache
- Data được tổng hợp từ MongoDB logs và Redis cache stats

### `routes/health.py`
- `GET /health` — kiểm tra kết nối Qdrant, Elasticsearch, MongoDB

### `schemas.py`
- `ChatRequest`: `question`, `session_id`, `history`, `top_k`, `user_context`
- `ChatResponse`: `answer`, `sources`, `intent`, `timings_ms`, `request_trace`

---

## Tương tác với các module khác

```
Client (HTTP)
    │
    ▼
api/routes/chat.py
    │
    ├─► pipeline/rag_pipeline.py  (RAGPipeline.query / query_stream / query_v3)
    │       │
    │       ├─► query/router.py          (định tuyến intent)
    │       ├─► pipeline/flows.py        (rag_flow / chitchat_flow)
    │       └─► agent/react_agent.py     (LangGraph agent)
    │
    └─► pipeline/mongo_logger.py  (ghi log MongoDB)
```

---

## LLM involvement

Module `api` **không gọi LLM trực tiếp**. Nó chỉ là lớp điều phối HTTP.

---

## Latency contribution

| Component | Ảnh hưởng |
|---|---|
| Request parsing | < 1ms |
| Response serialization | ~2-5ms |
| **Tổng overhead của API layer** | **~3-8ms** |
