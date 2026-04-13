"""Pipeline Flows — chitchat and RAG flow definitions."""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime
from typing import Any, Dict, Generator, List, Optional

from embedding.base import BaseEmbedder
from llm.base import BaseLLM
from llm.prompts import build_rag_messages
from llm.self_eval import SelfEvaluator
from reranking.base import BaseReranker
from retrieval.collection_selector import CollectionSelector

logger = logging.getLogger(__name__)

_collection_selector = CollectionSelector()

# Personal-pronoun pattern: indicates that reflection failed to resolve context
_UNRESOLVED_PERSONAL_REF = re.compile(
    r"\b(c(?:ủa tôi|ủa mình)|ng(?:ành tôi|ành mình)|ch(?:ương trình tôi|ương trình mình)"
    r"|kh(?:óa tôi)|tôi đang|của tôi)\b",
    re.IGNORECASE,
)

# ── History budget ──────────────────────────────────────────────────────────────
_DEFAULT_HISTORY_LIMIT = 8
_HISTORY_MESSAGE_CHAR_LIMIT = 400  # chars per message before truncation
_HISTORY_TOTAL_CHAR_BUDGET = 2000  # total chars across all kept messages

# ── Context budget ─────────────────────────────────────────────────────────────
_DEFAULT_CONTEXT_DOC_CHAR_LIMIT = 1500  # chars per retrieved chunk
_DEFAULT_CONTEXT_TOTAL_CHAR_BUDGET = 8000  # total context chars sent to LLM

# ── Self-eval ──────────────────────────────────────────────────────────────────
_SELF_EVAL_SCORE_THRESHOLD = 0.72  # run self-eval only when top score < this
_SELF_EVAL_MAX_DOCS = 2
_SELF_EVAL_DOC_CHAR_LIMIT = 600
_SELF_EVAL_TOTAL_CHAR_BUDGET = 1800

# ── Context-length error markers (shared across providers) ─────────────────────
_CTX_ERROR_MARKERS = (
    "context length",
    "maximum context length",
    "too many tokens",
    "tokens to keep",
    "prompt is too long",
    "context_length_exceeded",
)


# ═══════════════════════════════════════════════════════════════════════════════
# Helper
# ═══════════════════════════════════════════════════════════════════════════════


def _elapsed_ms(start: float) -> float:
    """Return elapsed milliseconds rounded for compact logs/JSON."""
    return round((time.perf_counter() - start) * 1000, 2)


def _log_timings(flow_name: str, timings_ms: Dict[str, float]) -> None:
    """Log timing breakdown sorted by slowest stage first."""
    if not timings_ms:
        return
    ordered = sorted(
        timings_ms.items(), key=lambda item: item[1], reverse=True
    )
    summary = ", ".join(
        f"{stage}={duration:.1f}" for stage, duration in ordered
    )
    logger.info("%s timings (ms): %s", flow_name, summary)


def _format_context(
    documents: List[Dict[str, Any]],
    *,
    per_doc_char_limit: int = _DEFAULT_CONTEXT_DOC_CHAR_LIMIT,
    total_char_budget: int = _DEFAULT_CONTEXT_TOTAL_CHAR_BUDGET,
) -> str:
    """Convert retrieved documents into a token-budgeted context string.

    Limits per-document and total context size to prevent context-length
    errors and keep LLM latency predictable regardless of chunk sizes.
    """
    parts: List[str] = []
    used = 0
    for i, doc in enumerate(documents, 1):
        meta = doc.get("metadata", {})
        title = meta.get("title") or meta.get("source") or "Tài liệu không rõ nguồn"
        text = str(doc.get("text", "") or "").strip()
        if len(text) > per_doc_char_limit:
            text = text[:per_doc_char_limit] + "\u2026"  # ellipsis
        chunk = f"--- Văn bản: {title}\n{text}"
        separator_cost = 7 if parts else 0  # len("\n\n---\n\n")
        if used + len(chunk) + separator_cost > total_char_budget:
            break
        parts.append(chunk)
        used += len(chunk) + separator_cost
    return "\n\n---\n\n".join(parts)


def _trim_history(
    history: Optional[List[Dict[str, str]]],
    limit: int = _DEFAULT_HISTORY_LIMIT,
) -> List[Dict[str, str]]:
    """Keep recent history within message-count and character budgets.

    Truncates individual messages that are too long and stops adding
    older messages once the total character budget is exhausted. This
    prevents context-length errors that grow with conversation length.
    """
    if not history:
        return []

    recent = history[-limit:]
    normalised: List[Dict[str, str]] = []
    for msg in recent:
        role = str(msg.get("role", "")).strip()
        content = str(msg.get("content", "") or "").strip()
        if role not in {"user", "assistant"} or not content:
            continue
        if len(content) > _HISTORY_MESSAGE_CHAR_LIMIT:
            content = content[:_HISTORY_MESSAGE_CHAR_LIMIT] + "\u2026"
        normalised.append({"role": role, "content": content})

    if not normalised:
        return []

    # Apply total char budget from newest to oldest.
    kept_reversed: List[Dict[str, str]] = []
    used = 0
    for msg in reversed(normalised):
        msg_len = len(msg["content"])
        if used + msg_len > _HISTORY_TOTAL_CHAR_BUDGET and kept_reversed:
            break
        kept_reversed.append(msg)
        used += msg_len

    return list(reversed(kept_reversed))


def _is_context_length_error(exc: Exception) -> bool:
    """Detect provider errors caused by prompt/context length overflow."""
    message = str(exc).lower()
    return any(marker in message for marker in _CTX_ERROR_MARKERS)


def _try_direct_answer(question: str) -> Optional[str]:
    """Handle simple out-of-domain questions locally — no LLM or retrieval."""
    q = question.lower().strip()
    now = datetime.now()
    days_vi = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]

    if any(kw in q for kw in ("mấy giờ", "may gio", "bây giờ là mấy", "bay gio la may")):
        return f"Bây giờ là {now.strftime('%H:%M')} ngày {now.strftime('%d/%m/%Y')}."

    if any(kw in q for kw in ("hôm nay", "hom nay", "ngày mấy", "ngay may", "thứ mấy", "thu may")):
        day_name = days_vi[now.weekday()]
        return f"Hôm nay là {day_name}, ngày {now.strftime('%d/%m/%Y')}."

    return None


def _extract_session_profile_dict(
    history: Optional[List[Dict[str, str]]],
) -> Dict[str, str]:
    """Scan full conversation history and return a raw dict of user-stated facts.

    Keys: ``"nganh"``, ``"nam"``, ``"khoa"``, ``"gpa"`` (all optional).
    Returns empty dict when nothing useful is found.
    """
    if not history:
        return {}

    profile: Dict[str, str] = {}
    user_messages = [
        m.get("content", "") for m in history
        if m.get("role") == "user" and m.get("content")
    ]

    for text in user_messages:
        t = text.lower()
        if not profile.get("nganh"):
            m = re.search(r"(?:h\u1ecdc ng\u00e0nh|ng\u00e0nh|chuy\u00ean ng\u00e0nh)\s+([^\.,\n]{2,30})", t)
            if m:
                profile["nganh"] = m.group(1).strip()
        if not profile.get("nam"):
            m = re.search(r"sinh vi\u00ean n\u0103m\s*(\d)|n\u0103m\s*(\d)\b|n\u0103m th\u1ee9\s*(\d)", t)
            if m:
                profile["nam"] = next(g for g in m.groups() if g)
        if not profile.get("khoa"):
            m = re.search(r"\bk(\d{2,3})\b|kh\u00f3a\s*(\d{2,3})", t)
            if m:
                profile["khoa"] = next(g for g in m.groups() if g)
        if not profile.get("gpa"):
            m = re.search(r"\b(?:cpa|gpa)\s*(?:l\u00e0|=|:)?\s*(\d+[\.,]\d+)\b", t)
            if m:
                profile["gpa"] = m.group(1).replace(",", ".")

    return profile


def _extract_session_profile(history: Optional[List[Dict[str, str]]]) -> str:
    """Scan full conversation history for user-stated facts (major, year, GPA).

    Returns a compact note like:
        "Thông tin sinh viên: ngành CNTT, năm 3, CPA=2.4."
    or empty string when nothing useful is found.

    This allows the LLM to answer personal questions (\"tôi học ngành gì?\") even
    after the original turn has been trimmed from the context window.
    """
    profile = _extract_session_profile_dict(history)
    if not profile:
        return ""

    parts: List[str] = []
    if "nganh" in profile:
        parts.append(f"ng\u00e0nh {profile['nganh']}")
    if "nam" in profile:
        parts.append(f"n\u0103m {profile['nam']}")
    if "khoa" in profile:
        parts.append(f"K{profile['khoa']}")
    if "gpa" in profile:
        parts.append(f"CPA={profile['gpa']}")

    return "Th\u00f4ng tin sinh vi\u00ean: " + ", ".join(parts) + "."


def _build_profile_note_from_user_context(
    user_context: Optional[Dict[str, Any]],
) -> str:
    """Build a compact profile note from the authenticated user's profile dict.

    Returns a string like:
        "Sinh viên: Nguyễn Hoài Nam | Mã SV: 20204242 | Ngành: CNTT Việt Nhật | Khoá: K65"
    or empty string when user_context is None / empty.

    This is injected into the search query and context so that user-specific
    questions ("tôi học ngành gì?") resolve correctly even on the very first
    turn — without waiting for the LLM to extract profile facts from history.
    """
    if not user_context:
        return ""

    parts: List[str] = []
    if user_context.get("full_name"):
        parts.append(f"Sinh viên: {user_context['full_name']}")
    if user_context.get("student_id"):
        parts.append(f"Mã SV: {user_context['student_id']}")
    if user_context.get("major"):
        major_note = user_context["major"]
        if user_context.get("major_code"):
            major_note += f" [{user_context['major_code']}]"
        parts.append(f"Ngành: {major_note}")
    if user_context.get("cohort"):
        parts.append(f"Khoá: {user_context['cohort']}")

    return " | ".join(parts) if parts else ""


def _enrich_search_query(
    search_query: str,
    history: Optional[List[Dict[str, str]]],
) -> str:
    """Fallback enrichment: if reflection left personal pronouns unresolved,
    append the user's profile note so retrieval targets the right programme.

    This is a safety net for cases where the local reflection model (e.g.
    LM Studio / Qwen) failed to expand "của tôi" → tên ngành cụ thể.

    Example:
        search_query = "chương trình của tôi có tổng cộng bao nhiêu tín"
        → "chương trình của tôi có tổng cộng bao nhiêu tín [ngành Công nghệ
            thông tin Việt-Nhật]"
    """
    if not _UNRESOLVED_PERSONAL_REF.search(search_query):
        return search_query

    profile = _extract_session_profile(history)
    if not profile:
        return search_query

    # Extract just the key facts (strip the prefix "Thông tin sinh viên: " and trailing ".")
    facts = profile.removeprefix("Thông tin sinh viên: ").rstrip(".")
    enriched = f"{search_query} [{facts}]"
    logger.info(
        "Post-reflection enrichment: %r → %r",
        search_query[:60],
        enriched[:80],
    )
    return enriched


def _resolve_major_for_filter(
    user_context: Optional[Dict[str, Any]],
    history: Optional[List[Dict[str, str]]],
) -> Optional[str]:
    """Resolve the major string for metadata pre-filtering.

    Priority:
      1. Most recent major mentioned in conversation history.
      2. Authenticated user profile (``user_context['major']``).
      3. ``None`` — the extractor will try regex on the current query.

    The returned value may be a major code ('IT-E6') or a name string
    ('Công nghệ thông tin Việt - Nhật').  The filter extractor handles both.
    """
    # Priority 1: scan history for explicit major mention (most recent wins)
    profile = _extract_session_profile_dict(history)
    history_major = profile.get("nganh")
    if history_major:
        return history_major

    # Priority 2: use authenticated user profile — prefer code (exact) over name
    if user_context:
        if user_context.get("major_code"):
            return str(user_context["major_code"])
        if user_context.get("major"):
            return str(user_context["major"])

    return None


def _build_collection_scores(
    *,
    all_collections: Optional[List[str]],
    target_collections: Optional[List[str]],
    routing_result: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Build ranked query scores for all configured collections."""
    selected = target_collections or []

    candidates = [c for c in (all_collections or []) if c]
    if not candidates:
        candidates = [c for c in selected if c]

    if not candidates:
        return []

    if not routing_result:
        return [{"collection": col, "score": 0.0} for col in candidates]

    confidence_raw = routing_result.get("confidence", 0.0)
    try:
        confidence = float(confidence_raw)
    except (TypeError, ValueError):
        confidence = 0.0

    probabilities = routing_result.get("probabilities") or {}
    if not isinstance(probabilities, dict):
        probabilities = {}

    if routing_result.get("tier3_override"):
        # Tier-3 LLM override can change selected domains without updating the
        # classifier probability map. Use confidence for selected collections.
        probabilities = {
            col: confidence for col in selected if isinstance(col, str)
        }

    scores: List[Dict[str, Any]] = []
    for collection in candidates:
        # Non-selected collections default to 0 so ranking is explicit.
        default_score = confidence if collection in selected else 0.0
        score_raw = probabilities.get(collection, default_score)
        try:
            score = float(score_raw)
        except (TypeError, ValueError):
            score = default_score
        score = max(0.0, min(1.0, score))
        scores.append(
            {
                "collection": collection,
                "score": round(score, 4),
            }
        )

    scores.sort(key=lambda item: item["score"], reverse=True)
    return scores


# ═══════════════════════════════════════════════════════════════════════════════
# Chitchat Flow
# ═══════════════════════════════════════════════════════════════════════════════


def chitchat_flow(
    *,
    question: str,
    history: Optional[List[Dict[str, str]]],
    chat_model: BaseLLM,
) -> Dict[str, Any]:
    """Router → Chat Model → response (no retrieval).

    Args:
        question: The user message.
        history: Recent chat turns.
        chat_model: A :class:`~llm.base.BaseLLM` instance.

    Returns:
        Dict with ``answer``, ``sources``, ``intent``.
    """
    flow_t0 = time.perf_counter()
    timings_ms: Dict[str, float] = {}

    step_t0 = time.perf_counter()
    trimmed = _trim_history(history)
    timings_ms["trim_history"] = _elapsed_ms(step_t0)

    step_t0 = time.perf_counter()
    answer = chat_model.generate(
        query=question,
        history=trimmed,
        mode="chitchat",
    )
    timings_ms["generate"] = _elapsed_ms(step_t0)
    timings_ms["flow_total"] = _elapsed_ms(flow_t0)

    logger.info("chitchat_flow: generated %d chars", len(answer))
    _log_timings("chitchat_flow", timings_ms)

    return {
        "question": question,
        "answer": answer,
        "sources": [],
        "num_sources": 0,
        "intent": "chitchat",
        "target_collections": [],
        "reflected_question": question,
        "model_name": chat_model.model,
        "timings_ms": timings_ms,
    }


def chitchat_flow_stream(
    *,
    question: str,
    history: Optional[List[Dict[str, str]]],
    chat_model: BaseLLM,
) -> Generator[str, None, None]:
    """Streaming variant of :func:`chitchat_flow`."""
    trimmed = _trim_history(history)
    yield from chat_model.generate_stream(
        query=question, history=trimmed, mode="chitchat"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# RAG Flow
# ═══════════════════════════════════════════════════════════════════════════════


def rag_flow(
    *,
    question: str,
    history: Optional[List[Dict[str, str]]],
    reflector: Any | None,
    bge_embedder: BaseEmbedder,
    e5_embedder: BaseEmbedder,
    searcher: Any,
    reranker: BaseReranker,
    chat_model: BaseLLM,
    self_evaluator: Optional[SelfEvaluator],
    tavily_tool: Any | None,
    cfg: Dict[str, Any],
    routing_result: Optional[Dict[str, Any]] = None,
    user_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Full RAG flow: Reflect → Embed → Search → Rerank → Generate → SelfEval → (Tavily fallback).

    Args:
        question: Raw user question.
        history: Chat history.
        reflector: ``QueryReflector`` (or *None* to skip reflection).
        bge_embedder: BGE-M3 :class:`~embedding.base.BaseEmbedder`.
        e5_embedder: E5 :class:`~embedding.base.BaseEmbedder`.
        searcher: ``MultiCollectionSearch`` instance.
        reranker: :class:`~reranking.base.BaseReranker` instance.
        chat_model: :class:`~llm.base.BaseLLM` instance.
        self_evaluator: ``SelfEvaluator`` (or *None* to skip).
        tavily_tool: ``TavilySearchTool`` (or *None* to skip).
        cfg: Pipeline config dict with retrieval params.
        user_context: Authenticated user profile (major, cohort, student_id …).

    Returns:
        Dict with ``answer``, ``sources``, ``intent``, etc.
    """
    flow_t0 = time.perf_counter()
    timings_ms: Dict[str, float] = {}

    step_t0 = time.perf_counter()
    trimmed = _trim_history(history)
    timings_ms["trim_history"] = _elapsed_ms(step_t0)

    # 1. Reflection — rewrite query for better retrieval
    search_query = question
    reflection_prompt: Optional[str] = None
    if reflector is not None:
        reflection_t0 = time.perf_counter()
        try:
            result = reflector.reflect(question, chat_history=trimmed, user_context=user_context)
            search_query = result.get("rewritten", question)
            reflection_prompt = result.get("prompt")
            logger.info("Reflected query: %r", search_query[:80])
        except Exception:
            logger.warning(
                "Reflection failed, using original query", exc_info=True
            )
        timings_ms["reflection"] = _elapsed_ms(reflection_t0)

    # 1b. Post-reflection enrichment:
    #   Priority 1 — use authenticated user profile (always accurate, zero latency).
    #   Priority 2 — fallback regex scan of history if no user_context given.
    auth_profile_note = _build_profile_note_from_user_context(user_context)
    if auth_profile_note:
        # Prepend profile note as bracketed context for the search query so that
        # retrieval targets the right programme from the very first turn.
        if _UNRESOLVED_PERSONAL_REF.search(search_query):
            search_query = f"{search_query} [{auth_profile_note}]"
            logger.info("User-context enrichment applied: %r", search_query[:100])
    else:
        # Fallback: scan history for user-stated facts
        search_query = _enrich_search_query(search_query, history)

    # 2. Collection-aware routing (Phase 8 — Tier 2 multi-domain)
    target_collections: Optional[List[str]] = None
    routing_probabilities: Optional[Dict[str, Any]] = None
    if routing_result:
        routing_t0 = time.perf_counter()
        domain = routing_result.get("domain")
        domains = routing_result.get("domains") or ([domain] if domain else [])
        confidence = routing_result.get("confidence", 0.0)
        target_collections = _collection_selector.select(
            domain=domain,
            confidence=confidence,
            domains=domains,
        )
        routing_probabilities = routing_result.get("probabilities")
        logger.info(
            "Domains: %s (conf=%.3f) → searching collections: %s",
            domains,
            confidence,
            target_collections,
        )
        timings_ms["collection_routing"] = _elapsed_ms(routing_t0)

    collection_scores = _build_collection_scores(
        all_collections=cfg.get("collections"),
        target_collections=target_collections,
        routing_result=routing_result,
    )

    # 3. Embed
    embed_t0 = time.perf_counter()
    bge_vec = bge_embedder.embed_query(search_query)
    timings_ms["embed_bge"] = _elapsed_ms(embed_t0)

    embed_t0 = time.perf_counter()
    e5_vec = e5_embedder.embed_query(search_query)
    timings_ms["embed_e5"] = _elapsed_ms(embed_t0)

    # 4. Hybrid search with metadata pre-filtering
    # Resolve major from conversation history + user profile before searching.
    resolved_major = _resolve_major_for_filter(user_context, trimmed)

    search_trace: Dict[str, Any] = {}
    search_t0 = time.perf_counter()
    raw_results = searcher.search(
        query=search_query,
        bge_m3_query=bge_vec,
        e5_query=e5_vec,
        top_k=cfg.get("top_k", 5) * 4,
        vector_top_k=cfg.get("vector_top_k", 20),
        keyword_top_k=cfg.get("keyword_top_k", 20),
        vector_pool_k=cfg.get("vector_pool_k", 15),
        keyword_pool_k=cfg.get("keyword_pool_k", 15),
        active_collections=target_collections,
        resolved_major=resolved_major,
        trace_out=search_trace,
    )
    timings_ms["search"] = _elapsed_ms(search_t0)
    logger.info("Retrieved %d raw candidates", len(raw_results))

    # 5. Rerank
    rerank_t0 = time.perf_counter()
    reranked = reranker.rerank(
        query=search_query, documents=raw_results, top_k=cfg.get("top_k", 5)
    )
    timings_ms["rerank"] = _elapsed_ms(rerank_t0)
    logger.info("Reranked to %d documents", len(reranked))


    # 6. Format context — inject profile so user facts survive trimming.
    #    Priority 1: use authenticated user_context (precise, always present).
    #    Priority 2: fall back to regex scan of history.
    context_t0 = time.perf_counter()
    context = _format_context(reranked)
    profile_note = (
        auth_profile_note
        or _extract_session_profile(history)
    )
    full_context = f"{profile_note}\n\n---\n\n{context}" if profile_note else context
    timings_ms["format_context"] = _elapsed_ms(context_t0)

    # 7. Generate answer with context-length error recovery
    # Capture the prompt that will be sent to the LLM (for trace/debug).
    try:
        llm_messages = build_rag_messages(question, full_context, trimmed)
        llm_prompt_str: Optional[str] = "\n\n".join(
            f"[{m['role'].upper()}]\n{m['content']}" for m in llm_messages
        )
    except Exception:
        llm_prompt_str = None

    generate_t0 = time.perf_counter()
    recovered = False
    try:
        answer = chat_model.generate(
            query=question,
            context=full_context,
            history=trimmed,
            mode="rag",
        )
    except Exception as exc:
        if not _is_context_length_error(exc):
            raise
        logger.warning(
            "Context too long, retrying with reduced budget",
            exc_info=True,
        )
        reduced_context = _format_context(
            reranked[:2],
            per_doc_char_limit=600,
            total_char_budget=1500,
        )
        trimmed = _trim_history(history, limit=3)
        try:
            answer = chat_model.generate(
                query=question,
                context=reduced_context,
                history=trimmed,
                mode="rag",
            )
            recovered = True
        except Exception as retry_exc:
            if _is_context_length_error(retry_exc):
                raise RuntimeError(
                    "Ngữ cảnh hội thoại đang quá dài. "
                    "Vui lòng bắt đầu phiên mới hoặc hỏi ngắn gọn hơn."
                ) from retry_exc
            raise
    if recovered:
        timings_ms["context_recovery"] = 1.0
    timings_ms["generate"] = _elapsed_ms(generate_t0)

    # 8. Self-evaluation — only when retrieval confidence is low.
    # Saves 11-20s per query when retrieval already found a relevant chunk.
    top_score = 0.0
    if reranked:
        try:
            top_score = float(reranked[0].get("score", 0.0))
        except (TypeError, ValueError):
            top_score = 0.0
    run_self_eval = (
        self_evaluator is not None
        and top_score < cfg.get("self_eval_min_top_score", _SELF_EVAL_SCORE_THRESHOLD)
    )
    if run_self_eval:
        self_eval_t0 = time.perf_counter()
        try:
            eval_context = _format_context(
                reranked[:_SELF_EVAL_MAX_DOCS],
                per_doc_char_limit=_SELF_EVAL_DOC_CHAR_LIMIT,
                total_char_budget=_SELF_EVAL_TOTAL_CHAR_BUDGET,
            )
            eval_result = self_evaluator.evaluate(
                query=question, context=eval_context, response=answer
            )
            timings_ms["self_eval"] = _elapsed_ms(self_eval_t0)
            if not eval_result.get("pass", True):
                logger.info(
                    "Self-eval FAILED (%s), attempting Tavily fallback",
                    eval_result.get("reason", "")[:60],
                )
                answer, fallback_timings = _tavily_fallback(
                    question=question,
                    answer=answer,
                    tavily_tool=tavily_tool,
                    chat_model=chat_model,
                    history=trimmed,
                )
                timings_ms.update(fallback_timings)
        except Exception:
            timings_ms["self_eval"] = _elapsed_ms(self_eval_t0)
            logger.warning(
                "Self-evaluation error, keeping original answer", exc_info=True
            )
    elif self_evaluator is not None:
        timings_ms["self_eval_skipped"] = 1.0
        logger.debug(
            "Self-eval skipped: top_score=%.3f >= threshold=%.3f",
            top_score,
            cfg.get("self_eval_min_top_score", _SELF_EVAL_SCORE_THRESHOLD),
        )
    timings_ms["retrieval_total"] = round(
        timings_ms.get("embed_bge", 0.0)
        + timings_ms.get("embed_e5", 0.0)
        + timings_ms.get("search", 0.0)
        + timings_ms.get("rerank", 0.0)
        + timings_ms.get("format_context", 0.0),
        2,
    )
    timings_ms["flow_total"] = _elapsed_ms(flow_t0)
    _log_timings("rag_flow", timings_ms)

    return {
        "question": question,
        "answer": answer,
        "sources": reranked,
        "num_sources": len(reranked),
        "intent": "rag",
        "model_name": chat_model.model,
        "target_collections": target_collections,
        "collection_scores": collection_scores,
        "reflected_question": search_query,
        "timings_ms": timings_ms,
        # Extended trace fields
        "routing_probabilities": routing_probabilities,
        "reflection_prompt": reflection_prompt,
        "llm_prompt": llm_prompt_str,
        "applied_filters": search_trace.get("filters"),
        "collection_results": search_trace.get("collection_counts"),
    }


def rag_flow_stream(
    *,
    question: str,
    history: Optional[List[Dict[str, str]]],
    reflector: Any | None,
    bge_embedder: BaseEmbedder,
    e5_embedder: BaseEmbedder,
    searcher: Any,
    reranker: BaseReranker,
    chat_model: BaseLLM,
    cfg: Dict[str, Any],
    routing_result: Optional[Dict[str, Any]] = None,
    user_context: Optional[Dict[str, Any]] = None,
    timings_ms_out: Optional[Dict[str, float]] = None,
) -> tuple[Generator[str, None, None], List[Dict[str, Any]]]:
    """Streaming RAG flow — retrieval runs first, then generation is streamed.

    Returns:
        A tuple of (text_chunk_generator, reranked_sources).
    """
    flow_t0 = time.perf_counter()
    timings_ms = timings_ms_out if timings_ms_out is not None else {}

    step_t0 = time.perf_counter()
    trimmed = _trim_history(history)
    timings_ms["trim_history"] = _elapsed_ms(step_t0)

    # Reflection
    search_query = question
    if reflector is not None:
        reflection_t0 = time.perf_counter()
        try:
            result = reflector.reflect(question, chat_history=trimmed, user_context=user_context)
            search_query = result.get("rewritten", question)
        except Exception:
            logger.warning(
                "Reflection failed, using original query", exc_info=True
            )
        timings_ms["reflection"] = _elapsed_ms(reflection_t0)

    # Post-reflection enrichment:
    #   Priority 1 — authenticated user profile.
    #   Priority 2 — fallback regex scan of history.
    auth_profile_note = _build_profile_note_from_user_context(user_context)
    if auth_profile_note:
        if _UNRESOLVED_PERSONAL_REF.search(search_query):
            search_query = f"{search_query} [{auth_profile_note}]"
            logger.info("User-context enrichment applied: %r", search_query[:100])
    else:
        search_query = _enrich_search_query(search_query, history)

    # Collection-aware routing (Phase 8 — Tier 2 multi-domain)
    target_collections: Optional[List[str]] = None
    if routing_result:
        routing_t0 = time.perf_counter()
        domain = routing_result.get("domain")
        domains = routing_result.get("domains") or ([domain] if domain else [])
        confidence = routing_result.get("confidence", 0.0)
        target_collections = _collection_selector.select(
            domain=domain,
            confidence=confidence,
            domains=domains,
        )
        timings_ms["collection_routing"] = _elapsed_ms(routing_t0)

    # Embed → Search → Rerank
    embed_t0 = time.perf_counter()
    bge_vec = bge_embedder.embed_query(search_query)
    timings_ms["embed_bge"] = _elapsed_ms(embed_t0)

    embed_t0 = time.perf_counter()
    e5_vec = e5_embedder.embed_query(search_query)
    timings_ms["embed_e5"] = _elapsed_ms(embed_t0)

    # Resolve major from conversation history + user profile before searching.
    resolved_major = _resolve_major_for_filter(user_context, trimmed)

    search_t0 = time.perf_counter()
    raw_results = searcher.search(
        query=search_query,
        bge_m3_query=bge_vec,
        e5_query=e5_vec,
        top_k=cfg.get("top_k", 5) * 4,
        vector_top_k=cfg.get("vector_top_k", 20),
        keyword_top_k=cfg.get("keyword_top_k", 20),
        vector_pool_k=cfg.get("vector_pool_k", 15),
        keyword_pool_k=cfg.get("keyword_pool_k", 15),
        active_collections=target_collections,
        resolved_major=resolved_major,
    )
    timings_ms["search"] = _elapsed_ms(search_t0)

    rerank_t0 = time.perf_counter()
    reranked = reranker.rerank(
        query=search_query, documents=raw_results, top_k=cfg.get("top_k", 5)
    )
    timings_ms["rerank"] = _elapsed_ms(rerank_t0)

    context_t0 = time.perf_counter()
    context = _format_context(reranked)
    profile_note = auth_profile_note or _extract_session_profile(history)
    full_context = f"{profile_note}\n\n---\n\n{context}" if profile_note else context
    timings_ms["format_context"] = _elapsed_ms(context_t0)
    timings_ms["retrieval_total"] = round(
        timings_ms.get("embed_bge", 0.0)
        + timings_ms.get("embed_e5", 0.0)
        + timings_ms.get("search", 0.0)
        + timings_ms.get("rerank", 0.0)
        + timings_ms.get("format_context", 0.0),
        2,
    )

    generate_stream = chat_model.generate_stream(
        query=question, context=full_context, history=trimmed, mode="rag"
    )
    def _timed_stream() -> Generator[str, None, None]:
        stream_t0 = time.perf_counter()
        first_token_ms: Optional[float] = None
        generated_chars = 0

        for chunk in generate_stream:
            if first_token_ms is None:
                first_token_ms = _elapsed_ms(stream_t0)
            generated_chars += len(chunk)
            yield chunk

        timings_ms["stream_first_token"] = round(first_token_ms or 0.0, 2)
        timings_ms["stream_generate"] = _elapsed_ms(stream_t0)
        timings_ms["flow_total"] = _elapsed_ms(flow_t0)
        logger.info("rag_flow_stream: streamed %d chars", generated_chars)
        _log_timings("rag_flow_stream", timings_ms)

    return _timed_stream(), reranked


# ═══════════════════════════════════════════════════════════════════════════════
# Tavily Fallback
# ═══════════════════════════════════════════════════════════════════════════════


def _tavily_fallback(
    *,
    question: str,
    answer: str,
    tavily_tool: Any | None,
    chat_model: BaseLLM,
    history: List[Dict[str, str]],
) -> tuple[str, Dict[str, float]]:
    """Use Tavily web search to re-generate the answer when self-eval fails."""
    fallback_t0 = time.perf_counter()
    timings_ms: Dict[str, float] = {}

    if tavily_tool is None:
        logger.info("No Tavily tool configured, returning original answer")
        timings_ms["tavily_total"] = _elapsed_ms(fallback_t0)
        return answer, timings_ms

    try:
        search_t0 = time.perf_counter()
        search_result = tavily_tool.search(question)
        timings_ms["tavily_search"] = _elapsed_ms(search_t0)

        web_context = search_result.get("context", "")
        if not web_context:
            timings_ms["tavily_total"] = _elapsed_ms(fallback_t0)
            return answer, timings_ms

        regenerate_t0 = time.perf_counter()
        new_answer = chat_model.generate(
            query=question,
            context=web_context,
            history=history,
            mode="rag",
        )
        timings_ms["tavily_generate"] = _elapsed_ms(regenerate_t0)
        timings_ms["tavily_total"] = _elapsed_ms(fallback_t0)
        logger.info("Tavily fallback generated %d chars", len(new_answer))
        return new_answer, timings_ms
    except Exception:
        logger.warning(
            "Tavily fallback failed, returning original answer", exc_info=True
        )
        timings_ms["tavily_total"] = _elapsed_ms(fallback_t0)
        return answer, timings_ms
