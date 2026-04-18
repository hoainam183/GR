from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from threading import Lock
from typing import Any

from config.settings import Settings

logger = logging.getLogger(__name__)

# Agent-facing collection names -> real retrieval collection names.
COLLECTION_MAP: dict[str, str] = {
    "quy_dinh": "quydinh",
    "chuong_trinh": "ctdt",
    "ke_hoach": "kehoach",
    "thong_bao": "stsv",
}

_COHORT_RE = re.compile(r"\bK\d{2}\b", re.IGNORECASE)


@dataclass
class _AdapterRuntime:
    settings: Settings
    bge_embedder: Any
    e5_embedder: Any
    searcher: Any
    reranker: Any | None
    tavily_tool: Any | None


_RUNTIME: _AdapterRuntime | None = None
_RUNTIME_LOCK = Lock()


def _build_runtime() -> _AdapterRuntime:
    from embedding import BGEm3Embedder, E5MultilingualEmbedder
    from reranking import create_reranker
    from retrieval import create_retriever
    from tools.tavily_search import TavilySearchTool

    settings = Settings()
    bge_embedder = BGEm3Embedder()
    e5_embedder = E5MultilingualEmbedder()
    searcher = create_retriever(settings)
    reranker = create_reranker(settings)

    tavily_key = settings.tavily_api_key or os.environ.get("TAVILY_API_KEY", "")
    tavily_tool: TavilySearchTool | None = None
    if tavily_key and tavily_key not in {"", "your-key-here", "CHANGE_ME", "tvly-xxx"}:
        tavily_tool = TavilySearchTool(api_key=tavily_key)

    return _AdapterRuntime(
        settings=settings,
        bge_embedder=bge_embedder,
        e5_embedder=e5_embedder,
        searcher=searcher,
        reranker=reranker,
        tavily_tool=tavily_tool,
    )


def _get_runtime() -> _AdapterRuntime:
    global _RUNTIME
    if _RUNTIME is not None:
        return _RUNTIME
    with _RUNTIME_LOCK:
        if _RUNTIME is None:
            _RUNTIME = _build_runtime()
    return _RUNTIME


def execute_tool(tool_name: str, args: dict[str, Any]) -> str:
    """Dispatch tool execution and always return a safe string response."""
    dispatch = {
        "rag_search": _rag_search,
        "multi_rag_search": _multi_rag_search,
        "compare_cohorts": _compare_cohorts,
        "web_search": _web_search,
        "clarify_question": _clarify_question,
    }
    adapter = dispatch.get(tool_name)
    if adapter is None:
        return f"[Loi he thong: Tool '{tool_name}' khong duoc ho tro]"
    try:
        result = adapter(**args)
        logger.info("Tool %s executed (chars=%d)", tool_name, len(result))
        return result
    except TypeError as exc:
        logger.error("Tool %s wrong args %s: %s", tool_name, args, exc)
        return f"[Loi: Tham so khong dung cho tool {tool_name}: {exc}]"
    except Exception as exc:  # pragma: no cover - defensive runtime protection
        logger.error("Tool %s failed: %s", tool_name, exc, exc_info=True)
        return f"[Loi khi tim kiem: {exc}]"


def _rag_search(
    query: str,
    collection: str,
    top_k: int | None = None,
    resolved_cohort: str | None = None,
) -> str:
    if not query or not query.strip():
        return "[Loi: Query rong]"

    qdrant_collection = COLLECTION_MAP.get(collection)
    if qdrant_collection is None:
        return f"[Loi: Collection '{collection}' khong hop le]"

    runtime = _get_runtime()
    effective_top_k = max(1, min(int(top_k or runtime.settings.top_k), 10))
    raw_candidate_k = max(effective_top_k * 4, 20)

    bge_vec = runtime.bge_embedder.embed_query(query)
    e5_vec = runtime.e5_embedder.embed_query(query)

    search_kwargs: dict[str, Any] = {
        "query": query,
        "bge_m3_query": bge_vec,
        "e5_query": e5_vec,
        "top_k": raw_candidate_k,
        "vector_top_k": runtime.settings.vector_top_k,
        "keyword_top_k": runtime.settings.keyword_top_k,
        "vector_pool_k": runtime.settings.vector_pool_k,
        "keyword_pool_k": runtime.settings.keyword_pool_k,
        "active_collections": [qdrant_collection],
    }

    cohort = (resolved_cohort or _extract_cohort(query) or "").upper()
    if cohort:
        search_kwargs["resolved_cohort"] = cohort

    results = runtime.searcher.search(**search_kwargs)

    if runtime.reranker is not None:
        results = runtime.reranker.rerank(
            query=query,
            documents=results,
            top_k=effective_top_k,
        )
    else:
        results = results[:effective_top_k]

    return _format_search_results(results, collection)


def _multi_rag_search(queries: list[dict[str, Any]]) -> str:
    if not queries:
        return "[Loi: Khong co query nao duoc cung cap]"

    parts: list[str] = []
    for item in queries[:4]:
        query_text = str(item.get("query", "")).strip()
        collection = str(item.get("collection", "")).strip()
        if not query_text or not collection:
            continue
        result = _rag_search(
            query=query_text,
            collection=collection,
            resolved_cohort=str(item.get("resolved_cohort", "") or "") or None,
        )
        header = f"### Thong tin tu [{collection}] - '{query_text}'"
        parts.append(f"{header}\n{result}")

    if not parts:
        return "Khong tim thay thong tin tu cac nguon duoc yeu cau."
    return "\n\n---\n\n".join(parts)


def _compare_cohorts(topic: str, cohort_a: str, cohort_b: str, collection: str) -> str:
    query_a = f"{topic} {cohort_a}".strip()
    query_b = f"{topic} {cohort_b}".strip()

    result_a = _rag_search(
        query=query_a,
        collection=collection,
        resolved_cohort=cohort_a,
    )
    result_b = _rag_search(
        query=query_b,
        collection=collection,
        resolved_cohort=cohort_b,
    )

    return (
        f"### {topic} - {cohort_a}\n{result_a}\n\n"
        f"---\n\n"
        f"### {topic} - {cohort_b}\n{result_b}"
    )


def _web_search(query: str) -> str:
    if not query or not query.strip():
        return "[Loi: Query web rong]"

    runtime = _get_runtime()
    if runtime.tavily_tool is None:
        return "[Loi: Tavily chua duoc cau hinh API key]"

    results = runtime.tavily_tool.search(query=query, max_results=3)
    return _format_web_results(results)


def _clarify_question(message: str, options: list[str]) -> str:
    clean_options = [str(option).strip() for option in options if str(option).strip()][:3]
    options_text = "\n".join(f"{idx + 1}. {option}" for idx, option in enumerate(clean_options))
    return f"[CLARIFY]\n{message}\n\n{options_text}"


def _format_search_results(results: Any, collection: str) -> str:
    if not results:
        return f"Khong tim thay thong tin phu hop trong {collection}."

    chunks: list[str] = []
    for index, item in enumerate(results[:4], 1):
        content = ""
        source = ""
        score = None

        if hasattr(item, "payload"):
            payload = getattr(item, "payload", {}) or {}
            content = str(payload.get("content") or payload.get("text") or "")
            source = str(payload.get("source") or payload.get("title") or "")
            score = getattr(item, "score", None)
        elif isinstance(item, dict):
            metadata = item.get("metadata", {}) or {}
            content = str(item.get("text") or item.get("content") or "")
            source = str(
                item.get("source")
                or metadata.get("source")
                or metadata.get("title")
                or item.get("collection", "")
            )
            score = item.get("rerank_score", item.get("score"))
        else:
            content = str(item)

        content = " ".join(content.split())
        if len(content) > 700:
            content = content[:700].rstrip() + "..."

        if not content:
            continue

        chunk = f"[{index}] {content}"
        if source:
            chunk += f"\n    Nguon: {source}"
        if score is not None:
            try:
                chunk += f"\n    Diem: {float(score):.4f}"
            except (TypeError, ValueError):
                pass
        chunks.append(chunk)

    if not chunks:
        return f"Khong tim thay thong tin phu hop trong {collection}."
    return "\n\n".join(chunks)


def _format_web_results(results: Any) -> str:
    if not results:
        return "Khong tim thay thong tin tren web."

    answer = ""
    items: list[dict[str, Any]] = []

    if isinstance(results, dict):
        answer = str(results.get("answer", "")).strip()
        raw_items = results.get("results", [])
        if isinstance(raw_items, list):
            items = [item for item in raw_items if isinstance(item, dict)]
    elif isinstance(results, list):
        items = [item for item in results if isinstance(item, dict)]

    chunks: list[str] = []
    for index, item in enumerate(items[:3], 1):
        title = str(item.get("title", "")).strip() or f"Ket qua {index}"
        content = " ".join(str(item.get("content", "")).split())
        if len(content) > 500:
            content = content[:500].rstrip() + "..."
        url = str(item.get("url", "")).strip()
        chunks.append(f"[{index}] {title}\n{content}\nURL: {url}")

    if not chunks and answer:
        return answer
    if answer:
        return f"Tom tat Tavily: {answer}\n\n" + "\n\n".join(chunks)
    if chunks:
        return "\n\n".join(chunks)
    return "Khong tim thay thong tin tren web."


def _extract_cohort(text: str) -> str | None:
    match = _COHORT_RE.search(text)
    if match is None:
        return None
    return match.group(0).upper()