from pathlib import Path
from typing import Dict, Any, List
import fitz  # PyMuPDF
from PIL import Image
import io
from paddleocr import PaddleOCRVL

from pdf_to_markdown.base.converter import BasePDFConverter


class PaddleOCRVLConverter(BasePDFConverter):
    """PDF Converter sử dụng PaddleOCRVL - hỗ trợ tables và layout phức tạp"""

    def __init__(
        self,
        output_dir: str = "./output",
        dpi: int = 300,
        save_images: bool = False,
    ):
        super().__init__(output_dir)
        self.dpi = dpi
        self.save_images = save_images
        self.pipeline = PaddleOCRVL()

        # Thư mục lưu images tạm (nếu cần)
        self.images_dir = self.output_dir / "images"
        if self.save_images:
            self.images_dir.mkdir(exist_ok=True)

    def convert(self, pdf_path: Path) -> Dict[str, Any]:
        """Convert PDF sang Markdown với PaddleOCRVL"""
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        # 1. Convert PDF thành images
        print(f"📄 Converting PDF to images...")
        images = self._pdf_to_images(pdf_path)
        print(f"✅ Extracted {len(images)} pages")

        # 2. OCR từng page với PaddleOCRVL
        print(f"🔍 Running OCR with PaddleOCRVL...")
        markdown_parts = []
        all_results = []

        for page_num, img_path in enumerate(images, start=1):
            print(f"  Processing page {page_num}/{len(images)}...")

            # Predict với PaddleOCRVL
            output = self.pipeline.predict(str(img_path))

            # Lưu kết quả của page này
            for res in output:
                # Lưu markdown của page vào temp
                temp_md_path = self.output_dir / f"_temp_page_{page_num}.md"
                res.save_to_markdown(save_path=str(self.output_dir))

                # Đọc nội dung markdown
                # PaddleOCRVL tạo file với tên theo input image
                generated_md = self._find_generated_markdown(img_path, page_num)

                if generated_md and generated_md.exists():
                    page_content = generated_md.read_text(encoding="utf-8")
                    markdown_parts.append(
                        f"## Page {page_num}\n\n{page_content}"
                    )

                    # Xóa file temp
                    generated_md.unlink()

                # Lưu metadata từ result
                all_results.append(
                    {
                        "page": page_num,
                        "has_tables": self._check_has_tables(res),
                        "num_elements": (
                            len(res.layout_result)
                            if hasattr(res, "layout_result")
                            else 0
                        ),
                    }
                )

        # 3. Ghép tất cả pages thành một markdown file
        full_markdown = "\n\n---\n\n".join(markdown_parts)

        # 4. Lưu markdown cuối cùng
        md_path = self._save_markdown(full_markdown, pdf_path.stem)
        print(f"💾 Markdown saved to: {md_path}")

        # 5. Tạo metadata
        metadata = self._get_stats(
            full_markdown,
            {
                "source_pdf": str(pdf_path),
                "num_pages": len(images),
                "dpi": self.dpi,
                "ocr_engine": "PaddleOCRVL",
                "pages_detail": all_results,
            },
        )
        meta_path = self._save_metadata(metadata, pdf_path.stem)
        print(f"📊 Metadata saved to: {meta_path}")

        # 6. Cleanup: xóa images tạm nếu không cần lưu
        if not self.save_images:
            self._cleanup_images(images)

        return {
            "markdown_path": md_path,
            "metadata_path": meta_path,
            "content": full_markdown,
            "metadata": metadata,
        }

    def _pdf_to_images(self, pdf_path: Path) -> List[Path]:
        """Convert PDF thành list các image paths"""
        doc = fitz.open(pdf_path)
        image_paths = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            # Render với DPI cao để OCR tốt hơn
            mat = fitz.Matrix(self.dpi / 72, self.dpi / 72)
            pix = page.get_pixmap(matrix=mat)

            # Lưu thành PNG
            img_path = (
                self.images_dir / f"{pdf_path.stem}_page_{page_num + 1:03d}.png"
            )
            pix.save(str(img_path))
            image_paths.append(img_path)

        doc.close()
        return image_paths

    def _find_generated_markdown(self, img_path: Path, page_num: int) -> Path:
        """Tìm file markdown được PaddleOCRVL generate"""
        # PaddleOCRVL tạo file markdown với tên dựa trên input image
        expected_name = f"{img_path.stem}.md"
        md_path = self.output_dir / expected_name
        return md_path

    def _check_has_tables(self, result) -> bool:
        """Kiểm tra xem page có table không"""
        if not hasattr(result, "layout_result"):
            return False

        for item in result.layout_result:
            if hasattr(item, "type") and "table" in str(item.type).lower():
                return True
        return False

    def _cleanup_images(self, image_paths: List[Path]):
        """Xóa các image tạm"""
        for img_path in image_paths:
            if img_path.exists():
                img_path.unlink()
