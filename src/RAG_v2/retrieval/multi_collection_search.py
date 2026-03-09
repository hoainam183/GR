"""Multi-Collection Hybrid Search — search across multiple Qdrant/ES collections.

Runs hybrid search (vector + BM25) against each registered collection in
parallel (threads), then merges all per-collection results with a second
round of RRF so the final list is globally ranked.

Usage::

    from retrieval.multi_collection_search import MultiCollectionSearch

    searcher = MultiCollectionSearch.from_collection_names(
        ["stsv", "quydinh"],
        bge_embedder=bge,
        e5_embedder=e5,
    )

    results = searcher.search(
        query="Điều kiện xét học bổng?",
        bge_m3_query=bge_vec,
        e5_query=e5_vec,
        top_k=10,
    )
    # Each result dict includes a "collection" field.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple

from .elasticsearch_store import ElasticsearchStore
from .hybrid_search import HybridSearch, rrf_score
from .qdrant_store import QdrantStore

logger = logging.getLogger(__name__)


class MultiCollectionSearch:
    """Hybrid search across multiple (Qdrant collection, ES index) pairs.

    Parameters:
        searchers: List of ``(collection_name, HybridSearch)`` tuples.
        rrf_k: RRF constant for the global-merge step (default 60).
        max_workers: Thread-pool size for parallel per-collection searches.
    """

    def __init__(
        self,
        searchers: List[Tuple[str, HybridSearch]],
        rrf_k: int = 60,
        max_workers: int = 4,
        collection_score_weight: float = 1.0,
    ) -> None:
        """Initialise multi-collection search.

        Args:
            collection_score_weight: Weight applied to the per-collection hybrid
                score when computing the global ranking.  Set to 0 for pure
                positional RRF (original behaviour).  Default 1.0 blends the
                within-collection quality signal into the global score so that
                a high-quality result from one collection is not outranked by
                a lower-quality result from another collection that happened to
                land at the same positional rank.
        """
        if not searchers:
            raise ValueError(
                "At least one (collection_name, HybridSearch) is required."
            )
        self.searchers = searchers
        self.rrf_k = rrf_k
        self.max_workers = max_workers
        self.collection_score_weight = collection_score_weight

    # ------------------------------------------------------------------
    # Factory helpers
    # ------------------------------------------------------------------

    @classmethod
    def from_collection_names(
        cls,
        collection_names: List[str],
        es_index_names: Optional[List[str]] = None,
        qdrant_host: str = "localhost",
        qdrant_port: int = 6333,
        es_host: str = "localhost",
        es_port: int = 9200,
        rrf_k: int = 60,
        vector_weight: float = 1.0,
        keyword_weight: float = 1.0,
        max_workers: int = 4,
        collection_score_weight: float = 1.0,
    ) -> "MultiCollectionSearch":
        """Convenience constructor — create stores from names.

        Args:
            collection_names: Qdrant collection names.
            es_index_names: ES index names. Defaults to same as collection names.
            qdrant_host / qdrant_port: Qdrant connection params.
            es_host / es_port: Elasticsearch connection params.
            rrf_k: RRF constant.
            vector_weight / keyword_weight: Score weights.
            max_workers: Thread pool size.
        """
        if es_index_names is None:
            es_index_names = collection_names
        if len(es_index_names) != len(collection_names):
            raise ValueError(
                "es_index_names must have the same length as collection_names."
            )

        searchers: List[Tuple[str, HybridSearch]] = []
        for col, es_idx in zip(collection_names, es_index_names):
            logger.info(
                "Initialising HybridSearch for collection='%s', es_index='%s'",
                col,
                es_idx,
            )
            qdrant_store = QdrantStore(
                host=qdrant_host, port=qdrant_port, collection_name=col
            )
            es_store = ElasticsearchStore(
                host=es_host, port=es_port, index_name=es_idx
            )
            hybrid = HybridSearch(
                qdrant_store=qdrant_store,
                es_store=es_store,
                rrf_k=rrf_k,
                vector_weight=vector_weight,
                keyword_weight=keyword_weight,
            )
            searchers.append((col, hybrid))

        return cls(
            searchers=searchers,
            rrf_k=rrf_k,
            max_workers=max_workers,
            collection_score_weight=collection_score_weight,
        )

    # ------------------------------------------------------------------
    # Public search API
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        bge_m3_query: List[float],
        e5_query: List[float],
        top_k: int = 10,
        vector_top_k: int = 20,
        keyword_top_k: int = 20,
        score_threshold: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Search all collections and return a globally ranked list.

        Each result dict includes a ``"collection"`` key indicating which
        collection the document came from.

        Args:
            query: Raw user query string (used for BM25).
            bge_m3_query: Query vector from BGE-M3.
            e5_query: Query vector from E5.
            top_k: Number of final results.
            vector_top_k: Candidates fetched from Qdrant per collection.
            keyword_top_k: Candidates fetched from ES per collection.
            score_threshold: Optional minimum cosine similarity for Qdrant.

        Returns:
            List of result dicts sorted by global fused score (descending).
        """
        per_collection: Dict[str, List[Dict[str, Any]]] = {}

        def _search_one(name: str, hybrid: HybridSearch) -> Tuple[str, List]:
            results = hybrid.search(
                query=query,
                bge_m3_query=bge_m3_query,
                e5_query=e5_query,
                top_k=vector_top_k
                + keyword_top_k,  # fetch more for global merge
                vector_top_k=vector_top_k,
                keyword_top_k=keyword_top_k,
                score_threshold=score_threshold,
            )
            return name, results

        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {
                pool.submit(_search_one, name, hybrid): name
                for name, hybrid in self.searchers
            }
            for fut in as_completed(futures):
                name, results = fut.result()
                per_collection[name] = results
                logger.info("Collection '%s': %d results", name, len(results))

        return self._global_rrf(per_collection, top_k)

    # ------------------------------------------------------------------
    # Global RRF merge
    # ------------------------------------------------------------------

    def _global_rrf(
        self,
        per_collection: Dict[str, List[Dict[str, Any]]],
        top_k: int,
    ) -> List[Dict[str, Any]]:
        """Merge per-collection ranked lists with a second RRF pass.

        Global score combines two signals:
          1. Positional RRF: ``1 / (rrf_k + rank)`` — standard RRF weighting.
          2. Collection score: the per-collection hybrid (vector+BM25) RRF
             score, scaled by ``collection_score_weight``.

        Blending both signals prevents a high-ranked but low-quality result
        from one collection from outranking a slightly lower-ranked but
        higher-quality result from another collection.

        Document IDs are namespaced as ``"<collection>/<id>"`` so the same
        chunk-id in two different collections remains distinct.

        Parent/child deduplication: when a parent chunk and one of its
        children carry identical text, only the higher-scoring copy is kept.
        """
        combined: Dict[str, Dict[str, Any]] = {}

        for col_name, results in per_collection.items():
            for rank_0, item in enumerate(results):
                global_id = f"{col_name}/{item['id']}"
                col_score = item.get("score", 0.0)
                positional = rrf_score(rank_0 + 1, self.rrf_k)
                total = positional + self.collection_score_weight * col_score

                if global_id in combined:
                    # Same doc arrived from multiple collections (shouldn't
                    # normally happen since IDs are namespaced, but guard it).
                    combined[global_id]["global_rrf"] += total
                else:
                    combined[global_id] = {
                        "id": item["id"],
                        "collection": col_name,
                        "text": item["text"],
                        "metadata": item.get("metadata", {}),
                        "vector_rank": item.get("vector_rank", 0),
                        "keyword_rank": item.get("keyword_rank", 0),
                        "vector_score": item.get("vector_score", 0.0),
                        "keyword_score": item.get("keyword_score", 0.0),
                        "bge_score": item.get("bge_score", 0.0),
                        "e5_score": item.get("e5_score", 0.0),
                        "collection_score": col_score,
                        "global_rrf": total,
                    }

        ranked = sorted(
            combined.values(), key=lambda x: x["global_rrf"], reverse=True
        )

        # --- Parent/child deduplication -----------------------------------
        # When a parent chunk and its children have identical text (parent
        # retrieval), keep only the first occurrence (already highest score).
        seen_texts: set = set()
        deduped: List[Dict[str, Any]] = []
        for item in ranked:
            text_key = item["text"].strip()
            if text_key in seen_texts:
                logger.debug(
                    "Dedup: dropping duplicate text from %s/%s",
                    item["collection"],
                    item["id"],
                )
                continue
            seen_texts.add(text_key)
            deduped.append(item)

        # Rename global_rrf → score for API consistency
        for item in deduped:
            item["score"] = item.pop("global_rrf")

        return deduped[:top_k]

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    @property
    def collection_names(self) -> List[str]:
        """Names of all registered collections."""
        return [name for name, _ in self.searchers]

    def collection_counts(self) -> Dict[str, Dict[str, int]]:
        """Return {collection_name: {qdrant: n, es: n}} document counts."""
        counts: Dict[str, Dict[str, int]] = {}
        for name, hybrid in self.searchers:
            counts[name] = {
                "qdrant": hybrid.qdrant.count(),
                "es": hybrid.es.count(),
            }
        return counts
