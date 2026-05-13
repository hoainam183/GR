"""Cross-Reference Resolver — fetches referenced articles/clauses from the same document.

When a retrieved chunk says "theo Điều 48 Khoản 2" or "xem thêm Điều 12",
this module detects those references and fetches the relevant chunks from
the same document source, adding them to the context.

Usage::

    from retrieval.reference_resolver import ReferenceResolver

    resolver = ReferenceResolver(searcher=multi_collection_search)
    enriched = resolver.resolve(results, query="...")
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# ─── Vietnamese legal cross-reference patterns ────────────────────────────────
# Matches patterns like:
#   "Điều 48", "Điều 48 Khoản 2", "Khoản 3 Điều 15",
#   "theo quy định tại Điều 5", "xem thêm Điều 12"

_ARTICLE_RE = re.compile(
    r"(?:theo|xem|tại|căn cứ|quy định tại|nêu tại)?\s*"
    r"(?:Điều|điều)\s+(\d+)"
    r"(?:\s+(?:Khoản|khoản)\s+(\d+))?",
    re.UNICODE,
)

_CLAUSE_FIRST_RE = re.compile(
    r"(?:Khoản|khoản)\s+(\d+)\s+(?:Điều|điều)\s+(\d+)",
    re.UNICODE,
)

# Pattern for "Mục X", "Chương Y"
_SECTION_RE = re.compile(
    r"(?:Mục|mục|Chương|chương)\s+([IVXLC]+|\d+)",
    re.UNICODE,
)


def extract_references(text: str) -> List[Dict[str, Any]]:
    """Extract legal cross-references from a text chunk.

    Returns:
        List of dicts with keys: ``article``, ``clause`` (optional),
        ``raw_match`` (the matched text).
    """
    refs: List[Dict[str, Any]] = []
    seen: Set[str] = set()

    # "Khoản X Điều Y" format
    for match in _CLAUSE_FIRST_RE.finditer(text):
        clause = match.group(1)
        article = match.group(2)
        key = f"d{article}k{clause}"
        if key not in seen:
            seen.add(key)
            refs.append({
                "article": int(article),
                "clause": int(clause),
                "raw_match": match.group(0),
            })

    # "Điều X" or "Điều X Khoản Y" format
    for match in _ARTICLE_RE.finditer(text):
        article = match.group(1)
        clause = match.group(2)
        key = f"d{article}k{clause or 0}"
        if key not in seen:
            seen.add(key)
            refs.append({
                "article": int(article),
                "clause": int(clause) if clause else None,
                "raw_match": match.group(0),
            })

    return refs


class ReferenceResolver:
    """Fetch referenced articles/clauses and add them to context.

    When a retrieved chunk references other articles (e.g., "theo Điều 48"),
    this resolver searches for those articles in the same document source
    and appends them to the result set.

    Parameters:
        retrieval_service: The shared RetrievalService instance (or None
            to disable resolution — references are still extracted for logging).
        max_refs_per_chunk: Maximum number of references to resolve per chunk.
        max_total_refs: Maximum total referenced chunks to add.
    """

    def __init__(
        self,
        retrieval_service: Any = None,
        *,
        max_refs_per_chunk: int = 2,
        max_total_refs: int = 3,
    ) -> None:
        self._service = retrieval_service
        self._max_refs_per_chunk = max_refs_per_chunk
        self._max_total_refs = max_total_refs

    def resolve(
        self,
        results: List[Dict[str, Any]],
        query: str = "",
    ) -> List[Dict[str, Any]]:
        """Scan results for cross-references and fetch referenced chunks.

        Args:
            results: Reranked search results.
            query: Original query (for contextual search of references).

        Returns:
            Original results + any resolved reference chunks appended.
        """
        if not results or self._service is None:
            return results

        all_refs: List[Dict[str, Any]] = []
        existing_texts: Set[str] = set()

        # Build set of existing result texts to avoid duplicates
        for item in results:
            text = ""
            if isinstance(item, dict):
                text = str(item.get("text") or item.get("content") or "")
            existing_texts.add(text[:200])  # use prefix for dedup

        # Scan each result for cross-references
        for item in results:
            text = ""
            source = ""
            collection = ""

            if isinstance(item, dict):
                text = str(item.get("text") or item.get("content") or "")
                metadata = item.get("metadata", {}) or {}
                source = str(
                    item.get("source")
                    or metadata.get("source")
                    or ""
                )
                collection = str(
                    item.get("collection")
                    or metadata.get("collection")
                    or ""
                )

            refs = extract_references(text)
            if not refs:
                continue

            logger.info(
                "Cross-references found in chunk (source=%s): %s",
                source[:40],
                [r["raw_match"] for r in refs[:5]],
            )

            # Fetch referenced articles
            for ref in refs[:self._max_refs_per_chunk]:
                if len(all_refs) >= self._max_total_refs:
                    break

                ref_query = f"Điều {ref['article']}"
                if ref.get("clause"):
                    ref_query += f" Khoản {ref['clause']}"

                try:
                    ref_results = self._service.search(
                        query=ref_query,
                        collections=[collection] if collection else None,
                        top_k=2,
                        rerank=True,
                    )

                    for ref_item in ref_results:
                        ref_text = ""
                        if isinstance(ref_item, dict):
                            ref_text = str(
                                ref_item.get("text")
                                or ref_item.get("content")
                                or ""
                            )

                        # Skip if already in results
                        if ref_text[:200] in existing_texts:
                            continue

                        # Verify the reference actually contains the article
                        article_str = f"Điều {ref['article']}"
                        if article_str.lower() not in ref_text.lower():
                            continue

                        # Mark as cross-reference
                        if isinstance(ref_item, dict):
                            ref_item["_cross_reference"] = True
                            ref_item["_referenced_from"] = source[:60]
                            ref_item["_reference"] = ref["raw_match"]

                        all_refs.append(ref_item)
                        existing_texts.add(ref_text[:200])
                        logger.info(
                            "Resolved cross-reference: %s (from %s)",
                            ref["raw_match"], source[:40],
                        )
                        break  # one match per reference is enough

                except Exception:
                    logger.debug(
                        "Failed to resolve reference %s",
                        ref["raw_match"],
                        exc_info=True,
                    )

        if all_refs:
            logger.info(
                "Cross-reference resolver: added %d referenced chunks.",
                len(all_refs),
            )
            return results + all_refs

        return results
