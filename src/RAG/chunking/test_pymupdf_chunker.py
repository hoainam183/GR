"""
Test script for PyMuPDF4LLM Legal Document Chunker
Demonstrates chunking with PyMuPDF's bold-based format
"""

from pathlib import Path
import json
from chunker.hierarchical_legal_chunker_pymupdf import (
    ArticleLegalChunkerPyMuPDF,
)


def test_pymupdf_chunker():
    """Test the PyMuPDF chunker with a sample document"""

    # Input and output paths
    input_file = Path("../output_pymupdf4llm/QCDT_2025_5445_QD-DHBK.md")
    output_file = Path("chunks_by_articles/pymupdf_test_chunks.json")

    print("=" * 80)
    print("🚀 Testing PyMuPDF4LLM Legal Document Chunker")
    print("=" * 80)

    # Read input file
    if not input_file.exists():
        print(f"❌ File not found: {input_file}")
        return

    with open(input_file, "r", encoding="utf-8") as f:
        content = f.read()

    print(f"✅ Loaded document: {input_file.name}")
    print(f"   Total characters: {len(content):,}")
    print()

    # Initialize chunker
    chunker = ArticleLegalChunkerPyMuPDF(
        min_child_size=500,
        max_child_size=1000,
        parent_size_limit=4000,
        split_threshold=1500,  # Only split articles > 1500 chars
        chunk_overlap=0,  # No overlap for legal docs (clean splits)
    )

    # Process document
    print("⚙️  Processing document...")
    chunks, stats = chunker.chunk_document(content)

    # Display statistics
    print()
    print("=" * 80)
    print("📊 CHUNKING STATISTICS")
    print("=" * 80)
    print(f"Total chunks: {stats['total_chunks']}")
    print(f"Total characters: {stats['total_chars']:,}")
    print(f"Average chunk size: {stats['avg_chunk_size']:.0f} chars")
    print(f"Min chunk size: {stats['min_chunk_size']} chars")
    print(f"Max chunk size: {stats['max_chunk_size']} chars")
    print()

    print("📦 Chunks by level:")
    for level, count in stats["by_level"].items():
        print(f"   {level}: {count}")
    print()

    print(f"👨‍👦 Parent-child relationships:")
    print(f"   Parents: {stats['parent_chunks']}")
    print(f"   Children: {stats['child_chunks']}")
    print(
        f"   Avg children per parent: {stats['child_chunks'] / max(stats['parent_chunks'], 1):.1f}"
    )
    print()

    print(f"📋 Chunks with tables: {stats['chunks_with_tables']}")
    print()

    print("📏 Size distribution:")
    for size_range, count in stats["size_distribution"].items():
        print(f"   {size_range}: {count}")
    print()

    # Display sample chunks
    print("=" * 80)
    print("📄 SAMPLE CHUNKS")
    print("=" * 80)

    # Show header
    header_chunks = [c for c in chunks if c["metadata"]["level"] == "header"]
    if header_chunks:
        print("\n🏷️  HEADER CHUNK:")
        print("-" * 80)
        print(header_chunks[0]["content"][:300] + "...")
        print()

    # Show first parent-child pair
    parent_chunks = [c for c in chunks if c["metadata"]["level"] == "parent"]
    if parent_chunks:
        first_parent = parent_chunks[0]
        print(f"\n👨 PARENT CHUNK: {first_parent['readable_id']}")
        print("-" * 80)
        print(f"Chapter: {first_parent['metadata']['chapter_full']}")
        print(f"Article: {first_parent['metadata']['article_full']}")
        print(f"Size: {first_parent['metadata']['chunk_size']} chars")
        print(f"Has table: {first_parent['metadata']['has_table']}")
        print()
        print("Content preview:")
        print(first_parent["content"][:400] + "...")
        print()

        # Find children of this parent
        children = [
            c
            for c in chunks
            if c["metadata"]["level"] == "child"
            and c["parent_id"] == first_parent["readable_id"]
        ]

        if children:
            print(f"\n👶 CHILD CHUNKS ({len(children)} total):")
            for i, child in enumerate(children[:2], 1):  # Show first 2 children
                print("-" * 80)
                print(f"Child {i}: {child['readable_id']}")
                print(f"Size: {child['metadata']['chunk_size']} chars")
                print()
                print("Content preview:")
                print(child["content"][:300] + "...")
                print()

    # Save chunks
    print("=" * 80)
    chunker.save_chunks(chunks, output_file)

    # Display structure analysis
    print()
    print("=" * 80)
    print("🔍 STRUCTURE ANALYSIS")
    print("=" * 80)

    # Count chapters and articles
    chapters = set()
    articles = set()
    for chunk in chunks:
        meta = chunk["metadata"]
        if meta.get("chapter"):
            chapters.add(meta["chapter"])
        if meta.get("article"):
            articles.add(meta["article"])

    print(f"Unique chapters detected: {len(chapters)}")
    print(f"Unique articles detected: {len(articles)}")
    print()

    # Show parent-child mapping
    print("📊 Parent-Child Mapping (first 5):")
    parent_child_map = {}
    for chunk in chunks:
        if chunk["metadata"]["level"] == "parent":
            parent_id = chunk["readable_id"]
            parent_child_map[parent_id] = []

    for chunk in chunks:
        if chunk["metadata"]["level"] == "child":
            parent_id = chunk.get("parent_id")
            if parent_id in parent_child_map:
                parent_child_map[parent_id].append(chunk["readable_id"])

    for i, (parent_id, children) in enumerate(
        list(parent_child_map.items())[:5], 1
    ):
        print(f"   {parent_id} → {len(children)} children")

    print()
    print("=" * 80)
    print("✅ Testing completed successfully!")
    print("=" * 80)


if __name__ == "__main__":
    test_pymupdf_chunker()
