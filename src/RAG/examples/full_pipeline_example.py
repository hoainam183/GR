"""
Complete Example - Full RAG Pipeline
Demonstrates document processing from PDF to Vector Store
"""

import sys
from pathlib import Path

# Add to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from document_loader.main_v2 import DocumentLoaderProcessor
from chunking.main_v2 import ChunkingProcessor
from embedding.run_embedding_v2 import EmbeddingProcessor
from document_loader.pdf_to_markdown.converters.docling_converter import (
    DoclingConverter,
)
from embedding import create_pipeline
from common.file_utils import ProcessingStatus


def run_full_pipeline(
    input_pdf_dir: str = "../quydinh",
    pdf_pattern: str = "*.pdf",
    output_markdown_dir: str = "../output_docling",
    output_chunks_dir: str = "../chunks_by_articles",
    max_files: int = None,  # Set to number for testing
):
    """
    Run complete RAG pipeline: PDF → Markdown → Chunks → Embeddings

    Args:
        input_pdf_dir: Directory containing PDF files
        pdf_pattern: Glob pattern for PDF files
        output_markdown_dir: Output directory for markdown files
        output_chunks_dir: Output directory for chunk JSON files
        max_files: Maximum files to process (for testing)
    """

    print("\n" + "=" * 80)
    print(" " * 25 + "FULL RAG PIPELINE")
    print("=" * 80)

    # Statistics
    stats = {
        "pdfs_processed": 0,
        "markdowns_created": 0,
        "chunks_created": 0,
        "embeddings_created": 0,
    }

    # ========================================
    # STEP 1: PDF → Markdown
    # ========================================
    print("\n" + "=" * 80)
    print("STEP 1: Converting PDFs to Markdown")
    print("=" * 80)

    converter = DoclingConverter(output_dir=output_markdown_dir)
    doc_processor = DocumentLoaderProcessor(
        converter=converter,
        output_dir=output_markdown_dir,
        recursive=True,
        verbose=True,
    )

    doc_results = doc_processor.process_directory(
        input_dir=input_pdf_dir,
        pattern=pdf_pattern,
        max_files=max_files,
    )

    # Count results
    stats["pdfs_processed"] = len(
        [r for r in doc_results if r.status == ProcessingStatus.SUCCESS]
    )

    print(f"\n✅ Step 1 Complete: {stats['pdfs_processed']} PDFs converted")

    # ========================================
    # STEP 2: Markdown → Chunks
    # ========================================
    print("\n" + "=" * 80)
    print("STEP 2: Chunking Markdown files")
    print("=" * 80)

    # Use clean markdown directory if it exists
    markdown_input_dir = "../output_docling_clean"
    if not Path(markdown_input_dir).exists():
        markdown_input_dir = output_markdown_dir
        print(
            f"⚠️  Clean markdown directory not found, using: {markdown_input_dir}"
        )

    chunk_processor = ChunkingProcessor(
        output_dir=output_chunks_dir,
        min_child_size=500,
        max_child_size=1000,
        parent_size_limit=4000,
        chunk_overlap=150,
        recursive=True,
        verbose=True,
    )

    chunk_results = chunk_processor.process_directory(
        input_dir=markdown_input_dir,
        pattern="*.md",
        max_files=max_files,
    )

    # Count results
    stats["markdowns_created"] = len(
        [r for r in chunk_results if r.status == ProcessingStatus.SUCCESS]
    )
    stats["chunks_created"] = sum(
        r.details.get("total_chunks", 0)
        for r in chunk_results
        if r.status == ProcessingStatus.SUCCESS
    )

    print(
        f"\n✅ Step 2 Complete: {stats['markdowns_created']} files chunked → {stats['chunks_created']} chunks"
    )

    # ========================================
    # STEP 3: Chunks → Embeddings
    # ========================================
    print("\n" + "=" * 80)
    print("STEP 3: Creating Embeddings")
    print("=" * 80)

    # Initialize embedding pipeline
    pipeline = create_pipeline()

    # Try to load existing vector store
    try:
        pipeline.load_vector_store()
        print("✅ Loaded existing vector store")

        # Show stats
        vs_stats = pipeline.vector_store.get_statistics()
        print(
            f"   Current: {vs_stats['total_documents']} documents from {len(vs_stats['source_files'])} sources"
        )
    except FileNotFoundError:
        print("⚠️  No existing vector store found. Creating new one...")

    emb_processor = EmbeddingProcessor(
        pipeline=pipeline,
        chunks_dir=output_chunks_dir,
        recursive=True,
        verbose=True,
        force_reprocess=False,
    )

    emb_results = emb_processor.process_directory(
        input_dir=output_chunks_dir,
        pattern="*_chunks.json",
        max_files=max_files,
    )

    # Count results
    stats["embeddings_created"] = sum(
        r.details.get("total_chunks", 0)
        for r in emb_results
        if r.status == ProcessingStatus.SUCCESS
    )

    print(
        f"\n✅ Step 3 Complete: {stats['embeddings_created']} embeddings created"
    )

    # ========================================
    # FINAL SUMMARY
    # ========================================
    print("\n" + "=" * 80)
    print(" " * 30 + "PIPELINE SUMMARY")
    print("=" * 80)

    print(f"\n📊 Processing Statistics:")
    print(f"   PDFs converted:       {stats['pdfs_processed']}")
    print(f"   Markdowns chunked:    {stats['markdowns_created']}")
    print(f"   Total chunks:         {stats['chunks_created']}")
    print(f"   Embeddings created:   {stats['embeddings_created']}")

    # Final vector store stats
    vs_stats = pipeline.vector_store.get_statistics()
    print(f"\n📚 Final Vector Store:")
    print(f"   Total documents:      {vs_stats['total_documents']}")
    print(f"   Source files:         {len(vs_stats['source_files'])}")
    print(f"   Embedding dimension:  {vs_stats['dimension']}")

    print("\n" + "=" * 80)
    print("✅ PIPELINE COMPLETE!")
    print("=" * 80)

    return stats


def test_search(query: str = "điều kiện tốt nghiệp", top_k: int = 3):
    """
    Test search functionality

    Args:
        query: Search query
        top_k: Number of results
    """
    from embedding import create_pipeline

    print("\n" + "=" * 80)
    print("TESTING SEARCH FUNCTIONALITY")
    print("=" * 80)

    # Load pipeline
    pipeline = create_pipeline()

    try:
        pipeline.load_vector_store()
        print("✅ Loaded vector store")
    except FileNotFoundError:
        print("❌ Vector store not found. Please run the pipeline first!")
        return

    # Search
    print(f"\n🔍 Query: {query}")
    print(f"   Top K: {top_k}")

    results = pipeline.search(query, top_k=top_k)

    print(f"\n📋 Results ({len(results)} found):")
    print("=" * 80)

    for i, result in enumerate(results, 1):
        print(f"\n{i}. Score: {result.score:.4f}")
        print(f"   Source: {result.metadata.get('source_file', 'N/A')}")

        chapter = result.metadata.get("chapter_full", "")
        if chapter:
            print(f"   Chapter: {chapter}")

        article = result.metadata.get("article_full", "")
        if article:
            print(f"   Article: {article}")

        print(f"\n   Content:")
        content = (
            result.content[:300] + "..."
            if len(result.content) > 300
            else result.content
        )
        print(f"   {content}")
        print("-" * 80)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="RAG Pipeline - Complete Example"
    )
    parser.add_argument(
        "--mode",
        choices=["pipeline", "search", "both"],
        default="both",
        help="Run mode: pipeline, search, or both",
    )
    parser.add_argument(
        "--input-dir", default="../quydinh", help="Input PDF directory"
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=None,
        help="Maximum files to process (for testing)",
    )
    parser.add_argument(
        "--query",
        default="điều kiện tốt nghiệp",
        help="Search query (for search mode)",
    )

    args = parser.parse_args()

    # Run pipeline
    if args.mode in ["pipeline", "both"]:
        stats = run_full_pipeline(
            input_pdf_dir=args.input_dir,
            max_files=args.max_files,
        )

    # Test search
    if args.mode in ["search", "both"]:
        test_search(query=args.query)

    print("\n" + "=" * 80)
    print("✅ ALL DONE!")
    print("=" * 80)
