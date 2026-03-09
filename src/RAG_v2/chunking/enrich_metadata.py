"""
Metadata Enrichment for CTDT Chunks
====================================
Thêm các trường metadata cấu trúc hóa vào chunk JSON đã tồn tại:
  - effective_date: Ngày ban hành / hiệu lực
  - expiry_date: Ngày hết hiệu lực (thường trống)
  - applicable_cohort: Khóa áp dụng (K65, K66, K67, K68, K69, K70, ...)
  - applicable_major: Ngành đào tạo
  - document_type: Loại CTĐT (curriculum, training_framework, talent_program, ...)

Trích xuất từ:
  1. Nội dung file markdown gốc (clean_data)
  2. Tên file
  3. Nội dung chunk đầu tiên (header info)
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ============================================================
# DOCUMENT TYPE CLASSIFICATION
# ============================================================

# Rules applied to FILENAME + first H1/H2 headings only (not entire text body)
DOCUMENT_TYPE_RULES = [
    # (pattern, document_type)
    (r"tài\s*năng|tai\s*nang|talent|_TN_", "talent_program"),
    (
        r"tiên\s*tiến|tien\s*tien|ct[_\s]*tien[_\s]*tien|CTTT",
        "advanced_program",
    ),
    (r"chất\s*lượng\s*cao|chat\s*luong\s*cao|KSCLC", "high_quality_program"),
    (r"việt[\s-]*pháp|viet[\s-]*phap|ITEP", "international_program"),
    (r"việt[\s-]*nhật|viet[\s-]*nhat|HEDSPI", "international_program"),
    (r"LUH|Leibniz|Griffith|NUT|Nottingham|ME[-_]GU", "international_program"),
    (
        r"chương\s*trình\s*(?:đào\s*tạo\s*)?(?:quốc\s*tế|hợp\s*tác)",
        "international_program",
    ),
    (
        r"international\s+cooperation|cooperation\s+training",
        "international_program",
    ),
    (r"tích\s*hợp.*(?:cử\s*nhân|thạc\s*sĩ)", "integrated_program"),
    (r"cử\s*nhân[\s-]+thạc\s*sĩ|bachelor[\s-]+master", "integrated_program"),
    (r"cn[_\s]*-?[_\s]*thac[_\s]*sy|cu_nhan.*thac_si", "integrated_program"),
    (r"khung\s*(?:chương\s*trình|CT|CTDT|CTĐT)", "training_framework"),
]

# ============================================================
# MAJOR MAPPING
# ============================================================

FOLDER_TO_FACULTY = {
    "cokhi": "Trường Cơ khí",
    "dien-dientu": "Viện Điện",
    "hoa": "Viện Kỹ thuật Hóa học",
    "soict": "Viện CNTT và Truyền thông",
    "toan": "Viện Toán ứng dụng và Tin học",
    "vatlieu": "Viện Khoa học và Kỹ thuật Vật liệu",
}

# Known program code to major mapping (checked against filename)
# Sort by key length desc is done at match time
PROGRAM_CODE_MAP = {
    "EE-E8": "Kỹ thuật Điều khiển và Tự động hóa",
    "EE-EP": "Kỹ thuật Điều khiển và Tự động hóa",
    "EE1": "Kỹ thuật Điện",
    "EE2": "Kỹ thuật Điện",
    "ME-NUT": "Kỹ thuật Cơ điện tử",
    "ME-GU": "Kỹ thuật Cơ khí",
    "ME-LUH": "Kỹ thuật Cơ điện tử",
    "MSE3": "Khoa học và Kỹ thuật Vật liệu",
    "MS1": "Kỹ thuật Vật liệu",
    "ITE15": "An toàn Thông tin",
    "ITE10": "Công nghệ Thông tin",
    "ITE6": "Công nghệ Thông tin Việt-Nhật",
    "ITE7": "Công nghệ Thông tin",
    "ITEP": "Công nghệ Thông tin Việt-Pháp",
    "IT2": "Kỹ thuật Máy tính",
    "MI2": "Toán Tin",
    "BSCS": "Khoa học Máy tính",
    "KHMT": "Khoa học Máy tính",
}

# Keyword patterns in filename → major (for files without structured metadata)
_FILENAME_MAJOR_PATTERNS = [
    (
        r"CDT|CĐT|co[_\s-]?dien[_\s-]?tu|cơ[_\s-]?điện[_\s-]?tử",
        "Kỹ thuật Cơ điện tử",
    ),
    (r"QLTNMT", "Quản lý Tài nguyên và Môi trường"),
    (
        r"KTVDT.*CNNN|vi[_\s-]?dien[_\s-]?tu.*nano",
        "Kỹ thuật Vi điện tử và Công nghệ Nano",
    ),
    (
        r"polyme.*compozit|compozit.*polyme",
        "Công nghệ Vật liệu Polyme và Compozit",
    ),
    (r"KH[_-]?KTVL|KH.*KT.*vật.*liệu", "Khoa học và Kỹ thuật Vật liệu"),
    (r"mse[_-]?k\d{2}", "Kỹ thuật Vật liệu"),
    (r"toantin|toán[_\s-]?tin", "Toán Tin"),
    (r"Hang[_\s-]?khong|hàng[_\s-]?không", "Kỹ thuật Hàng không"),
    (
        r"Ky[_\s-]?thuat[_\s-]?Nhiet|kỹ[_\s-]?thuật[_\s-]?nhiệt",
        "Kỹ thuật Nhiệt",
    ),
]

# Generic H1/H2 headings that are NOT major names
_GENERIC_HEADING_PATTERNS = [
    r"^TRƯỜNG\b",
    r"^VIỆN\b",
    r"^CHƯƠNG\s+TRÌNH",
    r"^KHUNG\b",
    r"^THÔNG\s+TIN\s+TỔNG\s+QUAN",
    r"^DANH\s+MỤC",
    r"^NỘI\s+DUNG",
    r"^\d[\d.]*\.?\s",  # numbered sections: 1. or 3.1. or 3.1
    r"^KHỐI\b",
    r"^LÝ\s+LUẬN",
    r"^BẬC\s+CỬ\s+NHÂN",
    r"^BẬC\s+KỸ\s+SƯ",
    r"^BỘ\s+GIÁO\b",
    r"^KIẾN\s+THỨC",
    r"^Program\s+Content",
    r"^General\s+Program",
    r"^CẤU\s+TRÚC",
    r"^[A-Z]\.\s",  # lettered sections: A. Program Goals, B. ...
]


def _is_generic_heading(heading: str) -> bool:
    """Check if heading is generic (not a major name)."""
    h = heading.strip()
    for p in _GENERIC_HEADING_PATTERNS:
        if re.match(p, h, re.IGNORECASE):
            return True
    return False


def _extract_title_area(text: str) -> str:
    """Extract the title area: filename + H1 + H2 headings (first 500 chars)."""
    lines = []
    for line in text[:1500].split("\n"):
        stripped = line.strip()
        if stripped.startswith("#"):
            lines.append(stripped.lstrip("#").strip())
        elif stripped.startswith("**") and ":" not in stripped:
            lines.append(stripped.strip("* "))
    return " ".join(lines)


def extract_effective_date(text: str, filename: str) -> Optional[str]:
    """
    Trích xuất ngày ban hành / hiệu lực từ nội dung hoặc tên file.

    Thứ tự ưu tiên:
    1. Filename dạng YYYY.MM.DD hoặc YYYY-MM-DD hoặc YYYYMMDD-
    2. "Ban hành tại Quyết định... ngày DD tháng MM năm YYYY" (trong 2000 char đầu)
    3. "ngày DD/MM/YYYY" (trong 2000 char đầu)
    4. Năm trong tiêu đề "CHƯƠNG TRÌNH ... 2017"
    5. Năm trong filename
    """
    # Priority 1: Date in filename - YYYY.MM.DD
    m = re.search(r"(\d{4})\.(\d{2})\.(\d{2})", filename)
    if m:
        year, month, day = m.group(1), m.group(2), m.group(3)
        return f"{day}/{month}/{year}"

    # Priority 1b: Date in filename - YYYY-MM-DD
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", filename)
    if m:
        year, month, day = m.group(1), m.group(2), m.group(3)
        return f"{day}/{month}/{year}"

    # Priority 1c: Date in filename prefix - YYYYMMDD-
    m = re.match(r"(\d{4})(\d{2})(\d{2})-", filename)
    if m:
        year, month, day = m.group(1), m.group(2), m.group(3)
        return f"{day}/{month}/{year}"

    # Priority 2: "ngày DD tháng MM năm YYYY" in first 2000 chars
    header_text = text[:2000]
    m = re.search(
        r"ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})",
        header_text,
        re.IGNORECASE,
    )
    if m:
        day, month, year = m.group(1), m.group(2), m.group(3)
        return f"{day.zfill(2)}/{month.zfill(2)}/{year}"

    # Priority 3: "ngày DD/MM/YYYY" in first 2000 chars
    m = re.search(
        r"ngày\s+(\d{1,2})/(\d{1,2})/(\d{4})", header_text, re.IGNORECASE
    )
    if m:
        day, month, year = m.group(1), m.group(2), m.group(3)
        return f"{day.zfill(2)}/{month.zfill(2)}/{year}"

    # Priority 4: Year in program title "CHƯƠNG TRÌNH ... 2017/2019/2020"
    m = re.search(
        r"(?:chương\s+trình|CHƯƠNG\s+TRÌNH)[^\n]*?(20[12]\d)",
        text[:500],
    )
    if m:
        return m.group(1)

    # Priority 5a: Year in filename like _2020_ or _2023 or -2019-
    m = re.search(r"[_\s-](20[12]\d)(?:[_\s.\-]|$)", filename)
    if m:
        return m.group(1)

    # Priority 5b: Year in H1 title like "KỸ SƯ CHẤT LƯỢNG CAO 2016"
    m = re.search(r"^#\s+[^\n]*?(20[12]\d)", text[:500], re.MULTILINE)
    if m:
        return m.group(1)

    return None


def extract_applicable_cohort(text: str, filename: str) -> Optional[str]:
    """
    Trích xuất khóa áp dụng (K65, K66, ..., K70, ...).

    Tìm trong:
    1. Filename: k65, k68, k69, K70
    2. Content đầu file: "Từ K70", "Áp dụng từ khóa K65", "K66, K67"
    """
    cohorts = set()

    # Search in filename (case insensitive)
    for m in re.finditer(r"(?<![0-9])[Kk](\d{2})(?!\d)", filename):
        num = int(m.group(1))
        if 50 <= num <= 99:
            cohorts.add(f"K{num}")

    # Search in first 3000 chars of content
    # Patterns: "Từ K70", "khóa K65", "K68", etc.
    for m in re.finditer(r"(?<![0-9])[Kk](\d{2})(?!\d)", text[:3000]):
        num = int(m.group(1))
        if 50 <= num <= 99:
            cohorts.add(f"K{num}")

    if cohorts:
        sorted_cohorts = sorted(cohorts, key=lambda x: int(x[1:]))
        return ", ".join(sorted_cohorts)

    return None


def extract_applicable_major(
    text: str, filename: str, folder: str
) -> Optional[str]:
    """
    Trích xuất ngành đào tạo.

    Thứ tự ưu tiên:
    1. Trường "Ngành đào tạo:" (plain text or table)
    2. Trường "Tên chương trình:" (plain text or table)
    3. H1 heading nếu là tên ngành (không phải heading tổng quát)
    4. H2 heading đầu tiên nếu là tên ngành
    5. Program code mapping từ filename
    """
    header = text[:2000]

    # --- Pattern 1: "Ngành đào tạo:" field ---
    # Bold: **Ngành đào tạo:** XXX
    m = re.search(
        r"\*{0,2}Ngành\s+đào\s+tạo:?\*{0,2}\s*(.+?)(?:\s{2,}|\n)",
        header,
        re.IGNORECASE,
    )
    if m:
        major = _clean_field(m.group(1))
        if _is_valid_major(major):
            return major

    # Table: | Ngành đào tạo | XXX |
    m = re.search(
        r"\|\s*Ngành\s+đào\s+tạo\s*\|\s*(.+?)\s*\|",
        header,
        re.IGNORECASE,
    )
    if m:
        major = _clean_field(m.group(1))
        if _is_valid_major(major):
            return major

    # --- Pattern 2: "Tên chương trình:" field ---
    m = re.search(
        r"\*{0,2}Tên\s+chương\s+trình:?\*{0,2}\s*(.+?)(?:\s{2,}|\n)",
        header,
        re.IGNORECASE,
    )
    if m:
        major = _clean_field(m.group(1))
        if _is_valid_major(major):
            return major

    # Table: | Tên chương trình | XXX |
    m = re.search(
        r"\|\s*Tên\s+chương\s+trình\s*\|\s*(.+?)\s*\|",
        header,
        re.IGNORECASE,
    )
    if m:
        major = _clean_field(m.group(1))
        if _is_valid_major(major):
            return major

    # --- Pattern 3: H1 heading ---
    m = re.search(r"^#\s+(.+)$", text[:500], re.MULTILINE)
    if m:
        h1 = m.group(1).strip()
        if not _is_generic_heading(h1) and len(h1) <= 80:
            return h1

    # --- Pattern 4: Program code in filename (before H2, more reliable) ---
    fname_normalized = filename.replace("_", "-")
    for code in sorted(PROGRAM_CODE_MAP, key=len, reverse=True):
        if re.search(
            r"(?<![A-Za-z0-9])" + re.escape(code) + r"(?![A-Za-z0-9])",
            fname_normalized,
            re.IGNORECASE,
        ):
            return PROGRAM_CODE_MAP[code]

    # --- Pattern 5: Keyword pattern in filename (before H2) ---
    for pattern, major in _FILENAME_MAJOR_PATTERNS:
        if re.search(pattern, filename, re.IGNORECASE):
            return major

    # --- Pattern 6: H2 heading (first non-generic one) ---
    for m_h2 in re.finditer(r"^##\s+(.+)$", text[:1500], re.MULTILINE):
        h2 = m_h2.group(1).strip()
        if not _is_generic_heading(h2) and len(h2) <= 80:
            return h2

    # --- Pattern 7: Extract meaningful part from filename ---
    # e.g., "Khung chương trình đào tạo Công nghệ vật liệu polyme và compozit_fix"
    m = re.search(
        r"(?:khung\s+)?(?:chương\s+trình\s+)?(?:đào\s+tạo\s+)(.+?)(?:_fix|$)",
        filename,
        re.IGNORECASE,
    )
    if m:
        candidate = m.group(1).strip(" _-")
        if (
            candidate
            and len(candidate) > 5
            and not _is_generic_heading(candidate)
        ):
            return candidate

    return None


def _clean_field(raw: str) -> str:
    """Clean a raw field value from markdown artifacts."""
    s = raw.strip()
    s = re.sub(r"\*+", "", s)  # remove bold markers
    s = s.strip("|").strip()  # remove table separators
    # Remove trailing parenthetical mã ngành
    s = re.sub(r"\s*\|\s*\*{0,2}Mã\s+ngành.*$", "", s).strip()
    return s


def _is_valid_major(major: str) -> bool:
    """Check if extracted text looks like a valid major name."""
    if not major or len(major) < 3:
        return False
    # Too long = probably a description, not a name
    if len(major) > 80:
        return False
    # Should not be a generic heading
    if _is_generic_heading(major):
        return False
    return True


def classify_document_type(text: str, filename: str) -> str:
    """
    Phân loại loại tài liệu.

    Chỉ phân tích filename + tiêu đề (H1/H2 headings) để tránh false positives.
    """
    title_area = filename + " " + _extract_title_area(text)

    for pattern, doc_type in DOCUMENT_TYPE_RULES:
        if re.search(pattern, title_area, re.IGNORECASE):
            return doc_type

    return "curriculum"


def extract_document_metadata(
    text: str, filename: str, folder: str
) -> Dict[str, Optional[str]]:
    """
    Trích xuất toàn bộ metadata từ nội dung văn bản và tên file.
    """
    return {
        "effective_date": extract_effective_date(text, filename),
        "expiry_date": None,  # thường không có trong CTDT
        "applicable_cohort": extract_applicable_cohort(text, filename),
        "applicable_major": extract_applicable_major(text, filename, folder),
        "document_type": classify_document_type(text, filename),
    }


def enrich_chunks(
    chunks: List[Dict], doc_metadata: Dict[str, Optional[str]]
) -> List[Dict]:
    """
    Thêm metadata cấu trúc hóa vào tất cả chunks.
    """
    for chunk in chunks:
        meta = chunk.get("metadata", {})
        meta["effective_date"] = doc_metadata["effective_date"]
        meta["expiry_date"] = doc_metadata["expiry_date"]
        meta["applicable_cohort"] = doc_metadata["applicable_cohort"]
        meta["applicable_major"] = doc_metadata["applicable_major"]
        meta["document_type"] = doc_metadata["document_type"]
        chunk["metadata"] = meta
    return chunks


def process_single_file(
    clean_data_path: Path, chunks_path: Path, folder_name: str
) -> Tuple[bool, Dict]:
    """
    Xử lý 1 cặp file (clean_data + chunks JSON).

    Returns:
        (success, doc_metadata)
    """
    # Read source markdown
    text = clean_data_path.read_text(encoding="utf-8")

    # Read existing chunks
    with open(chunks_path, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    # Extract metadata
    doc_metadata = extract_document_metadata(
        text, clean_data_path.stem, folder_name
    )

    # Enrich chunks
    chunks = enrich_chunks(chunks, doc_metadata)

    # Save back
    with open(chunks_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)

    return True, doc_metadata


def process_ctdt_directory(ctdt_root: str):
    """
    Xử lý toàn bộ thư mục ctdt.

    Cấu trúc expected:
      ctdt_root/
        <faculty_folder>/
          clean_data/
            <name>_fix.md
          chunks_recursive_parent_child/
            <name>_fix_chunks.json
    """
    ctdt_path = Path(ctdt_root)
    results = []

    print(f"\n{'='*70}")
    print(f"📂 METADATA ENRICHMENT - CTDT")
    print(f"   Root: {ctdt_path}")
    print(f"{'='*70}\n")

    for faculty_dir in sorted(ctdt_path.iterdir()):
        if not faculty_dir.is_dir():
            continue

        folder_name = faculty_dir.name
        clean_dir = faculty_dir / "clean_data"
        chunks_dir = faculty_dir / "chunks_recursive_parent_child"

        if not clean_dir.exists() or not chunks_dir.exists():
            # Check for standalone md files (like toan/MI2.md)
            for md_file in faculty_dir.glob("*.md"):
                print(f"  ⚠️  Standalone file (no chunks): {md_file.name}")
            continue

        print(
            f"\n📁 {folder_name.upper()} ({FOLDER_TO_FACULTY.get(folder_name, '')})"
        )
        print(f"   {'─'*50}")

        for md_file in sorted(clean_dir.glob("*_fix.md")):
            stem = md_file.stem  # e.g., "1.2. Kỹ thuật Cơ khí_fix"
            chunks_file = chunks_dir / f"{stem}_chunks.json"

            if not chunks_file.exists():
                print(f"  ⚠️  No chunks for: {md_file.name}")
                continue

            success, doc_meta = process_single_file(
                md_file, chunks_file, folder_name
            )

            status = "✅" if success else "❌"
            major = doc_meta.get("applicable_major") or "—"
            cohort = doc_meta.get("applicable_cohort") or "—"
            date = doc_meta.get("effective_date") or "—"
            dtype = doc_meta.get("document_type") or "—"

            # Truncate major for display
            major_display = major[:40] + "..." if len(major) > 43 else major

            print(f"  {status} {md_file.stem}")
            print(f"      Ngành: {major_display}")
            print(f"      Khóa: {cohort} | Ngày: {date} | Loại: {dtype}")

            results.append(
                {
                    "file": md_file.name,
                    "folder": folder_name,
                    "chunks_file": chunks_file.name,
                    **doc_meta,
                }
            )

    # Summary
    print(f"\n{'='*70}")
    print(f"📊 SUMMARY")
    print(f"   Total files processed: {len(results)}")
    print(
        f"   With effective_date: {sum(1 for r in results if r['effective_date'])}"
    )
    print(
        f"   With applicable_cohort: {sum(1 for r in results if r['applicable_cohort'])}"
    )
    print(
        f"   With applicable_major: {sum(1 for r in results if r['applicable_major'])}"
    )

    # Document type breakdown
    type_counts = {}
    for r in results:
        dt = r["document_type"]
        type_counts[dt] = type_counts.get(dt, 0) + 1
    print(f"   Document types:")
    for dt, count in sorted(type_counts.items()):
        print(f"     - {dt}: {count}")

    print(f"{'='*70}\n")

    return results


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        ctdt_root = sys.argv[1]
    else:
        ctdt_root = str(Path(__file__).parent.parent / "data" / "ctdt")

    process_ctdt_directory(ctdt_root)
