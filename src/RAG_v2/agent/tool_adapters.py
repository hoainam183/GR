from __future__ import annotations

import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar
from dataclasses import dataclass
from threading import Lock
from typing import Any

from config.settings import Settings
from query.signals import fold_vietnamese_text
from retrieval.metadata_filters import (
    enrich_major_references_for_query,
    extract_major_codes,
    strip_major_from_query_for_retrieval,
)

logger = logging.getLogger(__name__)

# ─── Personal Identifier stripping ──────────────────────────────────────────────
_STUDENT_ID_RE = re.compile(r"\b\d{8}\b")
_STUDENT_ID_PREFIX_RE = re.compile(
    r"(mã\s*sv|mssv|sinh\s*viên\s*mã?)\s*:?\s*\d+", re.IGNORECASE
)


def strip_personal_identifiers(query: str) -> str:
    """Xóa mã sinh viên và các identifier cá nhân khỏi retrieval query."""
    q = _STUDENT_ID_PREFIX_RE.sub("", query)
    q = _STUDENT_ID_RE.sub("", q)
    q = re.sub(r",\s*,", ",", q)
    q = re.sub(r"\s{2,}", " ", q).strip().strip(",").strip()
    return q


# ─── Collection name mapping ──────────────────────────────────────────────────
# Agent-facing collection names → real Qdrant collection names.

COLLECTION_MAP: dict[str, str] = {
    "quy_dinh": "quydinh",  # quy định học vụ, học bổng, kỷ luật, tốt nghiệp
    "chuong_trinh": "ctdt",  # chương trình đào tạo, môn học, tín chỉ
    "ke_hoach": "kehoach",  # lịch đăng ký, deadline, kế hoạch học kỳ
    "ho_tro_sv": "stsv",  # hỗ trợ sinh viên: biểu mẫu, giấy tờ, thuê nhà, tìm việc
}

# Exam schedules (lịch thi) are NOT a Qdrant collection — they live in a
# dedicated Mongo collection + ES index and are queried via structured filters.
# Steps with this collection are dispatched to _exam_schedule_search, bypassing
# the vector-search path entirely (and must NOT be added to COLLECTION_MAP).
EXAM_COLLECTION = "lich_thi"

# Subject code (Mã HP), e.g. "CH1012"; date token, e.g. "9/5/2026".
_SUBJECT_CODE_RE = re.compile(r"\b[A-Za-z]{2}\d{3,4}\b")
_DATE_TOKEN_RE = re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b")
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# Exam-query handles mined from free text (all matched against folded text where
# noted): cohort "K70[C]", the exam term (giữa/cuối kỳ), and "tháng N[/YYYY]".
_COHORT_RE = re.compile(r"\bK\d{2,3}[A-Za-z]?\b")
_GIUA_KY_RE = re.compile(r"giua\s*(?:hoc\s*)?k[yi]")
_CUOI_KY_RE = re.compile(r"cuoi\s*(?:hoc\s*)?k[yi]")
_MONTH_RE = re.compile(r"thang\s+(\d{1,2})(?:\s*/?\s*(\d{4}))?")

# ─── Simple RAG search cache ─────────────────────────────────────────────────
# In-memory FIFO cache keyed by (query, collection, top_k, cohort, major).
# Avoids redundant Qdrant + reranker calls for frequently repeated queries.
# Thread-safe: protected by _CACHE_LOCK.

_MAJOR_FILTERABLE_COLLECTIONS = frozenset({"chuong_trinh"})

_RAG_CACHE: dict[tuple, str] = {}
_RAG_CACHE_MAX = 256
_CACHE_LOCK = Lock()

# NOTE: rerank() serialisation now lives inside BGEReranker.rerank (instance-level
# self._lock), protecting every call path. The old module-level _RERANKER_LOCK was
# removed to avoid double-locking.

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


@dataclass
class _AdapterRuntime:
    settings: Settings
    bge_embedder: Any
    e5_embedder: Any
    searcher: Any
    reranker: Any | None
    tavily_tool: Any | None
    exam_es_store: Any | None = None


@dataclass(frozen=True)
class _RagSearchRequest:
    query: str
    collection: str
    qdrant_collection: str
    top_k: int
    raw_query: str
    retrieval_query: str
    cohort: str
    resolved_major: str | None


_RUNTIME: _AdapterRuntime | None = None
_RUNTIME_LOCK = Lock()

# ─── API key validation ───────────────────────────────────────────────────────


def _is_valid_api_key(key: str) -> bool:
    """Return True only when *key* looks like a real, configured API key.

    Rejects empty strings, whitespace-only strings, and well-known placeholder
    values that appear in .env.example files.  Uses prefix matching so that
    new placeholder variants (e.g. ``your-tavily-api-key-here``) are rejected
    without having to maintain an ever-growing exact-match list.
    """
    from tools.tavily_search import is_valid_tavily_api_key

    return is_valid_tavily_api_key(key)


def _build_exam_es_store(settings: Settings) -> Any | None:
    """Build the exam-schedule ES store from settings, or None when ES is down.

    The exam index is independent of the document index and not exposed by the
    RetrievalService, so it is constructed fresh here. A failed connection
    degrades gracefully: the tool reports that the store is unavailable rather
    than crashing the agent.
    """
    try:
        from retrieval.exam_schedule_store import ExamScheduleESStore

        return ExamScheduleESStore(
            host=settings.elasticsearch_host,
            port=settings.elasticsearch_port,
            index_name=getattr(
                settings, "exam_schedule_es_index", "exam_schedules"
            ),
        )
    except Exception:
        logger.warning(
            "Exam ES store unavailable for agent tool", exc_info=True
        )
        return None


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
        exam_es_store=_build_exam_es_store(settings),
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
    settings = getattr(retrieval_service, "settings", None) or Settings()
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
        exam_es_store=_build_exam_es_store(settings),
    )
    set_runtime(runtime)
    logger.info(
        "[ToolAdapters] Runtime injected from RetrievalService (shared models)"
    )


def _get_runtime() -> _AdapterRuntime:
    global _RUNTIME
    if _RUNTIME is not None:
        return _RUNTIME
    with _RUNTIME_LOCK:
        if _RUNTIME is None:
            _RUNTIME = _build_runtime()
    return _RUNTIME


# ─── Tool implementations ─────────────────────────────────────────────────────


def _build_rag_request(
    query: str,
    collection: str,
    top_k: int | None,
    resolved_cohort: str | None,
    resolved_major: str | None,
    runtime: _AdapterRuntime,
) -> _RagSearchRequest | str:
    if not query or not query.strip():
        return "[Loi: Query rong]"

    qdrant_collection = COLLECTION_MAP.get(collection)
    if qdrant_collection is None:
        return f"[Loi: Collection '{collection}' khong hop le]"

    effective_top_k = max(
        1, int(top_k if top_k is not None else runtime.settings.top_k)
    )
    raw_query = enrich_major_references_for_query(
        strip_personal_identifiers(query.strip())
    )
    major_codes = extract_major_codes(raw_query)
    effective_major = _effective_major_hint(resolved_major, major_codes)
    retrieval_query = _retrieval_query_for_collection(
        raw_query,
        collection,
        effective_major,
        major_codes,
    )
    cohort = (resolved_cohort or _extract_cohort(raw_query) or "").upper()
    return _RagSearchRequest(
        query=query,
        collection=collection,
        qdrant_collection=qdrant_collection,
        top_k=effective_top_k,
        raw_query=raw_query,
        retrieval_query=retrieval_query,
        cohort=cohort,
        resolved_major=effective_major,
    )


def _effective_major_hint(
    resolved_major: str | None,
    major_codes: list[str],
) -> str | None:
    if resolved_major:
        return resolved_major
    return major_codes[0] if len(major_codes) == 1 else None


def _retrieval_query_for_collection(
    raw_query: str,
    collection: str,
    resolved_major: str | None,
    major_codes: list[str],
) -> str:
    if (
        resolved_major or len(major_codes) <= 1
    ) and collection in _MAJOR_FILTERABLE_COLLECTIONS:
        return strip_major_from_query_for_retrieval(
            raw_query,
            resolved_major=resolved_major,
        )
    return raw_query


def _rag_cache_key(request: _RagSearchRequest) -> tuple:
    return (
        request.retrieval_query.lower(),
        request.collection,
        request.top_k,
        request.cohort,
        (request.resolved_major or "").upper(),
    )


def _search_rag_candidates(
    request: _RagSearchRequest,
    runtime: _AdapterRuntime,
) -> Any:
    bge_vec = runtime.bge_embedder.embed_query(request.retrieval_query)
    e5_vec = runtime.e5_embedder.embed_query(request.retrieval_query)
    return runtime.searcher.search(
        **_search_kwargs(request, runtime, bge_vec, e5_vec)
    )


def _search_kwargs(
    request: _RagSearchRequest,
    runtime: _AdapterRuntime,
    bge_vec: Any,
    e5_vec: Any,
) -> dict[str, Any]:
    raw_candidate_k = _raw_candidate_k(runtime.settings, request.top_k)
    kwargs: dict[str, Any] = {
        "query": request.raw_query,
        "bge_m3_query": bge_vec,
        "e5_query": e5_vec,
        "top_k": raw_candidate_k,
        "vector_top_k": runtime.settings.vector_top_k,
        "keyword_top_k": runtime.settings.keyword_top_k,
        "vector_pool_k": runtime.settings.vector_pool_k,
        "keyword_pool_k": runtime.settings.keyword_pool_k,
        "active_collections": [request.qdrant_collection],
    }
    if request.resolved_major:
        kwargs["resolved_major"] = request.resolved_major
    if request.cohort:
        kwargs["resolved_cohort"] = request.cohort
    return kwargs


def _raw_candidate_k(settings: Settings, top_k: int) -> int:
    raw_multiplier = max(
        float(getattr(settings, "raw_candidate_multiplier", 4.0)), 1.0
    )
    raw_min = max(int(getattr(settings, "raw_candidate_min", 20)), 1)
    return max(int(round(top_k * raw_multiplier)), raw_min)


def _rerank_or_trim_results(
    results: Any,
    request: _RagSearchRequest,
    runtime: _AdapterRuntime,
) -> Any:
    if runtime.reranker is None or _should_skip_rerank(request):
        return results[: request.top_k]

    reranked = runtime.reranker.rerank(
        query=request.retrieval_query,
        documents=results,
        top_k=request.top_k,
        **_reranker_kwargs(runtime.settings, request.top_k),
    )
    _log_top_reranked_results(reranked, request.qdrant_collection)
    return reranked


def _should_skip_rerank(request: _RagSearchRequest) -> bool:
    curriculum_kw_check = request.raw_query.lower()
    return request.collection == "chuong_trinh" and any(
        word in curriculum_kw_check
        for word in [
            "kỳ",
            "kì",
            "ky ",
            'ky"',
            "chẵn",
            "lẻ",
            "đăng ký",
            "dang ky",
        ]
    )


def _reranker_kwargs(settings: Settings, top_k: int) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    min_top_k = int(getattr(settings, "reranker_min_top_k", 0) or 0)
    if min_top_k > 0:
        kwargs["min_top_k"] = min(min_top_k, top_k)
    if getattr(settings, "reranker_score_threshold", None) is not None:
        kwargs["score_threshold"] = settings.reranker_score_threshold
    if getattr(settings, "reranker_table_score_threshold", None) is not None:
        kwargs["table_score_threshold"] = (
            settings.reranker_table_score_threshold
        )
    return kwargs


def _log_top_reranked_results(results: Any, qdrant_collection: str) -> None:
    if not logger.isEnabledFor(logging.DEBUG):
        return
    for index, doc in enumerate(results[:3]):
        meta = doc.get("metadata") or {}
        logger.debug(
            "[_rag_search] Reranked #%d: rerank=%.4f col=%s h2=%.80s",
            index,
            doc.get("rerank_score", 0.0),
            qdrant_collection,
            str(meta.get("section_h2", meta.get("title", "")))[:80],
        )


def _expand_parent_context_if_enabled(
    results: Any,
    request: _RagSearchRequest,
    settings: Settings,
) -> Any:
    if not getattr(settings, "parent_context_enabled", True):
        return results
    try:
        from retrieval.parent_context import get_parent_expander

        expander = get_parent_expander(
            qdrant_host=settings.qdrant_host,
            qdrant_port=settings.qdrant_port,
            max_parent_chars=getattr(settings, "parent_max_chars_agent", 500),
        )
        return expander.expand_with_parents(results, request.qdrant_collection)
    except Exception:
        return results


def _rag_search(
    query: str,
    collection: str,
    top_k: int | None = None,
    resolved_cohort: str | None = None,
    resolved_major: str | None = None,
) -> str:
    runtime = _get_runtime()
    request = _build_rag_request(
        query=query,
        collection=collection,
        top_k=top_k,
        resolved_cohort=resolved_cohort,
        resolved_major=resolved_major,
        runtime=runtime,
    )
    if isinstance(request, str):
        return request

    cache_key = _rag_cache_key(request)
    cached = _cache_get(cache_key)
    if cached is not None:
        logger.debug(
            "[Cache] Hit: collection=%s query='%s'",
            request.collection,
            request.retrieval_query[:50],
        )
        return cached

    results = _search_rag_candidates(request, runtime)
    results = _rerank_or_trim_results(results, request, runtime)
    results = _expand_parent_context_if_enabled(
        results, request, runtime.settings
    )
    _append_agent_docs(results)

    if not results:
        return "[Khong tim thay thong tin trong co so du lieu]"

    formatted = _format_search_results(
        results, request.collection, runtime.settings
    )
    if not formatted.startswith("[Loi"):
        _cache_set(cache_key, formatted)
    return formatted



def _web_search(query: str) -> str:
    if not query or not query.strip():
        return "[Loi: Query web rong]"

    runtime = _get_runtime()
    if runtime.tavily_tool is None:
        return "[Loi: Tavily chua duoc cau hinh API key]"

    # Honour the master switch so web fallback policy is consistent with the
    # classic RAG path (flows.py gates every Tavily call on this flag). Without
    # this the agent would call Tavily purely on the planner's needs_web, making
    # TAVILY_FALLBACK_ENABLED impossible to use as a single kill-switch.
    if not getattr(runtime.settings, "tavily_fallback_enabled", False):
        return "[Web fallback dang tat (TAVILY_FALLBACK_ENABLED=false)]"

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
        result_count=getattr(runtime.settings, "tavily_web_result_count", None),
        content_char_limit=getattr(
            runtime.settings, "tavily_web_content_char_limit", None
        ),
    )
    return _format_web_results(results)


def web_search_for_executor(query: str) -> str:
    """Public wrapper cho _web_search — dùng bởi react_agent._executor_node.

    Tách riêng để react_agent có thể import ở top-level (thay vì runtime import
    private function), đảm bảo encapsulation và dễ mock trong tests.

    Strip mã SV / identifier cá nhân trước khi gửi ra dịch vụ web bên thứ ba
    (Tavily) — tránh rò rỉ PII, nhất quán với nhánh RAG.
    """
    return _web_search(query=strip_personal_identifiers(query))


# ─── Exam-schedule (lịch thi) structured search ───────────────────────────────


def _to_es_date(value: str | None) -> str | None:
    """Coerce a date filter to ISO ``yyyy-MM-dd`` for the ES date field."""
    if not value:
        return None
    if _ISO_DATE_RE.match(value):
        return value
    from utils.vn_datetime import normalize_exam_date

    parsed, _ = normalize_exam_date(value)
    return parsed.strftime("%Y-%m-%d") if parsed else value


def _extract_date_range(folded: str) -> tuple[str | None, str | None]:
    """Resolve a relative range to ISO ``(from, to)``.

    Handles "tuần này", "tuần tới"/"tuần sau", and "tháng N[/YYYY]". Anchored on
    the real current date so "lịch thi tuần tới" filters the right week.
    """
    from datetime import date, timedelta

    today = date.today()
    if "tuan nay" in folded:
        start = today - timedelta(days=today.weekday())
        return start.isoformat(), (start + timedelta(days=6)).isoformat()
    if "tuan toi" in folded or "tuan sau" in folded:
        start = today - timedelta(days=today.weekday()) + timedelta(days=7)
        return start.isoformat(), (start + timedelta(days=6)).isoformat()
    month_match = _MONTH_RE.search(folded)
    if month_match:
        month = int(month_match.group(1))
        year = int(month_match.group(2)) if month_match.group(2) else today.year
        if 1 <= month <= 12:
            start = date(year, month, 1)
            next_month = date(year + month // 12, month % 12 + 1, 1)
            return (
                start.isoformat(),
                (next_month - timedelta(days=1)).isoformat(),
            )
    return None, None


def _extract_exam_filters(query: str) -> dict[str, Any]:
    """Mine structured exam filters from a free-text query.

    Returns only the keys present (subject_code, exam_type, exam_date or
    exam_date_from/to, subject_name). Cohort is handled by the caller from the
    raw user query so we never inject one the user did not actually type.
    """
    cleaned = strip_personal_identifiers(query or "")
    folded = fold_vietnamese_text(cleaned)
    filters: dict[str, Any] = {}

    code_match = _SUBJECT_CODE_RE.search(cleaned)
    if code_match:
        filters["subject_code"] = code_match.group(0).upper()

    # Exam term — "cuối" checked first so "giữa kỳ và cuối kỳ" leans final.
    if _CUOI_KY_RE.search(folded):
        filters["exam_type"] = "cuoi_ky"
    elif _GIUA_KY_RE.search(folded):
        filters["exam_type"] = "giua_ky"

    date_match = _DATE_TOKEN_RE.search(cleaned)
    if date_match:
        filters["exam_date"] = _to_es_date(date_match.group(0))
    else:
        date_from, date_to = _extract_date_range(folded)
        if date_from or date_to:
            filters["exam_date_from"] = date_from
            filters["exam_date_to"] = date_to

    # A literal Kxx in the query counts as a structural narrowing signal too —
    # skip the BM25 name fallback so a generic "lịch thi K70 cuối kì" can't be
    # excluded by the name clause. The cohort itself is applied by the caller.
    has_cohort_token = bool(_COHORT_RE.search(cleaned))
    if not filters.get("subject_code") and not has_cohort_token:
        # Fall back to BM25 over subject_name/search_text using the whole
        # (PII-stripped) question — the analyzer drops stopwords like "thi".
        filters["subject_name"] = cleaned or None
    return filters


def _format_exam_results(rows: list[dict[str, Any]]) -> str:
    """Render exam rows as one compact Vietnamese line per slot."""
    if not rows:
        return "[Khong tim thay lich thi phu hop]"

    lines: list[str] = []
    for index, row in enumerate(rows, 1):
        code = row.get("subject_code", "")
        name = row.get("subject_name", "")
        head = f"{code} — {name}" if name else code

        when_parts = [
            part
            for part in (row.get("weekday", ""), row.get("exam_date_str", ""))
            if part
        ]
        when = " ".join(when_parts)
        if row.get("exam_session"):
            session = row["exam_session"]
            if row.get("start_time"):
                session += f" ({row['start_time']})"
            when = f"{when}, {session}" if when else session

        segments = [f"[{index}] {head}"]
        if when:
            segments.append(when)
        if row.get("exam_room"):
            segments.append(f"Phòng {row['exam_room']}")
        if row.get("group"):
            segments.append(f"Nhóm {row['group']}")
        if row.get("exam_batch"):
            segments.append(f"Đợt {row['exam_batch']}")
        # "Ghi chú" thường liệt kê các ngành/CTĐT được thi học phần này — giữ
        # nguyên dạng raw để LLM tự suy luận khi user hỏi về ngành/chương trình.
        note = (row.get("note") or "").strip()
        if note:
            segments.append(f"Ghi chú: {note}")
        lines.append(" | ".join(segments))
    return "\n".join(lines)


def _exam_schedule_search(
    query: str = "",
    subject_code: str | None = None,
    subject_name: str | None = None,
    exam_date: str | None = None,
    exam_room: str | None = None,
    group: str | None = None,
    exam_type: str | None = None,
    top_k: int | None = None,
) -> str:
    """Structured lookup against the exam-schedule ES index (no vector search)."""
    runtime = _get_runtime()
    store = runtime.exam_es_store
    if store is None:
        return "[Loi: Kho du lieu lich thi chua san sang]"

    # Explicit filters from the planner win; otherwise mine them from the raw
    # query (subject code / exam term / date + BM25 name fallback). Cohort is
    # intentionally not accepted from the planner — it is sourced only from a
    # literal Kxx token in the user's query (see below) so profile/context
    # cannot silently narrow the search.
    explicit = {
        key: value
        for key, value in {
            "subject_code": subject_code,
            "subject_name": subject_name,
            "exam_date": _to_es_date(exam_date),
            "exam_room": exam_room,
            "group": group,
            "exam_type": exam_type,
        }.items()
        if value
    }
    filters = explicit or _extract_exam_filters(query)

    # Cohort filter only applies when the user literally writes Kxx in the
    # query — strip any inferred cohort and re-detect from the raw text.
    filters.pop("cohort", None)
    cohort_match = _COHORT_RE.search(query or "")
    if cohort_match:
        filters["cohort"] = cohort_match.group(0).upper()

    if not any(filters.values()):
        return "[Loi: Khong xac dinh duoc mon/ngay thi tu cau hoi]"

    # Guard: if the only filter is exam_type (e.g. "cuối kỳ") without any
    # subject, date, or cohort narrowing, the query is too broad for a
    # structured lookup — it would return arbitrary top-K rows.
    _narrowing_keys = {"subject_code", "subject_name", "exam_date",
                       "exam_date_from", "exam_date_to", "exam_room",
                       "group", "cohort"}
    if not any(filters.get(k) for k in _narrowing_keys):
        return (
            "[Khong du thong tin de tra cuu lich thi cu the. "
            "Vui long cho biet ten/ma mon hoc, ngay thi, hoac ma khoa (vd: K67).]"
        )

    limit = int(
        top_k
        if top_k is not None
        else getattr(runtime.settings, "exam_schedule_search_top_k", 20)
    )
    rows = store.search(limit=limit, **filters)

    # Flexible match: an exact subject_code that returned nothing (typo / wrong
    # code) → retry by subject name (BM25), keeping any term/cohort narrowing.
    if not rows and filters.get("subject_code"):
        cleaned = strip_personal_identifiers(query)
        if cleaned:
            rows = store.search(
                subject_name=cleaned,
                exam_type=filters.get("exam_type"),
                cohort=filters.get("cohort"),
                limit=limit,
            )

    _append_agent_docs(rows)
    return _format_exam_results(rows)


# ─── Planner-Executor helpers (Phase 1 refactor) ─────────────────────────────


def execute_retrieval_plan(
    steps: list[dict[str, Any]],
    top_k: int | None = None,
) -> list[tuple[str, str]]:
    """Execute a list of retrieval steps in parallel. No LLM involved.

    Each step is a dict with keys: query, collection, major_hint, cohort_hint, label.
    Returns [(label, result_string), ...] in the same order as input steps.

    Thread-safe: _rag_search has its own cache + reranker lock.
    """
    if not steps:
        return []

    results: list[tuple[str, str] | None] = [None] * len(steps)

    def _run(i: int, step: dict[str, Any]) -> None:
        if step.get("collection") == EXAM_COLLECTION:
            # Structured DB lookup — return all matching rows; do NOT cap by the
            # chat-level top_k (which is sized for vector retrieval). Cohort is
            # intentionally omitted: the exam tool re-derives it from the raw
            # user query so a planner-injected cohort_hint (often pulled from
            # the student's profile) cannot silently narrow the result set.
            result = _exam_schedule_search(
                query=step.get("query", ""),
                subject_code=step.get("subject_code"),
                exam_date=step.get("exam_date"),
                exam_type=step.get("exam_type"),
                top_k=None,
            )
        else:
            result = _rag_search(
                query=step.get("query", ""),
                collection=step.get("collection", ""),
                top_k=top_k,
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
    char_limit = int(
        getattr(settings, "agent_search_result_char_limit", 500) or 500
    )
    total_limit = int(getattr(settings, "agent_tool_result_limit", 0) or 0)
    seen_parent_ids: set[str] = (
        set()
    )  # dedup parent context across children sharing same parent

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

        # Include parent section context for broader understanding.
        # Dedup: only render parent text once even when multiple children share the same parent.
        parent_ctx = str((metadata.get("parent_context") or "")).strip()
        parent_id = str(metadata.get("parent_id") or "").strip()
        if parent_ctx and parent_id and parent_id in seen_parent_ids:
            parent_ctx = ""  # already rendered for a previous sibling
        if parent_ctx:
            if parent_id:
                seen_parent_ids.add(parent_id)
            parent_short = (
                parent_ctx[:300] + "..."
                if len(parent_ctx) > 300
                else parent_ctx
            )
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
        raw_answer = results.get("answer")
        answer = str(raw_answer).strip() if raw_answer is not None else ""
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

    settings = _formatting_settings()
    web_count = int(getattr(settings, "tavily_web_result_count", 5) or 5)
    web_char_limit = int(
        getattr(settings, "tavily_web_content_char_limit", 3000) or 3000
    )

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


def _formatting_settings() -> Settings:
    if _RUNTIME is not None:
        return _RUNTIME.settings
    return Settings()


def _extract_cohort(text: str) -> str | None:
    match = _COHORT_RE.search(text)
    return match.group(0).upper() if match else None


def _normalise_cohort_token(value: str) -> str | None:
    match = _COHORT_TOKEN_RE.match(value)
    return f"K{match.group(1)}" if match else None


def _extract_single_major_code(value: str) -> str | None:
    codes = extract_major_codes(value)
    return codes[0] if codes else None
