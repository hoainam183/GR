# RAG v2 - Cấu hình đang chạy thật trong Pipeline

> Bản cập nhật: 07/07/2026.
>
> Tài liệu này mô tả config đang có hiệu lực trong source hiện tại, đối chiếu `config.settings.Settings()`, `src/RAG_v2/.env`, Mongo `system_config.llm_config`, và nơi các giá trị được tiêu thụ trong pipeline.

---

## 0. Thứ tự ưu tiên config

Giá trị runtime được quyết định theo thứ tự sau, tầng sau ghi đè tầng trước:

```text
Default trong code (config/settings.py)
  -> process environment variables / src/RAG_v2/.env
  -> Mongo system_config.llm_config khi app startup hoặc admin hot-swap
```

1. `config/settings.py`: class `Settings(BaseSettings)` chứa default cứng. `model_config.extra="ignore"` nên env key lạ bị bỏ qua âm thầm.
2. `src/RAG_v2/.env`: nguồn chính cho môi trường local. Nếu một key xuất hiện nhiều lần, dòng sau thắng theo cơ chế dotenv/pydantic-settings.
3. Process environment variables: có thể ghi đè `.env` khi process được start với biến môi trường ngoài.
4. Mongo `system_config.llm_config`: chỉ ghi đè nhóm LLM/admin key registry. Field persistable hiện tại: `llm_provider`, `chat_model`, `chat_temperature`, `chat_max_tokens`, `agent_model`, `agent_synthesis_provider`, `agent_synthesis_model`, `reflection_model`, `reflection_provider`, `llm_clean_provider`, `llm_clean_model`. Ngoài ra active API keys cho `deepseek`, `google`, `tavily` cũng được merge vào `Settings`.

Ghi chú quan trọng: `_settings_to_cfg` trong `pipeline/rag_runtime.py` không copy `fusion_mode`, `fusion_rrf_k`, `vector_bge_weight`, `vector_e5_weight`. Các giá trị này được nạp khi dựng retriever qua `retrieval.create_retriever()`.

---

## 1. Giá trị live hiện tại

### 1.1. Provider selectors

| Config | Giá trị hiệu lực | Nguồn |
|---|---:|---|
| `llm_provider` | `gemini` | `.env`, Mongo cũng đang set `gemini` |
| `embedding_provider` | `ensemble` | `.env` |
| `reranker_provider` | `bge` | `.env` |

`embedding_provider=ensemble` nghĩa là retrieval load cả BGE-M3 và E5. Không còn dòng ghi đè `EMBEDDING_PROVIDER=bge_m3` trong `.env` hiện tại.

### 1.2. Retrieval / hybrid search

| Config | Giá trị live | Default code | Ghi chú |
|---|---:|---:|---|
| `top_k` | 7 | 7 | số docs cuối sau rerank |
| `vector_top_k` | 20 | 50 | vector candidates mỗi collection |
| `keyword_top_k` | 20 | 50 | keyword candidates mỗi collection |
| `vector_pool_k` | 15 | 40 | vector pool toàn cục |
| `keyword_pool_k` | 15 | 40 | keyword pool toàn cục |
| `raw_candidate_multiplier` | 4.0 | 4.0 | nhân với `top_k` để ra pool rerank |
| `raw_candidate_min` | 20 | 20 | sàn pool rerank |
| `vector_weight` | 0.8 | 0.8 | chỉ có tác dụng khi `fusion_mode="linear"` |
| `keyword_weight` | 0.2 | 0.2 | chỉ có tác dụng khi `fusion_mode="linear"` |

Với query thường: `raw_candidate_k = max(round(7 * 4.0), 20) = 28`.

### 1.3. Fusion

| Config | Giá trị live | Nguồn |
|---|---:|---|
| `fusion_mode` | `rrf` | default `settings.py` |
| `fusion_rrf_k` | 10 | default `settings.py`, nạp vào searcher |
| `vector_bge_weight` | 0.5 | default `settings.py`, dùng trong Qdrant dual-vector fusion |
| `vector_e5_weight` | 0.5 | default `settings.py`, dùng trong Qdrant dual-vector fusion |

RRF formula: `rrf_score(rank, k) = 1 / (k + rank)`, với `k=10`.

Qdrant dual-vector fusion vẫn dùng `vector_bge_weight=0.5` và `vector_e5_weight=0.5` trước khi result đi vào global vector pool.

### 1.4. Reranker

| Config | Giá trị live | Default code | Ghi chú |
|---|---:|---:|---|
| `reranker_model` | `BAAI/bge-reranker-v2-m3` | cùng giá trị | local BGE cross-encoder |
| `reranker_top_k` | 7 | 7 | bị hot path shadow bởi `top_k_value` |
| `reranker_score_threshold` | 0.0 | 0.0 | `.env` đang set `-0.0`, tương đương `0.0` |
| `reranker_table_score_threshold` | -1.0 | -1.0 | `.env` hiện không override |
| `reranker_min_top_k` | 3 | 3 | `.env` hiện không override |

Trong `pipeline/flows/coordinators.py`, reranker được gọi với `top_k=top_k_value`, nên giá trị quyết định số docs cuối là `top_k` đã resolve, không phải `reranker_top_k`.

### 1.5. Embedding models

| Model | Định danh | Dim | Loader |
|---|---|---:|---|
| BGE-M3 | `BAAI/bge-m3` | 1024 | `FlagEmbedding.BGEM3FlagModel` |
| E5 multilingual | `intfloat/multilingual-e5-large` | 1024 | `sentence_transformers.SentenceTransformer` |

Qdrant collections dùng 2 named vectors: `bge_m3` và `e5`, đều cosine 1024 chiều.

Vì `embedding_provider=ensemble`, `RetrievalService.from_settings()` load E5 thật. `DummyE5` chỉ được dùng khi `embedding_provider != "ensemble"`.

### 1.6. LLM layers

Các giá trị dưới đây là effective sau khi merge Mongo `system_config.llm_config` local:

| Layer | Provider | Model | Temp | Max tokens | Ghi chú |
|---|---|---|---:|---:|---|
| Chat answer RAG | gemini | `gemini-3.1-flash-lite` | 0.2 | 2048 | `chat_temperature` bị Mongo override từ `.env` 0.3 xuống 0.2 |
| Reflection | gemini | `gemini-3.1-flash-lite` | 0.0 | 512 | model/provider từ `.env` và Mongo cùng là Gemini |
| HyDE | gemini | `gemini-3.1-flash-lite` | 0.2 | 2048 | dùng lại chat LLM |
| Agent planning | gemini | `gemini-3.1-flash-lite` | 0.2 | 2000 | dùng `_synthesis_llm`, không gọi LM Studio trên path hiện tại |
| Agent synthesis | gemini | `gemini-3.1-flash-lite` | 0.2 | 2000 | từ `AGENT_SYNTHESIS_*` |

Mongo `llm_config` hiện còn set `agent_model=gemini-3.1-flash-lite`. Tuy vậy agent planner/synthesis đang dùng `_synthesis_llm` được dựng từ `agent_synthesis_provider/model`, nên `agent_model` chủ yếu là field cấu hình/log/fallback, không phải LLM được gọi trên live path hiện tại.

### 1.7. Router & complexity

| Config | Giá trị live | Nguồn |
|---|---:|---|
| `router_mode` | `classifier` | `.env` |
| `domain_routing_enabled` | `True` | `.env` |
| `domain_confidence_threshold` | 0.65 | `.env` |
| `collections` | `["stsv", "quydinh", "kehoach", "ctdt"]` | default `settings.py` |
| `find_all` | `False` | default `settings.py` |

### 1.8. HyDE fallback

| Config | Giá trị live | Nguồn |
|---|---:|---|
| `hyde_enabled` | `True` | `.env` / default cùng giá trị |
| `hyde_min_results` | 3 | `.env` / default cùng giá trị |
| `hyde_confidence_threshold` | 0.3 | `.env` / default cùng giá trị |

`retrieval/config.py` có giá trị mirror cũ cho HyDE, nhưng hot path lấy từ `Settings` qua `pipeline/rag_runtime.py`.

### 1.9. Self-eval & Tavily web fallback

| Config | Giá trị live | Default code | Ghi chú |
|---|---:|---:|---|
| `self_eval_enabled` | `True` | `False` | `.env` override |
| `self_eval_min_top_score` | 100.0 | 100.0 | giữ rất cao để không skip self-eval theo raw logit |
| `tavily_fallback_enabled` | `True` | `False` | `.env` override |
| `tavily_search_depth` | `basic` | `basic` | `.env` set cùng default |
| `tavily_max_results` | 15 | 7 | `.env` override |
| `tavily_web_result_count` | 5 | 5 | số web results giữ lại sau filter |
| `web_fallback_on_dynamic` | `False` | `False` | hiện không bật pre-fetch theo dynamic query |
| `web_fallback_on_no_info` | `False` | `False` | hiện không bật trigger riêng theo no-info |
| `web_fallback_dynamic_collections` | `["kehoach"]` | `["kehoach"]` | collection được xem là dynamic |

### 1.10. Context / char budget

| Config | Giá trị live |
|---|---:|
| `context_doc_char_limit` | 2000 |
| `context_total_char_budget` | 12000 |
| `context_list_total_char_budget` | 24000 |
| `context_total_char_budget_with_expansion` | 16000 |
| `parent_context_enabled` | `True` |
| `parent_max_chars` | 1500 |
| `parent_max_chars_agent` | 500 |
| `sibling_expansion_enabled` | `False` |

### 1.11. Hạ tầng / infra

| Config | Giá trị live | Nguồn |
|---|---|---|
| Qdrant | `localhost:6333` | `.env` |
| Elasticsearch | `localhost:9200` | `.env` |
| MongoDB | `mongodb://localhost:27017`, db `rag_chatbot` | `.env` |
| Redis | enabled, `redis://localhost:6379/0`, max 20 connections | default `settings.py`; `.env` hiện không override |
| Rate limit | enabled, 20 rpm / 200 rpd | default `settings.py`; `.env` hiện không override |
| API server | `0.0.0.0:8000` | `.env` |
| Agent | enabled, max_iterations 3 | `.env` |

---

## 2. Retrieval hot path

Đường đi chính: `RAGPipeline.query()` -> `rag_flow()` -> `pipeline/flows/coordinators.py`.

`retrieval/service.py:_search_single()` là entry point khác, dùng cho agent tool adapter và `/retrieval/search`, không phải hot path chính của `rag_flow`.

| Stage | Xử lý | Số liệu live |
|---|---|---|
| 1 | Resolve `top_k` | 7; list query thì nhân đôi, cap 12 |
| 2 | Resolve `raw_candidate_k` | `max(round(7 * 4.0), 20) = 28` |
| 3 | Embed query | BGE-M3 1 lần + E5 1 lần |
| 4 | Search mỗi collection | vector top 20, keyword top 20; exact-policy/table query bump keyword lên 120 |
| 5 | Qdrant dual-vector | fetch `min(20 * 2, 100) = 40` ứng viên mỗi vector, fuse `0.5 * BGE + 0.5 * E5`, trả top 20 |
| 6 | Global pool | vector pool 15, keyword pool 15; exact-policy keyword pool bump lên 80 |
| 7 | RRF fusion | RRF k=10, vector/keyword weight ép 1.0/1.0, trả tối đa 28 candidates |
| 8 | Dedup + sibling | sibling expansion đang tắt |
| 9 | Rerank | chấm khoảng 28 cặp query-doc; `top_k=7`, threshold thường 0.0, table threshold -1.0, min_top_k 3 |
| 10 | Post-rerank | fallback khi rỗng/điểm âm, HyDE pass 2 nếu ít/low-confidence, validity filter, reference resolver, parent context |
| 11 | Context vào LLM | tối đa 7 docs trước các bước expansion/filter sau rerank |

Số inference mặc định cho một query thường:

- BGE-M3 embed query: 1 lần.
- E5 embed query: 1 lần.
- BGE reranker cross-encoder: khoảng 28 cặp.
- Gemini: reflection 1 lần, answer 1 lần; có thể thêm Tier-2 complexity judge hoặc HyDE nếu trigger.

---

## 3. Routing `/chat`: Agent hay RAG?

Handler chính: `api/routes/chat.py`.

| Request mode | Luồng |
|---|---|
| `mode=rag` | ép `pipeline.query()` |
| `mode=agent` | ép `pipeline.query_agent(require_agent=True)` |
| `mode=auto` hoặc không truyền | `pipeline.query_v3()` |

`agent_enabled=true` không có nghĩa mọi request đều qua agent. `query_v3()` chạy complexity router trước:

- `chitchat` -> `_handle_chitchat()`, không retrieval/LLM answer.
- `simple` -> RAG cổ điển `self.query()`.
- `complex` -> `self.query_agent(require_agent=False)`.
- Nếu agent không tồn tại, route vẫn fallback về RAG.

SSE `/chat/stream` mirror logic này.

---

## 4. Những điểm cần nhớ

1. `embedding_provider=ensemble`, nên E5 đang được dùng thật. Muốn chạy BGE-only thì đổi `EMBEDDING_PROVIDER=bge_m3`.
2. RRF bỏ qua `vector_weight=0.8` và `keyword_weight=0.2`; hai weight này chỉ có ý nghĩa với `fusion_mode="linear"`.
3. Agent planner và agent synthesis đang dùng Gemini qua `_synthesis_llm`. LM Studio/Qwen không phải model được gọi trên live path hiện tại.
4. `reranker_top_k` bị shadow bởi `top_k_value` trong hot path. Hiện hai giá trị cùng là 7 nên không gây lệch hành vi.
5. `reranker_table_score_threshold=-1.0`, không phải 0.0.
6. `web_fallback_on_dynamic` và `web_fallback_on_no_info` đang tắt. Tavily vẫn có thể được dùng khi các trigger khác trong flow kích hoạt và `tavily_fallback_enabled=True`.
7. Mongo `system_config.llm_config` có thể làm bảng LLM khác `.env`. Trạng thái local hiện tại đang override `chat_temperature=0.2`, `agent_model=gemini-3.1-flash-lite`, và active API keys.

---

## 5. Tham chiếu file nguồn

| Chủ đề | File |
|---|---|
| Default config | `config/settings.py` |
| Env local | `src/RAG_v2/.env` |
| Mongo LLM override/API key registry | `models/system_config.py` |
| Startup merge Mongo config | `api/main.py` |
| Settings -> cfg dict | `pipeline/rag_runtime.py` |
| Dựng retriever/searcher | `retrieval/__init__.py` |
| Hot path retrieval | `pipeline/flows/coordinators.py`, `pipeline/flows/retrieval_helpers.py` |
| Multi-collection search + RRF | `retrieval/multi_collection_search.py` |
| Qdrant dual-vector | `retrieval/qdrant_store.py` |
| Reranker BGE | `reranking/bge_reranker.py` |
| Embedding BGE/E5 | `embedding/bge_m3.py`, `embedding/e5_multilingual.py`, `retrieval/service.py` |
| LLM factory | `llm/__init__.py`, `llm/gemini.py` |
| HyDE | `retrieval/hyde.py`, `pipeline/flows/hyde.py` |
| Agent ReAct | `agent/react_agent.py` |
| Complexity routing | `pipeline/rag_pipeline.py`, `query/complexity_router.py` |
| Chat endpoints | `api/routes/chat.py` |
