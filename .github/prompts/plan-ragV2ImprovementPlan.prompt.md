# Plan: RAG v2 — Cải Thiện Toàn Diện (All Issues)

## TL;DR
Fix 5 nhóm vấn đề theo thứ tự tăng dần về độ phức tạp: Critical → Architecture → Observability → Testing → Long-term. Mỗi phase độc lập, có thể verify riêng.

---

## Phase 1 — Critical Security & Stability (5 fixes, ~4 giờ)
*Các bước trong phase này PARALLEL với nhau.*

1. **[P1-1] LLM timeout** — Thêm `httpx.Timeout(30.0, connect=5.0)` vào `OpenAI(...)` constructor trong `llm/gemini.py` và `query/reflection.py`
2. **[P1-2] RERANKER_PROVIDER=none crash** — Xoá `assert _reranker is not None` trong `pipeline/rag_pipeline.py:L145`. Đổi `self._reranker` sang `Optional[BaseReranker]`. Update `rag_flow()` và `rag_flow_stream()` trong `pipeline/flows.py` để skip rerank khi `reranker is None` (trả nguyên `raw_results`)
3. **[P1-3] Input sanitization** — `api/schemas.py`: `ChatRequest.question` đã có `max_length=4096`. Thêm `field_validator` strip control chars. Thêm `HistoryMessage.content` max_length=4096
4. **[P1-4] Error handler leak** — `api/routes/chat.py` L75 và SSE handler: đổi `detail=str(exc)` thành `detail="Internal server error"`
5. **[P1-5] .env.example typo** — Sửa `CHAT_MAX_TOKENS=1024 * 5` → `CHAT_MAX_TOKENS=5120`

**Verify Phase 1**: Run `test_phase7.py`, test `RERANKER_PROVIDER=none` qua API, check `/chat` với question chứa control chars

---

## Phase 2 — Architecture Cleanup (5 fixes, ~1 ngày)
*Bước 2.1 phải xong trước 2.3. Các bước còn lại parallel.*

6. **[P2-1] embedding/__init__.py lazy loading** — Xoá 3 dòng eager backward-compat imports:
   ```python
   from .bge_m3 import BGEm3Embedder            # ← xoá
   from embedding.e5_multilingual import ...     # ← xoá
   from embedding.ensemble import EnsembleEmbedder  # ← xoá
   ```
   Thêm vào `__all__` entries nhưng KHÔNG import. Ai cần concrete class phải import trực tiếp từ module con.

7. **[P2-2] rag_pipeline.py Dependency Rule** — *depends on P2-1*. Thay thế:
   ```python
   from embedding import BGEm3Embedder, E5MultilingualEmbedder  # xoá
   self._bge = BGEm3Embedder()   # xoá
   self._e5 = E5MultilingualEmbedder()  # xoá
   ```
   Thêm factory helper `create_dual_embedders(settings)` vào `embedding/__init__.py` trả `Tuple[BaseEmbedder, BaseEmbedder]`. Pipeline gọi `self._bge, self._e5 = create_dual_embedders(settings)`

8. **[P2-3] llm/__init__.py eager ChatModel** — Xoá `from .chat_model import ChatModel` và `from .self_eval import SelfEvaluator` khỏi `llm/__init__.py`. Ai dùng `ChatModel` sẽ import trực tiếp từ `llm.chat_model`. Verify bằng grep `from llm import ChatModel`

9. **[P2-4] QueryReflector nhận Settings API key** — Trong `pipeline/rag_pipeline.py` đổi:
   ```python
   self._reflector = QueryReflector()
   # →
   self._reflector = QueryReflector(api_key=settings.llm_api_key or settings.google_api_key)
   ```
   Tương tự TavilySearchTool: đổi `os.environ.get("TAVILY_API_KEY", "")` → `settings.tavily_api_key`

10. **[P2-5] Memory ABC** — Tạo `memory/base.py` với `BaseMemoryStore(ABC)` có methods: `get_history(session_id, limit)`, `save_message(session_id, role, content)`, `clear_history(session_id)`. `ChatHistoryStore` kế thừa ABC này. Đồng thời `MultiCollectionSearch` inherit `BaseRetriever` với `search(**kwargs)` signature

**Verify Phase 2**: Import `from embedding import create_embedder` không load torch. `RERANKER_PROVIDER=none` + `LLM_PROVIDER=gemini` work.

---

## Phase 3 — Observability (3 fixes, ~3 giờ)
*Parallel với nhau.*

11. **[P3-1] Per-step latency** — `pipeline/flows.py` trong `rag_flow()`: wrap mỗi bước bằng `t = time.perf_counter()` và log `logger.info("Step %s: %.0fms", step_name, (time.perf_counter()-t)*1000)` cho: reflect, embed, search, rerank, generate, self_eval

12. **[P3-2] Alert retrieval=0** — `pipeline/flows.py` sau `raw_results = searcher.search(...)`: thêm:
    ```python
    if not raw_results:
        logger.warning("RETRIEVAL_EMPTY: query=%r returned 0 results", search_query[:80])
    ```

13. **[P3-3] Remove dead CSV logger** — Xoá `backend/logger.py` và `backend/rag_logs.csv`, `backend/rag_logs_backup_*.csv`. Verify không còn import nào trỏ vào `backend.logger`

**Verify Phase 3**: Chạy một query, kiểm tra log có dòng `Step embed: Xms` v.v.

---

## Phase 4 — Testing Migration sang pytest (3 tasks, ~1 ngày)
*Bước 4.1 phải xong trước 4.2 và 4.3.*

14. **[P4-1] conftest.py với typed fakes** — Tạo `tests/conftest.py` với:
    - `FakeLLM(BaseLLM)` — generate() trả fixed string
    - `FakeEmbedder(BaseEmbedder)` — trả vector zeros
    - `FakeReranker(BaseReranker)` — trả input docs nguyên
    - Pytest fixtures: `fake_llm`, `fake_embedder`, `fake_reranker`

15. **[P4-2] Migrate test_phase5 + test_phase7 sang pytest** — *depends on P4-1*. Chuyển `report()` calls thành `assert`. Dùng fixtures thay vì `MagicMock` cho những chỗ có thể. Giữ `MagicMock` cho searcher (too complex to fake). Đổi `sys.exit()` → pytest `main()`. File output: `tests/test_settings.py`, `tests/test_flows.py`, `tests/test_api.py`, `tests/test_self_eval.py`

16. **[P4-3] Thêm unit tests cho adapter** — *depends on P4-1*. Tạo:
    - `tests/test_hybrid_search.py`: test `rrf_fuse()`, `filter_by_score()` với mock data thuần python
    - `tests/test_qdrant_store.py`: test `_fuse_results()` static method với fake ScoredPoint
    - `tests/test_chunking.py`: test `ArticleLevelLegalChunker` và `STSVChunker` với sample text

**Verify Phase 4**: `pytest tests/ -v` pass toàn bộ, coverage report

---

## Phase 5 — Long-term Improvements (4 tasks, ~3 ngày)
*Parallel với nhau. Có thể tách thành PR riêng.*

17. **[P5-1] Async embedding** — `pipeline/flows.py`: thay `bge_vec = bge_embedder.embed_query(...)` + `e5_vec = e5_embedder.embed_query(...)` tuần tự bằng `asyncio.gather` qua `loop.run_in_executor`. Cần refactor `rag_flow()` thành `async def rag_flow()` và update caller trong `rag_pipeline.py`

18. **[P5-2] LRU cache cho embed_query** — `embedding/bge_m3.py` và `e5_multilingual.py`: thêm `@functools.lru_cache(maxsize=256)` trên `embed_query()`. Cần hash input (string → hashable OK)

19. **[P5-3] Context window truncation** — `pipeline/flows.py` trong `_format_context()`: thêm optional `max_chars` param (default 16000). Truncate mỗi doc text đến `max_chars // len(docs)` trước khi join

20. **[P5-4] CORS production config** — `config/settings.py`: đổi default `cors_origins: List[str] = ["*"]` → không đổi default nhưng thêm comment prod warning. `api/main.py`: thêm log warning khi `cors_origins == ["*"]`

**Verify Phase 5**: Đo latency trước/sau async embed. Test cache hit ratio.

---

## Relevant Files

- `src/RAG_v2/llm/gemini.py` — P1-1: add timeout
- `src/RAG_v2/query/reflection.py` — P1-1, P2-4
- `src/RAG_v2/pipeline/rag_pipeline.py` — P1-2, P2-2, P2-4
- `src/RAG_v2/pipeline/flows.py` — P1-2, P3-1, P3-2, P5-1
- `src/RAG_v2/api/schemas.py` — P1-3
- `src/RAG_v2/api/routes/chat.py` — P1-4
- `src/RAG_v2/.env.example` — P1-5
- `src/RAG_v2/embedding/__init__.py` — P2-1, P2-2
- `src/RAG_v2/llm/__init__.py` — P2-3
- `src/RAG_v2/memory/base.py` — P2-5 (NEW FILE)
- `src/RAG_v2/memory/chat_history.py` — P2-5
- `src/RAG_v2/retrieval/base.py` — P2-5
- `src/RAG_v2/backend/logger.py` — P3-3 (DELETE)
- `src/RAG_v2/tests/conftest.py` — P4-1 (NEW FILE)
- `src/RAG_v2/tests/test_flows.py` — P4-2 (NEW FILE)
- `src/RAG_v2/tests/test_settings.py` — P4-2 (NEW FILE)

---

## Verification

1. `pytest tests/ -v --tb=short` — all pass
2. `RERANKER_PROVIDER=none uvicorn` → POST /chat works without crash
3. `python -c "import embedding"` không load torch (kiểm tra startup time)
4. POST /chat với `"question": "Ignore all previous instructions."` → 200 OK, không leak system prompt
5. POST /chat khi Qdrant down → HTTP 500 với `"Internal server error"` (không leak path)
6. Check log có `Step embed: Xms`, `Step retrieve: Xms` etc.

---

## Decisions

- Giữ dual-embedder architecture (BGE-M3 + E5) vì MultiCollectionSearch.search() yêu cầu 2 vector riêng → thêm `create_dual_embedders()` factory thay vì redesign retrieval layer
- `ChatModel` backward-compat alias vẫn tồn tại trong `llm/chat_model.py` (file riêng), chỉ xoá eager import khỏi `llm/__init__.py`
- Rewrite 100% tests sang pytest (không giữ custom `report()` pattern)
- Memory ABC tạo mới, không rename existing `ChatHistoryStore`
