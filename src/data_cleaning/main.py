#!/usr/bin/env python
"""
Main Entry Point for Data Cleaning
==================================

Script chính để chạy quá trình làm sạch dữ liệu markdown.

Usage:
    python -m src.data_cleaning.main --input olmocr/converted --output olmocr/cleaned
    python -m src.data_cleaning.main --file olmocr/converted/sample.md
    python -m src.data_cleaning.main --config config.json
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime

from .pipeline import CleaningPipeline
from .config import CleaningConfig


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Làm sạch dữ liệu markdown cho RAG system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Xử lý một thư mục
    python -m src.data_cleaning.main --input olmocr/converted --output olmocr/cleaned
    
    # Xử lý một file
    python -m src.data_cleaning.main --file olmocr/converted/sample.md --output output.md
    
    # Sử dụng config file
    python -m src.data_cleaning.main --config cleaning_config.json
    
    # Verbose mode
    python -m src.data_cleaning.main --input olmocr/converted --verbose
        """,
    )

    # Input/Output
    parser.add_argument(
        "--input", "-i", type=str, help="Thư mục chứa files markdown cần xử lý"
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        help="Thư mục đầu ra (hoặc file nếu dùng --file)",
    )
    parser.add_argument("--file", "-f", type=str, help="Xử lý một file cụ thể")

    # Config
    parser.add_argument(
        "--config", "-c", type=str, help="Đường dẫn file config JSON"
    )
    parser.add_argument(
        "--save-config", type=str, help="Lưu config hiện tại ra file"
    )

    # Options
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Hiển thị chi tiết quá trình xử lý",
    )
    parser.add_argument(
        "--no-backup", action="store_true", help="Không tạo backup files"
    )
    parser.add_argument(
        "--no-metadata",
        action="store_true",
        help="Không thêm metadata frontmatter",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Chỉ preview, không ghi file"
    )

    # Report
    parser.add_argument("--report", type=str, help="Đường dẫn file report JSON")

    return parser.parse_args()


def create_config_from_args(args) -> CleaningConfig:
    """Tạo config từ arguments."""
    # Load từ file nếu có
    if args.config:
        config = CleaningConfig.load(Path(args.config))
    else:
        config = CleaningConfig()

    # Override từ arguments
    if args.input:
        config.input_dir = Path(args.input)
    if args.output:
        config.output_dir = Path(args.output)
    if args.verbose:
        config.verbose = True
    if args.no_backup:
        config.backup_enabled = False
    if args.no_metadata:
        config.add_metadata_header = False

    return config


def main():
    """Main entry point."""
    args = parse_args()

    # Tạo config
    config = create_config_from_args(args)

    # Lưu config nếu được yêu cầu
    if args.save_config:
        config.save(Path(args.save_config))
        print(f"Config saved to: {args.save_config}")
        return 0

    # Tạo pipeline
    pipeline = CleaningPipeline(config)
    pipeline.add_default_cleaners()

    print("=" * 60)
    print("DATA CLEANING PIPELINE")
    print("=" * 60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Config:")
    print(f"  - Input: {config.input_dir}")
    print(f"  - Output: {config.output_dir}")
    print(f"  - Backup: {config.backup_enabled}")
    print(f"  - Metadata: {config.add_metadata_header}")
    print(f"  - Cleaners: {len(pipeline.cleaners)}")
    print("=" * 60)

    # Dry run mode
    if args.dry_run:
        print("\n[DRY RUN MODE - No files will be modified]")

    # Xử lý
    if args.file:
        # Xử lý một file
        input_path = Path(args.file)
        output_path = Path(args.output) if args.output else None

        if args.dry_run:
            with open(input_path, "r", encoding="utf-8") as f:
                content = f.read()
            cleaned, results = pipeline.process_content(content)
            print(f"\nDry run result:")
            print(f"  Original size: {len(content):,} bytes")
            print(f"  Cleaned size: {len(cleaned):,} bytes")
            print(f"  Changes: {sum(r.get('changes', 0) for r in results)}")
        else:
            result = pipeline.process_file(input_path, output_path)
            if result.success:
                print(f"\n✓ File processed successfully: {result.output_file}")
            else:
                print(f"\n✗ Failed: {result.errors}")
                return 1
    else:
        # Xử lý thư mục
        if not config.input_dir.exists():
            print(f"Error: Input directory not found: {config.input_dir}")
            return 1

        results = pipeline.process_directory()

        # Generate report nếu được yêu cầu
        if args.report:
            pipeline.generate_report(results, Path(args.report))

    print("\n" + "=" * 60)
    print("COMPLETED")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
