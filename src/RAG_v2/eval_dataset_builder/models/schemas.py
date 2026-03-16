"""
Pydantic schemas cho RAG Evaluation Dataset Builder.

Định nghĩa tất cả data models:
- RetrievalConfig: cấu hình retrieval (collection, top_k, embedding_model)
- RetrievedChunk: chunk trả về từ Qdrant
- AnnotatedQuery: query đã được human annotate
- ExportRecord: record chuẩn để export CSV
"""

import uuid
from typing import List, Optional
from enum import Enum

from pydantic import BaseModel, Field, field_validator


# ============================================================
# Enums
# ============================================================

class EmbeddingModel(str, Enum):
    """Các embedding model được hỗ trợ."""
    E5 = "e5"
    BGE_M3 = "bge_m3"
    HYBRID = "hybrid"


class QueryType(str, Enum):
    """Loại câu hỏi."""
    FACTOID = "factoid"
    MULTI_HOP = "multi-hop"
    SUMMARIZATION = "summarization"
    BOOLEAN = "boolean"


class Difficulty(str, Enum):
    """Độ khó của câu hỏi."""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


# ============================================================
# Core Models
# ============================================================

class RetrievalConfig(BaseModel):
    """Cấu hình retrieval — Phase 1.

    Lưu kèm từng record để phục vụ so sánh sau.
    Hybrid search có thêm các config: vector_weight, keyword_weight,
    vector_pool_k, keyword_pool_k, vector_top_k, keyword_top_k.

    Attributes:
        collections: Danh sách Qdrant collection names đã chọn.
        top_k: Số chunks kết quả cuối cùng trả về.
        embedding_model: Embedding model đang dùng (e5 / bge_m3 / hybrid).
        vector_weight: Weight cho vector score trong hybrid fusion.
        keyword_weight: Weight cho keyword (BM25) score trong hybrid fusion.
        vector_top_k: Số candidates fetch từ Qdrant mỗi collection.
        keyword_top_k: Số candidates fetch từ Elasticsearch mỗi collection.
        vector_pool_k: Kích thước pool vector toàn cục sau khi merge.
        keyword_pool_k: Kích thước pool keyword toàn cục sau khi merge.
    """
    collections: List[str] = Field(
        ...,
        min_length=1,
        description="Qdrant collection name(s)",
    )
    top_k: int = Field(
        default=10,
        gt=0,
        description="Số chunks kết quả cuối cùng",
    )
    embedding_model: EmbeddingModel = Field(
        ...,
        description="Embedding model đang dùng",
    )
    # --- Hybrid search config (chỉ dùng khi embedding_model = hybrid) ---
    vector_weight: float = Field(
        default=1.0,
        ge=0.0,
        description="Weight cho vector score (hybrid fusion)",
    )
    keyword_weight: float = Field(
        default=0.0,
        ge=0.0,
        description="Weight cho keyword/BM25 score (hybrid fusion)",
    )
    vector_top_k: int = Field(
        default=20,
        gt=0,
        description="Candidates từ Qdrant mỗi collection",
    )
    keyword_top_k: int = Field(
        default=20,
        gt=0,
        description="Candidates từ Elasticsearch mỗi collection",
    )
    vector_pool_k: int = Field(
        default=15,
        gt=0,
        description="Pool vector toàn cục sau merge",
    )
    keyword_pool_k: int = Field(
        default=15,
        gt=0,
        description="Pool keyword toàn cục sau merge",
    )

    def config_label(self) -> str:
        """Tạo label mô tả config (dùng cho so sánh / filename)."""
        if self.embedding_model == EmbeddingModel.HYBRID:
            return (
                f"hybrid_v{self.vector_weight:.1f}_k{self.keyword_weight:.1f}"
                f"_vp{self.vector_pool_k}_kp{self.keyword_pool_k}"
            )
        return self.embedding_model.value


class RetrievedChunk(BaseModel):
    """Một chunk trả về từ Qdrant — Phase 2.

    Attributes:
        chunk_id: ID của chunk trong Qdrant (point ID).
        score: Similarity score từ Qdrant.
        text: Nội dung text đầy đủ của chunk.
        collection: Collection chứa chunk này.
        metadata: Metadata gốc của chunk (source, page, ...).
    """
    chunk_id: str = Field(..., description="Qdrant point ID")
    score: float = Field(..., description="Similarity score")
    text: str = Field(..., description="Nội dung text đầy đủ")
    collection: str = Field(..., description="Collection chứa chunk")
    metadata: dict = Field(default_factory=dict, description="Metadata gốc")


class AnnotatedQuery(BaseModel):
    """Một query đã được human annotate — Phase 3.

    Attributes:
        id: UUID v4, auto-generate, không cho phép chỉnh sửa.
        query: Câu hỏi human nhập.
        query_type: Loại câu hỏi (factoid, multi-hop, ...).
        difficulty: Độ khó (easy, medium, hard).
        expected_answer: Câu trả lời tham chiếu (optional).
        relevant_doc_ids: Danh sách chunk IDs được tick là relevant.
        retrieved_chunks: Tất cả chunks đã retrieve (để hiển thị).
        config: Retrieval config đã dùng cho query này.
    """
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="UUID v4, auto-generate",
    )
    query: str = Field(..., min_length=1, description="Câu hỏi")
    query_type: QueryType = Field(..., description="Loại câu hỏi")
    difficulty: Difficulty = Field(..., description="Độ khó")
    expected_answer: Optional[str] = Field(
        default=None,
        description="Câu trả lời tham chiếu (optional)",
    )
    relevant_doc_ids: List[str] = Field(
        ...,
        min_length=1,
        description="Chunk IDs được tick relevant (≥ 1)",
    )
    retrieved_chunks: List[RetrievedChunk] = Field(
        default_factory=list,
        description="Tất cả chunks đã retrieve",
    )
    config: RetrievalConfig = Field(..., description="Retrieval config đã dùng")

    @field_validator("relevant_doc_ids")
    @classmethod
    def validate_relevant_doc_ids(cls, v: List[str]) -> List[str]:
        """Phải có ít nhất 1 chunk relevant."""
        if len(v) < 1:
            raise ValueError("Phải tick ít nhất 1 chunk relevant")
        return v


class ExportRecord(BaseModel):
    """Record chuẩn để export CSV — Phase 4.

    Đúng thứ tự 17 cột theo spec.
    Các cột eval (từ retrieved_doc_ids trở đi) luôn để trống.

    Attributes:
        id: UUID v4.
        query: Câu hỏi.
        query_type: Annotation.
        difficulty: Annotation.
        expected_answer: Optional.
        relevant_doc_ids: JSON array string.
        top_k: Config.
        embedding_model: Config.
        retrieved_doc_ids: Để trống (eval phase).
        retrieved_scores: Để trống (eval phase).
        llm_output: Để trống (eval phase).
        hit_at_1: Để trống (eval phase).
        hit_at_k: Để trống (eval phase).
        precision_at_k: Để trống (eval phase).
        recall_at_k: Để trống (eval phase).
        mrr: Để trống (eval phase).
        latency_ms: Để trống (eval phase).
    """
    id: str
    query: str
    query_type: str
    difficulty: str
    expected_answer: str = ""
    relevant_doc_ids: str  # JSON array string
    top_k: int
    embedding_model: str
    # --- Eval columns — luôn để trống ---
    retrieved_doc_ids: str = ""
    retrieved_scores: str = ""
    llm_output: str = ""
    hit_at_1: str = ""
    hit_at_k: str = ""
    precision_at_k: str = ""
    recall_at_k: str = ""
    mrr: str = ""
    latency_ms: str = ""

    @classmethod
    def from_annotated_query(cls, aq: AnnotatedQuery) -> "ExportRecord":
        """Chuyển AnnotatedQuery → ExportRecord để export CSV.

        Args:
            aq: AnnotatedQuery đã validate.

        Returns:
            ExportRecord với các cột eval để trống.
        """
        import json

        # embedding_model: bao gồm cả config label cho hybrid
        if aq.config.embedding_model == EmbeddingModel.HYBRID:
            model_str = aq.config.config_label()
        else:
            model_str = aq.config.embedding_model.value

        return cls(
            id=aq.id,
            query=aq.query,
            query_type=aq.query_type.value,
            difficulty=aq.difficulty.value,
            expected_answer=aq.expected_answer or "",
            relevant_doc_ids=json.dumps(aq.relevant_doc_ids),
            top_k=aq.config.top_k,
            embedding_model=model_str,
        )

    @classmethod
    def csv_columns(cls) -> List[str]:
        """Trả về danh sách tên cột CSV theo đúng thứ tự spec."""
        return [
            "id",
            "query",
            "query_type",
            "difficulty",
            "expected_answer",
            "relevant_doc_ids",
            "top_k",
            "embedding_model",
            "retrieved_doc_ids",
            "retrieved_scores",
            "llm_output",
            "hit@1",
            "hit@k",
            "precision@k",
            "recall@k",
            "mrr",
            "latency_ms",
        ]

    def to_csv_row(self) -> dict:
        """Chuyển thành dict để viết CSV row.

        Returns:
            dict với keys là tên cột CSV (dùng @ thay vì _at_).
        """
        return {
            "id": self.id,
            "query": self.query,
            "query_type": self.query_type,
            "difficulty": self.difficulty,
            "expected_answer": self.expected_answer,
            "relevant_doc_ids": self.relevant_doc_ids,
            "top_k": self.top_k,
            "embedding_model": self.embedding_model,
            "retrieved_doc_ids": self.retrieved_doc_ids,
            "retrieved_scores": self.retrieved_scores,
            "llm_output": self.llm_output,
            "hit@1": self.hit_at_1,
            "hit@k": self.hit_at_k,
            "precision@k": self.precision_at_k,
            "recall@k": self.recall_at_k,
            "mrr": self.mrr,
            "latency_ms": self.latency_ms,
        }
