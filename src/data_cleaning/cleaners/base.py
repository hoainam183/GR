"""
Base Cleaner Module
===================

Abstract base class cho tất cả các cleaners.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
import logging


@dataclass
class CleaningResult:
    """
    Kết quả của một bước làm sạch.

    Attributes:
        success: Xử lý thành công hay không
        content: Nội dung sau khi xử lý
        changes_made: Số thay đổi đã thực hiện
        details: Chi tiết các thay đổi
        errors: Các lỗi gặp phải (nếu có)
    """

    success: bool = True
    content: str = ""
    changes_made: int = 0
    details: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def add_detail(self, detail: str) -> None:
        """Thêm chi tiết về thay đổi."""
        self.details.append(detail)

    def add_error(self, error: str) -> None:
        """Thêm thông tin lỗi."""
        self.errors.append(error)
        self.success = False


class BaseCleaner(ABC):
    """
    Abstract base class cho tất cả các cleaners.

    Mỗi cleaner phải implement phương thức clean().
    Có thể override các phương thức khác để tùy chỉnh behavior.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Khởi tạo cleaner với config.

        Args:
            config: Dictionary chứa các tùy chọn cấu hình
        """
        self.config = config or {}
        self.logger = logging.getLogger(self.__class__.__name__)
        self._setup()

    def _setup(self) -> None:
        """
        Hook để setup cleaner sau khi khởi tạo.
        Override trong subclass nếu cần.
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Tên của cleaner để hiển thị trong log."""
        pass

    @property
    def description(self) -> str:
        """Mô tả ngắn về chức năng của cleaner."""
        return "Base cleaner"

    @abstractmethod
    def clean(self, content: str) -> CleaningResult:
        """
        Thực hiện làm sạch nội dung.

        Args:
            content: Nội dung markdown cần làm sạch

        Returns:
            CleaningResult chứa kết quả xử lý
        """
        pass

    def validate_input(self, content: str) -> bool:
        """
        Kiểm tra input có hợp lệ không.

        Args:
            content: Nội dung cần kiểm tra

        Returns:
            True nếu input hợp lệ
        """
        if content is None:
            self.logger.warning("Input is None")
            return False
        if not isinstance(content, str):
            self.logger.warning(f"Input is not string: {type(content)}")
            return False
        return True

    def pre_process(self, content: str) -> str:
        """
        Tiền xử lý trước khi clean.
        Override trong subclass nếu cần.

        Args:
            content: Nội dung gốc

        Returns:
            Nội dung sau tiền xử lý
        """
        return content

    def post_process(self, content: str) -> str:
        """
        Hậu xử lý sau khi clean.
        Override trong subclass nếu cần.

        Args:
            content: Nội dung sau clean

        Returns:
            Nội dung sau hậu xử lý
        """
        return content

    def __call__(self, content: str) -> CleaningResult:
        """
        Cho phép gọi cleaner như một function.

        Args:
            content: Nội dung cần làm sạch

        Returns:
            CleaningResult
        """
        if not self.validate_input(content):
            result = CleaningResult(success=False, content=content)
            result.add_error("Invalid input")
            return result

        try:
            processed = self.pre_process(content)
            result = self.clean(processed)
            if result.success:
                result.content = self.post_process(result.content)
            return result
        except Exception as e:
            self.logger.error(f"Error in {self.name}: {str(e)}")
            result = CleaningResult(success=False, content=content)
            result.add_error(str(e))
            return result

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(config={self.config})"
