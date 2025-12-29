"""
Simple Examples - RAG Pipeline
Các ví dụ đơn giản để bắt đầu
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def example_1_convert_single_pdf():
    """
    Example 1: Convert một file PDF sang Markdown
    """
    print("\n" + "=" * 60)
    print("Example 1: Convert single PDF to Markdown")
    print("=" * 60)

    from document_loader.main_v2 import DocumentLoaderProcessor
    from document_loader.pdf_to_markdown.converters.docling_converter import (
        DoclingConverter,
    )

    # Setup
    converter = DoclingConverter(output_dir="../output_docling")
    processor = DocumentLoaderProcessor(
        converter=converter,
        output_dir="../output_docling",
        verbose=True,
    )

    # Process
    result = processor.process_single("../quydinh/my_document.pdf")

    # Check result
    print(f"\n📊 Result:")
    print(f"   Status: {result.status.value}")
    print(f"   Input: {result.input_path}")
    print(f"   Output: {result.output_path}")

    if result.details:
        print(
            f"   Markdown size: {result.details.get('markdown_size', 0)} bytes"
        )


def example_2_convert_directory():
    """
    Example 2: Convert tất cả PDFs trong thư mục
    """
    print("\n" + "=" * 60)
    print("Example 2: Convert directory of PDFs")
    print("=" * 60)

    from document_loader.main_v2 import DocumentLoaderProcessor
    from document_loader.pdf_to_markdown.converters.docling_converter import (
        DoclingConverter,
    )

    # Setup
    converter = DoclingConverter(output_dir="../output_docling")
    processor = DocumentLoaderProcessor(
        converter=converter,
        output_dir="../output_docling",
        verbose=True,
    )

    # Process directory (limit to 3 files for demo)
    results = processor.process_directory(
        input_dir="../quydinh",
        pattern="*.pdf",
        max_files=3,
    )

    # Summary
    print(f"\n📊 Summary:")
    print(f"   Total: {len(results)}")
    print(
        f"   Success: {len([r for r in results if r.status.value == 'success'])}"
    )
    print(
        f"   Skipped: {len([r for r in results if r.status.value == 'skipped'])}"
    )


def example_3_chunk_markdown():
    """
    Example 3: Chunk một file Markdown
    """
    print("\n" + "=" * 60)
    print("Example 3: Chunk Markdown file")
    print("=" * 60)

    from chunking.main_v2 import ChunkingProcessor

    # Setup
    processor = ChunkingProcessor(
        output_dir="../chunks_by_articles",
        verbose=True,
    )

    # Process
    result = processor.process_single(
        "../output_docling_clean/my_document.clean.md"
    )

    # Check result
    print(f"\n📊 Result:")
    print(f"   Status: {result.status.value}")

    if result.details:
        print(f"   Total chunks: {result.details.get('total_chunks', 0)}")
        print(f"   Parent chunks: {result.details.get('parent_chunks', 0)}")
        print(f"   Child chunks: {result.details.get('child_chunks', 0)}")


def example_4_create_embeddings():
    """
    Example 4: Tạo embeddings từ chunks
    """
    print("\n" + "=" * 60)
    print("Example 4: Create embeddings")
    print("=" * 60)

    from embedding.run_embedding_v2 import EmbeddingProcessor
    from embedding import create_pipeline

    # Initialize pipeline
    pipeline = create_pipeline()

    # Load existing vector store (if any)
    try:
        pipeline.load_vector_store()
        print("✅ Loaded existing vector store")
    except FileNotFoundError:
        print("⚠️  Creating new vector store")

    # Setup processor
    processor = EmbeddingProcessor(
        pipeline=pipeline,
        chunks_dir="../chunks_by_articles",
        verbose=True,
    )

    # Process single file
    result = processor.process_single(
        "../chunks_by_articles/my_document_chunks.json"
    )

    # Save
    processor.save_vector_store()

    # Check result
    print(f"\n📊 Result:")
    print(f"   Status: {result.status.value}")

    if result.details:
        print(f"   Chunks embedded: {result.details.get('total_chunks', 0)}")


def example_5_search_documents():
    """
    Example 5: Search trong vector store
    """
    print("\n" + "=" * 60)
    print("Example 5: Search documents")
    print("=" * 60)

    from embedding import create_pipeline

    # Load pipeline
    pipeline = create_pipeline()

    try:
        pipeline.load_vector_store()
        print("✅ Loaded vector store")
    except FileNotFoundError:
        print("❌ Vector store not found!")
        return

    # Search
    query = "điều kiện tốt nghiệp"
    print(f"\n🔍 Searching for: '{query}'")

    results = pipeline.search(query, top_k=5)

    print(f"\n📋 Found {len(results)} results:")

    for i, result in enumerate(results, 1):
        print(f"\n{i}. Score: {result.score:.4f}")
        print(f"   Source: {result.metadata.get('source_file', 'N/A')}")
        print(f"   Content: {result.content[:200]}...")


def example_6_batch_process():
    """
    Example 6: Batch processing nhiều files
    """
    print("\n" + "=" * 60)
    print("Example 6: Batch processing")
    print("=" * 60)

    from chunking.main_v2 import ChunkingProcessor

    # Setup
    processor = ChunkingProcessor(
        output_dir="../chunks_by_articles",
        verbose=True,
    )

    # Process directory
    results = processor.process_directory(
        input_dir="../output_docling_clean",
        pattern="*.md",
        max_files=5,  # Process 5 files
    )

    # Detailed summary
    print(f"\n📊 Detailed Results:")

    for result in results:
        name = result.input_path.name
        status = result.status.value

        if status == "success" and result.details:
            chunks = result.details.get("total_chunks", 0)
            print(f"   ✅ {name}: {chunks} chunks")
        elif status == "skipped":
            print(f"   ⏭️  {name}: Already processed")
        elif status == "failed":
            print(f"   ❌ {name}: {result.message}")


def example_7_custom_configuration():
    """
    Example 7: Custom configuration cho chunking
    """
    print("\n" + "=" * 60)
    print("Example 7: Custom chunking configuration")
    print("=" * 60)

    from chunking.main_v2 import ChunkingProcessor

    # Setup với custom parameters
    processor = ChunkingProcessor(
        output_dir="../chunks_by_articles",
        min_child_size=300,  # Smaller chunks
        max_child_size=800,
        parent_size_limit=3000,
        chunk_overlap=100,
        verbose=True,
    )

    # Process
    result = processor.process_single(
        "../output_docling_clean/my_document.clean.md"
    )

    print(f"\n📊 Custom chunking result:")
    if result.details:
        print(f"   Total chunks: {result.details.get('total_chunks', 0)}")
        print(f"   Avg size: {result.details.get('avg_chunk_size', 0):.0f}")


def example_8_skip_logic():
    """
    Example 8: Demonstrate skip logic
    """
    print("\n" + "=" * 60)
    print("Example 8: Skip logic demonstration")
    print("=" * 60)

    from chunking.main_v2 import ChunkingProcessor

    processor = ChunkingProcessor(
        output_dir="../chunks_by_articles",
        verbose=True,
    )

    # First run - will process
    print("\n--- First run ---")
    result1 = processor.process_single(
        "../output_docling_clean/test_document.clean.md"
    )
    print(f"Status: {result1.status.value}")

    # Second run - should skip
    print("\n--- Second run (should skip) ---")
    result2 = processor.process_single(
        "../output_docling_clean/test_document.clean.md"
    )
    print(f"Status: {result2.status.value}")
    print(f"Message: {result2.message}")


def example_9_error_handling():
    """
    Example 9: Error handling
    """
    print("\n" + "=" * 60)
    print("Example 9: Error handling")
    print("=" * 60)

    from document_loader.main_v2 import DocumentLoaderProcessor
    from document_loader.pdf_to_markdown.converters.docling_converter import (
        DoclingConverter,
    )

    converter = DoclingConverter(output_dir="../output_docling")
    processor = DocumentLoaderProcessor(
        converter=converter,
        output_dir="../output_docling",
        verbose=True,
    )

    # Try to process non-existent file
    result = processor.process_single("../quydinh/non_existent_file.pdf")

    print(f"\n📊 Result:")
    print(f"   Status: {result.status.value}")
    print(f"   Message: {result.message}")

    # Try to process invalid file type
    result2 = processor.process_single("../quydinh/image.jpg")

    print(f"\n📊 Result 2:")
    print(f"   Status: {result2.status.value}")
    print(f"   Message: {result2.message}")


def example_10_statistics():
    """
    Example 10: Get processing statistics
    """
    print("\n" + "=" * 60)
    print("Example 10: Processing statistics")
    print("=" * 60)

    from chunking.main_v2 import ChunkingProcessor

    processor = ChunkingProcessor(
        output_dir="../chunks_by_articles",
        verbose=True,
    )

    # Process directory
    results = processor.process_directory(
        input_dir="../output_docling_clean",
        pattern="*.md",
        max_files=5,
    )

    # Get statistics
    stats = processor.get_statistics()

    print(f"\n📊 Statistics:")
    print(f"   Total files: {stats['total_files']}")
    print(f"   Processed: {stats['processed']}")
    print(f"   Skipped: {stats['skipped']}")
    print(f"   Failed: {stats['failed']}")
    print(f"   Invalid: {stats['invalid']}")

    if stats["start_time"] and stats["end_time"]:
        duration = (stats["end_time"] - stats["start_time"]).total_seconds()
        print(f"   Duration: {duration:.2f}s")

        if stats["processed"] > 0:
            print(f"   Avg time per file: {duration / stats['processed']:.2f}s")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print(" " * 20 + "RAG PIPELINE - SIMPLE EXAMPLES")
    print("=" * 70)

    # Uncomment examples you want to run:

    # example_1_convert_single_pdf()
    # example_2_convert_directory()
    # example_3_chunk_markdown()
    # example_4_create_embeddings()
    # example_5_search_documents()
    # example_6_batch_process()
    # example_7_custom_configuration()
    # example_8_skip_logic()
    # example_9_error_handling()
    example_10_statistics()

    print("\n" + "=" * 70)
    print("✅ Done!")
    print("=" * 70)
