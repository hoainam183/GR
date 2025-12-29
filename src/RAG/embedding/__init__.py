"""
RAG Embedding Package
Scalable embedding pipeline with multi-database support
"""

from .embedding import EmbeddingPipeline, create_pipeline
from .config import (
    PipelineConfig,
    EmbeddingModelConfig,
    ChunkProcessingConfig,
    VectorStoreConfig,
)
from .vector_store import VectorStore, Document, SearchResult
from .faiss_store import FaissVectorStore, FaissConfig

__all__ = [
    "EmbeddingPipeline",
    "create_pipeline",
    "PipelineConfig",
    "EmbeddingModelConfig",
    "ChunkProcessingConfig",
    "VectorStoreConfig",
    "VectorStore",
    "Document",
    "SearchResult",
    "FaissVectorStore",
    "FaissConfig",
]

__version__ = "1.0.0"
