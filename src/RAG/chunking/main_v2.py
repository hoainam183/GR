"""
Chunking Processor - Sử dụng base processor framework
Chunks Markdown files with skip logic
"""

import sys
from pathlib import Path
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from common import BaseProcessor, FileValidator, JSONOutputChecker
from typing import Dict, Any
from chunker.hierarchical_legal_chunker import ArticleLevelLegalChunker


class ChunkingProcessor(BaseProcessor):
    """
    Processor for chunking Markdown files
    Uses hierarchical legal chunker with new base processor framework
    """

    def __init__(
        self,
        output_dir: Path,
        min_child_size: int = 500,
        max_child_size: int = 1000,
        parent_size_limit: int = 4000,
        chunk_overlap: int = 150,
        recursive: bool = True,
        verbose: bool = True,
    ):
        """
        Args:
            output_dir: Output directory for chunks
            min_child_size: Minimum child chunk size
            max_child_size: Maximum child chunk size
            parent_size_limit: Parent size limit
            chunk_overlap: Overlap between chunks
            recursive: Duyệt đệ quy
            verbose: In chi tiết log
        """
        # File validator - Markdown only
        file_validator = FileValidator({".md"})

        # Output checker - JSON chunks
        output_checker = JSONOutputChecker(
            output_dir=Path(output_dir),
            output_suffix="_chunks",
            output_extension=".json",
        )

        super().__init__(
            output_dir=output_dir,
            file_validator=file_validator,
            output_checker=output_checker,
            recursive=recursive,
            verbose=verbose,
        )

        # Initialize chunker
        self.chunker = ArticleLevelLegalChunker(
            min_child_size=min_child_size,
            max_child_size=max_child_size,
            parent_size_limit=parent_size_limit,
            chunk_overlap=chunk_overlap,
        )

    def process_file(
        self, input_path: Path, output_path: Path
    ) -> Dict[str, Any]:
        """
        Process một file Markdown -> Chunks JSON

        Args:
            input_path: Input markdown file path
            output_path: Output chunks JSON path

        Returns:
            Dict with chunking statistics
        """
        # Read markdown
        with open(input_path, "r", encoding="utf-8") as f:
            markdown_text = f.read()

        # Chunk document
        chunks, stats = self.chunker.chunk_document(markdown_text)

        # Save chunks
        self.chunker.save_chunks(chunks, str(output_path))

        return {
            "output_file": str(output_path),
            "total_chunks": stats["total_chunks"],
            "parent_chunks": stats["parent_chunks"],
            "child_chunks": stats["child_chunks"],
            "avg_chunk_size": stats["avg_chunk_size"],
            "min_chunk_size": stats["min_chunk_size"],
            "max_chunk_size": stats["max_chunk_size"],
        }


def main():
    """Example usage"""

    # Initialize processor
    processor = ChunkingProcessor(
        output_dir="../chunks_by_articles",
        min_child_size=500,
        max_child_size=1000,
        parent_size_limit=4000,
        chunk_overlap=150,
        recursive=True,
        verbose=True,
    )

    # Process single file
    # result = processor.process_single("../output_docling_clean/QCDT_2025.clean.md")
    # print(f"\nResult: {result}")
    # print(f"Stats: {result.details}")

    # Process directory
    results = processor.process_directory(
        input_dir="../output_docling_clean",
        pattern="*.md",
        # max_files=5,  # Uncomment for testing
    )

    # Print results
    print("\n📊 Processing Results:")
    for result in results:
        status_str = result.status.value
        name = result.input_path.name

        if result.details and result.status.value == "success":
            chunks = result.details.get("total_chunks", 0)
            print(f"  {status_str:8s} | {name:50s} | {chunks} chunks")
        else:
            print(f"  {status_str:8s} | {name}")

    print("\n" + "=" * 60)
    print("✅ Done!")


if __name__ == "__main__":
    main()
