from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.chunk_indexing import is_indexable_chunk


def test_indexing_policy_skips_parent_and_header_chunks() -> None:
    assert is_indexable_chunk({"metadata": {"level": "parent"}}) is False
    assert is_indexable_chunk({"metadata": {"level": "header"}}) is False


def test_indexing_policy_allows_retrieval_chunks_and_legacy_chunks() -> None:
    assert is_indexable_chunk({"metadata": {"level": "child"}}) is True
    assert is_indexable_chunk({"metadata": {"level": "recursive"}}) is True
    assert is_indexable_chunk({"metadata": {"level": "appendix"}}) is True
    assert is_indexable_chunk({"metadata": {}}) is True
    assert is_indexable_chunk({}) is True
