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

import hashlib
import json
import logging
import os
import time
from collections import OrderedDict
from typing import Any, Dict, List, Optional

from config.settings import Settings

logger = logging.getLogger(__name__)


class _SearchResultCache:
    """TTL-based LRU cache for search results.

    Caches hybrid search results keyed by (query, collections, filters) to
    avoid re-executing identical searches within a short window.
    """

    def __init__(self, maxsize: int = 128, ttl_seconds: float = 180.0) -> None:
        self._maxsize = maxsize
        self._ttl = ttl_seconds
        self._cache: OrderedDict[str, tuple[float, List[Dict[str, Any]]]] = OrderedDict()
        self._hits = 0
        self._misses = 0

    def _make_key(
        self,
        query: str,
        collections: Optional[List[str]],
        resolved_major: Optional[str],
        resolved_cohort: Optional[str],
    ) -> str:
        raw = json.dumps(
            {
                "q": query,
                "c": sorted(collections) if collections else None,
                "m": resolved_major,
                "co": resolved_cohort,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(
        self,
        query: str,
        collections: Optional[List[str]],
        resolved_major: Optional[str] = None,
        resolved_cohort: Optional[str] = None,
    ) -> Optional[List[Dict[str, Any]]]:
        key = self._make_key(query, collections, resolved_major, resolved_cohort)
        if key in self._cache:
            ts, results = self._cache[key]
            if time.time() - ts < self._ttl:
                self._cache.move_to_end(key)
                self._hits += 1
                return results
            # Expired
            del self._cache[key]
        self._misses += 1
        return None

    def put(
        self,
        query: str,
        collections: Optional[List[str]],
        results: List[Dict[str, Any]],
        resolved_major: Optional[str] = None,
        resolved_cohort: Optional[str] = None,
    ) -> None:
        key = self._make_key(query, collections, resolved_major, resolved_cohort)
        self._cache[key] = (time.time(), results)
        self._cache.move_to_end(key)
        if len(self._cache) > self._maxsize:
            self._cache.popitem(last=False)

    @property
    def stats(self) -> Dict[str, Any]:
        return {"hits": self._hits, "misses": self._misses, "size": len(self._cache)}


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
        self._search_cache = _SearchResultCache(maxsize=128, ttl_seconds=180.0)

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
        entities: Optional[Dict[str, Any]] = None,
        use_multi_query: bool = False,
    ) -> List[Dict[str, Any]]:
        """Run hybrid search with optional reranking and multi-query expansion.

        Args:
            query: Search query text.
            collections: Qdrant collection names (defaults to all).
            top_k: Number of final results (after reranking).
            resolved_major: Major code for metadata pre-filtering.
            resolved_cohort: Cohort code for metadata pre-filtering.
            rerank: Whether to apply reranking (default True).
            entities: Extracted entities dict (for multi-query expansion).
            use_multi_query: Whether to use multi-query expansion for better recall.

        Returns:
            List of result dicts with text, metadata, and scores.
        """
        effective_top_k = top_k or self.settings.top_k
        # Tăng phễu hứng candidates lên gấp 8 lần top_k (trước đây là 4) để hạn chế rớt chunk khi rerank
        raw_candidate_k = max(effective_top_k * 8, 40)
        active_collections = collections or self.settings.collections

        # Multi-query expansion: search multiple query variants and merge
        if use_multi_query and entities:
            from retrieval.query_expander import MultiQueryExpander

            expander = MultiQueryExpander(max_variants=3)
            variants = expander.expand(query, entities)
            if len(variants) > 1:
                logger.info(
                    "Multi-query expansion: %d variants for '%s'",
                    len(variants),
                    query[:60],
                )
                return self._search_multi_query(
                    variants,
                    effective_top_k=effective_top_k,
                    raw_candidate_k=raw_candidate_k,
                    active_collections=active_collections,
                    resolved_major=resolved_major,
                    resolved_cohort=resolved_cohort,
                    rerank=rerank,
                )

        return self._search_single(
            query,
            effective_top_k=effective_top_k,
            raw_candidate_k=raw_candidate_k,
            active_collections=active_collections,
            resolved_major=resolved_major,
            resolved_cohort=resolved_cohort,
            rerank=rerank,
        )

    def search_with_hyde(
        self,
        query: str,
        llm: Any,
        *,
        collections: Optional[List[str]] = None,
        top_k: Optional[int] = None,
        resolved_major: Optional[str] = None,
        resolved_cohort: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """HyDE fallback search: generate hypothesis → embed → search.

        Use this when initial retrieval returns low-confidence results.

        Args:
            query: Original user query.
            llm: LLM instance for hypothesis generation.
            collections: Target collections.
            top_k: Number of results.
            resolved_major: Major for pre-filtering.
            resolved_cohort: Cohort for pre-filtering.

        Returns:
            Results from HyDE-enhanced search (no reranking applied — caller
            should rerank the merged pool).
        """
        from retrieval.hyde import HyDEExpander

        effective_top_k = top_k or self.settings.top_k
        raw_candidate_k = max(effective_top_k * 8, 40)
        active_collections = collections or self.settings.collections

        hyde = HyDEExpander(llm=llm, embedder=self.bge_embedder)
        hyde_vec = hyde.generate_embedding(query)
        # Also embed with E5 using the original query (HyDE only for BGE)
        e5_vec = self.e5_embedder.embed_query(query)

        search_kwargs: Dict[str, Any] = {
            "query": query,
            "bge_m3_query": hyde_vec,
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
        return results[:effective_top_k]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _search_single(
        self,
        query: str,
        *,
        effective_top_k: int,
        raw_candidate_k: int,
        active_collections: List[str],
        resolved_major: Optional[str],
        resolved_cohort: Optional[str],
        rerank: bool,
    ) -> List[Dict[str, Any]]:
        """Single-query search path with result caching."""
        # Check cache (pre-rerank results)
        cached = self._search_cache.get(
            query, active_collections, resolved_major, resolved_cohort
        )
        if cached is not None:
            logger.debug("Search cache hit for query: %s", query[:60])
            results = cached
        else:
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
            # Cache raw results before reranking
            self._search_cache.put(
                query, active_collections, results, resolved_major, resolved_cohort
            )

        if rerank and self.reranker is not None:
            results = self.reranker.rerank(
                query=query,
                documents=results,
                top_k=effective_top_k,
            )
        else:
            results = results[:effective_top_k]

        # Parent-child context expansion: enrich child results with parent content
        if self.settings.parent_context_enabled:
            results = self._expand_parent_context(results, active_collections)

        return results

    def _search_multi_query(
        self,
        variants: List[str],
        *,
        effective_top_k: int,
        raw_candidate_k: int,
        active_collections: List[str],
        resolved_major: Optional[str],
        resolved_cohort: Optional[str],
        rerank: bool,
    ) -> List[Dict[str, Any]]:
        """Multi-query search: run each variant, merge, dedup, then rerank."""
        all_results: List[Dict[str, Any]] = []
        seen_ids: set = set()

        # Distribute budget across variants
        per_variant_k = max(raw_candidate_k // len(variants), 10)

        for variant in variants:
            bge_vec, e5_vec = self.embed_query(variant)

            search_kwargs: Dict[str, Any] = {
                "query": variant,
                "bge_m3_query": bge_vec,
                "e5_query": e5_vec,
                "top_k": per_variant_k,
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

            for doc in results:
                doc_id = doc.get("id", "")
                if doc_id not in seen_ids:
                    seen_ids.add(doc_id)
                    all_results.append(doc)

        # Rerank the merged pool with the original query (first variant)
        if rerank and self.reranker is not None:
            all_results = self.reranker.rerank(
                query=variants[0],
                documents=all_results,
                top_k=effective_top_k,
            )
        else:
            # Sort by score and truncate
            all_results.sort(key=lambda x: x.get("score", 0), reverse=True)
            all_results = all_results[:effective_top_k]

        # Parent-child context expansion (same as _search_single)
        if self.settings.parent_context_enabled:
            all_results = self._expand_parent_context(all_results, active_collections)

        return all_results

    def _expand_parent_context(
        self,
        results: List[Dict[str, Any]],
        collections: List[str],
    ) -> List[Dict[str, Any]]:
        """Expand child results with parent chunk content.

        For each child result that has a parent_id, fetches the parent from
        Qdrant and attaches its content as `parent_context` in metadata.
        Groups by collection since parent fetches are per-collection.
        """
        if not results:
            return results

        # Check if any result actually has a parent_id
        has_parent = any(
            r.get("metadata", {}).get("parent_id")
            and r.get("metadata", {}).get("level") == "child"
            for r in results
        )
        if not has_parent:
            return results

        try:
            from retrieval.parent_context import ParentContextExpander

            expander = ParentContextExpander(
                qdrant_host=self.settings.qdrant_host,
                qdrant_port=self.settings.qdrant_port,
                max_parent_chars=self.settings.parent_max_chars,
            )

            # Group results by collection for efficient parent fetching
            # Determine collection from metadata or use first active collection
            collection_groups: Dict[str, List[int]] = {}
            for idx, result in enumerate(results):
                coll = (
                    result.get("collection", "")
                    or result.get("metadata", {}).get("collection", "")
                )
                if not coll and collections:
                    coll = collections[0]
                if coll:
                    collection_groups.setdefault(coll, []).append(idx)

            # Expand each collection group
            for coll, indices in collection_groups.items():
                group_results = [results[i] for i in indices]
                expanded = expander.expand_with_parents(group_results, coll)
                for i, expanded_result in zip(indices, expanded):
                    results[i] = expanded_result

        except Exception:
            logger.warning("Parent context expansion failed", exc_info=True)

        return results
