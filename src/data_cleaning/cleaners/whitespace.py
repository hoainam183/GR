"""
Whitespace Cleaner Module
=========================

Xử lý các vấn đề liên quan đến khoảng trắng:
- Dòng trống thừa
- Khoảng trắng cuối dòng
- Khoảng trắng đầu dòng không cần thiết
"""

import re
from typing import Optional, Dict, Any

from .base import BaseCleaner, CleaningResult


class WhitespaceCleaner(BaseCleaner):
    """
    Cleaner xử lý khoảng trắng thừa trong markdown.

    Config options:
        max_consecutive_blank_lines (int): Số dòng trống tối đa cho phép (default: 2)
        trim_trailing_whitespace (bool): Xóa khoảng trắng cuối dòng (default: True)
        normalize_line_endings (bool): Chuẩn hóa xuống dòng (default: True)
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.max_blank_lines = self.config.get("max_consecutive_blank_lines", 2)
        self.trim_trailing = self.config.get("trim_trailing_whitespace", True)
        self.normalize_endings = self.config.get("normalize_line_endings", True)

    @property
    def name(self) -> str:
        return "WhitespaceCleaner"

    @property
    def description(self) -> str:
        return "Xử lý khoảng trắng thừa: dòng trống, trailing spaces"

    def clean(self, content: str) -> CleaningResult:
        """
        Làm sạch khoảng trắng trong nội dung.

        Args:
            content: Nội dung markdown

        Returns:
            CleaningResult với nội dung đã làm sạch
        """
        result = CleaningResult(content=content)
        original_content = content

        # 1. Chuẩn hóa line endings (CRLF -> LF)
        if self.normalize_endings:
            content = content.replace("\r\n", "\n").replace("\r", "\n")
            if content != original_content:
                result.add_detail("Chuẩn hóa line endings")

        # 2. Xóa trailing whitespace
        if self.trim_trailing:
            lines = content.split("\n")
            cleaned_lines = []
            trailing_removed = 0

            for line in lines:
                stripped = line.rstrip()
                if len(stripped) != len(line):
                    trailing_removed += 1
                cleaned_lines.append(stripped)

            content = "\n".join(cleaned_lines)
            if trailing_removed > 0:
                result.add_detail(
                    f"Xóa trailing whitespace từ {trailing_removed} dòng"
                )
                result.changes_made += trailing_removed

        # 3. Giảm số dòng trống liên tiếp
        blank_line_pattern = r"\n{" + str(self.max_blank_lines + 2) + r",}"
        replacement = "\n" * (self.max_blank_lines + 1)

        count = 0
        while re.search(blank_line_pattern, content):
            content = re.sub(blank_line_pattern, replacement, content)
            count += 1

        if count > 0:
            result.add_detail(f"Giảm dòng trống thừa: {count} vị trí")
            result.changes_made += count

        # 4. Xóa khoảng trắng ở đầu và cuối file
        stripped_content = content.strip()
        if stripped_content != content:
            result.add_detail("Xóa khoảng trắng đầu/cuối file")
            result.changes_made += 1
        content = stripped_content

        # 5. Xử lý multiple spaces (giữ 1 space, trừ trong code blocks và tables)
        # Không xử lý trong code blocks và tables
        lines = content.split("\n")
        cleaned_lines = []
        in_code_block = False
        in_table = False
        spaces_normalized = 0

        for line in lines:
            # Detect code block
            if line.strip().startswith("```"):
                in_code_block = not in_code_block
                cleaned_lines.append(line)
                continue

            # Detect table (có |)
            in_table = "|" in line

            if not in_code_block and not in_table:
                # Normalize multiple spaces to single space
                new_line = re.sub(r" {2,}", " ", line)
                if new_line != line:
                    spaces_normalized += 1
                cleaned_lines.append(new_line)
            else:
                cleaned_lines.append(line)

        content = "\n".join(cleaned_lines)
        if spaces_normalized > 0:
            result.add_detail(
                f"Chuẩn hóa multiple spaces: {spaces_normalized} dòng"
            )
            result.changes_made += spaces_normalized

        result.content = content
        result.success = True
        return result
