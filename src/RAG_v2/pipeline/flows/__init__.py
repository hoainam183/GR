"""Pipeline flows package (re-exports the historical pipeline.flows API)."""

from __future__ import annotations

from .url_sanitize import (
    _MD_LINK_RE,
    _RAW_URL_RE,
    _NATURAL_ANCHORS,
    _MAX_ANCHOR_WORDS,
    _fix_markdown_link_spaces,
    _shorten_long_anchors,
    _wrap_raw_urls,
    _sanitize_answer_urls,
    _strip_raw_urls,
    _raw_url_hold_index,
    _StreamUrlSanitizer,
)
from .common import (
    _elapsed_ms,
    _log_timings,
    _safe_float,
    _cfg_bool,
    _cfg_str_list,
    _cfg_int,
    _cfg_float,
    _fold_vietnamese,
    _is_date_within_days,
    _CTX_ERROR_MARKERS,
    _is_context_length_error,
    _dedup_text_values,
)
from .history import (
    _DEFAULT_HISTORY_LIMIT,
    _HISTORY_MESSAGE_CHAR_LIMIT,
    _HISTORY_TOTAL_CHAR_BUDGET,
    _trim_history,
)
from .title_match import (
    _KEHOACH_LINK_HEADER,
    _TITLE_MENTION_MIN_BIGRAM_OVERLAP,
    _TITLE_MENTION_MIN_TOKENS,
    _MATCH_NORMALIZE_RE,
    _normalize_for_match,
    _bigrams,
    _title_mentioned,
)
from .profile import (
    _EXPLICIT_MAJOR_CODE_RE,
    _PROFILE_DEPENDENT_QUERY_RE,
    _extract_session_profile_dict,
    _extract_session_profile,
    _should_prepend_profile_note,
    _build_resolved_profile_note,
    _profile_note_for_generation,
)
from .rerank_scoring import (
    _CLIFF_MIN_GAP_BY_COLLECTION,
    _CLIFF_MIN_GAP_DEFAULT,
    _CLIFF_MIN_KEEP_PER_COLL,
    _CLIFF_MIN_KEEP_TOTAL,
    _apply_score_cliff_per_collection,
    _build_rerank_trace,
    _update_rerank_trace_after_fallback,
    _best_explicit_rerank_score,
    _is_web_document,
    _best_local_evidence_score,
    _has_strong_local_evidence,
)
from .retrieval_helpers import (
    _LIST_QUERY_RE,
    _LIST_TOP_K_MULTIPLIER,
    _LIST_TOP_K_MAX,
    _resolve_top_k,
    _should_strip_major_for_retrieval,
    _resolve_candidate_pool,
    _reranker_min_top_k,
    _reranker_kwargs,
    _expand_parent_context_post_rerank,
    _expand_with_siblings_pre_rerank,
    _dedup_retrieval_candidates,
    _merge_search_trace,
    _order_with_siblings,
    _build_collection_scores,
)
from .context import (
    _DEFAULT_CONTEXT_DOC_CHAR_LIMIT,
    _DEFAULT_CONTEXT_TOTAL_CHAR_BUDGET,
    _format_context,
    _resolve_context_budget,
    _merge_local_and_web_context,
)
from .web_fallback import (
    _WEB_FALLBACK_DEFAULT_DYNAMIC_COLLECTIONS,
    _WEB_FALLBACK_NO_INFO_PATTERNS,
    _GENERIC_POLICY_EVIDENCE_PHRASES,
    _WEB_FALLBACK_DYNAMIC_QUERY_RE,
    _answer_has_no_info_signal,
    _selected_collections,
    _is_dynamic_web_query,
    _routing_top_domain,
    _routing_probability_scores,
    _has_non_kehoach_policy_lock_signal,
    _should_lock_kehoach_route,
    _build_web_search_query,
    _build_pre_generation_web_decision,
    _build_answer_quality_gate,
    _has_local_exact_policy_evidence,
)
from .cache_policy import (
    _should_cache_final_answer,
    _should_bypass_query_cache,
    _build_cache_profile,
)
from .hyde import (
    _should_trigger_hyde,
    _hyde_fallback_post_rerank,
)
from .tavily import (
    _tavily_results_to_docs,
    _extract_query_year,
    _tavily_search_context,
    _tavily_fallback_result,
)
from .coordinators import (
    logger,
    _collection_selector,
    _SELF_EVAL_SCORE_THRESHOLD,
    _SELF_EVAL_MAX_DOCS,
    _SELF_EVAL_DOC_CHAR_LIMIT,
    _SELF_EVAL_TOTAL_CHAR_BUDGET,
    chitchat_flow,
    chitchat_flow_stream,
    rag_flow,
    _chunk_cached_answer,
    rag_flow_stream,
)
