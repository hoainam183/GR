# main.py
from pdf_to_markdown.converters.docling_converter import DoclingConverter
from pdf_to_markdown.converters.pymupdf4llm_converter import (
    PyMuPDF4LLMConverter,
)
from pdf_to_markdown.core.processor import PDFProcessor


if __name__ == "__main__":
    # Chọn converter
    converter = DoclingConverter(output_dir="../output_docling")
    # converter = PdfPlumberConverter(output_dir="../output_pdfplumber")
    # converter = PyMuPDF4LLMConverter(output_dir="../output_pymupdf4llm")
    # converter = PaddleOCRConverter(
    #     output_dir="./ocr_output",
    #     lang="vi",  # Vietnamese, hoặc 'en' cho tiếng Anh
    #     dpi=300,
    #     use_gpu=False,
    # )
    processor = PDFProcessor(converter)

    # Cách 1: Convert 1 file
    # processor.process_single("../quydinh/QD_ngoai_ngu_tu_K68_CQ_final.pdf")

    # Cách 2: Convert cả thư mục
    processor.process_directory(
        pdf_dir="../quydinh", pattern="*.pdf", show_progress=True
    )
