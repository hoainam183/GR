## Plan: RAG_v2 Clean Architecture Refactor

**TL;DR** — The codebase has 5 modules hard-wired to concrete classes. The refactor adds ABCs + lazy factories to each layer so that swapping any provider is a single `.env` change.

---

### Gap Analysis

| Module | Current Problem |
|---|---|
| `llm/__init__.py` | exports `ChatModel` directly, no ABC, no factory |
| `llm/chat_model.py` | Gemini-only, message builders inline in class |
| `llm/prompts.py` | pure strings only — missing `build_*_messages()` helpers |
| `llm/self_eval.py` | creates its own `OpenAI` client with hardcoded Gemini URL |
| `embedding/__init__.py` | `BaseEmbedder` inline, no factory |
| `reranking/__init__.py` | direct import of `BGEReranker`, no ABC, no factory |
| `retrieval/__init__.py` | all concrete imports, no ABC |
| `config/settings.py` | missing `llm_provider`, `embedding_provider`, `reranker_provider` fields |
| `pipeline/rag_pipeline.py` | directly instantiates `BGEm3Embedder`, `BGEReranker`, `ChatModel` |

---

### Phase 1 — Foundation *(steps parallel)*

1. **`config/settings.py`** — add `llm_provider`, `embedding_provider`, `reranker_provider`, `llm_api_key`, `azure_*`, `ollama_base_url`, `reranker_model`; sync `.env.example`
2. **`llm/base.py`** *(NEW)* — `BaseLLM` ABC: `generate()` + `generate_stream()`
3. **`embedding/base.py`** *(NEW)* — extract `BaseEmbedder` out of `__init__.py` into its own file
4. **`reranking/base.py`** *(NEW)* — `BaseReranker` ABC: `rerank(query, docs) -> list`
5. **`retrieval/base.py`** *(NEW)* — `BaseRetriever` ABC: `search(query, ...) -> list`

### Phase 2 — Concrete Classes *(depends on Phase 1)*

6. **`llm/prompts.py`** — add `build_rag_messages()` and `build_chitchat_messages()` helpers; move message-assembly logic out of `chat_model.py`
7. **`llm/gemini.py`** *(NEW from `chat_model.py`)* — `GeminiLLM(BaseLLM)`, decorated `@register_llm("gemini")`, calls helpers from `prompts.py`; keep `chat_model.py` as a thin backwards-compat alias
8. **`reranking/bge_reranker.py`** — inherit `BaseReranker`, add `@register_reranker("bge")`
9. **`llm/self_eval.py`** — refactor constructor to accept `BaseLLM` instance instead of raw `api_key`

### Phase 3 — Factories *(depends on Phase 1+2, steps parallel)*

10. **`llm/__init__.py`** — rewrite: `_PROVIDER_MODULES` dict, `_REGISTRY`, `register_llm()` decorator, `create_llm(settings) -> BaseLLM`
11. **`embedding/__init__.py`** — rewrite: import `BaseEmbedder` from `base.py`, add `create_embedder(settings)` lazy factory
12. **`reranking/__init__.py`** — rewrite: lazy registry, `create_reranker(settings) -> Optional[BaseReranker]` (returns `None` for `RERANKER_PROVIDER=none`)
13. **`retrieval/__init__.py`** — add `create_retriever(settings)` factory

### Phase 4 — Pipeline Rewire *(depends on Phase 3)*

14. **`pipeline/rag_pipeline.py`** — `RAGPipeline.__init__` accepts only `Settings`; all construction via `create_llm()`, `create_embedder()`, `create_reranker()`; pass `BaseLLM` instance into `SelfEvaluator`
15. **`pipeline/flows.py`** — update type hints to ABCs instead of concrete classes

### Phase 5 — Tests *(parallel with Phase 4)*

16. **`tests/fakes.py`** *(NEW)* — `FakeLLM(BaseLLM)`, `FakeEmbedder(BaseEmbedder)`, `FakeReranker(BaseReranker)`
17. Add pipeline unit tests that use fakes (no live API calls)

---

### Files Modified

- `src/RAG_v2/config/settings.py`
- `src/RAG_v2/llm/__init__.py`
- `src/RAG_v2/llm/prompts.py`
- `src/RAG_v2/llm/self_eval.py`
- `src/RAG_v2/embedding/__init__.py`
- `src/RAG_v2/reranking/__init__.py`
- `src/RAG_v2/reranking/bge_reranker.py`
- `src/RAG_v2/retrieval/__init__.py`
- `src/RAG_v2/pipeline/rag_pipeline.py`
- `src/RAG_v2/pipeline/flows.py`

### Files Created

- `src/RAG_v2/llm/base.py`
- `src/RAG_v2/llm/gemini.py`
- `src/RAG_v2/embedding/base.py`
- `src/RAG_v2/reranking/base.py`
- `src/RAG_v2/retrieval/base.py`
- `src/RAG_v2/tests/fakes.py`

---

### Verification

1. `python -c "from pipeline import RAGPipeline"` — no import errors
2. Existing behaviour unchanged: `LLM_PROVIDER=gemini` in `.env`
3. `mypy src/RAG_v2/llm/ src/RAG_v2/embedding/ src/RAG_v2/reranking/` — zero errors
4. Pipeline unit tests pass with `FakeLLM` (offline, no API key needed)
5. `create_reranker()` returns `None` when `RERANKER_PROVIDER=none`

---

### Scope Boundary

`chunking/` already has `DocumentChunker` ABC and is compliant — no changes needed.
`query/`, `memory/`, `tools/` are not swappable providers — excluded from this refactor.
