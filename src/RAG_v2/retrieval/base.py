"""Retrieval Base — provider-agnostic interface for all retriever backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class BaseRetriever(ABC):
    """Provider-agnostic retriever interface.

    All retriever implementations (Qdrant, Elasticsearch, hybrid, …) must
    inherit this class and implement ``search()``.
    """

    @abstractmethod
    def search(
        self,
        query: str,
        query_vector: Optional[List[float]] = None,
        top_k: int = 5,
        **kwargs: Any,
    ) -> List[Dict[str, Any]]:
        """Retrieve the most relevant documents for *query*.

        Args:
            query: The raw text query (used for keyword search).
            query_vector: Dense embedding of the query (used for vector search).
                May be ``None`` for keyword-only retrievers.
            top_k: Maximum number of documents to return.
            **kwargs: Additional backend-specific parameters.

        Returns:
            List of document dicts sorted by descending relevance.
        """
        ...
