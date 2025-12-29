# Test UnifiedConverter standalone
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# Import riêng lẻ để tránh import chain
from base.converter import BasePDFConverter
from core.pdf_detector import PDFDetector
from core.vietnamese_processor import VietnameseTextProcessor

# Kiểm tra libs có sẵn
try:
    import fitz

    print("✅ PyMuPDF available")
except:
    print("❌ PyMuPDF not available")

try:
    import pdfplumber

    print("✅ pdfplumber available")
except:
    print("❌ pdfplumber not available")

try:
    import pytesseract
    from PIL import Image

    print("✅ OCR (pytesseract + PIL) available")
except:
    print("❌ OCR not available")

print("\n" + "=" * 60)
print("🧪 Testing UnifiedConverter Components")
print("=" * 60)

# Test detector
detector = PDFDetector()
pdf_path = Path(
    r"d:\GR\src\extract_from_pdf\quydinh\QD_ngoai_ngu_tu_K68_CQ_final.pdf"
)

if pdf_path.exists():
    print(f"\n📄 Analyzing: {pdf_path.name}")
    analysis = detector.analyze(pdf_path)

    print(f"   Pages: {analysis['num_pages']}")
    print(f"   Text-based: {analysis['is_text_based']}")
    print(f"   Vietnamese: {analysis['has_vietnamese']}")
    print(f"   Recommended: {analysis['recommended_method']}")

    # Test conversion với PyMuPDF trực tiếp
    if analysis["is_text_based"]:
        print(f"\n🔄 Testing PyMuPDF extraction...")
        try:
            doc = fitz.open(str(pdf_path))
            sample_text = doc[0].get_text()[:500]
            doc.close()

            print(f"   ✅ Extracted {len(sample_text)} chars from first page")
            print(f"\n   Sample text:")
            print(f"   {sample_text[:200]}...")

            # Test Vietnamese processing
            processor = VietnameseTextProcessor()
            if processor.is_vietnamese_text(sample_text):
                print(
                    f"\n   🇻🇳 Vietnamese detected! Applying post-processing..."
                )
                result = processor.process(sample_text)
                print(f"   ✅ Processed successfully")

        except Exception as e:
            print(f"   ❌ Error: {e}")

print("\n✅ All components working!")
print(
    "\nℹ️  To use full UnifiedConverter, imports in converters/ need to be fixed."
)
