from pathlib import Path
from chunker.hierarchical_legal_chunker import HierarchicalLegalChunker


def main_pipeline(
    markdown_path: str,
    output_dir: str = "../chunks_by_articles",
    chunker_type: str = "hierarchical",
):
    """
    Main chunking pipeline

    Args:
        markdown_path: Path to markdown file
        output_dir: Output directory for chunks
        chunker_type: Type of chunker ('hierarchical', 'character', 'recursive')
    """
    print(f"\n🔪 Bắt đầu chunking: {markdown_path}")
    print(f"   Chunker type: {chunker_type}")

    # Read markdown
    with open(markdown_path, "r", encoding="utf-8") as f:
        markdown_text = f.read()

    # Select chunker
    if chunker_type == "hierarchical":
        chunker = HierarchicalLegalChunker(chunk_size=1200, chunk_overlap=200)
    # elif chunker_type == "character":
    #     chunker = CharacterChunker(chunk_size=1200, chunk_overlap=200)
    # elif chunker_type == "recursive":
    #     chunker = RecursiveCharacterChunker(chunk_size=1200, chunk_overlap=200)
    else:
        raise ValueError(f"Unknown chunker type: {chunker_type}")

    # Chunk document
    print("\n📑 Đang phân tích và chunking...")
    chunks = chunker.chunk_document(markdown_text)
    print(f"✅ Đã tạo: {len(chunks)} chunks")

    # Validate
    print("\n🔍 Validating chunks...")
    stats = chunker.validate_chunks(chunks)

    # Save
    chunks_path = Path(output_dir) / "chunks.json"
    chunker.save_chunks(chunks, str(chunks_path))

    # Summary
    print("\n" + "=" * 60)
    print("✅ PIPELINE COMPLETED!")
    print("=" * 60)
    print(f"\nOutput: {chunks_path}")
    print(f"Total chunks: {len(chunks)}")
    print("=" * 60)

    return chunks


if __name__ == "__main__":
    # Example 1: Hierarchical chunking for legal documents
    markdown_path = "../output_docling_clean/QCDT_2025_5445_QD-DHBK.clean.md"

    chunks = main_pipeline(
        markdown_path=markdown_path,
        output_dir="../chunks_by_articles",
        chunker_type="hierarchical",  # Options: 'hierarchical', 'character', 'recursive'
    )
