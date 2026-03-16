"""
AnnotationSession — Quản lý human annotation.

Phase 3: Tick relevant chunks, điền metadata, lưu annotation.

Chức năng chính:
- CRUD annotations (add, update, delete, get)
- Session persistence (save/load JSON)
- Progress tracking (count, by_type, by_difficulty)
- Validation (≥ 1 relevant chunk, no duplicate queries)
- Lookup by UUID
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ..models.schemas import (
    AnnotatedQuery,
    Difficulty,
    QueryType,
    RetrievalConfig,
    RetrievedChunk,
)

logger = logging.getLogger(__name__)


class AnnotationSession:
    """Quản lý annotation session cho nhiều queries.

    Lưu trữ tất cả annotated queries trong session,
    hỗ trợ xem lại, sửa, save/load, và export.

    Attributes:
        name: Tên session (dùng cho filename khi save).
        created_at: Thời điểm tạo session.
        annotations: Danh sách queries đã annotate.
    """

    def __init__(self, name: str = "eval_session") -> None:
        """Khởi tạo session rỗng.

        Args:
            name: Tên session (dùng cho filename khi save).
        """
        self.name = name
        self.created_at = datetime.now(timezone.utc).isoformat()
        self._annotations: List[AnnotatedQuery] = []
        logger.info("AnnotationSession '%s' created.", name)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def annotations(self) -> List[AnnotatedQuery]:
        """Trả về danh sách annotations (read-only copy)."""
        return list(self._annotations)

    @property
    def count(self) -> int:
        """Số lượng queries đã annotate."""
        return len(self._annotations)

    @property
    def total_relevant_chunks(self) -> int:
        """Tổng số relevant chunks đã chọn trong toàn session."""
        return sum(len(aq.relevant_doc_ids) for aq in self._annotations)

    # ------------------------------------------------------------------
    # CRUD — Add
    # ------------------------------------------------------------------

    def add_annotation(
        self,
        query: str,
        query_type: QueryType,
        difficulty: Difficulty,
        relevant_doc_ids: List[str],
        retrieved_chunks: List[RetrievedChunk],
        config: RetrievalConfig,
        expected_answer: Optional[str] = None,
    ) -> AnnotatedQuery:
        """Thêm một annotation mới vào session.

        UUID v4 được auto-generate bởi AnnotatedQuery.
        Validate: relevant_doc_ids ≥ 1 (enforced by Pydantic).

        Args:
            query: Câu hỏi.
            query_type: Loại câu hỏi.
            difficulty: Độ khó.
            relevant_doc_ids: Chunk IDs relevant (≥ 1).
            retrieved_chunks: Tất cả chunks đã retrieve.
            config: Retrieval config.
            expected_answer: Câu trả lời tham chiếu (optional).

        Returns:
            AnnotatedQuery mới tạo (với UUID auto-generated).

        Raises:
            ValueError: Nếu relevant_doc_ids rỗng hoặc query trùng.
        """
        # Validate relevant_doc_ids not empty (cũng được Pydantic check)
        if not relevant_doc_ids:
            raise ValueError("Phải tick ít nhất 1 chunk relevant")

        # Validate relevant_doc_ids nằm trong retrieved chunks
        retrieved_ids = {c.chunk_id for c in retrieved_chunks}
        invalid_ids = [rid for rid in relevant_doc_ids if rid not in retrieved_ids]
        if invalid_ids:
            raise ValueError(
                f"relevant_doc_ids không hợp lệ (không nằm trong retrieved chunks): "
                f"{invalid_ids}"
            )

        annotation = AnnotatedQuery(
            query=query,
            query_type=query_type,
            difficulty=difficulty,
            expected_answer=expected_answer,
            relevant_doc_ids=relevant_doc_ids,
            retrieved_chunks=retrieved_chunks,
            config=config,
        )
        self._annotations.append(annotation)

        logger.info(
            "Added annotation #%d: query='%s', relevant=%d chunks, id=%s",
            self.count,
            query[:50],
            len(relevant_doc_ids),
            annotation.id,
        )
        return annotation

    # ------------------------------------------------------------------
    # CRUD — Update
    # ------------------------------------------------------------------

    def update_annotation(
        self,
        index: int,
        query_type: Optional[QueryType] = None,
        difficulty: Optional[Difficulty] = None,
        relevant_doc_ids: Optional[List[str]] = None,
        expected_answer: Optional[str] = "__UNCHANGED__",
    ) -> AnnotatedQuery:
        """Cập nhật annotation đã tồn tại.

        Chỉ cập nhật các field được truyền vào.
        Không cho phép sửa: id, query, config, retrieved_chunks.

        Note: expected_answer dùng sentinel "__UNCHANGED__" để phân biệt
        None (muốn xóa answer) với không truyền (giữ nguyên).

        Args:
            index: Vị trí annotation trong session (0-indexed).
            query_type: Loại câu hỏi mới (None = giữ nguyên).
            difficulty: Độ khó mới (None = giữ nguyên).
            relevant_doc_ids: Chunk IDs relevant mới (None = giữ nguyên, ≥ 1).
            expected_answer: Trả lời mới ("__UNCHANGED__" = giữ nguyên, None = xóa).

        Returns:
            AnnotatedQuery đã cập nhật.

        Raises:
            IndexError: Nếu index không hợp lệ.
            ValueError: Nếu relevant_doc_ids rỗng.
        """
        self._validate_index(index)
        current = self._annotations[index]

        # Resolve new values
        new_relevant = (
            relevant_doc_ids if relevant_doc_ids is not None
            else current.relevant_doc_ids
        )
        new_expected = (
            current.expected_answer if expected_answer == "__UNCHANGED__"
            else expected_answer
        )

        # Validate relevant_doc_ids
        if not new_relevant:
            raise ValueError("Phải tick ít nhất 1 chunk relevant")

        updated = AnnotatedQuery(
            id=current.id,  # Giữ nguyên UUID
            query=current.query,  # Giữ nguyên query
            query_type=query_type if query_type is not None else current.query_type,
            difficulty=difficulty if difficulty is not None else current.difficulty,
            expected_answer=new_expected,
            relevant_doc_ids=new_relevant,
            retrieved_chunks=current.retrieved_chunks,  # Giữ nguyên
            config=current.config,  # Giữ nguyên
        )

        self._annotations[index] = updated
        logger.info("Updated annotation #%d (id=%s)", index, updated.id)
        return updated

    # ------------------------------------------------------------------
    # CRUD — Delete / Get
    # ------------------------------------------------------------------

    def delete_annotation(self, index: int) -> AnnotatedQuery:
        """Xóa annotation theo index.

        Args:
            index: Vị trí annotation (0-indexed).

        Returns:
            AnnotatedQuery đã xóa.

        Raises:
            IndexError: Nếu index không hợp lệ.
        """
        self._validate_index(index)
        removed = self._annotations.pop(index)
        logger.info("Deleted annotation #%d (id=%s)", index, removed.id)
        return removed

    def get_annotation(self, index: int) -> AnnotatedQuery:
        """Lấy annotation theo index.

        Args:
            index: Vị trí annotation (0-indexed).

        Returns:
            AnnotatedQuery tại vị trí index.

        Raises:
            IndexError: Nếu index không hợp lệ.
        """
        self._validate_index(index)
        return self._annotations[index]

    def get_by_id(self, annotation_id: str) -> Optional[AnnotatedQuery]:
        """Tìm annotation theo UUID.

        Args:
            annotation_id: UUID v4 string.

        Returns:
            AnnotatedQuery hoặc None nếu không tìm thấy.
        """
        for aq in self._annotations:
            if aq.id == annotation_id:
                return aq
        return None

    def clear(self) -> None:
        """Xóa toàn bộ annotations trong session."""
        count = self.count
        self._annotations.clear()
        logger.info("Cleared %d annotations from session.", count)

    # ------------------------------------------------------------------
    # Progress tracking
    # ------------------------------------------------------------------

    def get_progress_summary(self) -> Dict[str, Any]:
        """Trả về thông tin tiến độ annotation.

        Returns:
            dict với keys:
            - total_queries: int
            - total_relevant_chunks: int
            - queries_by_type: {type: count}
            - queries_by_difficulty: {difficulty: count}
            - avg_relevant_per_query: float
            - queries_list: [{index, id, query_preview, relevant_count, type, difficulty}]
        """
        by_type: Dict[str, int] = {}
        by_difficulty: Dict[str, int] = {}
        queries_list: List[Dict[str, Any]] = []

        for i, aq in enumerate(self._annotations):
            qt = aq.query_type.value
            by_type[qt] = by_type.get(qt, 0) + 1

            diff = aq.difficulty.value
            by_difficulty[diff] = by_difficulty.get(diff, 0) + 1

            queries_list.append({
                "index": i,
                "id": aq.id,
                "query_preview": aq.query[:80] + ("..." if len(aq.query) > 80 else ""),
                "relevant_count": len(aq.relevant_doc_ids),
                "query_type": qt,
                "difficulty": diff,
                "has_expected_answer": aq.expected_answer is not None
                    and aq.expected_answer.strip() != "",
            })

        total = self.count
        total_rel = self.total_relevant_chunks

        return {
            "total_queries": total,
            "total_relevant_chunks": total_rel,
            "avg_relevant_per_query": round(total_rel / total, 2) if total > 0 else 0,
            "queries_by_type": by_type,
            "queries_by_difficulty": by_difficulty,
            "queries_list": queries_list,
        }

    # ------------------------------------------------------------------
    # Session persistence — Save / Load JSON
    # ------------------------------------------------------------------

    def save(self, output_dir: Union[str, Path]) -> Path:
        """Lưu session ra file JSON.

        File name: {output_dir}/{self.name}.json

        Args:
            output_dir: Thư mục output.

        Returns:
            Path đến file JSON đã tạo.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        filepath = output_dir / f"{self.name}.json"

        data = {
            "name": self.name,
            "created_at": self.created_at,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "count": self.count,
            "annotations": [aq.model_dump() for aq in self._annotations],
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)

        logger.info("Session saved to %s (%d annotations)", filepath, self.count)
        return filepath

    @classmethod
    def load(cls, filepath: Union[str, Path]) -> "AnnotationSession":
        """Load session từ file JSON.

        Args:
            filepath: Đường dẫn file JSON.

        Returns:
            AnnotationSession đã restore.

        Raises:
            FileNotFoundError: Nếu file không tồn tại.
        """
        filepath = Path(filepath)
        if not filepath.exists():
            raise FileNotFoundError(f"Session file not found: {filepath}")

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        session = cls(name=data.get("name", "loaded_session"))
        session.created_at = data.get("created_at", session.created_at)

        for aq_data in data.get("annotations", []):
            annotation = AnnotatedQuery(**aq_data)
            session._annotations.append(annotation)

        logger.info(
            "Session loaded from %s (%d annotations)",
            filepath,
            session.count,
        )
        return session

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    def _validate_index(self, index: int) -> None:
        """Validate index nằm trong range.

        Args:
            index: 0-indexed position.

        Raises:
            IndexError: Nếu index không hợp lệ.
        """
        if index < 0 or index >= len(self._annotations):
            raise IndexError(
                f"Index {index} không hợp lệ. "
                f"Session có {len(self._annotations)} annotations (0-{len(self._annotations) - 1})."
            )

    def validate_session(self) -> List[str]:
        """Validate toàn bộ session trước khi export.

        Checks:
        - Mỗi annotation có ≥ 1 relevant chunk
        - Không có duplicate UUIDs
        - Tất cả required fields có giá trị

        Returns:
            List[str] các lỗi tìm thấy. Rỗng = valid.
        """
        errors: List[str] = []
        seen_ids: set = set()

        for i, aq in enumerate(self._annotations):
            # Check duplicate UUID
            if aq.id in seen_ids:
                errors.append(f"[#{i}] Duplicate UUID: {aq.id}")
            seen_ids.add(aq.id)

            # Check relevant_doc_ids
            if not aq.relevant_doc_ids:
                errors.append(f"[#{i}] Query '{aq.query[:40]}' không có relevant chunks")

            # Check query not empty
            if not aq.query.strip():
                errors.append(f"[#{i}] Query rỗng (id={aq.id})")

        if errors:
            logger.warning("Session validation found %d errors", len(errors))
        else:
            logger.info("Session validation passed (%d annotations)", self.count)

        return errors
