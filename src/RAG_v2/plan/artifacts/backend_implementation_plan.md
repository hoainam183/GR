# Lộ trình cải thiện RAG v2 — Plan cuối cùng

> Đã điều chỉnh theo feedback: loại bỏ chunk_overlap và expose chunk settings (không cần thiết với structure-aware chunking hiện tại).

---

## 🔴 Giai đoạn 1: 30 ngày — Critical Fixes & Quick Wins

### 1.1 Fix thread-safety `self.last_*` trong streaming
- **Ưu tiên**: 🔴 Cao
- **File**: [rag_pipeline.py](file:///Users/nam.nguyen/Documents/personal/GR/src/RAG_v2/pipeline/rag_pipeline.py) (line 920-932)
- **Vấn đề**: `query_stream()` lưu metadata vào instance attrs → race condition khi concurrent requests
- **Giải pháp**: Refactor `query_stream()` để return `(generator, metadata_dict)` thay vì ghi vào `self.last_*`. Chat route đọc metadata từ dict trả về.

### 1.2 Xóa hard-coded debug dump path
- **Ưu tiên**: 🔴 Cao
- **File**: [document_pipeline.py](file:///Users/nam.nguyen/Documents/personal/GR/src/RAG_v2/pipeline/document_pipeline.py) (line 476-483)
- **Vấn đề**: Hard-coded `/Users/nam.nguyen/...` → crash trên production/container
- **Giải pháp**: Xóa hoặc chuyển sang conditional debug (chỉ khi `DEBUG=true` trong settings), sử dụng `settings.upload_dir` thay vì absolute path

### 1.3 Implement `/auth/refresh` endpoint
- **Ưu tiên**: 🔴 Cao
- **File**: [auth.py](file:///Users/nam.nguyen/Documents/personal/GR/src/RAG_v2/routers/auth.py)
- **Vấn đề**: Mobile client gọi nhưng backend không implement → silent logout
- **Giải pháp**: Thêm `POST /auth/refresh` nhận refresh token, verify, trả JWT mới

### 1.4 Thêm timeout cho Gemini API calls
- **Ưu tiên**: 🔴 Cao
- **File**: LLM provider factory
- **Vấn đề**: Gemini API có thể hang vô thời hạn → request treo
- **Giải pháp**: Set `timeout=30s` cho tất cả external API calls (Gemini, Tavily)

### 1.5 Fix OAuth redirect port mismatch
- **Ưu tiên**: 🟡 Trung bình
- **File**: [auth.py](file:///Users/nam.nguyen/Documents/personal/GR/src/RAG_v2/routers/auth.py)
- **Vấn đề**: Auth callback redirect code dùng `http://localhost:5173` nhưng Vite dev config dùng port `8080`
- **Giải pháp**: Đọc redirect URL từ settings/env thay vì hard-code

### 1.6 Thêm `major_code` vào `UserUpdate`
- **Ưu tiên**: 🟡 Trung bình
- **File**: [schemas/user.py](file:///Users/nam.nguyen/Documents/personal/GR/src/RAG_v2/schemas/user.py)
- **Vấn đề**: `PATCH /auth/me` không update được `major_code` mặc dù chat `user_context` hỗ trợ
- **Giải pháp**: Thêm `major_code: Optional[str]` vào `UserUpdate` schema

### 1.7 Fix `retrieval_service` attribute access
- **Ưu tiên**: 🟡 Trung bình
- **Files**: [retrieval.py](file:///Users/nam.nguyen/Documents/personal/GR/src/RAG_v2/api/routes/retrieval.py), [main.py](file:///Users/nam.nguyen/Documents/personal/GR/src/RAG_v2/api/main.py)
- **Vấn đề**: Code truy cập `pipeline.retrieval_service` nhưng attr thực tế là `_retrieval_service` → cold-start mỗi request
- **Giải pháp**: Expose property `retrieval_service` trên `RAGPipeline`

---

## 🟡 Giai đoạn 2: 60 ngày — Reliability & Observability

### 2.1 Circuit breaker cho Qdrant/ES
- **File**: [service.py](file:///Users/nam.nguyen/Documents/personal/GR/src/RAG_v2/retrieval/service.py), [multi_collection_search.py](file:///Users/nam.nguyen/Documents/personal/GR/src/RAG_v2/retrieval/multi_collection_search.py)
- **Giải pháp**: Wrap Qdrant/ES calls với `pybreaker` hoặc custom circuit breaker. Khi open → trả empty results + warning thay vì crash 500.

### 2.2 Enhanced `/health` endpoint
- **File**: [health.py](file:///Users/nam.nguyen/Documents/personal/GR/src/RAG_v2/api/routes/health.py)
- **Giải pháp**: Ping Qdrant, ES, Redis trong health check. Return `degraded` status thay vì chỉ check pipeline init.

### 2.3 Document deduplication
- **File**: [upload.py](file:///Users/nam.nguyen/Documents/personal/GR/src/RAG_v2/api/routes/upload.py), [document.py](file:///Users/nam.nguyen/Documents/personal/GR/src/RAG_v2/models/document.py)
- **Giải pháp**: Thêm `content_hash` (SHA-256 of PDF bytes) vào `DocumentRecord`. Check trước insert, warn admin nếu duplicate.

### 2.4 Structured logging
- **File**: Toàn project
- **Giải pháp**: Chuyển sang JSON structured logging format. Thêm `correlation_id` per request cho trace across components.

### 2.5 Finalize backend Dockerfile
- **File**: Dockerfile.backend (cần tạo mới)
- **Giải pháp**: Uncomment docker-compose backend service, thêm resource limits (8GB memory cho embedding models), health check.

### 2.6 Database security
- **File**: [docker-compose.yml](file:///Users/nam.nguyen/Documents/personal/GR/src/RAG_v2/docker-compose.yml)
- **Giải pháp**: MongoDB authentication, Redis password, ES security (ít nhất cho production profile).

---

## 🟢 Giai đoạn 3: 90 ngày — Scale & Polish

### 3.1 Async MongoDB unification
- Unify `MongoLogger` (sync pymongo) và `DocumentPipeline` (async Motor) vào 1 client

### 3.2 Word/HTML file support
- Thêm `python-docx`, `beautifulsoup4` converter vào ingestion pipeline

### 3.3 Incremental re-index
- So content hash khi upload lại cùng document → chỉ re-process nếu thay đổi

### 3.4 Request timeout middleware
- Global 60s timeout middleware cho tất cả endpoints

### 3.5 API versioning
- Deprecate `/chat` in favor of `/chat/v3`, plan migration path

### 3.6 Container resource limits + auto-restart
- Deploy config với memory/CPU limits phù hợp cho embedding models

### 3.7 Monitoring
- Prometheus metrics endpoint cho latency, throughput, error rate tracking

---

## Verification Plan

### Automated Tests
- Run existing test suite: `python run_all_tests.py`
- Thêm concurrent streaming test để verify thread-safety fix
- Health endpoint integration test (mock Qdrant/ES down scenarios)

### Manual Verification
- Test `/auth/refresh` flow từ mobile app
- Verify debug dump không còn write tới absolute path
- Load test concurrent `/chat/stream` requests
