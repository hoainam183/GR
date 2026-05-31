"""Reranking Base — provider-agnostic interface for all reranker backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

# Provider registry — populated by @register_reranker decorators at import time.
# Phase 3 will add the full create_reranker() factory around this registry.
_REGISTRY: dict[str, type[BaseReranker]] = {}


def register_reranker(name: str):
    """Decorator that registers a reranker provider class under *name*."""

    def decorator(cls: type[BaseReranker]) -> type[BaseReranker]:
        _REGISTRY[name] = cls
        return cls

    return decorator


class BaseReranker(ABC):
    """Provider-agnostic reranker interface.

    All reranker implementations (BGE, Cohere, …) must inherit this class
    and implement ``rerank()``.
    """

    @abstractmethod
    def rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: int = 5,
        score_threshold: Optional[float] = None,
        table_score_threshold: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Score and sort *documents* by relevance to *query*.

        Args:
            query: The user question used to rank documents.
            documents: List of document dicts (must contain at least a ``"text"``
                key that the reranker can score against).
            top_k: Maximum number of documents to return.
            score_threshold: Override instance default score threshold.
                Documents below this score are filtered out.
            table_score_threshold: Override instance default threshold for
                table-type documents.

        Returns:
            Documents sorted by descending relevance, truncated to *top_k*.
            Each dict may have an additional ``"rerank_score"`` key added.
        """
        ...
