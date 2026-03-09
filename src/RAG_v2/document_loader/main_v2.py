"""
Document Loader Processor - Sử dụng base processor framework
Converts PDF/DOCX to Markdown with skip logic
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from common import BaseProcessor, FileValidator, MultiFileOutputChecker
from typing import Dict, Any


class DocumentLoaderProcessor(BaseProcessor):
    """
    Processor for converting PDF/DOCX to Markdown
    Uses existing converters with new base processor framework
    """

    def __init__(
        self,
        converter,
        output_dir: Path,
        recursive: bool = True,
        verbose: bool = True,
    ):
        """
        Args:
            converter: Converter instance (DoclingConverter, PyMuPDF4LLMConverter, etc.)
            output_dir: Output directory
            recursive: Duyệt đệ quy
            verbose: In chi tiết log
        """
        self.converter = converter

        # File validator - PDF và DOCX
        file_validator = FileValidator({".pdf", ".docx"})

        # Output checker - Markdown + metadata JSON
        output_checker = MultiFileOutputChecker(
            output_dir=Path(output_dir),
            output_patterns=[
                ("", ".md"),  # markdown file
                ("_metadata", ".json"),  # metadata file
            ],
        )

        super().__init__(
            output_dir=output_dir,
            file_validator=file_validator,
            output_checker=output_checker,
            recursive=recursive,
            verbose=verbose,
        )

    def process_file(
        self, input_path: Path, output_path: Path
    ) -> Dict[str, Any]:
        """
        Process một file PDF/DOCX -> Markdown

        Args:
            input_path: Input file path
            output_path: Output file path (not used, converter determines output)

        Returns:
            Dict with processing details
        """
        # Use existing converter
        markdown_text = self.converter.convert_single(str(input_path))

        # Get output paths (converter should have created them)
        base_name = input_path.stem
        md_path = self.output_dir / f"{base_name}.md"
        json_path = self.output_dir / f"{base_name}_metadata.json"

        # Check if files were created
        if not md_path.exists():
            raise FileNotFoundError(f"Markdown file not created: {md_path}")

        # Get file sizes
        md_size = md_path.stat().st_size if md_path.exists() else 0
        json_size = json_path.stat().st_size if json_path.exists() else 0

        return {
            "markdown_file": str(md_path),
            "markdown_size": md_size,
            "metadata_file": str(json_path) if json_path.exists() else None,
            "metadata_size": json_size,
        }


def main():
    """Example usage"""
    from pdf_to_markdown.converters.docling_converter import DoclingConverter
    from pdf_to_markdown.converters.pymupdf4llm_converter import (
        PyMuPDF4LLMConverter,
    )

    # Option 1: Using DoclingConverter
    converter = DoclingConverter(output_dir="../output_docling")
    processor = DocumentLoaderProcessor(
        converter=converter,
        output_dir="../output_docling",
        recursive=True,
        verbose=True,
    )

    # Option 2: Using PyMuPDF4LLMConverter
    # converter = PyMuPDF4LLMConverter(output_dir="../output_pymupdf4llm")
    # processor = DocumentLoaderProcessor(
    #     converter=converter,
    #     output_dir="../output_pymupdf4llm",
    #     recursive=True,
    #     verbose=True,
    # )

    # Process single file
    # result = processor.process_single("../quydinh/QD_ngoai_ngu_tu_K68_CQ_final.pdf")
    # print(f"\nResult: {result}")

    # Process directory
    results = processor.process_directory(
        input_dir="../quydinh",
        pattern="*.pdf",
        # max_files=5,  # Uncomment for testing
    )

    # Print results
    print("\n📊 Processing Results:")
    for result in results:
        print(f"  {result.status.value:8s} | {result.input_path.name}")

    print("\n" + "=" * 60)
    print("✅ Done!")


if __name__ == "__main__":
    main()
