"""
BATCH PROCESSING - Standalone Pipeline
======================================
Process multiple PDFs without complex dependencies

Usage:
    python batch_standalone.py <directory> [output_dir]

Example:
    python batch_standalone.py "d:/pdfs/" "./output"
"""

import sys
from pathlib import Path
from standalone_pipeline import standalone_pipeline


def batch_process(input_dir: str, output_dir: str = "./batch_output"):
    """
    Process all PDFs in a directory
    """
    input_path = Path(input_dir)

    if not input_path.exists():
        print(f"❌ Directory not found: {input_dir}")
        return

    # Find all PDFs
    pdf_files = list(input_path.glob("*.pdf"))

    if not pdf_files:
        print(f"❌ No PDF files found in: {input_dir}")
        return

    print(f"\n{'='*60}")
    print(f"🔄 BATCH PROCESSING: {len(pdf_files)} PDFs")
    print(f"{'='*60}\n")

    results = []

    for i, pdf_file in enumerate(pdf_files, 1):
        print(f"[{i}/{len(pdf_files)}] {pdf_file.name}")
        print("-" * 60)

        try:
            result = standalone_pipeline(str(pdf_file), output_dir)
            results.append(
                {
                    "file": pdf_file.name,
                    "status": "success",
                    "chunks": result["count"],
                }
            )
        except Exception as e:
            print(f"❌ Error: {e}")
            results.append(
                {"file": pdf_file.name, "status": "failed", "error": str(e)}
            )

        print()  # Blank line between files

    # Summary
    print(f"\n{'='*60}")
    print(f"📊 BATCH SUMMARY")
    print(f"{'='*60}\n")

    success = [r for r in results if r["status"] == "success"]
    failed = [r for r in results if r["status"] == "failed"]

    print(f"✅ Successful: {len(success)}/{len(results)}")
    print(f"❌ Failed: {len(failed)}/{len(results)}")

    if success:
        total_chunks = sum(r["chunks"] for r in success)
        print(f"\n📊 Total chunks created: {total_chunks}")
        print(f"📊 Avg chunks per doc: {total_chunks / len(success):.1f}")

    if failed:
        print(f"\n❌ Failed files:")
        for r in failed:
            print(f"   - {r['file']}: {r.get('error', 'Unknown error')}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python batch_standalone.py <directory> [output_dir]")
        print("\nExample:")
        print('  python batch_standalone.py "d:/pdfs/"')
        print('  python batch_standalone.py "d:/pdfs/" "./my_output"')
        sys.exit(1)

    input_dir = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "./batch_output"

    batch_process(input_dir, output_dir)
