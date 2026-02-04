"""
Table Cleaner Module
====================

Xử lý các vấn đề với bảng markdown:
- Bảng bị lỗi format từ OCR
- Các hàng trống trong bảng
- Chuẩn hóa ký tự phân cách
- Sửa các cell bị merge không đúng
"""

import re
from typing import Optional, Dict, Any, List, Tuple

from .base import BaseCleaner, CleaningResult


class TableCleaner(BaseCleaner):
    """
    Cleaner xử lý các bảng markdown bị lỗi.

    Config options:
        fix_malformed_tables (bool): Sửa bảng bị lỗi format (default: True)
        remove_empty_rows (bool): Xóa hàng trống (default: True)
        normalize_separators (bool): Chuẩn hóa ký tự phân cách (default: True)
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.fix_malformed = self.config.get("fix_malformed_tables", True)
        self.remove_empty = self.config.get("remove_empty_rows", True)
        self.normalize_seps = self.config.get("normalize_separators", True)

    @property
    def name(self) -> str:
        return "TableCleaner"

    @property
    def description(self) -> str:
        return "Sửa các bảng markdown bị lỗi format từ OCR"

    def _is_table_line(self, line: str) -> bool:
        """Kiểm tra xem dòng có phải là một phần của bảng không."""
        stripped = line.strip()
        return "|" in stripped

    def _is_separator_line(self, line: str) -> bool:
        """Kiểm tra xem dòng có phải là separator line của bảng không."""
        stripped = line.strip()
        if not stripped.startswith("|") or not "|" in stripped:
            return False
        # Separator line chỉ chứa |, -, :, và spaces
        content_between_pipes = re.sub(r"\|", "", stripped)
        return bool(re.match(r"^[\s\-:]+$", content_between_pipes))

    def _count_columns(self, line: str) -> int:
        """Đếm số cột trong một dòng bảng."""
        stripped = line.strip()
        if stripped.startswith("|"):
            stripped = stripped[1:]
        if stripped.endswith("|"):
            stripped = stripped[:-1]
        return len(stripped.split("|"))

    def _normalize_table_row(self, line: str, expected_cols: int) -> str:
        """Chuẩn hóa một hàng bảng."""
        stripped = line.strip()

        # Đảm bảo bắt đầu và kết thúc bằng |
        if not stripped.startswith("|"):
            stripped = "| " + stripped
        if not stripped.endswith("|"):
            stripped = stripped + " |"

        # Đếm số cột hiện tại
        current_cols = self._count_columns(stripped)

        # Nếu thiếu cột, thêm cột trống
        if current_cols < expected_cols:
            # Thêm cột trống vào cuối
            cells = stripped.split("|")
            while len(cells) - 2 < expected_cols:  # -2 vì có | ở đầu và cuối
                cells.insert(-1, " ")
            stripped = "|".join(cells)

        return stripped

    def _create_separator(self, num_cols: int) -> str:
        """Tạo separator line cho bảng."""
        return "|" + "---|" * num_cols

    def _fix_duplicate_cell_content(self, line: str) -> str:
        """
        Sửa các cell bị duplicate content (lỗi OCR phổ biến).
        Ví dụ: "| 2 Vi phạm | 2 Vi phạm | 2 Vi phạm |" -> "| 2 Vi phạm | | |"
        """
        if "|" not in line:
            return line

        cells = line.split("|")
        cleaned_cells = []
        seen_content = {}

        for i, cell in enumerate(cells):
            stripped = cell.strip()
            if stripped and stripped in seen_content and len(stripped) > 10:
                # Cell này là duplicate, đánh dấu để merge
                cleaned_cells.append(" ")  # Cell trống
            else:
                cleaned_cells.append(cell)
                if stripped:
                    seen_content[stripped] = i

        return "|".join(cleaned_cells)

    def _extract_tables(self, content: str) -> List[Tuple[int, int, List[str]]]:
        """
        Trích xuất các bảng từ content.

        Returns:
            List of (start_idx, end_idx, table_lines)
        """
        lines = content.split("\n")
        tables = []
        current_table = []
        table_start = -1

        for i, line in enumerate(lines):
            if self._is_table_line(line):
                if table_start == -1:
                    table_start = i
                current_table.append(line)
            else:
                if current_table and len(current_table) > 1:
                    tables.append((table_start, i - 1, current_table))
                current_table = []
                table_start = -1

        # Xử lý bảng cuối cùng
        if current_table and len(current_table) > 1:
            tables.append((table_start, len(lines) - 1, current_table))

        return tables

    def _clean_table(self, table_lines: List[str]) -> List[str]:
        """Làm sạch một bảng."""
        cleaned = []

        # Xác định số cột từ header (dòng đầu tiên)
        if not table_lines:
            return cleaned

        expected_cols = self._count_columns(table_lines[0])
        has_separator = False

        for i, line in enumerate(table_lines):
            # Kiểm tra và sửa duplicate content
            if self.fix_malformed:
                line = self._fix_duplicate_cell_content(line)

            # Xóa hàng trống
            if self.remove_empty:
                cells = line.split("|")
                cell_contents = [c.strip() for c in cells if c.strip()]
                if not cell_contents:
                    continue

            # Chuẩn hóa separator
            if self._is_separator_line(line):
                has_separator = True
                if self.normalize_seps:
                    line = self._create_separator(expected_cols)
            else:
                # Chuẩn hóa số cột
                if self.fix_malformed:
                    line = self._normalize_table_row(line, expected_cols)

            cleaned.append(line)

        # Thêm separator nếu thiếu (sau header)
        if not has_separator and len(cleaned) > 0:
            separator = self._create_separator(expected_cols)
            cleaned.insert(1, separator)

        return cleaned

    def clean(self, content: str) -> CleaningResult:
        """
        Làm sạch các bảng trong nội dung.

        Args:
            content: Nội dung markdown

        Returns:
            CleaningResult với các bảng đã được sửa
        """
        result = CleaningResult(content=content)
        lines = content.split("\n")

        # Tìm và xử lý các bảng
        tables = self._extract_tables(content)

        if not tables:
            result.add_detail("Không tìm thấy bảng nào")
            return result

        result.add_detail(f"Tìm thấy {len(tables)} bảng")

        # Xử lý từ cuối lên để không bị lệch index
        for start_idx, end_idx, table_lines in reversed(tables):
            cleaned_table = self._clean_table(table_lines)

            # Thay thế bảng cũ bằng bảng mới
            lines = lines[:start_idx] + cleaned_table + lines[end_idx + 1 :]
            result.changes_made += 1

        result.content = "\n".join(lines)
        result.success = True
        result.add_detail(f"Đã xử lý {len(tables)} bảng")

        return result
