"""Build the course-name → course-code catalog artifact.

Parses curriculum markdown tables under ``data/ctdt/{program}/clean_data/*.md``
(columns ``TT | Mã số | Tên học phần | Tín chỉ | Kỳ``) and groups courses by
``major_code`` (read from the sibling ``*_chunks.json`` metadata). The result is
written to ``query/models/course_catalog.json`` and loaded at runtime by
``query.course_catalog`` to enrich reflected queries with the right course code
for the user's major.

Usage:
    cd d:\\GR\\src\\RAG_v2
    python -m scripts.build_course_catalog
"""

from __future__ import annotations

import json
import logging
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional

# Repo-root-relative imports (run from src/RAG_v2).
from query.signals import fold_vietnamese_text

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)

# Course code: 2–4 uppercase letters + 3–4 digits + optional trailing letter.
# e.g. IT3080, SSH1110, FL1107, IT4062E.
_COURSE_CODE_RE = re.compile(r"^[A-Z]{2,4}\d{3,4}[A-Z]?$")
# Course-detail section headers like "#### IT3080E Mạng máy tính" — used to
# harvest extra (often Vietnamese) name aliases in bilingual programs whose
# summary table lists only the English name (e.g. IT-E7: "Computer Networks").
_HEADER_COURSE_RE = re.compile(r"^#{2,6}\s+([A-Z]{2,4}\d{3,4}[A-Z]?)\s+(.+?)\s*$")
_MAJOR_CODE_IN_JSON_RE = re.compile(r'"major_code"\s*:\s*"([^"]+)"')
_BARE_INT_RE = re.compile(r"^\d{1,2}$")
_CREDITS_RE = re.compile(r"^(\d+)\s*\(")

# Minimum folded length / word count for a course name to be usable as a
# lookup key (avoids matching tiny generic names against arbitrary text).
_MIN_NAME_FOLDED_LEN = 6

_DATA_ROOT = Path(__file__).resolve().parent.parent / "data" / "ctdt"
_OUTPUT_PATH = Path(__file__).resolve().parent.parent / "query" / "models" / "course_catalog.json"


def _row_cells(line: str) -> List[str]:
    """Split a markdown table row into trimmed cells (drop the edge empties)."""
    if "|" not in line:
        return []
    parts = [c.strip() for c in line.strip().strip("|").split("|")]
    return parts


def _is_separator_row(cells: List[str]) -> bool:
    return bool(cells) and all(set(c) <= {"-", ":", " "} and c for c in cells)


def _parse_course_row(cells: List[str]) -> Optional[Dict[str, Optional[str]]]:
    """Extract (code, name, credits, semester) from a table row, or None."""
    code_idx = next(
        (i for i, c in enumerate(cells) if _COURSE_CODE_RE.match(c.upper())),
        None,
    )
    if code_idx is None or code_idx + 1 >= len(cells):
        return None
    code = cells[code_idx].upper()
    name = cells[code_idx + 1].strip()
    if not name:
        return None

    trailing = cells[code_idx + 2 :]
    credits: Optional[str] = None
    semester: Optional[str] = None
    for cell in trailing:
        m = _CREDITS_RE.match(cell)
        if m and credits is None:
            credits = m.group(1)
            continue
        if _BARE_INT_RE.match(cell):
            value = int(cell)
            if 1 <= value <= 12:
                semester = cell  # last bare int in range wins (the "Kỳ" column)
    return {"code": code, "name": name, "credits": credits, "semester": semester}


def _major_code_for(md_path: Path) -> Optional[str]:
    """Read the dominant major_code from the sibling ``*_chunks.json`` file."""
    chunks_path = (
        md_path.parent.parent
        / "chunks_recursive_parent_child"
        / f"{md_path.stem}_chunks.json"
    )
    if not chunks_path.exists():
        logger.warning("No chunks file for %s (expected %s)", md_path.name, chunks_path.name)
        return None
    text = chunks_path.read_text(encoding="utf-8")
    codes = _MAJOR_CODE_IN_JSON_RE.findall(text)
    if not codes:
        return None
    return Counter(codes).most_common(1)[0][0]


def _add_entry(
    by_key: Dict[tuple, Dict[str, Optional[str]]],
    *,
    code: str,
    name: str,
    credits: Optional[str] = None,
    semester: Optional[str] = None,
) -> bool:
    """Add/merge a (code, name) alias. Returns True when a new key was added."""
    name = name.strip()
    name_folded = fold_vietnamese_text(name)
    if len(name_folded) < _MIN_NAME_FOLDED_LEN:
        return False
    key = (code, name_folded)
    existing = by_key.get(key)
    if existing is None:
        by_key[key] = {
            "code": code,
            "name": name,
            "name_folded": name_folded,
            "credits": credits,
            "semester": semester,
        }
        return True
    # Merge: fill missing semester/credits from whichever source has it.
    if not existing.get("semester") and semester:
        existing["semester"] = semester
    if not existing.get("credits") and credits:
        existing["credits"] = credits
    return False


def build_catalog() -> Dict[str, List[Dict[str, Optional[str]]]]:
    catalog: Dict[str, Dict[tuple, Dict[str, Optional[str]]]] = {}
    md_files = sorted(_DATA_ROOT.glob("*/clean_data/*.md"))
    logger.info("Found %d curriculum markdown files under %s", len(md_files), _DATA_ROOT)

    for md_path in md_files:
        major_code = _major_code_for(md_path)
        if not major_code:
            logger.warning("Skipping %s — no major_code resolved", md_path.name)
            continue
        by_key = catalog.setdefault(major_code, {})
        added = 0
        for line in md_path.read_text(encoding="utf-8").splitlines():
            # Source 1: course-detail section headers (alias names, no semester).
            header = _HEADER_COURSE_RE.match(line)
            if header:
                if _add_entry(by_key, code=header.group(1).upper(), name=header.group(2)):
                    added += 1
                continue
            # Source 2: summary table rows.
            cells = _row_cells(line)
            if len(cells) < 2 or _is_separator_row(cells):
                continue
            parsed = _parse_course_row(cells)
            if not parsed:
                continue
            if _add_entry(
                by_key,
                code=parsed["code"],
                name=parsed["name"],
                credits=parsed["credits"],
                semester=parsed["semester"],
            ):
                added += 1
        logger.info("  %-12s (%s): %d course-name aliases", major_code, md_path.name, added)

    # Flatten to {major_code: [entries]} with longest name first so the runtime
    # longest-match is cheap and deterministic.
    out: Dict[str, List[Dict[str, Optional[str]]]] = {}
    for major_code, by_key in catalog.items():
        entries = sorted(
            by_key.values(),
            key=lambda e: len(e["name_folded"]),
            reverse=True,
        )
        out[major_code] = entries
    return out


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    catalog = build_catalog()
    _OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _OUTPUT_PATH.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    total = sum(len(v) for v in catalog.values())
    logger.info("=" * 60)
    logger.info("Wrote %d majors, %d courses → %s", len(catalog), total, _OUTPUT_PATH)

    # Quick sanity probe for the canonical example.
    for mc in ("IT2", "IT-E6", "IT-E7", "IT1"):
        hit = next(
            (e for e in catalog.get(mc, []) if e["name_folded"] == "mang may tinh"),
            None,
        )
        logger.info("  probe %-6s 'mạng máy tính' → %s", mc, hit["code"] if hit else "—")


if __name__ == "__main__":
    main()
