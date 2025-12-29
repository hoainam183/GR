"""
Batch processing script for PyMuPDF4LLM legal documents
Processes all .md files in input directory and saves chunks
"""

from pathlib import Path
import json
from chunker.hierarchical_legal_chunker_pymupdf import (
    ArticleLegalChunkerPyMuPDF,
)
from datetime import datetime


def batch_process_pymupdf_documents(
    input_dir: str = "../output_pymupdf4llm",
    output_dir: str = "chunks_by_articles/pymupdf",
    config: dict = None,
):
    """
    Batch process all PyMuPDF4LLM markdown files

    Args:
        input_dir: Directory containing .md files
        output_dir: Directory to save chunk JSON files
        config: Chunker configuration (optional)
    """

    # Default config
    if config is None:
        config = {
            "min_child_size": 500,
            "max_child_size": 1000,
            "parent_size_limit": 4000,
            "split_threshold": 1500,  # Only split articles > 1500 chars
            "chunk_overlap": 0,  # No overlap - clean section splits
        }

    # Setup paths
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Initialize chunker
    chunker = ArticleLegalChunkerPyMuPDF(**config)

    # Find all markdown files
    md_files = list(input_path.glob("*.md"))

    if not md_files:
        print(f"❌ No .md files found in {input_dir}")
        return

    print("=" * 80)
    print(f"🚀 BATCH PROCESSING PyMuPDF4LLM DOCUMENTS")
    print("=" * 80)
    print(f"Input directory: {input_path}")
    print(f"Output directory: {output_path}")
    print(f"Total files: {len(md_files)}")
    print(f"Config: {config}")
    print()

    # Process each file
    results = []
    start_time = datetime.now()

    for i, md_file in enumerate(md_files, 1):
        try:
            print(f"[{i}/{len(md_files)}] Processing: {md_file.name}")

            # Read file
            with open(md_file, "r", encoding="utf-8") as f:
                text = f.read()

            # Chunk document
            chunks, stats = chunker.chunk_document(text)

            # Save chunks
            output_file = output_path / f"{md_file.stem}_chunks.json"
            chunker.save_chunks(chunks, output_file)

            # Record result
            result = {
                "file": md_file.name,
                "status": "success",
                "chunks": stats["total_chunks"],
                "chars": stats["total_chars"],
                "avg_size": stats["avg_chunk_size"],
                "parents": stats["parent_chunks"],
                "children": stats["child_chunks"],
                "tables": stats["chunks_with_tables"],
            }
            results.append(result)

            print(
                f"  ✅ Created {stats['total_chunks']} chunks "
                f"({stats['parent_chunks']} parents, {stats['child_chunks']} children)"
            )
            print()

        except Exception as e:
            print(f"  ❌ Error: {str(e)}")
            results.append(
                {
                    "file": md_file.name,
                    "status": "error",
                    "error": str(e),
                }
            )
            print()

    # Calculate summary
    end_time = datetime.now()
    elapsed = (end_time - start_time).total_seconds()

    successful = [r for r in results if r["status"] == "success"]
    failed = [r for r in results if r["status"] == "error"]

    total_chunks = sum(r.get("chunks", 0) for r in successful)
    total_chars = sum(r.get("chars", 0) for r in successful)

    # Print summary
    print("=" * 80)
    print("📊 PROCESSING SUMMARY")
    print("=" * 80)
    print(f"Total files: {len(md_files)}")
    print(f"Successful: {len(successful)}")
    print(f"Failed: {len(failed)}")
    print(f"Processing time: {elapsed:.2f}s")
    print()

    if successful:
        print(f"Total chunks created: {total_chunks:,}")
        print(f"Total characters: {total_chars:,}")
        print(f"Average chunks per file: {total_chunks / len(successful):.1f}")
        print()

        # Top files by chunk count
        print("📄 Top 5 files by chunk count:")
        top_files = sorted(successful, key=lambda x: x["chunks"], reverse=True)[
            :5
        ]
        for r in top_files:
            print(
                f"  {r['file']}: {r['chunks']} chunks "
                f"({r['parents']} parents, {r['children']} children)"
            )
        print()

    if failed:
        print("❌ Failed files:")
        for r in failed:
            print(f"  {r['file']}: {r['error']}")
        print()

    # Save summary report
    summary_file = output_path / "processing_summary.json"
    summary = {
        "timestamp": datetime.now().isoformat(),
        "config": config,
        "input_dir": str(input_path),
        "output_dir": str(output_path),
        "total_files": len(md_files),
        "successful": len(successful),
        "failed": len(failed),
        "processing_time_seconds": elapsed,
        "total_chunks": total_chunks,
        "total_chars": total_chars,
        "results": results,
    }

    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"💾 Summary saved to: {summary_file}")
    print()
    print("=" * 80)
    print("✅ Batch processing completed!")
    print("=" * 80)

    return summary


def process_with_different_configs():
    """Test different configurations"""

    configs = {
        "conservative": {
            "min_child_size": 700,
            "max_child_size": 1500,
            "parent_size_limit": 5000,
            "chunk_overlap": 200,
        },
        "standard": {
            "min_child_size": 500,
            "max_child_size": 1000,
            "parent_size_limit": 4000,
            "chunk_overlap": 150,
        },
        "aggressive": {
            "min_child_size": 300,
            "max_child_size": 800,
            "parent_size_limit": 3000,
            "chunk_overlap": 100,
        },
    }

    for config_name, config in configs.items():
        print(f"\n\n{'=' * 80}")
        print(f"Testing configuration: {config_name.upper()}")
        print(f"{'=' * 80}\n")

        output_dir = f"chunks_by_articles/pymupdf_{config_name}"
        batch_process_pymupdf_documents(
            output_dir=output_dir,
            config=config,
        )


if __name__ == "__main__":
    # Standard batch processing
    batch_process_pymupdf_documents()

    # Uncomment to test different configurations
    # process_with_different_configs()
