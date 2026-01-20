"""
Data Cleaning Package for RAG System
=====================================

Package để làm sạch dữ liệu markdown trước khi chunking.
Các module chính:
- cleaners: Các class cleaner cho từng loại dữ liệu thừa
- pipeline: Pipeline xử lý tuần tự các bước làm sạch
- utils: Các hàm tiện ích
- config: Cấu hình cho quá trình làm sạch
"""

from .pipeline import CleaningPipeline
from .cleaners import (
    WhitespaceCleaner,
    TableCleaner,
    HeaderFooterCleaner,
    DuplicateLineCleaner,
    SpecialCharacterCleaner,
    MetadataNormalizer,
)
from .config import CleaningConfig

__all__ = [
    "CleaningPipeline",
    "CleaningConfig",
    "WhitespaceCleaner",
    "TableCleaner",
    "HeaderFooterCleaner",
    "DuplicateLineCleaner",
    "SpecialCharacterCleaner",
    "MetadataNormalizer",
]

__version__ = "1.0.0"
