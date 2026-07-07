# RAG v2 — Cấu hình đang chạy thật trong Pipeline

> Tài liệu này tổng hợp **các giá trị config đang thực sự chạy** (live), đối chiếu source code + file `.env` thật, không phải default trong code.
> Xác minh bằng cách nạp trực tiếp `config.settings.Settings()` với `.env` hiện tại (07/2026) + trace consumption trong pipeline.

---

## 0. Thứ tự ưu tiên config (precedence)

Giá trị "đang chạy" được quyết định theo thứ tự (sau ghi đè trước):

```
Default trong code (config/settings.py)
   └─▶ ghi đè bởi  src/RAG_v2/.env
          └─▶ ghi đè (chỉ nhóm LLM) bởi  Mongo system_config "llm_config"
```

1. **`config/settings.py`** — class `Settings(BaseSettings)`: default cứng cho mọi knob. `model_config` đặt `extra="ignore"` (`config/settings.py:395-399`) → biến env lạ bị **bỏ qua âm thầm**, không lỗi.
2. **`src/RAG_v2/.env`** — ghi đè default (case-insensitive). Đây là nguồn chính của giá trị live. ⚠️ Nếu một key xuất hiện **2 lần** thì **dòng sau thắng** (python-dotenv/pydantic-settings).
3. **Mongo `system_config` (`llm_config`)** — `models/system_config.py:28-42`: admin có thể sửa runtime **chỉ các field LLM** (`llm_provider`, `chat_model`, `chat_temperature`, `chat_max_tokens`, `agent_model`, `agent_synthesis_provider`, `agent_synthesis_model`, `reflection_model`, `reflection_provider`, `llm_clean_provider`, `llm_clean_model`) và hot-swap qua `prepare_llm_config_reload`. Nếu DB có bản ghi, nó ghi đè `.env` cho các field này.

> `_settings_to_cfg` (`pipeline/rag_runtime.py:21-76`) chuyển `Settings` thành cfg dict cho các flow. **Lưu ý**: nó *không* copy `fusion_mode`, `fusion_rrf_k`, `vector_bge_weight`, `vector_e5_weight` — các giá trị này được nạp lúc **dựng searcher** (`retrieval/__init__.py: create_retriever`), không qua cfg dict.

---

## 1. Bảng tổng hợp giá trị LIVE (đã xác nhận bằng `Settings()`)

### 1.1. Provider selectors

| Config | Giá trị live | Default code | Nơi config |
|---|---|---|---|
| `llm_provider` | **gemini** | `deepseek` | `.env:10,126` · `settings.py:65` |
| `embedding_provider` | **bge_m3** ⚠️ | `ensemble` | `.env:11,127` (dòng 127 thắng) · `settings.py:68` |
| `reranker_provider` | **bge** | `bge` | `.env:12,128` · `settings.py:69` |

### 1.2. Retrieval / Hybrid search

| Config | Giá trị live | Default code | Ý nghĩa | Nơi config |
|---|---|---|---|---|
| `top_k` | **7** | 7 | Số docs cuối cùng sau rerank | `.env:73` · `settings.py:143` |
| `vector_top_k` | **20** | 50 | Vector search limit / collection | `.env:74` · `settings.py:144` |
| `keyword_top_k` | **20** | 50 | Keyword (ES) limit / collection | `.env:75` · `settings.py:145` |
| `vector_pool_k` | **15** | 40 | Vector pool toàn cục sau merge | `.env:76` · `settings.py:146` |
| `keyword_pool_k` | **15** | 40 | Keyword pool toàn cục sau merge | `.env:77` · `settings.py:147` |
| `raw_candidate_multiplier` | **4.0** | 4.0 | Nhân top_k để ra pool ứng viên | `settings.py:148` |
| `raw_candidate_min` | **20** | 20 | Sàn số ứng viên | `settings.py:149` |
| `vector_weight` | **0.8** | 0.8 | ⚠️ Chỉ dùng ở fusion `linear`; RRF bỏ qua | `.env:78` · `settings.py:150` |
| `keyword_weight` | **0.2** | 0.2 | ⚠️ Chỉ dùng ở fusion `linear`; RRF bỏ qua | `.env:79` · `settings.py:151` |

### 1.3. Fusion

| Config | Giá trị live | Nơi config |
|---|---|---|
| `fusion_mode` | **rrf** | `settings.py:154` (không có trong `.env` → default) |
| `fusion_rrf_k` | **10** | `settings.py:155` → nạp vào searcher qua `create_retriever` (`retrieval/__init__.py`) |
| `vector_bge_weight` | **0.5** | `settings.py:156` (trọng số hợp nhất 2 named vector trong Qdrant) |
| `vector_e5_weight` | **0.5** | `settings.py:157` |

**Công thức RRF** (`retrieval/hybrid_search.py:18-20`): `rrf_score(rank, k) = 1.0 / (k + rank)` với `k = 10`.

Trong `_score_fusion_rrf` (`retrieval/multi_collection_search.py:1012-1079`):
```
vector_rrf  = vector_weight  * rrf_score(rank+1, 10)     # vector_weight bị ép = 1.0
keyword_rrf = keyword_weight * rrf_score(rank+1, 10)     # keyword_weight bị ép = 1.0
raw = vector_rrf + keyword_rrf + kehoach_recency_bonus(entry) * (1/(10+1))
score = raw * (10+1)                                     # chuẩn hoá về ~[0,1]
```
- ⚠️ **Ở chế độ RRF, `vector_weight`/`keyword_weight` (0.8/0.2) bị ép thành 1.0/1.0** (`multi_collection_search.py:516-524`). 0.8/0.2 chỉ có tác dụng khi `fusion_mode="linear"`.
- **Recency boost**: `kehoach_recency_bonus` (tối đa +0.05, giảm dần theo ngày) chỉ áp cho collection `kehoach`, scale bằng `1/(rrf_k+1)` (`multi_collection_search.py:1053-1064`).

### 1.4. Reranker

| Config | Giá trị live | Default code | Nơi config |
|---|---|---|---|
| `reranker_model` | **BAAI/bge-reranker-v2-m3** (local) | như live | `.env:82` · `settings.py:166` |
| `reranker_top_k` | **7** | 7 | `.env:83` · `settings.py:167` — ⚠️ bị *shadow* bởi `top_k` (xem §2 Stage 8) |
| `reranker_score_threshold` | **0.0** | 0.0 | `.env:84` · `settings.py:173` |
| `reranker_table_score_threshold` | **0.0** ⚠️ | -1.0 | `.env:85` · `settings.py:179` (default -1.0, `.env` ghi đè về 0.0) |
| `reranker_min_top_k` | **5** | 3 | `.env:86` · `settings.py:183` |

### 1.5. Embedding models (đều chạy LOCAL)

| Model | Định danh | Dim | Loader | Nơi config |
|---|---|---|---|---|
| BGE-M3 (dense+sparse) | `BAAI/bge-m3` | 1024 | `FlagEmbedding.BGEM3FlagModel` | `embedding/bge_m3.py:77,104` |
| E5 multilingual | `intfloat/multilingual-e5-large` | 1024 | `sentence_transformers.SentenceTransformer` | `embedding/e5_multilingual.py:76,98` |

- Qdrant có **2 named vector**: `bge_m3` (1024, cosine) và `e5` (1024, cosine) — `retrieval/qdrant_store.py:15-18`.
- Device tự resolve CUDA → MPS → CPU (`bge_m3.py:56-65`, `e5_multilingual.py:55-64`). Prod = MacBook M4 Pro (MPS).
- ⚠️ **E5 đang bị vô hiệu hoá** (xem §3, mục ⚠️): vì `embedding_provider=bge_m3` (không phải `ensemble`), `RetrievalService.from_settings` thay E5 bằng `DummyE5` trả vector toàn 0 (`retrieval/service.py:158-166`).

### 1.6. LLM các layer

| Layer | Provider | Model | Temp | Max tokens | Nơi config |
|---|---|---|---|---|---|
| **Chat answer (RAG trực tiếp)** | gemini | `gemini-3.1-flash-lite` | 0.3 | 2048 | `.env:47-49` · `settings.py:136-140` |
| **Reflection (query rewrite)** | gemini | `gemini-3.1-flash-lite` | 0.0 | 512 | `.env:54-57` · `settings.py:230-237` |
| **HyDE (sinh giả thuyết)** | gemini | `gemini-3.1-flash-lite` | 0.3 | 2048 | *dùng lại chat model* — `pipeline/flows/hyde.py:108` |
| **Agent tool-calling / planning** | gemini | `gemini-3.1-flash-lite` | 0.2 | 2000 | ⚠️ dùng LLM synthesis, KHÔNG dùng qwen — `agent/react_agent.py:314-319,135-175` |
| **Agent synthesis (câu trả lời cuối)** | gemini | `gemini-3.1-flash-lite` | 0.2 | 2000 | `.env:40-43` · `settings.py:101-108` |
| ~~Agent model (khai báo)~~ | ~~lm_studio~~ | `qwen/qwen3-8b` | 0.0 | 1200 | `.env:34-36` — ⚠️ **không được gọi thật** trên live path (chỉ để log) |

**Factory `create_llm`** (`llm/__init__.py:31-68`): đọc `settings.llm_provider` → nạp module (`deepseek`/`gemini`/`lm_studio`), dựng LLM với `model=chat_model, temperature=chat_temperature, max_tokens=chat_max_tokens`. API key: `llm_api_key` nếu có, else `deepseek_api_key` (deepseek) hoặc `google_api_key` (còn lại) — `llm/__init__.py:54-59`. `GeminiLLM` fallback `os.environ["GOOGLE_API_KEY"]` (`llm/gemini.py:59`).

### 1.7. Router & complexity

| Config | Giá trị live | Nơi config |
|---|---|---|
| `router_mode` | **classifier** | `.env:93` · `settings.py:186` |
| `domain_routing_enabled` | **True** | `.env:96` · `settings.py:240` |
| `domain_confidence_threshold` | **0.65** | `.env:97` · `settings.py:241` |
| `collections` | `["stsv","quydinh","kehoach","ctdt"]` | `settings.py:127` |
| `find_all` | **False** (route tới subset collection) | `settings.py:132` |

### 1.8. HyDE fallback

| Config | Giá trị live | Nơi config |
|---|---|---|
| `hyde_enabled` | **True** | `settings.py:283` |
| `hyde_min_results` | **3** | `settings.py:284` (kích hoạt khi số docs sau rerank < 3) |
| `hyde_confidence_threshold` | **0.3** | `settings.py:285` (hoặc reranker mean < 0.3) |

> ⚠️ `retrieval/config.py` có `HYDE_ENABLED=False` nhưng đó là module không được pipeline live dùng; giá trị thực lấy từ `Settings.hyde_enabled=True`.

### 1.9. Self-eval & Web fallback (Tavily)

| Config | Giá trị live | Default | Nơi config |
|---|---|---|---|
| `self_eval_enabled` | **True** | False | `.env:101` · `settings.py:189` |
| `self_eval_min_top_score` | **100.0** | 100.0 | `.env:102` · `settings.py:194` |
| `tavily_fallback_enabled` | **True** | False | `.env:103` · `settings.py:199` |
| `tavily_search_depth` | **basic** | basic | `settings.py:200` |
| `tavily_max_results` | **7** | 7 | `.env:104` · `settings.py:203` |
| `tavily_web_result_count` | **5** | 5 | `settings.py:209` (giữ lại sau filter) |
| `web_fallback_on_dynamic` | **True** | False | `.env:105` · `settings.py:217` |
| `web_fallback_on_no_info` | **True** | False | `.env:106` · `settings.py:218` |
| `web_fallback_dynamic_collections` | `["kehoach"]` | | `settings.py:212` |

### 1.10. Context / char budget

| Config | Giá trị live | Nơi config |
|---|---|---|
| `context_doc_char_limit` | 2000 | `settings.py:159` |
| `context_total_char_budget` | 12000 | `settings.py:160` |
| `context_list_total_char_budget` | 24000 | `settings.py:161` |
| `context_total_char_budget_with_expansion` | 16000 | `settings.py:292` |
| `parent_context_enabled` | **True** | `settings.py:278` |
| `parent_max_chars` / `parent_max_chars_agent` | 1500 / 500 | `settings.py:288-291` |
| `sibling_expansion_enabled` | **False** | `settings.py:277` |

### 1.11. Hạ tầng / infra

| Config | Giá trị live | Nơi config |
|---|---|---|
| Qdrant | `localhost:6333` | `.env:60-61` · `settings.py:114-115` |
| Elasticsearch | `localhost:9200` | `.env:64-65` · `settings.py:118-119` |
| MongoDB | `mongodb://localhost:27017` / db `rag_chatbot` | `.env:68-70` · `settings.py:122-124` |
| Redis | enabled, `redis://localhost:6379/0`, max 20 conn | `.env:123` · `settings.py:253-261` |
| Rate limit | 20 rpm / 200 rpd | `.env:139-141` · `settings.py:264-267` |
| API server | `0.0.0.0:8000` | `.env:112-113` · `settings.py:392-393` |
| Agent | enabled, max_iterations 3 | `.env:32-33` · `settings.py:92-93` |

---

## 2. Kiến trúc retrieval theo từng Stage (số liệu LIVE)

Đường đi thật: `RAGPipeline.query` → `rag_flow` → `pipeline/flows/coordinators.py`.
(Lưu ý: `retrieval/service.py:_search_single` là entry point *khác*, dùng cho agent tool adapter và `/retrieval/search`, không phải hot path của `rag_flow`.)

| Stage | Xử lý | Số liệu LIVE | Nơi |
|---|---|---|---|
| 1 | Resolve `top_k` | **7** (query dạng list → gấp đôi, cap **12**) | `coordinators.py:476` · `retrieval_helpers.py:26-48` |
| 1 | Resolve pool ứng viên `raw_candidate_k` | `max(round(7×4.0), 20)` = **28** (×2 nếu low-conf expand, mặc định tắt) | `coordinators.py:481` · `retrieval_helpers.py:85-108` |
| 2 | Gọi searcher | vector_top_k=20, keyword_top_k=20, vector_pool_k=15, keyword_pool_k=15, fusion_mode=rrf | `coordinators.py:550-565` |
| 3 | Search / collection | Vector: `qdrant.search(top_k=20, bge_w=0.5, e5_w=0.5)`; Keyword: `es.keyword_search(top_k=20)` — query exact-policy/table bump keyword lên `max(20,120)=120` | `multi_collection_search.py:322-327,395-440` |
| 3a | Qdrant hợp nhất 2 vector | Fetch `min(20×2,100)=40` ứng viên **mỗi model** (BGE, E5); max-norm rồi `0.5·norm_bge + 0.5·norm_e5`; trả top 20 | `qdrant_store.py:156,193-257` |
| 4 | Gom pool toàn cục | Nối mọi collection, dedup theo id → cắt `vector_pool_k=15`; keyword → `keyword_pool_k=15` (exact-policy → `max(15,80)=80`) | `multi_collection_search.py:500-513` |
| 5 | Fusion RRF (k=10) | weights ép 1.0/1.0 (bỏ 0.8/0.2), + recency kehoach; trả `deduped[:raw_candidate_k]` = **28** | `multi_collection_search.py:515-534,1012-1079` |
| 6 | Dedup (+sibling nếu bật) | 28 docs (sibling_expansion tắt → không thêm) | `coordinators.py:604-607,701-714` |
| 7 | **Docs đưa VÀO reranker** | = `raw_candidate_k` = **28** (list query đến 48; +≤6 sibling nếu bật) | `coordinators.py:723-728` |
| 8 | Gọi rerank | `reranker.rerank(documents=28, top_k=top_k_value=7, score_threshold=0.0, table_score_threshold=0.0, min_top_k=min(5,7)=5)` — ⚠️ `top_k` (7) ghi đè `reranker_top_k` | `coordinators.py:722-728` · `retrieval_helpers.py:119-134` |
| 9 | Lọc ngưỡng trong reranker | Cross-encoder chấm 28 cặp; lọc theo threshold (bảng dùng table_threshold=0.0); `filtered[:7]`; nếu <5 docs sống thì bù lại cho đủ 5 | `bge_reranker.py:159,179-208` |
| 10 | Post-rerank | Fallback nếu rỗng/điểm âm; HyDE pass 2 nếu <3 docs hoặc mean<0.3; score-cliff; parent-context expansion | `coordinators.py:744-821` · `rerank_scoring.py:32-86` |
| — | **Docs cuối cùng đưa vào LLM** | **≤ 7** | `bge_reranker.py:191` |

**Số model inference một truy vấn (mặc định):**
- BGE-M3 embed query: 1 lần · (E5 embed: bị vô hiệu, trả zeros)
- Reranker BGE cross-encoder: chấm ~28 cặp
- Gemini: reflection (1) + [Tier-2 judge nếu ≥2 collection] + answer/synthesis (1) + [HyDE nếu trigger]

---

## 3. Routing `/chat`: Agent hay RAG?

Handler `api/routes/chat.py:97-213`. `mode` mặc định (`auto`) → `pipeline.query_v3`. `mode=agent` ép `query_agent`; `mode=rag` ép `query`.

**`agent_enabled=true` KHÔNG có nghĩa mọi request đều qua agent.** `query_v3` chạy complexity router 3 tầng trước:
- `_decide_complexity` (`rag_pipeline.py:1044-1101`): Tier-0 regex `ComplexityRouter.route` (`chitchat`/`simple`/`complex`/`unknown`) → Tier-1 ML multi-label → Tier-2 LLM judge (chỉ khi ≥2 collection active).
- Điều hướng (`rag_pipeline.py:839-885`):
  - `chitchat` → `_handle_chitchat` (không LLM/retrieval)
  - **`simple` → RAG cổ điển `self.query`** (dùng `self._chat` = Gemini)
  - `complex` → `self.query_agent(require_agent=False)` (LangGraph ReAct)
- Guard `:852`: `if route == "simple" or runtime.agent is None` → agent tắt thì luôn RAG. Chỉ query `complex` mới vào agent.
- SSE `/chat/stream` (`chat.py:413` → `query_stream`) mirror logic này (`rag_pipeline.py:1279`).

---

## ⚠️ 4. Các điểm cần lưu ý (config lệch / dead / gây hiểu nhầm)

1. **E5 đang bị vô hiệu hoá (retrieval thực chất chỉ dùng BGE-M3).**
   `.env` đặt `EMBEDDING_PROVIDER` **2 lần**: `ensemble` (`.env:11`) rồi `bge_m3` (`.env:127`). Dòng sau thắng → `Settings.embedding_provider = "bge_m3"` (đã xác nhận). Do đó `RetrievalService.from_settings` (`retrieval/service.py:158-166`) thay E5 bằng `DummyE5` trả `[0.0]*1024`. Named vector `e5` trong Qdrant không đóng góp gì; fusion `0.5·bge + 0.5·e5` thực chất chỉ còn BGE. → **Muốn dual-vector thật: xoá dòng `EMBEDDING_PROVIDER=bge_m3` (`.env:127`) hoặc đổi thành `ensemble`.**

2. **RRF bỏ qua `vector_weight`/`keyword_weight` (0.8/0.2).** Ở `fusion_mode="rrf"` (live), hai trọng số bị ép 1.0/1.0 (`multi_collection_search.py:516-524`). 0.8/0.2 chỉ tác dụng khi đổi sang `linear` (eval-only).

3. **Qwen3-8B / LM Studio không được gọi thật.** Vì `AGENT_SYNTHESIS_PROVIDER=gemini`, cả planning và synthesis của agent đều dùng cùng một `_synthesis_llm` = Gemini (`react_agent.py:314-319`). `AGENT_MODEL=qwen/qwen3-8b` và `LM_STUDIO_URL` chỉ để log.

4. **Remote GPU (Infinity) chưa được cài đặt trong code.** `.env:132-136` đặt `EMBEDDING_ENDPOINT_URL`/`RERANKER_ENDPOINT_URL=https://YOUR-GPU-HOST:7997`, `INFINITY_API_KEY`… nhưng **không field nào tồn tại trong `Settings`** và **không code runtime nào đọc chúng** (chỉ 2 test `test_remote_embedder.py`/`test_remote_reranker.py` import module `embedding.remote_embedder`/`reranking.remote_reranker` — **các module này không tồn tại**). Do `extra="ignore"`, các biến này bị bỏ qua âm thầm và giá trị placeholder vô hại. → Embedding + reranker luôn chạy **local**.

5. **`reranker_top_k` (7) bị shadow bởi `top_k`.** `coordinators.py:726` luôn truyền `top_k=top_k_value` (=`settings.top_k`=7), ghi đè giá trị `reranker_top_k` gắn lúc dựng reranker. Trùng 7 nên không lệch hành vi, nhưng giá trị *được dùng* là `top_k`.

6. **`reranker_table_score_threshold` = 0.0 (không phải -1.0).** Default code là -1.0 (`settings.py:179`) nhưng `.env:85` ghi đè về 0.0 → chunk bảng dùng cùng ngưỡng 0.0 như chunk thường.

7. **`retrieval/config.py` không phải nguồn HyDE thật.** File đó ghi `HYDE_ENABLED=False` nhưng chỉ là bản mirror tài liệu; pipeline lấy `Settings.hyde_enabled=True`.

8. **Nhóm LLM có thể bị admin đổi runtime.** Nếu Mongo `system_config.llm_config` có bản ghi, các field ở §1.6 sẽ khác `.env`. Kiểm tra collection `system_config` doc `llm_config` để biết giá trị runtime thực.

---

## 5. Tham chiếu file nguồn

| Chủ đề | File |
|---|---|
| Định nghĩa toàn bộ default | `config/settings.py` |
| Giá trị ghi đè live | `src/RAG_v2/.env` |
| Override LLM runtime (admin) | `models/system_config.py` |
| Settings → cfg dict | `pipeline/rag_runtime.py:21-76` |
| Dựng searcher (nạp rrf_k, bge/e5 weight) | `retrieval/__init__.py: create_retriever` |
| Hot path retrieval | `pipeline/flows/coordinators.py` + `pipeline/flows/retrieval_helpers.py` |
| Multi-collection + fusion RRF | `retrieval/multi_collection_search.py` |
| Qdrant dual-vector | `retrieval/qdrant_store.py` |
| RRF formula | `retrieval/hybrid_search.py:18-20` |
| Reranker BGE (local) | `reranking/bge_reranker.py` |
| Embedder (BGE/E5/Dummy) | `retrieval/service.py:143-206` · `embedding/bge_m3.py` · `embedding/e5_multilingual.py` |
| LLM factory | `llm/__init__.py` · `llm/gemini.py` |
| Reflection | `query/reflection.py` |
| HyDE | `retrieval/hyde.py` · `pipeline/flows/hyde.py` |
| Agent ReAct | `agent/react_agent.py` |
| Complexity routing | `pipeline/rag_pipeline.py:831-885,1044-1101` · `query/complexity_router.py` |
| Chat endpoint | `api/routes/chat.py` |
</content>
</invoke>
