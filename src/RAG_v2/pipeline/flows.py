"""Pipeline Flows — chitchat and RAG flow definitions."""

from __future__ import annotations

import logging
from typing import Any, Dict, Generator, List, Optional

from embedding.base import BaseEmbedder
from llm.base import BaseLLM
from llm.self_eval import SelfEvaluator
from reranking.base import BaseReranker
from retrieval.collection_selector import CollectionSelector

logger = logging.getLogger(__name__)

_collection_selector = CollectionSelector()


# ═══════════════════════════════════════════════════════════════════════════════
# Helper
# ═══════════════════════════════════════════════════════════════════════════════


def _format_context(documents: List[Dict[str, Any]]) -> str:
    """Convert retrieved documents into a context string for the LLM."""
    parts = []
    for i, doc in enumerate(documents, 1):
        meta = doc.get("metadata", {})
        title = meta.get("title") or meta.get("source") or "Tài liệu"
        text = doc.get("text", "")
        parts.append(f"[{i}] {title}\n{text}")
    return "\n\n---\n\n".join(parts)


def _trim_history(
    history: Optional[List[Dict[str, str]]], limit: int = 12
) -> List[Dict[str, str]]:
    """Keep only the last *limit* turns for LLM context."""
    if not history:
        return []
    return history[-limit:]


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
    trimmed = _trim_history(history)

    answer = chat_model.generate(
        query=question,
        history=trimmed,
        mode="chitchat",
    )
    logger.info("chitchat_flow: generated %d chars", len(answer))

    return {
        "question": question,
        "answer": answer,
        "sources": [],
        "num_sources": 0,
        "intent": "chitchat",
        "model_name": chat_model.model,
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

    Returns:
        Dict with ``answer``, ``sources``, ``intent``, etc.
    """
    trimmed = _trim_history(history)

    # 1. Reflection — rewrite query for better retrieval
    search_query = question
    if reflector is not None:
        try:
            result = reflector.reflect(question, chat_history=trimmed)
            search_query = result.get("rewritten", question)
            logger.info("Reflected query: %r", search_query[:80])
        except Exception:
            logger.warning(
                "Reflection failed, using original query", exc_info=True
            )

    # 2. Collection-aware routing (Phase 8 — Tier 2 multi-domain)
    target_collections: Optional[List[str]] = None
    if routing_result:
        domain = routing_result.get("domain")
        domains = routing_result.get("domains") or ([domain] if domain else [])
        confidence = routing_result.get("confidence", 0.0)
        target_collections = _collection_selector.select(
            domain=domain,
            confidence=confidence,
            domains=domains,
        )
        logger.info(
            "Domains: %s (conf=%.3f) → searching collections: %s",
            domains,
            confidence,
            target_collections,
        )

    # 3. Embed
    bge_vec = bge_embedder.embed_query(search_query)
    e5_vec = e5_embedder.embed_query(search_query)

    # 4. Hybrid search
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
    )
    logger.info("Retrieved %d raw candidates", len(raw_results))

    # 5. Rerank
    reranked = reranker.rerank(
        query=search_query, documents=raw_results, top_k=cfg.get("top_k", 5)
    )
    logger.info("Reranked to %d documents", len(reranked))

    # 6. Format context
    context = _format_context(reranked)

    # 7. Generate answer
    answer = chat_model.generate(
        query=question,
        context=context,
        history=trimmed,
        mode="rag",
    )

    # 8. Self-evaluation
    if self_evaluator is not None:
        try:
            eval_result = self_evaluator.evaluate(
                query=question, context=context, response=answer
            )
            if not eval_result.get("pass", True):
                logger.info(
                    "Self-eval FAILED (%s), attempting Tavily fallback",
                    eval_result.get("reason", "")[:60],
                )
                answer = _tavily_fallback(
                    question=question,
                    answer=answer,
                    tavily_tool=tavily_tool,
                    chat_model=chat_model,
                    history=trimmed,
                )
        except Exception:
            logger.warning(
                "Self-evaluation error, keeping original answer", exc_info=True
            )

    return {
        "question": question,
        "answer": answer,
        "sources": reranked,
        "num_sources": len(reranked),
        "intent": "rag",
        "model_name": chat_model.model,
        "target_collections": target_collections,
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
) -> tuple[Generator[str, None, None], List[Dict[str, Any]]]:
    """Streaming RAG flow — retrieval runs first, then generation is streamed.

    Returns:
        A tuple of (text_chunk_generator, reranked_sources).
    """
    trimmed = _trim_history(history)

    # Reflection
    search_query = question
    if reflector is not None:
        try:
            result = reflector.reflect(question, chat_history=trimmed)
            search_query = result.get("rewritten", question)
        except Exception:
            logger.warning(
                "Reflection failed, using original query", exc_info=True
            )

    # Collection-aware routing (Phase 8 — Tier 2 multi-domain)
    target_collections: Optional[List[str]] = None
    if routing_result:
        domain = routing_result.get("domain")
        domains = routing_result.get("domains") or ([domain] if domain else [])
        confidence = routing_result.get("confidence", 0.0)
        target_collections = _collection_selector.select(
            domain=domain,
            confidence=confidence,
            domains=domains,
        )

    # Embed → Search → Rerank
    bge_vec = bge_embedder.embed_query(search_query)
    e5_vec = e5_embedder.embed_query(search_query)

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
    )

    reranked = reranker.rerank(
        query=search_query, documents=raw_results, top_k=cfg.get("top_k", 5)
    )

    context = _format_context(reranked)

    stream = chat_model.generate_stream(
        query=question, context=context, history=trimmed, mode="rag"
    )

    return stream, reranked


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
) -> str:
    """Use Tavily web search to re-generate the answer when self-eval fails."""
    if tavily_tool is None:
        logger.info("No Tavily tool configured, returning original answer")
        return answer

    try:
        search_result = tavily_tool.search(question)
        web_context = search_result.get("context", "")
        if not web_context:
            return answer

        new_answer = chat_model.generate(
            query=question,
            context=web_context,
            history=history,
            mode="rag",
        )
        logger.info("Tavily fallback generated %d chars", len(new_answer))
        return new_answer
    except Exception:
        logger.warning(
            "Tavily fallback failed, returning original answer", exc_info=True
        )
        return answer
