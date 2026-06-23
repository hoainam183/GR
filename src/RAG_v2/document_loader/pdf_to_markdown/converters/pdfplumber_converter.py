# pdf_to_markdown/converters/pdfplumber_converter.py
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from ..base.converter import BasePDFConverter


class PDFPlumberConverter(BasePDFConverter):
    """Converter sử dụng pdfplumber để trích xuất **chỉ bảng** từ PDF.

    Chỉ extract tables, bỏ qua text thường. Phù hợp cho tài liệu
    chứa dữ liệu dạng bảng (danh sách, thống kê, lịch thi, …).
    """

    def convert(self, pdf_path: Path) -> Dict[str, Any]:
        """Convert PDF sang Markdown — chỉ trích xuất bảng."""
        import pdfplumber

        print(f"PDFPlumber (table-only) → Đang convert: {pdf_path.name}")

        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        try:
            sections: List[str] = []
            num_pages = 0
            table_count = 0

            with pdfplumber.open(str(pdf_path)) as pdf:
                num_pages = len(pdf.pages)
                for i, page in enumerate(pdf.pages, start=1):
                    tables = page.extract_tables()
                    if not tables:
                        continue

                    page_tables: List[str] = []
                    if num_pages > 1:
                        page_tables.append(f"## Page {i}\n")

                    for table in tables:
                        md_table = _render_markdown_table(table)
                        if md_table:
                            page_tables.append(md_table)
                            table_count += 1

                    if page_tables:
                        sections.append("\n\n".join(page_tables))

            markdown = "\n\n---\n\n".join(sections) if sections else ""

            stem = pdf_path.stem
            md_path = self._save_markdown(markdown, stem)

            metadata: Dict[str, Any] = {
                "converter": "pdfplumber",
                "pdf_path": str(pdf_path),
                "num_pages": num_pages,
                "table_count": table_count,
            }
            json_path = self._save_metadata(metadata, stem)

            stats = self._get_stats(
                markdown,
                {
                    "converter": "pdfplumber",
                    "pdf_path": str(pdf_path),
                    "markdown_path": str(md_path),
                    "json_path": str(json_path),
                    "num_pages": num_pages,
                    "table_count": table_count,
                },
            )

            print(
                f"   Đã lưu: {md_path.name} "
                f"({table_count} bảng từ {num_pages} trang, {stats['num_chars']} ký tự)"
            )
            return stats

        except Exception as e:
            print(f"   ❌ Lỗi: {str(e)}")
            return {
                "status": "failed",
                "error": str(e),
                "converter": "pdfplumber",
                "pdf_path": str(pdf_path),
            }


def _render_markdown_table(table: List[List[str | None]]) -> str:
    """Render a pdfplumber table (list of rows) as a GFM markdown table."""
    if not table or len(table) < 2:
        return ""

    def _clean_cell(cell: str | None) -> str:
        if cell is None:
            return ""
        return str(cell).replace("|", "\\|").replace("\n", " ").strip()

    header = [_clean_cell(c) for c in table[0]]
    separator = ["---"] * len(header)
    rows = [[_clean_cell(c) for c in row] for row in table[1:]]

    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(separator) + " |",
    ]
    for row in rows:
        # Pad row to match header length
        padded = row + [""] * (len(header) - len(row))
        lines.append("| " + " | ".join(padded[: len(header)]) + " |")

    return "\n".join(lines)
