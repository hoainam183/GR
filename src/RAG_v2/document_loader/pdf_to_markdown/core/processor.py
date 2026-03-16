# pdf_to_markdown/core/processor.py
from pathlib import Path
from typing import List, Dict, Any, Type
from pdf_to_markdown.base.converter import BasePDFConverter


class PDFProcessor:
    def __init__(self, converter: BasePDFConverter):
        self.converter = converter

    def process_single(self, pdf_path: str | Path) -> Dict[str, Any]:
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"Không tìm thấy: {pdf_path}")
        return self.converter.convert(pdf_path)

    def process_directory(
        self,
        pdf_dir: str | Path,
        pattern: str = "*.pdf",
        show_progress: bool = True,
    ) -> List[Dict[str, Any]]:
        pdf_dir = Path(pdf_dir)
        pdf_files = sorted(pdf_dir.glob(pattern))

        if not pdf_files:
            print(f"Không tìm thấy PDF nào trong: {pdf_dir}")
            return []

        results = []
        success = failed = 0

        print(f"Tìm thấy {len(pdf_files)} file PDF\n{'='*60}")

        for i, pdf_file in enumerate(pdf_files, 1):
            if show_progress:
                print(f"\n[{i}/{len(pdf_files)}] {pdf_file.name}")
                print("-" * 50)

            try:
                stat = self.process_single(pdf_file)
                results.append(stat)
                success += 1
            except Exception as e:
                print(f"   Lỗi: {e}")
                results.append(
                    {
                        "pdf_path": str(pdf_file),
                        "status": "failed",
                        "error": str(e),
                    }
                )
                failed += 1

        print(f"\n{'='*60}")
        print(f"HOÀN TẤT: {success} thành công, {failed} thất bại")
        print(f"Output: {self.converter.output_dir}")
        print("=" * 60)

        return results
