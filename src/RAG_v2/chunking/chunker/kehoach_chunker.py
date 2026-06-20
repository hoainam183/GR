"""
KeHoach Chunker – Kế hoạch / Thông báo Chunker

Chiến lược chunking dành riêng cho dữ liệu thông báo/kế hoạch crawl từ
ctt.hust.edu.vn (output_full.json), mỗi phần tử trong mảng JSON có cấu trúc:

    {
        "baiviet_id":   int,
        "url":          str,
        "title":        str,
        "category":     str,          # ví dụ "ĐTĐH", "CTSV"
        "tag_in_title": str,
        "date_str":     str,          # "11/3/2026"
        "title_detail": str,
        "date_detail":  str | null,
        "content_text": str,          # plain-text nội dung chính ← chunk từ đây
        "content_html": str,          # HTML (bỏ qua khi chunk)
        "crawled_at":   str
    }

Chiến lược tách:
  ┌─ Loại 1 – Ngắn  (< SINGLE_CHUNK_THRESHOLD ký tự)
  │      → 1 chunk duy nhất giữ nguyên toàn bộ nội dung
  │
  ├─ Loại 2 – Có mục số (1., 2., …)
  │      → Mục DÀI (> LONG_ITEM_THRESHOLD)  → mỗi mục 1 chunk
  │      → Mục NGẮN (≤ LONG_ITEM_THRESHOLD) → gộp nhiều mục / chunk
  │
  └─ Loại 3 – Văn xuôi thuần / không có cấu trúc rõ ràng
         → Dùng RecursiveCharacterTextSplitter

Metadata mỗi chunk:
    baiviet_id, title, category, tag_in_title, date_str, url,
    section_label   (nhãn mục số "1", "2", … hoặc None)
    chunk_index, total_chunks, chunk_size,
    source          ("kehoach")
"""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from langchain_text_splitters import RecursiveCharacterTextSplitter

from .markdown_table import (
    fix_mid_table_chunks,
    has_markdown_table,
    protect_tables,
    restore_tables,
    split_table_by_rows,
)
from .markdown_table import _RE_TABLE_BLOCK as _TABLE_BLOCK_RE


# ─────────────────────────────────────────────
# Tuning constants
# ─────────────────────────────────────────────
SINGLE_CHUNK_THRESHOLD = 1_500  # chars – keep whole content as 1 chunk
LONG_ITEM_THRESHOLD = 300  # chars – item is considered a "section"
DEFAULT_CHUNK_SIZE = 1_024
DEFAULT_OVERLAP = 150
MIN_CHUNK_SIZE = 60  # discard tiny fragments

# Separators for RecursiveCharacterTextSplitter (Vietnamese-aware)
_RECURSIVE_SEPS = ["\n\n", "\n", ". ", ", ", " ", ""]

# Numbered items at line start: "1.", "2.", …, "12."
_RE_NUMBERED = re.compile(r"(?m)^\d{1,2}\.\s+\S")

# ─────────────────────────────────────────────
# Internal helper
# ─────────────────────────────────────────────


def _split_at_numbered(text: str) -> List[Tuple[str, str]]:
    """
    Tách `text` tại các ranh giới mục số cấp-top (1. → 2. → 3. …).
    Trả về list of (label, full_text_of_item).
    Phần văn bản trước mục đầu tiên → label="".
    """
    lines = text.splitlines()

    preamble_lines: List[str] = []
    items: List[Tuple[str, str]] = []  # (label, accumulated lines)

    expected_num: Optional[int] = None
    current_label: Optional[str] = None
    current_lines: List[str] = []

    for line in lines:
        stripped = line.strip()
        m_alone = re.match(r"^(\d{1,2})\.$", stripped)
        m_inline = None if m_alone else re.match(r"^(\d{1,2})\.\s+\S", stripped)
        m = m_alone or m_inline

        if m:
            num = int(m.group(1))
            if expected_num is None and num == 1:
                expected_num = 1

            if expected_num is not None and num == expected_num:
                # Flush previous bucket
                if current_label is not None:
                    items.append((current_label, "\n".join(current_lines)))
                elif current_lines:
                    preamble_lines = list(current_lines)

                current_label = str(num)
                current_lines = [line]
                expected_num = num + 1
                continue

        current_lines.append(line)

    # Flush last bucket
    if current_label is not None:
        items.append((current_label, "\n".join(current_lines)))
    elif current_lines and not preamble_lines:
        preamble_lines = list(current_lines)

    result: List[Tuple[str, str]] = []
    preamble = "\n".join(preamble_lines).strip()
    if preamble:
        result.append(("", preamble))
    for label, body in items:
        body = body.strip()
        if body:
            result.append((label, body))

    return result


# ═══════════════════════════════════════════════════════════════════════════
class KeHoachChunker:
    """
    Chunker chuyên dụng cho dữ liệu thông báo/kế hoạch từ ctt.hust.edu.vn.

    Parameters
    ----------
    chunk_size : int
        Số ký tự tối đa mỗi chunk (mặc định 1 024).
    chunk_overlap : int
        Overlap khi dùng recursive splitter (mặc định 150).
    add_context_prefix : bool
        Nếu True, prepend "[title] | [category]" vào mỗi chunk.
    single_chunk_threshold : int
        Bài viết ngắn hơn ngưỡng này → 1 chunk duy nhất.
    long_item_threshold : int
        Mục dài hơn ngưỡng này → mỗi mục 1 chunk riêng.
    """

    def __init__(
        self,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_OVERLAP,
        add_context_prefix: bool = True,
        single_chunk_threshold: int = SINGLE_CHUNK_THRESHOLD,
        long_item_threshold: int = LONG_ITEM_THRESHOLD,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.add_context_prefix = add_context_prefix
        self.single_chunk_threshold = single_chunk_threshold
        self.long_item_threshold = long_item_threshold

        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=_RECURSIVE_SEPS,
            is_separator_regex=False,
        )

    # ──────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────

    def chunk_document(self, article: Dict) -> List[Dict]:
        """
        Nhận một dict bài viết, trả về list of chunk dicts.

        Mỗi chunk dict:
        {
            "chunk_id":   str (uuid4),
            "content":    str,
            "metadata": {
                "baiviet_id":    int,
                "title":         str,
                "category":      str,
                "tag_in_title":  str,
                "date_str":      str,
                "url":           str,
                "section_label": str | None,
                "chunk_index":   int,
                "total_chunks":  int,
                "chunk_size":    int,
                "source":        "kehoach"
            }
        }
        """
        baiviet_id = article.get("baiviet_id", 0)
        title = (
            article.get("title") or article.get("title_detail") or ""
        ).strip()
        category = article.get("category", "")
        tag_in_title = article.get("tag_in_title", "")
        date_str = article.get("date_str", "")
        url = article.get("url", "")
        content = article.get("content_text", "").strip()

        base_meta = {
            "baiviet_id": baiviet_id,
            "title": title,
            "category": category,
            "tag_in_title": tag_in_title,
            "date_str": date_str,
            "url": url,
            "source": "kehoach",
        }

        context_prefix = f"[{title}]" if self.add_context_prefix else ""

        raw_segments = self._segment(content)
        chunks = self._build_chunks(raw_segments, base_meta, context_prefix)
        chunks = fix_mid_table_chunks(chunks)

        total = len(chunks)
        for c in chunks:
            c["metadata"]["total_chunks"] = total
            c["metadata"]["has_table"] = has_markdown_table(c["content"])

        return chunks

    def chunk_file(self, json_path: str | Path) -> List[Dict]:
        """Đọc file JSON chứa mảng bài viết, trả về toàn bộ chunks."""
        json_path = Path(json_path)
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            articles = data
        elif isinstance(data, dict):
            articles = [data]
        else:
            raise ValueError(
                f"Không nhận dạng được định dạng JSON: {json_path}"
            )

        all_chunks: List[Dict] = []
        for article in articles:
            try:
                all_chunks.extend(self.chunk_document(article))
            except Exception as exc:
                bid = article.get("baiviet_id", "?")
                print(f"[WARN] Bỏ qua baiviet_id={bid}: {exc}")

        return all_chunks

    # ──────────────────────────────────────────
    # Core segmentation
    # ──────────────────────────────────────────

    def _segment(self, content: str) -> List[Tuple[str, Optional[str]]]:
        """
        Trả về list of (text, section_label).
        section_label: "1", "2", … hoặc None
        """
        if not content:
            return [("", None)]

        # Loại 1 – Ngắn
        if len(content) <= self.single_chunk_threshold:
            return [(content, None)]

        # Loại 2 – Có mục số
        if _RE_NUMBERED.search(content):
            return self._split_by_numbered(content)

        # Loại 3 – Văn xuôi thuần
        return [(content, None)]

    def _split_by_numbered(
        self, content: str
    ) -> List[Tuple[str, Optional[str]]]:
        """Tách theo mục số, gộp mục ngắn lại."""
        parsed = _split_at_numbered(content)
        segments: List[Tuple[str, Optional[str]]] = []

        group_buf: List[str] = []
        group_labels: List[str] = []

        def _flush_group() -> List[Tuple[str, Optional[str]]]:
            if not group_buf:
                return []
            combined = "\n\n".join(group_buf)
            label = group_labels[0] if len(group_labels) == 1 else None
            # Không tách ở đây — _build_chunks tách table-aware để không cắt bảng.
            return [(combined, label)]

        for label, item_text in parsed:
            item_text = item_text.strip()
            if not item_text:
                continue

            if len(item_text) > self.long_item_threshold:
                # Flush pending short group first; mục dài giữ nguyên, để
                # _build_chunks tách (bảo toàn bảng).
                segments.extend(_flush_group())
                group_buf, group_labels = [], []
                segments.append((item_text, label or None))
            else:
                group_buf.append(item_text)
                group_labels.append(label)
                if len("\n\n".join(group_buf)) >= self.chunk_size:
                    segments.extend(_flush_group())
                    group_buf, group_labels = [], []

        segments.extend(_flush_group())
        return segments

    # ──────────────────────────────────────────
    # Chunk construction
    # ──────────────────────────────────────────

    @staticmethod
    def _section_heading(text: str, label: Optional[str]) -> str:
        """Dòng tiêu đề/dẫn nhập của segment, để gắn vào mảnh bảng (self-contained)."""
        for line in text.splitlines():
            s = line.strip()
            if s and not s.startswith("|"):
                return s[:120]
        return f"Mục {label}" if label else ""

    def _protect_split(self, text: str) -> List[str]:
        """Tách văn xuôi; bảo vệ bảng nhỏ (≤ chunk_size) khỏi bị cắt giữa hàng."""
        text = text.strip()
        if not text:
            return []
        if len(text) <= self.chunk_size:
            return [text]
        protected, table_map = protect_tables(text, self.chunk_size)
        return [
            restore_tables(piece, table_map)
            for piece in self._splitter.split_text(protected)
        ]

    def _split_text_table_aware(
        self, text: str, heading_prefix: str = ""
    ) -> List[str]:
        """Tách text mà KHÔNG cắt giữa bảng.

        - Bảng ≤ chunk_size: giữ nguyên (atomic, kèm prose xung quanh nếu vừa).
        - Bảng > chunk_size: tách theo HÀNG, mỗi mảnh lặp lại header + heading.
        - Văn xuôi: tách bằng RecursiveCharacterTextSplitter.
        """
        text = text.strip()
        if len(text) <= self.chunk_size:
            return [text]

        pieces: List[str] = []
        pos = 0
        for m in _TABLE_BLOCK_RE.finditer(text):
            table = m.group(0)
            if len(table) <= self.chunk_size:
                continue  # bảng nhỏ → _protect_split giữ nguyên cùng ngữ cảnh
            pieces.extend(self._protect_split(text[pos : m.start()]))
            pieces.extend(
                split_table_by_rows(table, self.chunk_size, heading_prefix)
            )
            pos = m.end()
        pieces.extend(self._protect_split(text[pos:]))

        # Giữ mọi mảnh đủ dài HOẶC có chứa bảng — bảng nhỏ (vd 1 hàng ở cuối)
        # tuyệt đối KHÔNG được loại như mảnh vụn, nếu không sẽ mất data bảng.
        result = [
            p
            for p in pieces
            if len(p.strip()) >= MIN_CHUNK_SIZE or has_markdown_table(p)
        ]
        return result or [text]

    def _build_chunks(
        self,
        segments: List[Tuple[str, Optional[str]]],
        base_meta: Dict,
        context_prefix: str,
    ) -> List[Dict]:
        chunks: List[Dict] = []

        for text, section_label in segments:
            text = text.strip()
            if len(text) < MIN_CHUNK_SIZE and not has_markdown_table(text):
                continue

            heading = self._section_heading(text, section_label)
            for piece in self._split_text_table_aware(text, heading):
                piece = piece.strip()
                # Không bỏ mảnh chứa bảng dù ngắn (tránh mất data bảng ở cuối).
                if len(piece) < MIN_CHUNK_SIZE and not has_markdown_table(piece):
                    continue
                content = (
                    f"{context_prefix}\n{piece}".strip()
                    if context_prefix
                    else piece
                )
                chunks.append(
                    self._make_chunk(
                        content,
                        {
                            **base_meta,
                            "section_label": section_label,
                            "chunk_index": len(chunks),
                        },
                    )
                )

        # Ensure at least 1 chunk even for empty content
        if not chunks:
            fallback = context_prefix or base_meta.get("title", "")
            if fallback:
                chunks.append(
                    self._make_chunk(
                        fallback,
                        {
                            **base_meta,
                            "section_label": None,
                            "chunk_index": 0,
                        },
                    )
                )

        return chunks

    @staticmethod
    def _make_chunk(content: str, meta: Dict) -> Dict:
        return {
            "chunk_id": str(uuid.uuid4()),
            "content": content,
            "metadata": {**meta, "chunk_size": len(content)},
        }
