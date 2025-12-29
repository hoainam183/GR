"""
Base Processor for RAG Pipeline
Provides common functionality for processing files with skip logic and logging
"""

from pathlib import Path
from typing import List, Optional, Callable, Dict, Any
from abc import ABC, abstractmethod
from datetime import datetime
import traceback

from .file_utils import (
    FileValidator,
    DirectoryScanner,
    OutputChecker,
    ProcessingResult,
    ProcessingStatus,
)


class BaseProcessor(ABC):
    """
    Base class cho tất cả processors trong RAG pipeline

    Provides:
    - File/directory processing với skip logic
    - Logging và progress tracking
    - Error handling
    - Statistics collection
    """

    def __init__(
        self,
        output_dir: Path,
        file_validator: FileValidator,
        output_checker: OutputChecker,
        recursive: bool = True,
        verbose: bool = True,
    ):
        """
        Args:
            output_dir: Output directory
            file_validator: FileValidator instance
            output_checker: OutputChecker instance
            recursive: Duyệt đệ quy khi xử lý directory
            verbose: In chi tiết log
        """
        self.output_dir = Path(output_dir)
        self.file_validator = file_validator
        self.output_checker = output_checker
        self.recursive = recursive
        self.verbose = verbose

        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Directory scanner
        self.scanner = DirectoryScanner(file_validator, recursive)

        # Statistics
        self.stats = {
            "total_files": 0,
            "processed": 0,
            "skipped": 0,
            "failed": 0,
            "invalid": 0,
            "start_time": None,
            "end_time": None,
        }

    @abstractmethod
    def process_file(
        self, input_path: Path, output_path: Path
    ) -> Dict[str, Any]:
        """
        Xử lý một file cụ thể

        Args:
            input_path: Input file path
            output_path: Output file path

        Returns:
            Dict with processing details (e.g., {"chunks": 10, "size": 1024})

        Raises:
            Exception if processing fails
        """
        pass

    def _log(self, message: str, level: str = "INFO"):
        """Internal logging"""
        if self.verbose:
            timestamp = datetime.now().strftime("%H:%M:%S")
            prefix = {
                "INFO": "ℹ️ ",
                "SUCCESS": "✅",
                "WARNING": "⚠️ ",
                "ERROR": "❌",
                "SKIP": "⏭️ ",
            }.get(level, "")
            print(f"[{timestamp}] {prefix} {message}")

    def _print_separator(self, char: str = "=", length: int = 60):
        """Print separator line"""
        if self.verbose:
            print(char * length)

    def _process_single_file(self, input_path: Path) -> ProcessingResult:
        """
        Process một file với skip logic và error handling

        Returns:
            ProcessingResult
        """
        # Validate input file
        is_valid, message = self.file_validator.validate(input_path)
        if not is_valid:
            self._log(f"Invalid file: {input_path.name} - {message}", "WARNING")
            return ProcessingResult(
                input_path=input_path,
                output_path=None,
                status=ProcessingStatus.INVALID,
                message=message,
            )

        # Check if should skip
        should_skip, output_path = self.output_checker.should_skip(input_path)

        if should_skip:
            self._log(
                f"Skipping (already processed): {input_path.name}", "SKIP"
            )
            return ProcessingResult(
                input_path=input_path,
                output_path=output_path,
                status=ProcessingStatus.SKIPPED,
                message="Output already exists and is valid",
            )

        # Process file
        try:
            self._log(f"Processing: {input_path.name}", "INFO")

            details = self.process_file(input_path, output_path)

            self._log(f"Success: {input_path.name}", "SUCCESS")

            return ProcessingResult(
                input_path=input_path,
                output_path=output_path,
                status=ProcessingStatus.SUCCESS,
                message="Processed successfully",
                details=details,
            )

        except Exception as e:
            error_msg = f"Error processing {input_path.name}: {str(e)}"
            self._log(error_msg, "ERROR")

            if self.verbose:
                self._log(traceback.format_exc(), "ERROR")

            return ProcessingResult(
                input_path=input_path,
                output_path=output_path,
                status=ProcessingStatus.FAILED,
                message=error_msg,
                details={"error": str(e), "traceback": traceback.format_exc()},
            )

    def process_single(self, input_path: str | Path) -> ProcessingResult:
        """
        Process một file

        Args:
            input_path: Path to input file

        Returns:
            ProcessingResult
        """
        input_path = Path(input_path)

        self._print_separator()
        self._log(f"PROCESSING SINGLE FILE", "INFO")
        self._print_separator()

        self.stats["start_time"] = datetime.now()
        self.stats["total_files"] = 1

        result = self._process_single_file(input_path)

        # Update stats
        if result.status == ProcessingStatus.SUCCESS:
            self.stats["processed"] += 1
        elif result.status == ProcessingStatus.SKIPPED:
            self.stats["skipped"] += 1
        elif result.status == ProcessingStatus.FAILED:
            self.stats["failed"] += 1
        elif result.status == ProcessingStatus.INVALID:
            self.stats["invalid"] += 1

        self.stats["end_time"] = datetime.now()

        self._print_summary()

        return result

    def process_directory(
        self,
        input_dir: str | Path,
        pattern: str = "*",
        max_files: Optional[int] = None,
    ) -> List[ProcessingResult]:
        """
        Process tất cả files trong directory

        Args:
            input_dir: Input directory path
            pattern: Glob pattern (e.g., "*.pdf", "*")
            max_files: Maximum number of files to process (for testing)

        Returns:
            List of ProcessingResult
        """
        input_dir = Path(input_dir)

        self._print_separator()
        self._log(f"PROCESSING DIRECTORY: {input_dir}", "INFO")
        self._print_separator()

        # Scan directory
        self._log(f"Scanning directory with pattern: {pattern}", "INFO")
        valid_files, invalid_files = self.scanner.scan_with_validation(
            input_dir, pattern
        )

        self._log(f"Found {len(valid_files)} valid files", "INFO")
        if invalid_files:
            self._log(f"Found {len(invalid_files)} invalid files", "WARNING")

        if not valid_files:
            self._log("No valid files to process", "WARNING")
            return []

        # Limit files if specified
        if max_files and len(valid_files) > max_files:
            self._log(f"Limiting to {max_files} files (for testing)", "WARNING")
            valid_files = valid_files[:max_files]

        # Initialize stats
        self.stats["start_time"] = datetime.now()
        self.stats["total_files"] = len(valid_files)

        # Process files
        results = []
        for idx, file_path in enumerate(valid_files, 1):
            self._print_separator("-")
            self._log(f"[{idx}/{len(valid_files)}] {file_path.name}", "INFO")
            self._print_separator("-")

            result = self._process_single_file(file_path)
            results.append(result)

            # Update stats
            if result.status == ProcessingStatus.SUCCESS:
                self.stats["processed"] += 1
            elif result.status == ProcessingStatus.SKIPPED:
                self.stats["skipped"] += 1
            elif result.status == ProcessingStatus.FAILED:
                self.stats["failed"] += 1
            elif result.status == ProcessingStatus.INVALID:
                self.stats["invalid"] += 1

        self.stats["end_time"] = datetime.now()

        self._print_summary()

        return results

    def _print_summary(self):
        """Print processing summary"""
        if not self.verbose:
            return

        self._print_separator()
        self._log("PROCESSING SUMMARY", "INFO")
        self._print_separator()

        print(f"Total files:    {self.stats['total_files']}")
        print(f"✅ Processed:   {self.stats['processed']}")
        print(f"⏭️  Skipped:     {self.stats['skipped']}")
        print(f"❌ Failed:      {self.stats['failed']}")
        print(f"⚠️  Invalid:     {self.stats['invalid']}")

        if self.stats["start_time"] and self.stats["end_time"]:
            duration = self.stats["end_time"] - self.stats["start_time"]
            print(f"\n⏱️  Duration:    {duration.total_seconds():.2f}s")

        self._print_separator()

    def get_statistics(self) -> Dict[str, Any]:
        """Get processing statistics"""
        return self.stats.copy()

    def reset_statistics(self):
        """Reset statistics"""
        self.stats = {
            "total_files": 0,
            "processed": 0,
            "skipped": 0,
            "failed": 0,
            "invalid": 0,
            "start_time": None,
            "end_time": None,
        }


class BatchProcessor(BaseProcessor):
    """
    Extended processor với batch processing capabilities
    Dùng cho các trường hợp cần xử lý nhiều files cùng lúc (e.g., embedding)
    """

    def process_batch(
        self,
        input_paths: List[Path],
        batch_size: int = 10,
    ) -> List[ProcessingResult]:
        """
        Process multiple files in batches

        Args:
            input_paths: List of input file paths
            batch_size: Number of files per batch

        Returns:
            List of ProcessingResult
        """
        self._print_separator()
        self._log(f"BATCH PROCESSING: {len(input_paths)} files", "INFO")
        self._print_separator()

        self.stats["start_time"] = datetime.now()
        self.stats["total_files"] = len(input_paths)

        results = []

        # Process in batches
        for batch_start in range(0, len(input_paths), batch_size):
            batch_end = min(batch_start + batch_size, len(input_paths))
            batch = input_paths[batch_start:batch_end]

            self._log(
                f"Processing batch {batch_start//batch_size + 1}: {len(batch)} files",
                "INFO",
            )

            for idx, file_path in enumerate(batch, batch_start + 1):
                self._print_separator("-")
                self._log(
                    f"[{idx}/{len(input_paths)}] {file_path.name}", "INFO"
                )

                result = self._process_single_file(file_path)
                results.append(result)

                # Update stats
                if result.status == ProcessingStatus.SUCCESS:
                    self.stats["processed"] += 1
                elif result.status == ProcessingStatus.SKIPPED:
                    self.stats["skipped"] += 1
                elif result.status == ProcessingStatus.FAILED:
                    self.stats["failed"] += 1
                elif result.status == ProcessingStatus.INVALID:
                    self.stats["invalid"] += 1

        self.stats["end_time"] = datetime.now()
        self._print_summary()

        return results
