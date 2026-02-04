"""
Header Footer Cleaner Module
============================

Xử lý các artifact từ header/footer của văn bản:
- Số trang
- Header lặp lại (tên trường, logo text)
- Footer lặp lại
- Watermark text
"""

import re
from typing import Optional, Dict, Any, List, Pattern

from .base import BaseCleaner, CleaningResult


class HeaderFooterCleaner(BaseCleaner):
    """
    Cleaner xử lý header/footer artifacts.

    Config options:
        remove_page_numbers (bool): Xóa số trang (default: True)
        remove_header_patterns (List[str]): Các pattern header cần xóa
        remove_footer_patterns (List[str]): Các pattern footer cần xóa
        remove_watermarks (bool): Xóa watermark text (default: True)
    """

    DEFAULT_HEADER_PATTERNS = [
        r"^BỘ GIÁO DỤC VÀ ĐÀO TẠO\s*$",
        r"^(TRƯỜNG\s+)?Đ(ẠI\s+)?H(ỌC\s+)?BÁCH KHOA HÀ NỘI\s*$",
        r"^ĐẠI HỌC BÁCH KHOA HÀ NỘI\s*$",
        r"^DHBK\s+HÀ\s+NỘI\s*$",
        r"^CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM\s*$",
        r"^Độc lập\s*[-–]\s*Tự do\s*[-–]\s*Hạnh phúc\s*$",
        r"^_{3,}\s*$",  # Dòng gạch ngang
        r"^\*{3,}\s*$",  # Dòng sao
    ]

    DEFAULT_FOOTER_PATTERNS = [
        r"^\d{1,3}\s*$",  # Số trang đơn lẻ (1-999)
        r"^Trang\s+\d+\s*(\/\s*\d+)?\s*$",  # "Trang X" hoặc "Trang X/Y"
        r"^Page\s+\d+\s*(of\s+\d+)?\s*$",  # English page numbers
        r"^-\s*\d+\s*-\s*$",  # - X -
    ]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.remove_page_nums = self.config.get("remove_page_numbers", True)
        self.remove_watermarks = self.config.get("remove_watermarks", True)

        # Compile patterns
        header_patterns = self.config.get(
            "header_patterns", self.DEFAULT_HEADER_PATTERNS
        )
        footer_patterns = self.config.get(
            "footer_patterns", self.DEFAULT_FOOTER_PATTERNS
        )

        self.header_patterns: List[Pattern] = [
            re.compile(p, re.IGNORECASE | re.UNICODE) for p in header_patterns
        ]
        self.footer_patterns: List[Pattern] = [
            re.compile(p, re.IGNORECASE | re.UNICODE) for p in footer_patterns
        ]

    @property
    def name(self) -> str:
        return "HeaderFooterCleaner"

    @property
    def description(self) -> str:
        return "Xóa header/footer artifacts: số trang, tên trường lặp lại"

    def _should_remove_line(self, line: str) -> tuple[bool, str]:
        """
        Kiểm tra xem dòng có nên bị xóa không.

        Returns:
            (should_remove, reason)
        """
        stripped = line.strip()

        if not stripped:
            return False, ""

        # Check header patterns
        for pattern in self.header_patterns:
            if pattern.match(stripped):
                return True, f"Header pattern: {pattern.pattern[:30]}..."

        # Check footer patterns
        if self.remove_page_nums:
            for pattern in self.footer_patterns:
                if pattern.match(stripped):
                    return True, f"Footer pattern: {pattern.pattern[:30]}..."

        # Check for standalone numbers at beginning/end of file (likely page numbers)
        if self.remove_page_nums and stripped.isdigit() and len(stripped) <= 3:
            return True, "Standalone page number"

        return False, ""

    def _remove_repeated_headers(
        self, lines: List[str]
    ) -> tuple[List[str], int]:
        """
        Xóa các header bị lặp lại nhiều lần trong document.
        Giữ lại header đầu tiên.
        """
        seen_headers = {}
        cleaned_lines = []
        removed_count = 0

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Kiểm tra có phải header pattern không
            is_header = False
            for pattern in self.header_patterns:
                if pattern.match(stripped):
                    is_header = True
                    break

            if is_header:
                # Nếu đã thấy header này ở gần đầu file, bỏ qua các lần lặp sau
                if stripped in seen_headers and seen_headers[stripped] < 20:
                    removed_count += 1
                    continue
                else:
                    seen_headers[stripped] = i

            cleaned_lines.append(line)

        return cleaned_lines, removed_count

    def _clean_noi_nhan_section(self, content: str) -> tuple[str, int]:
        """
        Xử lý phần "Nơi nhận:" - giữ nguyên không xóa.
        Phần này thường xuất hiện ở cuối văn bản hành chính.
        """
        # Pattern cho phần Nơi nhận
        noi_nhan_pattern = re.compile(
            r"(Nơi nhận:\s*\n(?:[-–]\s*[^\n]+\n?)+)", re.IGNORECASE | re.UNICODE
        )

        # Đánh dấu để không xử lý phần này
        matches = list(noi_nhan_pattern.finditer(content))
        return content, 0  # Giữ nguyên phần này

    def clean(self, content: str) -> CleaningResult:
        """
        Làm sạch header/footer artifacts.

        Args:
            content: Nội dung markdown

        Returns:
            CleaningResult với các artifacts đã được xóa
        """
        result = CleaningResult(content=content)
        lines = content.split("\n")
        removed_count = 0

        # 1. Xóa các dòng match với patterns
        cleaned_lines = []
        for line in lines:
            should_remove, reason = self._should_remove_line(line)
            if should_remove:
                removed_count += 1
                self.logger.debug(f"Removing line: '{line[:50]}...' - {reason}")
            else:
                cleaned_lines.append(line)

        if removed_count > 0:
            result.add_detail(f"Xóa {removed_count} dòng header/footer")

        # 2. Xóa headers bị lặp lại
        cleaned_lines, repeated_removed = self._remove_repeated_headers(
            cleaned_lines
        )
        if repeated_removed > 0:
            result.add_detail(f"Xóa {repeated_removed} header lặp lại")
            removed_count += repeated_removed

        result.content = "\n".join(cleaned_lines)
        result.changes_made = removed_count
        result.success = True

        return result
