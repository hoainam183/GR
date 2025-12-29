"""
Embedding Processor - Sử dụng base processor framework
Embeds chunks with skip logic (for vector store)
"""

import sys
from pathlib import Path
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from common import BaseProcessor, FileValidator, OutputChecker
from typing import Dict, Any, Optional, List
from embedding import create_pipeline


class VectorStoreOutputChecker(OutputChecker):
    """
    Custom output checker for vector store
    Checks if chunks from a file already exist in vector store
    """

    def __init__(self, vector_store, output_dir: Path):
        """
        Args:
            vector_store: Vector store instance
            output_dir: Output directory (for logging)
        """
        super().__init__(output_dir, output_suffix="", output_extension="")
        self.vector_store = vector_store

    def should_skip(
        self, input_path: Path, custom_output_name: Optional[str] = None
    ) -> tuple:
        """
        Check if chunks from this file already exist in vector store

        Returns:
            (should_skip, output_identifier)
        """
        # Extract source file name from chunks file
        base_name = input_path.stem

        # Remove _chunks suffix
        if base_name.endswith("_chunks"):
            source_file = base_name[:-7]
        elif base_name.endswith("_final_chunks"):
            source_file = base_name[:-13]
        else:
            source_file = base_name

        # Check if this source file exists in vector store
        try:
            stats = self.vector_store.get_statistics()
            source_files = stats.get("source_files", {})

            if source_file in source_files:
                return True, source_file

        except Exception:
            # Vector store might not exist yet
            pass

        return False, source_file


class EmbeddingProcessor(BaseProcessor):
    """
    Processor for embedding chunks
    Uses existing embedding pipeline with new base processor framework
    """

    def __init__(
        self,
        pipeline,
        chunks_dir: Path,
        recursive: bool = True,
        verbose: bool = True,
        force_reprocess: bool = False,
    ):
        """
        Args:
            pipeline: EmbeddingPipeline instance
            chunks_dir: Directory containing chunk files
            recursive: Duyệt đệ quy
            verbose: In chi tiết log
            force_reprocess: Force reprocess even if already in vector store
        """
        self.pipeline = pipeline
        self.force_reprocess = force_reprocess

        # File validator - JSON only
        file_validator = FileValidator({".json"})

        # Output checker - Vector store
        output_checker = VectorStoreOutputChecker(
            vector_store=pipeline.vector_store, output_dir=chunks_dir
        )

        super().__init__(
            output_dir=chunks_dir,
            file_validator=file_validator,
            output_checker=output_checker,
            recursive=recursive,
            verbose=verbose,
        )

    def process_file(
        self, input_path: Path, output_path: Any
    ) -> Dict[str, Any]:
        """
        Process một file chunks JSON -> Embedding

        Args:
            input_path: Input chunks JSON path
            output_path: Source file name (used as identifier)

        Returns:
            Dict with embedding statistics
        """
        source_file = output_path  # This is actually the source_file name

        # If force reprocess, delete existing documents
        if self.force_reprocess:
            try:
                deleted = self.pipeline.vector_store.delete_by_metadata(
                    {"source_file": source_file}
                )
                if deleted > 0:
                    self._log(
                        f"Deleted {deleted} existing documents for {source_file}",
                        "INFO",
                    )
            except Exception as e:
                self._log(
                    f"Could not delete existing documents: {e}", "WARNING"
                )

        # Process file
        documents = self.pipeline.process_single_file(
            chunks_file=str(input_path),
            source_file=source_file,
            add_to_store=True,
        )

        return {
            "source_file": source_file,
            "total_chunks": len(documents),
            "embedded": True,
        }

    def save_vector_store(self):
        """Save vector store after processing"""
        self._log("Saving vector store...", "INFO")
        self.pipeline.save_vector_store()
        self._log("Vector store saved!", "SUCCESS")

    def process_directory(
        self,
        input_dir: str | Path,
        pattern: str = "*_chunks.json",
        max_files: Optional[int] = None,
        save_after_each: bool = False,
    ) -> List:
        """
        Process directory với auto-save option

        Args:
            input_dir: Input directory
            pattern: File pattern
            max_files: Max files to process
            save_after_each: Save vector store after each file
        """
        # Override to add save functionality
        results = super().process_directory(input_dir, pattern, max_files)

        # Save vector store if not saving after each
        if not save_after_each:
            self.save_vector_store()

        return results

    def _process_single_file(self, input_path: Path):
        """Override to add per-file save option"""
        result = super()._process_single_file(input_path)

        # Optionally save after each file (for safety)
        # Uncomment if needed
        # if result.status == ProcessingStatus.SUCCESS:
        #     self.save_vector_store()

        return result


def main():
    """Example usage"""

    # Initialize pipeline
    pipeline = create_pipeline()

    # Try to load existing vector store
    try:
        pipeline.load_vector_store()
        print("✅ Loaded existing vector store")

        # Show current stats
        stats = pipeline.vector_store.get_statistics()
        print(f"\n📊 Current Vector Store:")
        print(f"   Total documents: {stats['total_documents']}")
        print(f"   Source files: {list(stats['source_files'].keys())}")

    except FileNotFoundError:
        print("⚠️  No existing vector store found. Creating new one...")

    # Initialize processor
    processor = EmbeddingProcessor(
        pipeline=pipeline,
        chunks_dir="../chunks_by_articles",
        recursive=True,
        verbose=True,
        force_reprocess=False,  # Set to True to reprocess all files
    )

    # Option 1: Process single file
    # result = processor.process_single("../chunks_by_articles/QCDT_2025_chunks.json")
    # print(f"\nResult: {result}")
    # print(f"Stats: {result.details}")
    # processor.save_vector_store()

    # Option 2: Process directory
    results = processor.process_directory(
        input_dir="../chunks_by_articles",
        pattern="*_chunks.json",
        # max_files=5,  # Uncomment for testing
        save_after_each=False,  # Save all at once at the end
    )

    # Print results
    print("\n📊 Processing Results:")
    for result in results:
        status_str = result.status.value
        name = result.input_path.name

        if result.details and result.status.value == "success":
            chunks = result.details.get("total_chunks", 0)
            source = result.details.get("source_file", "")
            print(
                f"  {status_str:8s} | {name:50s} | {chunks:4d} chunks | {source}"
            )
        else:
            print(f"  {status_str:8s} | {name}")

    # Final stats
    print("\n📊 Final Vector Store Statistics:")
    stats = pipeline.vector_store.get_statistics()
    print(f"   Total documents: {stats['total_documents']}")
    print(f"   Source files: {len(stats['source_files'])}")
    for source, count in stats["source_files"].items():
        print(f"      - {source}: {count} chunks")

    print("\n" + "=" * 60)
    print("✅ Done!")


if __name__ == "__main__":
    main()
