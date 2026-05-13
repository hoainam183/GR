"""Document Validity Filter — excludes superseded regulations from search results.

Uses ``data/document_lineage.json`` to identify which documents have been
replaced by newer versions. After reranking, this filter removes chunks
belonging to superseded documents so the LLM only sees current regulations.

Usage::

    from retrieval.validity_filter import ValidityFilter

    vf = ValidityFilter()
    filtered = vf.filter(reranked_results)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

_REGISTRY_PATH = Path(__file__).resolve().parent.parent / "data" / "document_lineage.json"


class ValidityFilter:
    """Filter out chunks belonging to superseded documents.

    Loads the document lineage registry on init and builds a set of
    superseded ``doc_id`` values. During filtering, each search result's
    metadata ``source`` field is checked against known superseded patterns.

    Parameters:
        registry_path: Path to the lineage JSON file. Defaults to
            ``data/document_lineage.json``.
    """

    def __init__(self, registry_path: Optional[Path] = None) -> None:
        self._registry_path = registry_path or _REGISTRY_PATH
        self._superseded_ids: Set[str] = set()
        self._superseded_patterns: List[str] = []
        self._load_registry()

    def _load_registry(self) -> None:
        """Load the lineage registry and build the superseded sets."""
        if not self._registry_path.exists():
            logger.warning(
                "Document lineage registry not found at %s — "
                "validity filtering disabled.",
                self._registry_path,
            )
            return

        try:
            with open(self._registry_path, encoding="utf-8") as f:
                data = json.load(f)

            documents = data.get("documents", [])
            for doc in documents:
                if doc.get("status") == "superseded":
                    doc_id = doc.get("doc_id", "")
                    if doc_id:
                        self._superseded_ids.add(doc_id)
                    # Also extract filename patterns for fuzzy matching
                    source_file = doc.get("source_file", "")
                    if source_file:
                        # Strip extension for flexible matching
                        stem = Path(source_file).stem
                        self._superseded_patterns.append(stem.lower())

            if self._superseded_ids:
                logger.info(
                    "Validity filter loaded: %d superseded documents — %s",
                    len(self._superseded_ids),
                    sorted(self._superseded_ids),
                )
            else:
                logger.info("Validity filter: no superseded documents found in registry.")
        except Exception:
            logger.warning(
                "Failed to load document lineage registry",
                exc_info=True,
            )

    @property
    def superseded_ids(self) -> Set[str]:
        """Return the set of superseded document IDs."""
        return set(self._superseded_ids)

    def is_superseded(self, source: str) -> bool:
        """Check if a source string matches a superseded document.

        Performs fuzzy matching against known superseded document patterns.

        Args:
            source: The source/filename string from chunk metadata.

        Returns:
            True if the document is superseded.
        """
        if not source or not self._superseded_patterns:
            return False

        source_lower = source.lower()
        for pattern in self._superseded_patterns:
            if pattern in source_lower:
                return True
        return False

    def filter(
        self,
        results: List[Dict[str, Any]],
        *,
        min_results: int = 2,
    ) -> List[Dict[str, Any]]:
        """Remove results from superseded documents.

        Args:
            results: Reranked search results.
            min_results: Minimum number of results to keep. If filtering
                would leave fewer than this many results, return unfiltered.

        Returns:
            Filtered results list.
        """
        if not self._superseded_patterns:
            return results

        filtered: List[Dict[str, Any]] = []
        removed_count = 0

        for item in results:
            source = ""
            if isinstance(item, dict):
                metadata = item.get("metadata", {}) or {}
                source = str(
                    item.get("source")
                    or metadata.get("source")
                    or metadata.get("title")
                    or ""
                )
            elif hasattr(item, "payload"):
                payload = getattr(item, "payload", {}) or {}
                source = str(payload.get("source") or payload.get("title") or "")

            if self.is_superseded(source):
                removed_count += 1
                logger.debug(
                    "Validity filter: removing superseded chunk (source=%s)",
                    source[:60],
                )
            else:
                filtered.append(item)

        # Safety: don't filter so aggressively that we lose all results
        if len(filtered) < min_results and results:
            logger.info(
                "Validity filter would leave only %d results (min=%d), "
                "keeping original %d results.",
                len(filtered), min_results, len(results),
            )
            return results

        if removed_count:
            logger.info(
                "Validity filter: removed %d superseded chunks, %d remaining.",
                removed_count, len(filtered),
            )

        return filtered

    def reload(self) -> None:
        """Reload the registry from disk (for hot-reloading after data updates)."""
        self._superseded_ids.clear()
        self._superseded_patterns.clear()
        self._load_registry()
