"""
Special Characters Cleaner Module
=================================

Xử lý các vấn đề với ký tự đặc biệt:
- Chuẩn hóa Unicode (NFC)
- Sửa lỗi OCR phổ biến
- Xóa ký tự không in được
- Chuẩn hóa dấu câu
"""

import re
import unicodedata
from typing import Optional, Dict, Any, List, Tuple

from .base import BaseCleaner, CleaningResult


class SpecialCharacterCleaner(BaseCleaner):
    """
    Cleaner xử lý ký tự đặc biệt và lỗi OCR.

    Config options:
        normalize_unicode (bool): Chuẩn hóa NFC (default: True)
        fix_ocr_errors (bool): Sửa lỗi OCR (default: True)
        remove_control_chars (bool): Xóa control characters (default: True)
        normalize_punctuation (bool): Chuẩn hóa dấu câu (default: True)
        ocr_error_mappings (Dict[str, str]): Custom OCR error mappings
    """

    # Các lỗi OCR phổ biến trong văn bản tiếng Việt
    DEFAULT_OCR_MAPPINGS = {
        # Lỗi tên viết tắt
        "ĐHIBK": "ĐHBK",
        "DHBK": "ĐHBK",
        "ĐH BK": "ĐHBK",
        # Lỗi từ phổ biến
        "cổ văn": "cố vấn",
        "cõ vấn": "cố vấn",
        "cồ văn": "cố vấn",
        "Mình chừng": "Minh chứng",
        "minh chừng": "minh chứng",
        "sachsHT": "sách HT",
        "sinh vien": "sinh viên",
        "hoc bong": "học bổng",
        "diem ren luyen": "điểm rèn luyện",
        # Lỗi số/ký tự
        "M9": "119",  # Số QĐ thường bị OCR sai
        # Lỗi dấu
        "việt Nam": "Việt Nam",
        "hà Nội": "Hà Nội",
        "bách Khoa": "Bách khoa",
    }

    # Các ký tự cần chuẩn hóa
    PUNCTUATION_MAPPINGS = {
        "–": "-",  # En dash -> hyphen
        "—": "-",  # Em dash -> hyphen
        '"': '"',  # Smart quote
        '"': '"',  # Smart quote
        """: "'",  # Smart quote
        """: "'",  # Smart quote
        "…": "...",  # Ellipsis
        "\u00a0": " ",  # Non-breaking space
        "\u2003": " ",  # Em space
        "\u2002": " ",  # En space
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.normalize_unicode = self.config.get("normalize_unicode", True)
        self.fix_ocr = self.config.get("fix_ocr_errors", True)
        self.remove_control = self.config.get("remove_control_chars", True)
        self.normalize_punct = self.config.get("normalize_punctuation", True)

        # Merge default mappings với custom mappings
        self.ocr_mappings = self.DEFAULT_OCR_MAPPINGS.copy()
        custom_mappings = self.config.get("ocr_error_mappings", {})
        self.ocr_mappings.update(custom_mappings)

    @property
    def name(self) -> str:
        return "SpecialCharacterCleaner"

    @property
    def description(self) -> str:
        return "Chuẩn hóa Unicode, sửa lỗi OCR, xóa ký tự đặc biệt"

    def _normalize_unicode(self, content: str) -> Tuple[str, int]:
        """
        Chuẩn hóa Unicode về dạng NFC (Canonical Decomposition, followed by Canonical Composition).

        Returns:
            (normalized_content, changes_count)
        """
        normalized = unicodedata.normalize("NFC", content)
        changes = 1 if normalized != content else 0
        return normalized, changes

    def _remove_control_characters(self, content: str) -> Tuple[str, int]:
        """
        Xóa các control characters không in được.
        Giữ lại newline (\n), tab (\t), và carriage return (\r).

        Returns:
            (cleaned_content, removed_count)
        """
        result = []
        removed = 0

        for char in content:
            category = unicodedata.category(char)

            # Giữ lại whitespace characters cần thiết
            if char in "\n\t\r ":
                result.append(char)
            # Xóa control characters (category 'C')
            elif category.startswith("C"):
                removed += 1
            else:
                result.append(char)

        return "".join(result), removed

    def _normalize_punctuation(self, content: str) -> Tuple[str, int]:
        """
        Chuẩn hóa các dấu câu về dạng ASCII standard.

        Returns:
            (normalized_content, changes_count)
        """
        changes = 0
        for old, new in self.PUNCTUATION_MAPPINGS.items():
            count = content.count(old)
            if count > 0:
                content = content.replace(old, new)
                changes += count

        return content, changes

    def _fix_ocr_errors(self, content: str) -> Tuple[str, int]:
        """
        Sửa các lỗi OCR phổ biến.

        Returns:
            (fixed_content, fixes_count)
        """
        fixes = 0

        for wrong, correct in self.ocr_mappings.items():
            # Case-sensitive replacement
            count = content.count(wrong)
            if count > 0:
                content = content.replace(wrong, correct)
                fixes += count
                self.logger.debug(
                    f"Fixed OCR error: '{wrong}' -> '{correct}' ({count} times)"
                )

        return content, fixes

    def _fix_vietnamese_encoding(self, content: str) -> Tuple[str, int]:
        """
        Sửa các lỗi encoding tiếng Việt phổ biến.

        Returns:
            (fixed_content, fixes_count)
        """
        fixes = 0

        # Các pattern lỗi encoding phổ biến
        encoding_patterns = [
            # Combining characters không đúng vị trí
            (r"([aeiouAEIOU])(\u0301)", r"\1́"),  # Dấu sắc
            (r"([aeiouAEIOU])(\u0300)", r"\1̀"),  # Dấu huyền
            (r"([aeiouAEIOU])(\u0303)", r"\1̃"),  # Dấu ngã
            (r"([aeiouAEIOU])(\u0309)", r"\1̉"),  # Dấu hỏi
            (r"([aeiouAEIOU])(\u0323)", r"\1̣"),  # Dấu nặng
        ]

        for pattern, replacement in encoding_patterns:
            content, count = re.subn(pattern, replacement, content)
            fixes += count

        return content, fixes

    def _clean_markdown_artifacts(self, content: str) -> Tuple[str, int]:
        """
        Xóa các artifact từ quá trình convert HTML -> Markdown.

        Returns:
            (cleaned_content, removed_count)
        """
        changes = 0

        # Xóa các HTML entities còn sót
        html_entities = [
            ("&nbsp;", " "),
            ("&amp;", "&"),
            ("&lt;", "<"),
            ("&gt;", ">"),
            ("&quot;", '"'),
            ("&#39;", "'"),
        ]

        for entity, char in html_entities:
            count = content.count(entity)
            if count > 0:
                content = content.replace(entity, char)
                changes += count

        # Xóa các empty markdown elements
        patterns = [
            (r"\*\*\s*\*\*", ""),  # Empty bold
            (r"__\s*__", ""),  # Empty bold
            (r"\*\s*\*", ""),  # Empty italic
            (r"_\s*_", ""),  # Empty italic
            (r"\[\s*\]\(\s*\)", ""),  # Empty links
        ]

        for pattern, replacement in patterns:
            content, count = re.subn(pattern, replacement, content)
            changes += count

        return content, changes

    def clean(self, content: str) -> CleaningResult:
        """
        Làm sạch ký tự đặc biệt và lỗi OCR.

        Args:
            content: Nội dung markdown

        Returns:
            CleaningResult với các ký tự đã được xử lý
        """
        result = CleaningResult(content=content)
        total_changes = 0

        # 1. Chuẩn hóa Unicode
        if self.normalize_unicode:
            content, changes = self._normalize_unicode(content)
            if changes:
                result.add_detail("Chuẩn hóa Unicode NFC")
                total_changes += changes

        # 2. Xóa control characters
        if self.remove_control:
            content, changes = self._remove_control_characters(content)
            if changes:
                result.add_detail(f"Xóa {changes} control characters")
                total_changes += changes

        # 3. Chuẩn hóa punctuation
        if self.normalize_punct:
            content, changes = self._normalize_punctuation(content)
            if changes:
                result.add_detail(f"Chuẩn hóa {changes} dấu câu")
                total_changes += changes

        # 4. Sửa lỗi OCR
        if self.fix_ocr:
            content, changes = self._fix_ocr_errors(content)
            if changes:
                result.add_detail(f"Sửa {changes} lỗi OCR")
                total_changes += changes

        # 5. Sửa lỗi encoding tiếng Việt
        content, changes = self._fix_vietnamese_encoding(content)
        if changes:
            result.add_detail(f"Sửa {changes} lỗi encoding tiếng Việt")
            total_changes += changes

        # 6. Xóa markdown artifacts
        content, changes = self._clean_markdown_artifacts(content)
        if changes:
            result.add_detail(f"Xóa {changes} markdown artifacts")
            total_changes += changes

        result.content = content
        result.changes_made = total_changes
        result.success = True

        return result
