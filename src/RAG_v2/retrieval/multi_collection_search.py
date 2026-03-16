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
        vector_weight: float = 0.7,
        keyword_weight: float = 0.3,
    ) -> None:
        """Initialise multi-collection search.

        Args:
            vector_weight: Weight for normalised vector score in final fusion.
            keyword_weight: Weight for normalised keyword (BM25) score in final fusion.
                vector_weight > keyword_weight gives priority to semantic search.
            rrf_k / collection_score_weight: Kept for backward compatibility.
        """
        if not searchers:
            raise ValueError(
                "At least one (collection_name, HybridSearch) is required."
            )
        self.searchers = searchers
        self.rrf_k = rrf_k
        self.max_workers = max_workers
        self.collection_score_weight = collection_score_weight
        self.vector_weight = vector_weight
        self.keyword_weight = keyword_weight

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
            vector_weight=vector_weight,
            keyword_weight=keyword_weight,
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
        vector_pool_k: int = 15,
        keyword_pool_k: int = 15,
        score_threshold: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Search all collections and return a globally ranked list.

        Strategy:
          1. Fetch ``vector_top_k`` vector candidates per collection from Qdrant
             (BGE-M3 + E5 score-fused internally by :class:`QdrantStore`).
          2. Fetch ``keyword_top_k`` keyword candidates per collection from ES.
          3. Pool all vector results globally, sort by raw cosine score,
             deduplicate by ID, keep top ``vector_pool_k``.
          4. Pool all keyword results globally, sort by BM25 score,
             deduplicate by ID, keep top ``keyword_pool_k``.
          5. Min-max normalise both score sets independently, then combine::

                 score = vector_weight * norm_vec + keyword_weight * norm_kw

             Higher ``vector_weight`` gives priority to semantic search.

        Args:
            query: Raw user query string (used for BM25).
            bge_m3_query: Query vector from BGE-M3.
            e5_query: Query vector from E5.
            top_k: Number of final results to return.
            vector_top_k: Candidates fetched from Qdrant per collection.
            keyword_top_k: Candidates fetched from ES per collection.
            vector_pool_k: Size of the global vector candidate pool after sorting.
            keyword_pool_k: Size of the global keyword candidate pool after sorting.
            score_threshold: Optional minimum cosine similarity for Qdrant.

        Returns:
            List of result dicts sorted by global fused score (descending).
        """
        all_vector: List[Dict[str, Any]] = []
        all_keyword: List[Dict[str, Any]] = []

        def _fetch_one(
            name: str, hybrid: HybridSearch
        ) -> Tuple[str, List[Dict], List[Dict]]:
            vecs = hybrid.qdrant.search(
                bge_m3_query=bge_m3_query,
                e5_query=e5_query,
                top_k=vector_top_k,
                score_threshold=score_threshold,
            )
            kws = hybrid.es.keyword_search(query=query, top_k=keyword_top_k)
            return name, vecs, kws

        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {
                pool.submit(_fetch_one, name, hybrid): name
                for name, hybrid in self.searchers
            }
            for fut in as_completed(futures):
                name, vecs, kws = fut.result()
                logger.info(
                    "Collection '%s': %d vector, %d keyword",
                    name,
                    len(vecs),
                    len(kws),
                )
                for item in vecs:
                    all_vector.append(
                        {
                            **item,
                            "collection": name,
                            "id": f"{name}/{item['id']}",
                        }
                    )
                for item in kws:
                    all_keyword.append(
                        {
                            **item,
                            "collection": name,
                            "id": f"{name}/{item['id']}",
                        }
                    )

        # Sort globally by raw score (desc), dedup by ID, take top pool_k
        all_vector.sort(key=lambda x: x["score"], reverse=True)
        vector_pool = self._dedup_pool(all_vector, vector_pool_k)

        all_keyword.sort(key=lambda x: x["score"], reverse=True)
        keyword_pool = self._dedup_pool(all_keyword, keyword_pool_k)

        return self._score_fusion(vector_pool, keyword_pool, top_k)

    # ------------------------------------------------------------------
    # Score fusion helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _dedup_pool(
        results: List[Dict[str, Any]], k: int
    ) -> List[Dict[str, Any]]:
        """Return first ``k`` items with unique IDs (results assumed pre-sorted)."""
        seen: set = set()
        out: List[Dict[str, Any]] = []
        for item in results:
            if item["id"] not in seen:
                seen.add(item["id"])
                out.append(item)
            if len(out) >= k:
                break
        return out

    def _score_fusion(
        self,
        vector_pool: List[Dict[str, Any]],
        keyword_pool: List[Dict[str, Any]],
        top_k: int,
    ) -> List[Dict[str, Any]]:
        """Combine vector and keyword pools via min-max normalised score weighting.

        Both score ranges are independently normalised to [0, 1] so that the
        ``vector_weight`` / ``keyword_weight`` ratio directly controls the
        semantic-vs-keyword trade-off.
        """
        # --- Normalisation bounds (pools are already sorted desc) ---
        if vector_pool:
            v_max = vector_pool[0]["score"]
            v_min = vector_pool[-1]["score"]
            v_range = v_max - v_min if v_max != v_min else 1.0
        else:
            v_min = v_range = 1.0

        if keyword_pool:
            k_max = keyword_pool[0]["score"]
            k_min = keyword_pool[-1]["score"]
            k_range = k_max - k_min if k_max != k_min else 1.0
        else:
            k_min = k_range = 1.0

        combined: Dict[str, Dict[str, Any]] = {}

        for item in vector_pool:
            norm_v = (item["score"] - v_min) / v_range
            doc_id = item["id"]
            combined[doc_id] = {
                **item,
                "vector_score": item["score"],
                "keyword_score": 0.0,
                "norm_vector": norm_v,
                "norm_keyword": 0.0,
            }

        for item in keyword_pool:
            norm_k = (item["score"] - k_min) / k_range
            doc_id = item["id"]
            if doc_id in combined:
                combined[doc_id]["keyword_score"] = item["score"]
                combined[doc_id]["norm_keyword"] = norm_k
            else:
                combined[doc_id] = {
                    **item,
                    "vector_score": 0.0,
                    "keyword_score": item["score"],
                    "norm_vector": 0.0,
                    "norm_keyword": norm_k,
                }

        for entry in combined.values():
            entry["score"] = (
                self.vector_weight * entry["norm_vector"]
                + self.keyword_weight * entry["norm_keyword"]
            )

        ranked = sorted(
            combined.values(), key=lambda x: x["score"], reverse=True
        )

        # Text-level deduplication (parent/child chunks with identical text)
        seen_texts: set = set()
        deduped: List[Dict[str, Any]] = []
        for item in ranked:
            text_key = item["text"].strip()
            if text_key in seen_texts:
                logger.debug(
                    "Dedup: dropping duplicate text from %s", item["id"]
                )
                continue
            seen_texts.add(text_key)
            deduped.append(item)

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
