"""Shared chunk indexing policy for retrieval stores."""

from __future__ import annotations

from typing import Any, Mapping


_NON_INDEXABLE_LEVELS = {"parent", "header"}
_INDEXABLE_LEVELS = {"child", "recursive", "appendix"}


def is_indexable_chunk(chunk: Mapping[str, Any]) -> bool:
    """Return True when a chunk should be embedded and indexed.

    Parent/header chunks are useful for review and hierarchy metadata, but they
    should not consume retrieval slots. Older chunkers may omit ``metadata.level``;
    those chunks remain indexable for backward compatibility.
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
