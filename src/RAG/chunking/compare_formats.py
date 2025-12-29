"""
Comparison script: Docling vs PyMuPDF4LLM formats
Shows detection differences and chunking strategy
"""

import re


def analyze_docling_format():
    """Analyze Docling markdown format patterns"""

    docling_samples = [
        "# CHƯƠNG I",
        "## CHƯƠNG II: QUẢN LÝ",
        "## Điều 1. Phạm vi điều chỉnh",
        "### Điều 2. Đối tượng áp dụng",
        "1. Khoản một của điều",
        "a) Điểm a của khoản",
    ]

    print("=" * 80)
    print("📘 DOCLING FORMAT DETECTION")
    print("=" * 80)

    for sample in docling_samples:
        print(f"\nInput: {sample}")

        # Chapter detection
        if re.match(r"^#*\s*CHƯƠNG\s+[IVX\d]+", sample):
            print("  ✅ Detected as: CHAPTER")

        # Article detection
        elif re.match(r"^##?\s*Điều\s+\d+", sample):
            print("  ✅ Detected as: ARTICLE")

        # Numbered point
        elif re.match(r"^\d+\.\s+", sample):
            print("  ✅ Detected as: NUMBERED POINT")

        # Lettered point
        elif re.match(r"^[a-z]\)\s+", sample):
            print("  ✅ Detected as: LETTERED POINT")

        else:
            print("  ⚠️  Not detected (content)")


def analyze_pymupdf_format():
    """Analyze PyMuPDF4LLM bold format patterns"""

    pymupdf_samples = [
        "**CHƯƠNG I**",
        "**Chương II**",
        "**QUẢN LÝ VÀ TỔ CHỨC DẠY, HỌC**",
        "**Điều 1. Phạm vi điều chỉnh và đối tượng áp dụng**",
        "**Điều 4. Đối tượng được miễn, tạm hoãn học môn học GDQP&AN**",
        "1. Thông tư liên tịch này quy định về tổ chức dạy",
        "a) Học sinh, sinh viên có giấy chứng nhận",
    ]

    print("\n\n")
    print("=" * 80)
    print("📕 PYMUPDF4LLM FORMAT DETECTION")
    print("=" * 80)

    for sample in pymupdf_samples:
        print(f"\nInput: {sample}")

        # Clean bold markers
        cleaned = sample.strip().strip("*").strip()

        # Chapter detection
        if re.match(r"^CHƯƠNG\s+[IVX\d]+", cleaned, re.IGNORECASE):
            print(f"  ✅ Detected as: CHAPTER")
            print(f"     Cleaned: {cleaned}")

        # Article detection
        elif re.match(r"^Điều\s+\d+", cleaned):
            print(f"  ✅ Detected as: ARTICLE")
            print(f"     Cleaned: {cleaned}")

        # Numbered point
        elif re.match(r"^\d+\.\s+", sample.strip()):
            print("  ✅ Detected as: NUMBERED POINT")

        # Lettered point
        elif re.match(r"^[a-z]\)\s+", sample.strip()):
            print("  ✅ Detected as: LETTERED POINT")

        else:
            print("  ⚠️  Not detected (content or title)")


def compare_formats():
    """Side-by-side comparison"""

    print("\n\n")
    print("=" * 80)
    print("🔄 FORMAT COMPARISON")
    print("=" * 80)

    comparisons = [
        {
            "element": "Chapter heading",
            "docling": "# CHƯƠNG I",
            "pymupdf": "**CHƯƠNG I**",
            "pattern_docling": r"^#*\s*CHƯƠNG\s+[IVX\d]+",
            "pattern_pymupdf": r"^CHƯƠNG\s+[IVX\d]+ (after stripping **)",
        },
        {
            "element": "Article heading",
            "docling": "## Điều 1. Title",
            "pymupdf": "**Điều 1. Title**",
            "pattern_docling": r"^##?\s*Điều\s+\d+",
            "pattern_pymupdf": r"^Điều\s+\d+ (after stripping **)",
        },
        {
            "element": "Numbered list",
            "docling": "1. Khoản một",
            "pymupdf": "1. Khoản một",
            "pattern_docling": r"^\d+\.\s+",
            "pattern_pymupdf": r"^\d+\.\s+ (same)",
        },
        {
            "element": "Lettered list",
            "docling": "a) Điểm a",
            "pymupdf": "a) Điểm a",
            "pattern_docling": r"^[a-z]\)\s+",
            "pattern_pymupdf": r"^[a-z]\)\s+ (same)",
        },
    ]

    print(
        "\n{:<20} {:<30} {:<30}".format(
            "Element", "Docling Format", "PyMuPDF Format"
        )
    )
    print("-" * 80)

    for comp in comparisons:
        print(f"\n{comp['element']}:")
        print(f"  Docling:  {comp['docling']}")
        print(f"  PyMuPDF:  {comp['pymupdf']}")


def show_key_differences():
    """Highlight key implementation differences"""

    print("\n\n")
    print("=" * 80)
    print("🔑 KEY IMPLEMENTATION DIFFERENCES")
    print("=" * 80)

    differences = [
        {
            "aspect": "Chapter Detection",
            "docling": "Direct regex on markdown headers (#)",
            "pymupdf": "Strip ** first, then regex",
        },
        {
            "aspect": "Article Detection",
            "docling": "Direct regex on markdown headers (##)",
            "pymupdf": "Strip ** first, then regex",
        },
        {
            "aspect": "Bold Text Handling",
            "docling": "Not needed (uses # headers)",
            "pymupdf": "Must strip ** before detection",
        },
        {
            "aspect": "Metadata Field",
            "docling": "source_format: 'docling'",
            "pymupdf": "source_format: 'pymupdf4llm'",
        },
        {
            "aspect": "Chunking Strategy",
            "docling": "Parent-child with chapter context",
            "pymupdf": "Same parent-child strategy",
        },
    ]

    print("\n{:<25} {:<30} {:<30}".format("Aspect", "Docling", "PyMuPDF"))
    print("-" * 85)

    for diff in differences:
        print(f"\n{diff['aspect']}:")
        print(f"  Docling:  {diff['docling']}")
        print(f"  PyMuPDF:  {diff['pymupdf']}")


def show_usage_example():
    """Show usage example"""

    print("\n\n")
    print("=" * 80)
    print("💡 USAGE EXAMPLE")
    print("=" * 80)

    code = """
# For Docling format
from chunker.hierarchical_legal_chunker import ArticleLevelLegalChunker

chunker = ArticleLevelLegalChunker()
chunks, stats = chunker.chunk_document(docling_text)

# For PyMuPDF4LLM format
from chunker.hierarchical_legal_chunker_pymupdf import ArticleLegalChunkerPyMuPDF

chunker = ArticleLegalChunkerPyMuPDF()
chunks, stats = chunker.chunk_document(pymupdf_text)

# Both return same structure:
# - chunks: List[Dict] with parent-child relationships
# - stats: Dict with statistics
"""

    print(code)

    print("\n✅ Both chunkers:")
    print("   - Use same parent-child architecture")
    print("   - Preserve chapter context")
    print("   - Protect tables from splitting")
    print("   - Generate same metadata structure")
    print("   - Only differ in format detection")


if __name__ == "__main__":
    analyze_docling_format()
    analyze_pymupdf_format()
    compare_formats()
    show_key_differences()
    show_usage_example()

    print("\n\n" + "=" * 80)
    print("✅ Comparison completed!")
    print("=" * 80)
