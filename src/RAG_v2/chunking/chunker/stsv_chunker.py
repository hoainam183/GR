"""
STSV Chunker – Student Handbook / Sổ tay Sinh viên Chunker

Chiến lược chunking dành riêng cho định dạng JSON của dữ liệu STSV:
    {
        "DocumentID": int,
        "Title":      str,
        "TypeDoc":    str,   # "Sổ tay SV" | "Kit nhập học" | ...
        "Description": str,  # Nội dung chính, markdown-like
        "CreaterID":  str,
        "TimeCreate": str,
        "Status":     int
    }

Phân tích cấu trúc nội dung (Description):
  ┌─ Loại 1 – Ngắn  (< SINGLE_CHUNK_THRESHOLD)
  │      → 1 chunk duy nhất, giữ nguyên toàn bộ
  │
  ├─ Loại 2 – Có phần Roman (I., II., III.)
  │      → Tách tại ranh giới phần
  │      → Mỗi phần tiếp tục được tách theo mục số (nếu dài)
  │
  ├─ Loại 3 – Có mục số (1., 2., …) không có phần Roman
  │      → Mục DÀI (> LONG_ITEM_THRESHOLD)  → mỗi mục 1 chunk
  │      → Mục NGẮN (≤ LONG_ITEM_THRESHOLD) → gộp nhiều mục / chunk
  │
  └─ Loại 4 – Văn xuôi thuần / không có cấu trúc rõ ràng
         → Dùng RecursiveCharacterTextSplitter

Metadata mỗi chunk:
    doc_id, title, type_doc, time_create,
    section_context  (phần Roman, nếu có),
    item_label       (số thứ tự mục, nếu có),
    chunk_index, total_chunks, chunk_size,
    has_links        (True nếu chứa URL markdown)
"""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from langchain_text_splitters import RecursiveCharacterTextSplitter


# ─────────────────────────────────────────────
# Tuning constants
# ─────────────────────────────────────────────
SINGLE_CHUNK_THRESHOLD = 1_500  # chars – keep whole description as 1 chunk
LONG_ITEM_THRESHOLD = 300  # chars – item is a "section", not a table row
DEFAULT_CHUNK_SIZE = 1_024
DEFAULT_OVERLAP = 150
MIN_CHUNK_SIZE = 60  # discard tiny fragments

# Separators for RecursiveCharacterTextSplitter (Vietnamese-aware)
_RECURSIVE_SEPS = [
    "\n\n",
    "\n",
    ". ",
    ", ",
    " ",
    "",
]

# ─────────────────────────────────────────────
# Regex patterns
# ─────────────────────────────────────────────
# Matches Roman-numeral section headers at line start, e.g. "I. Giới thiệu"
_RE_ROMAN = re.compile(
    r"(?m)^(I{1,3}V?|VI{0,3}|IX|XI{0,3}|XIV|XV)\.\s+\S",
)

# Matches numbered items at line start, e.g. "1.", "12.", "41."
_RE_NUMBERED = re.compile(r"(?m)^\d{1,2}\.\s+\S")

# Detect markdown links
_RE_MD_LINK = re.compile(r"\[.+?\]\(.+?\)")


# ═══════════════════════════════════════════════════════════════════════════
class STSVChunker:
    """
    Chunker chuyên dụng cho tài liệu STSV (định dạng JSON).

    Parameters
    ----------
    chunk_size : int
        Số ký tự tối đa mỗi chunk (mặc định 1024).
    chunk_overlap : int
        Số ký tự overlap giữa các chunk khi dùng recursive splitter
        (mặc định 150).
    add_context_prefix : bool
        Nếu True, mỗi chunk được tiền tố bởi "[Tiêu đề] | [TypeDoc]"
        để chunk có thể đứng độc lập khi retrieval.
    single_chunk_threshold : int
        Nếu Description ngắn hơn ngưỡng này → trả về 1 chunk.
    long_item_threshold : int
        Mục số dài hơn ngưỡng này được coi là "section" → chunk riêng.
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

    def chunk_document(self, doc: Dict) -> List[Dict]:
        """
        Nhận một dict JSON STSV, trả về list of chunk dicts.

        Mỗi chunk dict có cấu trúc:
        {
            "chunk_id":       str (uuid),
            "content":        str,
            "metadata": {
                "doc_id":         int,
                "title":          str,
                "type_doc":       str,
                "time_create":    str,
                "section_context":str | None,
                "item_label":     str | None,
                "chunk_index":    int,
                "total_chunks":   int,   # điền sau
                "chunk_size":     int,
                "has_links":      bool,
            }
        }
        """
        title = doc.get("Title", "")
        type_doc = doc.get("TypeDoc", "")
        doc_id = doc.get("DocumentID", 0)
        time_create = doc.get("TimeCreate", "")
        description = doc.get("Description", "").strip()

        base_meta = {
            "doc_id": doc_id,
            "title": title,
            "type_doc": type_doc,
            "time_create": time_create,
        }

        raw_segments = self._segment(description, title, type_doc)
        chunks = self._build_chunks(raw_segments, base_meta)

        # Back-fill total_chunks
        total = len(chunks)
        for c in chunks:
            c["metadata"]["total_chunks"] = total

        return chunks

    def chunk_file(self, json_path: str | Path) -> List[Dict]:
        """Tiện ích: đọc file JSON và trả về chunks."""
        with open(json_path, encoding="utf-8") as f:
            doc = json.load(f)
        return self.chunk_document(doc)

    def chunk_directory(
        self,
        dir_path: str | Path,
        output_path: Optional[str | Path] = None,
    ) -> List[Dict]:
        """Chunk toàn bộ file JSON trong một thư mục."""
        dir_path = Path(dir_path)
        all_chunks: List[Dict] = []
        for fp in sorted(dir_path.glob("*.json")):
            try:
                all_chunks.extend(self.chunk_file(fp))
            except Exception as exc:
                print(f"[WARN] Bỏ qua {fp.name}: {exc}")

        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(all_chunks, f, ensure_ascii=False, indent=2)
            print(f"✅ Đã lưu {len(all_chunks)} chunks → {output_path}")

        return all_chunks

    # ──────────────────────────────────────────
    # Core segmentation logic
    # ──────────────────────────────────────────

    def _segment(
        self, description: str, title: str, type_doc: str
    ) -> List[Tuple[str, Optional[str], Optional[str]]]:
        """
        Trả về list (text, section_context, item_label).

        section_context : tiêu đề phần Roman (I., II., ...) hoặc None
        item_label      : nhãn mục số ("1", "2", …) hoặc None
        """

        # ── Loại 1: Ngắn → 1 segment ──────────────────────────────────────
        if len(description) <= self.single_chunk_threshold:
            return [(description, None, None)]

        # ── Loại 2: Có phần Roman ─────────────────────────────────────────
        if _RE_ROMAN.search(description):
            return self._split_by_roman_then_items(description)

        # ── Loại 3: Có mục số ─────────────────────────────────────────────
        if _RE_NUMBERED.search(description):
            return self._split_by_numbered_items(description, section_ctx=None)

        # ── Loại 4: Văn xuôi thuần ────────────────────────────────────────
        return [(description, None, None)]

    # ──────────────────────────────────────────

    def _split_by_roman_then_items(
        self, text: str
    ) -> List[Tuple[str, Optional[str], Optional[str]]]:
        """Tách theo phần Roman, rồi trong mỗi phần tách theo mục số."""
        roman_sections = _split_at_pattern(text, _RE_ROMAN)
        segments: List[Tuple[str, Optional[str], Optional[str]]] = []

        for sec_text in roman_sections:
            # Lấy dòng đầu làm tiêu đề phần
            first_line = sec_text.split("\n", 1)[0].strip()
            section_ctx = first_line if _RE_ROMAN.match(first_line) else None

            if _RE_NUMBERED.search(sec_text):
                sub = self._split_by_numbered_items(sec_text, section_ctx)
                segments.extend(sub)
            else:
                segments.append((sec_text, section_ctx, None))

        return segments

    def _split_by_numbered_items(
        self,
        text: str,
        section_ctx: Optional[str],
    ) -> List[Tuple[str, Optional[str], Optional[str]]]:
        """
        Tách text theo các mục số (1., 2., …) với *sequential tracking*.

        Chỉ nhận một mục mới khi số thứ tự đúng bằng expected (1→2→3→…),
        tránh hiểu nhầm sub-items (vd. "1. Miễn học phần…" trong mục 8)
        thành mục cấp cao.

        - Mục DÀI (> long_item_threshold): mỗi mục → 1 segment
        - Mục NGẮN (≤ long_item_threshold): gộp nhiều mục cho đến khi
          tổng < chunk_size
        - Phần header trước mục số đầu tiên → segment riêng
        """
        lines = text.splitlines()

        preamble_lines: List[str] = []
        items: List[Tuple[str, str]] = []  # (label, full item text)

        expected_num: Optional[int] = None
        current_label: Optional[str] = None
        current_lines: List[str] = []

        for line in lines:
            stripped = line.strip()
            # "N." alone on a line
            m_alone = re.match(r"^(\d{1,2})\.$", stripped)
            # "N. content" on the same line
            m_inline = (
                None if m_alone else re.match(r"^(\d{1,2})\.\s+\S", stripped)
            )
            m = m_alone or m_inline

            if m:
                num = int(m.group(1))
                if expected_num is None and num == 1:
                    expected_num = 1

                if expected_num is not None and num == expected_num:
                    # Save previous bucket
                    if current_label is not None:
                        items.append((current_label, "\n".join(current_lines)))
                    elif current_lines:
                        preamble_lines = list(current_lines)

                    current_label = str(num)
                    current_lines = [line]
                    expected_num = num + 1
                    continue

            # Not a top-level boundary → accumulate into current bucket
            current_lines.append(line)

        # Flush last bucket
        if current_label is not None:
            items.append((current_label, "\n".join(current_lines)))
        elif current_lines and not preamble_lines:
            preamble_lines = list(current_lines)

        # ── Build segments ────────────────────────────────────────────────
        segments: List[Tuple[str, Optional[str], Optional[str]]] = []

        if preamble_lines:
            preamble = "\n".join(preamble_lines).strip()
            if preamble:
                segments.append((preamble, section_ctx, None))

        group_buf: List[str] = []
        group_labels: List[str] = []

        for label, item_text in items:
            item_text = item_text.strip()
            if not item_text:
                continue

            if len(item_text) > self.long_item_threshold:
                if group_buf:
                    segments.extend(
                        self._flush_group(group_buf, group_labels, section_ctx)
                    )
                    group_buf, group_labels = [], []
                segments.append((item_text, section_ctx, label))
            else:
                group_buf.append(item_text)
                group_labels.append(label)
                if len("\n\n".join(group_buf)) >= self.chunk_size:
                    segments.extend(
                        self._flush_group(group_buf, group_labels, section_ctx)
                    )
                    group_buf, group_labels = [], []

        if group_buf:
            segments.extend(
                self._flush_group(group_buf, group_labels, section_ctx)
            )

        return segments

    @staticmethod
    def _flush_group(
        group: List[str],
        labels: List[str],
        section_ctx: Optional[str],
    ) -> List[Tuple[str, Optional[str], Optional[str]]]:
        """Gộp nhóm mục ngắn thành 1 segment."""
        combined = "\n\n".join(group)
        label_str = (
            f"{labels[0]}–{labels[-1]}" if len(labels) > 1 else labels[0]
        )
        return [(combined, section_ctx, label_str)]

    # ──────────────────────────────────────────
    # Build final chunk dicts
    # ──────────────────────────────────────────

    def _build_chunks(
        self,
        segments: List[Tuple[str, Optional[str], Optional[str]]],
        base_meta: Dict,
    ) -> List[Dict]:
        """
        Chuyển segments → chunk dicts.

        Mỗi segment còn dài → recursive split tiếp.
        Mỗi chunk được thêm context prefix (nếu bật).
        """
        chunks: List[Dict] = []
        title = base_meta["title"]
        type_doc = base_meta["type_doc"]
        idx = 0

        for text, sec_ctx, item_label in segments:
            if len(text) <= self.chunk_size:
                sub_texts = [text]
            else:
                sub_texts = self._splitter.split_text(text)

            for sub in sub_texts:
                sub = sub.strip()
                if len(sub) < MIN_CHUNK_SIZE:
                    continue

                content = self._build_content(sub, title, type_doc, sec_ctx)

                chunk = {
                    "chunk_id": str(uuid.uuid4()),
                    "content": content,
                    "metadata": {
                        **base_meta,
                        "section_context": sec_ctx,
                        "item_label": item_label,
                        "chunk_index": idx,
                        "total_chunks": 0,  # filled later
                        "chunk_size": len(content),
                        "has_links": bool(_RE_MD_LINK.search(sub)),
                    },
                }
                chunks.append(chunk)
                idx += 1

        return chunks

    def _build_content(
        self,
        text: str,
        title: str,
        type_doc: str,
        section_ctx: Optional[str],
    ) -> str:
        """Xây dựng nội dung chunk với context prefix tuỳ chọn."""
        if not self.add_context_prefix:
            return text

        parts = [title]
        if type_doc:
            parts.append(type_doc)
        if section_ctx:
            parts.append(section_ctx)

        prefix = " | ".join(parts)
        return f"[{prefix}]\n{text}"


# ═══════════════════════════════════════════════════════════════════════════
# Helper
# ═══════════════════════════════════════════════════════════════════════════


def _split_at_pattern(text: str, pattern: re.Pattern) -> List[str]:
    """
    Tách text thành nhiều phần tại mỗi vị trí khớp pattern.
    Vị trí khớp được giữ ở đầu của phần tiếp theo (không bỏ tiêu đề).
    """
    boundaries = [m.start() for m in pattern.finditer(text)]
    if not boundaries:
        return [text]

    parts: List[str] = []
    # Phần trước boundary đầu tiên (có thể là preamble)
    if boundaries[0] > 0:
        parts.append(text[: boundaries[0]])

    for i, start in enumerate(boundaries):
        end = boundaries[i + 1] if i + 1 < len(boundaries) else len(text)
        parts.append(text[start:end])

    return parts


# ═══════════════════════════════════════════════════════════════════════════
# CLI helper
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print(
            "Usage: python stsv_chunker.py <path_to_json_or_dir> [output.json]"
        )
        sys.exit(1)

    source = Path(sys.argv[1])
    output = sys.argv[2] if len(sys.argv) > 2 else None
    chunker = STSVChunker()

    if source.is_dir():
        chunks = chunker.chunk_directory(source, output)
    else:
        chunks = chunker.chunk_file(source)
        if output:
            with open(output, "w", encoding="utf-8") as f:
                json.dump(chunks, f, ensure_ascii=False, indent=2)
            print(f"✅ Đã lưu {len(chunks)} chunks → {output}")

    # In thống kê
    sizes = [c["metadata"]["chunk_size"] for c in chunks]
    if sizes:
        print(f"\n📊 Thống kê ({len(chunks)} chunks):")
        print(f"   Trung bình : {sum(sizes)/len(sizes):.0f} ký tự")
        print(f"   Nhỏ nhất   : {min(sizes)} ký tự")
        print(f"   Lớn nhất   : {max(sizes)} ký tự")
        # In 3 chunk đầu để kiểm tra
        print("\n── Chunk mẫu ──")
        for c in chunks[:3]:
            m = c["metadata"]
            print(
                f"  [{m['chunk_index']}] doc={m['doc_id']} | sec={m['section_context']} | item={m['item_label']}"
            )
            print(f"      {c['content'][:120].replace(chr(10),' ')}…")
