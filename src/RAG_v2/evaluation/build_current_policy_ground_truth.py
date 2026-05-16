"""Build and validate current-policy ground truth drafts.

This script is intentionally artifact-first. It creates draft JSON/JSONL files
for review instead of mutating the production golden dataset directly.

Examples from ``src/RAG_v2``::

    python -m evaluation.build_current_policy_ground_truth inventory
    python -m evaluation.build_current_policy_ground_truth generate-cases --target-cases 200
    python -m evaluation.build_current_policy_ground_truth seed-labels --cases evaluation/ground_truth_drafts/current_policy_cases_draft.json
    python -m evaluation.build_current_policy_ground_truth validate --cases evaluation/ground_truth_drafts/current_policy_cases_draft.json --labels evaluation/ground_truth_drafts/search_strategy_labels_seed.jsonl
    python -m evaluation.build_current_policy_ground_truth audit-export --cases eval/golden_dataset.json --labels evaluation/search_strategy_labels.jsonl
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_DRAFT_DIR = PROJECT_ROOT / "evaluation" / "ground_truth_drafts"
DEFAULT_CASES = DEFAULT_DRAFT_DIR / "current_policy_cases_draft.json"
DEFAULT_SEED_LABELS = DEFAULT_DRAFT_DIR / "search_strategy_labels_seed.jsonl"
DEFAULT_AUDIT_CSV = DEFAULT_DRAFT_DIR / "current_policy_audit.csv"
DEFAULT_LINEAGE = PROJECT_ROOT / "data" / "document_lineage.json"


@dataclass
class ChunkRecord:
    doc_id: str
    collection: str
    content: str
    title: str
    source_path: str
    source_file: str = ""
    date_str: str = ""
    chunk_index: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["metadata"] = self.metadata or {}
        return payload


def raw_id(value: Any) -> str:
    text = str(value or "").strip()
    return text.split("/", 1)[-1] if "/" in text else text


def full_id(collection: str, doc_id: Any) -> str:
    rid = raw_id(doc_id)
    return f"{collection}/{rid}" if collection and rid else rid


def strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def compact_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _collection_from_path(path: Path) -> str:
    parts = set(path.parts)
    for collection in ("quydinh", "ctdt", "kehoach", "stsv"):
        if collection in parts:
            return collection
    return ""


def _iter_chunk_files(data_dir: Path) -> Iterable[Path]:
    patterns = [
        "quydinh/chunks/*.json",
        "quydinh/admin_upload/*_chunks.json",
        "ctdt/**/chunks_recursive_parent_child/*_chunks.json",
        "kehoach/chunks/*.json",
        "stsv/chunks/*.json",
    ]
    seen: set[Path] = set()
    for pattern in patterns:
        for path in sorted(data_dir.glob(pattern)):
            if path not in seen:
                seen.add(path)
                yield path


def _load_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _row_id(row: Dict[str, Any]) -> str:
    return str(row.get("id") or row.get("chunk_id") or row.get("readable_id") or "").strip()


def _safe_relative_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _title_from_row(path: Path, row: Dict[str, Any], meta: Dict[str, Any], content: str) -> str:
    major_code = compact_spaces(str(meta.get("major_code") or ""))
    major_name = compact_spaces(str(meta.get("major_name") or ""))
    if major_code or major_name:
        section = compact_spaces(str(meta.get("section_h4") or meta.get("section_h3") or meta.get("section_h2") or ""))
        title = compact_spaces(" ".join(part for part in (major_code, major_name, section) if part))
        return title[:220]

    if "ctdt" in path.parts:
        stem = path.stem.replace("_fix_chunks", "").replace("_chunks", "").replace("_fix", "")
        section = compact_spaces(str(meta.get("section_h4") or meta.get("section_h3") or meta.get("section_h2") or ""))
        if section and section.lower() not in {"1. nội dung chương trình", "nội dung chương trình"}:
            return compact_spaces(f"{stem} - {section}")[:220]
        return compact_spaces(stem)[:220]

    title = (
        meta.get("title")
        or meta.get("doc_title")
        or meta.get("course_name")
        or meta.get("filename")
        or meta.get("source")
        or path.stem
    )
    title = compact_spaces(str(title))
    if title and title != path.stem:
        return title[:220]
    match = re.search(r"^\s*(?:#{1,4}\s*)?[\[\(]*([^\]\)\n]{8,180})", content)
    return compact_spaces(match.group(1) if match else path.stem)[:220]


def load_chunk_inventory(data_dir: Path = DEFAULT_DATA_DIR) -> List[ChunkRecord]:
    records: List[ChunkRecord] = []
    for path in _iter_chunk_files(data_dir):
        collection = _collection_from_path(path)
        if not collection:
            continue
        payload = _load_json(path)
        rows = payload if isinstance(payload, list) else payload.get("chunks", [])
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            content = compact_spaces(str(row.get("content") or row.get("text") or ""))
            doc_id = _row_id(row)
            if not doc_id or len(content) < 120:
                continue
            meta = dict(row.get("metadata") or {})
            title = _title_from_row(path, row, meta, content)
            records.append(
                ChunkRecord(
                    doc_id=full_id(collection, doc_id),
                    collection=collection,
                    content=content,
                    title=title,
                    source_path=_safe_relative_path(path, PROJECT_ROOT),
                    source_file=str(meta.get("source") or meta.get("filename") or path.name),
                    date_str=str(meta.get("date_str") or meta.get("time_create") or ""),
                    chunk_index=int(meta.get("chunk_index") or 0),
                    metadata=meta,
                )
            )
    return records


def _query_class(collection: str, title: str, content: str) -> str:
    haystack = f"{title} {content}".lower()
    title_l = title.lower()
    if collection == "ctdt":
        return "course"
    if any(term in title_l for term in ("biểu mẫu", "thủ tục", "hồ sơ", "giấy", "đơn xin", "xác nhận")):
        return "stsv_form"
    if any(term in title_l for term in ("lịch", "thời gian", "thời hạn", "deadline", "kỳ học")):
        return "schedule"
    if any(term in title_l for term in ("học bổng", "tốt nghiệp", "ngoại ngữ", "quy định", "kỷ luật", "học phí")):
        return "policy"
    if any(term in haystack for term in ("lịch", "thời gian", "thời hạn", "đăng ký", "deadline", "kỳ học")):
        return "schedule"
    if any(term in haystack for term in ("biểu mẫu", "thủ tục", "hồ sơ", "giấy", "đơn xin", "xác nhận")):
        return "stsv_form"
    if any(term in haystack for term in ("học bổng", "tốt nghiệp", "ngoại ngữ", "quy định", "kỷ luật", "học phí")):
        return "policy"
    if collection == "stsv":
        return "stsv_form"
    if any(term in haystack for term in ("tín chỉ", "học phần", "chương trình đào tạo", "ctđt", "môn ")):
        return "course"
    return {
        "quydinh": "policy",
        "kehoach": "schedule",
        "stsv": "stsv_form",
        "ctdt": "course",
    }.get(collection, "general")


def _difficulty(record: ChunkRecord, qclass: str) -> str:
    text = f"{record.title} {record.content}".lower()
    if qclass in {"comparison", "multi_source", "negation"}:
        return "hard"
    if any(term in text for term in ("không áp dụng", "không bao gồm", "trừ ", "so sánh", "khác nhau")):
        return "hard"
    if len(record.content) > 900:
        return "medium"
    return "easy"


def _keywords(title: str) -> List[str]:
    words = [
        word.strip(".,:;()[]{}\"'").lower()
        for word in compact_spaces(title).split()
    ]
    stop = {"và", "của", "cho", "về", "theo", "các", "một", "trong", "tại", "đại", "học"}
    out = []
    for word in words:
        if len(word) >= 4 and word not in stop and word not in out:
            out.append(word)
        if len(out) >= 4:
            break
    return out


def _query_for(record: ChunkRecord, qclass: str) -> str:
    title = record.title.strip(" .:-")
    if qclass == "course":
        return f"{title} có những thông tin chính nào?"
    if qclass == "schedule":
        return f"Thời gian hoặc kế hoạch {title} là gì?"
    if qclass == "stsv_form":
        return f"Hướng dẫn thủ tục {title} như thế nào?"
    if qclass == "policy":
        return f"{title} quy định như thế nào?"
    return f"Thông tin về {title} là gì?"


def _case_id(collection: str, qclass: str, index: int) -> str:
    return f"retrieval_{collection}_{qclass}_{index:04d}"


def _select_stratified(records: List[ChunkRecord], target_cases: int) -> List[ChunkRecord]:
    by_collection: Dict[str, List[ChunkRecord]] = {}
    for record in records:
        by_collection.setdefault(record.collection, []).append(record)
    weights = {"quydinh": 0.30, "ctdt": 0.28, "kehoach": 0.22, "stsv": 0.20}
    selected: List[ChunkRecord] = []
    selected_titles: set[tuple[str, str]] = set()
    for collection, weight in weights.items():
        rows = by_collection.get(collection, [])
        rows = sorted(rows, key=lambda r: (r.title.lower(), r.chunk_index, r.doc_id))
        quota = max(1, round(target_cases * weight))
        for row in rows:
            title_key = (collection, row.title.lower())
            if title_key in selected_titles:
                continue
            selected.append(row)
            selected_titles.add(title_key)
            if sum(1 for item in selected if item.collection == collection) >= quota:
                break
    if len(selected) < target_cases:
        chosen = {row.doc_id for row in selected}
        for row in sorted(records, key=lambda r: (r.collection, r.title.lower(), r.chunk_index)):
            title_key = (row.collection, row.title.lower())
            if row.doc_id not in chosen and title_key not in selected_titles:
                selected.append(row)
                chosen.add(row.doc_id)
                selected_titles.add(title_key)
            if len(selected) >= target_cases:
                break
    return selected[:target_cases]


def build_cases(records: List[ChunkRecord], target_cases: int, include_variants: bool = True) -> Dict[str, Any]:
    selected = _select_stratified(records, target_cases)
    cases: List[Dict[str, Any]] = []
    for index, record in enumerate(selected, start=1):
        qclass = _query_class(record.collection, record.title, record.content)
        query = _query_for(record, qclass)
        case = {
            "id": _case_id(record.collection, qclass, index),
            "category": "retrieval",
            "query": query,
            "expected_collection": record.collection,
            "expected_collections": [record.collection],
            "expected_source_ids": [record.doc_id],
            "expected_keywords": _keywords(record.title),
            "ground_truth_answer": record.content[:700],
            "valid_as_of": record.date_str or datetime.now().date().isoformat(),
            "query_class": qclass,
            "difficulty": _difficulty(record, qclass),
            "description": f"Auto-generated from {record.source_path}",
            "source_path": record.source_path,
            "audit_status": "draft",
        }
        cases.append(case)
        if include_variants and index % 8 == 0:
            variant = dict(case)
            variant["id"] = case["id"].replace("retrieval_", "retrieval_nodiacritic_", 1)
            variant["query"] = strip_accents(query)
            variant["query_class"] = "typo_no_diacritic"
            variant["difficulty"] = "medium"
            variant["description"] = case["description"] + " | no-diacritic query variant"
            cases.append(variant)
    return {
        "_description": "Draft current-policy golden dataset generated from indexed RAG data chunks.",
        "_version": "draft",
        "_generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "_notes": [
            "Do not use as production golden until audit_status is reviewed.",
            "Run search_strategy_benchmark.py to add candidate relevance labels.",
        ],
        "test_cases": cases,
    }


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_cases(path: Path) -> List[Dict[str, Any]]:
    payload = _load_json(path)
    if isinstance(payload, dict):
        return [row for row in payload.get("test_cases", []) if isinstance(row, dict)]
    return [row for row in payload if isinstance(row, dict)] if isinstance(payload, list) else []


def load_labels(path: Optional[Path]) -> Dict[str, Dict[str, Dict[str, Any]]]:
    if path is None or not path.exists():
        return {}
    out: Dict[str, Dict[str, Dict[str, Any]]] = {}
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            case_id = str(row.get("case_id") or "")
            doc_id = raw_id(row.get("doc_id"))
            if case_id and doc_id:
                out.setdefault(case_id, {})[doc_id] = row
    return out


def seed_labels(cases_path: Path, output_path: Path) -> int:
    cases = load_cases(cases_path)
    rows = []
    for case in cases:
        if case.get("category") != "retrieval":
            continue
        for doc_id in case.get("expected_source_ids") or []:
            rows.append(
                {
                    "case_id": case.get("id"),
                    "query": case.get("query"),
                    "doc_id": doc_id,
                    "relevance": 2,
                    "reason": "Expected source from generated/audited current-policy golden case.",
                    "judge_model": "seed_expected_source",
                    "source": "expected_source_ids",
                }
            )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return len(rows)


def validate_cases(cases_path: Path, labels_path: Optional[Path], lineage_path: Path = DEFAULT_LINEAGE) -> Dict[str, Any]:
    cases = [row for row in load_cases(cases_path) if row.get("category") == "retrieval"]
    labels = load_labels(labels_path)
    errors: List[str] = []
    warnings: List[str] = []
    seen: set[str] = set()
    for case in cases:
        case_id = str(case.get("id") or "")
        if not case_id:
            errors.append("case_missing_id")
            continue
        if case_id in seen:
            errors.append(f"{case_id}:duplicate_id")
        seen.add(case_id)
        if not str(case.get("query") or "").strip():
            errors.append(f"{case_id}:missing_query")
        if not case.get("expected_source_ids"):
            errors.append(f"{case_id}:missing_expected_source_ids")
        if not case.get("expected_collection") and not case.get("expected_collections"):
            errors.append(f"{case_id}:missing_expected_collection")
        case_labels = labels.get(case_id, {})
        if labels_path and not case_labels:
            warnings.append(f"{case_id}:missing_relevance_labels")
        if labels_path and case_labels and not any(int(row.get("relevance", 0)) >= 2 for row in case_labels.values()):
            errors.append(f"{case_id}:no_relevance_2_label")

    return {
        "cases": len(cases),
        "labels_cases": len(labels),
        "errors": errors,
        "warnings": warnings,
        "lineage": str(lineage_path),
        "valid": not errors,
    }


def export_audit_csv(cases_path: Path, labels_path: Optional[Path], output_path: Path) -> int:
    cases = [row for row in load_cases(cases_path) if row.get("category") == "retrieval"]
    labels = load_labels(labels_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "case_id",
                "query",
                "query_class",
                "expected_collection",
                "expected_source_ids",
                "doc_id",
                "relevance",
                "reason",
                "source",
                "audit_relevance",
                "audit_notes",
            ],
        )
        writer.writeheader()
        count = 0
        for case in cases:
            case_id = str(case.get("id") or "")
            case_labels = labels.get(case_id) or {}
            if not case_labels:
                for doc_id in case.get("expected_source_ids") or [""]:
                    writer.writerow(
                        {
                            "case_id": case_id,
                            "query": case.get("query"),
                            "query_class": case.get("query_class"),
                            "expected_collection": case.get("expected_collection"),
                            "expected_source_ids": json.dumps(case.get("expected_source_ids") or [], ensure_ascii=False),
                            "doc_id": doc_id,
                            "relevance": "",
                            "reason": "",
                            "source": "",
                            "audit_relevance": "",
                            "audit_notes": "",
                        }
                    )
                    count += 1
                continue
            for doc_id, label in sorted(case_labels.items()):
                writer.writerow(
                    {
                        "case_id": case_id,
                        "query": case.get("query"),
                        "query_class": case.get("query_class"),
                        "expected_collection": case.get("expected_collection"),
                        "expected_source_ids": json.dumps(case.get("expected_source_ids") or [], ensure_ascii=False),
                        "doc_id": doc_id,
                        "relevance": label.get("relevance"),
                        "reason": label.get("reason"),
                        "source": label.get("source"),
                        "audit_relevance": "",
                        "audit_notes": "",
                    }
                )
                count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    inventory = sub.add_parser("inventory", help="Summarize available current-policy chunks")
    inventory.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    inventory.add_argument("--output", type=Path, default=DEFAULT_DRAFT_DIR / "chunk_inventory.json")

    generate = sub.add_parser("generate-cases", help="Generate draft golden retrieval cases from chunks")
    generate.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    generate.add_argument("--target-cases", type=int, default=200)
    generate.add_argument("--output", type=Path, default=DEFAULT_CASES)
    generate.add_argument("--no-variants", action="store_true")

    seed = sub.add_parser("seed-labels", help="Create relevance=2 seed labels from expected_source_ids")
    seed.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    seed.add_argument("--output", type=Path, default=DEFAULT_SEED_LABELS)

    validate = sub.add_parser("validate", help="Validate cases and optional labels")
    validate.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    validate.add_argument("--labels", type=Path, default=None)

    audit = sub.add_parser("audit-export", help="Export CSV for manual relevance audit")
    audit.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    audit.add_argument("--labels", type=Path, default=None)
    audit.add_argument("--output", type=Path, default=DEFAULT_AUDIT_CSV)

    args = parser.parse_args()

    if args.command == "inventory":
        records = load_chunk_inventory(args.data_dir)
        summary: Dict[str, Any] = {"total_chunks": len(records), "by_collection": {}}
        for record in records:
            summary["by_collection"].setdefault(record.collection, 0)
            summary["by_collection"][record.collection] += 1
        write_json(args.output, {"summary": summary, "chunks": [record.to_dict() for record in records]})
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    elif args.command == "generate-cases":
        records = load_chunk_inventory(args.data_dir)
        payload = build_cases(records, args.target_cases, include_variants=not args.no_variants)
        write_json(args.output, payload)
        print(json.dumps({"output": str(args.output), "cases": len(payload["test_cases"])}, ensure_ascii=False, indent=2))
    elif args.command == "seed-labels":
        count = seed_labels(args.cases, args.output)
        print(json.dumps({"output": str(args.output), "labels": count}, ensure_ascii=False, indent=2))
    elif args.command == "validate":
        result = validate_cases(args.cases, args.labels)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if not result["valid"]:
            raise SystemExit(1)
    elif args.command == "audit-export":
        count = export_audit_csv(args.cases, args.labels, args.output)
        print(json.dumps({"output": str(args.output), "rows": count}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
