"""Vietnamese Word Segmentation — pre-tokenization for improved BM25 matching.

Vietnamese is a monosyllabic language where words consist of multiple syllables
separated by spaces. Without proper word segmentation, ES treats each syllable
as a separate token, causing false matches (e.g. "sinh viên" → "sinh" + "viên"
which can match "viên thuốc").

This module provides:
  - ``segment(text)`` — segment Vietnamese text into multi-syllable words
  - ``segment_for_indexing(text)`` — combine original + segmented for index-time
  - ``segment_query(query)`` — segment a search query for query-time matching

Strategy:
  - If ``underthesea`` is available, use its ``word_tokenize`` (CRF-based).
  - Otherwise, use a dictionary-based compound word lookup for the most common
    Vietnamese academic terms.

Usage at index time (in indexing scripts)::

    from utils.vietnamese_segmenter import segment_for_indexing
    segmented_text = segment_for_indexing(original_text)
    # Index segmented_text into ES

Usage at query time (in ElasticsearchStore.keyword_search)::

    from utils.vietnamese_segmenter import segment_query
    segmented_q = segment_query(user_query)
    # Use segmented_q for BM25 matching
"""

from __future__ import annotations

import logging
import re
from typing import List, Optional

logger = logging.getLogger(__name__)

# ─── Try to import underthesea ────────────────────────────────────────────────

_UNDERTHESEA_AVAILABLE = False
_word_tokenize = None

try:
    from underthesea import word_tokenize as _ut_tokenize
    _word_tokenize = _ut_tokenize
    _UNDERTHESEA_AVAILABLE = True
    logger.info("Vietnamese segmenter: using underthesea (CRF model)")
except ImportError:
    logger.info(
        "Vietnamese segmenter: underthesea not available, "
        "falling back to dictionary-based compound word matching"
    )


# ─── Fallback: Dictionary of common Vietnamese compound words ─────────────────
# These are multi-syllable Vietnamese words commonly found in university documents.
# Format: "syllable1 syllable2" → used as-is (space-separated syllables form one word)

_COMPOUND_WORDS = {
    # Academic terms
    "sinh viên", "giảng viên", "học phần", "tín chỉ", "học kỳ", "năm học",
    "chương trình", "đào tạo", "chương trình đào tạo", "tốt nghiệp",
    "điều kiện", "học bổng", "ký túc xá", "đăng ký", "học phí",
    "bảng điểm", "điểm trung bình", "trung bình chung", "tích lũy",
    "điểm rèn luyện", "rèn luyện", "thang điểm", "xếp loại",
    "khóa luận", "đồ án", "luận văn", "nghiên cứu khoa học",
    "tiên quyết", "song hành", "bắt buộc", "tự chọn",
    # University structure
    "đại học", "cao đẳng", "sau đại học", "thạc sĩ", "tiến sĩ",
    "khoa học", "công nghệ", "kỹ thuật", "nhân văn", "xã hội",
    "công nghệ thông tin", "khoa học máy tính", "kỹ thuật phần mềm",
    "trí tuệ nhân tạo", "khoa học dữ liệu",
    # Administrative
    "phòng đào tạo", "ban giám hiệu", "hội đồng", "quy chế",
    "quy định", "kế hoạch", "sổ tay", "nội quy", "thông báo",
    "hồ sơ", "thủ tục", "đơn xin", "giấy xác nhận",
    # Assessment
    "kiểm tra", "thi cuối kỳ", "thi giữa kỳ", "bài tập lớn",
    "đồ án môn học", "thực hành", "thực tập", "thí nghiệm",
    "chuyên đề", "tiểu luận", "báo cáo",
    # Student affairs
    "bảo hiểm", "bảo hiểm y tế", "hoạt động", "ngoại khóa",
    "câu lạc bộ", "đoàn thanh niên", "hội sinh viên",
    "miễn giảm", "trợ cấp", "hỗ trợ", "tư vấn",
    # Scheduling
    "thời khóa biểu", "lịch thi", "lịch học", "buổi học",
    "tiết học", "học trực tuyến", "học trực tiếp",
}

# Build a sorted list (longest first) for greedy matching
_SORTED_COMPOUNDS = sorted(_COMPOUND_WORDS, key=len, reverse=True)

# Pre-compile regex patterns for each compound word
_COMPOUND_PATTERNS = [
    (re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE), word)
    for word in _SORTED_COMPOUNDS
]


def is_available() -> bool:
    """Return True if underthesea is available for full segmentation."""
    return _UNDERTHESEA_AVAILABLE


def segment(text: str) -> str:
    """Segment Vietnamese text into words.

    Multi-syllable words are joined with underscores (e.g. "sinh_viên").

    Args:
        text: Raw Vietnamese text.

    Returns:
        Segmented text with compound words joined by underscores.
    """
    if not text or not text.strip():
        return text

    if _UNDERTHESEA_AVAILABLE and _word_tokenize is not None:
        try:
            return _word_tokenize(text, format="text")
        except Exception as exc:
            logger.debug("underthesea segmentation failed: %s", exc)
            # Fall through to dictionary-based

    return _segment_by_dictionary(text)


def _segment_by_dictionary(text: str) -> str:
    """Dictionary-based compound word segmentation.

    Replaces spaces in known compound words with underscores.
    Greedy longest-match strategy.
    """
    result = text
    for pattern, word in _COMPOUND_PATTERNS:
        replacement = word.replace(" ", "_")
        result = pattern.sub(replacement, result)
    return result


def segment_for_indexing(text: str) -> str:
    """Prepare text for ES indexing with segmentation.

    Returns a concatenation of original text + segmented version.
    This ensures both syllable-level and word-level matches work.

    Args:
        text: Raw Vietnamese text to index.

    Returns:
        Combined text: ``"<original>\\n<segmented>"``
    """
    if not text or not text.strip():
        return text

    segmented = segment(text)
    if segmented == text:
        return text

    # Only append if segmentation actually changed something
    return f"{text}\n{segmented}"


def segment_query(query: str) -> str:
    """Segment a search query for BM25 matching.

    Applies word segmentation so that multi-syllable terms are searched
    as single tokens, improving precision.

    Args:
        query: Raw user query.

    Returns:
        Segmented query string.
    """
    if not query or not query.strip():
        return query

    return segment(query)


def get_compound_variants(query: str) -> List[str]:
    """Return both original and segmented forms for multi-query search.

    Useful when you want to search with both forms to maximize recall.

    Args:
        query: Raw query text.

    Returns:
        List containing original and segmented forms (deduplicated).
    """
    if not query or not query.strip():
        return [query] if query else []

    segmented = segment(query)
    variants = [query]
    if segmented != query:
        variants.append(segmented)
    return variants
