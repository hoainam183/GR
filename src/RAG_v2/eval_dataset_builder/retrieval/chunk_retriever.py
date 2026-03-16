"""
ChunkRetriever — Gọi Qdrant retrieve chunks cho eval dataset builder.

Phase 2: Nhập query → embed bằng model đã chọn → search Qdrant → trả chunks.

Tích hợp trực tiếp với:
- RAG_v2/embedding/ (BGEm3Embedder, E5MultilingualEmbedder)
- RAG_v2/retrieval/multi_collection_search.py (MultiCollectionSearch — hybrid search)

Hỗ trợ 3 search modes:
- e5: chỉ dùng E5 named vector
- bge_m3: chỉ dùng BGE-M3 named vector
- hybrid: dùng MultiCollectionSearch (Qdrant vectors + Elasticsearch BM25,
          score fusion với vector_weight/keyword_weight,
          pool_k cho global pooling)
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from qdrant_client import QdrantClient, models as qdrant_models

from ..models.schemas import EmbeddingModel, RetrievalConfig, RetrievedChunk

# Ensure RAG_v2 root is importable
_RAG_V2_ROOT = str(Path(__file__).resolve().parents[2])
if _RAG_V2_ROOT not in sys.path:
    sys.path.insert(0, _RAG_V2_ROOT)

logger = logging.getLogger(__name__)


class ChunkRetriever:
    """Retrieve chunks từ Qdrant dựa trên query và config.

    Sử dụng embedding models từ RAG_v2/embedding/ để embed query,
    sau đó search trên Qdrant collection(s).

    Hỗ trợ 3 search modes:
    - e5: Search bằng E5 named vector (Qdrant only)
    - bge_m3: Search bằng BGE-M3 named vector (Qdrant only)
    - hybrid: MultiCollectionSearch (Qdrant + Elasticsearch, score fusion)

    Config params cho hybrid:
    - vector_weight / keyword_weight: weights cho score fusion
    - vector_top_k / keyword_top_k: candidates per collection
    - vector_pool_k / keyword_pool_k: global pool size after merge
    - top_k: final number of results

    Attributes:
        qdrant_host: Qdrant server host.
        qdrant_port: Qdrant server port.
        es_host: Elasticsearch server host.
        es_port: Elasticsearch server port.
        qdrant_client: QdrantClient instance.
        _embedders: Lazy-loaded embedder cache.
        _multi_searcher_cache: Lazy-loaded MultiCollectionSearch cache.
    """

    def __init__(
        self,
        qdrant_host: str = "localhost",
        qdrant_port: int = 6333,
        es_host: str = "localhost",
        es_port: int = 9200,
    ) -> None:
        """Khởi tạo retriever.

        Args:
            qdrant_host: Qdrant server host.
            qdrant_port: Qdrant server port.
            es_host: Elasticsearch server host.
            es_port: Elasticsearch server port.
        """
        self.qdrant_host = qdrant_host
        self.qdrant_port = qdrant_port
        self.es_host = es_host
        self.es_port = es_port
        self.qdrant_client = QdrantClient(host=qdrant_host, port=qdrant_port)
        self._embedders: Dict[str, Any] = {}
        self._multi_searcher_cache: Dict[str, Any] = {}
        logger.info(
            "ChunkRetriever initialized — Qdrant at %s:%d, ES at %s:%d",
            qdrant_host,
            qdrant_port,
            es_host,
            es_port,
        )

    # ------------------------------------------------------------------
    # Embedder management (lazy-loaded)
    # ------------------------------------------------------------------

    def _get_bge_embedder(self):
        """Lazy-load BGE-M3 embedder."""
        if "bge_m3" not in self._embedders:
            from embedding.bge_m3 import BGEm3Embedder
            self._embedders["bge_m3"] = BGEm3Embedder()
            logger.info("Loaded BGE-M3 embedder")
        return self._embedders["bge_m3"]

    def _get_e5_embedder(self):
        """Lazy-load E5 Multilingual embedder."""
        if "e5" not in self._embedders:
            from embedding.e5_multilingual import E5MultilingualEmbedder
            self._embedders["e5"] = E5MultilingualEmbedder()
            logger.info("Loaded E5 Multilingual embedder")
        return self._embedders["e5"]

    def _get_multi_searcher(
        self,
        collections: List[str],
        vector_weight: float,
        keyword_weight: float,
    ):
        """Lazy-load MultiCollectionSearch cho hybrid mode.

        Cache by (collections, vector_weight, keyword_weight).

        Args:
            collections: Qdrant collection names.
            vector_weight: Weight cho vector scores.
            keyword_weight: Weight cho keyword scores.
        """
        cache_key = f"{','.join(sorted(collections))}_{vector_weight}_{keyword_weight}"
        if cache_key not in self._multi_searcher_cache:
            from retrieval.multi_collection_search import MultiCollectionSearch
            searcher = MultiCollectionSearch.from_collection_names(
                collection_names=collections,
                qdrant_host=self.qdrant_host,
                qdrant_port=self.qdrant_port,
                es_host=self.es_host,
                es_port=self.es_port,
                vector_weight=vector_weight,
                keyword_weight=keyword_weight,
            )
            self._multi_searcher_cache[cache_key] = searcher
            logger.info(
                "Built MultiCollectionSearch: collections=%s, v_w=%.1f, k_w=%.1f",
                collections,
                vector_weight,
                keyword_weight,
            )
        return self._multi_searcher_cache[cache_key]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def retrieve(
        self,
        query: str,
        config: RetrievalConfig,
    ) -> List[RetrievedChunk]:
        """Retrieve chunks từ Qdrant theo config.

        Args:
            query: Câu hỏi của human.
            config: Retrieval config (collections, top_k, embedding_model,
                    + hybrid params nếu model=hybrid).

        Returns:
            List[RetrievedChunk] sorted by score (cao → thấp).
        """
        model = config.embedding_model

        if model == EmbeddingModel.E5:
            chunks = self._search_single_vector_all_collections(
                query=query,
                collections=config.collections,
                vector_name="e5",
                embedder=self._get_e5_embedder(),
                top_k=config.top_k,
            )
        elif model == EmbeddingModel.BGE_M3:
            chunks = self._search_single_vector_all_collections(
                query=query,
                collections=config.collections,
                vector_name="bge_m3",
                embedder=self._get_bge_embedder(),
                top_k=config.top_k,
            )
        elif model == EmbeddingModel.HYBRID:
            chunks = self._search_hybrid(query=query, config=config)
        else:
            raise ValueError(f"Unknown embedding model: {model}")

        logger.info(
            "Retrieved %d chunks for query='%s' (model=%s, collections=%s)",
            len(chunks),
            query[:50],
            config.config_label(),
            config.collections,
        )
        return chunks

    # ------------------------------------------------------------------
    # Single-vector search (e5 hoặc bge_m3)
    # ------------------------------------------------------------------

    def _search_single_vector_all_collections(
        self,
        query: str,
        collections: List[str],
        vector_name: str,
        embedder: Any,
        top_k: int,
    ) -> List[RetrievedChunk]:
        """Search bằng một named vector trên nhiều collections.

        Args:
            query: Câu hỏi.
            collections: Qdrant collections.
            vector_name: Tên named vector ("e5" hoặc "bge_m3").
            embedder: Embedder instance (có method embed_query).
            top_k: Số kết quả cuối cùng.

        Returns:
            List[RetrievedChunk] dedup + sort.
        """
        query_vector = embedder.embed_query(query)
        search_params = qdrant_models.SearchParams(hnsw_ef=128, exact=False)
        all_chunks: List[RetrievedChunk] = []

        for collection_name in collections:
            response = self.qdrant_client.query_points(
                collection_name=collection_name,
                query=query_vector,
                using=vector_name,
                limit=top_k,
                search_params=search_params,
                with_payload=True,
            )
            all_chunks.extend(
                self._points_to_chunks(response.points, collection_name)
            )

        return self._dedup_and_sort(all_chunks, top_k)

    # ------------------------------------------------------------------
    # Hybrid search (MultiCollectionSearch)
    # ------------------------------------------------------------------

    def _search_hybrid(
        self,
        query: str,
        config: RetrievalConfig,
    ) -> List[RetrievedChunk]:
        """Hybrid search qua MultiCollectionSearch.

        Sử dụng đúng flow của evaluate_retrieval.py:
        1. Embed query bằng cả BGE-M3 và E5
        2. Gọi MultiCollectionSearch.search() với đầy đủ params:
           - top_k, vector_top_k, keyword_top_k
           - vector_pool_k, keyword_pool_k
           - vector_weight, keyword_weight (đã set lúc init searcher)

        Args:
            query: Câu hỏi.
            config: RetrievalConfig chứa đầy đủ hybrid params.

        Returns:
            List[RetrievedChunk] sorted by fused score.
        """
        # Embed query
        bge_embedder = self._get_bge_embedder()
        e5_embedder = self._get_e5_embedder()
        bge_query_vec = bge_embedder.embed_query(query)
        e5_query_vec = e5_embedder.embed_query(query)

        # Get or create MultiCollectionSearch
        searcher = self._get_multi_searcher(
            collections=config.collections,
            vector_weight=config.vector_weight,
            keyword_weight=config.keyword_weight,
        )

        # Search với đầy đủ params
        results = searcher.search(
            query=query,
            bge_m3_query=bge_query_vec,
            e5_query=e5_query_vec,
            top_k=config.top_k,
            vector_top_k=config.vector_top_k,
            keyword_top_k=config.keyword_top_k,
            vector_pool_k=config.vector_pool_k,
            keyword_pool_k=config.keyword_pool_k,
        )

        # Convert dict results → RetrievedChunk
        return self._dicts_to_chunks(results)

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _points_to_chunks(
        points: list,
        collection_name: str,
    ) -> List[RetrievedChunk]:
        """Convert Qdrant ScoredPoints → RetrievedChunk list."""
        chunks = []
        for point in points:
            payload = point.payload or {}
            text = payload.get("text", "")
            metadata = {k: v for k, v in payload.items() if k != "text"}

            chunks.append(
                RetrievedChunk(
                    chunk_id=str(point.id),
                    score=round(point.score, 6),
                    text=text,
                    collection=collection_name,
                    metadata=metadata,
                )
            )
        return chunks

    @staticmethod
    def _dicts_to_chunks(results: List[Dict[str, Any]]) -> List[RetrievedChunk]:
        """Convert MultiCollectionSearch dict results → RetrievedChunk list.

        MultiCollectionSearch returns:
        {"id", "text", "metadata", "score", "vector_score", "keyword_score",
         "vector_rank", "keyword_rank", "collection"}
        """
        chunks = []
        for r in results:
            metadata = dict(r.get("metadata", {}))
            # Thêm sub-scores vào metadata cho transparency
            if "vector_score" in r:
                metadata["vector_score"] = round(r["vector_score"], 6)
            if "keyword_score" in r:
                metadata["keyword_score"] = round(r["keyword_score"], 6)
            if "vector_rank" in r:
                metadata["vector_rank"] = r["vector_rank"]
            if "keyword_rank" in r:
                metadata["keyword_rank"] = r["keyword_rank"]

            chunks.append(
                RetrievedChunk(
                    chunk_id=str(r["id"]),
                    score=round(r.get("score", 0.0), 6),
                    text=r.get("text", ""),
                    collection=r.get("collection", ""),
                    metadata=metadata,
                )
            )
        return chunks

    @staticmethod
    def _dedup_and_sort(
        chunks: List[RetrievedChunk],
        top_k: int,
    ) -> List[RetrievedChunk]:
        """Dedup by chunk_id, sort by score, trả top_k.

        Nếu search nhiều collections, chunk_id có thể trùng.
        Giữ chunk có score cao nhất.
        """
        seen: Dict[str, RetrievedChunk] = {}
        for chunk in chunks:
            key = f"{chunk.collection}/{chunk.chunk_id}"
            if key not in seen or chunk.score > seen[key].score:
                seen[key] = chunk

        sorted_chunks = sorted(
            seen.values(), key=lambda c: c.score, reverse=True
        )
        return sorted_chunks[:top_k]
