"""Embedding Layer - BGE-M3, Multilingual-E5-Large, Ensemble"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import BaseEmbedder

# Map provider name → dotted module path inside embedding/
_PROVIDER_MODULES: dict[str, str] = {
    "bge_m3": "embedding.bge_m3",
    "e5": "embedding.e5_multilingual",
    "ensemble": "embedding.ensemble",
}


def create_embedder(settings: "Settings") -> BaseEmbedder:  # type: ignore[name-defined]
    """Lazy-import and instantiate the configured embedding model.

    Args:
        settings: Application settings instance.

    Returns:
        A concrete BaseEmbedder for the configured provider.

    Raises:
        ValueError: If *settings.embedding_provider* is not recognised.
    """
    provider = settings.embedding_provider
    if provider == "bge_m3":
        from embedding.bge_m3 import BGEm3Embedder

        return BGEm3Embedder()
    if provider == "e5":
        from embedding.e5_multilingual import E5MultilingualEmbedder

        return E5MultilingualEmbedder()
    if provider == "ensemble":
        from embedding.bge_m3 import BGEm3Embedder
        from embedding.e5_multilingual import E5MultilingualEmbedder
        from embedding.ensemble import EnsembleEmbedder

        return EnsembleEmbedder([BGEm3Embedder(), E5MultilingualEmbedder()])
    raise ValueError(
        f"Unknown embedding provider '{provider}'. "
        f"Known providers: {list(_PROVIDER_MODULES)}"
    )


# Backwards-compatible concrete class exports.
from .bge_m3 import BGEm3Embedder
from embedding.e5_multilingual import E5MultilingualEmbedder
from embedding.ensemble import EnsembleEmbedder

__all__ = [
    "BaseEmbedder",
    "BGEm3Embedder",
    "E5MultilingualEmbedder",
    "EnsembleEmbedder",
    "create_embedder",
]
