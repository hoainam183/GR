"""Hybrid Search — combines Qdrant vector search + Elasticsearch BM25 via RRF."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from qdrant_client import models as qdrant_models

from .elasticsearch_store import ElasticsearchStore
from .qdrant_store import QdrantStore

logger = logging.getLogger(__name__)


def rrf_score(rank: int, k: int = 60) -> float:
    """Reciprocal Rank Fusion score for a given 1-based rank."""
    return 1.0 / (k + rank)


class HybridSearch:
    """Combines Qdrant (dense vector) and Elasticsearch (BM25 keyword) results
    using Reciprocal Rank Fusion (RRF).

    Parameters:
        qdrant_store: An initialised QdrantStore instance.
        es_store: An initialised ElasticsearchStore instance.
        rrf_k: RRF constant (default 60).
        vector_weight: Multiplier applied to the vector RRF score.
        keyword_weight: Multiplier applied to the keyword RRF score.
    """

    def __init__(
        self,
        qdrant_store: QdrantStore,
        es_store: ElasticsearchStore,
        rrf_k: int = 60,
        vector_weight: float = 1.0,
        keyword_weight: float = 1.0,
    ) -> None:
        self.qdrant = qdrant_store
        self.es = es_store
        self.rrf_k = rrf_k
        self.vector_weight = vector_weight
        self.keyword_weight = keyword_weight

    # ------------------------------------------------------------------
    # Public API
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
        qdrant_filters: Optional[qdrant_models.Filter] = None,
        es_filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Run hybrid retrieval and return fused results.

        Args:
            query: Raw user query string (used for BM25).
            bge_m3_query: Query vector from BGE-M3 embedder.
            e5_query: Query vector from E5 embedder.
            top_k: Number of final results to return after fusion.
            vector_top_k: Candidates to fetch from Qdrant.
            keyword_top_k: Candidates to fetch from Elasticsearch.
            score_threshold: Optional minimum similarity for vector search.
            qdrant_filters: Optional Qdrant filter conditions.
            es_filters: Optional Elasticsearch filter clauses.

        Returns:
            List of dicts sorted by fused RRF score (descending):
            ``{"id", "text", "metadata", "score", "vector_score", "keyword_score",
               "vector_rank", "keyword_rank"}``
        """
        # Step 1 — Qdrant vector search
        vector_results = self.qdrant.search(
            bge_m3_query=bge_m3_query,
            e5_query=e5_query,
            top_k=vector_top_k,
            score_threshold=score_threshold,
            filters=qdrant_filters,
        )

        # Step 2 — Elasticsearch keyword search
        keyword_results = self.es.keyword_search(
            query=query,
            top_k=keyword_top_k,
            filters=es_filters,
        )

        # Step 3 — RRF fusion
        fused = self._rrf_fuse(vector_results, keyword_results)

        # Step 4 — Return top-K
        return fused[:top_k]

    # ------------------------------------------------------------------
    # RRF Fusion
    # ------------------------------------------------------------------

    def _rrf_fuse(
        self,
        vector_results: List[Dict[str, Any]],
        keyword_results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Merge two ranked result lists using Reciprocal Rank Fusion.

        Each document gets:
            fused_score = vector_weight * rrf(vector_rank) + keyword_weight * rrf(keyword_rank)

        Documents appearing in only one list receive 0 for the missing component.
        """
        combined: Dict[str, Dict[str, Any]] = {}

        # Process vector results (1-based ranks)
        for rank_0, item in enumerate(vector_results):
            doc_id = str(item["id"])
            combined[doc_id] = {
                "id": doc_id,
                "text": item["text"],
                "metadata": item.get("metadata", {}),
                "vector_rank": rank_0 + 1,
                "keyword_rank": 0,
                "vector_rrf": self.vector_weight
                * rrf_score(rank_0 + 1, self.rrf_k),
                "keyword_rrf": 0.0,
                "vector_score": item.get("score", 0.0),
                "keyword_score": 0.0,
                # Raw per-model cosine scores from Qdrant (pass-through for diagnostics)
                "bge_score": item.get("bge_score", 0.0),
                "e5_score": item.get("e5_score", 0.0),
            }

        # Process keyword results (1-based ranks)
        for rank_0, item in enumerate(keyword_results):
            doc_id = str(item["id"])
            kw_rrf = self.keyword_weight * rrf_score(rank_0 + 1, self.rrf_k)

            if doc_id in combined:
                combined[doc_id]["keyword_rank"] = rank_0 + 1
                combined[doc_id]["keyword_rrf"] = kw_rrf
                combined[doc_id]["keyword_score"] = item.get("score", 0.0)
            else:
                combined[doc_id] = {
                    "id": doc_id,
                    "text": item["text"],
                    "metadata": item.get("metadata", {}),
                    "vector_rank": 0,
                    "keyword_rank": rank_0 + 1,
                    "vector_rrf": 0.0,
                    "keyword_rrf": kw_rrf,
                    "vector_score": 0.0,
                    "keyword_score": item.get("score", 0.0),
                }

        # Compute final fused score
        for item in combined.values():
            item["score"] = item["vector_rrf"] + item["keyword_rrf"]

        ranked = sorted(
            combined.values(), key=lambda x: x["score"], reverse=True
        )
        return ranked
