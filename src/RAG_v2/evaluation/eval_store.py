"""MongoDB and artifact storage helpers for evaluation runs."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .eval_schemas import EvalCaseResult, EvalRun

EVAL_RUNS_COLLECTION = "eval_runs"
EVAL_CASE_RESULTS_COLLECTION = "eval_case_results"


def persist_eval_run_sync(
    db: Any,
    run: EvalRun,
    case_results: Iterable[EvalCaseResult],
) -> None:
    run_doc = run.to_dict()
    run_doc["_id"] = run.run_id
    run_doc["created_at"] = datetime.now(timezone.utc)
    db[EVAL_RUNS_COLLECTION].replace_one({"_id": run.run_id}, run_doc, upsert=True)

    case_docs: List[Dict[str, Any]] = []
    for result in case_results:
        doc = result.to_dict()
        doc["run_id"] = run.run_id
        doc["_id"] = f"{run.run_id}:{result.case_id}"
        doc["created_at"] = datetime.now(timezone.utc)
        case_docs.append(doc)
    if case_docs:
        db[EVAL_CASE_RESULTS_COLLECTION].delete_many({"run_id": run.run_id})
        db[EVAL_CASE_RESULTS_COLLECTION].insert_many(case_docs)


def write_eval_artifacts(
    output_dir: Path,
    run: EvalRun,
    case_results: Iterable[EvalCaseResult],
) -> Dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    cases = [result.to_dict() for result in case_results]

    json_path = output_dir / f"{run.eval_suite}_{run.run_id}.json"
    csv_path = output_dir / f"{run.eval_suite}_{run.run_id}.csv"
    artifacts = {"json": str(json_path), "csv": str(csv_path)}
    run_doc = run.to_dict()
    run_doc["artifacts"] = artifacts
    payload = {"run": run_doc, "cases": cases}
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    import csv

    with open(csv_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "case_id",
                "eval_suite",
                "passed",
                "error",
                "fail_reasons",
                "judge_scores",
                "metrics",
                "retrieved_source_ids",
                "latency_ms",
            ],
        )
        writer.writeheader()
        for row in cases:
            metrics = row.get("metrics") or {}
            timings = row.get("timings_ms") or {}
            writer.writerow(
                {
                    "case_id": row.get("case_id"),
                    "eval_suite": row.get("eval_suite"),
                    "passed": row.get("passed"),
                    "error": row.get("error") or "",
                    "fail_reasons": json.dumps(row.get("fail_reasons") or [], ensure_ascii=False),
                    "judge_scores": json.dumps(row.get("judge_scores") or {}, ensure_ascii=False),
                    "metrics": json.dumps(metrics, ensure_ascii=False),
                    "retrieved_source_ids": json.dumps(row.get("retrieved_source_ids") or [], ensure_ascii=False),
                    "latency_ms": timings.get("pipeline_total") or metrics.get("latency_ms") or 0,
                }
            )

    return artifacts


def _public_run(doc: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(doc)
    out.pop("_id", None)
    out.pop("created_at", None)
    return out


def _case_query_class(case: Dict[str, Any]) -> str:
    raw_case = case.get("case") if isinstance(case.get("case"), dict) else {}
    return str(raw_case.get("query_class") or "unknown")


def _case_collections(case: Dict[str, Any]) -> List[str]:
    raw_case = case.get("case") if isinstance(case.get("case"), dict) else {}
    expected = raw_case.get("expected_collections")
    if isinstance(expected, list) and expected:
        return [str(item) for item in expected if str(item).strip()]
    sources = case.get("sources") if isinstance(case.get("sources"), list) else []
    collections = []
    for source in sources:
        if not isinstance(source, dict):
            continue
        collection = source.get("collection")
        if collection:
            collections.append(str(collection))
    return sorted(set(collections)) or ["unknown"]


def _summarize_groups(groups: Dict[str, Dict[str, int]]) -> List[Dict[str, Any]]:
    rows = []
    for key, stats in sorted(groups.items()):
        total = stats["total_cases"]
        passed = stats["passed_cases"]
        rows.append(
            {
                "key": key,
                "total_cases": total,
                "passed_cases": passed,
                "failed_cases": total - passed,
                "pass_rate": round(passed / total, 4) if total else 0.0,
            }
        )
    return rows


def _build_case_breakdown(cases: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_query_class: Dict[str, Dict[str, int]] = defaultdict(lambda: {"total_cases": 0, "passed_cases": 0})
    by_collection: Dict[str, Dict[str, int]] = defaultdict(lambda: {"total_cases": 0, "passed_cases": 0})
    for case in cases:
        passed = bool(case.get("passed"))
        query_class = _case_query_class(case)
        by_query_class[query_class]["total_cases"] += 1
        by_query_class[query_class]["passed_cases"] += int(passed)
        for collection in _case_collections(case):
            by_collection[collection]["total_cases"] += 1
            by_collection[collection]["passed_cases"] += int(passed)
    return {
        "by_query_class": _summarize_groups(by_query_class),
        "by_collection": _summarize_groups(by_collection),
    }


def _stale_cases(cases: List[Dict[str, Any]], limit: int = 20) -> List[Dict[str, Any]]:
    return [
        case for case in cases
        if "stale_or_superseded_source" in (case.get("fail_reasons") or [])
    ][:limit]


def load_eval_dashboard_sync(
    db: Any,
    *,
    suite: Optional[str] = None,
    limit: int = 10,
    failing_limit: int = 20,
) -> Dict[str, Any]:
    query: Dict[str, Any] = {}
    if suite:
        query["eval_suite"] = suite

    cursor = (
        db[EVAL_RUNS_COLLECTION]
        .find(query)
        .sort("finished_at", -1)
        .limit(max(1, limit))
    )
    runs = [_public_run(doc) for doc in cursor]
    latest = runs[0] if runs else None
    trends = [
        {
            "run_id": run.get("run_id"),
            "eval_suite": run.get("eval_suite"),
            "finished_at": run.get("finished_at"),
            "status": run.get("status"),
            "summary": run.get("summary", {}),
        }
        for run in reversed(runs)
    ]

    latest_cases: List[Dict[str, Any]] = []
    fail_query: Dict[str, Any] = {"passed": False}
    if latest:
        fail_query["run_id"] = latest.get("run_id")
        latest_cases = list(
            db[EVAL_CASE_RESULTS_COLLECTION]
            .find({"run_id": latest.get("run_id")}, {"_id": 0})
            .limit(5000)
        )
    elif suite:
        fail_query["eval_suite"] = suite

    failing_cursor = (
        db[EVAL_CASE_RESULTS_COLLECTION]
        .find(fail_query, {"_id": 0})
        .sort("created_at", -1)
        .limit(max(1, failing_limit))
    )
    return {
        "status": "ok" if latest else "empty",
        "latest": latest,
        "runs": runs,
        "trends": trends,
        "failing_cases": list(failing_cursor),
        "breakdown": _build_case_breakdown(latest_cases),
        "stale_source_violations": _stale_cases(latest_cases),
    }


def load_latest_artifact_dashboard(output_dir: Path, suite: Optional[str] = None) -> Dict[str, Any]:
    pattern = f"{suite}_*.json" if suite else "*.json"
    files = sorted(output_dir.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return {
            "status": "empty",
            "latest": None,
            "runs": [],
            "trends": [],
            "failing_cases": [],
        }

    runs: List[Dict[str, Any]] = []
    latest_payload: Dict[str, Any] | None = None
    for path in files[:10]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        run = payload.get("run", {})
        if run:
            runs.append(run)
            if latest_payload is None:
                latest_payload = payload

    latest_cases: List[Dict[str, Any]] = []
    failing_cases = []
    if latest_payload:
        latest_cases = latest_payload.get("cases", [])
        failing_cases = [
            case for case in latest_cases
            if not case.get("passed")
        ][:20]

    return {
        "status": "ok" if runs else "empty",
        "latest": runs[0] if runs else None,
        "runs": runs,
        "trends": [
            {
                "run_id": run.get("run_id"),
                "eval_suite": run.get("eval_suite"),
                "finished_at": run.get("finished_at"),
                "status": run.get("status"),
                "summary": run.get("summary", {}),
            }
            for run in reversed(runs)
        ],
        "failing_cases": failing_cases,
        "breakdown": _build_case_breakdown(latest_cases),
        "stale_source_violations": _stale_cases(latest_cases),
    }
