"""Evaluate domain routing without running retrieval.

The report separates four stages:

1. Raw classifier domains.
2. ``CollectionSelector`` collections.
3. Final pipeline collections after the kehoach lock.
4. All-collections baseline.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Any, Dict, Iterable, List, Optional, Sequence

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from query.router import QueryRouter
from query.training_data import get_training_data
from retrieval.collection_selector import (
    ALL_COLLECTIONS,
    CONFIDENCE_THRESHOLD,
    CollectionSelector,
)
from pipeline.flows import _should_lock_kehoach_route

VALID_DOMAINS = {"ctdt", "quydinh", "kehoach", "stsv"}
STAGE_RAW = "raw_classifier"
STAGE_SELECTOR = "selector"
STAGE_FINAL = "final_pipeline"
STAGE_ALL = "all_collections"
CONFIDENCE_BUCKETS = (
    (0.0, 0.35, "0.00-0.35"),
    (0.35, 0.55, "0.35-0.55"),
    (0.55, 0.75, "0.55-0.75"),
    (0.75, 1.01, "0.75-1.00"),
)
MARGIN_BUCKETS = (
    (0.0, 0.05, "0.00-0.05"),
    (0.05, 0.15, "0.05-0.15"),
    (0.15, 0.30, "0.15-0.30"),
    (0.30, 1.01, "0.30-1.00"),
)


@dataclass(frozen=True)
class RoutingEvalCase:
    case_id: str
    query: str
    expected_domains: List[str]
    source: str = ""


def _dedup(values: Iterable[str]) -> List[str]:
    seen: Dict[str, None] = {}
    for value in values:
        domain = str(value or "").strip().lower()
        if domain in VALID_DOMAINS:
            seen.setdefault(domain, None)
    return list(seen.keys())


def _as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.replace(";", ",").split(",") if part.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _raw_id(value: Any) -> str:
    text = str(value or "").strip()
    return text.split("/", 1)[-1] if "/" in text else text


def _collection_from_prefixed_id(value: Any) -> str:
    text = str(value or "").strip().lower()
    if "/" not in text:
        return ""
    collection = text.split("/", 1)[0]
    return collection if collection in VALID_DOMAINS else ""


def _load_json_or_jsonl(path: Path) -> List[Dict[str, Any]]:
    if path.suffix == ".jsonl":
        with open(path, encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    if isinstance(payload, dict):
        for key in ("items", "cases", "test_cases", "rows", "data", "chunks"):
            if isinstance(payload.get(key), list):
                return payload[key]
    return payload if isinstance(payload, list) else []


def _rows_from_payload(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("items", "chunks", "data", "rows"):
            if isinstance(payload.get(key), list):
                return [item for item in payload[key] if isinstance(item, dict)]
        return [payload]
    return []


def build_chunk_collection_index(data_dir: Path) -> Dict[str, str]:
    """Build a lightweight id -> collection map from local chunk JSON files."""
    index: Dict[str, str] = {}
    if not data_dir.exists():
        return index
    for collection in sorted(VALID_DOMAINS):
        root = data_dir / collection
        if not root.exists():
            continue
        for path in root.rglob("*.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            for row in _rows_from_payload(payload):
                for key in ("id", "chunk_id", "readable_id", "doc_id"):
                    raw = _raw_id(row.get(key))
                    if raw:
                        index.setdefault(raw, collection)
    return index


def _expected_domains_from_ids(
    ids: Iterable[str],
    chunk_collection_index: Optional[Dict[str, str]] = None,
) -> List[str]:
    expected: List[str] = []
    for value in ids:
        collection = _collection_from_prefixed_id(value)
        if not collection and chunk_collection_index is not None:
            collection = chunk_collection_index.get(_raw_id(value), "")
        if collection:
            expected.append(collection)
    return _dedup(expected)


def expected_domains_for_item(
    item: Dict[str, Any],
    chunk_collection_index: Optional[Dict[str, str]] = None,
) -> List[str]:
    expected = _as_list(item.get("expected_collections"))
    expected += _as_list(
        item.get("expected_collection")
        or item.get("source")
        or item.get("collection")
    )
    evidence_ids = (
        _as_list(item.get("evidence_chunk_ids"))
        or _as_list(item.get("expected_source_ids"))
        or _as_list(item.get("relevant_doc_ids"))
        or _as_list(item.get("ground_truth_contexts"))
        or _as_list(item.get("context_ids"))
    )
    expected += _expected_domains_from_ids(
        evidence_ids,
        chunk_collection_index=chunk_collection_index,
    )
    return _dedup(expected)


def load_training_cases(limit: int = 0) -> List[RoutingEvalCase]:
    cases: List[RoutingEvalCase] = []
    for index, (query, labels) in enumerate(get_training_data(), start=1):
        expected = _dedup(labels)
        if not query or not expected:
            continue
        cases.append(
            RoutingEvalCase(
                case_id=f"training_{index:04d}",
                query=query,
                expected_domains=expected,
                source="training_data",
            )
        )
        if limit and len(cases) >= limit:
            break
    return cases


def load_dataset_cases(
    paths: Sequence[Path],
    *,
    chunk_collection_index: Optional[Dict[str, str]] = None,
    limit: int = 0,
) -> List[RoutingEvalCase]:
    cases: List[RoutingEvalCase] = []
    for path in paths:
        for index, item in enumerate(_load_json_or_jsonl(path), start=1):
            if not isinstance(item, dict):
                continue
            query = str(
                item.get("query")
                or item.get("question")
                or item.get("instruction")
                or ""
            ).strip()
            expected = expected_domains_for_item(
                item,
                chunk_collection_index=chunk_collection_index,
            )
            if not query or not expected:
                continue
            cases.append(
                RoutingEvalCase(
                    case_id=str(item.get("id") or f"{path.stem}_{index:04d}"),
                    query=query,
                    expected_domains=expected,
                    source=str(path),
                )
            )
            if limit and len(cases) >= limit:
                return cases
    return cases


def _raw_classifier_domains(routing: Dict[str, Any]) -> List[str]:
    if routing.get("intent") not in (None, "rag"):
        return []
    domains = _as_list(routing.get("domains"))
    if not domains:
        domains = _as_list(routing.get("domain"))
    return _dedup(domains)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _probability_margin(routing: Dict[str, Any]) -> float:
    probabilities = routing.get("probabilities") or {}
    if not isinstance(probabilities, dict):
        return 0.0
    scores = sorted(
        (_safe_float(value) for value in probabilities.values()),
        reverse=True,
    )
    if len(scores) < 2:
        return scores[0] if scores else 0.0
    return max(0.0, scores[0] - scores[1])


def _bucket_label(value: float, buckets: Sequence[tuple[float, float, str]]) -> str:
    for lower, upper, label in buckets:
        if lower <= value < upper:
            return label
    return buckets[-1][2]


def _evaluate_set(predicted: List[str], expected: List[str]) -> Dict[str, Any]:
    pred_set = set(predicted)
    exp_set = set(expected)
    matched = pred_set & exp_set
    precision = len(matched) / len(pred_set) if pred_set else 0.0
    recall = len(matched) / len(exp_set) if exp_set else 0.0
    f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    return {
        "top1": 1.0 if predicted and predicted[0] in exp_set else 0.0,
        "exact": 1.0 if pred_set == exp_set else 0.0,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "missing": 1.0 if exp_set - pred_set else 0.0,
        "extra": 1.0 if pred_set - exp_set else 0.0,
    }


def _summarize_stage(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not rows:
        return {
            "count": 0,
            "top1_accuracy": 0.0,
            "exact_set_accuracy": 0.0,
            "set_precision": 0.0,
            "set_recall": 0.0,
            "set_f1": 0.0,
            "missing_domain_rate": 0.0,
            "extra_domain_rate": 0.0,
            "kehoach_false_negative_rate": 0.0,
            "kehoach_false_positive_rate": 0.0,
            "per_domain": {},
        }

    totals = {key: 0.0 for key in ("top1", "exact", "precision", "recall", "f1", "missing", "extra")}
    per_domain = {
        domain: {"tp": 0, "predicted": 0, "expected": 0, "fp": 0, "fn": 0}
        for domain in sorted(VALID_DOMAINS)
    }
    kehoach_expected = 0
    kehoach_not_expected = 0
    kehoach_fn = 0
    kehoach_fp = 0

    for row in rows:
        metrics = _evaluate_set(row["predicted"], row["expected"])
        for key in totals:
            totals[key] += metrics[key]
        pred_set = set(row["predicted"])
        exp_set = set(row["expected"])
        for domain, counts in per_domain.items():
            if domain in pred_set:
                counts["predicted"] += 1
            if domain in exp_set:
                counts["expected"] += 1
            if domain in pred_set and domain in exp_set:
                counts["tp"] += 1
            if domain in pred_set and domain not in exp_set:
                counts["fp"] += 1
            if domain in exp_set and domain not in pred_set:
                counts["fn"] += 1
        if "kehoach" in exp_set:
            kehoach_expected += 1
            if "kehoach" not in pred_set:
                kehoach_fn += 1
        else:
            kehoach_not_expected += 1
            if "kehoach" in pred_set:
                kehoach_fp += 1

    count = len(rows)
    domain_metrics: Dict[str, Dict[str, float]] = {}
    for domain, counts in per_domain.items():
        precision = counts["tp"] / counts["predicted"] if counts["predicted"] else 0.0
        recall = counts["tp"] / counts["expected"] if counts["expected"] else 0.0
        f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
        domain_metrics[domain] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "missing_rate": round(counts["fn"] / counts["expected"], 4) if counts["expected"] else 0.0,
            "extra_rate": round(counts["fp"] / (count - counts["expected"]), 4)
            if count > counts["expected"]
            else 0.0,
            "expected_count": counts["expected"],
            "predicted_count": counts["predicted"],
        }

    return {
        "count": count,
        "top1_accuracy": round(totals["top1"] / count, 4),
        "exact_set_accuracy": round(totals["exact"] / count, 4),
        "set_precision": round(totals["precision"] / count, 4),
        "set_recall": round(totals["recall"] / count, 4),
        "set_f1": round(totals["f1"] / count, 4),
        "missing_domain_rate": round(totals["missing"] / count, 4),
        "extra_domain_rate": round(totals["extra"] / count, 4),
        "kehoach_false_negative_rate": round(kehoach_fn / kehoach_expected, 4)
        if kehoach_expected
        else 0.0,
        "kehoach_false_positive_rate": round(kehoach_fp / kehoach_not_expected, 4)
        if kehoach_not_expected
        else 0.0,
        "per_domain": domain_metrics,
    }


def _summarize_buckets(
    rows: List[Dict[str, Any]],
    bucket_key: str,
) -> Dict[str, Dict[str, Any]]:
    buckets: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        buckets.setdefault(str(row[bucket_key]), []).append(row)
    return {label: _summarize_stage(bucket_rows) for label, bucket_rows in sorted(buckets.items())}


def evaluate_cases(
    cases: Sequence[RoutingEvalCase],
    *,
    router: Any,
    selector: Optional[CollectionSelector] = None,
    confidence_threshold: float = CONFIDENCE_THRESHOLD,
) -> Dict[str, Any]:
    selector = selector or CollectionSelector(confidence_threshold=confidence_threshold)
    stage_rows: Dict[str, List[Dict[str, Any]]] = {
        STAGE_RAW: [],
        STAGE_SELECTOR: [],
        STAGE_FINAL: [],
        STAGE_ALL: [],
    }
    case_rows: List[Dict[str, Any]] = []
    low_confidence_count = 0

    for case in cases:
        routing = router.route(case.query)
        confidence = _safe_float(routing.get("confidence"))
        margin = _probability_margin(routing)
        if confidence < selector.confidence_threshold:
            low_confidence_count += 1

        raw_domains = _raw_classifier_domains(routing)
        domain = routing.get("domain")
        domains = routing.get("domains") or ([domain] if domain else [])
        selector_collections = selector.select(
            domain=domain,
            domains=domains,
            confidence=confidence,
            query=case.query,
            probabilities=routing.get("probabilities"),
        )
        final_collections = list(selector_collections)
        if _should_lock_kehoach_route(
            question=case.query,
            search_query=case.query,
            routing_result=routing,
        ):
            final_collections = ["kehoach"]

        predictions = {
            STAGE_RAW: raw_domains,
            STAGE_SELECTOR: _dedup(selector_collections),
            STAGE_FINAL: _dedup(final_collections),
            STAGE_ALL: list(ALL_COLLECTIONS),
        }
        confidence_bucket = _bucket_label(confidence, CONFIDENCE_BUCKETS)
        margin_bucket = _bucket_label(margin, MARGIN_BUCKETS)
        for stage, predicted in predictions.items():
            stage_rows[stage].append(
                {
                    "case_id": case.case_id,
                    "query": case.query,
                    "expected": list(case.expected_domains),
                    "predicted": list(predicted),
                    "confidence": confidence,
                    "margin": margin,
                    "confidence_bucket": confidence_bucket,
                    "margin_bucket": margin_bucket,
                }
            )
        case_rows.append(
            {
                "id": case.case_id,
                "query": case.query,
                "source": case.source,
                "expected_domains": list(case.expected_domains),
                "routing": routing,
                "raw_classifier": raw_domains,
                "selector": selector_collections,
                "final_pipeline": final_collections,
                "confidence": round(confidence, 4),
                "margin": round(margin, 4),
                "confidence_bucket": confidence_bucket,
                "margin_bucket": margin_bucket,
            }
        )

    stage_summaries = {stage: _summarize_stage(rows) for stage, rows in stage_rows.items()}
    for stage_summary in stage_summaries.values():
        stage_summary["low_confidence_fallback_rate"] = round(
            low_confidence_count / len(cases),
            4,
        ) if cases else 0.0

    return {
        "case_count": len(cases),
        "confidence_threshold": selector.confidence_threshold,
        "stages": stage_summaries,
        "confidence_buckets": _summarize_buckets(stage_rows[STAGE_FINAL], "confidence_bucket"),
        "margin_buckets": _summarize_buckets(stage_rows[STAGE_FINAL], "margin_bucket"),
        "cases": case_rows,
    }


def evaluate_thresholds(
    cases: Sequence[RoutingEvalCase],
    *,
    router: Any,
    thresholds: Sequence[float],
) -> Dict[str, Any]:
    reports = [
        evaluate_cases(
            cases,
            router=router,
            selector=CollectionSelector(confidence_threshold=threshold),
            confidence_threshold=threshold,
        )
        for threshold in thresholds
    ]
    return {
        "case_count": len(cases),
        "thresholds": list(thresholds),
        "runs": reports,
    }


def build_router(mode: str = "classifier") -> QueryRouter:
    if mode != "classifier":
        raise ValueError("Only classifier router mode is supported for routing-only eval")
    return QueryRouter(mode="classifier")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", action="append", type=Path, default=[])
    parser.add_argument("--data-dir", type=Path, default=PROJECT_ROOT / "data")
    parser.add_argument("--no-training-data", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument(
        "--thresholds",
        type=float,
        nargs="+",
        default=[CONFIDENCE_THRESHOLD],
        help="Selector confidence thresholds to sweep.",
    )
    parser.add_argument("--output", type=Path)
    return parser


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args()
    chunk_index = build_chunk_collection_index(args.data_dir) if args.dataset else {}
    cases: List[RoutingEvalCase] = []
    if not args.no_training_data:
        cases.extend(load_training_cases(limit=args.limit))
    remaining_limit = max(0, args.limit - len(cases)) if args.limit else 0
    cases.extend(
        load_dataset_cases(
            args.dataset,
            chunk_collection_index=chunk_index,
            limit=remaining_limit,
        )
    )
    if args.limit:
        cases = cases[: args.limit]

    router = build_router()
    report = evaluate_thresholds(cases, router=router, thresholds=args.thresholds)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
