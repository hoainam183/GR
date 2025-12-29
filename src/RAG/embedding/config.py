"""
Configuration for Embedding Pipeline
Centralized configuration để dễ quản lý và scale
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class EmbeddingModelConfig:
    """Config cho embedding model"""

    model_name: str = "intfloat/multilingual-e5-large"
    device: str = "cpu"  # "cpu" hoặc "cuda"
    normalize_embeddings: bool = True
    batch_size: int = 32

    # Model kwargs
    model_kwargs: dict = field(default_factory=lambda: {"device": "cpu"})

    # Encoding kwargs
    encode_kwargs: dict = field(
        default_factory=lambda: {"normalize_embeddings": True, "batch_size": 32}
    )

    def __post_init__(self):
        """Update nested configs"""
        self.model_kwargs["device"] = self.device
        self.encode_kwargs["normalize_embeddings"] = self.normalize_embeddings
        self.encode_kwargs["batch_size"] = self.batch_size


@dataclass
class ChunkProcessingConfig:
    """Config cho chunk processing"""

    # Input/Output paths
    input_chunks_dir: str = "../chunks_by_articles"  # Thư mục chứa chunks.json
    output_dir: str = "./output"
    vector_store_dir: str = "./vector_store"

    # Processing options
    context_strategy: str = "optimized"  # "optimized" hoặc "alternative"
    add_instruction_prefix: bool = True  # Thêm "passage: " prefix cho E5 model

    # Batch processing
    embedding_batch_size: int = 32
    save_intermediate: bool = True  # Lưu chunks_with_embeddings.json

    # Multi-file processing
    overwrite_existing: bool = False  # Có ghi đè documents cũ không
    track_source_file: bool = True  # Luôn True để track source


@dataclass
class VectorStoreConfig:
    """Config cho vector store (FAISS, PostgreSQL, etc.)"""

    store_type: str = "faiss"  # "faiss", "postgres", "chromadb", etc.

    # FAISS specific
    faiss_index_type: str = "IndexFlatIP"  # Inner Product for cosine similarity
    dimension: int = 1024  # multilingual-e5-large dimension
    use_gpu: bool = False

    # PostgreSQL specific (for future)
    postgres_host: Optional[str] = None
    postgres_port: int = 5432
    postgres_db: Optional[str] = None
    postgres_user: Optional[str] = None
    postgres_password: Optional[str] = None

    # Search settings
    default_top_k: int = 5
    enable_metadata_filter: bool = True


@dataclass
class PipelineConfig:
    """Complete pipeline configuration"""

    embedding: EmbeddingModelConfig = field(
        default_factory=EmbeddingModelConfig
    )
    chunks: ChunkProcessingConfig = field(default_factory=ChunkProcessingConfig)
    vector_store: VectorStoreConfig = field(default_factory=VectorStoreConfig)

    # Logging
    verbose: bool = True
    log_file: Optional[str] = None

    @classmethod
    def from_dict(cls, config_dict: dict) -> "PipelineConfig":
        """Create config from dictionary"""
        return cls(
            embedding=EmbeddingModelConfig(**config_dict.get("embedding", {})),
            chunks=ChunkProcessingConfig(**config_dict.get("chunks", {})),
            vector_store=VectorStoreConfig(
                **config_dict.get("vector_store", {})
            ),
            verbose=config_dict.get("verbose", True),
            log_file=config_dict.get("log_file"),
        )

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "embedding": self.embedding.__dict__,
            "chunks": self.chunks.__dict__,
            "vector_store": self.vector_store.__dict__,
            "verbose": self.verbose,
            "log_file": self.log_file,
        }


# Default config instance
DEFAULT_CONFIG = PipelineConfig()
