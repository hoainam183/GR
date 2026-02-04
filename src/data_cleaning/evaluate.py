"""
Evaluation Report for Converted Markdown Files
==============================================

Script đánh giá chất lượng các file markdown đã convert từ HTML.
Tạo báo cáo chi tiết về các vấn đề cần làm sạch.
"""

import re
from pathlib import Path
from typing import Dict, List, Any
from dataclasses import dataclass, field
from collections import Counter
import json


@dataclass
class FileAnalysis:
    """Kết quả phân tích một file."""

    filename: str
    file_size: int = 0
    line_count: int = 0
    word_count: int = 0

    # Issues found
    extra_blank_lines: int = 0
    trailing_whitespace_lines: int = 0
    duplicate_lines: int = 0
    malformed_tables: int = 0
    ocr_errors: List[str] = field(default_factory=list)
    header_artifacts: int = 0
    special_chars: List[str] = field(default_factory=list)

    # Quality score (0-100)
    quality_score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "filename": self.filename,
            "file_size": self.file_size,
            "line_count": self.line_count,
            "word_count": self.word_count,
            "issues": {
                "extra_blank_lines": self.extra_blank_lines,
                "trailing_whitespace_lines": self.trailing_whitespace_lines,
                "duplicate_lines": self.duplicate_lines,
                "malformed_tables": self.malformed_tables,
                "ocr_errors": self.ocr_errors,
                "header_artifacts": self.header_artifacts,
                "special_chars": self.special_chars,
            },
            "quality_score": self.quality_score,
        }


class MarkdownEvaluator:
    """Đánh giá chất lượng file markdown."""

    # Known OCR errors
    OCR_ERROR_PATTERNS = {
        "ĐHIBK": "ĐHBK",
        "cổ văn": "cố vấn",
        "Mình chừng": "Minh chứng",
        "sachsHT": "sách HT",
    }

    # Header patterns that shouldn't repeat
    HEADER_PATTERNS = [
        r"BỘ GIÁO DỤC VÀ ĐÀO TẠO",
        r"ĐẠI HỌC BÁCH KHOA HÀ NỘI",
        r"CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM",
        r"Độc lập - Tự do - Hạnh phúc",
    ]

    def __init__(self, input_dir: Path):
        self.input_dir = Path(input_dir)
        self.results: List[FileAnalysis] = []

    def analyze_file(self, filepath: Path) -> FileAnalysis:
        """Phân tích một file markdown."""
        analysis = FileAnalysis(filename=filepath.name)

        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        lines = content.split("\n")
        analysis.file_size = len(content)
        analysis.line_count = len(lines)
        analysis.word_count = len(content.split())

        # Check extra blank lines
        blank_count = 0
        for i in range(len(lines) - 2):
            if (
                not lines[i].strip()
                and not lines[i + 1].strip()
                and not lines[i + 2].strip()
            ):
                blank_count += 1
        analysis.extra_blank_lines = blank_count

        # Check trailing whitespace
        analysis.trailing_whitespace_lines = sum(
            1 for line in lines if line != line.rstrip()
        )

        # Check duplicate lines
        prev_line = ""
        dup_count = 0
        for line in lines:
            if line.strip() and line.strip() == prev_line.strip():
                dup_count += 1
            prev_line = line
        analysis.duplicate_lines = dup_count

        # Check malformed tables
        table_issues = 0
        in_table = False
        for line in lines:
            if "|" in line:
                if not in_table:
                    in_table = True
                # Check if columns are misaligned
                cells = line.split("|")
                if len(cells) < 3:  # Likely malformed
                    table_issues += 1
            else:
                in_table = False
        analysis.malformed_tables = table_issues

        # Check OCR errors
        for wrong, correct in self.OCR_ERROR_PATTERNS.items():
            if wrong in content:
                analysis.ocr_errors.append(f"'{wrong}' -> '{correct}'")

        # Check header artifacts
        for pattern in self.HEADER_PATTERNS:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if len(matches) > 1:
                analysis.header_artifacts += len(matches) - 1

        # Check special characters
        special_chars = set()
        for char in content:
            if (
                ord(char) > 127
                and char
                not in "àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴĐ"
            ):
                if char not in " \n\t\r":
                    special_chars.add(f"U+{ord(char):04X}: {char}")
        analysis.special_chars = list(special_chars)[:10]  # Limit to 10

        # Calculate quality score
        total_issues = (
            analysis.extra_blank_lines * 0.5
            + analysis.trailing_whitespace_lines * 0.1
            + analysis.duplicate_lines * 2
            + analysis.malformed_tables * 3
            + len(analysis.ocr_errors) * 5
            + analysis.header_artifacts * 1
            + len(analysis.special_chars) * 0.5
        )
        # Score from 0-100 (fewer issues = higher score)
        analysis.quality_score = max(0, 100 - total_issues)

        return analysis

    def analyze_all(self) -> List[FileAnalysis]:
        """Phân tích tất cả files trong thư mục."""
        files = list(self.input_dir.glob("*.md"))
        print(f"Found {len(files)} markdown files to analyze")

        self.results = []
        for filepath in files:
            print(f"Analyzing: {filepath.name}")
            analysis = self.analyze_file(filepath)
            self.results.append(analysis)

        return self.results

    def generate_report(self) -> str:
        """Tạo báo cáo đánh giá."""
        if not self.results:
            self.analyze_all()

        report = []
        report.append("=" * 70)
        report.append("BÁO CÁO ĐÁNH GIÁ CHẤT LƯỢNG MARKDOWN FILES")
        report.append("=" * 70)
        report.append(f"\nTổng số files: {len(self.results)}")
        report.append(f"Thư mục: {self.input_dir}")
        report.append("")

        # Summary statistics
        total_issues = {
            "extra_blank_lines": 0,
            "trailing_whitespace": 0,
            "duplicate_lines": 0,
            "malformed_tables": 0,
            "ocr_errors": 0,
            "header_artifacts": 0,
        }

        for r in self.results:
            total_issues["extra_blank_lines"] += r.extra_blank_lines
            total_issues["trailing_whitespace"] += r.trailing_whitespace_lines
            total_issues["duplicate_lines"] += r.duplicate_lines
            total_issues["malformed_tables"] += r.malformed_tables
            total_issues["ocr_errors"] += len(r.ocr_errors)
            total_issues["header_artifacts"] += r.header_artifacts

        report.append("TỔNG HỢP VẤN ĐỀ CẦN XỬ LÝ:")
        report.append("-" * 40)
        report.append(
            f"  • Dòng trống thừa: {total_issues['extra_blank_lines']}"
        )
        report.append(
            f"  • Trailing whitespace: {total_issues['trailing_whitespace']}"
        )
        report.append(f"  • Dòng duplicate: {total_issues['duplicate_lines']}")
        report.append(
            f"  • Bảng bị lỗi format: {total_issues['malformed_tables']}"
        )
        report.append(f"  • Lỗi OCR: {total_issues['ocr_errors']}")
        report.append(
            f"  • Header artifacts: {total_issues['header_artifacts']}"
        )
        report.append("")

        # Average quality score
        avg_score = sum(r.quality_score for r in self.results) / len(
            self.results
        )
        report.append(f"ĐIỂM CHẤT LƯỢNG TRUNG BÌNH: {avg_score:.1f}/100")
        report.append("")

        # Detail per file
        report.append("CHI TIẾT TỪNG FILE:")
        report.append("-" * 70)

        # Sort by quality score (lowest first = needs most work)
        sorted_results = sorted(self.results, key=lambda x: x.quality_score)

        for r in sorted_results:
            report.append(f"\n📄 {r.filename}")
            report.append(
                f"   Size: {r.file_size:,} bytes | Lines: {r.line_count} | Words: {r.word_count}"
            )
            report.append(f"   Quality Score: {r.quality_score:.1f}/100")

            issues = []
            if r.extra_blank_lines:
                issues.append(f"Dòng trống thừa: {r.extra_blank_lines}")
            if r.trailing_whitespace_lines:
                issues.append(
                    f"Trailing whitespace: {r.trailing_whitespace_lines}"
                )
            if r.duplicate_lines:
                issues.append(f"Duplicate lines: {r.duplicate_lines}")
            if r.malformed_tables:
                issues.append(f"Malformed tables: {r.malformed_tables}")
            if r.ocr_errors:
                issues.append(f"OCR errors: {', '.join(r.ocr_errors[:3])}")
            if r.header_artifacts:
                issues.append(f"Header artifacts: {r.header_artifacts}")

            if issues:
                report.append("   Issues:")
                for issue in issues:
                    report.append(f"     - {issue}")
            else:
                report.append("   ✓ No major issues found")

        report.append("")
        report.append("=" * 70)
        report.append("KẾT LUẬN VÀ KHUYẾN NGHỊ:")
        report.append("-" * 70)

        if avg_score >= 80:
            report.append(
                "✓ Chất lượng tổng thể TỐT. Cần một số điều chỉnh nhỏ."
            )
        elif avg_score >= 60:
            report.append(
                "⚠ Chất lượng TRUNG BÌNH. Cần làm sạch dữ liệu trước khi chunking."
            )
        else:
            report.append("✗ Chất lượng THẤP. CẦN LÀM SẠCH DỮ LIỆU NGAY.")

        report.append("")
        report.append("Các bước tiếp theo:")
        report.append(
            "1. Chạy script làm sạch: python -m src.data_cleaning.main --input olmocr/converted"
        )
        report.append("2. Kiểm tra lại chất lượng sau khi làm sạch")
        report.append("3. Tiến hành chunking cho RAG")

        return "\n".join(report)

    def export_json(self, output_path: Path) -> None:
        """Export kết quả ra JSON."""
        if not self.results:
            self.analyze_all()

        data = {
            "summary": {
                "total_files": len(self.results),
                "avg_quality_score": sum(r.quality_score for r in self.results)
                / len(self.results),
            },
            "files": [r.to_dict() for r in self.results],
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


def main():
    """Main function."""
    import sys

    # Default input directory
    input_dir = Path("olmocr/converted")

    # Override from command line if provided
    if len(sys.argv) > 1:
        input_dir = Path(sys.argv[1])

    if not input_dir.exists():
        print(f"Error: Directory not found: {input_dir}")
        return 1

    evaluator = MarkdownEvaluator(input_dir)
    evaluator.analyze_all()

    # Print report
    report = evaluator.generate_report()
    print(report)

    # Export JSON
    json_output = input_dir.parent / "evaluation_report.json"
    evaluator.export_json(json_output)
    print(f"\nJSON report saved to: {json_output}")

    return 0


if __name__ == "__main__":
    exit(main())
