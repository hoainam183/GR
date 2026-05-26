from __future__ import annotations

import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextvars import ContextVar
from dataclasses import dataclass
from threading import Lock
from typing import Any

from config.settings import Settings
from retrieval.metadata_filters import (
    extract_major_codes,
    strip_major_comparison_scaffold_for_retrieval,
    strip_major_from_query_for_retrieval,
)
from schemas.constants import CLARIFY_SENTINEL

logger = logging.getLogger(__name__)

# ─── Personal Identifier stripping ──────────────────────────────────────────────
_STUDENT_ID_RE = re.compile(r'\b\d{8}\b')
_STUDENT_ID_PREFIX_RE = re.compile(
    r'(mã\s*sv|mssv|sinh\s*viên\s*mã?)\s*:?\s*\d+',
    re.IGNORECASE
)

def strip_personal_identifiers(query: str) -> str:
    """Xóa mã sinh viên và các identifier cá nhân khỏi retrieval query."""
    q = _STUDENT_ID_PREFIX_RE.sub('', query)
    q = _STUDENT_ID_RE.sub('', q)
    q = re.sub(r',\s*,', ',', q)
    q = re.sub(r'\s{2,}', ' ', q).strip().strip(',').strip()
    return q

# ─── Collection name mapping ──────────────────────────────────────────────────
# Agent-facing collection names → real Qdrant collection names.

COLLECTION_MAP: dict[str, str] = {
    "quy_dinh":     "quydinh",   # quy định học vụ, học bổng, kỷ luật, tốt nghiệp
    "chuong_trinh": "ctdt",      # chương trình đào tạo, môn học, tín chỉ
    "ke_hoach":     "kehoach",   # lịch đăng ký, lịch thi, deadline, kế hoạch học kỳ
    "ho_tro_sv":    "stsv",      # hỗ trợ sinh viên: biểu mẫu, giấy tờ, thuê nhà, tìm việc
}

# ─── Simple RAG search cache ─────────────────────────────────────────────────
# In-memory FIFO cache keyed by (query, collection, top_k, cohort, major).
# Avoids redundant Qdrant + reranker calls for frequently repeated queries.
# Thread-safe: protected by _CACHE_LOCK.

_RAG_CACHE: dict[tuple, str] = {}
_RAG_CACHE_MAX = 256
_CACHE_LOCK = Lock()

# BGE reranker tokenizer is not thread-safe ("Already borrowed" RuntimeError).
# This lock serialises rerank() calls while still allowing parallel embedding + search.
_RERANKER_LOCK = Lock()

# ─── Per-request Agent Retrieved Documents ────────────────────────────────────
# Dùng ContextVar để mỗi request/thread có danh sách docs riêng biệt.
# Tránh race condition khi nhiều user query đồng thời trên cùng server.
#
# Cách dùng đúng:
#   1. Gọi init_agent_docs() trước agent.run() (trong thread worker)
#   2. Gọi get_agent_docs() sau agent.run() để lấy kết quả
_agent_docs_ctx: ContextVar[list[dict[str, Any]] | None] = ContextVar(
    "agent_docs", default=None
)


def init_agent_docs() -> list[dict[str, Any]]:
    """Khởi tạo danh sách docs cho request hiện tại.

    Phải được gọi trong thread worker (sau anyio.to_thread.run_sync)
    để ContextVar được set đúng trong context của thread đó.
    """
    docs: list[dict[str, Any]] = []
    _agent_docs_ctx.set(docs)
    return docs


def clear_agent_docs() -> None:
    """Reset context về empty list (backward compat với code cũ)."""
    _agent_docs_ctx.set([])


def get_agent_docs() -> list[dict[str, Any]]:
    """Trả về danh sách docs của request hiện tại (thread-safe)."""
    docs = _agent_docs_ctx.get(None)
    return list(docs) if docs is not None else []


def _append_agent_docs(items: list) -> None:
    """Thêm items vào danh sách docs của request hiện tại."""
    docs = _agent_docs_ctx.get(None)
    if docs is not None:
        docs.extend(items)


def _cache_get(key: tuple) -> str | None:
    with _CACHE_LOCK:
        return _RAG_CACHE.get(key)


def _cache_set(key: tuple, value: str) -> None:
    with _CACHE_LOCK:
        if len(_RAG_CACHE) >= _RAG_CACHE_MAX:
            # FIFO eviction — remove the oldest entry
            _RAG_CACHE.pop(next(iter(_RAG_CACHE)))
        _RAG_CACHE[key] = value


def cache_clear() -> None:
    """Clear the RAG search cache.  Useful for testing and after data updates."""
    with _CACHE_LOCK:
        _RAG_CACHE.clear()
    logger.info("[Cache] RAG search cache cleared")


# ─── Lazy singleton runtime ───────────────────────────────────────────────────

_COHORT_RE = re.compile(r"\bK\d{2,3}\b", re.IGNORECASE)
_COHORT_TOKEN_RE = re.compile(r"^\s*K?(\d{2,3})\s*$", re.IGNORECASE)
_DEFAULT_CLARIFY_OPTIONS = [
    "So sanh giua 2 ma nganh cu the",
    "So sanh giua 2 khoa cu the",
    "Dat lai cau hoi kem day du ma nganh hoac ma khoa",
]
_COMPARE_CLARIFY_MESSAGE = (
    "Ban muon so sanh mon nay giua hai ma nganh hay hai ma khoa nao?"
)
_COMPARE_CLARIFY_OPTIONS = [
    "Nhap 2 ma nganh (A va B)",
    "Nhap 2 ma khoa (A va B)",
    "Nhap lai cau hoi theo mau: so sanh <mon> giua <A> va <B>",
]


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

# ─── API key validation ───────────────────────────────────────────────────────

# Known placeholder patterns that indicate the key has NOT been configured.
_INVALID_KEY_PREFIXES: tuple[str, ...] = ("your-", "CHANGE", "tvly-xxx")
_INVALID_KEY_EXACT: frozenset[str] = frozenset({"", "tvly-xxx", "CHANGE_ME"})


def _is_valid_api_key(key: str) -> bool:
    """Return True only when *key* looks like a real, configured API key.

    Rejects empty strings, whitespace-only strings, and well-known placeholder
    values that appear in .env.example files.  Uses prefix matching so that
    new placeholder variants (e.g. ``your-tavily-api-key-here``) are rejected
    without having to maintain an ever-growing exact-match list.
    """
    from tools.tavily_search import is_valid_tavily_api_key

    return is_valid_tavily_api_key(key)


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
    if _is_valid_api_key(tavily_key):
        tavily_tool = TavilySearchTool(
            api_key=tavily_key,
            cache_maxsize=settings.tavily_cache_maxsize,
            cache_ttl_seconds=settings.tavily_cache_ttl_seconds,
        )

    return _AdapterRuntime(
        settings=settings,
        bge_embedder=bge_embedder,
        e5_embedder=e5_embedder,
        searcher=searcher,
        reranker=reranker,
        tavily_tool=tavily_tool,
    )


def set_runtime(runtime: _AdapterRuntime | None) -> None:
    """Inject a pre-built (or mock) runtime.

    Used by ``RAGPipeline.__init__`` to share its already-loaded embedders,
    searcher, and reranker with the agent tool adapters — eliminating the
    ~17 s cold-start that occurs when models are loaded a second time.

    Pass ``None`` to reset to lazy-init mode so the next call to
    ``_get_runtime()`` will rebuild from settings.
    """
    global _RUNTIME
    with _RUNTIME_LOCK:
        _RUNTIME = runtime


def inject_from_retrieval_service(retrieval_service: Any) -> None:
    """Inject a shared runtime from the pipeline's RetrievalService.

    This avoids duplicating heavy model loading (BGE-M3, E5, reranker)
    that would otherwise add ~17 s to the first agent tool call.
    """
    settings = Settings()
    tavily_key = settings.tavily_api_key or os.environ.get("TAVILY_API_KEY", "")
    tavily_tool = None
    if _is_valid_api_key(tavily_key):
        from tools.tavily_search import TavilySearchTool
        tavily_tool = TavilySearchTool(
            api_key=tavily_key,
            cache_maxsize=settings.tavily_cache_maxsize,
            cache_ttl_seconds=settings.tavily_cache_ttl_seconds,
        )

    runtime = _AdapterRuntime(
        settings=settings,
        bge_embedder=retrieval_service.bge_embedder,
        e5_embedder=retrieval_service.e5_embedder,
        searcher=retrieval_service.searcher,
        reranker=retrieval_service.reranker,
        tavily_tool=retrieval_service.tavily_tool or tavily_tool,
    )
    set_runtime(runtime)
    logger.info("[ToolAdapters] Runtime injected from RetrievalService (shared models)")


def _get_runtime() -> _AdapterRuntime:
    global _RUNTIME
    if _RUNTIME is not None:
        return _RUNTIME
    with _RUNTIME_LOCK:
        if _RUNTIME is None:
            _RUNTIME = _build_runtime()
    return _RUNTIME


# ─── Public dispatch ──────────────────────────────────────────────────────────


def execute_tool(tool_name: str, args: dict[str, Any]) -> str:
    """Dispatch tool execution and always return a safe string response."""
    dispatch = {
        "rag_search": _rag_search,
        "multi_rag_search": _multi_rag_search,
        "compare_cohorts": _compare_cohorts,
        "compare_programs": _compare_programs,
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
    except Exception as exc:  # pragma: no cover
        logger.error("Tool %s failed: %s", tool_name, exc, exc_info=True)
        return f"[Loi khi tim kiem: {exc}]"


# ─── Tool implementations ─────────────────────────────────────────────────────


def _rag_search(
    query: str,
    collection: str,
    top_k: int | None = None,
    resolved_cohort: str | None = None,
    resolved_major: str | None = None,
) -> str:
    if not query or not query.strip():
        return "[Loi: Query rong]"

    qdrant_collection = COLLECTION_MAP.get(collection)
    if qdrant_collection is None:
        return f"[Loi: Collection '{collection}' khong hop le]"

    runtime = _get_runtime()
    effective_top_k = max(1, min(top_k if top_k is not None else runtime.settings.top_k, 10))

    raw_query = strip_personal_identifiers(query.strip())
    major_codes = extract_major_codes(raw_query)
    effective_resolved_major = resolved_major
    if not effective_resolved_major and len(major_codes) == 1:
        effective_resolved_major = major_codes[0]

    retrieval_query = raw_query
    if effective_resolved_major or len(major_codes) <= 1:
        retrieval_query = strip_major_from_query_for_retrieval(
            raw_query,
            resolved_major=effective_resolved_major,
        )

    cohort = (resolved_cohort or _extract_cohort(raw_query) or "").upper()

    # ── Cache lookup ──────────────────────────────────────────────────────────
    cache_key = (
        retrieval_query.lower(),
        collection,
        effective_top_k,
        cohort,
        (effective_resolved_major or "").upper(),
    )
    cached = _cache_get(cache_key)
    if cached is not None:
        logger.debug("[Cache] Hit: collection=%s query='%s'", collection, retrieval_query[:50])
        return cached

    # ── Execute search ────────────────────────────────────────────────────────
    raw_candidate_k = max(effective_top_k * 4, 20)

    bge_vec = runtime.bge_embedder.embed_query(retrieval_query)
    e5_vec = runtime.e5_embedder.embed_query(retrieval_query)

    search_kwargs: dict[str, Any] = {
        # ES keyword search uses raw_query to preserve "kỳ", quoted phrases,
        # and other signals stripped from retrieval_query for vector embedding.
        "query": raw_query,
        "bge_m3_query": bge_vec,
        "e5_query": e5_vec,
        "top_k": raw_candidate_k,
        "vector_top_k": runtime.settings.vector_top_k,
        "keyword_top_k": runtime.settings.keyword_top_k,
        "vector_pool_k": runtime.settings.vector_pool_k,
        "keyword_pool_k": runtime.settings.keyword_pool_k,
        "active_collections": [qdrant_collection],
    }
    if effective_resolved_major:
        search_kwargs["resolved_major"] = effective_resolved_major
    if cohort:
        search_kwargs["resolved_cohort"] = cohort

    results = runtime.searcher.search(**search_kwargs)

    # Bypass reranker for curriculum tables because the reranker's semantic
    # threshold tends to drop long tables when the query is very short.
    # Check against raw_query (before major stripping) so we don't miss
    # "kỳ" keywords that may have been stripped alongside major codes.
    skip_rerank = False
    curriculum_kw_check = raw_query.lower()
    if collection == "chuong_trinh" and any(w in curriculum_kw_check for w in ["kỳ", "kì", "ky ", "ky\"", "chẵn", "lẻ", "đăng ký", "dang ky"]):
        skip_rerank = True

    if runtime.reranker is not None and not skip_rerank:
        with _RERANKER_LOCK:
            results = runtime.reranker.rerank(
                query=retrieval_query,
                documents=results,
                top_k=effective_top_k,
            )
    else:
        results = results[:effective_top_k]

    # Parent context expansion for agent (tight budget: 500 chars)
    if getattr(runtime.settings, "parent_context_enabled", True):
        try:
            from retrieval.parent_context import ParentContextExpander

            expander = ParentContextExpander(
                qdrant_host=runtime.settings.qdrant_host,
                qdrant_port=runtime.settings.qdrant_port,
                max_parent_chars=getattr(runtime.settings, "parent_max_chars_agent", 500),
            )
            results = expander.expand_with_parents(results, qdrant_collection)
        except Exception:
            pass  # Graceful degradation — continue without parent

    # Accumulate for UI diagnostic logging (per-request, thread-safe)
    _append_agent_docs(results)

    if not results:
        return "[Khong tim thay thong tin trong co so du lieu]"

    formatted = _format_search_results(results, collection, runtime.settings)

    # ── Cache write (skip system errors) ─────────────────────────────────────
    if not formatted.startswith("[Loi"):
        _cache_set(cache_key, formatted)

    return formatted


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
            resolved_major=str(item.get("resolved_major", "") or "") or None,
        )
        header = f"### Thong tin tu [{collection}] - '{query_text}'"
        parts.append(f"{header}\n{result}")

    if not parts:
        return "Khong tim thay thong tin tu cac nguon duoc yeu cau."
    return "\n\n---\n\n".join(parts)

def _topic_with_course_focus(topic: str, course_keyword: str | None) -> str:
    raw_topic = (topic or "").strip()
    raw_course = (course_keyword or "").strip()

    if not raw_course:
        return raw_topic

    if not raw_topic:
        return f"mon {raw_course}"

    if raw_course.lower() in raw_topic.lower():
        return raw_topic

    return f"{raw_topic} (tap trung vao mon {raw_course})"


def _extract_all_cohort_codes(value: str) -> list[str]:
    return [match.group(0).upper() for match in _COHORT_RE.finditer(value or "")]


def _is_compare_clarification(message: str, options: list[str]) -> bool:
    merged = " ".join([message, *options]).lower()
    return (
        "so sanh" in merged
        or "so sánh" in merged
        or "vs" in merged
        or "khac nhau" in merged
    )


def _normalise_compare_clarification(
    message: str,
    options: list[str],
) -> tuple[str, list[str]]:
    if not _is_compare_clarification(message, options):
        return message, options

    # Never suggest mixed major/cohort pairings for comparison clarification.
    return _COMPARE_CLARIFY_MESSAGE, list(_COMPARE_CLARIFY_OPTIONS)


def _compare_cohorts(
    topic: str,
    cohort_a: str,
    cohort_b: str,
    collection: str,
) -> str:
    """
    So sánh quy định / chính sách giữa 2 **khóa** sinh viên (K65, K70, …).

    Chỉ chấp nhận mã khóa (Kxx).  Nếu nhận mã ngành, trả về hướng dẫn
    chuyển sang compare_programs.
    """
    label_a = (cohort_a or "").strip()
    label_b = (cohort_b or "").strip()

    # Guard: từ chối nếu user truyền mã ngành thay vì mã khóa
    major_a = _extract_single_major_code(label_a)
    major_b = _extract_single_major_code(label_b)
    if major_a or major_b:
        return (
            f"'{label_a}' hoặc '{label_b}' trông giống mã ngành, không phải mã khóa (Kxx).\n"
            "Vui lòng dùng tool compare_programs để so sánh giữa 2 mã ngành."
        )

    resolved_cohort_a = _normalise_cohort_token(label_a) or label_a
    resolved_cohort_b = _normalise_cohort_token(label_b) or label_b

    query_a = f"{topic} {resolved_cohort_a}".strip()
    query_b = f"{topic} {resolved_cohort_b}".strip()

    # Parallel search — halves latency for the two independent retrievals.
    with ThreadPoolExecutor(max_workers=2) as pool:
        future_a = pool.submit(
            _rag_search, query=query_a, collection=collection,
            resolved_cohort=resolved_cohort_a,
        )
        future_b = pool.submit(
            _rag_search, query=query_b, collection=collection,
            resolved_cohort=resolved_cohort_b,
        )
        result_a = future_a.result(timeout=45)
        result_b = future_b.result(timeout=45)

    return (
        f"### {topic} — {resolved_cohort_a}\n{result_a}\n\n"
        f"---\n\n"
        f"### {topic} — {resolved_cohort_b}\n{result_b}"
    )


def _compare_programs(
    topic: str,
    major_a: str,
    major_b: str,
    collection: str,
    course_keyword: str | None = None,
) -> str:
    """
    So sánh chương trình đào tạo / môn học giữa 2 **mã ngành** (IT-E6, IT-E7, …).

    Chỉ chấp nhận mã ngành.  Nếu nhận mã khóa (Kxx), trả về hướng dẫn
    chuyển sang compare_cohorts.
    """
    label_a = (major_a or "").strip()
    label_b = (major_b or "").strip()

    # Guard: từ chối nếu user truyền mã khóa thay vì mã ngành
    cohort_a = _normalise_cohort_token(label_a)
    cohort_b = _normalise_cohort_token(label_b)
    if cohort_a or cohort_b:
        return (
            f"'{label_a}' hoặc '{label_b}' trông giống mã khóa (Kxx), không phải mã ngành.\n"
            "Vui lòng dùng tool compare_cohorts để so sánh giữa 2 khóa."
        )

    resolved_major_a = _extract_single_major_code(label_a) or label_a
    resolved_major_b = _extract_single_major_code(label_b) or label_b

    focused_topic = _topic_with_course_focus(topic, course_keyword)
    clean_topic = strip_major_comparison_scaffold_for_retrieval(focused_topic)
    if not clean_topic.strip():
        clean_topic = focused_topic or "chuong trinh dao tao"

    query_a = f"{clean_topic} ngành {resolved_major_a}".strip()
    query_b = f"{clean_topic} ngành {resolved_major_b}".strip()

    # Parallel search — halves latency for the two independent retrievals.
    with ThreadPoolExecutor(max_workers=2) as pool:
        future_a = pool.submit(
            _rag_search, query=query_a, collection=collection,
            resolved_major=resolved_major_a,
        )
        future_b = pool.submit(
            _rag_search, query=query_b, collection=collection,
            resolved_major=resolved_major_b,
        )
        result_a = future_a.result(timeout=45)
        result_b = future_b.result(timeout=45)

    header = focused_topic or topic
    return (
        f"### {header} — {resolved_major_a}\n{result_a}\n\n"
        f"---\n\n"
        f"### {header} — {resolved_major_b}\n{result_b}"
    )


def _web_search(query: str) -> str:
    if not query or not query.strip():
        return "[Loi: Query web rong]"

    runtime = _get_runtime()
    if runtime.tavily_tool is None:
        return "[Loi: Tavily chua duoc cau hinh API key]"

    from tools.tavily_search import (
        EDU_AUTHORITATIVE_DOMAINS,
        HUST_EXTENDED_DOMAINS,
        HUST_OFFICIAL_DOMAINS,
    )

    results = runtime.tavily_tool.search(
        query=query,
        max_results=getattr(runtime.settings, "tavily_max_results", 3),
        search_depth=getattr(runtime.settings, "tavily_search_depth", "basic"),
        include_domains=(
            HUST_OFFICIAL_DOMAINS
            + HUST_EXTENDED_DOMAINS
            + EDU_AUTHORITATIVE_DOMAINS
        ),
    )
    return _format_web_results(results)


def web_search_for_executor(query: str) -> str:
    """Public wrapper cho _web_search — dùng bởi react_agent._executor_node.

    Tách riêng để react_agent có thể import ở top-level (thay vì runtime import
    private function), đảm bảo encapsulation và dễ mock trong tests.
    """
    return _web_search(query=query)


def _clarify_question(message: str, options: list[str]) -> str:
    clean_message = (message or "").strip()
    clean_options = [opt.strip() for opt in options if opt.strip()][:3]
    clean_message, clean_options = _normalise_compare_clarification(
        clean_message,
        clean_options,
    )

    if len(clean_options) < 2:
        for default_option in _DEFAULT_CLARIFY_OPTIONS:
            if default_option not in clean_options:
                clean_options.append(default_option)
            if len(clean_options) >= 3:
                break

    # Remove options that accidentally mix major+cohort codes in one choice.
    filtered_options: list[str] = []
    for option in clean_options:
        has_major = bool(extract_major_codes(option))
        has_cohort = bool(_extract_all_cohort_codes(option))
        if has_major and has_cohort:
            continue
        filtered_options.append(option)

    clean_options = filtered_options[:3]
    if len(clean_options) < 2:
        clean_options = list(_COMPARE_CLARIFY_OPTIONS)

    options_text = "\n".join(f"{i + 1}. {opt}" for i, opt in enumerate(clean_options))
    return f"{CLARIFY_SENTINEL}\n{clean_message}\n\n{options_text}"


# ─── Planner-Executor helpers (Phase 1 refactor) ─────────────────────────────


def execute_retrieval_plan(steps: list[dict[str, Any]]) -> list[tuple[str, str]]:
    """Execute a list of retrieval steps in parallel. No LLM involved.

    Each step is a dict with keys: query, collection, major_hint, cohort_hint, label.
    Returns [(label, result_string), ...] in the same order as input steps.

    Thread-safe: _rag_search has its own cache + reranker lock.
    """
    if not steps:
        return []

    results: list[tuple[str, str] | None] = [None] * len(steps)

    def _run(i: int, step: dict[str, Any]) -> None:
        result = _rag_search(
            query=step.get("query", ""),
            collection=step.get("collection", ""),
            resolved_cohort=step.get("cohort_hint"),
            resolved_major=step.get("major_hint"),
        )
        label = step.get("label") or step.get("collection", f"step_{i}")
        results[i] = (label, result)

    import contextvars

    worker_count = min(4, len(steps))
    with ThreadPoolExecutor(max_workers=worker_count) as pool:
        futures = [
            pool.submit(contextvars.copy_context().run, _run, i, step)
            for i, step in enumerate(steps)
        ]
        for f in futures:
            try:
                f.result(timeout=45)
            except Exception as exc:
                logger.error("[Executor] Step failed: %s", exc)

    return [r for r in results if r is not None]


# ─── Formatting helpers ───────────────────────────────────────────────────────


def _format_search_results(
    results: Any,
    collection: str,
    settings: Settings | None = None,
) -> str:
    if not results:
        return f"Khong tim thay thong tin phu hop trong {collection}."

    chunks: list[str] = []
    result_count = int(getattr(settings, "agent_search_result_count", 3) or 3)
    char_limit = int(getattr(settings, "agent_search_result_char_limit", 500) or 500)
    total_limit = int(getattr(settings, "agent_tool_result_limit", 0) or 0)

    for index, item in enumerate(results[:result_count], 1):
        content = ""
        source = ""
        metadata = {}

        if hasattr(item, "payload"):
            payload = getattr(item, "payload", {}) or {}
            content = str(payload.get("content") or payload.get("text") or "")
            source = str(payload.get("source") or payload.get("title") or "")
            metadata = payload
        elif isinstance(item, dict):
            metadata = item.get("metadata", {}) or {}
            content = str(item.get("text") or item.get("content") or "")
            source = str(
                item.get("source")
                or metadata.get("source")
                or metadata.get("title")
                or item.get("collection", "")
            )
        else:
            content = str(item)

        content = " ".join(content.split())

        # Include parent section context for broader understanding
        parent_ctx = str((metadata.get("parent_context") or "")).strip()
        if parent_ctx:
            parent_short = parent_ctx[:300] + "..." if len(parent_ctx) > 300 else parent_ctx
            parent_short = " ".join(parent_short.split())
            content = f"[Section] {parent_short}\n[Detail] {content}"

        if len(content) > char_limit:
            content = content[:char_limit].rstrip() + "..."

        if not content:
            continue

        # Inject major metadata into the source info so the LLM agent is aware of the program context
        meta_parts = []
        if metadata.get("major_code"):
            meta_parts.append(f"Ma nganh: {metadata['major_code']}")
        if metadata.get("major_name"):
            meta_parts.append(f"Nganh: {metadata['major_name']}")
        meta_str = f" ({', '.join(meta_parts)})" if meta_parts else ""

        chunk = f"[{index}] {content}"
        if source:
            chunk += f"\n    Nguon: {source}{meta_str}"
        # Score omitted — not useful for LLM synthesis and wastes tokens
        chunks.append(chunk)

    if not chunks:
        return f"Khong tim thay thong tin phu hop trong {collection}."
    formatted = "\n\n".join(chunks)
    if total_limit > 0 and len(formatted) > total_limit:
        return formatted[:total_limit].rstrip() + "..."
    return formatted


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

    all_results: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    for item in items:
        key = str(item.get("url") or item.get("id") or item.get("title") or "")
        if not key:
            key = str(len(all_results))
        if key in seen_keys:
            continue
        seen_keys.add(key)
        all_results.append(item)

    # Accumulate for UI diagnostic logging (per-request, thread-safe)
    _append_agent_docs(all_results)

    runtime = _get_runtime()
    web_count = int(getattr(runtime.settings, "tavily_web_result_count", 3) or 3)
    web_char_limit = int(getattr(runtime.settings, "tavily_web_content_char_limit", 1500) or 1500)

    chunks: list[str] = []
    for index, item in enumerate(all_results[:web_count], 1):
        title = str(item.get("title", "")).strip() or f"Ket qua {index}"
        content = " ".join(str(item.get("content", "")).split())
        if len(content) > web_char_limit:
            content = content[:web_char_limit].rstrip() + "..."
        url = str(item.get("url", "")).strip()
        chunks.append(f"[{index}] {title}\n{content}\nURL: {url}")

    if not chunks and answer:
        return answer
    if answer:
        return f"Tom tat Tavily: {answer}\n\n" + "\n\n".join(chunks)
    if chunks:
        return "\n\n".join(chunks)
    return "Khong tim thay thong tin tren web."


# ─── Utility helpers ──────────────────────────────────────────────────────────


def _extract_cohort(text: str) -> str | None:
    match = _COHORT_RE.search(text)
    return match.group(0).upper() if match else None


def _normalise_cohort_token(value: str) -> str | None:
    match = _COHORT_TOKEN_RE.match(value)
    return f"K{match.group(1)}" if match else None


def _extract_single_major_code(value: str) -> str | None:
    codes = extract_major_codes(value)
    return codes[0] if codes else None
