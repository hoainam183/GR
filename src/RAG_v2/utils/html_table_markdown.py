"""html_table_markdown
=====================
Chuyển các thẻ ``<table>`` HTML thành bảng Markdown để giữ cấu trúc 2D khi
clean nội dung crawl (kehoach / baiviet). Nhờ vậy retrieval (embedding + BM25)
giữ được liên kết hàng/cột thay vì làm phẳng từng ô thành dòng rời rạc.

Việc parse ô dùng BeautifulSoup (``get_text(separator=" ")``) để chịu được HTML
"bẩn" do dán từ Word (nhiều ``<span class="MsoNormal">``, ``<o:p>``, ``<b>``,
``&nbsp;`` lồng nhau). Engine dựng grid + xử lý rowspan/colspan
(``convert_table_to_markdown``) được hợp nhất từ
``data/quydinh/olmocr/convert_html_to_markdown_tables.py``.

Định dạng bảng Markdown (``|...|``) đồng bộ với ``recursive_chunker``/``olmocr``
nên các bước chunk có sẵn (``has_table``, fix mid-table) áp dụng được.
"""

from __future__ import annotations

import re
from typing import Dict, List

from bs4 import BeautifulSoup, NavigableString, Tag

_WS_RE = re.compile(r"\s+")


def _cell_text(cell: Tag) -> str:
    """Lấy text sạch của một ô: gộp mọi block/inline con, chuẩn hoá khoảng trắng."""
    text = cell.get_text(separator=" ")
    text = text.replace("\xa0", " ")
    # Bỏ ký tự "|" để không phá cột Markdown.
    text = text.replace("|", "/")
    return _WS_RE.sub(" ", text).strip()


def _table_data_from_soup(table: Tag) -> List[List[Dict]]:
    """Trích dữ liệu bảng từ một thẻ ``<table>`` (đã loại bảng lồng)."""
    rows: List[List[Dict]] = []
    for tr in table.find_all("tr"):
        cells: List[Dict] = []
        for cell in tr.find_all(["th", "td"]):
            try:
                colspan = max(1, int(cell.get("colspan", 1) or 1))
            except (TypeError, ValueError):
                colspan = 1
            try:
                rowspan = max(1, int(cell.get("rowspan", 1) or 1))
            except (TypeError, ValueError):
                rowspan = 1
            cells.append(
                {
                    "text": _cell_text(cell),
                    "type": cell.name,
                    "colspan": colspan,
                    "rowspan": rowspan,
                }
            )
        if cells:
            rows.append(cells)
    return rows


def convert_table_to_markdown(
    table_data: List[List[Dict]],
    fill_rowspan: bool = True,
    fill_empty_from_above: bool = False,
    fill_empty_columns: int = 4,
) -> str:
    """Chuyển dữ liệu bảng đã parse sang Markdown, xử lý rowspan/colspan.

    Args:
        table_data: dữ liệu bảng (list các hàng, mỗi ô là dict
            ``{text, type, colspan, rowspan}``).
        fill_rowspan: nếu True, lặp giá trị ô gộp xuống mọi dòng bị span
            (mỗi dòng tự chứa đủ ngữ cảnh → tốt cho retrieval).
        fill_empty_from_above: nếu True, lấp ô trống ở các cột đầu bằng giá
            trị dòng trên. Mặc định False để tránh lấp sai trên bảng đa dạng.
        fill_empty_columns: số cột đầu áp dụng ``fill_empty_from_above``.
    """

    if not table_data:
        return ""

    max_cols = 0
    for row in table_data:
        col_count = sum(cell["colspan"] for cell in row)
        max_cols = max(max_cols, col_count)

    if max_cols == 0:
        return ""

    grid: List[List[Dict | None]] = []
    num_rows = len(table_data) + 10  # dư hàng cho rowspan an toàn
    for _ in range(num_rows):
        grid.append([None] * max_cols)

    for row_idx, row in enumerate(table_data):
        col_idx = 0
        for cell in row:
            while col_idx < max_cols and grid[row_idx][col_idx] is not None:
                col_idx += 1

            if col_idx >= max_cols:
                break

            for r in range(cell["rowspan"]):
                for c in range(cell["colspan"]):
                    target_row = row_idx + r
                    target_col = col_idx + c

                    if target_row < num_rows and target_col < max_cols:
                        if r == 0 and c == 0:
                            grid[target_row][target_col] = {
                                "text": cell["text"],
                                "type": cell["type"],
                                "is_spanned": False,
                                "original_text": cell["text"],
                            }
                        else:
                            grid[target_row][target_col] = {
                                "text": cell["text"] if fill_rowspan else "",
                                "type": cell["type"],
                                "is_spanned": True,
                                "original_text": cell["text"],
                            }

            col_idx += cell["colspan"]

    actual_rows = len(table_data)
    grid = grid[:actual_rows]

    for row_idx in range(len(grid)):
        for col_idx in range(len(grid[row_idx])):
            if grid[row_idx][col_idx] is None:
                grid[row_idx][col_idx] = {
                    "text": "",
                    "type": "td",
                    "is_spanned": False,
                    "original_text": "",
                }

    if fill_empty_from_above:
        for row_idx in range(1, len(grid)):
            for col_idx in range(min(fill_empty_columns, len(grid[row_idx]))):
                cell = grid[row_idx][col_idx]
                if cell["text"] == "" and cell["type"] == "td":
                    above_cell = grid[row_idx - 1][col_idx]
                    if above_cell["text"]:
                        grid[row_idx][col_idx] = {
                            "text": above_cell["text"],
                            "type": cell["type"],
                            "is_spanned": True,
                            "original_text": above_cell["text"],
                        }

    # Đếm số dòng header: dòng đầu mà mọi ô gốc đều là <th>
    header_row_count = 0
    for row_idx, row in enumerate(table_data):
        if all(cell["type"] == "th" for cell in row):
            header_row_count = row_idx + 1
        else:
            break

    if header_row_count == 0:
        header_row_count = 1

    # Nếu mọi dòng đều là header → chỉ lấy dòng đầu làm header,
    # tránh bỏ rơi các dòng còn lại như "data rows".
    if header_row_count >= len(grid):
        header_row_count = 1

    md_lines: List[str] = []

    if header_row_count > 1:
        parent_headers: Dict[int, str] = {}
        first_col_of_colspan: Dict[int, str] = {}

        col_idx = 0
        for cell in table_data[0]:
            if cell["colspan"] > 1:
                first_col_of_colspan[col_idx] = cell["text"]
                for c in range(cell["colspan"]):
                    parent_headers[col_idx + c] = cell["text"]
            col_idx += cell["colspan"]

        combined_header = [""] * max_cols
        header_filled = [False] * max_cols

        for row_idx in range(header_row_count):
            for col_idx in range(max_cols):
                cell = grid[row_idx][col_idx]
                cell_text = cell["text"]
                is_spanned = cell.get("is_spanned", False)

                if header_filled[col_idx]:
                    continue

                parent = parent_headers.get(col_idx, "")
                is_first_of_colspan = col_idx in first_col_of_colspan

                if row_idx == 0 and is_first_of_colspan:
                    continue

                if cell_text and not is_spanned:
                    if parent:
                        combined_header[col_idx] = parent + " " + cell_text
                    else:
                        combined_header[col_idx] = cell_text
                    header_filled[col_idx] = True
                elif cell_text and is_spanned and not parent:
                    combined_header[col_idx] = cell_text
                    header_filled[col_idx] = True

        md_lines.append("| " + " | ".join(combined_header) + " |")
    else:
        md_lines.append(
            "| " + " | ".join(cell["text"] for cell in grid[0]) + " |"
        )

    md_lines.append("|" + "|".join(["---"] * max_cols) + "|")

    for row_idx in range(header_row_count, len(grid)):
        md_lines.append(
            "| " + " | ".join(cell["text"] for cell in grid[row_idx]) + " |"
        )

    return "\n".join(md_lines)


def table_to_markdown(table: Tag) -> str:
    """Render một thẻ ``<table>`` (BeautifulSoup) thành Markdown ('' nếu rỗng)."""
    return convert_table_to_markdown(_table_data_from_soup(table))


def replace_tables_with_markdown(soup: BeautifulSoup) -> int:
    """Thay mỗi ``<table>`` trong ``soup`` bằng bảng Markdown (sửa cây tại chỗ).

    Bọc Markdown trong ``\\n...\\n`` để bước normalize giữ mỗi dòng bảng
    riêng biệt. Trả về số bảng đã chuyển. Bảng không parse được sẽ giữ nguyên
    (để vòng xử lý block-tag phía sau vẫn bóc được text thô).

    Xử lý từ trong ra ngoài (``reversed``) để bảng lồng nhau được chuyển trước,
    không bị bảng cha nuốt theo.
    """
    converted = 0
    for table in reversed(soup.find_all("table")):
        markdown = table_to_markdown(table)
        if not markdown:
            continue
        table.replace_with(NavigableString("\n" + markdown + "\n"))
        converted += 1
    return converted
