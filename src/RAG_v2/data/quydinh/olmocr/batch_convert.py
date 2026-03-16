#!/usr/bin/env python3
"""
Batch convert all markdown files from quydinh to converted folder.
Process all .md files, converting HTML tables if present.
"""

import os
import sys
from pathlib import Path
import re

# Import the conversion function from the existing script
from convert_html_to_markdown_tables import convert_html_tables_in_file


def main():
    # Define paths
    input_dir = Path(r"D:\GR\src\RAG_v2\data\quydinh\olmocr\quydinh")
    output_dir = Path(r"D:\GR\src\RAG_v2\data\quydinh\olmocr\converted")

    # Get all markdown files in the quydinh folder
    all_md_files = sorted(input_dir.glob("*.md"))

    if not all_md_files:
        print(f"No markdown files found in {input_dir}")
        return

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    print(
        f"Processing {len(all_md_files)} markdown files from {input_dir} to {output_dir}\n"
    )

    success_count = 0
    failed_files = []
    files_with_tables = 0
    files_without_tables = 0

    for input_file in all_md_files:
        filename = input_file.name

        # Create output filename by adding _converted suffix before extension
        base_name = input_file.stem
        output_file = output_dir / f"{base_name}_converted.md"

        print(f"Processing: {filename}")

        try:
            # Check if file contains HTML tables
            with open(input_file, "r", encoding="utf-8") as f:
                content = f.read()
                has_tables = bool(re.search(r"<table>", content, re.IGNORECASE))

            if has_tables:
                print(f"  📊 Found HTML tables - converting...")
                files_with_tables += 1
            else:
                print(f"  📄 No HTML tables - copying as-is...")
                files_without_tables += 1

            # Convert the file (will handle both cases - with or without tables)
            convert_html_tables_in_file(str(input_file), str(output_file))
            success_count += 1
            print(f"  ✅ Saved to: {output_file.name}\n")

        except Exception as e:
            print(f"  ❌ Error: {str(e)}\n")
            failed_files.append(filename)

    # Summary
    print("\n" + "=" * 60)
    print(f"Conversion Summary:")
    print(f"  Total files processed: {len(all_md_files)}")
    print(f"  Successfully converted: {success_count}")
    print(f"  Files with HTML tables: {files_with_tables}")
    print(f"  Files without HTML tables: {files_without_tables}")
    print(f"  Failed: {len(failed_files)}")

    if failed_files:
        print(f"\nFailed files:")
        for f in failed_files:
            print(f"  - {f}")

    print("=" * 60)


if __name__ == "__main__":
    main()
