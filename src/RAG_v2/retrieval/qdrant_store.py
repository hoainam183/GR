"""Qdrant Vector Store — dual named-vector collection for BGE-M3 + E5."""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional, Sequence

from qdrant_client import QdrantClient, models

logger = logging.getLogger(__name__)

# Default collection / vector config
DEFAULT_COLLECTION = "stsv"
VECTOR_CONFIGS = {
    "bge_m3": models.VectorParams(size=1024, distance=models.Distance.COSINE),
    "e5": models.VectorParams(size=1024, distance=models.Distance.COSINE),
}


class QdrantStore:
    """Manages a Qdrant collection with two named vectors (bge_m3, e5).

    Parameters:
        host: Qdrant server hostname.
        port: Qdrant gRPC-REST port (default 6333).
        collection_name: Name of the collection to use.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6333,
        collection_name: str = DEFAULT_COLLECTION,
    ) -> None:
        self.collection_name = collection_name
        self.client = QdrantClient(host=host, port=port)
        self._ensure_collection()

    # ------------------------------------------------------------------
    # Collection management
    # ------------------------------------------------------------------

    def _ensure_collection(self) -> None:
        """Create the collection if it does not already exist."""
        collections = [
            c.name for c in self.client.get_collections().collections
        ]
        if self.collection_name in collections:
            logger.info("Collection '%s' already exists.", self.collection_name)
            return

        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VECTOR_CONFIGS,
        )
        logger.info("Created collection '%s'.", self.collection_name)

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def index_documents(
        self,
        texts: List[str],
        bge_m3_vectors: List[List[float]],
        e5_vectors: List[List[float]],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None,
        batch_size: int = 64,
    ) -> None:
        """Upsert documents with both named vectors + payload.

        Args:
            texts: Raw chunk texts.
            bge_m3_vectors: Dense vectors from BGE-M3 embedder.
            e5_vectors: Dense vectors from E5 embedder.
            metadatas: Optional list of metadata dicts per chunk.
            ids: Optional list of point id strings (UUIDs generated if absent).
            batch_size: Number of points per upsert call.
        """
        n = len(texts)
        if not (n == len(bge_m3_vectors) == len(e5_vectors)):
            raise ValueError(
                "texts, bge_m3_vectors, and e5_vectors must have the same length."
            )

        if metadatas is None:
            metadatas = [{}] * n
        if ids is None:
            ids = [str(uuid.uuid4()) for _ in range(n)]

        points: List[models.PointStruct] = []
        for i in range(n):
            payload = {**metadatas[i], "text": texts[i]}
            point = models.PointStruct(
                id=ids[i],
                vector={
                    "bge_m3": bge_m3_vectors[i],
                    "e5": e5_vectors[i],
                },
                payload=payload,
            )
            points.append(point)

            # Flush in batches
            if len(points) >= batch_size:
                self.client.upsert(
                    collection_name=self.collection_name, points=points
                )
                points.clear()

        # Flush remaining
        if points:
            self.client.upsert(
                collection_name=self.collection_name, points=points
            )

        logger.info("Indexed %d documents into '%s'.", n, self.collection_name)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        bge_m3_query: List[float],
        e5_query: List[float],
        top_k: int = 20,
        score_threshold: Optional[float] = None,
        filters: Optional[models.Filter] = None,
        bge_weight: float = 0.5,
        e5_weight: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """Search with both named vectors and fuse their scores.

        Performs two separate searches (one per vector) then combines results
        using weighted score fusion.

        Args:
            bge_m3_query: Query vector from BGE-M3.
            e5_query: Query vector from E5.
            top_k: Number of results to return.
            score_threshold: Minimum similarity score (applied per vector search).
            filters: Optional Qdrant filter conditions.
            bge_weight: Weight for BGE-M3 scores in fusion.
            e5_weight: Weight for E5 scores in fusion.

        Returns:
            List of dicts sorted by fused score (descending):
            ``{"id", "text", "metadata", "score", "bge_score", "e5_score"}``
        """
        search_params = models.SearchParams(hnsw_ef=128, exact=False)

        # Fetch more candidates per vector to improve fusion quality
        per_vector_k = min(top_k * 2, 100)

        bge_resp = self.client.query_points(
            collection_name=self.collection_name,
            query=bge_m3_query,
            using="bge_m3",
            limit=per_vector_k,
            score_threshold=score_threshold,
            query_filter=filters,
            search_params=search_params,
            with_payload=True,
        )
        bge_results = bge_resp.points

        e5_resp = self.client.query_points(
            collection_name=self.collection_name,
            query=e5_query,
            using="e5",
            limit=per_vector_k,
            score_threshold=score_threshold,
            query_filter=filters,
            search_params=search_params,
            with_payload=True,
        )
        e5_results = e5_resp.points

        return self._fuse_results(
            bge_results, e5_results, top_k, bge_weight, e5_weight
        )

    # ------------------------------------------------------------------
    # Fusion
    # ------------------------------------------------------------------

    @staticmethod
    def _fuse_results(
        bge_results: Sequence,
        e5_results: Sequence,
        top_k: int,
        bge_weight: float,
        e5_weight: float,
    ) -> List[Dict[str, Any]]:
        """Weighted score fusion of two result sets."""
        combined: Dict[str, Dict[str, Any]] = {}

        for hit in bge_results:
            pid = str(hit.id)
            payload = dict(hit.payload or {})
            text = payload.pop("text", "")
            combined[pid] = {
                "id": pid,
                "text": text,
                "metadata": payload,
                "bge_score": hit.score,
                "e5_score": 0.0,
            }

        for hit in e5_results:
            pid = str(hit.id)
            payload = dict(hit.payload or {})
            text = payload.pop("text", "")
            if pid in combined:
                combined[pid]["e5_score"] = hit.score
            else:
                combined[pid] = {
                    "id": pid,
                    "text": text,
                    "metadata": payload,
                    "bge_score": 0.0,
                    "e5_score": hit.score,
                }

        for item in combined.values():
            item["score"] = (
                bge_weight * item["bge_score"] + e5_weight * item["e5_score"]
            )

        ranked = sorted(
            combined.values(), key=lambda x: x["score"], reverse=True
        )
        return ranked[:top_k]

    # ------------------------------------------------------------------
    # Point lookup by IDs
    # ------------------------------------------------------------------

    def get_by_ids(self, ids: List[str]) -> List[Dict[str, Any]]:
        """Fetch points by their IDs.

        Args:
            ids: List of point ID strings.

        Returns:
            List of dicts: ``{"id", "text", "metadata"}``.
            Missing IDs are silently skipped.
        """
        if not ids:
            return []

        points = self.client.retrieve(
            collection_name=self.collection_name,
            ids=ids,
            with_payload=True,
            with_vectors=False,
        )

        results: List[Dict[str, Any]] = []
        for point in points:
            payload = dict(point.payload or {})
            text = payload.pop("text", "")
            results.append(
                {
                    "id": str(point.id),
                    "text": text,
                    "metadata": payload,
                }
            )
        logger.info(
            "Retrieved %d/%d points from '%s'.",
            len(results),
            len(ids),
            self.collection_name,
        )
        return results

    def get_by_metadata(
        self,
        filters: Dict[str, Any],
        limit: int = 1,
    ) -> List[Dict[str, Any]]:
        """Lookup points by payload filter (fast scroll, ~5ms).

        Args:
            filters: Dict of {key: value} — matched as exact payload conditions.
            limit: Max number of points to return.

        Returns:
            List of dicts: ``{"id", "text", "metadata", "collection"}``.
        """
        if not filters:
            return []

        conditions = [
            models.FieldCondition(key=k, match=models.MatchValue(value=v))
            for k, v in filters.items()
        ]
        result, _ = self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=models.Filter(must=conditions),
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )

        docs: List[Dict[str, Any]] = []
        for point in result:
            payload = dict(point.payload or {})
            text = payload.pop("text", "")
            docs.append({
                "id": str(point.id),
                "text": text,
                "metadata": payload,
                "collection": self.collection_name,
            })
        return docs

    # ------------------------------------------------------------------
    # Metadata update
    # ------------------------------------------------------------------

    def update_metadata_by_ids(
        self,
        ids: List[str],
        metadata: Dict[str, Any],
        overwrite: bool = False,
    ) -> None:
        """Update payload fields for specific point IDs without re-indexing vectors.

        Args:
            ids: List of point ID strings to update.
            metadata: Dict of payload fields to set/update.
            overwrite: If True, replace the entire payload (except 'text' is kept
                       only if included in *metadata*). If False (default), merge
                       the provided fields into the existing payload.
        """
        if not ids:
            return

        selector = models.PointIdsList(points=ids)  # type: ignore[arg-type]
        if overwrite:
            self.client.overwrite_payload(
                collection_name=self.collection_name,
                payload=metadata,
                points=selector,
            )
        else:
            self.client.set_payload(
                collection_name=self.collection_name,
                payload=metadata,
                points=selector,
            )
        logger.info(
            "Updated metadata for %d point(s) in '%s' (overwrite=%s).",
            len(ids),
            self.collection_name,
            overwrite,
        )

    def update_metadata_batch(
        self,
        id_metadata_pairs: List[tuple],
        overwrite: bool = False,
        batch_size: int = 100,
    ) -> None:
        """Update metadata for many points, each with its own payload dict.

        This is more efficient than calling ``update_metadata_by_ids`` in a
        loop when each point has *different* metadata to set.

        Args:
            id_metadata_pairs: Iterable of ``(id, metadata_dict)`` tuples.
            overwrite: If True, replace the entire payload for each point.
                       If False (default), merge the provided fields.
            batch_size: Number of individual ``set_payload`` / ``overwrite_payload``
                        calls to issue per iteration.  Each call targets exactly
                        one point so the batch here groups them for logging only.
        """
        total = len(id_metadata_pairs)
        updated = 0
        for start in range(0, total, batch_size):
            batch = id_metadata_pairs[start : start + batch_size]
            for point_id, meta in batch:
                selector = models.PointIdsList(points=[point_id])
                if overwrite:
                    self.client.overwrite_payload(
                        collection_name=self.collection_name,
                        payload=meta,
                        points=selector,
                    )
                else:
                    self.client.set_payload(
                        collection_name=self.collection_name,
                        payload=meta,
                        points=selector,
                    )
            updated += len(batch)
            logger.info(
                "update_metadata_batch: %d/%d points processed in '%s'.",
                updated,
                total,
                self.collection_name,
            )
        logger.info(
            "update_metadata_batch done: %d point(s) updated in '%s' (overwrite=%s).",
            total,
            self.collection_name,
            overwrite,
        )

    def update_metadata_by_filter(
        self,
        filter_key: str,
        filter_value: Any,
        metadata: Dict[str, Any],
        overwrite: bool = False,
    ) -> None:
        """Update payload fields for all points matching a filter condition.

        Args:
            filter_key: Payload key to filter on (e.g. ``"source"``).
            filter_value: Expected value for the filter key.
            metadata: Dict of payload fields to set/update.
            overwrite: If True, replace the entire payload for matched points.
                       If False (default), merge the provided fields.
        """
        selector = models.FilterSelector(
            filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key=filter_key,
                        match=models.MatchValue(value=filter_value),
                    )
                ]
            )
        )
        if overwrite:
            self.client.overwrite_payload(
                collection_name=self.collection_name,
                payload=metadata,
                points=selector,
            )
        else:
            self.client.set_payload(
                collection_name=self.collection_name,
                payload=metadata,
                points=selector,
            )
        logger.info(
            "Updated metadata where %s='%s' in '%s' (overwrite=%s).",
            filter_key,
            filter_value,
            self.collection_name,
            overwrite,
        )

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def delete_by_metadata(self, key: str, value: Any) -> None:
        """Delete all points whose payload[key] == value.

        Typical usage: ``store.delete_by_metadata("source", "file.md")``
        """
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key=key,
                            match=models.MatchValue(value=value),
                        )
                    ]
                )
            ),
        )
        logger.info(
            "Deleted points where %s='%s' from '%s'.",
            key,
            value,
            self.collection_name,
        )

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def count(self) -> int:
        """Return the number of points in the collection."""
        info = self.client.get_collection(self.collection_name)
        return info.points_count or 0

    def delete_collection(self) -> None:
        """Drop the entire collection (irreversible)."""
        self.client.delete_collection(self.collection_name)
        logger.info("Deleted collection '%s'.", self.collection_name)
