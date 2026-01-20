"""
Metadata Normalizer Module
==========================

Trích xuất và chuẩn hóa metadata từ văn bản:
- Số quyết định
- Ngày ban hành
- Loại văn bản
- Đơn vị ban hành
"""

import re
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime

from .base import BaseCleaner, CleaningResult


@dataclass
class DocumentMetadata:
    """Metadata của một văn bản."""

    document_type: str = ""  # QUYẾT ĐỊNH, THÔNG TƯ, NGHỊ ĐỊNH, etc.
    document_number: str = ""  # Số văn bản
    issue_date: str = ""  # Ngày ban hành
    issuer: str = ""  # Đơn vị ban hành
    title: str = ""  # Tiêu đề văn bản
    effective_date: str = ""  # Ngày có hiệu lực
    keywords: List[str] = field(default_factory=list)  # Từ khóa

    def to_markdown_header(self) -> str:
        """Tạo markdown header từ metadata."""
        lines = ["---"]
        if self.document_type:
            lines.append(f"loai_van_ban: {self.document_type}")
        if self.document_number:
            lines.append(f"so_van_ban: {self.document_number}")
        if self.issue_date:
            lines.append(f"ngay_ban_hanh: {self.issue_date}")
        if self.issuer:
            lines.append(f"don_vi_ban_hanh: {self.issuer}")
        if self.title:
            lines.append(f"tieu_de: {self.title}")
        if self.effective_date:
            lines.append(f"ngay_hieu_luc: {self.effective_date}")
        if self.keywords:
            lines.append(f"tu_khoa: {', '.join(self.keywords)}")
        lines.append("---")
        lines.append("")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Chuyển metadata sang dictionary."""
        return {
            "document_type": self.document_type,
            "document_number": self.document_number,
            "issue_date": self.issue_date,
            "issuer": self.issuer,
            "title": self.title,
            "effective_date": self.effective_date,
            "keywords": self.keywords,
        }


class MetadataNormalizer(BaseCleaner):
    """
    Cleaner trích xuất và chuẩn hóa metadata văn bản.

    Config options:
        extract_metadata (bool): Có trích xuất metadata không (default: True)
        add_frontmatter (bool): Thêm YAML frontmatter (default: True)
        normalize_document_number (bool): Chuẩn hóa số văn bản (default: True)
    """

    # Patterns để trích xuất thông tin
    DOCUMENT_TYPE_PATTERNS = {
        "QUYẾT ĐỊNH": r"QUYẾT ĐỊNH|QUY[EÊ]́?T Đ[IỊ]NH",
        "THÔNG TƯ": r"THÔNG TƯ",
        "NGHỊ ĐỊNH": r"NGHỊ ĐỊNH|NGH[IỊ] Đ[IỊ]NH",
        "QUY ĐỊNH": r"QUY ĐỊNH|QUY Đ[IỊ]NH",
        "QUY CHẾ": r"QUY CHẾ|QUY CH[EÊ]́?",
        "HƯỚNG DẪN": r"HƯỚNG DẪN",
    }

    # Pattern số văn bản
    DOCUMENT_NUMBER_PATTERN = re.compile(
        r"[Ss]ố[:\s]*(\d+[\s/]*(QĐ|TT|NĐ|NQ|CV|HD)?[-–/]?[\w\-]*)", re.UNICODE
    )

    # Pattern ngày tháng
    DATE_PATTERNS = [
        # "ngày 28 tháng 5 năm 2025"
        re.compile(
            r"ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})",
            re.IGNORECASE,
        ),
        # "28/5/2025" hoặc "28-5-2025"
        re.compile(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})"),
        # "ngày 28/5/2025"
        re.compile(r"ngày\s+(\d{1,2})[/-](\d{1,2})[/-](\d{4})", re.IGNORECASE),
    ]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.extract_metadata = self.config.get("extract_metadata", True)
        self.add_frontmatter = self.config.get("add_frontmatter", True)
        self.normalize_docnum = self.config.get(
            "normalize_document_number", True
        )

    @property
    def name(self) -> str:
        return "MetadataNormalizer"

    @property
    def description(self) -> str:
        return "Trích xuất và chuẩn hóa metadata văn bản"

    def _extract_document_type(self, content: str) -> str:
        """Trích xuất loại văn bản."""
        for doc_type, pattern in self.DOCUMENT_TYPE_PATTERNS.items():
            if re.search(pattern, content, re.IGNORECASE):
                return doc_type
        return ""

    def _extract_document_number(self, content: str) -> str:
        """Trích xuất số văn bản."""
        match = self.DOCUMENT_NUMBER_PATTERN.search(content)
        if match:
            number = match.group(1).strip()
            # Chuẩn hóa format
            if self.normalize_docnum:
                number = re.sub(r"\s+", "", number)  # Xóa khoảng trắng
                number = number.replace("–", "-")  # Chuẩn hóa dấu gạch
            return number
        return ""

    def _extract_date(self, content: str) -> str:
        """Trích xuất ngày ban hành."""
        for pattern in self.DATE_PATTERNS:
            match = pattern.search(content)
            if match:
                day, month, year = match.groups()
                try:
                    # Validate date
                    date = datetime(int(year), int(month), int(day))
                    return date.strftime("%d/%m/%Y")
                except ValueError:
                    continue
        return ""

    def _extract_issuer(self, content: str) -> str:
        """Trích xuất đơn vị ban hành."""
        # Pattern cho các đơn vị phổ biến
        issuer_patterns = [
            r"(GIÁM ĐỐC|HIỆU TRƯỞNG)\s+(ĐẠI HỌC|TRƯỜNG)[^\n]+",
            r"(ĐẠI HỌC|TRƯỜNG ĐẠI HỌC)\s+[^\n]+",
        ]

        for pattern in issuer_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                issuer = match.group(0).strip()
                # Chuẩn hóa
                if "BÁCH KHOA HÀ NỘI" in issuer.upper():
                    return "Đại học Bách khoa Hà Nội"

        return ""

    def _extract_title(self, content: str) -> str:
        """Trích xuất tiêu đề văn bản."""
        # Tìm sau "QUYẾT ĐỊNH" hoặc tương tự
        patterns = [
            r"QUYẾT ĐỊNH\s*\n+(.+?)(?:\n\n|GIÁM ĐỐC|HIỆU TRƯỞNG)",
            r"Về việc\s+(.+?)(?:\n\n|GIÁM ĐỐC|HIỆU TRƯỞNG)",
            r"Ban hành\s+(.+?)(?:\n\n|GIÁM ĐỐC|HIỆU TRƯỞNG)",
        ]

        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
            if match:
                title = match.group(1).strip()
                # Xóa newlines và normalize
                title = re.sub(r"\s+", " ", title)
                return title[:200]  # Giới hạn độ dài

        return ""

    def _extract_keywords(self, content: str) -> List[str]:
        """Trích xuất từ khóa từ nội dung."""
        keywords = set()

        # Các từ khóa phổ biến trong văn bản giáo dục
        keyword_patterns = [
            r"học bổng",
            r"sinh viên",
            r"học phí",
            r"đào tạo",
            r"tốt nghiệp",
            r"điểm rèn luyện",
            r"ngoại ngữ",
            r"tín chỉ",
            r"khuyết tật",
            r"chính sách",
            r"quy chế",
            r"quy định",
        ]

        for pattern in keyword_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                keywords.add(pattern)

        return list(keywords)

    def extract_all_metadata(self, content: str) -> DocumentMetadata:
        """
        Trích xuất toàn bộ metadata từ văn bản.

        Args:
            content: Nội dung văn bản

        Returns:
            DocumentMetadata object
        """
        metadata = DocumentMetadata()

        # Chỉ xử lý phần đầu văn bản (2000 ký tự đầu)
        header_content = content[:2000]

        metadata.document_type = self._extract_document_type(header_content)
        metadata.document_number = self._extract_document_number(header_content)
        metadata.issue_date = self._extract_date(header_content)
        metadata.issuer = self._extract_issuer(header_content)
        metadata.title = self._extract_title(header_content)
        metadata.keywords = self._extract_keywords(content)

        return metadata

    def _has_frontmatter(self, content: str) -> bool:
        """Kiểm tra xem nội dung đã có frontmatter chưa."""
        return content.strip().startswith("---")

    def clean(self, content: str) -> CleaningResult:
        """
        Trích xuất metadata và thêm frontmatter.

        Args:
            content: Nội dung markdown

        Returns:
            CleaningResult với metadata được thêm vào
        """
        result = CleaningResult(content=content)

        if not self.extract_metadata:
            return result

        # Kiểm tra nếu đã có frontmatter
        if self._has_frontmatter(content):
            result.add_detail("Đã có frontmatter, bỏ qua")
            return result

        # Trích xuất metadata
        metadata = self.extract_all_metadata(content)

        # Log metadata được trích xuất
        if metadata.document_type:
            result.add_detail(f"Loại văn bản: {metadata.document_type}")
        if metadata.document_number:
            result.add_detail(f"Số văn bản: {metadata.document_number}")
        if metadata.issue_date:
            result.add_detail(f"Ngày ban hành: {metadata.issue_date}")

        # Thêm frontmatter nếu được yêu cầu
        if self.add_frontmatter:
            frontmatter = metadata.to_markdown_header()
            content = frontmatter + content
            result.add_detail("Đã thêm YAML frontmatter")
            result.changes_made = 1

        result.content = content
        result.success = True

        # Lưu metadata vào result để có thể sử dụng sau
        result.details.append(f"metadata: {metadata.to_dict()}")

        return result
