"""Retrieval Service — unified singleton for search operations.

Eliminates the duplicated runtime init between ``RAGPipeline`` and
``tool_adapters._AdapterRuntime`` by providing a single, injectable service
that wraps embedders, searcher, reranker, and web-search tool.

Usage::

    # At application startup (RAGPipeline.__init__)
    service = RetrievalService.from_settings(settings)

    # Inject into agent tool adapters
    from agent import tool_adapters
    tool_adapters.set_retrieval_service(service)

    # Direct use in pipeline code
    results = service.search(query="...", collections=["ctdt"], ...)
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from config.settings import Settings

logger = logging.getLogger(__name__)


class RetrievalService:
    """Unified retrieval service wrapping all search infrastructure.

    Holds shared references to embedders, searcher, reranker and optional
    web-search tool.  Designed to be created once at startup and injected
    into both the RAG pipeline flows and the agent tool adapters.

    Parameters:
        settings: Application settings instance.
        bge_embedder: BGE-M3 embedder instance.
        e5_embedder: E5-multilingual embedder instance.
        searcher: MultiCollectionSearch instance.
        reranker: Reranker instance (or None for no reranking).
        tavily_tool: TavilySearchTool instance (or None).
    """

    def __init__(
        self,
        settings: Settings,
        bge_embedder: Any,
        e5_embedder: Any,
        searcher: Any,
        reranker: Any | None = None,
        tavily_tool: Any | None = None,
    ) -> None:
        self.settings = settings
        self.bge_embedder = bge_embedder
        self.e5_embedder = e5_embedder
        self.searcher = searcher
        self.reranker = reranker
        self.tavily_tool = tavily_tool

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_settings(cls, settings: Settings) -> "RetrievalService":
        """Build a fully initialised service from application settings.

        This is the canonical entry-point: it loads embedders, connects to
        Qdrant/ES, and optionally creates the Tavily web search tool.
        """
        from embedding import BGEm3Embedder, E5MultilingualEmbedder
        from reranking import create_reranker
        from retrieval import create_retriever
        from tools.tavily_search import TavilySearchTool, is_valid_tavily_api_key

        logger.info("RetrievalService: loading BGE-M3 embedder …")
        bge = BGEm3Embedder()
        logger.info("RetrievalService: loading E5-multilingual embedder …")
        e5 = E5MultilingualEmbedder()

        logger.info(
            "RetrievalService: connecting to retrieval stores (collections=%s) …",
            settings.collections,
        )
        searcher = create_retriever(settings)

        logger.info("RetrievalService: loading reranker …")
        reranker = create_reranker(settings)

        tavily_key = settings.tavily_api_key or os.environ.get("TAVILY_API_KEY", "")
        tavily_tool: TavilySearchTool | None = None
        if is_valid_tavily_api_key(tavily_key):
            tavily_tool = TavilySearchTool(
                api_key=tavily_key,
                cache_maxsize=settings.tavily_cache_maxsize,
                cache_ttl_seconds=settings.tavily_cache_ttl_seconds,
            )
            logger.info("RetrievalService: Tavily web search tool loaded.")

        service = cls(
            settings=settings,
            bge_embedder=bge,
            e5_embedder=e5,
            searcher=searcher,
            reranker=reranker,
            tavily_tool=tavily_tool,
        )
        logger.info("RetrievalService: ready.")
        return service

    # ------------------------------------------------------------------
    # Search operations
    # ------------------------------------------------------------------

    def embed_query(self, query: str) -> tuple[list[float], list[float]]:
        """Embed a query with both BGE-M3 and E5, returning (bge_vec, e5_vec)."""
        bge_vec = self.bge_embedder.embed_query(query)
        e5_vec = self.e5_embedder.embed_query(query)
        return bge_vec, e5_vec

    def search(
        self,
        query: str,
        *,
        collections: Optional[List[str]] = None,
        top_k: Optional[int] = None,
        resolved_major: Optional[str] = None,
        resolved_cohort: Optional[str] = None,
        rerank: bool = True,
    ) -> List[Dict[str, Any]]:
        """Run hybrid search with optional reranking.

        Args:
            query: Search query text.
            collections: Qdrant collection names (defaults to all).
            top_k: Number of final results (after reranking).
            resolved_major: Major code for metadata pre-filtering.
            resolved_cohort: Cohort code for metadata pre-filtering.
            rerank: Whether to apply reranking (default True).

        Returns:
            List of result dicts with text, metadata, and scores.
        """
        effective_top_k = top_k or self.settings.top_k
        raw_candidate_k = max(effective_top_k * 4, 20)
        active_collections = collections or self.settings.collections

        bge_vec, e5_vec = self.embed_query(query)

        search_kwargs: Dict[str, Any] = {
            "query": query,
            "bge_m3_query": bge_vec,
            "e5_query": e5_vec,
            "top_k": raw_candidate_k,
            "vector_top_k": self.settings.vector_top_k,
            "keyword_top_k": self.settings.keyword_top_k,
            "vector_pool_k": self.settings.vector_pool_k,
            "keyword_pool_k": self.settings.keyword_pool_k,
            "active_collections": active_collections,
        }
        if resolved_major:
            search_kwargs["resolved_major"] = resolved_major
        if resolved_cohort:
            search_kwargs["resolved_cohort"] = resolved_cohort

        results = self.searcher.search(**search_kwargs)

        if rerank and self.reranker is not None:
            results = self.reranker.rerank(
                query=query,
                documents=results,
                top_k=effective_top_k,
            )
        else:
            results = results[:effective_top_k]

        return results

    def web_search(self, query: str, max_results: int = 3) -> Any:
        """Run a Tavily web search.

        Returns:
            Search results dict, or None if Tavily is not configured.

        Raises:
            RuntimeError: If Tavily is not available.
        """
        if self.tavily_tool is None:
            raise RuntimeError("Tavily web search tool is not configured.")
        return self.tavily_tool.search(query=query, max_results=max_results)
