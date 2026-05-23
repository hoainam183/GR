"""Two-layer evaluation runner for RAG v2.

Examples from ``src/RAG_v2``::

    python -m evaluation.two_layer_eval current --persist
    python -m evaluation.two_layer_eval historical --max-cases 50 --persist
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import Settings
from evaluation.eval_schemas import (
    CURRENT_POLICY_RUBRIC,
    HISTORICAL_RUBRIC,
    EvalCase,
    EvalCaseResult,
    EvalRun,
    freshness_pass_for_sources,
    load_current_policy_cases,
    load_historical_email_cases,
    mean_score,
    now_iso,
    parse_judge_scores,
    percentile,
    raw_id,
    status_from_metrics,
)
from evaluation.eval_store import persist_eval_run_sync, write_eval_artifacts

logger = logging.getLogger(__name__)

DEFAULT_HISTORICAL_DATASET = SRC_ROOT / "clean_data" / "test_dataset.json"
DEFAULT_CURRENT_DATASET = PROJECT_ROOT / "eval" / "golden_dataset.json"
DEFAULT_CURRENT_LABELS = PROJECT_ROOT / "evaluation" / "search_strategy_labels.jsonl"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "evaluation" / "results"
DEFAULT_LINEAGE = PROJECT_ROOT / "data" / "document_lineage.json"


def _build_history_from_email_context(context: str) -> List[Dict[str, str]]:
    context = (context or "").strip()
    if not context:
        return []
    return [
        {
            "role": "assistant",
            "content": (
                "Ngữ cảnh các email tư vấn trước trong cùng thread:\n"
                + context[-6000:]
            ),
        }
    ]


class GeminiJudge:
    def __init__(self, settings: Settings) -> None:
        from openai import OpenAI

        api_key = settings.google_api_key or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError("GOOGLE_API_KEY is required for LLM judging")
        self.model = settings.chat_model
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        )

    def judge_historical(self, case: EvalCase, actual_answer: str) -> tuple[Dict[str, float], List[str]]:
        system = (
            "You are evaluating a Vietnamese academic advising assistant on "
            "historical email threads. Do not penalize the answer for not "
            "matching outdated factual policy. Penalize ignoring thread context, "
            "illogical advice, failure to ask for missing critical information, "
            "or hallucinating personal facts. Return JSON only."
        )
        user = {
            "rubric": HISTORICAL_RUBRIC,
            "score_range": "0.0 to 1.0",
            "question": case.question,
            "thread_context": case.context,
            "historical_reference_answer": case.ground_truth_answer,
            "actual_answer": actual_answer,
            "output_schema": {
                "scores": {key: 0.0 for key in HISTORICAL_RUBRIC},
                "fail_reasons": ["short strings"],
            },
        }
        return self._judge(system, user, HISTORICAL_RUBRIC)

    def judge_current(self, case: EvalCase, actual_answer: str, sources: List[Dict[str, Any]]) -> tuple[Dict[str, float], List[str]]:
        system = (
            "You are a strict evaluator for a Vietnamese university current-policy "
            "RAG system. Judge only against the provided current retrieved sources. "
            "Return JSON only."
        )
        user = {
            "rubric": CURRENT_POLICY_RUBRIC,
            "score_range": "0.0 to 1.0",
            "question": case.question,
            "ground_truth_answer": case.ground_truth_answer,
            "expected_source_ids": case.expected_source_ids,
            "actual_answer": actual_answer,
            "sources": sources[:8],
            "output_schema": {
                "scores": {key: 0.0 for key in CURRENT_POLICY_RUBRIC},
                "fail_reasons": ["short strings"],
            },
        }
        return self._judge(system, user, CURRENT_POLICY_RUBRIC)

    def _judge(self, system: str, payload: Dict[str, Any], rubric: List[str]) -> tuple[Dict[str, float], List[str]]:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            temperature=0.0,
            max_tokens=1024,
        )
        raw = response.choices[0].message.content or ""
        return parse_judge_scores(raw, rubric)


def _compact_source(row: Dict[str, Any]) -> Dict[str, Any]:
    metadata = dict(row.get("metadata") or {})
    return {
        "id": row.get("id"),
        "collection": row.get("collection") or metadata.get("collection"),
        "score": row.get("rerank_score", row.get("score", 0.0)),
        "text": str(row.get("text") or row.get("content") or "")[:1200],
        "metadata": {
            key: metadata.get(key)
            for key in (
                "source",
                "filename",
                "document_id",
                "doc_id",
                "doc_title",
                "document_title",
                "doc_type",
                "chapter",
                "article",
                "clause",
                "effective_date",
                "title",
                "major_code",
                "applicable_cohort",
                "date_str",
            )
            if metadata.get(key) is not None
        },
    }


def _source_ids(sources: List[Dict[str, Any]]) -> List[str]:
    ids: List[str] = []
    for source in sources:
        sid = raw_id(source.get("id"))
        if sid:
            ids.append(sid)
    return ids


def _expected_hit(retrieved: List[str], expected: List[str]) -> bool:
    expected_set = {raw_id(item) for item in expected if raw_id(item)}
    if not expected_set:
        return True
    return bool({raw_id(item) for item in retrieved} & expected_set)


def _as_text_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.replace(";", ",").split(",") if part.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _bool_metadata(value: Any, default: bool = True) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "y"}:
            return True
        if lowered in {"false", "0", "no", "n"}:
            return False
    return default


def _answer_contains_all(answer: str, expected: List[str]) -> tuple[bool, List[str]]:
    normalized_answer = " ".join(answer.lower().split())
    missing = [
        item for item in expected
        if " ".join(item.lower().split()) not in normalized_answer
    ]
    return not missing, missing


def _looks_like_refusal(answer: str) -> bool:
    normalized = " ".join(answer.lower().split())
    refusal_markers = (
        "không có đủ thông tin",
        "không đủ thông tin",
        "chưa có đủ thông tin",
        "không tìm thấy thông tin",
        "không thể trả lời",
        "không xác định được",
        "cần thêm thông tin",
        "insufficient information",
        "not enough information",
    )
    return any(marker in normalized for marker in refusal_markers)


def _case_expected_citations(case: EvalCase) -> List[str]:
    metadata = case.metadata or {}
    explicit = _as_text_list(metadata.get("expected_citations"))
    if explicit:
        return explicit

    doc_label = metadata.get("doc_type") or metadata.get("document_title") or metadata.get("doc_title")
    article = metadata.get("article")
    clause = metadata.get("clause")
    parts = [str(part).strip() for part in (doc_label, article) if str(part or "").strip()]
    if clause:
        parts.append(f"Khoản {clause}")
    return [" - ".join(parts)] if parts else []


def _citation_text_ok(answer: str, case: EvalCase) -> bool:
    citations = _case_expected_citations(case)
    if not citations:
        return True
    return _answer_contains_all(answer, citations)[0]


def _deterministic_answer_checks(
    case: EvalCase,
    actual_answer: str,
) -> tuple[Dict[str, float], List[str]]:
    """Check schema-v1 answer/refusal/citation expectations without an LLM judge."""
    if not actual_answer:
        return {}, []

    metadata = case.metadata or {}
    metrics: Dict[str, float] = {}
    fail_reasons: List[str] = []
    answerable = _bool_metadata(metadata.get("answerable"), default=True)
    expected_behavior = str(metadata.get("expected_behavior") or "").strip()

    if not answerable or expected_behavior == "refuse_insufficient_context":
        refused = _looks_like_refusal(actual_answer)
        metrics["refusal_accuracy"] = 1.0 if refused else 0.0
        if not refused:
            fail_reasons.append("expected_refusal_not_found")

        explicit_citations = _as_text_list(metadata.get("expected_citations"))
        if explicit_citations and any(
            citation.lower() in actual_answer.lower() for citation in explicit_citations
        ):
            fail_reasons.append("refusal_includes_citation")
        return metrics, fail_reasons

    atomic_facts = _as_text_list(metadata.get("atomic_facts"))
    if atomic_facts:
        ok, missing = _answer_contains_all(actual_answer, atomic_facts)
        metrics["atomic_fact_coverage"] = (
            (len(atomic_facts) - len(missing)) / len(atomic_facts)
            if atomic_facts else 1.0
        )
        if not ok:
            fail_reasons.append("missing_atomic_facts:" + ",".join(missing))

    citations = _case_expected_citations(case)
    if citations:
        citation_ok = _citation_text_ok(actual_answer, case)
        metrics["citation_text_accuracy"] = 1.0 if citation_ok else 0.0
        if not citation_ok:
            fail_reasons.append("expected_citation_missing")

    return metrics, fail_reasons


def _mean_metric_or_none(results: List[EvalCaseResult], key: str) -> Optional[float]:
    values = [r.metrics.get(key) for r in results if r.metrics.get(key) is not None]
    return mean_score(values) if values else None


def run_historical_eval(
    *,
    dataset_path: Path,
    max_cases: int,
    trigger: str,
    persist: bool,
    output_dir: Path,
    judge_enabled: bool,
) -> tuple[EvalRun, List[EvalCaseResult]]:
    started = now_iso()
    run_id = f"{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    settings = Settings()
    cases = load_historical_email_cases(dataset_path, limit=max_cases)
    errors: List[str] = []
    results: List[EvalCaseResult] = []

    pipeline = None
    judge = None
    try:
        from pipeline.rag_pipeline import RAGPipeline
        pipeline = RAGPipeline(settings=settings)
    except Exception as exc:
        errors.append(f"pipeline_init_failed: {exc}")

    if judge_enabled:
        try:
            judge = GeminiJudge(settings)
        except Exception as exc:
            errors.append(f"judge_init_failed: {exc}")

    for case in cases:
        try:
            actual = ""
            sources: List[Dict[str, Any]] = []
            timings: Dict[str, float] = {}
            if pipeline is not None:
                t0 = time.perf_counter()
                out = pipeline.query_v3(
                    question=case.question,
                    history=_build_history_from_email_context(case.context),
                    top_k=settings.top_k,
                )
                timings = dict(out.get("timings_ms") or {})
                timings.setdefault("pipeline_total", round((time.perf_counter() - t0) * 1000, 2))
                actual = str(out.get("answer") or "")
                sources = [_compact_source(src) for src in (out.get("sources") or [])]

            scores: Dict[str, float] = {}
            fail_reasons: List[str] = []
            if judge is not None:
                scores, fail_reasons = judge.judge_historical(case, actual)
            passed = not fail_reasons and (not scores or mean_score(scores.values()) >= 0.7)
            results.append(
                EvalCaseResult(
                    eval_suite="historical_email",
                    case_id=case.case_id,
                    question=case.question,
                    actual_answer=actual,
                    retrieved_source_ids=_source_ids(sources),
                    sources=sources,
                    timings_ms=timings,
                    judge_scores=scores,
                    fail_reasons=fail_reasons,
                    passed=passed,
                    case=case.to_dict(),
                )
            )
        except Exception as exc:
            results.append(
                EvalCaseResult(
                    eval_suite="historical_email",
                    case_id=case.case_id,
                    question=case.question,
                    error=str(exc),
                    passed=False,
                    fail_reasons=["case_execution_error"],
                    case=case.to_dict(),
                )
            )

    summary = {
        "total_cases": len(results),
        "passed_cases": sum(1 for r in results if r.passed),
        "failed_cases": sum(1 for r in results if not r.passed),
        "avg_judge_score": mean_score(
            mean_score(r.judge_scores.values()) for r in results if r.judge_scores
        ),
        "latency_p50_ms": percentile(
            (r.timings_ms or {}).get("pipeline_total", 0.0) for r in results
        ),
        "latency_p95_ms": percentile(
            (r.timings_ms or {}).get("pipeline_total", 0.0) for r in results
        ),
    }
    run = EvalRun(
        run_id=run_id,
        eval_suite="historical_email",
        status=status_from_metrics(summary, errors if not results else None),
        started_at=started,
        finished_at=now_iso(),
        trigger=trigger,
        summary=summary,
        config={"dataset": str(dataset_path), "max_cases": max_cases, "judge_enabled": judge_enabled},
        errors=errors,
    )
    run.artifacts = write_eval_artifacts(output_dir, run, results)
    if persist:
        _persist_with_settings(settings, run, results)
    return run, results


def _load_search_strategy_baseline() -> Dict[str, Any]:
    path = PROJECT_ROOT / "evaluation" / "search_strategy_results.json"
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        current = (payload.get("summary") or {}).get("current_hybrid") or {}
        reranked = (payload.get("summary") or {}).get("current_hybrid_reranked") or {}
        return {
            "raw_recall_at_50": current.get("recall_at_50"),
            "reranked_ndcg_at_10": reranked.get("ndcg_at_10"),
            "reranked_mrr_at_10": reranked.get("mrr_at_10"),
        }
    except Exception:
        return {}


def _baseline_warnings(summary: Dict[str, Any], baseline: Dict[str, Any]) -> List[str]:
    comparisons = [
        ("ndcg_at_10", baseline.get("reranked_ndcg_at_10")),
        ("mrr_at_10", baseline.get("reranked_mrr_at_10")),
        ("recall_at_50", baseline.get("raw_recall_at_50")),
    ]
    warnings: List[str] = []
    for metric, baseline_value in comparisons:
        if baseline_value is None:
            continue
        current_value = float(summary.get(metric) or 0.0)
        if current_value < float(baseline_value):
            warnings.append(
                f"{metric}_below_baseline:{current_value:.4f}<baseline:{float(baseline_value):.4f}"
            )
    return warnings


def run_current_policy_eval(
    *,
    dataset_path: Path,
    max_cases: int,
    trigger: str,
    persist: bool,
    output_dir: Path,
    judge_enabled: bool,
    labels_path: Path = DEFAULT_CURRENT_LABELS,
    trigger_document_id: Optional[str] = None,
    trigger_collection: Optional[str] = None,
) -> tuple[EvalRun, List[EvalCaseResult]]:
    started = now_iso()
    run_id = f"{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    settings = Settings()
    errors: List[str] = []
    cases = load_current_policy_cases(dataset_path, limit=max_cases)
    case_map = {case.case_id: case for case in cases}
    results: List[EvalCaseResult] = []
    judge = None
    pipeline = None

    if judge_enabled:
        try:
            judge = GeminiJudge(settings)
        except Exception as exc:
            errors.append(f"judge_init_failed: {exc}")
        try:
            from pipeline.rag_pipeline import RAGPipeline
            pipeline = RAGPipeline(settings=settings)
        except Exception as exc:
            errors.append(f"pipeline_init_failed: {exc}")

    try:
        from evaluation.evaluate_current_pipeline import evaluate
        payload = evaluate(dataset_path, 10, None, max_cases=max_cases, labels_path=labels_path)
        rows = payload.get("rows", [])
        summary_src = payload.get("summary", {})
    except Exception as exc:
        rows = []
        summary_src = {}
        errors.append(f"current_pipeline_eval_failed: {exc}")

    for row in rows:
        case_id = str(row.get("id") or "")
        case = case_map.get(case_id) or EvalCase(
            eval_suite="current_policy",
            case_id=case_id or f"row_{len(results) + 1}",
            question=str(row.get("query") or ""),
        )
        compact_sources = [_compact_source(src) for src in row.get("sources", [])]
        retrieved_ids = [raw_id(item) for item in row.get("retrieved_ids", [])]
        actual_answer = ""
        judge_sources = compact_sources
        metrics = {
            "recall_at_k": float(row.get("recall_at_k") or 0.0),
            "raw_recall_at_50": float(row.get("raw_recall_at_50") or 0.0),
            "context_precision": float(row.get("context_precision") or 0.0),
            "context_recall": float(row.get("context_recall") or 0.0),
            "mrr_at_k": float(row.get("mrr_at_k") or 0.0),
            "ndcg_at_k": float(row.get("ndcg_at_k") or 0.0),
            "latency_ms": float(row.get("latency_ms") or 0.0),
            "collection_hit": 1.0 if row.get("collection_hit") else 0.0,
            "keyword_hit": 1.0 if row.get("keyword_hit") else 0.0,
            "label_count": float(row.get("label_count") or 0.0),
            "relevant_count": float(row.get("relevant_count") or 0.0),
            "rel2_count": float(row.get("rel2_count") or 0.0),
        }
        fresh = freshness_pass_for_sources(compact_sources, DEFAULT_LINEAGE)
        citation_ok = _expected_hit(retrieved_ids, case.expected_source_ids)
        metrics["freshness_pass"] = 1.0 if fresh else 0.0
        metrics["citation_accuracy"] = 1.0 if citation_ok else 0.0
        fail_reasons: List[str] = []
        if not fresh:
            fail_reasons.append("stale_or_superseded_source")
        if not citation_ok:
            fail_reasons.append("expected_source_not_retrieved")

        scores: Dict[str, float] = {}
        if judge is not None and case.ground_truth_answer:
            if pipeline is not None:
                try:
                    out = pipeline.query_v3(
                        question=case.question,
                        history=[],
                        top_k=settings.top_k,
                    )
                    actual_answer = str(out.get("answer") or "")
                    generated_sources = [
                        _compact_source(src) for src in (out.get("sources") or [])
                    ]
                    if generated_sources:
                        judge_sources = generated_sources
                except Exception as exc:
                    fail_reasons.append("full_rag_generation_error")
                    errors.append(f"case_{case.case_id}_generation_failed: {exc}")
            scores, judge_reasons = judge.judge_current(case, actual_answer, judge_sources)
            fail_reasons.extend(judge_reasons)

        deterministic_metrics, deterministic_reasons = _deterministic_answer_checks(
            case,
            actual_answer,
        )
        metrics.update(deterministic_metrics)
        fail_reasons.extend(deterministic_reasons)

        results.append(
            EvalCaseResult(
                eval_suite="current_policy",
                case_id=case.case_id,
                question=case.question,
                actual_answer=actual_answer,
                retrieved_source_ids=retrieved_ids,
                sources=judge_sources,
                timings_ms=row.get("timings_ms") or {"pipeline_total": metrics["latency_ms"]},
                judge_scores=scores,
                metrics=metrics,
                fail_reasons=fail_reasons,
                passed=not fail_reasons,
                case=case.to_dict(),
            )
        )

    baseline = _load_search_strategy_baseline()
    summary = {
        "total_cases": len(results),
        "passed_cases": sum(1 for r in results if r.passed),
        "failed_cases": sum(1 for r in results if not r.passed),
        "collection_accuracy": summary_src.get("collection_accuracy", 0.0),
        "keyword_hit_rate": summary_src.get("keyword_hit_rate", 0.0),
        "n_source_labeled_cases": summary_src.get("n_source_labeled_cases", 0),
        "n_relevance_labeled_cases": summary_src.get("n_relevance_labeled_cases", 0),
        "ndcg_at_10": mean_score(r.metrics.get("ndcg_at_k") for r in results),
        "mrr_at_10": mean_score(r.metrics.get("mrr_at_k") for r in results),
        "recall_at_50": mean_score(r.metrics.get("raw_recall_at_50") for r in results),
        "context_precision": mean_score(r.metrics.get("context_precision") for r in results),
        "context_recall": mean_score(r.metrics.get("context_recall") for r in results),
        "ndcg_at_k": mean_score(r.metrics.get("ndcg_at_k") for r in results),
        "mrr_at_k": mean_score(r.metrics.get("mrr_at_k") for r in results),
        "recall_at_k": mean_score(r.metrics.get("recall_at_k") for r in results),
        "raw_recall_at_50": summary_src.get("raw_recall_at_50", baseline.get("raw_recall_at_50")),
        "citation_accuracy": mean_score(r.metrics.get("citation_accuracy") for r in results),
        "citation_text_accuracy": _mean_metric_or_none(results, "citation_text_accuracy"),
        "atomic_fact_coverage": _mean_metric_or_none(results, "atomic_fact_coverage"),
        "refusal_accuracy": _mean_metric_or_none(results, "refusal_accuracy"),
        "freshness_pass_rate": mean_score(r.metrics.get("freshness_pass") for r in results),
        "latency_p50_ms": summary_src.get("latency_p50_ms", 0.0),
        "latency_p95_ms": summary_src.get("latency_p95_ms", 0.0),
        "search_strategy_baseline": baseline,
    }
    summary["baseline_warnings"] = _baseline_warnings(summary, baseline)
    config = {
        "dataset": str(dataset_path),
        "labels": str(labels_path),
        "max_cases": max_cases,
        "judge_enabled": judge_enabled,
        "trigger_document_id": trigger_document_id,
        "trigger_collection": trigger_collection,
    }
    status = status_from_metrics(summary, errors if not results else None)
    if status == "passed" and summary["baseline_warnings"]:
        status = "warning"
    run = EvalRun(
        run_id=run_id,
        eval_suite="current_policy",
        status=status,
        started_at=started,
        finished_at=now_iso(),
        trigger=trigger,
        summary=summary,
        config=config,
        errors=errors,
    )
    run.artifacts = write_eval_artifacts(output_dir, run, results)
    if persist:
        _persist_with_settings(settings, run, results)
    return run, results


def _persist_with_settings(settings: Settings, run: EvalRun, results: List[EvalCaseResult]) -> None:
    from pymongo import MongoClient

    client = MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000)
    try:
        client.admin.command("ping")
        db = client[settings.mongodb_database]
        persist_eval_run_sync(db, run, results)
    finally:
        client.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="suite", required=True)

    cur = sub.add_parser("current", help="Run current policy production eval")
    cur.add_argument("--dataset", type=Path, default=DEFAULT_CURRENT_DATASET)
    cur.add_argument("--labels", type=Path, default=DEFAULT_CURRENT_LABELS)
    cur.add_argument("--max-cases", type=int, default=0)
    cur.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    cur.add_argument("--persist", action="store_true")
    cur.add_argument("--judge", action="store_true")
    cur.add_argument("--trigger", default="manual")
    cur.add_argument("--trigger-document-id", default=None)
    cur.add_argument("--trigger-collection", default=None)

    hist = sub.add_parser("historical", help="Run historical email behavior eval")
    hist.add_argument("--dataset", type=Path, default=DEFAULT_HISTORICAL_DATASET)
    hist.add_argument("--max-cases", type=int, default=50)
    hist.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    hist.add_argument("--persist", action="store_true")
    hist.add_argument("--judge", action="store_true")
    hist.add_argument("--trigger", default="manual")

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if args.suite == "current":
        run, _ = run_current_policy_eval(
            dataset_path=args.dataset,
            max_cases=args.max_cases,
            trigger=args.trigger,
            persist=args.persist,
            output_dir=args.output_dir,
            judge_enabled=args.judge,
            labels_path=args.labels,
            trigger_document_id=args.trigger_document_id,
            trigger_collection=args.trigger_collection,
        )
    else:
        run, _ = run_historical_eval(
            dataset_path=args.dataset,
            max_cases=args.max_cases,
            trigger=args.trigger,
            persist=args.persist,
            output_dir=args.output_dir,
            judge_enabled=args.judge,
        )
    print(json.dumps(run.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
