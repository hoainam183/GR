"""
Cleaning Pipeline Module
========================

Pipeline để chạy tuần tự các bước làm sạch.
Hỗ trợ cấu hình, logging, và error handling.
"""

import logging
from pathlib import Path
from typing import List, Optional, Dict, Any, Type
from dataclasses import dataclass, field
from datetime import datetime
import json
import shutil

from .config import CleaningConfig, DEFAULT_CONFIG
from .cleaners.base import BaseCleaner, CleaningResult
from .cleaners import (
    WhitespaceCleaner,
    TableCleaner,
    HeaderFooterCleaner,
    DuplicateLineCleaner,
    SpecialCharacterCleaner,
    MetadataNormalizer,
)


@dataclass
class PipelineResult:
    """
    Kết quả của toàn bộ pipeline.

    Attributes:
        success: Xử lý thành công hay không
        input_file: File đầu vào
        output_file: File đầu ra
        original_size: Kích thước file gốc
        cleaned_size: Kích thước file sau làm sạch
        total_changes: Tổng số thay đổi
        step_results: Kết quả từng bước
        errors: Các lỗi gặp phải
        processing_time: Thời gian xử lý (seconds)
    """

    success: bool = True
    input_file: str = ""
    output_file: str = ""
    original_size: int = 0
    cleaned_size: int = 0
    total_changes: int = 0
    step_results: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    processing_time: float = 0.0

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "input_file": self.input_file,
            "output_file": self.output_file,
            "original_size": self.original_size,
            "cleaned_size": self.cleaned_size,
            "size_reduction": (
                f"{(1 - self.cleaned_size/self.original_size)*100:.1f}%"
                if self.original_size > 0
                else "0%"
            ),
            "total_changes": self.total_changes,
            "step_results": self.step_results,
            "errors": self.errors,
            "processing_time": f"{self.processing_time:.2f}s",
        }


class CleaningPipeline:
    """
    Pipeline để xử lý tuần tự các bước làm sạch.

    Usage:
        pipeline = CleaningPipeline(config)
        pipeline.add_cleaner(WhitespaceCleaner())
        pipeline.add_cleaner(TableCleaner())
        result = pipeline.process_file(input_path, output_path)
    """

    # Default cleaner order
    DEFAULT_CLEANERS = [
        SpecialCharacterCleaner,  # Xử lý ký tự trước
        WhitespaceCleaner,  # Sau đó xử lý whitespace
        HeaderFooterCleaner,  # Xóa header/footer
        DuplicateLineCleaner,  # Xóa duplicates
        TableCleaner,  # Sửa tables
        MetadataNormalizer,  # Cuối cùng thêm metadata
    ]

    def __init__(self, config: Optional[CleaningConfig] = None):
        """
        Khởi tạo pipeline.

        Args:
            config: CleaningConfig object. Nếu None, sử dụng default config.
        """
        self.config = config or DEFAULT_CONFIG
        self.cleaners: List[BaseCleaner] = []
        self.logger = self._setup_logger()

    def _setup_logger(self) -> logging.Logger:
        """Setup logger cho pipeline."""
        logger = logging.getLogger("CleaningPipeline")
        logger.setLevel(logging.DEBUG if self.config.verbose else logging.INFO)

        # Console handler
        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setLevel(
                logging.DEBUG if self.config.verbose else logging.INFO
            )
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%H:%M:%S",
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        # File handler (nếu được cấu hình)
        if self.config.log_file:
            file_handler = logging.FileHandler(
                self.config.log_file, encoding="utf-8"
            )
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        return logger

    def add_cleaner(self, cleaner: BaseCleaner) -> "CleaningPipeline":
        """
        Thêm một cleaner vào pipeline.

        Args:
            cleaner: Instance của BaseCleaner

        Returns:
            self (để chain)
        """
        self.cleaners.append(cleaner)
        self.logger.debug(f"Added cleaner: {cleaner.name}")
        return self

    def add_default_cleaners(self) -> "CleaningPipeline":
        """
        Thêm tất cả default cleaners với config phù hợp.

        Returns:
            self (để chain)
        """
        cleaner_configs = {
            SpecialCharacterCleaner: {
                "normalize_unicode": self.config.normalize_unicode,
                "fix_ocr_errors": self.config.fix_ocr_errors,
                "ocr_error_mappings": self.config.ocr_error_mappings,
            },
            WhitespaceCleaner: {
                "max_consecutive_blank_lines": self.config.max_consecutive_blank_lines,
                "trim_trailing_whitespace": self.config.trim_trailing_whitespace,
            },
            HeaderFooterCleaner: {
                "remove_page_numbers": self.config.remove_page_numbers,
                "header_patterns": self.config.header_patterns,
            },
            DuplicateLineCleaner: {
                "similarity_threshold": self.config.similarity_threshold,
            },
            TableCleaner: {
                "fix_malformed_tables": self.config.fix_malformed_tables,
                "normalize_separators": self.config.normalize_table_separators,
                "remove_empty_rows": self.config.remove_empty_table_rows,
            },
            MetadataNormalizer: {
                "extract_metadata": self.config.extract_document_info,
                "add_frontmatter": self.config.add_metadata_header,
            },
        }

        for cleaner_class in self.DEFAULT_CLEANERS:
            config = cleaner_configs.get(cleaner_class, {})
            self.add_cleaner(cleaner_class(config))

        return self

    def clear_cleaners(self) -> "CleaningPipeline":
        """
        Xóa tất cả cleaners.

        Returns:
            self (để chain)
        """
        self.cleaners = []
        return self

    def process_content(self, content: str) -> tuple[str, List[Dict[str, Any]]]:
        """
        Xử lý nội dung qua tất cả cleaners.

        Args:
            content: Nội dung cần xử lý

        Returns:
            (cleaned_content, step_results)
        """
        step_results = []
        current_content = content

        for cleaner in self.cleaners:
            self.logger.info(f"Running: {cleaner.name}")

            try:
                result = cleaner(current_content)

                step_result = {
                    "cleaner": cleaner.name,
                    "success": result.success,
                    "changes": result.changes_made,
                    "details": result.details,
                }

                if result.errors:
                    step_result["errors"] = result.errors

                step_results.append(step_result)

                if result.success:
                    current_content = result.content
                    self.logger.info(
                        f"  ✓ {cleaner.name}: {result.changes_made} changes"
                    )
                    for detail in result.details[:3]:  # Log 3 chi tiết đầu
                        self.logger.debug(f"    - {detail}")
                else:
                    self.logger.warning(
                        f"  ✗ {cleaner.name} failed: {result.errors}"
                    )

            except Exception as e:
                self.logger.error(f"  ✗ {cleaner.name} error: {str(e)}")
                step_results.append(
                    {
                        "cleaner": cleaner.name,
                        "success": False,
                        "errors": [str(e)],
                    }
                )

        return current_content, step_results

    def process_file(
        self, input_path: Path, output_path: Optional[Path] = None
    ) -> PipelineResult:
        """
        Xử lý một file markdown.

        Args:
            input_path: Đường dẫn file đầu vào
            output_path: Đường dẫn file đầu ra. Nếu None, tạo tự động.

        Returns:
            PipelineResult
        """
        start_time = datetime.now()
        result = PipelineResult(input_file=str(input_path))

        input_path = Path(input_path)

        # Kiểm tra file tồn tại
        if not input_path.exists():
            result.success = False
            result.errors.append(f"File not found: {input_path}")
            return result

        # Tạo output path nếu chưa có
        if output_path is None:
            output_dir = Path(self.config.output_dir)
            output_path = output_dir / input_path.name

        output_path = Path(output_path)
        result.output_file = str(output_path)

        # Đọc file
        try:
            with open(input_path, "r", encoding="utf-8") as f:
                content = f.read()
            result.original_size = len(content)
        except Exception as e:
            result.success = False
            result.errors.append(f"Error reading file: {str(e)}")
            return result

        self.logger.info(f"Processing: {input_path.name}")
        self.logger.info(f"  Original size: {result.original_size:,} bytes")

        # Xử lý content
        cleaned_content, step_results = self.process_content(content)
        result.step_results = step_results
        result.cleaned_size = len(cleaned_content)
        result.total_changes = sum(
            s.get("changes", 0) for s in step_results if s.get("success", False)
        )

        # Kiểm tra errors
        errors = [error for s in step_results for error in s.get("errors", [])]
        result.errors = errors

        # Tạo backup nếu được yêu cầu
        if self.config.backup_enabled and output_path.exists():
            backup_path = output_path.with_suffix(".md.bak")
            shutil.copy2(output_path, backup_path)
            self.logger.debug(f"  Backup created: {backup_path}")

        # Ghi file output
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(cleaned_content)
        except Exception as e:
            result.success = False
            result.errors.append(f"Error writing file: {str(e)}")
            return result

        # Tính thời gian xử lý
        result.processing_time = (datetime.now() - start_time).total_seconds()

        # Log kết quả
        reduction = (1 - result.cleaned_size / result.original_size) * 100
        self.logger.info(
            f"  Cleaned size: {result.cleaned_size:,} bytes ({reduction:.1f}% reduction)"
        )
        self.logger.info(f"  Total changes: {result.total_changes}")
        self.logger.info(f"  Time: {result.processing_time:.2f}s")

        return result

    def process_directory(
        self,
        input_dir: Optional[Path] = None,
        output_dir: Optional[Path] = None,
        pattern: str = "*.md",
    ) -> List[PipelineResult]:
        """
        Xử lý tất cả file markdown trong một thư mục.

        Args:
            input_dir: Thư mục đầu vào. Nếu None, dùng config.input_dir.
            output_dir: Thư mục đầu ra. Nếu None, dùng config.output_dir.
            pattern: Glob pattern cho files.

        Returns:
            List of PipelineResult
        """
        input_dir = Path(input_dir or self.config.input_dir)
        output_dir = Path(output_dir or self.config.output_dir)

        # Tạo output directory
        output_dir.mkdir(parents=True, exist_ok=True)

        # Tìm files
        files = list(input_dir.glob(pattern))
        self.logger.info(f"Found {len(files)} files in {input_dir}")

        results = []
        for i, file_path in enumerate(files, 1):
            self.logger.info(
                f"\n[{i}/{len(files)}] Processing: {file_path.name}"
            )

            output_path = output_dir / file_path.name
            result = self.process_file(file_path, output_path)
            results.append(result)

        # Summary
        successful = sum(1 for r in results if r.success)
        total_changes = sum(r.total_changes for r in results)
        total_time = sum(r.processing_time for r in results)

        self.logger.info(f"\n{'='*50}")
        self.logger.info(f"SUMMARY")
        self.logger.info(f"{'='*50}")
        self.logger.info(f"Files processed: {len(results)}")
        self.logger.info(f"Successful: {successful}")
        self.logger.info(f"Failed: {len(results) - successful}")
        self.logger.info(f"Total changes: {total_changes}")
        self.logger.info(f"Total time: {total_time:.2f}s")

        return results

    def generate_report(
        self, results: List[PipelineResult], output_path: Optional[Path] = None
    ) -> str:
        """
        Tạo report từ kết quả xử lý.

        Args:
            results: List of PipelineResult
            output_path: Nếu có, lưu report ra file

        Returns:
            Report string
        """
        report_data = {
            "generated_at": datetime.now().isoformat(),
            "total_files": len(results),
            "successful": sum(1 for r in results if r.success),
            "failed": sum(1 for r in results if not r.success),
            "total_changes": sum(r.total_changes for r in results),
            "total_time": sum(r.processing_time for r in results),
            "files": [r.to_dict() for r in results],
        }

        report_json = json.dumps(report_data, indent=2, ensure_ascii=False)

        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(report_json)
            self.logger.info(f"Report saved to: {output_path}")

        return report_json
