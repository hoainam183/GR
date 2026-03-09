# pdf_to_markdown/core/vietnamese_processor.py
"""
Stage 3: Vietnamese Text Post-Processing
- Unicode normalization (NFC cho tiếng Việt)
- Dấu thanh reconstruction
- Character mapping cho các ký tự bị lỗi
"""
import unicodedata
import re
from typing import Dict, List


class VietnameseTextProcessor:
    """
    Xử lý và sửa các vấn đề encoding của tiếng Việt
    """

    # Mapping các ký tự bị lỗi phổ biến → ký tự đúng
    COMMON_ERRORS = {
        # UTF-8 misread as Windows-1252
        "Ã¡": "á",
        "Ã ": "à",
        "áº£": "ả",
        "Ã£": "ã",
        "áº¡": "ạ",
        "Ã©": "é",
        "Ã¨": "è",
        "áº»": "ẻ",
        "áº½": "ẽ",
        "áº¹": "ẹ",
        "Ã­": "í",
        "Ã¬": "ì",
        "áº£": "ỉ",
        "Ä©": "ĩ",
        "á»‹": "ị",
        "Ã³": "ó",
        "Ã²": "ò",
        "á»": "ỏ",
        "Ãµ": "õ",
        "á»": "ọ",
        "Ãº": "ú",
        "Ã¹": "ù",
        "á»§": "ủ",
        "Å©": "ũ",
        "á»¥": "ụ",
        "Ã½": "ý",
        "á»³": "ỳ",
        "á»·": "ỷ",
        "á»¹": "ỹ",
        "á»µ": "ỵ",
        "Ä'": "đ",
        "Ä": "Đ",
        # Vowels with tone marks
        "Ã¢": "â",
        "Ã ": "ă",
        "Ãª": "ê",
        "Ã´": "ô",
        "Æ¡": "ơ",
        "Æ°": "ư",
        # Common Windows-1258 artifacts
        "Ã\x83Â ": "à",
        "Ã\x83Â¡": "á",
        "Ã\x83\x82": "â",
    }

    # Vietnamese vowels và dấu thanh (tones)
    VOWELS = "aăâeêioôơuưy"
    VOWELS_UPPER = "AĂÂEÊIOÔƠUƯY"
    TONES = (
        "\u0300\u0301\u0303\u0309\u0323"  # grave, acute, tilde, hook, dot below
    )

    def __init__(self):
        pass

    def process(self, text: str) -> str:
        """
        Pipeline xử lý đầy đủ cho text tiếng Việt
        """
        if not text:
            return text

        # 1. Fix common encoding errors
        text = self._fix_common_errors(text)

        # 2. Unicode normalization
        text = self._normalize_unicode(text)

        # 3. Reconstruct tone marks
        text = self._reconstruct_tones(text)

        # 4. Clean up whitespace
        text = self._clean_whitespace(text)

        return text

    def _fix_common_errors(self, text: str) -> str:
        """
        Thay thế các ký tự bị lỗi phổ biến
        """
        for wrong, correct in self.COMMON_ERRORS.items():
            text = text.replace(wrong, correct)
        return text

    def _normalize_unicode(self, text: str) -> str:
        """
        Chuẩn hóa Unicode về dạng NFC (composed form)
        NFC: ế = e + ́ + ̂ → single character
        """
        return unicodedata.normalize("NFC", text)

    def _reconstruct_tones(self, text: str) -> str:
        """
        Sửa các trường hợp dấu thanh bị tách rời khỏi nguyên âm
        VD: "e ́" → "é"
        """
        # Pattern: vowel + space + combining diacritic
        pattern = f"([{self.VOWELS}{self.VOWELS_UPPER}])\\s+([{self.TONES}])"
        text = re.sub(pattern, r"\1\2", text)

        # Normalize lại sau khi reconstruct
        text = unicodedata.normalize("NFC", text)
        return text

    def _clean_whitespace(self, text: str) -> str:
        """
        Dọn dẹp khoảng trắng thừa
        """
        # Remove multiple spaces
        text = re.sub(r" +", " ", text)

        # Remove space before punctuation
        text = re.sub(r"\s+([.,;:!?])", r"\1", text)

        # Remove trailing whitespace
        text = "\n".join(line.rstrip() for line in text.splitlines())

        return text

    def detect_and_fix(self, text: str) -> Dict[str, any]:
        """
        Phát hiện vấn đề và sửa, trả về report
        """
        original_length = len(text)
        issues_found = []

        # Check for common errors
        for wrong_char in self.COMMON_ERRORS.keys():
            if wrong_char in text:
                issues_found.append(f"Encoding error: {wrong_char}")

        # Check for separated tone marks
        pattern = f"([{self.VOWELS}{self.VOWELS_UPPER}])\\s+([{self.TONES}])"
        if re.search(pattern, text):
            issues_found.append("Separated tone marks detected")

        # Process text
        fixed_text = self.process(text)

        return {
            "original_length": original_length,
            "fixed_length": len(fixed_text),
            "issues_found": issues_found,
            "num_fixes": len(issues_found),
            "fixed_text": fixed_text,
        }

    def is_vietnamese_text(self, text: str, threshold: float = 0.05) -> bool:
        """
        Kiểm tra text có phải tiếng Việt không
        threshold: tỷ lệ ký tự tiếng Việt tối thiểu
        """
        if not text:
            return False

        vietnamese_chars = "àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ"
        vietnamese_chars += vietnamese_chars.upper()

        viet_count = sum(1 for c in text if c in vietnamese_chars)
        ratio = viet_count / len(text) if len(text) > 0 else 0

        return ratio >= threshold
