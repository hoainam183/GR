# RAG v2 System Flow

Source-verified: 2026-06-02 from GitNexus repo `GR`, `src/RAG_v2/ARCHITECTURE.md`, and all `src/RAG_v2/*/MODULE.md` files.

## Scope

This file describes the complete runtime and ingestion flow for `D:\GR\src\RAG_v2`.

Main collections:

- `ctdt`: curriculum, majors, courses, credits, prerequisites.
- `quydinh`: regulations, scholarships, graduation, foreign-language rules.
- `kehoach`: plans, notices, schedules, deadlines.
- `stsv`: student support handbook, forms, procedures.
- `test`: upload/dev collection.

## 1. Whole-System Runtime Flow

```mermaid
flowchart TD
  Web["React/Vite web app"] --> API["FastAPI api/main.py"]
  Mobile["Expo mobile app"] --> API
  Shared["@rag/shared clients/types"] --> Web
  Shared --> Mobile

  API --> Auth["auth + routers/auth.py"]
  API --> Schemas["schemas Pydantic contracts"]
  API --> Pipeline["pipeline/RAGPipeline singleton"]
  API --> Sessions["models/MongoLogger + cache Redis"]

  Pipeline --> Query["query routing/reflection/signals"]
  Query -->|chitchat| Chitchat["local chitchat answer"]
  Query -->|simple| RAG["classic RAG flow"]
  Query -->|complex| Agent["agent Planner-Executor"]
  Agent -->|fallback allowed| RAG

  RAG --> Retrieval["retrieval/RetrievalService"]
  Agent --> Retrieval
  Retrieval --> Embedding["embedding BGE-M3 + E5"]
  Retrieval --> Qdrant["Qdrant named vectors"]
  Retrieval --> ES["Elasticsearch BM25 + metadata filters"]
  Retrieval --> Rerank["reranking BGE cross-encoder"]
  Retrieval --> Validity["ValidityFilter + ReferenceResolver + parent context"]

  Validity --> Prompt["llm prompt/context formatting"]
  Agent --> Synthesis["agent synthesis LLM"]
  Prompt --> LLM["llm DeepSeek/Gemini/LM Studio"]
  LLM --> Quality["SelfEvaluator/Tavily fallback when enabled"]
  Quality --> Mapper["api/response_mapper.py"]
  Synthesis --> Mapper
  Mapper --> Response["ChatResponse or SSE metadata"]
  Response --> Web
  Response --> Mobile

  Pipeline --> Logs["Mongo sessions/turns/query_logs/agent_traces"]
  Pipeline --> Cache["Redis history/session/LLM cache/rate limit"]
```

## 2. FastAPI Startup Flow

```mermaid
flowchart TD
  Entrypoint["backend/main.py legacy or api/main.py"] --> App["create_app"]
  App --> Lifespan["lifespan startup"]
  Lifespan --> Env["load .env + Settings"]
  Env --> Persisted["models/system_config llm_config"]
  Persisted --> Merge["merge persisted LLM overrides"]
  Merge --> Mongo["MongoLogger + Motor indexes"]
  Merge --> Redis["RedisManager/session/history/cache/rate limit"]
  Merge --> Pipeline["build one RAGPipeline in executor"]
  Pipeline --> Retrieval["one shared RetrievalService"]
  Retrieval --> AgentInject["inject retrieval service into agent adapters"]
  Lifespan --> Warmup["optional agent LLM warmup"]
  Lifespan --> Scheduler["optional auto_crawler APScheduler"]
```

Important boundary: `RAGPipeline` owns one `RetrievalService`; agent adapters should use that same shared runtime. Current source stores it as `_retrieval_service`, while some diagnostic routes still look for `service`/`retrieval_service`.

## 3. Chat Request Flow

```mermaid
sequenceDiagram
  participant C as Web/Mobile client
  participant A as FastAPI chat route
  participant P as RAGPipeline
  participant Q as query module
  participant R as retrieval module
  participant G as agent module
  participant L as llm module
  participant M as Mongo/Redis

  C->>A: POST /chat, /chat/v3, or /chat/stream
  A->>A: validate schema, resolve optional JWT/profile/session
  A->>P: query_v3/query_stream(question, history, user_context)
  P->>Q: ComplexityRouter + signals
  alt chitchat
    P->>A: local chitchat response
  else simple RAG
    P->>Q: QueryRouter + QueryReflector
    Q->>R: domains, entities, reflected query, filters
    R->>R: BGE/E5 embed, Qdrant+ES search, fusion, rerank
    R->>P: context documents + trace
    P->>L: grounded generation
  else complex
    P->>G: ReActAgent.run Planner-Executor
    G->>R: execute retrieval plan with shared RetrievalService
    G->>L: synthesize final answer
    G->>P: AgentState + docs
  end
  P->>M: log session/turn/query trace/cache when allowed
  P->>A: result dict + metadata
  A->>C: normalized JSON or SSE events
```

## 4. Classic RAG Flow

```mermaid
flowchart TD
  Question["question + history + profile"] --> CacheRead["query-only cache when safe"]
  CacheRead --> Route["QueryRouter domain route"]
  Route --> Select["CollectionSelector target collections"]
  Select --> Reflect["QueryReflector rewrite/entities"]
  Reflect --> Filters["metadata filters: major/cohort/date/freshness"]
  Filters --> Variants["query variants/comparison subqueries"]
  Variants --> Embed["BGE + E5 query embeddings"]
  Embed --> Search["MultiCollectionSearch"]
  Search --> Retry["relaxed retry when empty"]
  Retry --> Siblings["optional sibling expansion before rerank"]
  Siblings --> Rerank["BGE reranker with fallback to raw fusion"]
  Rerank --> HyDE["HyDE fallback when recall is poor"]
  HyDE --> Validity["ValidityFilter"]
  Validity --> References["ReferenceResolver"]
  References --> Parent["parent context expansion"]
  Parent --> WebPre["optional pre-generation Tavily enrichment"]
  WebPre --> Context["context formatting + profile note"]
  Context --> Generate["LLM generate"]
  Generate --> SelfEval["optional self-eval"]
  SelfEval --> WebPost["optional Tavily regeneration"]
  WebPost --> CacheWrite["write cache only for stable local answers"]
  CacheWrite --> Result["answer + sources + trace metadata"]
```

## 5. Agent Flow

```mermaid
flowchart TD
  Complex["complex query from RAGPipeline"] --> Init["init_agent_docs ContextVar"]
  Init --> Run["ReActAgent.run"]
  Run --> Route["route_entry"]
  Route -->|comparison/multi_source| Decompose["decompose subquestions"]
  Route -->|general/missing| Planner["planner JSON retrieval plan"]
  Decompose --> Planner
  Planner --> Validate["validate plan query + collection"]
  Validate -->|invalid| Error["state.error -> pipeline fallback policy"]
  Validate -->|valid| Execute["executor"]
  Execute --> RetrievalPlan["tool_adapters.execute_retrieval_plan"]
  RetrievalPlan --> Retrieval["shared RetrievalService"]
  RetrievalPlan -->|needs_web| Tavily["TavilySearchTool"]
  Retrieval --> ToolResults["ToolResult list + agent docs"]
  Tavily --> ToolResults
  ToolResults --> Synthesize["synthesis LLM"]
  Synthesize --> State["AgentState"]
  State --> API["response mapper + Mongo agent_traces"]
```

## 6. Retrieval Flow

```mermaid
flowchart TD
  Query["reflected query + collections + entities"] --> Service["RetrievalService.search"]
  Service --> Embedders["BGE-M3 + E5"]
  Service --> Multi["MultiCollectionSearch"]
  Multi --> Signals["query/signals.py"]
  Multi --> Metadata["metadata_filters.py"]
  Metadata --> ESFilter["ES metadata fallback chain"]
  ESFilter --> IDFilter["Qdrant HasIdCondition + ES bool filter"]
  Multi --> Qdrant["Qdrant vector search per collection"]
  Multi --> ES["Elasticsearch keyword search per collection"]
  Qdrant --> Pools["global vector pool"]
  ES --> Pools2["global keyword pool"]
  Pools --> Fusion["linear/RRF fusion"]
  Pools2 --> Fusion
  Fusion --> Recency["kehoach recency bonus"]
  Recency --> Dedup["dedup by id/text"]
  Dedup --> Rerank["optional BGE reranker"]
  Rerank --> Validity["drop superseded docs when safe"]
  Validity --> Reference["same-document legal reference chunks"]
  Reference --> Parent["parent context chunks"]
  Parent --> Context["context docs for pipeline/agent"]
```

## 7. Admin Document Upload Flow

```mermaid
flowchart TD
  Admin["admin web UI"] --> UploadAPI["/admin/documents*"]
  UploadAPI --> Storage["utils/LocalStorage original PDF"]
  UploadAPI --> MongoDoc["Mongo documents status=uploaded"]
  MongoDoc --> Convert["DocumentPipeline.convert_pdf"]
  Convert --> Loader["document_loader converters"]
  Loader --> Markdown["converted Markdown"]
  Markdown --> Clean["DocumentPipeline.clean"]
  Clean --> Chunk["DocumentPipeline.chunk + chunking strategies"]
  Chunk --> Review["Mongo document_chunks selected/editable"]
  Review --> Approve["admin approve chunks"]
  Approve --> Policy["is_indexable_chunk"]
  Policy --> Embed["BGE/E5 embed_documents"]
  Embed --> Qdrant["Qdrant upsert"]
  Embed --> ES["Elasticsearch bulk index"]
  ES --> Indexed["documents status=indexed + counts"]
  Qdrant --> Indexed
  Indexed --> CacheInvalidate["invalidate LLM/doc cache where applicable"]
```

Status lifecycle:

```text
uploaded -> converting -> converted -> cleaning -> cleaned
-> chunking -> chunked -> embedding -> indexed
```

## 8. Crawler Review/Index Flow

```mermaid
flowchart TD
  Scheduler["APScheduler or admin trigger"] --> Crawler["scripts/auto_crawler.AutoCrawlPipeline"]
  Crawler --> Fetch["official HUST sources"]
  Fetch --> Save["save crawl JSON"]
  Save --> Chunk["ChunkProcessor"]
  Chunk --> Stage["Mongo crawler_runs/crawler_chunks pending"]
  Stage --> UI["frontend SystemTab review/edit"]
  UI --> Patch["PATCH staged chunk content"]
  UI --> Index["POST run index"]
  Index --> IndexRun["index_staged_crawler_run"]
  IndexRun --> Embed["reuse app BGE/E5 when available"]
  Embed --> Qdrant["Qdrant"]
  IndexRun --> ES["Elasticsearch"]
  IndexRun --> Archive["append reviewed chunks to data archive"]
  IndexRun --> Cache["invalidate Redis LLM cache by doc/chunk ids"]
  IndexRun --> Eval["post-index current eval trigger"]
  IndexRun --> Notify["notifications + Expo push best-effort"]
```

Current supported crawler targets include `kehoach` and `quydinh`.

## 9. Auth And Session Flow

```mermaid
flowchart TD
  Web["web"] --> AuthRoutes["/auth login/register/refresh/logout"]
  Mobile["mobile"] --> AuthRoutes
  AuthRoutes --> Password["auth/password.py"]
  AuthRoutes --> Microsoft["auth/microsoft.py"]
  AuthRoutes --> Users["Mongo users"]
  AuthRoutes --> Access["JWT access token"]
  AuthRoutes --> Refresh["opaque refresh token hash in Mongo"]
  Refresh -->|web| Cookie["HttpOnly refresh cookie"]
  Refresh -->|mobile| JSON["JSON refresh_token stored in SecureStore"]
  ClientReq["Bearer request"] --> CurrentUser["get_current_user/get_optional_current_user"]
  CurrentUser --> Protected["chat/session/admin/bookmark/notification routes"]
  Protected --> SessionStore["Redis session/history optional"]
  Protected --> MongoLogger["Mongo durable sessions/turns"]
```

## 10. Client Flow

```mermaid
flowchart TD
  Shared["packages/shared"] --> WebLocal["frontend local services/types"]
  Shared --> Mobile["mobile API/stores/types"]
  WebLocal --> WebAuth["in-memory access token + HttpOnly refresh cookie"]
  Mobile --> MobileAuth["SecureStore access + refresh tokens"]
  WebAuth --> API["FastAPI"]
  MobileAuth --> API
  WebChat["ChatContainer"] --> Stream["/chat/stream"]
  WebChat --> ChatV3["/chat/v3"]
  MobileChat["useStreamChat"] --> Stream
  MobileChat --> ChatV3
  API --> Normalize["shared/web normalize response"]
  Normalize --> Trace["trace/debug/source rendering"]
```

## 11. Evaluation Flow

```mermaid
flowchart TD
  Current["evaluation.two_layer_eval current"] --> Golden["eval/golden_dataset.json"]
  Golden --> RetrievalEval["production RetrievalService + router/selector/reranker"]
  Historical["evaluation.two_layer_eval historical"] --> Email["historical email dataset"]
  Email --> E2E["RAGPipeline.query_v3 + optional Gemini judge"]
  SFT["evaluate_sft_backend.py"] --> LiveAPI["live /chat/v3"]
  RetrievalEval --> Store["evaluation/results + Mongo eval runs"]
  E2E --> Store
  SFT --> Store
  Store --> Metrics["/metrics/eval"]
  Metrics --> EvalPage["frontend /eval"]
  CrawlerIndex["crawler post-index"] --> PostIndex["evaluation/post_index.py fail-soft"]
  PostIndex --> Current
```

## 12. Module Boundary Summary

| Module | Owns | Talks to |
| --- | --- | --- |
| `api` | FastAPI app, routes, response mapping, middleware | `auth`, `pipeline`, `models`, `cache`, `schemas`, clients |
| `auth` + `routers` | JWT, refresh tokens, OAuth, RBAC, auth routes | `models`, `schemas`, web/mobile |
| `pipeline` | chat RAG orchestration and admin document pipeline | `query`, `retrieval`, `agent`, `llm`, `models`, `cache` |
| `query` | complexity/domain routing, reflection, entities, structured query | `pipeline`, `retrieval`, `evaluation` |
| `retrieval` | Qdrant/ES search, fusion, filters, validity/reference/parent context | `embedding`, `reranking`, `data`, `pipeline`, `agent` |
| `agent` | Planner-Executor graph for complex questions | `pipeline`, `retrieval`, `tools`, `llm`, `api` |
| `llm` | provider wrappers, prompt messages, self-eval | `pipeline`, `agent`, `config` |
| `tools` | Tavily adapter | `retrieval` runtime wiring, `pipeline`, `agent` |
| `models` | Mongo persistence models/logging/config | `api`, `auth`, `pipeline`, `scripts` |
| `cache` | optional Redis session/history/LLM cache/rate limit | `api`, `pipeline`, `models`, `scripts` |
| `chunking` + `document_loader` | conversion/chunking/metadata production | `pipeline`, `scripts`, `retrieval`, `data` |
| `scripts` | crawler/indexing/maintenance CLIs | `data`, `embedding`, `retrieval`, `models`, `cache`, `evaluation` |
| `frontend` | web UX and admin/trace views | `api`, `schemas`, `packages/shared` |
| `mobile` | Expo/native UX and mobile auth/storage | `api`, `packages/shared` |
| `packages` | shared TS API clients/types/normalizers | web, mobile, backend route/schema contracts |
| `evaluation` + `eval` | regression/eval runners and artifacts | runtime stack, API metrics, frontend eval dashboard |

## 13. Known Flow Cautions

1. `/retrieval/search` currently looks for `pipeline.service`, while `RAGPipeline` stores `_retrieval_service`.
2. `api/main.py` auto-crawler reuse checks may also expect a public retrieval-service property.
3. `/sessions` and `/sessions/me` are produced by router prefix/path composition in `api/routes/session.py`; keep contract tests around this.
4. Streaming chat runs retrieval before streaming tokens and intentionally skips post-generation self-eval/Tavily fallback.
5. Redis is fail-soft and should never be the only durable store.
6. Agent class name is `ReActAgent`, but runtime behavior is Planner-Executor.
