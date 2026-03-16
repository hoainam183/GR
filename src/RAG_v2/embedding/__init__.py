"""Embedding Layer - BGE-M3, Multilingual-E5-Large, Ensemble"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class BaseEmbedder(ABC):
    """Abstract base class for all embedding models."""

    @abstractmethod
    def embed(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of texts into dense vectors.

        Args:
            texts: List of input strings to embed.

        Returns:
            List of embedding vectors (each a list of floats).
        """
        ...

    @abstractmethod
    def embed_query(self, text: str) -> List[float]:
        """Embed a single query text.

        Args:
            text: The query string.

        Returns:
            A single embedding vector.
        """
        ...

    @abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of document texts.

        Args:
            texts: List of document strings.

        Returns:
            List of embedding vectors.
        """
        ...

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the dimension of the embedding vectors."""
        ...


from embedding.bge_m3 import BGEm3Embedder
from embedding.e5_multilingual import E5MultilingualEmbedder
from embedding.ensemble import EnsembleEmbedder

__all__ = [
    "BaseEmbedder",
    "BGEm3Embedder",
    "E5MultilingualEmbedder",
    "EnsembleEmbedder",
]
