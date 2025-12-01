from docling.document_converter import DocumentConverter
from pathlib import Path
import json
from datetime import datetime


def convert_pdf_to_markdown(
    pdf_path: str, output_dir: str = "./output"
) -> dict:
    """
    Convert PDF sang Markdown với Docling

    Args:
        pdf_path: Đường dẫn đến file PDF
        output_dir: Thư mục lưu output

    Returns:
        dict chứa thông tin conversion
    """
    print(f"📄 Bắt đầu convert PDF: {pdf_path}")
    print(f"⏰ Thời gian: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Tạo output directory
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Khởi tạo DocumentConverter
    converter = DocumentConverter()

    # Convert PDF
    print("🔄 Đang phân tích document...")
    result = converter.convert(pdf_path)

    # Export sang Markdown
    markdown_output = result.document.export_to_markdown()

    # Lưu Markdown file
    pdf_name = Path(pdf_path).stem
    markdown_path = Path(output_dir) / f"{pdf_name}.md"

    with open(markdown_path, "w", encoding="utf-8") as f:
        f.write(markdown_output)

    print(f"✅ Đã lưu Markdown: {markdown_path}")

    # Export sang JSON (để kiểm tra metadata)
    json_output = result.document.export_to_dict()
    json_path = Path(output_dir) / f"{pdf_name}_metadata.json"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_output, f, ensure_ascii=False, indent=2)

    print(f"✅ Đã lưu JSON metadata: {json_path}")

    # Thống kê
    stats = {
        "pdf_path": pdf_path,
        "markdown_path": str(markdown_path),
        "json_path": str(json_path),
        "num_pages": len(json_output.get("pages", [])),
        "num_chars": len(markdown_output),
        "num_lines": len(markdown_output.split("\n")),
        "conversion_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    print(f"\n📊 Thống kê:")
    print(f"   - Số trang: {stats['num_pages']}")
    print(f"   - Số ký tự: {stats['num_chars']:,}")
    print(f"   - Số dòng: {stats['num_lines']:,}")

    return stats


# Test conversion
if __name__ == "__main__":
    pdf_path = "STSV.pdf"
    stats = convert_pdf_to_markdown(pdf_path)
