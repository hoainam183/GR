"""
Batch convert nhiều PDF files cùng lúc
"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from simple_converter import convert_vietnamese_pdf


def batch_convert(input_dir: str, output_dir: str = "./output_batch"):
    """Convert tất cả PDFs trong một directory"""
    input_path = Path(input_dir)
    output_path = Path(output_dir)

    if not input_path.exists():
        print(f"❌ Directory not found: {input_dir}")
        return

    pdf_files = list(input_path.glob("*.pdf"))

    if not pdf_files:
        print(f"❌ No PDF files found in: {input_dir}")
        return

    print(f"\n📁 Found {len(pdf_files)} PDF files")
    print("=" * 60)

    results = []
    for i, pdf_file in enumerate(pdf_files, 1):
        print(f"\n[{i}/{len(pdf_files)}] {pdf_file.name}")
        print("-" * 60)

        try:
            convert_vietnamese_pdf(str(pdf_file), output_dir)
            results.append({"file": pdf_file.name, "status": "success"})
        except Exception as e:
            print(f"❌ Failed: {e}")
            results.append(
                {"file": pdf_file.name, "status": "failed", "error": str(e)}
            )

    # Summary
    print("\n" + "=" * 60)
    print("📊 SUMMARY")
    print("=" * 60)

    success = [r for r in results if r["status"] == "success"]
    failed = [r for r in results if r["status"] == "failed"]

    print(f"✅ Successful: {len(success)}/{len(results)}")
    print(f"❌ Failed: {len(failed)}/{len(results)}")

    if failed:
        print(f"\n❌ Failed files:")
        for r in failed:
            print(f"   - {r['file']}: {r.get('error', 'Unknown error')}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(
            "Usage: python batch_converter.py <input_directory> [output_directory]"
        )
        print("\nExample:")
        print(
            '  python batch_converter.py "d:/GR/src/extract_from_pdf/quydinh"'
        )
        print('  python batch_converter.py "./pdfs" "./output"')
        sys.exit(1)

    input_dir = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "./output_batch"

    batch_convert(input_dir, output_dir)
