"""
Utility Functions for Data Cleaning
===================================

Các hàm tiện ích cho quá trình làm sạch dữ liệu.
"""

import re
import hashlib
from pathlib import Path
from typing import List, Optional, Dict, Tuple
from datetime import datetime


def get_file_hash(filepath: Path) -> str:
    """
    Tính MD5 hash của file.

    Args:
        filepath: Đường dẫn file

    Returns:
        MD5 hash string
    """
    with open(filepath, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def count_words(text: str) -> int:
    """
    Đếm số từ trong text (hỗ trợ tiếng Việt).

    Args:
        text: Nội dung cần đếm

    Returns:
        Số từ
    """
    # Split theo whitespace
    words = text.split()
    return len(words)


def count_characters(text: str, include_spaces: bool = False) -> int:
    """
    Đếm số ký tự trong text.

    Args:
        text: Nội dung cần đếm
        include_spaces: Có đếm khoảng trắng không

    Returns:
        Số ký tự
    """
    if include_spaces:
        return len(text)
    return len(text.replace(" ", "").replace("\n", "").replace("\t", ""))


def extract_sections(content: str) -> List[Dict[str, str]]:
    """
    Trích xuất các section từ markdown document.

    Args:
        content: Nội dung markdown

    Returns:
        List of {level, title, content}
    """
    sections = []

    # Pattern cho headers markdown
    header_pattern = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

    matches = list(header_pattern.finditer(content))

    for i, match in enumerate(matches):
        level = len(match.group(1))
        title = match.group(2).strip()

        # Tìm content của section (đến header tiếp theo hoặc cuối file)
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        section_content = content[start:end].strip()

        sections.append(
            {"level": level, "title": title, "content": section_content}
        )

    return sections


def extract_tables(content: str) -> List[str]:
    """
    Trích xuất các bảng từ markdown.

    Args:
        content: Nội dung markdown

    Returns:
        List of table strings
    """
    tables = []
    lines = content.split("\n")
    current_table = []
    in_table = False

    for line in lines:
        if "|" in line:
            in_table = True
            current_table.append(line)
        else:
            if in_table and current_table:
                tables.append("\n".join(current_table))
                current_table = []
            in_table = False

    # Don't forget last table
    if current_table:
        tables.append("\n".join(current_table))

    return tables


def normalize_vietnamese_text(text: str) -> str:
    """
    Chuẩn hóa text tiếng Việt.

    Args:
        text: Text cần chuẩn hóa

    Returns:
        Text đã chuẩn hóa
    """
    import unicodedata

    # Normalize Unicode
    text = unicodedata.normalize("NFC", text)

    # Fix common issues
    replacements = [
        (r"\s+", " "),  # Multiple spaces -> single space
        (
            r"(?<=[.!?])\s*(?=[A-ZÀÁẢÃẠ])",
            "\n",
        ),  # Add line break after sentences
    ]

    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text)

    return text.strip()


def detect_document_language(content: str) -> str:
    """
    Phát hiện ngôn ngữ của document.

    Args:
        content: Nội dung document

    Returns:
        'vi' cho tiếng Việt, 'en' cho tiếng Anh
    """
    # Vietnamese-specific characters
    vietnamese_chars = set(
        "àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ"
    )

    # Count Vietnamese characters
    vn_count = sum(1 for char in content.lower() if char in vietnamese_chars)

    # If more than 1% of content is Vietnamese chars, it's Vietnamese
    if vn_count / max(len(content), 1) > 0.01:
        return "vi"
    return "en"


def create_slug(text: str) -> str:
    """
    Tạo slug từ text (cho filename).

    Args:
        text: Text cần chuyển đổi

    Returns:
        Slug string
    """
    import unicodedata

    # Normalize và chuyển về ASCII
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")

    # Lowercase và replace non-alphanumeric
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text)  # Multiple dashes -> single

    return text.strip("-")


def estimate_reading_time(content: str, wpm: int = 200) -> int:
    """
    Ước tính thời gian đọc (phút).

    Args:
        content: Nội dung
        wpm: Words per minute (default 200 cho tiếng Việt)

    Returns:
        Số phút
    """
    word_count = count_words(content)
    return max(1, round(word_count / wpm))


def split_into_chunks(
    content: str, max_chars: int = 1000, overlap: int = 100
) -> List[str]:
    """
    Chia content thành các chunks với overlap.

    Args:
        content: Nội dung cần chia
        max_chars: Số ký tự tối đa mỗi chunk
        overlap: Số ký tự overlap giữa các chunks

    Returns:
        List of chunks
    """
    chunks = []
    start = 0

    while start < len(content):
        end = start + max_chars

        # Tìm điểm kết thúc câu gần nhất
        if end < len(content):
            # Tìm . hoặc \n gần nhất
            last_period = content.rfind(".", start, end)
            last_newline = content.rfind("\n", start, end)
            break_point = max(last_period, last_newline)

            if break_point > start:
                end = break_point + 1

        chunk = content[start:end].strip()
        if chunk:
            chunks.append(chunk)

        # Move start with overlap
        start = end - overlap
        if start < 0:
            start = 0

    return chunks


def compare_files(file1: Path, file2: Path) -> Dict[str, any]:
    """
    So sánh 2 file markdown.

    Args:
        file1, file2: Đường dẫn 2 files

    Returns:
        Dictionary với thông tin so sánh
    """
    with open(file1, "r", encoding="utf-8") as f:
        content1 = f.read()
    with open(file2, "r", encoding="utf-8") as f:
        content2 = f.read()

    return {
        "file1_size": len(content1),
        "file2_size": len(content2),
        "size_difference": len(content1) - len(content2),
        "file1_words": count_words(content1),
        "file2_words": count_words(content2),
        "file1_lines": content1.count("\n"),
        "file2_lines": content2.count("\n"),
        "identical": content1 == content2,
    }


def format_file_size(size_bytes: int) -> str:
    """
    Format size thành human-readable string.

    Args:
        size_bytes: Kích thước bytes

    Returns:
        Formatted string (e.g., "1.5 KB")
    """
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"
