"""
Duplicate Line Cleaner Module
=============================

Xử lý các dòng bị lặp lại:
- Dòng duplicate liên tiếp (do OCR scan nhiều lần)
- Dòng gần giống nhau (similarity check)
"""

import re
from typing import Optional, Dict, Any, List
from difflib import SequenceMatcher

from .base import BaseCleaner, CleaningResult


class DuplicateLineCleaner(BaseCleaner):
    """
    Cleaner xử lý các dòng bị lặp lại.

    Config options:
        remove_exact_duplicates (bool): Xóa duplicate chính xác (default: True)
        similarity_threshold (float): Ngưỡng similarity để coi là duplicate (default: 0.95)
        min_line_length (int): Độ dài tối thiểu để check similarity (default: 10)
        consecutive_only (bool): Chỉ xóa duplicate liên tiếp (default: True)
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.remove_exact = self.config.get("remove_exact_duplicates", True)
        self.similarity_threshold = self.config.get(
            "similarity_threshold", 0.95
        )
        self.min_length = self.config.get("min_line_length", 10)
        self.consecutive_only = self.config.get("consecutive_only", True)

    @property
    def name(self) -> str:
        return "DuplicateLineCleaner"

    @property
    def description(self) -> str:
        return "Xóa các dòng bị lặp lại do OCR"

    def _similarity(self, str1: str, str2: str) -> float:
        """
        Tính độ tương đồng giữa 2 string.

        Returns:
            Float từ 0 đến 1
        """
        return SequenceMatcher(None, str1, str2).ratio()

    def _normalize_for_comparison(self, line: str) -> str:
        """Chuẩn hóa dòng để so sánh."""
        # Lowercase, remove extra spaces, remove punctuation
        normalized = line.lower().strip()
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized

    def _remove_consecutive_duplicates(
        self, lines: List[str]
    ) -> tuple[List[str], int]:
        """
        Xóa các dòng duplicate liên tiếp.

        Returns:
            (cleaned_lines, removed_count)
        """
        if not lines:
            return lines, 0

        cleaned = [lines[0]]
        removed = 0

        for i in range(1, len(lines)):
            current = self._normalize_for_comparison(lines[i])
            previous = self._normalize_for_comparison(lines[i - 1])

            # Bỏ qua dòng trống
            if not current.strip():
                cleaned.append(lines[i])
                continue

            # Check exact duplicate
            if self.remove_exact and current == previous:
                removed += 1
                self.logger.debug(
                    f"Removing exact duplicate: '{lines[i][:50]}...'"
                )
                continue

            # Check similar lines (nếu đủ dài)
            if (
                len(current) >= self.min_length
                and len(previous) >= self.min_length
            ):
                similarity = self._similarity(current, previous)
                if similarity >= self.similarity_threshold:
                    removed += 1
                    self.logger.debug(
                        f"Removing similar line (sim={similarity:.2f}): '{lines[i][:50]}...'"
                    )
                    continue

            cleaned.append(lines[i])

        return cleaned, removed

    def _remove_global_duplicates(
        self, lines: List[str]
    ) -> tuple[List[str], int]:
        """
        Xóa các dòng duplicate không liên tiếp (toàn bộ document).
        Giữ lại occurrence đầu tiên.

        Returns:
            (cleaned_lines, removed_count)
        """
        seen = set()
        cleaned = []
        removed = 0

        for line in lines:
            normalized = self._normalize_for_comparison(line)

            # Bỏ qua dòng trống và dòng ngắn
            if not normalized.strip() or len(normalized) < self.min_length:
                cleaned.append(line)
                continue

            # Check if seen before
            if normalized in seen:
                removed += 1
                self.logger.debug(
                    f"Removing global duplicate: '{line[:50]}...'"
                )
                continue

            seen.add(normalized)
            cleaned.append(line)

        return cleaned, removed

    def _remove_paragraph_duplicates(self, content: str) -> tuple[str, int]:
        """
        Xóa các đoạn văn bị duplicate.
        Thường xảy ra khi OCR scan cùng một trang nhiều lần.
        """
        # Split thành các paragraphs (separated by 2+ newlines)
        paragraphs = re.split(r"\n{2,}", content)

        seen = set()
        cleaned = []
        removed = 0

        for para in paragraphs:
            normalized = self._normalize_for_comparison(para)

            # Bỏ qua paragraph ngắn
            if len(normalized) < 50:
                cleaned.append(para)
                continue

            # Check similarity với các paragraph đã thấy
            is_duplicate = False
            for seen_para in seen:
                if (
                    self._similarity(normalized, seen_para)
                    >= self.similarity_threshold
                ):
                    removed += 1
                    is_duplicate = True
                    break

            if not is_duplicate:
                seen.add(normalized)
                cleaned.append(para)

        return "\n\n".join(cleaned), removed

    def clean(self, content: str) -> CleaningResult:
        """
        Xóa các duplicate trong nội dung.

        Args:
            content: Nội dung markdown

        Returns:
            CleaningResult với các duplicates đã được xóa
        """
        result = CleaningResult(content=content)
        total_removed = 0

        # 1. Xóa consecutive duplicates (luôn làm)
        lines = content.split("\n")
        cleaned_lines, removed = self._remove_consecutive_duplicates(lines)
        if removed > 0:
            result.add_detail(f"Xóa {removed} dòng duplicate liên tiếp")
            total_removed += removed

        # 2. Xóa global duplicates (nếu không chỉ consecutive)
        if not self.consecutive_only:
            cleaned_lines, removed = self._remove_global_duplicates(
                cleaned_lines
            )
            if removed > 0:
                result.add_detail(
                    f"Xóa {removed} dòng duplicate không liên tiếp"
                )
                total_removed += removed

        content = "\n".join(cleaned_lines)

        # 3. Xóa paragraph duplicates
        content, removed = self._remove_paragraph_duplicates(content)
        if removed > 0:
            result.add_detail(f"Xóa {removed} đoạn văn duplicate")
            total_removed += removed

        result.content = content
        result.changes_made = total_removed
        result.success = True

        return result
