# PROJECT MEMORY — RAG v2 (HUST Academic Chatbot)

> Đọc file này trước khi sửa bất kỳ code nào. Cập nhật khi có thay đổi kiến trúc lớn.

---

## 1. Stack & Công nghệ

| Layer | Tech |
|-------|------|
| API | FastAPI (lifespan pattern, CORS cho localhost:5173 & 8080) |
| Agent | LangGraph `StateGraph` + LangChain StructuredTool |
| Vector store | Qdrant (dense search, BGE-M3 + E5 dual-embed) |
| Keyword store | Elasticsearch (BM25, cùng index name với Qdrant collection) |
| Reranker | BGE Reranker (cross-encoder) |
| Chat LLM | Gemini (thường là `gemini-3.1-flash-lite-preview` qua `GOOGLE_API_KEY`) |
| Agent LLM | LM Studio local (Qwen 2.5 8B) — chuyên xử lý tool-calling |
| Synthesis LLM | Gemini (tổng hợp final answer để tăng tốc độ và chất lượng) |
| DB logging | MongoDB (`MongoLogger`) — lưu lịch sử chat & agent trace |
| Frontend | React + Vite (port 5173) |

---

## 2. Kiến trúc tổng quan

```
Request
  │
  ▼
ComplexityRouter (regex) → chitchat / simple / complex
  │
  ├─► chitchat  → canned response (no LLM)
  │
  ├─► simple    → RAGPipeline.query()
  │                  QueryRouter (classifier, tier1/2/3) → domain
  │                  QueryReflector → rewritten query + entities
  │                  MultiCollectionSearch (Qdrant + ES hybrid, parallel)
  │                  BGEReranker
  │                  Gemini generate / stream
  │
  └─► complex   → RAGPipeline.query_agent()
                    ReActAgent (LangGraph)
                      agent_node (Qwen tool-call)
                      tools_node (execute tools)
                      synthesize_node (Gemini final answer)
```

**Entry point**: `api/main.py` → `create_app()` → `RAGPipeline` khởi tạo 1 lần khi startup.

---

## 3. Module Map

```
RAG_v2/
├── api/
│   ├── main.py              # FastAPI factory + lifespan
│   ├── routes/chat.py       # POST /chat, POST /chat/stream
│   ├── routes/session.py    # GET /sessions
│   ├── routes/health.py     # GET /health
│   └── routes/metrics.py    # GET /metrics
│
├── pipeline/
│   ├── rag_pipeline.py      # RAGPipeline class — orchestrator chính
│   ├── flows.py             # chitchat_flow, rag_flow, rag_flow_stream
│   └── mongo_logger.py      # MongoLogger — log turn & agent trace
│
├── agent/
│   ├── react_agent.py       # ReActAgent (LangGraph graph)
│   ├── complexity_router.py # ComplexityRouter (regex → tier)
│   ├── lc_tools.py          # LANGGRAPH_TOOLS list + TOOL_MAP dict
│   ├── tool_adapters.py     # execute_tool() dispatcher
│   ├── state.py             # AgentState dataclass + ToolResult
│   └── graph_state.py       # AgentGraphState (TypedDict cho LangGraph)
│
├── retrieval/
│   ├── service.py           # RetrievalService (singleton, inject vào tool_adapters)
│   ├── multi_collection_search.py  # MultiCollectionSearch (parallel hybrid)
│   ├── qdrant_store.py      # QdrantStore
│   ├── elasticsearch_store.py      # ElasticsearchStore (keyword_search, metadata_filter_search)
│   ├── hybrid_search.py     # HybridSearch (RRF fusion)
│   ├── metadata_filters.py  # CollectionFilter + per-collection extractors
│   ├── collection_selector.py      # domain → collections mapping
│   ├── validity_filter.py   # lọc chunk không liên quan
│   └── reference_resolver.py
│
├── query/
│   ├── reflection.py        # QueryReflector — rewrite + entity extraction
│   ├── router.py            # QueryRouter (classifier)
│   └── domain_classifier.py
│
├── llm/
│   ├── gemini.py            # GeminiLLM (BaseLLM impl)
│   ├── lm_studio.py         # LMStudioLLM
│   └── self_eval.py         # SelfEvaluator
│
├── schemas/
│   ├── chat.py              # Pydantic models cho request/response
│   └── constants.py         # CLARIFY_SENTINEL
│
├── config/settings.py       # Settings (pydantic BaseSettings, đọc .env)
├── embedding/               # BGEm3Embedder, E5MultilingualEmbedder
├── reranking/               # BGEReranker
├── tools/tavily_search.py   # TavilySearchTool (web fallback)
├── models/database.py       # MongoDB model + create_indexes()
└── routers/auth.py          # JWT auth router
```

---

## 4. Collections (Qdrant/ES)

| Internal name | Nội dung | Key metadata fields |
|--------------|----------|---------------------|
| `ctdt` | Chương trình đào tạo (môn học, tín chỉ) | `major_code`, `major_name` |
| `quydinh` | Quy định học vụ, học bổng, tốt nghiệp | `applicable_major` (list `["K65","K70"]`) |
| `kehoach` | Kế hoạch học kỳ, lịch đăng ký | `date_str` (format `"D/M/YYYY"`) |
| `stsv` | Hỗ trợ sinh viên, biểu mẫu, thủ tục | (không filter metadata) |

**Alias trong agent tools**: `chuong_trinh` → `ctdt`, `quy_dinh` → `quydinh`, `ke_hoach` → `kehoach`, `ho_tro_sv` → `stsv`

---

## 5. Data Schemas chính

### ChatRequest (POST /chat body)
```python
question: str          # max 4096 chars
mode: "auto"|"rag"|"agent"
top_k: int = 5
history: List[{role, content}]
session_id: str | None
user_context: UserContext | None  # {student_id, cohort, major, major_code, full_name}
```

### ChatResponse
```python
answer: str
retrieved_documents: List[RetrievedDocument]  # {rank, content, score, collection, metadata}
intent: str           # "rag" | "chitchat"
mode: str             # "rag_v2" | "agent" | "chitchat"
route: str            # "simple" | "complex" | "chitchat"
tool_calls: List[AgentToolCall]
agent_trace: AgentTracePayload
timings_ms: Dict[str, float]
session_id: str
```

### AgentState (internal)
```python
query: str
session_id: str
tool_results: List[ToolResult]   # truncated to last 3 (context window)
_log_tool_results: List[ToolResult]  # full log cho MongoDB
tool_call_history: List[str]
iteration: int
max_iterations: int = 4
final_answer: str | None
route: "simple"|"complex"|"chitchat"
```

---

## 6. Agent Tools

| Tool name | Khi dùng | Tính chất |
|-----------|----------|-----------|
| `rag_search` | Tìm 1 collection cụ thể | Normal |
| `multi_rag_search` | Tìm ≥2 collections cùng lúc | Normal |
| `compare_cohorts` | So sánh 2 **khóa** (K65 vs K70) | **Terminal** (chuyển thẳng sang Synthesis) |
| `compare_programs` | So sánh 2 **mã ngành** (IT-E6 vs IT-E7) | **Terminal** (chuyển thẳng sang Synthesis) |
| `web_search` | Tavily fallback khi DB rỗng | Normal |
| `clarify_question` | Hỏi lại user (max 1 lần/turn) | **Terminal** (dừng agent) |

> **Lưu ý Terminal Tools**: Các tool như so sánh sẽ gọi RAG song song bên dưới (trả về full data). Thay vì tốn ~75s cho Qwen 8B duyệt lại, đồ thị LangGraph sẽ tự động ngắt loop (`_after_tools`) và chuyển thẳng sang `synthesize_node` (dùng Gemini) để sinh câu trả lời mượt mà, giảm latency.

---

## 7. Routing Logic

### Tier 1 — ComplexityRouter (regex, trước khi vào pipeline)
- `chitchat` → greeting, cảm ơn, tạm biệt
- `complex` → "so sánh", 2 mã khóa Kxx, 2 mã ngành, nhiều câu hỏi
- `simple` → default

### Tier 2 — QueryRouter (domain classifier, trong RAGPipeline)
- Phân loại domain: `ctdt | quydinh | kehoach | stsv`
- Output: `{intent, domain, domains, confidence, probabilities}`

### Tier 3 — LLM fallback (khi confidence < 0.55)
- Gọi Gemini để classify domain, override kết quả classifier

---

## 8. Metadata Filter Flow (Pre-search)

```
build_collection_filters(query, resolved_major, resolved_cohort)
  → CollectionFilter per collection (ordered ES fallback chain)
       ctdt    : major_code exact → major_name fuzzy → major_code OR null → no filter
       quydinh : applicable_major (cohort) OR null → no filter
       kehoach : date wildcard (nếu query có năm/tháng) → no filter
       stsv    : no filter
  → MultiCollectionSearch._resolve_filter_with_fallback()
       → ES metadata_filter_search() → doc IDs
       → Qdrant HasIdCondition (restrict vector search)
```

---

## 9. Major Codes (canonical)

```
IT-E6  = Việt-Nhật (ICTVJ, HEDSPI)
IT-E7  = Toàn cầu (ICTG, Global ICT)
IT-E10 = Data AI
IT-E15 = An toàn không gian số
IT-EP  = Việt-Pháp
IT1    = Khoa học máy tính
IT2    = Kỹ thuật máy tính
MI1    = Toán-Tin
MI2    = Hệ thống thông tin quản lý
```

Cohort format: `K65`, `K70`, `K67` (số 2–3 chữ số, prefix `K`)

---

## 10. Conventions & Naming Rules

- **File naming**: `snake_case.py` cho tất cả Python modules
- **Class naming**: `PascalCase` (VD: `MultiCollectionSearch`, `ReActAgent`)
- **Async**: Tất cả pipeline entry points là `async`. ES `keyword_search` vẫn sync (gọi trong `asyncio.gather` qua thread).
- **Settings**: Dùng `config/settings.py` (pydantic BaseSettings). KHÔNG hardcode config.
- **Injection**: `RetrievalService.from_settings(settings)` tạo 1 lần, inject vào cả `RAGPipeline` lẫn `tool_adapters`.
- **Logging**: `logger = logging.getLogger(__name__)` ở top mỗi file.
- **Fallback chain**: Mọi component đều có fallback (agent crash → RAG v2, filter rỗng → full search, reflection fail → original query).
- **Context budget**: Lịch sử chat trim tới 8 turns / 2000 chars. Tool results trim tới 3 kết quả gần nhất (context window), nhưng log đầy đủ vào MongoDB.
- **ID format trong search result**: `"{collection_name}/{doc_id}"` (VD: `"ctdt/abc123"`)
- **Score fusion**: min-max normalize vector + keyword, rồi weighted sum: `score = vector_weight * norm_vec + keyword_weight * norm_kw`
- **Adaptive fusion**: Query có "môn", "học phần", mã môn → tăng `keyword_weight` lên 0.6 (course_query_keyword_bias)
- **CLARIFY_SENTINEL**: Token đặc biệt trong `schemas/constants.py` để detect clarify_question output
- **Module Documentation**: Mỗi khi update code vào một module, BẮT BUỘC phải kiểm tra và cập nhật file `MODULE.md` trong module đó (nếu có) để phản ánh các thay đổi.

---

## 11. Key ENV Variables

```env
GOOGLE_API_KEY=...          # Gemini
LM_STUDIO_BASE_URL=...      # Local agent LLM
QDRANT_HOST / QDRANT_PORT
ELASTICSEARCH_HOST / ELASTICSEARCH_PORT
MONGODB_URI / MONGODB_DATABASE
MONGODB_ENABLED=true
AGENT_ENABLED=true
AGENT_SYNTHESIS_PROVIDER=gemini
TAVILY_API_KEY=...
RERANKER_PROVIDER=bge
```

---

## 12. Cạm bẫy thường gặp

- **ITE6 ≠ IT-E6**: Input user hay viết compact, cần `_normalise_major_text()` trước khi so sánh.
- **applicable_major** trong `quydinh` là list (`["K65","K70"]`) — ES `term` query match tự động.
- Agent LLM (Qwen) chỉ dùng **LM Studio local** — không dùng Gemini để tool-call (quá chậm).
- `tool_results` trong luồng Agent được cắt tỉa động (dynamic trimming) dựa trên token budget (`_context_token_budget=3200`), cắt bớt các content dài quá 600 chars và xoá dần history cũ. Log đầy đủ vẫn lưu qua `_log_tool_results` vào MongoDB.
- `rag_flow_stream` (và `query_stream`) tạo ra các chunk kết quả. Metadata được sinh ra ở cuối luồng và gửi xuống frontend dưới dạng SSE event: `{"type": "metadata", ...}` qua `api/routes/chat.py`.
- Mỗi ES index name = Qdrant collection name (cùng key trong `settings.collections`).


---

## 13. Mobile App (React Native)
- Đang phát triển kiến trúc Mobile App dùng React Native / Expo.
- Có monorepo structure share TypeScript types giữa Web và Mobile.
- Dùng Server-Sent Events (SSE) tương thích với React Native để stream chat.
- Xác thực bằng `expo-secure-store`.

---

## 14. Known Bugs & Kiến trúc cần chú ý (Cập nhật liên tục)
- **`query_agent` blocking async loop (ĐÃ FIX)**: Hàm `query_agent` chạy đồng bộ, nhưng tại FastAPI route (`api/routes/chat.py`) đã được wrap trong `anyio.to_thread.run_sync` và `loop.run_in_executor` để không block event loop.
- **Mất `user_context` trong luồng Agent**: Hàm `query_agent` có nhận `user_context` nhưng KHÔNG truyền xuống `self.agent.run(...)` vì ReActAgent chưa support. Tuy nhiên, luồng reflection bên ngoài agent (trước khi vào LangGraph) VẪN CÓ `user_context`.
- **`validity_filter` không được dùng trong Agent tool**: Hàm `_rag_search` trong `tool_adapters.py` chỉ gọi `searcher` và `reranker`, KHÔNG gọi `validity_filter` (bộ lọc này hiện chỉ hoạt động trong `rag_flow` cơ bản).
- **Qwen 8B lờ đi negative constraints**: Các rule phức tạp ("KHÔNG dùng ke_hoach cho môn học kỳ mấy") dễ bị model size nhỏ lờ đi.
- **Truy xuất Session API Coroutine Bug (ĐÃ FIX)**: Endpoint `/sessions` từng bị lỗi trả về coroutine thay vì list. Đã fix trong `MongoLogger.list_sessions()` bằng cách trả về đồng bộ.
- **Reranker loại nhầm văn bản dạng bảng (ĐÃ FIX)**: Do BGE cross-encoder thường chấm điểm logit âm cho văn bản bảng biểu, các chunk có `has_table: true` sẽ được áp dụng ngưỡng riêng `table_score_threshold` (mặc định -3.0) thay vì `score_threshold` (0.0).
- **Table Retrieval Failure (Recall & Rerank)**: Fixed an issue where specific keywords (e.g., "hiến máu") in table rows were missed due to low retrieval limits (20) and strict reranking (0.0). Increased retrieval limits (50 candidates) and lowered table rerank threshold to -5.0. Verified that correct chunks reach the LLM.
- **LLM bỏ qua URL trong chunk (ĐÃ FIX)**: Prompt hệ thống trước đây dặn "Không viết 'tại đây' nếu không có URL", gây hiểu nhầm làm LLM ẩn luôn cả URL thực tế. Đã cập nhật `prompts.py` yêu cầu LLM BẮT BUỘC phải đưa URL vào câu trả lời nếu tài liệu có cung cấp.
