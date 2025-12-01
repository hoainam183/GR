# main.py
from pdf_to_markdown.converters.docling_converter import DoclingConverter
from pdf_to_markdown.converters.pdfplumber_converter import PdfPlumberConverter
from pdf_to_markdown.converters.paddle_ocr_vl_converter import (
    PaddleOCRVLConverter,
)
from pdf_to_markdown.core.processor import PDFProcessor


if __name__ == "__main__":
    # Chọn converter
    # converter = DoclingConverter(output_dir="../output_docling")
    # converter = PdfPlumberConverter(output_dir="../output_pdfplumber")
    converter = PaddleOCRVLConverter(
        output_dir="../ocr_vl_output",
        dpi=300,  # DPI cao hơn = chất lượng OCR tốt hơn
        save_images=True,  # Giữ lại images để debug
    )
    processor = PDFProcessor(converter)

    # Cách 1: Convert 1 file
    processor.process_single("../quydinh/QCDT_2025_5445_QD-DHBK.pdf")

    # Cách 2: Convert cả thư mục
    # processor.process_directory(
    #     pdf_dir="../quydinh", pattern="*.pdf", show_progress=True
    # )
