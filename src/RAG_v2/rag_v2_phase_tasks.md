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

- [ ] **4.1 Tavily Search Tool**
  - [ ] Implement `TavilySearchTool` trong `tools/tavily_search.py`
    - [ ] `search(query)` → web search results
    - [ ] Parse và format kết quả thành context cho LLM
    - [ ] Rate limiting và error handling
  - [ ] Tích hợp vào self-eval fallback pipeline:
    - Self-eval FAIL → Tavily search → Chat Model → Final answer

- [ ] **4.2 MongoDB Memory Layer**
  - [ ] Setup MongoDB (Docker hoặc MongoDB Atlas)
  - [ ] Implement `MongoClient` trong `memory/mongo_client.py`
    - [ ] Connection pooling, retry logic
  - [ ] Implement `ChatHistoryStore` trong `memory/chat_history.py`
    - [ ] `save_message(session_id, role, content)` — lưu tin nhắn
    - [ ] `get_history(session_id, limit)` — lấy N tin gần nhất
    - [ ] `clear_history(session_id)` — xóa lịch sử
  - [ ] Implement `ConversationState` trong `memory/conversation.py`
    - [ ] Lưu final answer + metadata (sources, scores)
    - [ ] Update conversation state (active/closed)
    - [ ] Track session metadata (created_at, last_active)

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

- [ ] **5.1 Pipeline Orchestration**
  - [ ] Implement `RAGPipeline` trong `pipeline/rag_pipeline.py`
    - [ ] Kết nối: Router → Reflection → Embedding → Hybrid Search → Rerank → Chat Model → Self Eval
    - [ ] `process(user_message, session_id)` — entry point
  - [ ] Implement flows trong `pipeline/flows.py`
    - [ ] `chitchat_flow()`: Router → Chat Model → Save MongoDB
    - [ ] `rag_flow()`: Router → Reflection → Embed → Search → Rerank → Top 5 → Chat Model → Self Eval → (Tavily fallback) → Save MongoDB

- [ ] **5.2 FastAPI Backend**
  - [ ] Implement FastAPI app trong `api/main.py`
    - [ ] CORS, middleware, error handling
  - [ ] Implement routes:
    - [ ] `POST /chat` — SSE streaming response trong `api/routes/chat.py`
    - [ ] `GET /health` — health check trong `api/routes/health.py`
  - [ ] Pydantic schemas trong `api/schemas.py`
    - [ ] `ChatRequest`, `ChatResponse`, `HealthResponse`
  - [ ] Singleton pattern cho models (tránh load lại)

- [ ] **5.3 Configuration**
  - [ ] Implement `Settings` trong `config/settings.py`
    - [ ] Dùng Pydantic BaseSettings + `.env` file
    - [ ] Config cho: OpenAI, Qdrant, Elasticsearch, MongoDB, Tavily, Models
  - [ ] Tạo `.env.example` với tất cả biến môi trường

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

## Tổng kết Timeline

| Phase | Nội dung | Thời lượng ước tính | Ưu tiên |
|-------|---------|---------------------|---------| 
| Phase 1 | Embedding + Hybrid Retrieval | 3–4 tuần | 🔴 Cao nhất |
| Phase 2 | Reranking + Query Router | 2–3 tuần | 🔴 Cao |
| Phase 3 | Chat Model + Self Eval | 2–3 tuần | 🔴 Cao |
| Phase 4 | Tavily + MongoDB | 2–3 tuần | 🟡 Trung bình |
| Phase 5 | FastAPI + Integration | 2–3 tuần | 🟡 Trung bình |
| Phase 6 | Evaluation + Optimization | 2–3 tuần | 🟢 Sau cùng |

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
