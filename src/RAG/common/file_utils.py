"""
File processing utilities for RAG pipeline
Handles file validation, directory scanning, and output checking
"""

from pathlib import Path
from typing import List, Set, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import json


class ProcessingStatus(Enum):
    """Status của file processing"""

    SUCCESS = "success"
    SKIPPED = "skipped"
    FAILED = "failed"
    INVALID = "invalid"


@dataclass
class ProcessingResult:
    """Kết quả xử lý một file"""

    input_path: Path
    output_path: Optional[Path]
    status: ProcessingStatus
    message: str
    details: Optional[Dict] = None


class FileValidator:
    """Validate file extensions và kiểm tra file hợp lệ"""

    def __init__(self, valid_extensions: Set[str]):
        """
        Args:
            valid_extensions: Set of valid file extensions (e.g., {'.pdf', '.docx', '.md'})
        """
        self.valid_extensions = {ext.lower() for ext in valid_extensions}

    def is_valid(self, file_path: Path) -> bool:
        """Kiểm tra file có extension hợp lệ không"""
        return file_path.suffix.lower() in self.valid_extensions

    def is_readable(self, file_path: Path) -> bool:
        """Kiểm tra file có thể đọc được không"""
        try:
            return (
                file_path.exists()
                and file_path.is_file()
                and file_path.stat().st_size > 0
            )
        except Exception:
            return False

    def validate(self, file_path: Path) -> Tuple[bool, str]:
        """
        Validate đầy đủ một file

        Returns:
            (is_valid, message)
        """
        if not self.is_readable(file_path):
            return False, f"File không tồn tại hoặc không thể đọc: {file_path}"

        if not self.is_valid(file_path):
            return (
                False,
                f"Extension không hợp lệ: {file_path.suffix} (hỗ trợ: {self.valid_extensions})",
            )

        return True, "OK"


class DirectoryScanner:
    """Scan directory và tìm files cần xử lý"""

    def __init__(self, file_validator: FileValidator, recursive: bool = True):
        """
        Args:
            file_validator: FileValidator instance
            recursive: Có duyệt đệ quy không
        """
        self.validator = file_validator
        self.recursive = recursive

    def scan(self, directory: Path, pattern: str = "*") -> List[Path]:
        """
        Scan directory và trả về list files hợp lệ

        Args:
            directory: Directory path
            pattern: Glob pattern (e.g., "*.pdf", "*")

        Returns:
            List of valid file paths
        """
        if not directory.exists() or not directory.is_dir():
            raise ValueError(f"Directory không tồn tại: {directory}")

        # Scan files
        if self.recursive:
            files = directory.rglob(pattern)
        else:
            files = directory.glob(pattern)

        # Filter valid files
        valid_files = []
        for file_path in files:
            if file_path.is_file() and self.validator.is_valid(file_path):
                valid_files.append(file_path)

        return sorted(valid_files)

    def scan_with_validation(
        self, directory: Path, pattern: str = "*"
    ) -> Tuple[List[Path], List[Tuple[Path, str]]]:
        """
        Scan với validation chi tiết

        Returns:
            (valid_files, invalid_files_with_reasons)
        """
        if not directory.exists() or not directory.is_dir():
            raise ValueError(f"Directory không tồn tại: {directory}")

        valid_files = []
        invalid_files = []

        # Scan all files
        if self.recursive:
            files = directory.rglob(pattern)
        else:
            files = directory.glob(pattern)

        for file_path in files:
            if not file_path.is_file():
                continue

            is_valid, message = self.validator.validate(file_path)
            if is_valid:
                valid_files.append(file_path)
            else:
                invalid_files.append((file_path, message))

        return sorted(valid_files), invalid_files


class OutputChecker:
    """Kiểm tra output đã tồn tại và hợp lệ chưa"""

    def __init__(
        self,
        output_dir: Path,
        output_suffix: str = "",
        output_extension: str = "",
    ):
        """
        Args:
            output_dir: Output directory
            output_suffix: Suffix to add to output filename (e.g., "_chunks", "_clean")
            output_extension: Output file extension (e.g., ".json", ".md")
        """
        self.output_dir = Path(output_dir)
        self.output_suffix = output_suffix
        self.output_extension = output_extension

    def get_output_path(
        self, input_path: Path, custom_output_name: Optional[str] = None
    ) -> Path:
        """
        Tính toán output path từ input path

        Args:
            input_path: Input file path
            custom_output_name: Custom output name (optional)

        Returns:
            Output file path
        """
        if custom_output_name:
            output_name = custom_output_name
        else:
            # Get base name (remove extension)
            base_name = input_path.stem

            # Remove common suffixes
            for suffix in [".clean", "_final"]:
                if base_name.endswith(suffix):
                    base_name = base_name[: -len(suffix)]

            output_name = f"{base_name}{self.output_suffix}"

        # Add extension if specified
        if self.output_extension:
            output_name = f"{output_name}{self.output_extension}"

        return self.output_dir / output_name

    def exists(self, output_path: Path) -> bool:
        """Kiểm tra output file có tồn tại không"""
        return output_path.exists() and output_path.is_file()

    def is_valid(self, output_path: Path) -> bool:
        """
        Kiểm tra output file có hợp lệ không
        Override method này cho từng loại output cụ thể
        """
        if not self.exists(output_path):
            return False

        # Basic check: file size > 0
        try:
            return output_path.stat().st_size > 0
        except Exception:
            return False

    def should_skip(
        self, input_path: Path, custom_output_name: Optional[str] = None
    ) -> Tuple[bool, Path]:
        """
        Kiểm tra có nên skip file này không (đã xử lý và hợp lệ)

        Returns:
            (should_skip, output_path)
        """
        output_path = self.get_output_path(input_path, custom_output_name)

        if self.exists(output_path) and self.is_valid(output_path):
            return True, output_path

        return False, output_path


class JSONOutputChecker(OutputChecker):
    """Output checker cho JSON files"""

    def is_valid(self, output_path: Path) -> bool:
        """Validate JSON file"""
        if not self.exists(output_path):
            return False

        try:
            with open(output_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Check if data is not empty
            if isinstance(data, list):
                return len(data) > 0
            elif isinstance(data, dict):
                return len(data) > 0

            return True
        except Exception:
            return False


class MarkdownOutputChecker(OutputChecker):
    """Output checker cho Markdown files"""

    def __init__(
        self, output_dir: Path, output_suffix: str = "", min_lines: int = 10
    ):
        """
        Args:
            min_lines: Minimum number of lines for valid markdown
        """
        super().__init__(output_dir, output_suffix, output_extension=".md")
        self.min_lines = min_lines

    def is_valid(self, output_path: Path) -> bool:
        """Validate Markdown file"""
        if not self.exists(output_path):
            return False

        try:
            with open(output_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # Check minimum lines
            return len(lines) >= self.min_lines
        except Exception:
            return False


class MultiFileOutputChecker(OutputChecker):
    """
    Output checker cho trường hợp một input tạo ra nhiều output files
    (e.g., markdown + metadata JSON)
    """

    def __init__(
        self, output_dir: Path, output_patterns: List[Tuple[str, str]]
    ):
        """
        Args:
            output_patterns: List of (suffix, extension) tuples
                           e.g., [("", ".md"), ("_metadata", ".json")]
        """
        super().__init__(output_dir)
        self.output_patterns = output_patterns

    def get_output_paths(self, input_path: Path) -> List[Path]:
        """Get all output paths for an input file"""
        base_name = input_path.stem

        # Remove common suffixes
        for suffix in [".clean", "_final"]:
            if base_name.endswith(suffix):
                base_name = base_name[: -len(suffix)]

        output_paths = []
        for suffix, extension in self.output_patterns:
            output_name = f"{base_name}{suffix}{extension}"
            output_paths.append(self.output_dir / output_name)

        return output_paths

    def should_skip(
        self, input_path: Path, custom_output_name: Optional[str] = None
    ) -> Tuple[bool, List[Path]]:
        """
        Check if all output files exist and are valid

        Returns:
            (should_skip, output_paths)
        """
        output_paths = self.get_output_paths(input_path)

        # Check if all outputs exist and are valid
        all_valid = True
        for output_path in output_paths:
            if not self.exists(output_path) or not self.is_valid(output_path):
                all_valid = False
                break

        return all_valid, output_paths
