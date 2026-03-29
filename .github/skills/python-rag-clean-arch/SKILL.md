---
description: >
  Rules and workflow for implementing a clean-architecture Python RAG project:
  provider-agnostic LLM/Embedder/Reranker interfaces, folder conventions,
  config-driven provider selection, and factory patterns. USE THIS SKILL for
  any task involving adding a new LLM provider, embedding model, retriever,
  or restructuring the RAG_v2 codebase.
applyTo: "d:/GR/src/RAG_v2/**"
---

# SKILL: Python RAG — Clean Architecture Rules

## Purpose
Produce code that allows swapping LLM providers, embedding models, retrievers,
or rerankers entirely through configuration (`.env` / `Settings`) without
touching business logic or pipeline code.

---

## 1. Folder Structure

```
RAG_v2/
├── config/
│   ├── settings.py          # Pydantic BaseSettings — single source of truth
│   └── __init__.py
├── llm/
│   ├── __init__.py          # exports BaseLLM + factory
│   ├── base.py              # BaseLLM ABC / Protocol
│   ├── gemini.py            # GeminiLLM(BaseLLM)
│   ├── openai_llm.py        # OpenAILLM(BaseLLM)
│   ├── prompts.py           # prompt templates (no provider logic)
│   └── self_eval.py
├── embedding/
│   ├── __init__.py          # exports BaseEmbedder + factory
│   ├── base.py              # BaseEmbedder ABC (already exists)
│   ├── bge_m3.py
│   ├── e5_multilingual.py
│   └── ensemble.py
├── retrieval/
│   ├── __init__.py          # exports BaseRetriever + factory
│   ├── base.py              # BaseRetriever ABC
│   ├── qdrant_store.py
│   └── elasticsearch_store.py
├── reranking/
│   ├── __init__.py          # exports BaseReranker + factory
│   ├── base.py              # BaseReranker ABC
│   └── bge_reranker.py
├── chunking/
│   └── chunker/
│       ├── base_chunker.py  # DocumentChunker ABC (already exists)
│       └── ...
├── pipeline/
│   ├── rag_pipeline.py      # depends only on ABCs, not concretions
│   └── flows.py
├── memory/
├── query/
├── tools/
├── utils/
├── api/
└── tests/
```

**Rules:**
- Every layer (`llm`, `embedding`, `retrieval`, `reranking`) MUST have a
  `base.py` with an ABC or Protocol and a factory function in `__init__.py`.
- `pipeline/` imports only ABCs, never concrete classes directly.
- `config/settings.py` is the ONLY place provider names and credentials live.

---

## 2. Interface Pattern (ABC)

Every swappable component uses this pattern:

```python
# llm/base.py
from abc import ABC, abstractmethod
from typing import Dict, Generator, List, Optional

class BaseLLM(ABC):
    """Provider-agnostic LLM interface."""

    @abstractmethod
    def generate(
        self,
        query: str,
        context: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        mode: str = "rag",
    ) -> str: ...

    @abstractmethod
    def generate_stream(
        self,
        query: str,
        context: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        mode: str = "rag",
    ) -> Generator[str, None, None]: ...
```

**Rules:**
- Concrete classes (`GeminiLLM`, `OpenAILLM`) inherit the ABC and implement
  ALL abstract methods.
- Concrete classes take only their own credentials + model params in `__init__`.
  They do NOT read from `Settings` directly — `Settings` is read by the factory.
- Never import a concrete class outside its own module except in the factory.

---

## 3. Factory / Registry Pattern (Lazy Loading)

Providers are **not imported at module load time**. The factory imports the
concrete module on first call, so unused providers add zero startup cost and
their heavy dependencies (torch, transformers, etc.) are never loaded unless
actually needed.

```python
# llm/__init__.py
from __future__ import annotations
import importlib
from typing import Optional
from .base import BaseLLM
from config.settings import Settings

# Map provider name → dotted module path inside llm/
_PROVIDER_MODULES: dict[str, str] = {
    "gemini":  "llm.gemini",
    "openai":  "llm.openai_llm",
    "azure":   "llm.azure_llm",
    "ollama":  "llm.ollama_llm",
}
_REGISTRY: dict[str, type[BaseLLM]] = {}

def register_llm(name: str):
    """Decorator to register an LLM provider class."""
    def decorator(cls: type[BaseLLM]):
        _REGISTRY[name] = cls
        return cls
    return decorator

def create_llm(settings: Settings) -> BaseLLM:
    """Lazy-import and instantiate the configured LLM provider."""
    provider = settings.llm_provider
    if provider not in _REGISTRY:
        module_path = _PROVIDER_MODULES.get(provider)
        if module_path is None:
            raise ValueError(
                f"Unknown LLM provider '{provider}'. "
                f"Known providers: {list(_PROVIDER_MODULES)}"
            )
        importlib.import_module(module_path)  # triggers @register_llm
    cls = _REGISTRY[provider]
    return cls(
        api_key=settings.llm_api_key,
        model=settings.chat_model,
        temperature=settings.chat_temperature,
        max_tokens=settings.chat_max_tokens,
    )
```

```python
# llm/gemini.py  — registers itself when imported
from llm import register_llm
from llm.base import BaseLLM

@register_llm("gemini")
class GeminiLLM(BaseLLM):
    ...
```

**Rules for lazy loading:**
- Add every new provider to `_PROVIDER_MODULES` in `__init__.py` — this is the
  only registration step needed beside the decorated class itself.
- Never add a bare `import llm.gemini` at the top of `__init__.py`; that defeats
  lazy loading.
- `_REGISTRY` is populated on first call to `create_llm`, not at import time.

Apply the same lazy-loading factory pattern to `embedding/`, `reranking/`,
`retrieval/`.

---

## 4. Settings — Provider Selection via Env

```python
# config/settings.py  (additions)
class Settings(BaseSettings):
    # Provider selectors — change in .env, no code edits needed
    llm_provider: str = "gemini"          # gemini | openai | azure | ollama
    embedding_provider: str = "ensemble"  # ensemble | bge_m3 | e5
    reranker_provider: str = "bge"        # bge | cohere | none

    # Per-provider credentials (only the active one must be set)
    google_api_key: str = ""
    openai_api_key: str = ""
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"
```

**.env example:**
```dotenv
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
CHAT_MODEL=gpt-4o-mini
```

**Rules:**
- Adding a new provider = create `llm/<provider>.py`, decorate with
  `@register_llm("<name>")`, set `LLM_PROVIDER=<name>` in `.env`.
- Zero changes to `pipeline/`, `api/`, or `flows.py`.

---

## 5. Pipeline Wiring

### Optional Reranker

Set `RERANKER_PROVIDER=none` in `.env` to skip reranking entirely (useful for
lightweight / CPU-only deployments). The factory returns `None`; the pipeline
branches on it:

```python
# reranking/__init__.py
from __future__ import annotations
import importlib
from typing import Optional
from .base import BaseReranker
from config.settings import Settings

_PROVIDER_MODULES: dict[str, str] = {
    "bge":    "reranking.bge_reranker",
    "cohere": "reranking.cohere_reranker",
}
_REGISTRY: dict[str, type[BaseReranker]] = {}

def register_reranker(name: str):
    def decorator(cls: type[BaseReranker]):
        _REGISTRY[name] = cls
        return cls
    return decorator

def create_reranker(settings: Settings) -> Optional[BaseReranker]:
    """Return None when reranker_provider is 'none'."""
    provider = settings.reranker_provider
    if provider == "none":
        return None
    if provider not in _REGISTRY:
        module_path = _PROVIDER_MODULES.get(provider)
        if module_path is None:
            raise ValueError(f"Unknown reranker '{provider}'.")
        importlib.import_module(module_path)
    return _REGISTRY[provider](model_name=settings.reranker_model)
```

```python
# pipeline/rag_pipeline.py
from config.settings import Settings
from embedding import create_embedder
from llm import create_llm
from reranking import create_reranker
from reranking.base import BaseReranker
from typing import Optional

class RAGPipeline:
    def __init__(self, settings: Settings):
        self._llm = create_llm(settings)
        self._embedder = create_embedder(settings)
        self._reranker: Optional[BaseReranker] = create_reranker(settings)
        # ...

    def _rerank(self, query: str, docs: list) -> list:
        """Rerank docs if a reranker is configured, else return as-is."""
        if self._reranker is None:
            return docs
        return self._reranker.rerank(query, docs)
```

**Settings addition:**
```python
reranker_provider: str = "bge"   # bge | cohere | none
reranker_model: str = "BAAI/bge-reranker-v2-m3"
```

**Rules:**
- `RAGPipeline.__init__` calls only factory functions, never constructors.
- All runtime behaviour flows from a single `Settings` instance passed in.
- Tests inject mock / stub implementations of the ABCs — no live API calls.
- Always check `if self._reranker is None` before calling reranker methods.

---

## 6. Prompts — Provider-Neutral Design

`llm/prompts.py` contains **only string templates**. It must never import any
SDK, call any API, or reference a provider class.

```python
# llm/prompts.py  — provider-neutral template module

RAG_SYSTEM_PROMPT: str = "..."       # pure string
RAG_USER_TEMPLATE: str = "..."       # uses {context} / {query} placeholders
CHITCHAT_SYSTEM_PROMPT: str = "..."

def build_rag_messages(
    query: str,
    context: str,
    history: list[dict] | None = None,
) -> list[dict]:
    """Return OpenAI-style message list — no SDK import."""
    messages = [{"role": "system", "content": RAG_SYSTEM_PROMPT}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": RAG_USER_TEMPLATE.format(
        context=context, query=query
    )})
    return messages
```

Concrete LLM classes call `build_rag_messages()` and adapt the output to their
SDK's expected format:

```python
# llm/gemini.py
from llm.prompts import build_rag_messages
from openai import OpenAI  # Gemini via OpenAI-compat endpoint

class GeminiLLM(BaseLLM):
    def generate(self, query, context=None, history=None, mode="rag") -> str:
        messages = build_rag_messages(query, context or "", history)
        # Pass messages to the Gemini-compatible client
        ...

# llm/ollama_llm.py
from llm.prompts import build_rag_messages
import ollama

class OllamaLLM(BaseLLM):
    def generate(self, query, context=None, history=None, mode="rag") -> str:
        messages = build_rag_messages(query, context or "", history)
        # Same messages dict, different SDK call
        ...
```

**Rules:**
- `prompts.py` has zero imports from any LLM SDK.
- Template helpers (`build_rag_messages`, `build_chitchat_messages`) live in
  `prompts.py`, not inside a concrete provider class.
- All providers share the same Vietnamese HUST prompt wording — never duplicate
  prompt text inside individual provider files.
- To change wording for all providers at once, edit only `prompts.py`.

---

## 7. Checklist — Adding a New LLM Provider

1. [ ] Create `llm/<provider>.py` with `class <Name>LLM(BaseLLM):`
2. [ ] Decorate with `@register_llm("<name>")`
3. [ ] Implement `generate()` and `generate_stream()` using helpers from `prompts.py`
4. [ ] Add the provider to `_PROVIDER_MODULES` in `llm/__init__.py`
5. [ ] Add any new credential fields to `Settings` (with empty string default)
6. [ ] Add the new key to `.env.example` with a comment
7. [ ] Set `LLM_PROVIDER=<name>` + credentials in `.env` — no other code change
8. [ ] Write a unit test using the ABC stub fixture

---

## 8. Testing Convention

```python
# tests/fakes.py
from llm.base import BaseLLM

class FakeLLM(BaseLLM):
    def generate(self, query, context=None, history=None, mode="rag") -> str:
        return f"FAKE:{query}"

    def generate_stream(self, query, context=None, history=None, mode="rag"):
        yield f"FAKE:{query}"
```

Use `FakeLLM` / `FakeEmbedder` in all pipeline unit tests so tests are fast,
offline, and provider-independent.

---

## 9. Quality Gates (before merging provider code)

- `mypy src/RAG_v2/llm/` passes with no errors.
- `isinstance(llm, BaseLLM)` is `True` for every concrete class.
- Pipeline tests pass against `FakeLLM` without any real API call.
- `.env.example` documents every new env var added.
- No concrete provider class is imported outside `llm/__init__.py` factory.
