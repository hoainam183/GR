from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from reranking import create_reranker
from reranking.base import _REGISTRY


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        reranker_provider="bge",
        reranker_model="BAAI/bge-reranker-v2-m3",
        reranker_top_k=5,
        reranker_score_threshold=0.0,
        reranker_table_score_threshold=-5.0,
    )


class _PagingFileFailureReranker:
    def __init__(self, **_: object) -> None:
        raise OSError(
            "The paging file is too small for this operation to complete. "
            "(os error 1455)"
        )


class _OtherOSErrorReranker:
    def __init__(self, **_: object) -> None:
        raise OSError("model file is corrupt")


def test_create_reranker_returns_none_on_model_memory_error(monkeypatch) -> None:
    monkeypatch.setitem(_REGISTRY, "bge", _PagingFileFailureReranker)

    assert create_reranker(_settings()) is None


def test_create_reranker_reraises_non_memory_oserror(monkeypatch) -> None:
    monkeypatch.setitem(_REGISTRY, "bge", _OtherOSErrorReranker)

    with pytest.raises(OSError, match="model file is corrupt"):
        create_reranker(_settings())
