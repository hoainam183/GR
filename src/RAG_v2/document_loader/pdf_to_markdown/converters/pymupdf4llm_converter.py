# pdf_to_markdown/converters/pymupdf4llm_converter.py
from ..base.converter import BasePDFConverter
from pathlib import Path
from typing import Dict, Any
import pymupdf4llm


class PyMuPDF4LLMConverter(BasePDFConverter):
    """Converter sử dụng pymupdf4llm để chuyển PDF sang Markdown"""

    def __init__(self, output_dir: str = "./output", **kwargs):
        """
        Args:
            output_dir: Thư mục lưu output
            **kwargs: Các tham số bổ sung cho pymupdf4llm.to_markdown()
                - page_chunks: bool, chia theo page
                - write_images: bool, xuất images
                - image_path: str, thư mục lưu images
                - dpi: int, DPI cho images
        """
        super().__init__(output_dir)
        self.conversion_options = kwargs

    def convert(self, pdf_path: Path) -> Dict[str, Any]:
        """Convert PDF sang Markdown sử dụng pymupdf4llm"""
        print(f"PyMuPDF4LLM → Đang convert: {pdf_path.name}")

        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        try:
            # Convert PDF sang markdown
            markdown = pymupdf4llm.to_markdown(
                str(pdf_path), **self.conversion_options
            )

            # Lưu markdown và metadata
            stem = pdf_path.stem
            md_path = self._save_markdown(markdown, stem)

            # Tạo metadata dictionary
            metadata = {
                "converter": "pymupdf4llm",
                "pdf_path": str(pdf_path),
                "conversion_options": self.conversion_options,
            }
            json_path = self._save_metadata(metadata, stem)

            # Thu thập stats
            stats = self._get_stats(
                markdown,
                {
                    "converter": "pymupdf4llm",
                    "pdf_path": str(pdf_path),
                    "markdown_path": str(md_path),
                    "json_path": str(json_path),
                },
            )

            print(f"   Đã lưu: {md_path.name} ({stats['num_chars']} ký tự)")
            return stats

        except Exception as e:
            print(f"   ❌ Lỗi: {str(e)}")
            return {
                "status": "failed",
                "error": str(e),
                "converter": "pymupdf4llm",
                "pdf_path": str(pdf_path),
            }

    def convert_with_images(
        self, pdf_path: Path, image_dir: str = None, dpi: int = 150
    ) -> Dict[str, Any]:
        """Convert PDF với hỗ trợ xuất images"""
        if image_dir is None:
            image_dir = str(self.output_dir / "images")

        print(f"PyMuPDF4LLM → Đang convert (with images): {pdf_path.name}")

        # Cập nhật options để xuất images
        options = {
            **self.conversion_options,
            "write_images": True,
            "image_path": image_dir,
            "dpi": dpi,
        }

        # Tạo temporary converter với options mới
        temp_converter = PyMuPDF4LLMConverter(
            output_dir=str(self.output_dir), **options
        )

        result = temp_converter.convert(pdf_path)

        if result.get("status") == "success":
            print(f"   Images đã lưu tại: {image_dir}")

        return result
