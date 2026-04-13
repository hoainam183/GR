# Hybrid Retrieval Layer - Qdrant + Elasticsearch
from __future__ import annotations

from typing import TYPE_CHECKING

from .base import BaseRetriever
from .qdrant_store import QdrantStore
from .elasticsearch_store import ElasticsearchStore
from .hybrid_search import HybridSearch
from .metadata_filters import (
    BaseFilterExtractor,
    CollectionFilter,
    build_collection_filters,
)
from .multi_collection_search import MultiCollectionSearch


def create_retriever(settings: "Settings") -> MultiCollectionSearch:  # type: ignore[name-defined]
    """Instantiate a MultiCollectionSearch retriever from settings.

    Args:
        settings: Application settings instance.

    Returns:
        A MultiCollectionSearch configured for all collections in settings.
    """
    return MultiCollectionSearch.from_collection_names(
        collection_names=settings.collections,
        qdrant_host=settings.qdrant_host,
        qdrant_port=settings.qdrant_port,
        es_host=settings.elasticsearch_host,
        es_port=settings.elasticsearch_port,
        vector_weight=settings.vector_weight,
        keyword_weight=settings.keyword_weight,
    )


__all__ = [
    "BaseRetriever",
    "QdrantStore",
    "ElasticsearchStore",
    "HybridSearch",
    "BaseFilterExtractor",
    "CollectionFilter",
    "build_collection_filters",
    "MultiCollectionSearch",
    "create_retriever",
]
