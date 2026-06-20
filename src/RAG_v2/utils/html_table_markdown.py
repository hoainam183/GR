"""html_table_markdown
=====================
Chuyển các thẻ ``<table>`` HTML thành bảng Markdown để giữ cấu trúc 2D khi
clean nội dung crawl (kehoach / baiviet). Nhờ vậy retrieval (embedding + BM25)
giữ được liên kết hàng/cột thay vì làm phẳng từng ô thành dòng rời rạc.

Core (`HTMLTableParser`, `convert_table_to_markdown`) được hợp nhất từ
``data/quydinh/olmocr/convert_html_to_markdown_tables.py`` (vốn chỉ dùng cho
quydinh). Bản tại đây là nguồn dùng chung; file quydinh giữ nguyên để không phá
luồng chạy standalone của ``batch_convert.py``.

Đồng bộ định dạng bảng Markdown với ``recursive_chunker``/``olmocr`` (``|...|``)
nên các bước chunk có sẵn (``has_table``, fix mid-table) áp dụng được.
"""

from __future__ import annotations

from html.parser import HTMLParser
from typing import Dict, List

from bs4 import BeautifulSoup, NavigableString


class HTMLTableParser(HTMLParser):
    """Parser đọc một ``<table>`` HTML và trích dữ liệu từng ô."""

    def __init__(self) -> None:
        super().__init__()
        self.tables: List[List[List[Dict]]] = []
        self.current_table: List[List[Dict]] = []
        self.current_row: List[Dict] = []
        self.current_cell: List[str] = []
        self.in_table = False
        self.in_row = False
        self.in_cell = False
        self.cell_type: str | None = None  # 'th' | 'td'
        self.cell_attrs: Dict[str, str] = {}

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)

        if tag == "table":
            self.in_table = True
            self.current_table = []

        elif tag == "tr" and self.in_table:
            self.in_row = True
            self.current_row = []

        elif tag in ["th", "td"] and self.in_row:
            self.in_cell = True
            self.cell_type = tag
            self.current_cell = []
            self.cell_attrs = attrs_dict

        elif tag == "br" and self.in_cell:
            self.current_cell.append(" ")

        elif tag == "b" and self.in_cell:
            self.current_cell.append("**")

    def handle_endtag(self, tag):
        if tag == "table" and self.in_table:
            if self.current_table:
                self.tables.append(self.current_table)
            self.in_table = False
            self.current_table = []

        elif tag == "tr" and self.in_row:
            if self.current_row:
                self.current_table.append(self.current_row)
            self.in_row = False
            self.current_row = []

        elif tag in ["th", "td"] and self.in_cell:
            cell_text = " ".join("".join(self.current_cell).split()).strip()
            colspan = int(self.cell_attrs.get("colspan", 1) or 1)
            rowspan = int(self.cell_attrs.get("rowspan", 1) or 1)

            self.current_row.append(
                {
                    "text": cell_text,
                    "type": self.cell_type,
                    "colspan": colspan,
                    "rowspan": rowspan,
                }
            )

            self.in_cell = False
            self.current_cell = []
            self.cell_attrs = {}

        elif tag == "b" and self.in_cell:
            self.current_cell.append("**")

    def handle_data(self, data):
        if self.in_cell:
            self.current_cell.append(data)


def convert_table_to_markdown(
    table_data: List[List[Dict]],
    fill_rowspan: bool = True,
    fill_empty_from_above: bool = False,
    fill_empty_columns: int = 4,
) -> str:
    """Chuyển dữ liệu bảng đã parse sang Markdown, xử lý rowspan/colspan.

    Args:
        table_data: dữ liệu bảng từ :class:`HTMLTableParser`.
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


def _render_table(table_html: str) -> str:
    """Parse một fragment ``<table>...</table>`` → Markdown (rỗng nếu fail)."""
    parser = HTMLTableParser()
    parser.feed(table_html)
    if not parser.tables:
        return ""
    return convert_table_to_markdown(parser.tables[0])


def replace_tables_with_markdown(soup: BeautifulSoup) -> int:
    """Thay mỗi ``<table>`` trong ``soup`` bằng bảng Markdown (sửa cây tại chỗ).

    Bọc Markdown trong ``\\n...\\n`` để bước normalize giữ mỗi dòng bảng
    riêng biệt. Trả về số bảng đã chuyển. Bảng không parse được sẽ giữ nguyên
    (để vòng xử lý block-tag phía sau vẫn bóc được text thô).
    """
    converted = 0
    # Xử lý từ trong ra ngoài để bảng lồng nhau không bị nuốt theo bảng cha.
    for table in reversed(soup.find_all("table")):
        markdown = _render_table(str(table))
        if not markdown:
            continue
        table.replace_with(NavigableString("\n" + markdown + "\n"))
        converted += 1
    return converted
