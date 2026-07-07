"""Parent Context Retrieval — expand child search results with parent context.

When search is performed on child chunks (fine-grained), this module fetches
the associated parent chunk to provide broader context to the LLM.

Strategy:
  - Search results contain child chunks (precise, small)
  - For each unique parent_id found in results, fetch the parent from Qdrant
  - Return expanded context: child chunks + their parent's content
  - Deduplicate: if multiple children share the same parent, include parent once

This implements the "search on children, read from parents" pattern that
maximizes both retrieval precision and LLM context quality.

Usage::

    from retrieval.parent_context import ParentContextExpander

    expander = ParentContextExpander(qdrant_host="localhost", qdrant_port=6333)
    expanded = expander.expand_with_parents(search_results, collection="ctdt")
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, List, Optional, Set, Tuple

from qdrant_client import QdrantClient

logger = logging.getLogger(__name__)


class ParentContextExpander:
    """Expands search results by fetching parent chunk context.

    Given a list of child chunks from search, fetches their parent chunks
    from Qdrant and returns enriched results with parent context attached.

    Args:
        qdrant_host: Qdrant server hostname.
        qdrant_port: Qdrant server port.
        max_parent_chars: Maximum characters from parent content to include.
    """

    def __init__(
        self,
        qdrant_host: str = "localhost",
        qdrant_port: int = 6333,
        max_parent_chars: int = 3000,
    ) -> None:
        self._host = qdrant_host
        self._port = qdrant_port
        self._max_parent_chars = max_parent_chars
        self._client: Optional[QdrantClient] = None

    @property
    def client(self) -> QdrantClient:
        """Lazy-initialize Qdrant client."""
        if self._client is None:
            self._client = QdrantClient(host=self._host, port=self._port)
        return self._client

    def expand_with_parents(
        self,
        search_results: List[Dict[str, Any]],
        collection: str,
        include_parent_content: bool = True,
    ) -> List[Dict[str, Any]]:
        """Expand search results with parent chunk context.

        For each child chunk that has a parent_id, fetches the parent and
        attaches its content as `parent_context` in the result metadata.

        Args:
            search_results: List of search result dicts (must have 'metadata').
            collection: Qdrant collection name to fetch parents from.
            include_parent_content: Whether to include parent text content.

        Returns:
            Enriched search results with parent_context field added.
        """
        if not search_results:
            return search_results

        # Collect unique parent IDs that need fetching
        parent_ids_needed: Set[str] = set()
        for result in search_results:
            metadata = result.get("metadata", {})
            parent_id = metadata.get("parent_id")
            level = metadata.get("level", "child")
            if parent_id and level == "child":
                parent_ids_needed.add(parent_id)

        if not parent_ids_needed:
            logger.debug("No parent IDs to fetch — all results are parents or orphans")
            return search_results

        # Fetch parent chunks from Qdrant
        parent_map = self._fetch_parents(
            list(parent_ids_needed), collection
        )
        logger.info(
            "Fetched %d/%d parent chunks from '%s'",
            len(parent_map),
            len(parent_ids_needed),
            collection,
        )

        # Enrich results with parent context
        enriched = []
        for result in search_results:
            metadata = result.get("metadata", {})
            parent_id = metadata.get("parent_id")

            if parent_id and parent_id in parent_map:
                parent = parent_map[parent_id]
                enriched_result = {**result}
                enriched_meta = {**metadata}

                if include_parent_content:
                    parent_content = parent.get("text", "")
                    if len(parent_content) > self._max_parent_chars:
                        truncated = parent_content[: self._max_parent_chars]
                        # Prefer cutting at a sentence/paragraph boundary so the
                        # LLM does not receive a clause sliced mid-sentence.
                        boundary = max(truncated.rfind(". "), truncated.rfind("\n"))
                        if boundary >= self._max_parent_chars * 0.6:
                            truncated = truncated[: boundary + 1]
                        # Explicit marker so the LLM knows the content is incomplete
                        # and avoids asserting the truncated text is the full rule.
                        parent_content = truncated.rstrip() + "\n\n[… nội dung còn tiếp, xem tài liệu gốc …]"
                    enriched_meta["parent_context"] = parent_content

                enriched_meta["parent_title"] = parent.get("metadata", {}).get(
                    "hierarchy_path", ""
                )
                enriched_meta["parent_section_h2"] = parent.get("metadata", {}).get(
                    "section_h2", ""
                )
                enriched_result["metadata"] = enriched_meta
                enriched.append(enriched_result)
            else:
                enriched.append(result)

        return enriched

    def get_parent_for_child(
        self,
        child_result: Dict[str, Any],
        collection: str,
    ) -> Optional[Dict[str, Any]]:
        """Fetch the parent chunk for a single child result.

        Args:
            child_result: Search result dict with metadata.parent_id.
            collection: Qdrant collection name.

        Returns:
            Parent chunk dict or None if not found.
        """
        metadata = child_result.get("metadata", {})
        parent_id = metadata.get("parent_id")
        if not parent_id:
            return None

        parents = self._fetch_parents([parent_id], collection)
        return parents.get(parent_id)

    def _fetch_parents(
        self,
        parent_ids: List[str],
        collection: str,
    ) -> Dict[str, Dict[str, Any]]:
        """Fetch parent chunks by their IDs from Qdrant.

        Returns:
            Mapping of parent_id → {"text": ..., "metadata": {...}}
        """
        if not parent_ids:
            return {}

        try:
            points = self.client.retrieve(
                collection_name=collection,
                ids=parent_ids,
                with_payload=True,
                with_vectors=False,
            )
        except Exception:
            logger.warning(
                "Failed to fetch %d parent chunks from '%s'",
                len(parent_ids),
                collection,
                exc_info=True,
            )
            return {}

        result: Dict[str, Dict[str, Any]] = {}
        for point in points:
            payload = dict(point.payload or {})
            text = payload.pop("text", "")
            result[str(point.id)] = {
                "text": text,
                "metadata": payload,
            }

        return result


# ── Process-wide expander cache ───────────────────────────────────────────────
# Building a ParentContextExpander lazily opens a new QdrantClient (a fresh TCP
# connection). Parent expansion runs on almost every RAG query, so constructing
# one per call reconnects to Qdrant each time. Cache expanders by their config so
# the client is opened once and reused; the client is used read-only (retrieve),
# which is safe to share across the pipeline threadpool.
_EXPANDER_CACHE: Dict[Tuple[str, int, int], "ParentContextExpander"] = {}
_EXPANDER_CACHE_LOCK = threading.Lock()


def get_parent_expander(
    qdrant_host: str = "localhost",
    qdrant_port: int = 6333,
    max_parent_chars: int = 3000,
) -> "ParentContextExpander":
    """Return a cached :class:`ParentContextExpander` for the given config.

    Reuses one expander (and its lazily-opened Qdrant connection) per distinct
    ``(host, port, max_parent_chars)`` instead of building a new one — and a new
    ``QdrantClient`` — on every query.
    """
    key = (qdrant_host, qdrant_port, max_parent_chars)
    cached = _EXPANDER_CACHE.get(key)
    if cached is not None:
        return cached
    with _EXPANDER_CACHE_LOCK:
        cached = _EXPANDER_CACHE.get(key)
        if cached is None:
            cached = ParentContextExpander(
                qdrant_host=qdrant_host,
                qdrant_port=qdrant_port,
                max_parent_chars=max_parent_chars,
            )
            _EXPANDER_CACHE[key] = cached
        return cached
