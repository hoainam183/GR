"""Shared chunk indexing policy for retrieval stores."""

from __future__ import annotations

from typing import Any, Mapping


_NON_INDEXABLE_LEVELS = {"parent", "header"}
_INDEXABLE_LEVELS = {"child", "recursive", "appendix"}

# Qdrant storage: keep parent for ID-based fetch (ParentContextExpander),
# skip header only. Parents are excluded from search results by
# `must_not level=parent` filter in MultiCollectionSearch.
_NON_QDRANT_STORABLE_LEVELS = {"header"}


def is_indexable_chunk(chunk: Mapping[str, Any]) -> bool:
    """Return True when a chunk should be embedded and indexed for SEARCH.

    Parent/header chunks are excluded from the search index (ES + Qdrant search).
    They serve as context containers fetched by ID after rerank.
    Older chunkers may omit ``metadata.level``; those chunks remain indexable
    for backward compatibility.
    """
    metadata = chunk.get("metadata") or {}
    if not isinstance(metadata, Mapping):
        return True

    level = metadata.get("level")
    if level is None:
        return True

    normalized = str(level).strip().lower()
    if normalized in _NON_INDEXABLE_LEVELS:
        return False
    if normalized in _INDEXABLE_LEVELS:
        return True
    return True


def is_qdrant_storable(chunk: Mapping[str, Any]) -> bool:
    """Return True when a chunk should be stored in Qdrant.

    Parent chunks ARE stored in Qdrant (needed for ParentContextExpander to
    fetch them by ID) but excluded from search results via the
    ``must_not level=parent`` filter in MultiCollectionSearch.
    Only header chunks are fully excluded from Qdrant.
    """
    metadata = chunk.get("metadata") or {}
    if not isinstance(metadata, Mapping):
        return True

    level = metadata.get("level")
    if level is None:
        return True

    normalized = str(level).strip().lower()
    return normalized not in _NON_QDRANT_STORABLE_LEVELS
