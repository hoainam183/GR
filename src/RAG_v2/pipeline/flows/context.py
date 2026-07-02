"""Context formatting, budget resolution, and local/web context merge."""

from __future__ import annotations

import logging

from typing import Any, Dict, Generator, List, Optional, Set

from retrieval.metadata_filters import (
    MAJOR_CODE_TO_NAME,
)

from .common import (
    _cfg_bool,
    _cfg_int,
    _fold_vietnamese,
)
from .retrieval_helpers import _LIST_TOP_K_MULTIPLIER

logger = logging.getLogger(__name__)


# â”€â”€ Context budget â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
_DEFAULT_CONTEXT_DOC_CHAR_LIMIT = 1500  # chars per retrieved chunk
_DEFAULT_CONTEXT_TOTAL_CHAR_BUDGET = 8000  # total context chars sent to LLM


def _merge_local_and_web_context(local_context: str, web_context: str) -> str:
    """Combine local RAG context with supplemental live web context deterministically."""
    if not web_context:
        return local_context
    if not local_context:
        return (
            f"## web_live_context (Tavily / nguá»“n web chÃ­nh thá»©c)\n"
            f"{web_context}"
        )
    return (
        f"## Nguá»“n CÆ¡ Sá»Ÿ Dá»¯ Liá»‡u Ná»™i Bá»™ (Æ°u tiÃªn date_str khi cÃ³)\n"
        f"{local_context}\n\n---\n\n"
        f"## web_live_context (Tavily / nguá»“n web chÃ­nh thá»©c)\n"
        f"{web_context}\n\n"
        f"LÆ°u Ã½: Æ¯u tiÃªn Nguá»“n CÆ¡ Sá»Ÿ Dá»¯ Liá»‡u Ná»™i Bá»™ cho cÃ¡c cÃ¢u há»i vá» quy cháº¿, "
        f"chÆ°Æ¡ng trÃ¬nh Ä‘Ã o táº¡o vÃ  Ä‘iá»u kiá»‡n tá»‘t nghiá»‡p â€” Ä‘Ã¢y lÃ  nguá»“n chÃ­nh xÃ¡c "
        f"vÃ  cá»¥ thá»ƒ nháº¥t. Chá»‰ dÃ¹ng web_live_context khi nguá»“n ná»™i bá»™ khÃ´ng cÃ³ "
        f"thÃ´ng tin hoáº·c cáº§n xÃ¡c nháº­n dá»¯ liá»‡u thá»i gian thá»±c (lá»‹ch thi, thÃ´ng bÃ¡o má»›i)."
    )


def _format_context(
    documents: List[Dict[str, Any]],
    *,
    per_doc_char_limit: int = _DEFAULT_CONTEXT_DOC_CHAR_LIMIT,
    total_char_budget: int = _DEFAULT_CONTEXT_TOTAL_CHAR_BUDGET,
    sibling_per_doc_limit: int = 800,
    trace_out: Optional[Dict[str, Any]] = None,
) -> str:
    """Convert retrieved documents into a token-budgeted context string.

    Limits per-document and total context size to prevent context-length
    errors and keep LLM latency predictable regardless of chunk sizes.

    When sibling expansion is active, siblings (docs with _expansion_source)
    get a separate, lower per-doc limit to preserve budget for primary docs.
    """
    parts: List[str] = []
    used = 0
    docs_used = 0
    seen_parent_ids: Set[str] = (
        set()
    )  # C5: dedup parent context across children sharing same parent
    for i, doc in enumerate(documents, 1):
        meta = doc.get("metadata", {}) or {}
        title = (
            meta.get("title") or meta.get("source") or "TÃ i liá»‡u khÃ´ng rÃµ nguá»“n"
        )

        # Inject metadata into document header so the LLM is aware of the program/major context.
        # If storage metadata has mismatched code/name, prefer the canonical name by code
        # to avoid leaking contradictory labels (e.g. "Việt - Nhật [IT-E7]").
        meta_parts = []
        major_code = str(meta.get("major_code") or "").strip()
        major_name = str(meta.get("major_name") or "").strip()
        canonical_major_name = MAJOR_CODE_TO_NAME.get(major_code) if major_code else None
        if canonical_major_name and (
            not major_name
            or _fold_vietnamese(major_name) != _fold_vietnamese(canonical_major_name)
        ):
            major_name = canonical_major_name
        if major_code:
            meta_parts.append(f"MÃ£ ngÃ nh: {major_code}")
        if major_name:
            meta_parts.append(f"NgÃ nh: {major_name}")
        if meta.get("applicable_cohort"):
            meta_parts.append(f"KhÃ³a: {meta['applicable_cohort']}")
        # Posting date is kehoach-specific (freshness signal for notifications).
        if doc.get("collection") == "kehoach" and meta.get("date_str"):
            meta_parts.append(f"NgÃ y Ä‘Äƒng: {meta['date_str']}")
        # Expose a real source URL so the LLM can cite it as a Markdown link
        # [anchor text](URL). Only inject genuine http(s) URLs.
        url = str(meta.get("url") or "").strip()
        if url.startswith(("http://", "https://")):
            meta_parts.append(f"URL: {url}")
        meta_str = f" [{', '.join(meta_parts)}]" if meta_parts else ""

        text = str(doc.get("text", "") or "").strip()

        # C5: Prepend parent context for broader section context.
        # Dedup: only render parent text once even when multiple children share the same parent.
        parent_ctx = str((meta.get("parent_context") or "")).strip()
        parent_title = str(
            (meta.get("parent_title") or meta.get("parent_section_h2") or "")
        ).strip()
        parent_id = str(meta.get("parent_id") or "").strip()
        if parent_ctx and parent_id and parent_id in seen_parent_ids:
            parent_ctx = ""  # already rendered for a previous sibling
        if parent_ctx:
            if parent_id:
                seen_parent_ids.add(parent_id)
            parent_header = (
                f"[Ngá»¯ cáº£nh section: {parent_title}]"
                if parent_title
                else "[Ngá»¯ cáº£nh section]"
            )
            text = f"{parent_header}\n{parent_ctx}\n\n[Chi tiáº¿t]\n{text}"

        # Siblings get reduced per-doc limit (C2: 70/30 budget split)
        effective_limit = (
            sibling_per_doc_limit
            if doc.get("_expansion_source")
            else per_doc_char_limit
        )
        # When parent context is prepended, allow more chars per doc
        if parent_ctx:
            effective_limit = min(
                effective_limit + 1500, per_doc_char_limit + 1500
            )
        if len(text) > effective_limit:
            text = text[:effective_limit] + "\u2026"  # ellipsis
        chunk = f"--- VÄƒn báº£n: {title}{meta_str}\n{text}"
        separator_cost = 7 if parts else 0  # len("\n\n---\n\n")
        if used + len(chunk) + separator_cost > total_char_budget:
            break
        parts.append(chunk)
        docs_used += 1
        used += len(chunk) + separator_cost
    context = "\n\n---\n\n".join(parts)
    if trace_out is not None:
        trace_out["context_chars"] = len(context)
        trace_out["context_docs_used"] = docs_used
        trace_out["context_docs_dropped"] = max(0, len(documents) - docs_used)
        trace_out["context_doc_char_limit"] = per_doc_char_limit
        trace_out["context_total_char_budget"] = total_char_budget
    return context


def _resolve_context_budget(
    cfg: Dict[str, Any],
    *,
    top_k_value: int,
) -> tuple[int, int]:
    """Return (per_doc_limit, total_budget) for the current query."""
    base_top_k = _cfg_int(cfg, "top_k", 5)
    per_doc_limit = _cfg_int(
        cfg, "context_doc_char_limit", _DEFAULT_CONTEXT_DOC_CHAR_LIMIT
    )
    base_budget = _cfg_int(
        cfg, "context_total_char_budget", _DEFAULT_CONTEXT_TOTAL_CHAR_BUDGET
    )
    list_budget = _cfg_int(
        cfg,
        "context_list_total_char_budget",
        base_budget * _LIST_TOP_K_MULTIPLIER,
    )
    total_budget = list_budget if top_k_value > base_top_k else base_budget

    # C2: Expand budget when sibling expansion is active
    if _cfg_bool(cfg, "sibling_expansion_enabled", False):
        expanded_budget = _cfg_int(
            cfg, "context_total_char_budget_with_expansion", 16000
        )
        total_budget = max(total_budget, expanded_budget)

    return per_doc_limit, total_budget
