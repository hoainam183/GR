"""RAG v2 Pipeline — orchestrates routing, retrieval, reranking, and generation."""

from __future__ import annotations

import logging
import os
import sys
import time
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from types import SimpleNamespace
from typing import Any, Dict, Generator, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from models.mongo_logger import MongoLogger

# Ensure project root is on sys.path so sibling packages resolve correctly
PROJECT_ROOT = Path(__file__).resolve().parent.parent  # …/RAG_v2
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

from query.complexity_router import ComplexityRouter
from agent.react_agent import ReActAgent
from config.settings import Settings
from llm import BaseLLM, create_llm
from llm.self_eval import SelfEvaluator
from query.decomposer import QueryDecomposer
from query.prompts import DOMAIN_CLASSIFICATION_PROMPT
from query.reflection import QueryReflector
from query.router import QueryRouter
from query.training_data import RAG_LABELS
from utils.tracing import RequestTrace

# Confidence below this threshold triggers the Tier-3 LLM domain fallback.
_LLM_FALLBACK_THRESHOLD: float = 0.55
_VALID_DOMAINS = set(RAG_LABELS)

# If the leading domain's probability margin over the 2nd domain exceeds this
# value, Tier-3 is skipped even when absolute confidence < _LLM_FALLBACK_THRESHOLD.
# Rationale: a dominant single domain (e.g. kehoach=0.531, ctdt=0.180, margin=0.351)
# doesn't need an expensive LLM call to disambiguate.
_TIER3_DOMINANT_DOMAIN_MARGIN: float = 0.25


def _should_trigger_tier3(routing: Dict[str, Any]) -> bool:
    """Return True when the Tier-3 LLM domain fallback should run.

    Skips when one domain is already clearly dominant (probability margin over
    the second-best domain exceeds ``_TIER3_DOMINANT_DOMAIN_MARGIN``), saving
    ~12 s per query that would previously trigger an unnecessary LLM call.

    Example: kehoach=0.531, ctdt=0.180 → margin=0.351 > 0.25 → skip Tier-3.
    """
    # NOTE: distinguish "no confidence reported" (None) from a genuine low score.
    # `routing.get("confidence") or 1.0` would turn both None and 0.0 into 1.0,
    # silently disabling Tier-3 exactly when it is most needed (e.g. the LLM
    # router returns confidence=None). Only skip on a real high-confidence score.
    confidence = routing.get("confidence")
    if confidence is not None and confidence >= _LLM_FALLBACK_THRESHOLD:
        return False

    probs: Dict[str, float] = routing.get("probabilities") or {}
    if len(probs) >= 2:
        sorted_vals = sorted(probs.values(), reverse=True)
        margin = sorted_vals[0] - sorted_vals[1]
        if margin >= _TIER3_DOMINANT_DOMAIN_MARGIN:
            logger.debug(
                "Skipping Tier-3: domain margin=%.3f ≥ threshold=%.3f "
                "(top domain is clearly dominant)",
                margin,
                _TIER3_DOMINANT_DOMAIN_MARGIN,
            )
            return False

    return True


from .flows import (
    _format_context,
    chitchat_flow,
    chitchat_flow_stream,
    rag_flow,
    rag_flow_stream,
)

logger = logging.getLogger(__name__)

# Route cache avoids repeat classifier calls.
_ROUTE_CACHE_TTL_SEC = 45.0
_ROUTE_CACHE_MAX_SIZE = 256


def _build_cache_key(
    question: str,
    history: "Optional[List[Dict[str, str]]]",
) -> str:
    """Compact cache key from question + last 2 history turns."""
    q = question.strip().lower()
    if not history:
        return q
    recent = history[-2:]
    parts = [
        f"{m.get('role','')}:{str(m.get('content',''))[:120]}" for m in recent
    ]
    return f"{q}||{'|'.join(parts)}"


def _elapsed_ms(start: float) -> float:
    """Return elapsed milliseconds rounded for compact logs/JSON."""
    return round((time.perf_counter() - start) * 1000, 2)


def _chunk_for_stream(text: str, size: int = 24) -> Generator[str, None, None]:
    """Split a finished answer into small pieces for animated delivery.

    Used for answers computed synchronously (e.g. the agent path) so the UI
    animates them in instead of dumping the whole block at once. Splits on
    spaces so markdown tokens are not torn mid-word; newlines inside tokens
    survive. Runs of multiple spaces collapse to a single space in the deltas.
    """
    if not text:
        return
    buf: List[str] = []
    length = 0
    for word in text.split(" "):
        buf.append(word)
        length += len(word) + 1
        if length >= size:
            yield " ".join(buf) + " "
            buf, length = [], 0
    if buf:
        yield " ".join(buf)


def _merge_timings(*timings: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge timing dictionaries while preserving insertion order."""
    merged: Dict[str, Any] = {}
    for timing in timings:
        if timing:
            merged.update(timing)
    return merged


def _log_timings(label: str, timings_ms: Dict[str, Any]) -> None:
    """Log timing breakdown sorted by slowest stage first."""
    if not timings_ms:
        return
    numeric_timings = {
        stage: duration
        for stage, duration in timings_ms.items()
        if isinstance(duration, (int, float))
    }
    if not numeric_timings:
        return
    ordered = sorted(
        numeric_timings.items(), key=lambda item: item[1], reverse=True
    )
    summary = ", ".join(
        f"{stage}={duration:.1f}" for stage, duration in ordered
    )
    logger.info("%s timings (ms): %s", label, summary)


# ---------------------------------------------------------------------------
# Config — built from Settings (centralised Pydantic config)
# ---------------------------------------------------------------------------


def _settings_to_cfg(settings: Settings) -> Dict[str, Any]:
    """Convert a ``Settings`` instance to the legacy cfg dict expected by flows."""
    return {
        "collections": settings.collections,
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
    decomposer: Optional[QueryDecomposer]
    agent: Optional[ReActAgent]
    tavily_tool: Any | None


class RAGPipeline:
    """End-to-end RAG v2 pipeline.

    Steps (for RAG intent):
      1. Embed query with BGE-M3 and E5.
      2. MultiCollectionSearch across all configured collections.
      3. BGEReranker to re-score top candidates.
      4. ChatModel generates the final answer grounded in retrieved context.

    Steps (for chitchat intent):
      1. ChatModel generates a friendly response directly (no retrieval).

    Parameters:
        api_key: Google API key. Falls back to ``GOOGLE_API_KEY`` env var.
        config: Override any value in the module-level CONFIG dict.
        env_path: Path to a ``.env`` file to load before init.
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        api_key: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        env_path: Optional[str] = None,
        mongo_logger: Optional[MongoLogger] = None,
        llm_cache: Optional[Any] = None,
    ) -> None:
        if env_path:
            load_dotenv(dotenv_path=env_path)
        else:
            load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

        if settings is None:
            settings = Settings()
        # Allow callers who still pass api_key to override settings
        if api_key:
            settings.google_api_key = api_key
        base_cfg = _settings_to_cfg(settings)
        cfg = {**base_cfg, **(config or {})}

        logger.info("Initialising RAG v2 Pipeline …")

        # --- Unified retrieval service (embedders + searcher + reranker + tavily) ---
        from retrieval.service import RetrievalService

        self._retrieval_service = RetrievalService.from_settings(settings)

        # Convenient aliases — these are references into the shared service.
        self._bge = self._retrieval_service.bge_embedder
        self._e5 = self._retrieval_service.e5_embedder
        self._searcher = self._retrieval_service.searcher
        self._reranker = self._retrieval_service.reranker
        self._tavily = self._retrieval_service.tavily_tool

        if self._reranker is None:
            logger.warning(
                "Reranker unavailable; using raw hybrid search results."
            )

        # Query reflector (LLM-based rewrite)
        self._reflector: Optional[QueryReflector] = None
        if cfg.get("reflection_enabled", True):
            try:
                self._reflector = QueryReflector(settings=settings)
                logger.info("Query reflector loaded.")
            except Exception:
                logger.warning(
                    "Failed to load QueryReflector, skipping reflection",
                    exc_info=True,
                )

        # Query decomposer (multi-domain decomposition — same provider as reflector)
        try:
            self._decomposer = QueryDecomposer(settings=settings)
            logger.info("Query decomposer loaded.")
        except Exception:
            self._decomposer = None
            logger.warning(
                "Failed to load QueryDecomposer, decomposition disabled",
                exc_info=True,
            )

        # Query router (zero-cost local classifier)
        self._router = QueryRouter(
            mode=cfg.get("router_mode", "classifier"), embedder=self._bge
        )

        # Chat model via factory
        self._chat: BaseLLM = create_llm(settings)

        # Self evaluator (reuses same LLM instance — no extra API client)
        self._self_eval: Optional[SelfEvaluator] = None
        if _should_enable_self_evaluator(cfg):
            self._self_eval = SelfEvaluator(llm=self._chat)
            if cfg.get("tavily_fallback_enabled", False) and not cfg.get(
                "self_eval_enabled", False
            ):
                logger.info("Self evaluator loaded for Tavily fallback.")
            else:
                logger.info("Self evaluator loaded.")

        self._cfg = cfg
        self._mongo_logger = mongo_logger
        self._llm_cache = llm_cache
        self._llm_runtime_lock = RLock()
        self._route_cache: OrderedDict[str, tuple[float, Dict[str, Any]]] = (
            OrderedDict()
        )

        # Inject pipeline's shared retrieval stack into agent tool adapters.
        # This eliminates the ~17 s cold-start that occurs when the agent
        # tools lazily build their own embedders / searcher / reranker.
        from agent.tool_adapters import inject_from_retrieval_service

        inject_from_retrieval_service(self._retrieval_service)

        # Phase 2: Retrieval Quality & Data Intelligence
        from retrieval.validity_filter import ValidityFilter
        from retrieval.reference_resolver import ReferenceResolver

        self._validity_filter = ValidityFilter()
        self._reference_resolver = ReferenceResolver(self._retrieval_service)

        # Week 3 integration: smart router for RAG v2 vs LangGraph agent.
        self.complexity_router = ComplexityRouter()
        self.agent = ReActAgent(settings) if settings.agent_enabled else None
        logger.info(
            "Agent mode: %s",
            "enabled (LangGraph)" if self.agent else "disabled",
        )

        logger.info("RAG v2 Pipeline ready.")

    @property
    def retrieval_service(self) -> Any:
        """The shared, already-loaded retrieval stack (embedders + searcher + reranker).

        Exposed read-only so request handlers (e.g. ``/retrieval/search``) reuse
        the singleton instead of building a second ``RetrievalService`` — which
        would reload BGE-M3, E5 and the reranker per request (OOM / multi-second lag).
        """
        return self._retrieval_service

    # ------------------------------------------------------------------
    # Runtime LLM reload
    # ------------------------------------------------------------------

    def _llm_runtime_snapshot(self) -> _PreparedLLMRuntime:
        """Capture one consistent set of hot-swappable LLM components."""
        with self._llm_runtime_lock:
            return _PreparedLLMRuntime(
                cfg=dict(self._cfg),
                chat=self._chat,
                self_evaluator=self._self_eval,
                reflector=self._reflector,
                decomposer=self._decomposer,
                agent=self.agent,
                tavily_tool=self._tavily,
            )

    def prepare_llm_config_reload(
        self, settings: Settings
    ) -> _PreparedLLMRuntime:
        """Build replacement LLM clients before persistent config is committed."""
        cfg = _settings_to_cfg(settings)
        chat = create_llm(settings)
        self_evaluator = (
            SelfEvaluator(llm=chat)
            if _should_enable_self_evaluator(cfg)
            else None
        )
        reflector = (
            QueryReflector(settings=settings)
            if cfg.get("reflection_enabled", True)
            else None
        )
        decomposer = QueryDecomposer(settings=settings)
        agent = ReActAgent(settings) if settings.agent_enabled else None
        tavily_tool = _build_tavily_tool(settings)
        return _PreparedLLMRuntime(
            cfg=cfg,
            chat=chat,
            self_evaluator=self_evaluator,
            reflector=reflector,
            decomposer=decomposer,
            agent=agent,
            tavily_tool=tavily_tool,
        )

    def commit_llm_config_reload(
        self,
        settings: Settings,
        prepared: _PreparedLLMRuntime,
    ) -> Dict[str, str]:
        """Hot-swap prepared LLM clients and clear LLM-dependent caches."""
        with self._llm_runtime_lock:
            self._cfg = dict(prepared.cfg)
            self._chat = prepared.chat
            self._self_eval = prepared.self_evaluator
            self._reflector = prepared.reflector
            self._decomposer = prepared.decomposer
            self.agent = prepared.agent
            self._tavily = prepared.tavily_tool
            self._retrieval_service.settings = settings
            self._retrieval_service.tavily_tool = prepared.tavily_tool
            self._route_cache.clear()

        from agent.tool_adapters import inject_from_retrieval_service

        inject_from_retrieval_service(self._retrieval_service)
        rebuilt = {
            "chat_llm": settings.chat_model,
            "reflector": (
                settings.reflection_model if prepared.reflector else "disabled"
            ),
            "decomposer": (
                settings.reflection_model if prepared.decomposer else "disabled"
            ),
            "agent": settings.agent_model if prepared.agent else "disabled",
            "tavily": "reloaded" if prepared.tavily_tool else "disabled",
            "caches": "cleared",
        }
        if prepared.self_evaluator is not None:
            rebuilt["self_evaluator"] = "rebuilt"
        logger.info("LLM config reloaded: %s", rebuilt)
        return rebuilt

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    def _route_with_cache(
        self,
        question: str,
        history: Optional[List[Dict[str, str]]],
    ) -> Dict[str, Any]:
        """Route with a short-lived cache to avoid repeat classifier calls."""
        import time as _time

        now = _time.time()
        key = _build_cache_key(question, history)
        cached = self._route_cache.get(key)
        if cached is not None:
            ts, payload = cached
            if now - ts <= _ROUTE_CACHE_TTL_SEC:
                self._route_cache.move_to_end(key)
                logger.debug("Route cache hit: %r", question[:60])
                return dict(payload)
            del self._route_cache[key]
        routed = self._router.route(question, chat_history=history)
        # Tier-3 LLM domain fallback runs *before* caching, so a cache hit reuses
        # the enriched routing instead of re-invoking the ~12 s LLM call on every
        # repeat of a low-confidence query.
        if routed.get("intent", "rag") == "rag" and _should_trigger_tier3(routed):
            routed = self._llm_domain_classify(question, history, routed)
        self._route_cache[key] = (now, dict(routed))
        self._route_cache.move_to_end(key)
        while len(self._route_cache) > _ROUTE_CACHE_MAX_SIZE:
            self._route_cache.popitem(last=False)
        return routed

    def _reroute_reflected(
        self,
        reflected_query: str,
        prior_routing: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Re-route the *reflected* (standalone) query for domain selection.

        The pipeline-level route runs on the raw query plus verbatim history,
        which lets a topic-heavy conversation bleed into domain selection — a
        prior ctdt-heavy chat can push a scholarship query to ctdt. The
        reflector has already resolved any legitimate follow-up context into a
        standalone query, so routing it *without* history is bleed-free and
        authoritative for the domain decision.

        Intent stays ``"rag"`` (already branched upstream); only domain /
        domains / confidence / probabilities are replaced. Tier-3 LLM fallback
        now judges the standalone reflected query when confidence is low.

        Called as a callback from ``rag_flow`` / ``rag_flow_stream`` after
        reflection, so it never reorders the existing pipeline.
        """
        prior = dict(prior_routing or {})
        if not reflected_query:
            return prior
        try:
            rr = self._router.route(reflected_query)  # chat_history=None → no bleed
        except Exception:
            logger.warning(
                "Reflected-query route failed; keeping pipeline routing",
                exc_info=True,
            )
            return prior
        # If the standalone query no longer looks like RAG, keep the upstream
        # decision — we are already committed to the RAG flow.
        if rr.get("intent") != "rag":
            return prior
        domains = rr.get("domains") or ([rr["domain"]] if rr.get("domain") else [])
        merged = {
            **prior,
            "domain": rr.get("domain"),
            "domains": domains,
            "confidence": rr.get("confidence", 0.0),
            "probabilities": rr.get("probabilities", {}),
        }
        merged.pop("tier3_override", None)
        if _should_trigger_tier3(merged):
            merged = self._llm_domain_classify(reflected_query, None, merged)
        logger.info(
            "Reflected-query reroute: %r → domains=%s conf=%.3f",
            reflected_query[:80],
            merged.get("domains"),
            merged.get("confidence") or 0.0,
        )
        return merged

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def _run_reflection(
        self,
        question: str,
        history: Optional[List[Dict[str, str]]],
        user_context: Optional[Dict[str, Any]],
        runtime: _PreparedLLMRuntime,
    ) -> tuple:
        """Run reflection and return (reflected_question, ref_result, reflection_ms).

        Returns:
            reflected_question: The rewritten query (or original if no reflector).
            ref_result: Full dict from reflector.reflect() (None if skipped/failed).
            reflection_ms: Elapsed time in ms (None if no reflector).
        """
        reflected_question = question
        ref_result: Optional[Dict[str, Any]] = None
        reflection_ms: Optional[float] = None
        reflector = runtime.reflector
        if reflector is not None:
            reflect_t0 = time.perf_counter()
            try:
                trimmed = history[-8:] if history else []
                ref_result = reflector.reflect(
                    question,
                    chat_history=trimmed,
                    user_context=user_context,
                    user_profile=user_context,
                )
                rewritten = (
                    str(ref_result.get("rewritten") or "").strip()
                    if isinstance(ref_result, dict)
                    else ""
                )
                if rewritten and rewritten != question:
                    reflected_question = rewritten
            except Exception as exc:
                logger.warning("Reflection failed (%s), using original", exc)
                ref_result = None
            reflection_ms = _elapsed_ms(reflect_t0)
        return reflected_question, ref_result, reflection_ms

    def query(
        self,
        question: str,
        history: Optional[List[Dict[str, str]]] = None,
        top_k: Optional[int] = None,
        session_id: Optional[str] = None,
        user_context: Optional[Dict[str, Any]] = None,
        *,
        pre_ref_result: Optional[Dict[str, Any]] = None,
        pre_reflection_ms: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Process a user question end-to-end (non-streaming).

        Args:
            question: Raw user question.
            history: Previous chat turns as list of ``{"role", "content"}`` dicts.
            top_k: Override default number of retrieved documents.

        Returns:
            Dict with keys:
            - ``question`` — original question
            - ``answer`` — generated answer text
            - ``sources`` — list of retrieved+reranked source dicts
            - ``num_sources`` — number of sources used
            - ``intent`` — routing decision (``"rag"`` | ``"chitchat"``)
            - ``model_name`` — chat model name
            - ``request_trace`` — structured timing summary (``RequestTrace.summary()``)
        """
        runtime = self._llm_runtime_snapshot()
        effective_top_k = top_k or runtime.cfg["top_k"]
        pipeline_t0 = time.perf_counter()
        pipeline_timings: Dict[str, float] = {}

        # ── RequestTrace — structured observability carrier ──────────────────
        trace = RequestTrace(query=question)
        trace.set_metadata("session_id", session_id or "")
        trace.set_metadata("top_k", effective_top_k)

        # Auto-load history from MongoDB if session exists and no history given
        if session_id and not history and self._mongo_logger:
            with trace.stage("history_load"):
                history = self._mongo_logger.get_history(session_id)
            pipeline_timings["history_load"] = trace.stages.get(
                "history_load", 0.0
            )

        # 1. Route the query (context-aware — Tier 1, cached)
        with trace.stage("routing"):
            routing = self._route_with_cache(question, history)
        pipeline_timings["routing"] = trace.stages.get("routing", 0.0)
        intent = routing.get("intent", "rag")
        trace.set_metadata("intent", intent)
        logger.info("Routing decision: intent=%s", intent)

        # Tier-3 LLM domain fallback already ran inside _route_with_cache (so its
        # result is cached and not recomputed on every repeat).

        if intent == "chitchat":
            with trace.stage("chitchat_flow"):
                result = chitchat_flow(
                    question=question,
                    history=history,
                    chat_model=runtime.chat,
                )
            timings_ms = _merge_timings(
                pipeline_timings, result.get("timings_ms")
            )
            timings_ms["pipeline_total"] = _elapsed_ms(pipeline_t0)
            result["timings_ms"] = timings_ms
            trace.record_stage("pipeline_total", timings_ms["pipeline_total"])
            trace.set_metadata("flow", "chitchat")
            trace.log_summary("query(chitchat)")
            result["request_trace"] = trace.summary()
            result["correlation_id"] = trace.correlation_id

            # Chitchat turns are intentionally NOT logged to MongoDB to avoid
            # noise in history and unnecessary storage cost.
            return result

        # 2. RAG flow with reflection, self-eval, and Tavily fallback
        flow_cfg = {**runtime.cfg, "top_k": effective_top_k}
        with trace.stage("rag_flow"):
            result = rag_flow(
                question=question,
                history=history,
                reflector=runtime.reflector,
                bge_embedder=self._bge,
                e5_embedder=self._e5,
                searcher=self._searcher,
                reranker=self._reranker,
                chat_model=runtime.chat,
                self_evaluator=runtime.self_evaluator,
                tavily_tool=runtime.tavily_tool,
                cfg=flow_cfg,
                routing_result=routing,
                user_context=user_context,
                validity_filter=self._validity_filter,
                reference_resolver=self._reference_resolver,
                llm_cache=self._llm_cache,
                reroute_reflected=self._reroute_reflected,
                pre_ref_result=pre_ref_result,
                pre_reflection_ms=pre_reflection_ms,
            )
        timings_ms = _merge_timings(pipeline_timings, result.get("timings_ms"))
        timings_ms["pipeline_total"] = _elapsed_ms(pipeline_t0)
        result["timings_ms"] = timings_ms

        # Sync flow-level timings into the trace
        for stage, ms in timings_ms.items():
            if isinstance(ms, (int, float)):
                trace.record_stage(stage, ms)
        trace.set_metadata("flow", "rag")
        trace.set_metadata(
            "model", str(getattr(runtime.chat, "model", "unknown"))
        )
        trace.set_metadata("domain", routing.get("domain", ""))
        trace.log_summary("query(rag)")

        result["request_trace"] = trace.summary()
        result["correlation_id"] = trace.correlation_id

        # Log to MongoDB
        if session_id and self._mongo_logger:
            latency_ms = int((time.perf_counter() - pipeline_t0) * 1000)
            turn_id = self._mongo_logger.log_turn(
                session_id=session_id,
                question=question,
                result=result,
                reflected_question=result.get("reflected_question"),
                latency_ms=latency_ms,
                timings_ms=timings_ms,
            )
            result["turn_id"] = turn_id

        return result

    def query_agent(
        self,
        question: str,
        history: Optional[List[Dict[str, str]]] = None,
        top_k: Optional[int] = None,
        session_id: Optional[str] = None,
        user_context: Optional[Dict[str, Any]] = None,
        *,
        route_label: str = "complex",
        require_agent: bool = False,
        complexity_subtype: Optional[str] = None,
        pre_reflected: Optional[str] = None,
        pre_reflection_prompt: Optional[str] = None,
        pre_reflection_ms: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Force execution through the agent path.

        When ``require_agent`` is False, failures gracefully fall back to
        classic RAG v2 so requests still complete.

        Args:
            complexity_subtype: Passed to ``agent.run()`` to choose planner
                path shape ("comparison", "multi_source", "general").
            pre_reflected: If provided, skip internal reflection and use this
                as the reflected query (already computed upstream).
            pre_reflection_prompt: The reflection prompt from upstream.
            pre_reflection_ms: The reflection timing from upstream.
        """
        agent_t0 = time.perf_counter()
        runtime = self._llm_runtime_snapshot()
        agent = runtime.agent
        effective_top_k = top_k or runtime.cfg["top_k"]
        reflected_question = question
        reflection_prompt: Optional[str] = None
        reflection_ms: Optional[float] = None

        if complexity_subtype is None:
            try:
                inferred = self.complexity_router.route(question)
                if inferred.get("tier") == "complex":
                    complexity_subtype = inferred.get("complex_subtype") or "general"
            except Exception:
                logger.debug("Failed to infer agent complexity subtype", exc_info=True)

        def _fallback_result(
            agent_error: str, tool_payload: Optional[Dict[str, Any]] = None
        ) -> Dict[str, Any]:
            result = self.query(
                question=question,
                history=history,
                top_k=effective_top_k,
                session_id=session_id,
                user_context=user_context,
            )
            result["mode"] = "rag_v2_fallback"
            result["route"] = route_label
            result["agent_error"] = agent_error

            tool_info = tool_payload or {}
            result["tools_used"] = list(tool_info.get("tools_used", []))
            result["tool_calls"] = list(tool_info.get("tool_calls", []))
            result["iterations"] = int(tool_info.get("iterations", 0) or 0)

            result["agent_trace"] = {
                "query": reflected_question,
                "original_query": question,
                "reflected_question": reflected_question,
                "reflection_prompt": reflection_prompt,
                "session_id": session_id or "",
                "route": route_label,
                "iterations": int(tool_info.get("iterations", 0) or 0),
                "tool_calls": list(tool_info.get("tool_calls", [])),
                "tool_names_sequence": list(tool_info.get("tools_used", [])),
                "final_answer_length": 0,
                "error": agent_error,
                "latency_ms": _elapsed_ms(agent_t0),
            }

            existing_timings = (
                result.get("timings_ms")
                if isinstance(result.get("timings_ms"), dict)
                else None
            )
            result["timings_ms"] = _merge_timings(
                existing_timings,
                {
                    "agent_attempt_total": _elapsed_ms(agent_t0),
                    **(
                        {"reflection": reflection_ms}
                        if reflection_ms is not None
                        else {}
                    ),
                },
            )
            return result

        if agent is None:
            if require_agent:
                raise RuntimeError(
                    "Agent is required for this endpoint but is disabled"
                )
            logger.warning("Agent unavailable, falling back to RAG v2")
            return _fallback_result("Agent is disabled")

        # Use pre-computed reflection if available (from query_v3/query_stream)
        if pre_reflected is not None:
            reflected_question = pre_reflected
            reflection_prompt = pre_reflection_prompt
            reflection_ms = pre_reflection_ms
            logger.info(
                "[query_agent] Using pre-reflected: %r",
                reflected_question[:100],
            )
        else:
            reflector = getattr(runtime, "reflector", None)
            if reflector is not None:
                reflect_t0 = time.perf_counter()
                try:
                    trimmed_for_reflect = history[-8:] if history else []
                    ref_result = reflector.reflect(
                        question,
                        chat_history=trimmed_for_reflect,
                        user_context=user_context,
                        user_profile=user_context,
                    )
                    reflection_prompt = (
                        ref_result.get("prompt") if isinstance(ref_result, dict) else None
                    )
                    rewritten = (
                        str(ref_result.get("rewritten") or "").strip()
                        if isinstance(ref_result, dict)
                        else ""
                    )
                    if rewritten and rewritten != question:
                        reflected_question = rewritten
                        logger.info(
                            "[query_agent] Reflected: %r -> %r",
                            question[:60],
                            reflected_question[:100],
                        )
                except Exception as ref_exc:
                    logger.warning(
                        "[query_agent] Reflection failed (%s), using original",
                        ref_exc,
                    )
                reflection_ms = _elapsed_ms(reflect_t0)

        from agent.tool_adapters import init_agent_docs, get_agent_docs

        init_agent_docs()  # Tạo context riêng cho request này (thread-safe)

        try:
            state = agent.run(
                reflected_question,
                session_id=session_id or "",
                history=history,
                complexity_subtype=complexity_subtype,
                user_context=user_context,
                top_k=effective_top_k,
            )
        except Exception as exc:
            logger.warning(
                "Agent execution crashed (%s), falling back to RAG v2",
                exc,
                exc_info=True,
            )
            return _fallback_result(str(exc))

        agent_trace = state.to_log_dict()
        agent_trace["latency_ms"] = _elapsed_ms(agent_t0)
        agent_trace["original_query"] = question
        agent_trace["reflected_question"] = reflected_question
        agent_trace["reflection_prompt"] = reflection_prompt
        tool_calls = [tr.to_dict() for tr in state.tool_results]

        if (
            hasattr(self, "_mongo_logger")
            and self._mongo_logger
            and hasattr(self._mongo_logger, "log_agent_trace")
        ):
            try:
                self._mongo_logger.log_agent_trace(
                    session_id or "",
                    agent_trace,
                )
            except Exception:
                logger.warning("Failed to persist agent trace", exc_info=True)

        if state.error:
            logger.warning(
                "Agent failed (%s), falling back to RAG v2",
                state.error,
            )
            return _fallback_result(
                state.error,
                {
                    "tools_used": list(state.tool_call_history),
                    "tool_calls": tool_calls,
                    "iterations": state.iteration,
                },
            )

        agent_latency_ms = _elapsed_ms(agent_t0)
        timings_ms = {
            "agent_total": agent_latency_ms,
            "pipeline_total": agent_latency_ms,
        }
        if reflection_ms is not None:
            timings_ms["reflection"] = reflection_ms
        return {
            "question": question,
            "reflected_question": reflected_question,
            "reflection_prompt": reflection_prompt,
            "answer": state.final_answer or "",
            "mode": "agent",
            "route": route_label,
            "intent": route_label,
            "model_name": str(getattr(agent, "model_name", "agent")),
            "tools_used": list(state.tool_call_history),
            "tool_calls": tool_calls,
            "iterations": state.iteration,
            "agent_trace": agent_trace,
            "sources": get_agent_docs(),
            "timings_ms": timings_ms,
        }

    def query_v3(
        self,
        question: str,
        history: Optional[List[Dict[str, str]]] = None,
        top_k: Optional[int] = None,
        session_id: Optional[str] = None,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Smart entrypoint for Week 3 integration.

        Routing:
            - chitchat      → lightweight local handler
            - simple        → classic RAG v2 pipeline (query)
            - complex       → Planner-Executor agent when enabled (fallback to RAG)

        Falls back to RAG v2 when agent is unavailable or fails.
        """
        runtime = self._llm_runtime_snapshot()

        # Step 1: Reflection FIRST — so routing sees the expanded query
        reflected_question, ref_result, reflection_ms = self._run_reflection(
            question, history, user_context, runtime,
        )

        # Step 2: Route on REFLECTED query
        route_result = self.complexity_router.route(reflected_question)
        route = route_result["tier"]
        subtype = route_result.get("complex_subtype", "")
        logger.info(
            "[query_v3] Reflected: %r → route=%s",
            reflected_question[:80],
            route,
        )

        if route == "chitchat":
            return {
                "question": question,
                "answer": self._handle_chitchat(question),
                "mode": "chitchat",
                "route": "chitchat",
                "route_reason": route_result.get("reason", ""),
                "tools_used": [],
                "tool_calls": [],
                "iterations": 0,
                "agent_trace": None,
            }

        if route == "simple" or runtime.agent is None:
            result = self.query(
                question=question,
                history=history,
                top_k=top_k,
                session_id=session_id,
                user_context=user_context,
                pre_ref_result=ref_result,
                pre_reflection_ms=reflection_ms,
            )
            result["mode"] = "rag_v2"
            result["route"] = route
            result.setdefault("tools_used", [])
            result.setdefault("tool_calls", [])
            result.setdefault("iterations", 0)
            result.setdefault("agent_trace", None)
            return result

        reflection_prompt = (
            ref_result.get("prompt") if isinstance(ref_result, dict) else None
        )
        return self.query_agent(
            question=question,
            history=history,
            top_k=top_k,
            session_id=session_id,
            user_context=user_context,
            route_label="complex",
            require_agent=False,
            complexity_subtype=subtype,
            pre_reflected=reflected_question,
            pre_reflection_prompt=reflection_prompt,
            pre_reflection_ms=reflection_ms,
        )

    # ------------------------------------------------------------------
    # Decomposed multi-domain RAG
    # ------------------------------------------------------------------

    def _query_decomposed(
        self,
        question: str,
        domain_subqueries: List[Dict[str, str]],
        history: Optional[List[Dict[str, str]]] = None,
        top_k: Optional[int] = None,
        session_id: Optional[str] = None,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Run RAG with per-domain sub-queries and merged context.

        Calls ``rag_flow`` passing ``domain_subqueries`` so each sub-query is
        directed to its target collection.  The reflector, reranker, and LLM
        generation steps use the original question for coherence.
        """
        runtime = self._llm_runtime_snapshot()
        pipeline_t0 = time.perf_counter()
        effective_top_k = top_k or runtime.cfg["top_k"]
        # Expand top_k proportionally when we have multiple sub-queries so
        # each collection contributes enough candidates to the merged pool.
        expanded_top_k = min(effective_top_k * len(domain_subqueries), 12)

        # Collect multi-domain routing: union of all targeted collections
        target_cols = list(
            dict.fromkeys(
                sq["collection"]
                for sq in domain_subqueries
                if sq.get("collection")
            )
        )
        routing_result: Dict[str, Any] = {
            "intent": "rag",
            "domain": target_cols[0] if target_cols else None,
            "domains": target_cols,
            "confidence": 1.0,
            "probabilities": {c: 1.0 / len(target_cols) for c in target_cols},
        }

        flow_cfg = {**runtime.cfg, "top_k": expanded_top_k}

        result = rag_flow(
            question=question,
            history=history,
            reflector=runtime.reflector,
            bge_embedder=self._bge,
            e5_embedder=self._e5,
            searcher=self._searcher,
            reranker=self._reranker,
            chat_model=runtime.chat,
            self_evaluator=runtime.self_evaluator,
            tavily_tool=runtime.tavily_tool,
            cfg=flow_cfg,
            routing_result=routing_result,
            user_context=user_context,
            validity_filter=self._validity_filter,
            reference_resolver=self._reference_resolver,
            llm_cache=self._llm_cache,
            domain_subqueries=domain_subqueries,
        )

        timings_ms = dict(result.get("timings_ms") or {})
        timings_ms["pipeline_total"] = _elapsed_ms(pipeline_t0)
        result["timings_ms"] = timings_ms

        if session_id and self._mongo_logger:
            latency_ms = int((time.perf_counter() - pipeline_t0) * 1000)
            turn_id = self._mongo_logger.log_turn(
                session_id=session_id,
                question=question,
                result=result,
                reflected_question=result.get("reflected_question"),
                latency_ms=latency_ms,
                timings_ms=timings_ms,
            )
            result["turn_id"] = turn_id

        return result

    # ------------------------------------------------------------------
    # Tier-3: LLM domain classification fallback
    # ------------------------------------------------------------------

    def _llm_domain_classify(
        self,
        question: str,
        history: Optional[List[Dict[str, str]]],
        current_routing: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Call the chat LLM to classify domain when classifier confidence is low.

        Only triggers for ~5% of queries (those near domain boundaries).
        Replaces the hardcoded MULTI_DOMAIN_FALLBACK with a data-driven decision.

        Args:
            question: Raw user question.
            history: Recent chat turns (used for context).
            current_routing: Routing dict from the classifier.

        Returns:
            Updated routing dict with ``domains`` and ``domain`` overridden.
        """
        try:
            chat = self._llm_runtime_snapshot().chat
            recent_ctx = ""
            if history:
                recent = history[-2:]
                recent_ctx = " | ".join(
                    m["content"] for m in recent if m.get("content")
                )

            prompt = DOMAIN_CLASSIFICATION_PROMPT.format(
                query=question,
                context=recent_ctx or "(none)",
            )
            raw = chat.generate(query=prompt, mode="chitchat")

            import json as _json
            import re as _re

            # Extract the first JSON object. NOTE: the old
            # `raw.strip("```json").strip("```")` stripped *character sets* (a
            # Python footgun), not substrings, so valid JSON was often mangled
            # and silently dropped into the except branch — disabling Tier-3.
            _match = _re.search(r"\{.*\}", raw, _re.DOTALL)
            clean = _match.group(0) if _match else raw.strip()
            parsed = _json.loads(clean)

            raw_domains = parsed.get("domains") or []
            llm_confidence_str = parsed.get("confidence", "medium")
            # Map LLM confidence string to a numeric value
            llm_confidence = {"high": 0.85, "medium": 0.65, "low": 0.45}.get(
                llm_confidence_str, 0.65
            )

            # Filter to valid RAG domains only
            valid_domains = [d for d in raw_domains if d in _VALID_DOMAINS]
            if not valid_domains:
                logger.warning(
                    "Tier-3 LLM returned no valid domains (%s); "
                    "keeping classifier result.",
                    raw_domains,
                )
                return current_routing

            logger.info(
                "Tier-3 LLM domain override: %s → %s (LLM conf=%s)",
                current_routing.get("domains"),
                valid_domains,
                llm_confidence_str,
            )
            updated = dict(current_routing)
            updated["domains"] = valid_domains
            updated["domain"] = valid_domains[0]
            updated["confidence"] = llm_confidence
            updated["tier3_override"] = True
            return updated

        except Exception as exc:
            logger.warning(
                "Tier-3 LLM domain classification failed (%s); "
                "keeping classifier result.",
                exc,
            )
            return current_routing

    def _handle_chitchat(self, question: str) -> str:
        """Simple chitchat replies without retrieval cost."""
        q = question.strip().lower()

        if any(token in q for token in ("cảm ơn", "thank", "thanks")):
            return "Rất vui được hỗ trợ bạn. Nếu cần thêm thông tin học vụ, bạn cứ hỏi nhé."
        if any(token in q for token in ("tạm biệt", "bye", "goodbye")):
            return "Chào bạn, chúc bạn học tốt. Khi cần hỗ trợ học vụ, mình luôn sẵn sàng."
        if any(
            token in q
            for token in (
                "xin chào",
                "hello",
                "hi",
                "chào",
                "ok",
                "oke",
                "okay",
            )
        ):
            return (
                "Xin chào! Tôi là trợ lý tư vấn học vụ ĐHBK. Bạn cần hỗ trợ gì?"
            )

        return "Mình đang sẵn sàng hỗ trợ các câu hỏi học vụ ĐHBK. Bạn muốn hỏi nội dung nào?"

    def query_stream(
        self,
        question: str,
        history: Optional[List[Dict[str, str]]] = None,
        top_k: Optional[int] = None,
        session_id: Optional[str] = None,
        user_context: Optional[Dict[str, Any]] = None,
        metadata_out: Optional[Dict[str, Any]] = None,
    ) -> Generator[Any, None, None]:
        """Stream the answer token-by-token.

        Routing:
          - chitchat   → direct LLM stream (no retrieval)
          - complex    → LangGraph agent (answer delivered as a single chunk)
          - simple/rag → RAG v2 streaming pipeline

        Metadata (mode, timings, reflected_question, etc.) is written to the
        per-request ``metadata_out`` dict (if provided) as the final step of the
        generator, so the route handler can read it to emit a ``metadata`` SSE
        event WITHOUT racing on shared state. ``self.last_*`` attrs are still
        populated for in-call Mongo logging, but the pipeline is a singleton —
        callers must NOT read ``self.last_*`` after the generator returns when
        concurrent requests are possible; use ``metadata_out`` instead.

        Yields:
            Text chunks as they arrive from the LLM. The ``complex`` branch may
            also yield ``{"type": "status", ...}`` dicts (progress events) — the
            route forwards these; only ``str`` chunks form the answer.
        """
        runtime = self._llm_runtime_snapshot()
        effective_top_k = top_k or runtime.cfg["top_k"]
        pipeline_t0 = time.perf_counter()
        pipeline_timings: Dict[str, float] = {}

        # Auto-load history from MongoDB if session exists and no history given
        if session_id and not history and self._mongo_logger:
            load_t0 = time.perf_counter()
            history = self._mongo_logger.get_history(session_id)
            pipeline_timings["history_load"] = _elapsed_ms(load_t0)

        # ── Step 1: Reflection FIRST — so routing sees the expanded query ────
        reflected_question, ref_result, reflection_ms = self._run_reflection(
            question, history, user_context, runtime,
        )
        if reflection_ms is not None:
            pipeline_timings["reflection"] = reflection_ms

        # ── Step 2: Complexity routing on REFLECTED query ─────────────────────
        complexity_t0 = time.perf_counter()
        complexity = self.complexity_router.route(reflected_question)
        complexity_tier = complexity["tier"]
        complexity_subtype = complexity.get("complex_subtype")
        pipeline_timings["complexity_routing"] = _elapsed_ms(complexity_t0)
        logger.info(
            "ComplexityRouter: %r (reflected from %r) → %s",
            reflected_question[:60],
            question[:40],
            complexity_tier,
        )

        # Request-local stream state. The pipeline is a singleton and this
        # generator is driven concurrently for multiple users, so per-request
        # data MUST live in a local object — writing it to ``self.last_*`` would
        # let concurrent streams clobber each other's Mongo log + metadata.
        # ``self.last_*`` is still mirrored from this object at the very end for
        # backward compatibility (single-request tests / debugging), but it is
        # no longer authoritative.
        _st = SimpleNamespace(
            last_sources=[],
            last_intent=complexity_tier,
            last_timings={},
            last_mode=complexity_tier,
            last_reflected_question=None,
            last_target_collections=None,
            last_collection_scores=None,
            last_routing_probabilities=None,
            last_applied_filters=None,
            last_collection_results=None,
            last_agent_trace=None,
            last_tools_used=[],
            last_tool_calls=[],
            last_iterations=0,
            last_context_trace=None,
            last_rerank_trace=None,
            last_answer_quality_gate=None,
            last_fusion_weights=None,
            last_turn_id=None,
        )

        full_answer_chunks: List[str] = []

        # ── Chitchat branch ───────────────────────────────────────────────────
        if complexity_tier == "chitchat":
            _st.last_mode = "chitchat"
            _st.last_intent = "chitchat"
            stream_t0 = time.perf_counter()
            first_token_ms: Optional[float] = None
            for chunk in chitchat_flow_stream(
                question=question,
                history=history,
                chat_model=runtime.chat,
            ):
                if first_token_ms is None:
                    first_token_ms = _elapsed_ms(stream_t0)
                full_answer_chunks.append(chunk)
                yield chunk

            pipeline_timings["stream_first_token"] = round(
                first_token_ms or 0.0, 2
            )
            pipeline_timings["stream_generate"] = _elapsed_ms(stream_t0)

        # ── Complex branch → agent ────────────────────────────────────────────
        elif (
            complexity_tier == "complex"
            and runtime.agent is not None
        ):
            _st.last_mode = "agent"
            _st.last_intent = "complex"

            # Progress event — agent.run() blocks for ~15-30s; without this the
            # UI shows a frozen spinner the whole time.
            yield {
                "type": "status",
                "stage": "retrieval",
                "message": "Đang tìm kiếm tài liệu liên quan...",
            }

            reflection_prompt = (
                ref_result.get("prompt") if isinstance(ref_result, dict) else None
            )
            agent_t0 = time.perf_counter()
            try:
                agent_result = self.query_agent(
                    question=question,
                    history=history,
                    top_k=effective_top_k,
                    session_id=session_id,
                    user_context=user_context,
                    route_label="complex",
                    require_agent=False,
                    complexity_subtype=complexity.get("complex_subtype"),
                    pre_reflected=reflected_question,
                    pre_reflection_prompt=reflection_prompt,
                    pre_reflection_ms=reflection_ms,
                )
                answer = agent_result.get("answer", "")
                _st.last_mode = str(agent_result.get("mode", "agent"))
                _st.last_agent_trace = agent_result.get("agent_trace")
                _st.last_tools_used = list(
                    agent_result.get("tools_used") or []
                )
                _st.last_tool_calls = list(
                    agent_result.get("tool_calls") or []
                )
                _st.last_iterations = int(agent_result.get("iterations") or 0)
                _st.last_sources = agent_result.get("sources") or []
                _st.last_intent = str(agent_result.get("route") or "complex")
                _st.last_reflected_question = agent_result.get("reflected_question")
                agent_timings = agent_result.get("timings_ms")
                if isinstance(agent_timings, dict) and isinstance(
                    agent_timings.get("reflection"),
                    (int, float),
                ):
                    pipeline_timings["reflection"] = agent_timings["reflection"]
                pipeline_timings["agent_total"] = _elapsed_ms(agent_t0)
            except Exception as exc:
                logger.warning(
                    "Agent failed in stream path (%s), falling back", exc
                )
                answer = "Xin lỗi, có lỗi xảy ra khi xử lý câu hỏi. Vui lòng thử lại."

            # Chunk the finished agent answer so the UI animates it in instead
            # of dumping the whole block. (True token-streaming of the agent's
            # synthesis step is a future change — see plan follow-ups.)
            if answer:
                yield {
                    "type": "status",
                    "stage": "synthesis",
                    "message": "Đang tổng hợp câu trả lời...",
                }
                # Only the str answer feeds full_answer_chunks (it is "".join()-ed
                # for logging below) — never append the status dicts.
                full_answer_chunks.append(answer)
                for piece in _chunk_for_stream(answer):
                    yield piece

        # ── Simple / RAG branch ───────────────────────────────────────────────
        else:
            # Fall back to classic RAG v2 when complexity tier is simple or agent disabled
            _st.last_mode = "rag_v2"
            if (
                complexity_tier == "complex"
                and runtime.agent is None
            ):
                logger.info(
                    "Agent disabled, falling back to RAG v2 for complex query"
                )
                _st.last_mode = "rag_v2_fallback"

            route_t0 = time.perf_counter()
            routing = self._route_with_cache(question, history)
            pipeline_timings["routing"] = _elapsed_ms(route_t0)
            intent = routing.get("intent", "rag")
            _st.last_intent = intent

            # Tier-3 LLM domain fallback already ran inside _route_with_cache (so
            # its result is cached and not recomputed on every repeat).

            flow_cfg = {**runtime.cfg, "top_k": effective_top_k}
            flow_timings: Dict[str, float] = {}
            flow_metadata: Dict[str, Any] = {}
            stream, reranked = rag_flow_stream(
                question=question,
                history=history,
                reflector=runtime.reflector,
                bge_embedder=self._bge,
                e5_embedder=self._e5,
                searcher=self._searcher,
                reranker=self._reranker,
                chat_model=runtime.chat,
                cfg=flow_cfg,
                tavily_tool=runtime.tavily_tool,
                routing_result=routing,
                user_context=user_context,
                validity_filter=self._validity_filter,
                reference_resolver=self._reference_resolver,
                timings_ms_out=flow_timings,
                metadata_out=flow_metadata,
                llm_cache=self._llm_cache,
                reroute_reflected=self._reroute_reflected,
                pre_ref_result=ref_result,
                pre_reflection_ms=reflection_ms,
            )
            _st.last_sources = reranked
            _st.last_reflected_question = flow_metadata.get(
                "reflected_question"
            )
            _st.last_target_collections = flow_metadata.get(
                "target_collections"
            )
            _st.last_collection_scores = flow_metadata.get("collection_scores")
            _st.last_routing_probabilities = flow_metadata.get(
                "routing_probabilities"
            )
            _st.last_applied_filters = flow_metadata.get("applied_filters")
            _st.last_collection_results = flow_metadata.get(
                "collection_results"
            )
            _st.last_context_trace = flow_metadata.get("context_trace")
            _st.last_rerank_trace = flow_metadata.get("rerank_trace")
            _st.last_answer_quality_gate = flow_metadata.get("answer_quality_gate")
            _st.last_fusion_weights = flow_metadata.get("fusion_weights")
            _st.last_tools_used = list(flow_metadata.get("tools_used") or [])
            _st.last_tool_calls = list(flow_metadata.get("tool_calls") or [])

            for chunk in stream:
                full_answer_chunks.append(chunk)
                yield chunk
            pipeline_timings = _merge_timings(pipeline_timings, flow_timings)
            # Update collection scores after stream finishes (timings may have changed)
            if flow_metadata.get("collection_scores"):
                _st.last_collection_scores = flow_metadata.get(
                    "collection_scores"
                )

        timings_ms = _merge_timings(pipeline_timings)
        timings_ms["pipeline_total"] = _elapsed_ms(pipeline_t0)
        _st.last_timings = timings_ms
        _log_timings(f"query_stream({complexity_tier})", timings_ms)

        # Log to MongoDB after stream finishes (skip chitchat to reduce noise/cost)
        if session_id and self._mongo_logger and complexity_tier != "chitchat":
            latency_ms = int((time.perf_counter() - pipeline_t0) * 1000)
            result = {
                "answer": "".join(full_answer_chunks),
                "intent": _st.last_intent,
                "route": _st.last_intent,
                "mode": _st.last_mode,
                "num_sources": len(_st.last_sources),
                "sources": _st.last_sources,
                "model_name": runtime.chat.model,
                "timings_ms": timings_ms,
                "target_collections": _st.last_target_collections,
                "collection_scores": _st.last_collection_scores,
                "routing_probabilities": _st.last_routing_probabilities,
                "applied_filters": _st.last_applied_filters,
                "collection_results": _st.last_collection_results,
                "context_trace": _st.last_context_trace,
                "rerank_trace": _st.last_rerank_trace,
                "answer_quality_gate": _st.last_answer_quality_gate,
                "fusion_weights": _st.last_fusion_weights,
                "answer_status": (
                    _st.last_answer_quality_gate or {}
                ).get("answer_status"),
                "tools_used": _st.last_tools_used,
                "tool_calls": _st.last_tool_calls,
                "iterations": _st.last_iterations,
                "agent_trace": _st.last_agent_trace,
            }
            turn_id = self._mongo_logger.log_turn(
                session_id=session_id,
                question=question,
                result=result,
                reflected_question=_st.last_reflected_question,
                latency_ms=latency_ms,
                timings_ms=timings_ms,
            )
            _st.last_turn_id = turn_id
        else:
            _st.last_turn_id = None

        # ── Per-request metadata export (avoids self.last_* cross-request race) ──
        # The pipeline is a singleton; reading self.last_* in the route after the
        # generator returns races with concurrent streams. All per-request data
        # lives in the local ``_st`` namespace; snapshot it into the caller-owned
        # dict here, as the final statement of the generator.
        if metadata_out is not None:
            metadata_out.update(
                {
                    "mode": _st.last_mode,
                    "route": _st.last_intent,
                    "intent": _st.last_intent,
                    "num_sources": len(_st.last_sources),
                    "retrieved_documents": _st.last_sources,
                    "timings_ms": _st.last_timings,
                    "reflected_question": _st.last_reflected_question,
                    "target_collections": _st.last_target_collections,
                    "collection_scores": _st.last_collection_scores,
                    "routing_probabilities": _st.last_routing_probabilities,
                    "applied_filters": _st.last_applied_filters,
                    "collection_results": _st.last_collection_results,
                    "context_trace": _st.last_context_trace,
                    "rerank_trace": _st.last_rerank_trace,
                    "answer_quality_gate": _st.last_answer_quality_gate,
                    "fusion_weights": _st.last_fusion_weights,
                    "agent_trace": _st.last_agent_trace,
                    "tools_used": _st.last_tools_used,
                    "tool_calls": _st.last_tool_calls,
                    "iterations": _st.last_iterations,
                    "turn_id": _st.last_turn_id,
                }
            )

        # Mirror request-local state onto the singleton for backward-compat
        # (single-request tests / debugging). NOT authoritative under concurrency.
        for _attr, _value in vars(_st).items():
            setattr(self, _attr, _value)
