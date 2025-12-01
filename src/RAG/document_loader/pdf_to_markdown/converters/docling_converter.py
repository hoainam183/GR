# pdf_to_markdown/converters/docling_converter.py
from pdf_to_markdown.base.converter import BasePDFConverter
from docling.document_converter import DocumentConverter
from pathlib import Path
from typing import Dict, Any


class DoclingConverter(BasePDFConverter):
    def __init__(self, output_dir: str = "./output"):
        super().__init__(output_dir)
        self.converter = DocumentConverter()

    def convert(self, pdf_path: Path) -> Dict[str, Any]:
        print(f"Docling → Đang convert: {pdf_path.name}")

        result = self.converter.convert(str(pdf_path))
        markdown = result.document.export_to_markdown()
        doc_dict = result.document.export_to_dict()

        stem = pdf_path.stem
        md_path = self._save_markdown(markdown, stem)
        json_path = self._save_metadata(doc_dict, stem)

        stats = self._get_stats(
            markdown,
            {
                "converter": "docling",
                "pdf_path": str(pdf_path),
                "markdown_path": str(md_path),
                "json_path": str(json_path),
                "num_pages": len(doc_dict.get("pages", [])),
            },
        )

        print(f"   Đã lưu: {md_path.name} ({stats['num_pages']} trang)")
        return stats
