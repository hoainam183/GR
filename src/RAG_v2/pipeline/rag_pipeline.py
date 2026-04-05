"""RAG v2 Pipeline — orchestrates routing, retrieval, reranking, and generation."""

from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .mongo_logger import MongoLogger

# Ensure project root is on sys.path so sibling packages resolve correctly
PROJECT_ROOT = Path(__file__).resolve().parent.parent  # …/RAG_v2
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

from config.settings import Settings
from embedding import BGEm3Embedder, E5MultilingualEmbedder
from llm import BaseLLM, create_llm
from llm.self_eval import SelfEvaluator
from query.prompts import DOMAIN_CLASSIFICATION_PROMPT
from query.reflection import QueryReflector
from query.router import QueryRouter
from query.training_data import RAG_LABELS
from reranking import create_reranker
from retrieval import create_retriever
from tools.tavily_search import TavilySearchTool

# Confidence below this threshold triggers the Tier-3 LLM domain fallback.
_LLM_FALLBACK_THRESHOLD: float = 0.55
_VALID_DOMAINS = set(RAG_LABELS)

from .flows import (
    chitchat_flow,
    chitchat_flow_stream,
    rag_flow,
    rag_flow_stream,
)

logger = logging.getLogger(__name__)


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
        "vector_weight": settings.vector_weight,
        "keyword_weight": settings.keyword_weight,
        "reranker_top_k": settings.reranker_top_k,
        "model": settings.chat_model,
        "temperature": settings.chat_temperature,
        "max_tokens": settings.chat_max_tokens,
        "router_mode": settings.router_mode,
        "reflection_enabled": settings.reflection_enabled,
        "self_eval_enabled": settings.self_eval_enabled,
        "tavily_fallback_enabled": settings.tavily_fallback_enabled,
    }


# ═══════════════════════════════════════════════════════════════════════════════
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

        # Query router (zero-cost local classifier)
        self._router = QueryRouter(mode=cfg.get("router_mode", "classifier"))

        # Query reflector (LLM-based rewrite)
        self._reflector: Optional[QueryReflector] = None
        if cfg.get("reflection_enabled", True):
            try:
                self._reflector = QueryReflector()
                logger.info("Query reflector loaded.")
            except Exception:
                logger.warning(
                    "Failed to load QueryReflector, skipping reflection",
                    exc_info=True,
                )

        # Embedders (dual named-vector: BGE-M3 + E5 for hybrid search)
        logger.info("Loading BGE-M3 embedder …")
        self._bge = BGEm3Embedder()
        logger.info("Loading E5-multilingual embedder …")
        self._e5 = E5MultilingualEmbedder()

        # Multi-collection hybrid search via factory
        logger.info(
            "Connecting to retrieval stores (collections=%s) …",
            cfg["collections"],
        )
        self._searcher = create_retriever(settings)

        # Reranker via factory
        logger.info("Loading reranker …")
        _reranker = create_reranker(settings)
        assert (
            _reranker is not None
        ), "A reranker is required. Set RERANKER_PROVIDER in .env (e.g. bge)."
        self._reranker = _reranker

        # Chat model via factory
        self._chat: BaseLLM = create_llm(settings)

        # Self evaluator (reuses same LLM instance — no extra API client)
        self._self_eval: Optional[SelfEvaluator] = None
        if cfg.get("self_eval_enabled", False):
            self._self_eval = SelfEvaluator(llm=self._chat)
            logger.info("Self evaluator loaded.")

        # Tavily web search fallback
        self._tavily: Optional[TavilySearchTool] = None
        if cfg.get("tavily_fallback_enabled", False):
            tavily_key = os.environ.get("TAVILY_API_KEY", "").strip()
            if tavily_key and tavily_key not in (
                "",
                "your-key-here",
                "CHANGE_ME",
            ):
                self._tavily = TavilySearchTool(api_key=tavily_key)
                logger.info("Tavily search tool loaded.")
            else:
                logger.warning(
                    "Tavily fallback enabled but TAVILY_API_KEY is missing or "
                    "invalid. Tavily fallback disabled."
                )

        self._cfg = cfg
        self._mongo_logger = mongo_logger
        logger.info("RAG v2 Pipeline ready.")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def query(
        self,
        question: str,
        history: Optional[List[Dict[str, str]]] = None,
        top_k: Optional[int] = None,
        session_id: Optional[str] = None,
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
        """
        effective_top_k = top_k or self._cfg["top_k"]
        t0 = time.perf_counter()

        # Auto-load history from MongoDB if session exists and no history given
        if session_id and not history and self._mongo_logger:
            history = self._mongo_logger.get_history(session_id)

        # 1. Route the query (context-aware — Tier 1)
        routing = self._router.route(question, chat_history=history)
        intent = routing.get("intent", "rag")
        logger.info("Routing decision: intent=%s", intent)

        # Tier-3: LLM domain fallback for low-confidence RAG routing
        if (
            intent == "rag"
            and (routing.get("confidence") or 1.0) < _LLM_FALLBACK_THRESHOLD
        ):
            routing = self._llm_domain_classify(question, history, routing)

        if intent == "chitchat":
            result = chitchat_flow(
                question=question,
                history=history,
                chat_model=self._chat,
            )
            if session_id and self._mongo_logger:
                latency_ms = int((time.perf_counter() - t0) * 1000)
                self._mongo_logger.log_turn(
                    session_id=session_id,
                    question=question,
                    result=result,
                    latency_ms=latency_ms,
                )
            return result

        # 2. RAG flow with reflection, self-eval, and Tavily fallback
        flow_cfg = {**self._cfg, "top_k": effective_top_k}
        result = rag_flow(
            question=question,
            history=history,
            reflector=self._reflector,
            bge_embedder=self._bge,
            e5_embedder=self._e5,
            searcher=self._searcher,
            reranker=self._reranker,
            chat_model=self._chat,
            self_evaluator=self._self_eval,
            tavily_tool=self._tavily,
            cfg=flow_cfg,
            routing_result=routing,
        )

        # Log to MongoDB
        if session_id and self._mongo_logger:
            latency_ms = int((time.perf_counter() - t0) * 1000)
            self._mongo_logger.log_turn(
                session_id=session_id,
                question=question,
                result=result,
                latency_ms=latency_ms,
            )

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
            raw = self._chat.generate(query=prompt, mode="chitchat")

            import json as _json

            # Strip markdown fences if present
            clean = raw.strip().strip("```json").strip("```").strip()
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

    def query_stream(
        self,
        question: str,
        history: Optional[List[Dict[str, str]]] = None,
        top_k: Optional[int] = None,
        session_id: Optional[str] = None,
    ) -> Generator[str, None, None]:
        """Stream the answer token-by-token.

        Retrieval and reranking run synchronously first, then generation is
        streamed.  The reranked sources are stored in ``self.last_sources``
        after the first call so that the caller can retrieve them after the
        stream is exhausted.

        Yields:
            Text chunks as they arrive from the API.
        """
        effective_top_k = top_k or self._cfg["top_k"]
        t0 = time.perf_counter()

        # Auto-load history from MongoDB if session exists and no history given
        if session_id and not history and self._mongo_logger:
            history = self._mongo_logger.get_history(session_id)

        routing = self._router.route(question, chat_history=history)
        intent = routing.get("intent", "rag")

        # Tier-3: LLM domain fallback for low-confidence RAG routing
        if (
            intent == "rag"
            and (routing.get("confidence") or 1.0) < _LLM_FALLBACK_THRESHOLD
        ):
            routing = self._llm_domain_classify(question, history, routing)

        self.last_sources: List[Dict[str, Any]] = []
        self.last_intent: str = intent

        full_answer_chunks: List[str] = []

        if intent == "chitchat":
            for chunk in chitchat_flow_stream(
                question=question,
                history=history,
                chat_model=self._chat,
            ):
                full_answer_chunks.append(chunk)
                yield chunk
        else:
            flow_cfg = {**self._cfg, "top_k": effective_top_k}
            stream, reranked = rag_flow_stream(
                question=question,
                history=history,
                reflector=self._reflector,
                bge_embedder=self._bge,
                e5_embedder=self._e5,
                searcher=self._searcher,
                reranker=self._reranker,
                chat_model=self._chat,
                cfg=flow_cfg,
                routing_result=routing,
            )
            self.last_sources = reranked
            for chunk in stream:
                full_answer_chunks.append(chunk)
                yield chunk

        # Log to MongoDB after stream finishes
        if session_id and self._mongo_logger:
            latency_ms = int((time.perf_counter() - t0) * 1000)
            result = {
                "answer": "".join(full_answer_chunks),
                "intent": intent,
                "num_sources": len(self.last_sources),
                "model_name": self._chat.model,
            }
            self._mongo_logger.log_turn(
                session_id=session_id,
                question=question,
                result=result,
                latency_ms=latency_ms,
            )
