# 📋 RAG v2 System — Task List theo Phase

> **Hệ thống chatbot đại học** với kiến trúc 8 Layers:
> Embedding → Hybrid Retrieval → Reranking → Query Router & Reflection → Chat Model → Self Evaluation → Tool Search → MongoDB Memory

---

## Phase 1: Embedding Layer + Hybrid Retrieval

> **Mục tiêu**: Xây dựng nền tảng embedding ensemble và hybrid search với Qdrant + Elasticsearch.

### Tasks

- [ ] **1.1 Embedding Layer**
  - [ ] Implement `BGEm3Embedder` trong `embedding/bge_m3.py` — wrapper cho BAAI/bge-m3
  - [ ] Implement `E5MultilingualEmbedder` trong `embedding/e5_multilingual.py` — wrapper cho multilingual-e5-large
  - [ ] Implement `EnsembleEmbedder` trong `embedding/ensemble.py` — kết hợp 2 model với weighted average
  - [ ] Viết base class `BaseEmbedder` (abstract) cho chuẩn interface
  - [ ] Benchmark embedding speed + quality trên dataset đại học

- [ ] **1.2 Qdrant Vector Store**
  - [ ] Setup Qdrant (Docker hoặc Qdrant Cloud)
  - [ ] Implement `QdrantStore` trong `retrieval/qdrant_store.py`
    - [ ] `index_documents()` — upsert chunks + embeddings
    - [ ] `search()` — vector search với score threshold
    - [ ] `delete_by_metadata()` — xóa theo source file
  - [ ] Cấu hình collection với 2 vector fields (bge-m3, e5) cho ensemble

- [ ] **1.3 Elasticsearch BM25**
  - [ ] Setup Elasticsearch (Docker)
  - [ ] Implement `ElasticsearchStore` trong `retrieval/elasticsearch_store.py`
    - [ ] `index_documents()` — index chunks với Vietnamese analyzer
    - [ ] `keyword_search()` — BM25 search
    - [ ] Cấu hình custom analyzer cho tiếng Việt (lowercase, unicode folding)

- [ ] **1.4 Hybrid Search**
  - [ ] Implement `HybridSearcher` trong `retrieval/hybrid_search.py`
    - [ ] Vector search (Qdrant) + Keyword search (Elasticsearch) → RRF fusion
    - [ ] Configurable weights cho vector vs keyword
    - [ ] Score normalization
  - [ ] Viết config trong `retrieval/config.py` (top_k, thresholds, weights)

### ✅ Kết quả đạt được sau Phase 1

| Deliverable | Mô tả |
|------------|-------|
| **Dual Embedding** | 2 model BGE-M3 + E5-large chạy ensemble cho quality cao |
| **Vector Store** | Qdrant lưu trữ và search vector |
| **Keyword Search** | Elasticsearch BM25 cho exact match |
| **Hybrid Search** | Kết hợp Vector + Keyword qua RRF |

---

## Phase 2: Reranking + Query Router & Reflection

> **Mục tiêu**: Thêm reranking layer và xây dựng query router thông minh.

### Tasks

- [x] **2.1 Reranking Layer**
  - [x] Implement `BGEReranker` trong `reranking/bge_reranker.py`
    - [x] Load model BAAI/bge-reranker-v2-m3
    - [x] `rerank(query, documents)` → sorted docs với relevance score
    - [x] Top-K selection sau rerank (default: top 5)
  - [ ] Tích hợp reranker vào hybrid search pipeline

- [x] **2.2 Query Router**
  - [x] Implement `QueryRouter` trong `query/router.py`
    - [x] Phân loại intent: Chit-chat / Cần RAG / Cần Search Tool
    - [x] Dùng LLM (OpenAI) để classify với few-shot prompt
    - [x] Return routing decision: `{"intent": "rag"|"chitchat"|"tool_search"}`
  - [x] Viết prompts trong `query/prompts.py`

- [x] **2.3 Query Reflection**
  - [x] Implement `QueryReflector` trong `query/reflection.py`
    - [x] Rewrite query — viết lại rõ ràng hơn
    - [x] Clarify — làm rõ câu hỏi mơ hồ
    - [x] Format — chuẩn hóa format query
    - [x] Add context — thêm context từ chat history (MongoDB)
  - [ ] Chain: Router → Reflection → Embedding (cho RAG flow)

### ✅ Kết quả đạt được sau Phase 2

| Deliverable | Mô tả |
|------------|-------|
| **Reranker** | BGE-v2-M3 rerank kết quả, chọn top 5 chính xác nhất |
| **Router** | Tự phân loại chitchat / RAG / tool search |
| **Reflection** | Query được viết lại, làm rõ, thêm context trước khi search |

---

## Phase 3: Chat Model + Self Evaluation

> **Mục tiêu**: Xây dựng chat model layer và cơ chế tự đánh giá câu trả lời.

### Tasks

- [x] **3.1 Chat Model Layer**
  - [x] Implement `ChatModel` trong `llm/chat_model.py`
    - [x] Wrapper cho OpenAI GPT API (hoặc model khác)
    - [x] `generate(query, context, history)` → response
    - [x] Streaming response support
  - [x] Thiết kế System Prompt trong `llm/prompts.py`
    - [x] Prompt cho RAG answer (có context, trích dẫn nguồn)
    - [x] Prompt cho Chitchat (chào hỏi, thân thiện)
    - [x] Prompt cho university domain (ngữ cảnh đại học)

- [x] **3.2 Self Evaluation**
  - [x] Implement `SelfEvaluator` trong `llm/self_eval.py`
    - [x] Check response quality: có trả lời đúng câu hỏi không?
    - [x] Check hallucination: response có dựa trên context không?
    - [x] Check completeness: response có đầy đủ không?
    - [x] Return decision: `{"pass": true/false, "reason": "..."}`
  - [ ] Nếu FAIL → trigger fallback (Tavily search → re-generate)

### ✅ Kết quả đạt được sau Phase 3

| Deliverable | Mô tả |
|------------|-------|
| **Chat Model** | LLM wrapper với streaming, multi-prompt support |
| **Self Evaluation** | Tự kiểm tra chất lượng answer, trigger fallback nếu kém |
| **Quality Gate** | Đảm bảo user nhận câu trả lời chất lượng |

---

## Phase 4: Tool Search (Tavily) + MongoDB Memory

> **Mục tiêu**: Thêm web search fallback và persistence layer.

### Tasks

- [x] **4.1 Tavily Search Tool**
  - [x] Implement `TavilySearchTool` trong `tools/tavily_search.py`
    - [x] `search(query)` → web search results
    - [x] Parse và format kết quả thành context cho LLM
    - [ ] Rate limiting và error handling
  - [ ] Tích hợp vào self-eval fallback pipeline:
    - Self-eval FAIL → Tavily search → Chat Model → Final answer

- [x] **4.2 MongoDB Memory Layer**
  - [ ] Setup MongoDB (Docker hoặc MongoDB Atlas)
  - [x] Implement `MongoClient` trong `memory/mongo_client.py`
    - [x] Connection pooling, retry logic
  - [x] Implement `ChatHistoryStore` trong `memory/chat_history.py`
    - [x] `save_message(session_id, role, content)` — lưu tin nhắn
    - [x] `get_history(session_id, limit)` — lấy N tin gần nhất
    - [x] `clear_history(session_id)` — xóa lịch sử
  - [x] Implement `ConversationState` trong `memory/conversation.py`
    - [x] Lưu final answer + metadata (sources, scores)
    - [x] Update conversation state (active/closed)
    - [x] Track session metadata (created_at, last_active)

### ✅ Kết quả đạt được sau Phase 4

| Deliverable | Mô tả |
|------------|-------|
| **Tavily Search** | Web search fallback khi RAG không đủ |
| **Chat History** | MongoDB lưu đầy đủ lịch sử chat |
| **Conversation State** | Quản lý trạng thái phiên hội thoại |

---

## Phase 5: FastAPI Backend + Pipeline Integration

> **Mục tiêu**: Kết nối tất cả layers thành pipeline hoàn chỉnh, expose qua API.

### Tasks

- [x] **5.1 Pipeline Orchestration**
  - [x] Implement `RAGPipeline` trong `pipeline/rag_pipeline.py`
    - [x] Kết nối: Router → Reflection → Embedding → Hybrid Search → Rerank → Chat Model → Self Eval
    - [x] `process(user_message, session_id)` — entry point
  - [x] Implement flows trong `pipeline/flows.py`
    - [x] `chitchat_flow()`: Router → Chat Model → Save MongoDB
    - [x] `rag_flow()`: Router → Reflection → Embed → Search → Rerank → Top 5 → Chat Model → Self Eval → (Tavily fallback) → Save MongoDB

- [x] **5.2 FastAPI Backend**
  - [x] Implement FastAPI app trong `api/main.py`
    - [x] CORS, middleware, error handling
  - [x] Implement routes:
    - [x] `POST /chat` — SSE streaming response trong `api/routes/chat.py`
    - [x] `GET /health` — health check trong `api/routes/health.py`
  - [x] Pydantic schemas trong `api/schemas.py`
    - [x] `ChatRequest`, `ChatResponse`, `HealthResponse`
  - [x] Singleton pattern cho models (tránh load lại)

- [x] **5.3 Configuration**
  - [x] Implement `Settings` trong `config/settings.py`
    - [x] Dùng Pydantic BaseSettings + `.env` file
    - [x] Config cho: OpenAI, Qdrant, Elasticsearch, MongoDB, Tavily, Models
  - [x] Tạo `.env.example` với tất cả biến môi trường

### ✅ Kết quả đạt được sau Phase 5

| Deliverable | Mô tả |
|------------|-------|
| **Full Pipeline** | End-to-end: User → Router → (Chitchat/RAG) → Response |
| **API Server** | FastAPI với streaming, health check, sẵn sàng kết nối frontend |
| **Config** | Centralized settings, dễ deploy |

---

## Phase 6: Evaluation + Optimization

> **Mục tiêu**: Đánh giá toàn diện hệ thống và tối ưu.

### Tasks

- [ ] **6.1 Evaluation Framework**
  - [ ] Tạo evaluation dataset cho domain đại học (100+ Q&A pairs)
  - [ ] Đánh giá Retrieval: Hit Rate, MRR, NDCG
  - [ ] Đánh giá Response: Faithfulness, Relevance, Completeness
  - [ ] So sánh ensemble embedding vs single model
  - [ ] So sánh có/không có reranking

- [ ] **6.2 Optimization**
  - [ ] Tune hybrid search weights (vector vs keyword ratio)
  - [ ] Tune reranker top-K
  - [ ] Optimize embedding batch size
  - [ ] Caching layer cho repeated queries
  - [ ] Latency profiling và bottleneck identification

### ✅ Kết quả đạt được sau Phase 6

| Deliverable | Mô tả |
|------------|-------|
| **Evaluation Report** | Metrics đầy đủ cho retrieval + response quality |
| **Optimized System** | System được tune cho domain đại học |
| **Benchmark** | So sánh các config khác nhau |

---

## Phase 7: CTDT Chunker & Indexing

> **Mục tiêu**: Bổ sung dữ liệu **chương trình đào tạo** (CTDT) vào hệ thống — hiện là collection duy nhất chưa được index. CTDT có cấu trúc bảng (mã HP, tên môn, số tín chỉ, học kỳ, bắt buộc/tự chọn) khác biệt hoàn toàn với văn bản pháp lý.

### Context

- Dữ liệu nằm ở `data/ctdt/` — 6 khoa: `cokhi`, `dien-dientu`, `hoa`, `soict`, `toan`, `vatlieu`
- Mỗi khoa có PDF chương trình đào tạo (ví dụ: `CTDT-CN.KHMT-K70-V2025.pdf`)
- `data/ctdt/soict/output_docling/` đã có Markdown đầu ra từ docling — cần chunker parse tiếp
- Chưa có `CTDTChunker` nào trong `chunking/chunker/`

### Tasks

- [ ] **7.1 Phân tích cấu trúc CTDT**
  - [ ] Khảo sát format Markdown output của docling từ `data/ctdt/soict/output_docling/`
  - [ ] Xác định pattern bảng: mã HP, tên môn, số TC, học kỳ, loại (BB/TC)
  - [ ] Xác định cấu trúc phân cấp: Khối kiến thức → Học kỳ → Môn học
  - [ ] Document spec chunking cho reviewer

- [ ] **7.2 Implement `CTDTChunker`**
  - [ ] Tạo `chunking/chunker/ctdt_chunker.py` — kế thừa `DocumentChunker` (base)
  - [ ] Parse bảng curriculum thành structured chunks:
    - **Parent chunk**: toàn bộ một khối kiến thức (ví dụ: "Kiến thức cơ sở ngành")
    - **Child chunk**: một môn học với đầy đủ metadata
  - [ ] Metadata cho mỗi chunk:
    ```python
    {
        "source": "CTDT-CN.KHMT-K70",
        "khoa": "soict",
        "nganh": "Khoa học máy tính",
        "khoa_hoc": "K70",
        "loai_kien_thuc": "Cơ sở ngành | Chuyên ngành | Đại cương",
        "hoc_ky": 3,
        "loai_mon": "Bắt buộc | Tự chọn",
        "ma_hp": "IT3040",
        "so_tin_chi": 3,
        "parent_id": "<uuid-of-parent-chunk>",   # for hierarchical retrieval
    }
    ```
  - [ ] Xử lý môn học tự chọn theo nhóm (group electives)
  - [ ] Unit test: parse 1 file SOICT, verify số chunk + metadata đúng

- [ ] **7.3 Batch Indexing Pipeline**
  - [ ] Tạo `pipeline/index_ctdt.py` — script index toàn bộ `data/ctdt/`
    - [ ] Convert PDF → Markdown (tái dùng docling pipeline hiện tại)
    - [ ] Chạy `CTDTChunker` cho từng file
    - [ ] Upsert vào Qdrant collection `ctdt`
    - [ ] Index vào Elasticsearch index `ctdt` với field `ma_hp`, `ten_mon`, `nganh`
  - [ ] Config trong `config/settings.py`: thêm `ctdt_qdrant_collection`, `ctdt_es_index`
  - [ ] Verify: query "môn học học kỳ 3 ngành KHMT" trả về kết quả đúng

- [ ] **7.4 Cập nhật `MultiCollectionSearch`**
  - [ ] Đăng ký collection `ctdt` vào `MultiCollectionSearch` trong `pipeline/rag_pipeline.py`
  - [ ] Verify end-to-end: câu hỏi về CTDT → Router → RAG flow → kết quả ctdt

### ✅ Kết quả đạt được sau Phase 7

| Deliverable | Mô tả |
|------------|-------|
| **CTDTChunker** | Parser chuyên biệt cho bảng curriculum — sinh parent-child chunks |
| **CTDT Collection** | Toàn bộ 6 khoa được index vào Qdrant + Elasticsearch |
| **Full Coverage** | Hệ thống phủ đủ 4 domain: `ctdt`, `quydinh`, `kehoach`, `stsv` |

---

## Phase 8: Collection-aware Query Routing

> **Mục tiêu**: Tận dụng kết quả phân loại domain của `DomainClassifier` để tập trung search vào collection phù hợp, thay vì luôn search tất cả 4 collections — giảm noise và tăng precision.

### Context

- `DomainClassifier` (trong `query/domain_classifier.py`) đã trả về `domain` trong kết quả route: `{"intent": "rag", "domain": "quydinh", "confidence": 0.87}`
- `rag_flow()` trong `pipeline/flows.py` hiện **bỏ qua `domain`**, luôn gọi `MultiCollectionSearch` với tất cả collections
- `MultiCollectionSearch.search()` chưa có tham số lọc collection

### Tasks

- [ ] **8.1 Implement `CollectionSelector`**
  - [ ] Tạo `retrieval/collection_selector.py`
  - [ ] Logic chọn collections dựa trên domain + confidence:
    ```python
    DOMAIN_TO_COLLECTIONS = {
        "ctdt":     ["ctdt"],
        "quydinh":  ["quydinh"],
        "kehoach":  ["kehoach"],
        "stsv":     ["stsv"],
    }
    CONFIDENCE_THRESHOLD = 0.65  # dưới ngưỡng → search tất cả
    MULTI_DOMAIN_FALLBACK = ["quydinh", "stsv"]  # fallback mặc định
    ```
  - [ ] Hàm `select(domain, confidence) -> List[str]`:
    - Confidence ≥ 0.65 → trả về collections theo map
    - Confidence < 0.65 → trả về `MULTI_DOMAIN_FALLBACK`
    - Domain = `None` → trả về tất cả 4 collections
  - [ ] Unit test: kiểm tra 6 trường hợp (4 domain rõ + confidence thấp + None)

- [ ] **8.2 Cập nhật `MultiCollectionSearch`**
  - [ ] Thêm tham số `active_collections: Optional[List[str]]` vào `search()`
  - [ ] Nếu `active_collections` được truyền → chỉ search các searchers có tên nằm trong list
  - [ ] Log warning nếu collection yêu cầu chưa được đăng ký

- [ ] **8.3 Cập nhật `rag_flow()`**
  - [ ] Thêm tham số `routing_result: Dict[str, Any]` vào hàm
  - [ ] Gọi `CollectionSelector.select(domain, confidence)` → `target_collections`
  - [ ] Truyền `target_collections` vào `searcher.search()`
  - [ ] Log: "Domain: quydinh (conf=0.87) → searching collections: ['quydinh']"
  - [ ] Trả về `target_collections` trong result dict để debug

- [ ] **8.4 Cập nhật `RAGPipeline.process()`**
  - [ ] Pass `routing_result` (gồm `domain` + `confidence`) xuống `rag_flow()`
  - [ ] Expose `target_collections` trong response metadata

- [ ] **8.5 Evaluation**
  - [ ] So sánh precision@5: domain-aware routing vs all-collection search
  - [ ] Đo latency: tìm kiếm 1 collection vs 4 collections

### ✅ Kết quả đạt được sau Phase 8

| Deliverable | Mô tả |
|------------|-------|
| **CollectionSelector** | Tự chọn collection theo domain, fallback khi confidence thấp |
| **Targeted Search** | Câu hỏi về CTDT chỉ search `ctdt`, không bị nhiễu từ `stsv` |
| **Latency giảm** | 1-collection search nhanh hơn ~3x so với 4-collection |

---

## Phase 9: Parent-Child Retrieval

> **Mục tiêu**: Khi retriever trả về **child chunk** (đoạn nhỏ, chính xác), hệ thống tự động fetch **parent chunk** (đoạn lớn hơn, đầy đủ ngữ cảnh) để LLM có đủ thông tin generate câu trả lời tốt hơn.

### Context

- `ArticleLevelLegalChunker` (trong `chunking/chunker/hierarchical_legal_chunker.py`) đã tạo parent-child chunks với `parent_id` trong metadata
- `CTDTChunker` (Phase 7) cũng sẽ tạo parent-child chunks
- Hiện tại `rag_flow()` dùng child chunks trực tiếp → LLM đôi khi thiếu context (ví dụ: "khoản 2 điều 5" không đủ nghĩa nếu tách khỏi "điều 5")
- Qdrant hỗ trợ lookup by ID → có thể fetch parent bằng `parent_id`

### Tasks

- [ ] **9.1 Implement `HierarchicalRetriever`**
  - [ ] Tạo `retrieval/hierarchical_retriever.py`
  - [ ] Hàm `expand_to_parents(documents, qdrant_stores) -> List[Dict]`:
    - Với mỗi document có `metadata.parent_id` → fetch parent từ Qdrant
    - Nếu không có `parent_id` → giữ nguyên document
    - Deduplication: nếu ≥2 child chunks có cùng parent → chỉ fetch parent 1 lần
  - [ ] Hàm `merge(child_docs, parent_docs) -> List[Dict]`:
    - Giữ child chunk trong list (để reranking vẫn dùng child score)
    - Thêm parent chunk vào context với label `[PARENT CONTEXT]`
    - Không tính parent vào top-K limit (metadata-only context)
  - [ ] Config flag: `enable_parent_retrieval: bool = True`
  - [ ] Unit test: mock Qdrant → verify parent được fetch đúng

- [ ] **9.2 Cập nhật `QdrantStore`**
  - [ ] Thêm method `get_by_ids(ids: List[str]) -> List[Dict]`
  - [ ] Dùng `qdrant_client.retrieve(collection_name, ids=[...])` 

- [ ] **9.3 Cập nhật `rag_flow()`**
  - [ ] Sau bước Rerank → gọi `HierarchicalRetriever.expand_to_parents()`
  - [ ] Build context: child chunks (cho relevance) + parent chunks (cho completeness)
  - [ ] Format context riêng biệt:
    ```
    [1] Điều 5, Quyết định 1234/QĐ-ĐHBK
    <nội dung child chunk>
    
    [CONTEXT ĐẦY ĐỦ - Điều 5]
    <nội dung parent chunk>
    ```
  - [ ] Trả về `has_parent_expansion: bool` trong result

- [ ] **9.4 Evaluation**
  - [ ] So sánh Faithfulness score: có/không có parent expansion
  - [ ] Đo lường token count tăng thêm khi dùng parent context

### ✅ Kết quả đạt được sau Phase 9

| Deliverable | Mô tả |
|------------|-------|
| **HierarchicalRetriever** | Tự fetch parent chunk khi child chunk được retrieve |
| **Richer Context** | LLM nhận cả child (relevance) lẫn parent (completeness) |
| **Better Faithfulness** | Giảm hallucination do thiếu context văn bản pháp lý |

---

## Phase 10: Query Decomposition

> **Mục tiêu**: Xử lý câu hỏi phức hợp (multi-part questions) bằng cách tách thành các sub-queries độc lập, retrieve riêng lẻ, rồi merge context trước khi generate — thay vì dùng 1 query duy nhất tìm nhiều thứ cùng lúc.

### Context

- Ví dụ câu hỏi phức hợp từ sinh viên:
  - *"So sánh điều kiện xét học bổng loại A và điều kiện miễn học phí?"*
  - *"Tôi cần biết lịch thi và quy định về thi lại cùng lúc"*
  - *"Học kỳ 3 ngành KHMT học những môn gì và học phí là bao nhiêu?"*
- Hiện tại `QueryReflector` chỉ rewrite → 1 query duy nhất → miss một nửa câu hỏi
- Chưa có `QueryDecomposer` nào trong `query/`

### Tasks

- [ ] **10.1 Implement `QueryDecomposer`**
  - [ ] Tạo `query/decomposer.py`
  - [ ] Tích hợp với LLM (Gemini/OpenAI) qua `BaseLLM`
  - [ ] Viết prompt phát hiện + tách câu hỏi phức hợp trong `query/prompts.py`:
    ```
    Phân tích câu hỏi sau. Nếu câu hỏi hỏi nhiều thông tin khác nhau,
    hãy tách thành các sub-query độc lập (tối đa 3).
    Trả về JSON: {"is_complex": bool, "sub_queries": [...]}
    ```
  - [ ] Hàm `decompose(query: str) -> DecompositionResult`:
    ```python
    @dataclass
    class DecompositionResult:
        is_complex: bool
        sub_queries: List[str]   # 1 item nếu không phức hợp
        original: str
    ```
  - [ ] Threshold: chỉ decompose nếu `is_complex=True` VÀ sub_queries có ≥ 2 items
  - [ ] Unit test: 5 câu phức hợp + 5 câu đơn giản → verify đúng

- [ ] **10.2 Implement `MultiQueryRetriever`**
  - [ ] Tạo `retrieval/multi_query_retriever.py`
  - [ ] Hàm `retrieve_multi(sub_queries, embedders, searcher, cfg) -> List[Dict]`:
    - Embed + search song song cho từng sub-query (dùng `ThreadPoolExecutor`)
    - Merge tất cả kết quả thô (có thể có duplicate)
    - Global RRF fusion trên toàn bộ results từ mọi sub-query
    - Deduplication theo chunk ID trước khi rerank
  - [ ] Đảm bảo metadata của từng chunk ghi rõ `matched_sub_query`

- [ ] **10.3 Cập nhật `rag_flow()`**
  - [ ] Sau reflection → gọi `QueryDecomposer.decompose()`
  - [ ] Nếu `is_complex=False` → flow hiện tại (không thay đổi)
  - [ ] Nếu `is_complex=True` → gọi `MultiQueryRetriever.retrieve_multi(sub_queries)`
  - [ ] Tiếp tục: Rerank → Parent Expansion → Generate như bình thường
  - [ ] Config flag: `enable_decomposition: bool = True`
  - [ ] Trả về `sub_queries: List[str]` trong result dict

- [ ] **10.4 Evaluation**
  - [ ] Tạo test set 20 câu hỏi phức hợp từ domain đại học
  - [ ] So sánh Answer Completeness: có/không có decomposition
  - [ ] Đo latency overhead của bước decompose (LLM call thêm)

### ✅ Kết quả đạt được sau Phase 10

| Deliverable | Mô tả |
|------------|-------|
| **QueryDecomposer** | Phát hiện và tách câu hỏi phức hợp → sub-queries |
| **MultiQueryRetriever** | Retrieve song song cho từng sub-query, RRF merge |
| **Complete Answers** | LLM nhận context đầy đủ cho câu hỏi nhiều phần |

---

## Phase 11: Evaluation Framework mở rộng

> **Mục tiêu**: Xây dựng bộ đánh giá toàn diện cho tất cả 4 domains, đo lường tác động của từng cải tiến (Phase 8, 9, 10), cung cấp số liệu cho báo cáo.

### Context

- Hiện đã có evaluation scripts trong `evaluation/` cho `stsv` (39 queries)
- Chưa có dataset cho `ctdt`, `quydinh`, `kehoach`
- Chưa có end-to-end evaluation (chỉ có retrieval-level)
- Cần số liệu so sánh A/B để chứng minh giá trị của từng cải tiến

### Tasks

- [ ] **11.1 Build Evaluation Datasets**
  - [ ] `quydinh`: 40 câu Q&A từ các quy định ĐHBK (học bổng, ngoại ngữ, rèn luyện)
  - [ ] `kehoach`: 30 câu Q&A từ kế hoạch học tập, lịch thi, đăng ký môn
  - [ ] `ctdt`: 30 câu Q&A từ chương trình đào tạo (môn học, số TC, tiên quyết)
  - [ ] `stsv`: mở rộng từ 39 → 70 câu Q&A
  - [ ] Format chuẩn: `{"query": str, "answer": str, "relevant_chunks": [str], "domain": str}`
  - [ ] Lưu vào `evaluation/data/<domain>_eval_dataset.json`

- [ ] **11.2 Retrieval Evaluation**
  - [ ] Tạo `evaluation/evaluate_retrieval_all.py`
  - [ ] Metrics: Hit@1, Hit@3, Hit@5, MRR@5, NDCG@5
  - [ ] Chạy cho từng domain riêng + tổng hợp
  - [ ] So sánh A/B:
    - Baseline: search tất cả 4 collections (hiện tại)
    - Phase 8: domain-aware routing
    - Phase 9: + parent expansion

- [ ] **11.3 Generation Evaluation (LLM-as-Judge)**
  - [ ] Tạo `evaluation/evaluate_generation_all.py`
  - [ ] Dùng Gemini/GPT-4o làm judge (1–5 scale):
    - **Faithfulness**: câu trả lời có dựa trên context không? (chống hallucination)
    - **Answer Relevance**: có trả lời đúng câu hỏi không?
    - **Completeness**: có đủ thông tin không?
  - [ ] So sánh A/B: baseline vs + parent expansion vs + decomposition

- [ ] **11.4 End-to-End Benchmark**
  - [ ] Tạo `evaluation/benchmark_e2e.py` — chạy pipeline đầy đủ trên toàn bộ dataset
  - [ ] Output report CSV: `evaluation/results/benchmark_<timestamp>.csv`
  - [ ] Summary table: so sánh 4 configurations:

    | Config | Hit@5 | MRR | Faithfulness | Relevance | Latency (p95) |
    |--------|-------|-----|-------------|-----------|---------------|
    | Baseline (Phase 1-6) | | | | | |
    | + Domain Routing (P8) | | | | | |
    | + Parent Retrieval (P9) | | | | | |
    | + Decomposition (P10) | | | | | |

### ✅ Kết quả đạt được sau Phase 11

| Deliverable | Mô tả |
|------------|-------|
| **Eval Datasets** | 170+ Q&A pairs phủ 4 domains |
| **Retrieval Metrics** | Hit@K, MRR, NDCG cho từng domain |
| **Generation Metrics** | Faithfulness, Relevance, Completeness (LLM judge) |
| **A/B Report** | Số liệu chứng minh giá trị từng cải tiến |

---

## Tổng kết Timeline

| Phase | Nội dung | Thời lượng ước tính | Ưu tiên |
|-------|---------|---------------------|---------| 
| Phase 1 | Embedding + Hybrid Retrieval | 3–4 tuần | 🔴 Cao nhất |
| Phase 2 | Reranking + Query Router | 2–3 tuần | 🔴 Cao |
| Phase 3 | Chat Model + Self Eval | 2–3 tuần | 🔴 Cao |
| Phase 4 | Tavily + MongoDB | 2–3 tuần | 🟡 Trung bình |
| Phase 5 | FastAPI + Integration | 2–3 tuần | 🟡 Trung bình |
| Phase 6 | Evaluation + Optimization | 2–3 tuần | 🟢 Sau cùng |
| Phase 7 | CTDT Chunker & Indexing | 1–2 tuần | 🔴 Cao (data coverage) |
| Phase 8 | Collection-aware Routing | 3–5 ngày | 🔴 Cao (precision) |
| Phase 9 | Parent-Child Retrieval | 3–5 ngày | 🔴 Cao (context quality) |
| Phase 10 | Query Decomposition | 1–2 tuần | 🟡 Trung bình |
| Phase 11 | Evaluation Framework | 1–2 tuần | 🟡 Trung bình |

---

## Luồng xử lý tổng thể

### Trường hợp 1 — Chit-chat

```
User → QueryRouter → "chitchat"
  → ChatModel (OpenAI)
  → Final Answer
  → Lưu MongoDB
```

### Trường hợp 2 — Query cần RAG

```
User → QueryRouter → "rag"
  → QueryReflector (rewrite + add context)
  → EnsembleEmbedder (BGE-M3 + E5)
  → HybridSearch (Qdrant + Elasticsearch)
  → BGEReranker → Top 5 Docs
  → ChatModel (generate answer)
  → SelfEvaluator (check quality)
    ├── OK → Final Answer → Lưu MongoDB
    └── FAIL → TavilySearch → ChatModel → Final Answer → Lưu MongoDB
```
