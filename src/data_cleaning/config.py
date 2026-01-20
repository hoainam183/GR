"""
Configuration Module for Data Cleaning
======================================

Chứa các cấu hình cho quá trình làm sạch dữ liệu.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from pathlib import Path
import json


@dataclass
class CleaningConfig:
    """
    Cấu hình cho quá trình làm sạch dữ liệu markdown.

    Attributes:
        input_dir: Thư mục chứa các file markdown gốc
        output_dir: Thư mục xuất các file đã làm sạch
        backup_enabled: Có tạo backup trước khi xử lý không

        # Whitespace cleaning
        remove_extra_blank_lines: Xóa các dòng trống thừa (>2 dòng liên tiếp)
        max_consecutive_blank_lines: Số dòng trống tối đa cho phép liên tiếp
        trim_trailing_whitespace: Xóa khoảng trắng cuối dòng

        # Table cleaning
        fix_malformed_tables: Sửa các bảng bị lỗi format
        normalize_table_separators: Chuẩn hóa ký tự phân cách bảng
        remove_empty_table_rows: Xóa các hàng trống trong bảng

        # Header/Footer cleaning
        remove_page_numbers: Xóa số trang
        remove_header_artifacts: Xóa các artifact từ header (logo, tên trường lặp lại)

        # Duplicate handling
        remove_duplicate_lines: Xóa các dòng lặp lại liên tiếp
        similarity_threshold: Ngưỡng tương đồng để xác định duplicate (0-1)

        # Special characters
        normalize_unicode: Chuẩn hóa Unicode (NFC)
        fix_ocr_errors: Sửa các lỗi OCR phổ biến

        # Metadata
        extract_document_info: Trích xuất thông tin văn bản (số QĐ, ngày tháng)
        add_metadata_header: Thêm header metadata chuẩn
    """

    # Paths
    input_dir: Path = field(default_factory=lambda: Path("olmocr/converted"))
    output_dir: Path = field(default_factory=lambda: Path("olmocr/cleaned"))
    backup_enabled: bool = True

    # Whitespace cleaning
    remove_extra_blank_lines: bool = True
    max_consecutive_blank_lines: int = 2
    trim_trailing_whitespace: bool = True

    # Table cleaning
    fix_malformed_tables: bool = True
    normalize_table_separators: bool = True
    remove_empty_table_rows: bool = True

    # Header/Footer cleaning
    remove_page_numbers: bool = True
    remove_header_artifacts: bool = True
    header_patterns: List[str] = field(
        default_factory=lambda: [
            r"^BỘ GIÁO DỤC VÀ ĐÀO TẠO$",
            r"^(TRƯỜNG )?ĐẠI HỌC BÁCH KHOA HÀ NỘI$",
            r"^ĐẠI HỌC BÁCH KHOA HÀ NỘI$",
            r"^CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM$",
            r"^Độc lập - Tự do - Hạnh phúc$",
            r"^\d+$",  # Số trang đơn lẻ
        ]
    )

    # Duplicate handling
    remove_duplicate_lines: bool = True
    similarity_threshold: float = 0.95

    # Special characters
    normalize_unicode: bool = True
    fix_ocr_errors: bool = True
    ocr_error_mappings: Dict[str, str] = field(
        default_factory=lambda: {
            "ĐH": "ĐH",  # Có thể bị lỗi font
            "ĐHBK": "ĐHBK",
            "ĐHIBK": "ĐHBK",  # Lỗi OCR phổ biến
            "sachsHT": "sách HT",
            "cóc trà đá": "cốc trà đá",  # Typo
            "cổ văn": "cố vấn",  # Lỗi OCR
            "Mình chừng": "Minh chứng",  # Lỗi OCR trong bảng
        }
    )

    # Metadata
    extract_document_info: bool = False
    add_metadata_header: bool = False

    # Logging
    verbose: bool = True
    log_file: Optional[Path] = None

    def to_dict(self) -> dict:
        """Chuyển config sang dictionary."""
        result = {}
        for key, value in self.__dict__.items():
            if isinstance(value, Path):
                result[key] = str(value)
            else:
                result[key] = value
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "CleaningConfig":
        """Tạo config từ dictionary."""
        if "input_dir" in data:
            data["input_dir"] = Path(data["input_dir"])
        if "output_dir" in data:
            data["output_dir"] = Path(data["output_dir"])
        if "log_file" in data and data["log_file"]:
            data["log_file"] = Path(data["log_file"])
        return cls(**data)

    def save(self, filepath: Path) -> None:
        """Lưu config ra file JSON."""
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, filepath: Path) -> "CleaningConfig":
        """Load config từ file JSON."""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)


# Default config instance
DEFAULT_CONFIG = CleaningConfig()
