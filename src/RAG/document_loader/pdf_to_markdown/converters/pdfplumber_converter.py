# pdf_to_markdown/converters/pdfplumber_converter.py
from pdf_to_markdown.base.converter import BasePDFConverter
import pdfplumber
from pathlib import Path
from typing import Dict, Any
import html
import re


def _clean_text(text: str) -> str:
    if not text:
        return ""
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([.,!?;:])", r"\1", text)
    return text.strip()


class PdfPlumberConverter(BasePDFConverter):
    def convert(self, pdf_path: Path) -> Dict[str, Any]:
        print(f"pdfplumber → Đang convert: {pdf_path.name}")

        text_parts = []
        table_parts = []

        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                # Text
                text = _clean_text(page.extract_text() or "")
                if text:
                    text_parts.append(f"## Trang {page_num}\n\n{text}\n")

                # Tables
                tables = page.extract_tables()
                if tables:
                    table_parts.append(f"\n## Bảng - Trang {page_num}\n")
                    for i, table in enumerate(tables, 1):
                        if not table or not table[0]:
                            continue
                        table_parts.append(f"\n### Bảng {i}\n")
                        headers = table[0]
                        table_parts.append(
                            "| "
                            + " | ".join(str(c or "").strip() for c in headers)
                            + " |\n"
                        )
                        table_parts.append("|" + " --- |" * len(headers) + "\n")
                        for row in table[1:]:
                            clean_row = [
                                html.unescape(str(c or "")).strip() for c in row
                            ]
                            table_parts.append(
                                "| " + " | ".join(clean_row) + " |\n"
                            )

        markdown = "\n".join(text_parts + table_parts).strip()
        stem = pdf_path.stem

        md_path = self._save_markdown(markdown, stem)

        # Metadata đơn giản
        metadata = {
            "converter": "pdfplumber",
            "pdf_path": str(pdf_path),
            "num_pages": len(pdf.pages),
            "num_tables": sum(len(p.extract_tables() or []) for p in pdf.pages),
        }
        json_path = self._save_metadata(metadata, stem)

        stats = self._get_stats(
            markdown,
            {
                **metadata,
                "markdown_path": str(md_path),
                "json_path": str(json_path),
            },
        )

        print(
            f"   Đã lưu: {md_path.name} ({stats['num_pages']} trang, {metadata['num_tables']} bảng)"
        )
        return stats
