"""
Abstract Vector Store Interface
Thiết kế để dễ dàng switch giữa các vector databases:
- FAISS (local, fast, simple)
- PostgreSQL with pgvector (production, scalable)
- ChromaDB, Pinecone, Weaviate (cloud-based)
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass


@dataclass
class SearchResult:
    """Kết quả tìm kiếm chuẩn hóa"""

    chunk_id: str
    content: str
    metadata: Dict[str, Any]
    score: float
    embedding: Optional[List[float]] = None


@dataclass
class Document:
    """Document chuẩn hóa để lưu vào vector store"""

    id: str  # chunk_id hoặc unique ID
    content: str
    embedding: List[float]
    metadata: Dict[
        str, Any
    ]  # Bao gồm: source_file, chapter, article, level, etc.


class VectorStore(ABC):
    """
    Abstract base class cho vector database
    Implement class này để support các DB backends khác nhau
    """

    @abstractmethod
    def add_documents(
        self, documents: List[Document], batch_size: int = 100
    ) -> None:
        """
        Thêm documents vào vector store

        Args:
            documents: List các documents cần thêm
            batch_size: Batch size để tối ưu insert
        """
        pass

    @abstractmethod
    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[SearchResult]:
        """
        Semantic search

        Args:
            query_embedding: Vector của query
            top_k: Số lượng kết quả trả về
            filters: Metadata filters (e.g., {"source_file": "doc1.pdf", "chapter": "I"})

        Returns:
            List SearchResult đã được sort theo score
        """
        pass

    @abstractmethod
    def delete_by_metadata(self, filters: Dict[str, Any]) -> int:
        """
        Xóa documents theo metadata filter
        Useful khi muốn cập nhật lại 1 file cụ thể

        Args:
            filters: Metadata filters (e.g., {"source_file": "doc1.pdf"})

        Returns:
            Số lượng documents đã xóa
        """
        pass

    @abstractmethod
    def save(self, path: str) -> None:
        """
        Lưu vector store ra disk (cho FAISS)
        Hoặc persist/commit (cho DB-based stores)
        """
        pass

    @abstractmethod
    def load(self, path: str) -> None:
        """
        Load vector store từ disk hoặc connect tới existing DB
        """
        pass

    @abstractmethod
    def get_statistics(self) -> Dict[str, Any]:
        """
        Lấy thống kê về vector store

        Returns:
            Dict chứa: total_documents, dimension, source_files, etc.
        """
        pass

    # Extension point cho future hybrid search
    def hybrid_search(
        self,
        query_embedding: List[float],
        query_text: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        semantic_weight: float = 0.7,
    ) -> List[SearchResult]:
        """
        Hybrid search: Semantic + Keyword (BM25/FTS)

        Default implementation: chỉ semantic search
        Override trong subclass để implement hybrid search

        Args:
            query_embedding: Vector của query
            query_text: Text query (cho keyword search)
            top_k: Số lượng kết quả
            filters: Metadata filters
            semantic_weight: Trọng số semantic (0-1), phần còn lại là keyword
        """
        # Default: fall back to semantic search only
        return self.search(query_embedding, top_k, filters)


class VectorStoreConfig(ABC):
    """
    Abstract config cho từng loại vector store
    Subclass này để tạo config cụ thể cho FAISS, PostgreSQL, etc.
    """

    @abstractmethod
    def validate(self) -> None:
        """Validate config trước khi khởi tạo store"""
        pass
