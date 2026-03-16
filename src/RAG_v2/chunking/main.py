from pathlib import Path
from chunker.hierarchical_legal_chunker import ArticleLevelLegalChunker
from chunker.olmocr_legal_chunker import OlmOcrLegalChunker
from chunker.recursive_chunker import RecursiveChunker
from chunker.stsv_chunker import STSVChunker


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
        chunker_type: Type of chunker ('hierarchical', 'olmocr', 'character', 'recursive')
            - 'hierarchical': For Docling OCR output (with markdown headings)
            - 'olmocr': For OLM OCR output (plain text, no markdown headings)
    """
    print(f"\n🔪 Bắt đầu chunking: {markdown_path}")
    print(f"   Chunker type: {chunker_type}")

    # Read markdown
    with open(markdown_path, "r", encoding="utf-8") as f:
        markdown_text = f.read()

    # Select chunker
    if chunker_type == "hierarchical":
        # For Docling OCR output (with markdown headings #, ##)
        chunker = ArticleLevelLegalChunker(
            min_child_size=500,
            max_child_size=1000,
            parent_size_limit=4000,
            chunk_overlap=150,
        )
    elif chunker_type == "olmocr":
        # For OLM OCR output (plain text, no markdown headings)
        chunker = OlmOcrLegalChunker(
            min_child_size=300,
            max_child_size=1000,
            parent_size_limit=4000,
            chunk_overlap=100,
        )
    elif chunker_type == "recursive":
        chunker = RecursiveChunker(
            chunk_size=1024,
            chunk_overlap=0,
            parent_chunk_max_chars=10000,
        )
    # elif chunker_type == "character":
    #     chunker = CharacterChunker(chunk_size=1200, chunk_overlap=200)
    else:
        raise ValueError(f"Unknown chunker type: {chunker_type}")

    # Chunk document
    print("\n📑 Đang phân tích và chunking...")
    chunks, stats = chunker.chunk_document(markdown_text)  # ✅ Trả về 2 giá trị

    # Print stats
    print(f"\n✅ Kết quả chunking:")
    print(f"   - Total chunks: {stats['total_chunks']}")
    print(f"   - By level: {stats.get('by_level', {})}")
    if "parent_chunks" in stats:
        print(f"   - Parent chunks: {stats['parent_chunks']}")
        print(f"   - Child chunks: {stats['child_chunks']}")
    print(f"   - Avg chunk size: {stats['avg_chunk_size']:.0f} chars")
    print(
        f"   - Size range: {stats['min_chunk_size']} - {stats['max_chunk_size']} chars"
    )
    if stats.get("chunks_with_tables"):
        print(f"   - Chunks with tables: {stats['chunks_with_tables']}")
    if stats.get("appendix_chunks"):
        print(f"   - Appendix chunks: {stats['appendix_chunks']}")

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
    print(f"By level: {stats.get('by_level', {})}")
    print("=" * 60)

    return chunks, stats


def stsv_pipeline(
    input_dir: str,
    output_dir: str,
    chunk_size: int = 1024,
    chunk_overlap: int = 150,
    long_item_threshold: int = 400,
):
    """
    Pipeline dành riêng cho dữ liệu STSV (định dạng JSON).

    Args:
        input_dir:            Thư mục chứa các file .json STSV
        output_dir:           Thư mục lưu file chunks
        chunk_size:           Kích thước tối đa mỗi chunk (ký tự)
        chunk_overlap:        Overlap giữa các chunk
        long_item_threshold:  Ngưỡng coi mục là "dài" (→ chunk riêng)
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    json_files = sorted(input_path.glob("*.json"))

    print(f"\n{'=' * 60}")
    print(f"📁 Input  : {input_dir}")
    print(f"📂 Output : {output_dir}")
    print(
        f"🔧 Chunker: stsv  (chunk_size={chunk_size}, long_item={long_item_threshold})"
    )
    print(f"{'=' * 60}")
    print(f"Tìm thấy {len(json_files)} file JSON")
    print(f"{'=' * 60}\n")

    chunker = STSVChunker(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        long_item_threshold=long_item_threshold,
    )

    all_chunks = []
    success_count = 0
    error_count = 0

    for idx, fp in enumerate(json_files, 1):
        print(f"[{idx:03d}/{len(json_files)}] {fp.name} ", end="")
        try:
            file_chunks = chunker.chunk_file(fp)
            all_chunks.extend(file_chunks)
            print(f"→ {len(file_chunks)} chunk(s)")
            success_count += 1
        except Exception as exc:
            print(f"❌ LỖI: {exc}")
            error_count += 1

    # --- Save combined output ---
    combined_out = output_path / "stsv_all_chunks.json"
    import json as _json

    with open(combined_out, "w", encoding="utf-8") as f:
        _json.dump(all_chunks, f, ensure_ascii=False, indent=2)

    # --- Stats ---
    sizes = [c["metadata"]["chunk_size"] for c in all_chunks]
    print(f"\n{'=' * 60}")
    print("✅ STSV PIPELINE COMPLETED!")
    print(f"{'=' * 60}")
    print(f"   ✓ Files   : {success_count} / {len(json_files)}")
    if error_count:
        print(f"   ✗ Lỗi    : {error_count}")
    print(f"   Chunks   : {len(all_chunks)}")
    if sizes:
        print(f"   Avg size : {sum(sizes)/len(sizes):.0f} ký tự")
        print(f"   Min/Max  : {min(sizes)} / {max(sizes)} ký tự")
    print(f"   Output   : {combined_out}")
    print(f"{'=' * 60}")

    return all_chunks


def process_folder(
    input_dir: str,
    output_dir: str,
    chunker_type: str = "hierarchical",
    pattern: str = "*.md",
):
    """
    Process all markdown files in a folder

    Args:
        input_dir: Input folder with markdown files
        output_dir: Output folder for chunk JSON files
        chunker_type: 'hierarchical' for Docling OCR, 'olmocr' for OLM OCR
        pattern: Glob pattern for files (default: *.md)
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Get all .md files
    md_files = list(input_path.glob(pattern))

    # Get already chunked files
    existing_chunks = set()
    for chunk_file in output_path.glob("*_chunks.json"):
        base_name = chunk_file.stem.replace("_chunks", "")
        existing_chunks.add(base_name)

    print(f"\n{'=' * 60}")
    print(f"📁 Input: {input_dir}")
    print(f"📂 Output: {output_dir}")
    print(f"🔧 Chunker: {chunker_type}")
    print(f"{'=' * 60}")
    print(f"Tìm thấy {len(md_files)} file markdown")
    print(f"Đã chunk: {len(existing_chunks)} file")
    print(f"{'=' * 60}\n")

    # Filter out already chunked files
    files_to_process = []
    for md_file in md_files:
        stem = md_file.stem
        # Remove common suffixes
        for suffix in [".clean", "_converted", "_cleaned"]:
            if stem.endswith(suffix):
                stem = stem[: -len(suffix)]
                break

        if stem not in existing_chunks:
            files_to_process.append(md_file)
        else:
            print(f"⏭️  Bỏ qua (đã chunk): {md_file.name}")

    print(f"\n{'=' * 60}")
    print(f"Cần chunk: {len(files_to_process)} file")
    print(f"{'=' * 60}\n")

    # Process each file
    success_count = 0
    error_count = 0

    for idx, md_file in enumerate(files_to_process, 1):
        print(f"\n{'=' * 60}")
        print(f"[{idx}/{len(files_to_process)}] Processing: {md_file.name}")
        print(f"{'=' * 60}")

        try:
            chunks, stats = main_pipeline(
                markdown_path=str(md_file),
                output_dir=str(output_path),
                chunker_type=chunker_type,
            )
            success_count += 1
        except Exception as e:
            print(f"❌ Lỗi khi xử lý {md_file.name}: {e}")
            error_count += 1
            continue

    print(f"\n{'=' * 60}")
    print("✅ HOÀN THÀNH TẤT CẢ!")
    print(f"   ✓ Thành công: {success_count} file")
    if error_count > 0:
        print(f"   ✗ Lỗi: {error_count} file")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Chunk legal documents for RAG",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Chunk Docling OCR output (default)
  python main.py --input ../output_docling_clean --output ../chunks_by_articles
  
  # Chunk OLM OCR output
  python main.py --input ../../olmocr/cleaned --output ../olmocr_chunks --chunker olmocr
  
  # Single file
  python main.py --file document.md --output ./chunks --chunker olmocr
        """,
    )

    parser.add_argument(
        "--input", "-i", type=str, help="Input folder with markdown files"
    )
    parser.add_argument(
        "--file", "-f", type=str, help="Single markdown file to process"
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="../chunks_by_articles",
        help="Output folder for chunk JSON files (default: ../chunks_by_articles)",
    )
    parser.add_argument(
        "--chunker",
        "-c",
        type=str,
        choices=["hierarchical", "olmocr", "recursive", "stsv"],
        default="hierarchical",
        help="Chunker type: 'hierarchical' for Docling OCR, 'olmocr' for OLM OCR, 'recursive' for general docs, 'stsv' for student handbook JSON (default: hierarchical)",
    )
    parser.add_argument(
        "--pattern",
        "-p",
        type=str,
        default="*.md",
        help="Glob pattern for input files (default: *.md)",
    )

    args = parser.parse_args()

    if args.chunker == "stsv":
        # STSV JSON pipeline (requires --input folder)
        if not args.input:
            print("❌ --input là bắt buộc khi dùng --chunker stsv")
            parser.print_help()
        else:
            # Default output = <input>/chunks nếu không chỉ định
            out = (
                args.output
                if args.output != "../chunks_by_articles"
                else str(Path(args.input) / "chunks")
            )
            stsv_pipeline(
                input_dir=args.input,
                output_dir=out,
            )
    elif args.file:
        # Process single markdown file
        main_pipeline(
            markdown_path=args.file,
            output_dir=args.output,
            chunker_type=args.chunker,
        )
    elif args.input:
        # Process markdown folder
        process_folder(
            input_dir=args.input,
            output_dir=args.output,
            chunker_type=args.chunker,
            pattern=args.pattern,
        )
    else:
        # Default: process Docling OCR output
        print("No input specified. Use --help for usage.")
        print("\nRunning default: Docling OCR chunking...")
        process_folder(
            input_dir="../output_docling_clean",
            output_dir="../chunks_by_articles",
            chunker_type="hierarchical",
        )
