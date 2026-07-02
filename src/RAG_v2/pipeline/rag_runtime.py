"""RAG pipeline runtime construction: Settings->cfg, Tavily tool, prepared LLM bundle."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

from agent.react_agent import ReActAgent
from config.settings import Settings
from llm import BaseLLM
from llm.self_eval import SelfEvaluator
from query.reflection import QueryReflector


# ---------------------------------------------------------------------------
# Config — built from Settings (centralised Pydantic config)
# ---------------------------------------------------------------------------


def _settings_to_cfg(settings: Settings) -> Dict[str, Any]:
    """Convert a ``Settings`` instance to the legacy cfg dict expected by flows."""
    return {
        "collections": settings.collections,
        "find_all": settings.find_all,
        "qdrant_host": settings.qdrant_host,
        "qdrant_port": settings.qdrant_port,
        "es_host": settings.elasticsearch_host,
        "es_port": settings.elasticsearch_port,
        "top_k": settings.top_k,
        "vector_top_k": settings.vector_top_k,
        "keyword_top_k": settings.keyword_top_k,
        "vector_pool_k": settings.vector_pool_k,
        "keyword_pool_k": settings.keyword_pool_k,
        "raw_candidate_multiplier": settings.raw_candidate_multiplier,
        "raw_candidate_min": settings.raw_candidate_min,
        "vector_weight": settings.vector_weight,
        "keyword_weight": settings.keyword_weight,
        "context_doc_char_limit": settings.context_doc_char_limit,
        "context_total_char_budget": settings.context_total_char_budget,
        "context_list_total_char_budget": settings.context_list_total_char_budget,
        "reranker_top_k": settings.reranker_top_k,
        "reranker_min_top_k": settings.reranker_min_top_k,
        "reranker_score_threshold": settings.reranker_score_threshold,
        "reranker_table_score_threshold": settings.reranker_table_score_threshold,
        "model": settings.chat_model,
        "temperature": settings.chat_temperature,
        "max_tokens": settings.chat_max_tokens,
        "router_mode": settings.router_mode,
        "reflection_enabled": settings.reflection_enabled,
        "self_eval_enabled": settings.self_eval_enabled,
        "self_eval_min_top_score": settings.self_eval_min_top_score,
        "tavily_fallback_enabled": settings.tavily_fallback_enabled,
        "tavily_search_depth": settings.tavily_search_depth,
        "tavily_max_results": settings.tavily_max_results,
        "web_fallback_dynamic_collections": settings.web_fallback_dynamic_collections,
        "web_fallback_on_dynamic": settings.web_fallback_on_dynamic,
        "web_fallback_on_no_info": settings.web_fallback_on_no_info,
        "score_cliff_enabled": settings.score_cliff_enabled,
        "per_collection_norm_enabled": settings.per_collection_norm_enabled,
        "sibling_expansion_enabled": settings.sibling_expansion_enabled,
        "parent_context_enabled": settings.parent_context_enabled,
        "freshness_tavily_check_enabled": settings.freshness_tavily_check_enabled,
        "low_conf_pool_expand_enabled": settings.low_conf_pool_expand_enabled,
        "sibling_budget_ratio": settings.sibling_budget_ratio,
        "sibling_per_doc_limit": settings.sibling_per_doc_limit,
        "parent_max_chars": settings.parent_max_chars,
        "parent_max_chars_agent": settings.parent_max_chars_agent,
        "context_total_char_budget_with_expansion": (
            settings.context_total_char_budget_with_expansion
        ),
        # HyDE post-rerank fallback
        "hyde_enabled": settings.hyde_enabled,
        "hyde_min_results": settings.hyde_min_results,
        "hyde_confidence_threshold": settings.hyde_confidence_threshold,
    }


# ═══════════════════════════════════════════════════════════════════════════════
def _should_enable_self_evaluator(cfg: Dict[str, Any]) -> bool:
    """Return True when self-evaluation is explicitly enabled.

    Self-eval is intentionally NOT auto-enabled by ``tavily_fallback_enabled``.
    Post-gen Tavily has independent trigger paths (``no_info`` pattern matching,
    ``no_sources``) that work without an LLM-based quality judge, so forcing
    self-eval on every query just because Tavily is configured would add
    ~2–5 s latency per query unnecessarily.

    To use self-eval as a Tavily trigger, set ``self_eval_enabled=True``
    explicitly alongside ``tavily_fallback_enabled=True``.
    """
    return bool(cfg.get("self_eval_enabled", False))


def _build_tavily_tool(settings: Settings) -> Any | None:
    """Build the web-search client without rebuilding RetrievalService."""
    from tools.tavily_search import TavilySearchTool, is_valid_tavily_api_key

    api_key = settings.tavily_api_key or os.environ.get("TAVILY_API_KEY", "")
    if not is_valid_tavily_api_key(api_key):
        return None
    return TavilySearchTool(
        api_key=api_key,
        cache_maxsize=settings.tavily_cache_maxsize,
        cache_ttl_seconds=settings.tavily_cache_ttl_seconds,
    )


@dataclass(frozen=True)
class _PreparedLLMRuntime:
    """LLM-dependent pipeline components prepared before a hot swap."""

    cfg: Dict[str, Any]
    chat: BaseLLM
    self_evaluator: Optional[SelfEvaluator]
    reflector: Optional[QueryReflector]

    agent: Optional[ReActAgent]
    tavily_tool: Any | None
