"""
CSVExporter — Export annotated queries ra CSV chuẩn.

Phase 4: Serialize AnnotatedQuery → ExportRecord → CSV file.

Chức năng:
- Export ra file CSV (17 cột, đúng thứ tự spec)
- Export ra CSV string (cho Streamlit download button)
- Preview table (dạng list of dicts cho hiển thị)
- Validate trước khi export (UUID uniqueness, eval columns trống)
- Append mode (ghi thêm vào file CSV đã tồn tại)
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ..models.schemas import AnnotatedQuery, ExportRecord

logger = logging.getLogger(__name__)


class CSVExporter:
    """Export annotations ra file CSV chuẩn.

    CSV format theo spec:
    - 17 cột, đúng thứ tự
    - relevant_doc_ids = JSON array string, ví dụ: ["id1","id2"]
    - Các cột eval (từ retrieved_doc_ids trở đi) để trống
    - id = UUID v4, unique, không trùng giữa các batch

    Ràng buộc:
    - Các cột eval LUÔN để trống — không điền null, không điền 0
    - Export tất cả queries trong session → 1 file CSV

    Example:
        >>> exporter = CSVExporter()
        >>> exporter.export(session.annotations, "output.csv")
        >>> csv_string = exporter.export_to_string(session.annotations)
    """

    COLUMNS = ExportRecord.csv_columns()

    # ------------------------------------------------------------------
    # Export to file
    # ------------------------------------------------------------------

    @staticmethod
    def export(
        annotations: List[AnnotatedQuery],
        output_path: Union[str, Path],
        overwrite: bool = True,
    ) -> Path:
        """Export annotations ra file CSV.

        Args:
            annotations: Danh sách queries đã annotate.
            output_path: Đường dẫn file CSV output.
            overwrite: True = ghi đè, False = append vào file đã có.

        Returns:
            Path đến file CSV đã tạo.

        Raises:
            ValueError: Nếu annotations rỗng hoặc validation fail.
        """
        CSVExporter._validate(annotations)

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        records = CSVExporter._to_records(annotations)
        columns = CSVExporter.COLUMNS

        # Determine write mode
        file_exists = output_path.exists()
        if overwrite or not file_exists:
            mode = "w"
            write_header = True
        else:
            mode = "a"
            write_header = False

        with open(output_path, mode, newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            if write_header:
                writer.writeheader()
            for record in records:
                writer.writerow(record.to_csv_row())

        logger.info(
            "Exported %d records to %s (mode=%s)",
            len(records),
            output_path,
            "overwrite" if mode == "w" else "append",
        )
        return output_path

    # ------------------------------------------------------------------
    # Export to string (for Streamlit download)
    # ------------------------------------------------------------------

    @staticmethod
    def export_to_string(annotations: List[AnnotatedQuery]) -> str:
        """Export annotations ra CSV string.

        Dùng cho Streamlit download_button hoặc preview.

        Args:
            annotations: Danh sách queries đã annotate.

        Returns:
            CSV content as string (UTF-8).

        Raises:
            ValueError: Nếu annotations rỗng.
        """
        CSVExporter._validate(annotations)

        records = CSVExporter._to_records(annotations)
        columns = CSVExporter.COLUMNS

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=columns)
        writer.writeheader()
        for record in records:
            writer.writerow(record.to_csv_row())

        return output.getvalue()

    # ------------------------------------------------------------------
    # Preview table (for UI display before export)
    # ------------------------------------------------------------------

    @staticmethod
    def preview(
        annotations: List[AnnotatedQuery],
        include_eval_columns: bool = False,
    ) -> List[Dict[str, Any]]:
        """Tạo preview table để hiển thị trước khi export.

        Trả về list of dicts dễ dùng trong Streamlit st.dataframe().

        Args:
            annotations: Danh sách queries đã annotate.
            include_eval_columns: True = hiển thị cả cột eval (trống).

        Returns:
            List[dict] mỗi dict là 1 row.
        """
        if not annotations:
            return []

        records = CSVExporter._to_records(annotations)
        rows = []

        for record in records:
            row = record.to_csv_row()
            if not include_eval_columns:
                # Chỉ hiển thị các cột có data
                row = {
                    "id": row["id"][:8] + "...",  # Rút gọn UUID
                    "query": row["query"],
                    "query_type": row["query_type"],
                    "difficulty": row["difficulty"],
                    "expected_answer": row["expected_answer"][:50] + "..."
                        if len(row.get("expected_answer", "")) > 50
                        else row.get("expected_answer", ""),
                    "relevant_doc_ids": row["relevant_doc_ids"],
                    "top_k": row["top_k"],
                    "embedding_model": row["embedding_model"],
                }
            rows.append(row)

        return rows

    # ------------------------------------------------------------------
    # Generate filename
    # ------------------------------------------------------------------

    @staticmethod
    def generate_filename(
        prefix: str = "rag_eval_dataset",
        session_name: Optional[str] = None,
    ) -> str:
        """Tạo filename CSV theo pattern chuẩn.

        Format: {prefix}_{session}_{timestamp}.csv

        Args:
            prefix: Prefix cho filename.
            session_name: Tên session (optional).

        Returns:
            Filename string, ví dụ: "rag_eval_dataset_session1_20260311_205000.csv"
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        parts = [prefix]
        if session_name:
            parts.append(session_name)
        parts.append(timestamp)
        return "_".join(parts) + ".csv"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_records(annotations: List[AnnotatedQuery]) -> List[ExportRecord]:
        """Convert AnnotatedQuery list → ExportRecord list."""
        return [ExportRecord.from_annotated_query(aq) for aq in annotations]

    @staticmethod
    def _validate(annotations: List[AnnotatedQuery]) -> None:
        """Validate annotations trước khi export.

        Checks:
        - annotations không rỗng
        - Không có duplicate UUIDs
        - Mỗi annotation có ≥ 1 relevant chunk

        Raises:
            ValueError: Nếu validation fail.
        """
        if not annotations:
            raise ValueError("Không có annotation nào để export")

        # Check duplicate UUIDs
        ids = [aq.id for aq in annotations]
        if len(ids) != len(set(ids)):
            duplicates = [uid for uid in ids if ids.count(uid) > 1]
            raise ValueError(f"Duplicate UUIDs found: {set(duplicates)}")

        # Check relevant_doc_ids
        for i, aq in enumerate(annotations):
            if not aq.relevant_doc_ids:
                raise ValueError(
                    f"Annotation #{i} (query='{aq.query[:40]}') "
                    f"không có relevant chunks"
                )

        logger.info("Validation passed for %d annotations", len(annotations))
