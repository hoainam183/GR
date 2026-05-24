"""Metadata Audit Script — report coverage and completeness of document metadata.

Scans all data/ JSON files across collections and reports:
  - Which metadata fields exist per collection
  - Fill rate (percentage of documents with each field populated)
  - Common missing fields that could improve retrieval if enriched
  - Suggestions for metadata enrichment

Usage from ``src/RAG_v2``::

    python scripts/metadata_audit.py
    python scripts/metadata_audit.py --output scripts/metadata_audit_report.json
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Set

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

# Fields that are important for retrieval quality
IMPORTANT_FIELDS = {
    "DocumentID", "Title", "TypeDoc", "Description",
    "TimeCreate", "Status", "major_code", "applicable_cohort",
    "applicable_major", "date_str", "source_url", "faculty",
}


def scan_collection(collection_dir: Path) -> Dict[str, Any]:
    """Scan a single collection folder and return metadata stats."""
    json_files = list(collection_dir.glob("*.json"))
    if not json_files:
        return {"name": collection_dir.name, "doc_count": 0, "fields": {}}

    all_fields: Set[str] = set()
    field_counts: Counter = Counter()
    field_empty_counts: Counter = Counter()
    total_docs = 0

    for jf in json_files:
        try:
            with open(jf, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue

        # Handle both list and single-doc formats
        docs = data if isinstance(data, list) else [data]

        for doc in docs:
            if not isinstance(doc, dict):
                continue
            total_docs += 1
            for key, value in doc.items():
                all_fields.add(key)
                field_counts[key] += 1
                # Check if field is effectively empty
                if value is None or value == "" or value == [] or value == {}:
                    field_empty_counts[key] += 1

    # Calculate fill rates
    field_stats = {}
    for field_name in sorted(all_fields):
        present = field_counts[field_name]
        empty = field_empty_counts[field_name]
        filled = present - empty
        fill_rate = (filled / total_docs * 100) if total_docs > 0 else 0
        field_stats[field_name] = {
            "present_count": present,
            "filled_count": filled,
            "empty_count": empty,
            "fill_rate_pct": round(fill_rate, 1),
        }

    return {
        "name": collection_dir.name,
        "doc_count": total_docs,
        "file_count": len(json_files),
        "fields": field_stats,
    }


def generate_suggestions(collection_stats: List[Dict[str, Any]]) -> List[str]:
    """Generate improvement suggestions based on audit results."""
    suggestions = []

    for coll in collection_stats:
        name = coll["name"]
        fields = coll.get("fields", {})
        doc_count = coll.get("doc_count", 0)
        if doc_count == 0:
            continue

        # Check important fields
        for imp_field in IMPORTANT_FIELDS:
            if imp_field not in fields:
                suggestions.append(
                    f"[{name}] Missing field '{imp_field}' entirely "
                    f"— consider adding it for better retrieval filtering."
                )
            elif fields[imp_field]["fill_rate_pct"] < 50:
                rate = fields[imp_field]["fill_rate_pct"]
                suggestions.append(
                    f"[{name}] Field '{imp_field}' has low fill rate ({rate}%) "
                    f"— enrichment needed for reliable metadata filtering."
                )

    return suggestions


def run_audit(output_path: Path | None = None) -> Dict[str, Any]:
    """Run the full metadata audit.

    Returns:
        Audit report as a dictionary.
    """
    if not DATA_DIR.exists():
        print(f"Data directory not found: {DATA_DIR}")
        sys.exit(1)

    collection_dirs = [d for d in DATA_DIR.iterdir() if d.is_dir()]
    print(f"Found {len(collection_dirs)} collection(s) in {DATA_DIR}\n")

    collection_stats = []
    for coll_dir in sorted(collection_dirs):
        stats = scan_collection(coll_dir)
        collection_stats.append(stats)
        print(f"  {stats['name']}: {stats['doc_count']} docs, "
              f"{len(stats['fields'])} unique fields")

    suggestions = generate_suggestions(collection_stats)

    report = {
        "data_directory": str(DATA_DIR),
        "total_collections": len(collection_stats),
        "collections": collection_stats,
        "suggestions": suggestions,
    }

    # Print summary
    print(f"\n{'='*60}")
    print("METADATA AUDIT SUMMARY")
    print(f"{'='*60}")
    for coll in collection_stats:
        print(f"\n[{coll['name']}] — {coll['doc_count']} documents")
        fields = coll.get("fields", {})
        if not fields:
            print("  (no fields found)")
            continue
        # Show important fields first
        for fname in sorted(fields.keys()):
            finfo = fields[fname]
            indicator = "✓" if finfo["fill_rate_pct"] >= 80 else "△" if finfo["fill_rate_pct"] >= 50 else "✗"
            important_tag = " [IMPORTANT]" if fname in IMPORTANT_FIELDS else ""
            print(f"  {indicator} {fname}: {finfo['fill_rate_pct']}% filled "
                  f"({finfo['filled_count']}/{coll['doc_count']}){important_tag}")

    if suggestions:
        print(f"\n{'─'*60}")
        print(f"SUGGESTIONS ({len(suggestions)}):")
        print(f"{'─'*60}")
        for i, s in enumerate(suggestions, 1):
            print(f"  {i}. {s}")

    # Save report
    if output_path is None:
        output_path = PROJECT_ROOT / "scripts" / "metadata_audit_report.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\nFull report saved to: {output_path}")

    return report


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Metadata audit for retrieval data")
    parser.add_argument("--output", type=str, default=None, help="Output JSON path")
    args = parser.parse_args()

    output = Path(args.output) if args.output else None
    run_audit(output_path=output)


if __name__ == "__main__":
    main()
