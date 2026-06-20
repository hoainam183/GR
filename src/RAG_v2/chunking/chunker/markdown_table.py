"""markdown_table
================
Helper thuần (không phụ thuộc chunker cụ thể) để xử lý bảng Markdown khi chunk:
phát hiện bảng, bảo vệ bảng khỏi bị cắt giữa hàng, tách bảng lớn theo hàng (lặp
lại header), và vá chunk bị cắt giữa bảng.

Port từ ``recursive_chunker.py`` (``_protect_tables_in_text`` / ``_restore_tables``
/ ``_split_table_by_rows``) + gom các helper vốn nằm rải ở ``kehoach_chunker.py``
để hai chunker dùng chung, tránh trùng lặp.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

# Một dòng bảng Markdown: bắt đầu bằng "|" và còn ít nhất một "|" nữa.
# Dòng separator, vd "|---|---|" hoặc "| :- | -: |".
_RE_TABLE_SEP = re.compile(r"^\|[\s\-|:]+\|$")
# Khối bảng liên tiếp (>=1 dòng "| ... |").
_RE_TABLE_BLOCK = re.compile(r"((?:^\|.+\|$\n?)+)", re.MULTILINE)

# Số hàng tối thiểu mỗi mảnh khi tách bảng lớn, và margin chừa cho prefix.
_MIN_ROWS_PER_CHUNK = 3
_PREFIX_MARGIN = 100


def has_markdown_table(text: str) -> bool:
    """True nếu text chứa ít nhất một dòng bảng Markdown ``| ... |``."""
    for line in (text or "").splitlines():
        s = line.strip()
        if s.startswith("|") and "|" in s[1:]:
            return True
    return False


def starts_mid_table(text: str) -> bool:
    """True nếu chunk bắt đầu giữa bảng (dòng đầu là row nhưng thiếu separator)."""
    lines = [ln for ln in text.strip().splitlines() if ln.strip()]
    if not lines or not lines[0].strip().startswith("|"):
        return False
    if len(lines) < 2:
        return True
    return not _RE_TABLE_SEP.match(lines[1].strip())


def find_table_header(text: str) -> Optional[str]:
    """Tìm cặp (header + separator) của bảng cuối trong text, hoặc None."""
    lines = text.splitlines()
    for i in range(len(lines) - 1, 0, -1):
        if _RE_TABLE_SEP.match(lines[i].strip()) and lines[
            i - 1
        ].strip().startswith("|"):
            return lines[i - 1] + "\n" + lines[i]
    return None


def fix_mid_table_chunks(chunks: List[Dict]) -> List[Dict]:
    """Chèn lại header+separator cho chunk bị cắt giữa bảng (mất header).

    Cập nhật tại chỗ ``content`` + ``metadata.chunk_size`` cho từng chunk dict.
    """
    for i in range(1, len(chunks)):
        content = chunks[i]["content"]
        if starts_mid_table(content):
            header = find_table_header(chunks[i - 1]["content"])
            if header:
                chunks[i]["content"] = header + "\n" + content
                chunks[i]["metadata"]["chunk_size"] = len(chunks[i]["content"])
    return chunks


def protect_tables(
    text: str, max_len: int
) -> Tuple[str, Dict[str, str]]:
    """Thay bảng ``<= max_len`` bằng placeholder để splitter không cắt giữa bảng.

    Bảng lớn hơn ``max_len`` để nguyên (sẽ được tách theo hàng sau đó).
    Trả về ``(text_có_placeholder, map placeholder→bảng)``.
    """
    table_map: Dict[str, str] = {}

    def _replace(match: "re.Match[str]") -> str:
        table_text = match.group(0)
        if len(table_text) <= max_len:
            placeholder = f"__MDTABLE_{len(table_map):04d}__"
            table_map[placeholder] = table_text
            return placeholder
        return table_text

    return _RE_TABLE_BLOCK.sub(_replace, text), table_map


def restore_tables(text: str, table_map: Dict[str, str]) -> str:
    """Khôi phục bảng từ placeholder do :func:`protect_tables` tạo."""
    for placeholder, table_text in table_map.items():
        text = text.replace(placeholder, table_text)
    return text


def split_table_by_rows(
    table_text: str, max_chars: int, heading_prefix: str = ""
) -> List[str]:
    """Tách một bảng Markdown lớn thành nhiều mảnh theo hàng.

    Mỗi mảnh = (``heading_prefix`` nếu có) + header + separator + N hàng dữ liệu,
    nên mọi mảnh đều tự chứa header và ngữ cảnh mục. ``N`` tự tính theo
    ``max_chars`` (>= ``_MIN_ROWS_PER_CHUNK``). Nếu không tách được (thiếu
    header/separator) thì trả về nguyên bảng.
    """
    lines = table_text.strip().splitlines()
    header_line: Optional[str] = None
    separator_line: Optional[str] = None
    data_rows: List[str] = []

    for line in lines:
        if not line.strip().startswith("|"):
            continue
        if separator_line is None:
            if _RE_TABLE_SEP.match(line.strip()):
                separator_line = line
            elif header_line is None:
                header_line = line
            else:
                data_rows.append(header_line)
                header_line = line
        else:
            data_rows.append(line)

    if not header_line or not separator_line or not data_rows:
        return [table_text]

    prefix = f"{heading_prefix.rstrip()}\n" if heading_prefix.strip() else ""
    header_block = header_line + "\n" + separator_line
    overhead = len(prefix) + len(header_block) + _PREFIX_MARGIN

    avg_row_len = sum(len(r) for r in data_rows) / len(data_rows)
    rows_per_chunk = max(
        _MIN_ROWS_PER_CHUNK,
        int(max(1, max_chars - overhead) / (avg_row_len + 1)),
    )

    pieces: List[str] = []
    for start in range(0, len(data_rows), rows_per_chunk):
        batch = data_rows[start : start + rows_per_chunk]
        pieces.append(prefix + header_block + "\n" + "\n".join(batch))
    return pieces
