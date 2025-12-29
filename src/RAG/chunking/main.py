from pathlib import Path
from chunker.hierarchical_legal_chunker import ArticleLevelLegalChunker


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
        chunker = ArticleLevelLegalChunker(
            min_child_size=500,  # ✅ Tham số mới
            max_child_size=1000,  # ✅ Tham số mới
            parent_size_limit=4000,  # ✅ Tham số mới
            chunk_overlap=150,
        )
    # elif chunker_type == "character":
    #     chunker = CharacterChunker(chunk_size=1200, chunk_overlap=200)
    # elif chunker_type == "recursive":
    #     chunker = RecursiveCharacterChunker(chunk_size=1200, chunk_overlap=200)
    else:
        raise ValueError(f"Unknown chunker type: {chunker_type}")

    # Chunk document
    print("\n📑 Đang phân tích và chunking...")
    chunks, stats = chunker.chunk_document(markdown_text)  # ✅ Trả về 2 giá trị

    # Print stats
    print(f"\n✅ Kết quả chunking:")
    print(f"   - Total chunks: {stats['total_chunks']}")
    print(f"   - Parent chunks: {stats['parent_chunks']}")
    print(f"   - Child chunks: {stats['child_chunks']}")
    print(f"   - Avg chunk size: {stats['avg_chunk_size']:.0f} chars")
    print(
        f"   - Size range: {stats['min_chunk_size']} - {stats['max_chunk_size']} chars"
    )

    # Save with filename based on input markdown
    markdown_stem = Path(
        markdown_path
    ).stem  # e.g., "QCDT_2025_5445_QD-DHBK.clean"
    # Remove .clean suffix if present
    if markdown_stem.endswith(".clean"):
        base_name = markdown_stem[:-6]
    else:
        base_name = markdown_stem
    chunks_path = Path(output_dir) / f"{base_name}_chunks.json"
    chunker.save_chunks(chunks, str(chunks_path))

    # Summary
    print("\n" + "=" * 60)
    print("✅ PIPELINE COMPLETED!")
    print("=" * 60)
    print(f"\nOutput: {chunks_path}")
    print(f"Total chunks: {stats['total_chunks']}")
    print(f"  - Parents: {stats['parent_chunks']}")
    print(f"  - Children: {stats['child_chunks']}")
    print("=" * 60)

    return chunks, stats


if __name__ == "__main__":
    # Process all markdown files in output_docling_clean folder
    input_dir = Path("../output_docling_clean")
    output_dir = Path("../chunks_by_articles")

    # Get all .md files
    md_files = list(input_dir.glob("*.md"))

    # Get already chunked files
    existing_chunks = set()
    if output_dir.exists():
        for chunk_file in output_dir.glob("*_chunks.json"):
            # Extract base name (remove _chunks.json suffix)
            base_name = chunk_file.stem.replace("_chunks", "")
            existing_chunks.add(base_name)

    print(f"\n{'=' * 60}")
    print(f"Tìm thấy {len(md_files)} file markdown")
    print(f"Đã chunk: {len(existing_chunks)} file")
    print(f"{'=' * 60}\n")

    # Filter out already chunked files
    files_to_process = []
    for md_file in md_files:
        # Get base name (remove .clean.md or .md suffix)
        stem = md_file.stem
        if stem.endswith(".clean"):
            base_name = stem[:-6]
        else:
            base_name = stem

        if base_name not in existing_chunks:
            files_to_process.append(md_file)
        else:
            print(f"⏭️  Bỏ qua (đã chunk): {md_file.name}")

    print(f"\n{'=' * 60}")
    print(f"Cần chunk: {len(files_to_process)} file")
    print(f"{'=' * 60}\n")

    # Process each file
    for idx, md_file in enumerate(files_to_process, 1):
        print(f"\n{'=' * 60}")
        print(f"[{idx}/{len(files_to_process)}] Processing: {md_file.name}")
        print(f"{'=' * 60}")

        try:
            chunks, stats = main_pipeline(
                markdown_path=str(md_file),
                output_dir=str(output_dir),
                chunker_type="hierarchical",
            )
        except Exception as e:
            print(f"❌ Lỗi khi xử lý {md_file.name}: {e}")
            continue

    print(f"\n{'=' * 60}")
    print("✅ HOÀN THÀNH TẤT CẢ!")
    print(f"{'=' * 60}")
