"""Rerun previously-hallucinated E2E queries through the *frontend* pipeline config.

The E2E evaluation script (``evaluate_e2e_pipeline.py``) intentionally diverges
from the production frontend pipeline so retrieved sources stay comparable to
``evidence_chunk_ids``. Its ``main()`` overrides are NOT production routing
defaults — it disables the agent path and Tavily/web fallback, forces
``reranker_score_threshold = -1.0`` and ``reranker_min_top_k = 7`` (production
defaults are ``0.0`` and ``3``), and patches the live reranker instance.

This runner answers a different question: *"If a real user asked these
hallucinated queries through the website right now, would the production
pipeline still hallucinate?"* It therefore rebuilds the runtime exactly the way
``api/main.py`` does for the frontend — plain ``Settings()`` with NO eval
overrides — so the agent path, ValidityFilter, reranker thresholds, HyDE, and
``top_k`` all match ``/chat/v3`` (mode=auto), the entrypoint the website hits.

Differences vs evaluate_e2e_pipeline.py (this script = frontend):
  - Agent path: ENABLED (production default) — eval disables it.
  - reranker_score_threshold: 0.0 (production) — eval forces -1.0.
  - reranker_min_top_k: 3 (production) — eval forces 7.
  - Web/Tavily fallback: production default (off unless configured) — eval forces off.
  - top_k: 7 (ChatRequest default = settings default).
  - No LLM cache, so we measure a fresh answer (not the old cached one).

Input  : evaluation/results/e2e_custom_eval/hallucinated_queries.csv (default)
Output : evaluation/results/e2e_custom_eval/rerun_frontend/<timestamp>/
           - rerun_results.csv   per-query before/after comparison
           - summary.json        aggregate recovery stats + run config

Usage (run from src/RAG_v2):
    python -m evaluation.rerun_hallucinated_frontend
    python -m evaluation.rerun_hallucinated_frontend --sample-n 5
    python -m evaluation.rerun_hallucinated_frontend \
        --input evaluation/results/e2e_custom_eval/hallucinated_queries.csv \
        --top-k 7
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Make project imports work when executed from any cwd (mirrors evaluate_e2e_pipeline).
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Reuse the E2E helpers so judging stays byte-for-byte aligned with the main eval.
from evaluation import evaluate_e2e_pipeline as e2e

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("rerun_hallucinated_frontend")

DEFAULT_INPUT = (
    PROJECT_ROOT
    / "evaluation"
    / "results"
    / "e2e_custom_eval"
    / "hallucinated_queries.csv"
)
DEFAULT_OUTPUT_DIR = (
    PROJECT_ROOT
    / "evaluation"
    / "results"
    / "e2e_custom_eval"
    / "rerun_frontend"
)
DATA_DIR = PROJECT_ROOT / "evaluation" / "data"


# ─── Input loading & evidence recovery ─────────────────────────────────────────


def _base_dataset_name(dataset_value: str) -> str:
    """Strip the ablation suffix the E2E runner appends to output folder names.

    e.g. ``kehoach_..._100__min_top_k_7_hyde`` → ``kehoach_..._100`` which maps
    back to ``evaluation/data/kehoach_..._100.json``.
    """
    name = (dataset_value or "").strip()
    return name.split("__", 1)[0] if "__" in name else name


def _load_evidence_lookup(dataset_values: List[str]) -> Dict[str, Dict[str, Any]]:
    """Map ``(base_dataset, question) → item`` from the original datasets.

    The hallucinated CSV does not carry ``evidence_chunk_ids``, so we re-join
    against ``evaluation/data/<dataset>.json`` to recover them for retrieval
    metrics. Missing dataset files are tolerated (metrics stay blank).
    """
    lookup: Dict[str, Dict[str, Any]] = {}
    bases = {_base_dataset_name(v) for v in dataset_values if v}
    for base in sorted(bases):
        path = DATA_DIR / f"{base}.json"
        if not path.exists():
            logger.warning(
                "Original dataset not found for %r (%s); retrieval metrics "
                "will be blank for its rows.",
                base,
                path.name,
            )
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("Failed to parse dataset %s; skipping.", path.name)
            continue
        for item in payload.get("items", []) or []:
            question = str(item.get("question") or "").strip()
            if question:
                lookup[f"{base}\u0000{question}"] = item
    logger.info("Loaded evidence lookup for %d dataset item(s).", len(lookup))
    return lookup


def _read_hallucinated_rows(input_path: Path) -> List[Dict[str, str]]:
    if not input_path.exists():
        logger.error("Input CSV not found at %s", input_path)
        sys.exit(1)
    # utf-8-sig handles the BOM written by the E2E exporter.
    with input_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        logger.error("No rows found in %s", input_path)
        sys.exit(1)
    return rows


# ─── Rerun loop ────────────────────────────────────────────────────────────────


def run_rerun(
    rows: List[Dict[str, str]],
    output_dir: Path,
    *,
    top_k: int,
    inter_question_sleep_s: float,
) -> Dict[str, Any]:
    # Build the SAME runtime the frontend uses: plain Settings(), agent enabled,
    # ValidityFilter on, production reranker thresholds. We deliberately do NOT
    # apply any of evaluate_e2e_pipeline.main()'s eval-only overrides.
    settings, pipeline, self_evaluator, judge_client = (
        e2e.build_evaluation_runtime()
    )
    judge_model = settings.chat_model
    cutoffs = [3, 5, 7]

    evidence_lookup = _load_evidence_lookup(
        [r.get("dataset", "") for r in rows]
    )

    logger.info(
        "Frontend-equivalent runtime: agent=%s, validity_filter=%s, "
        "reranker_score_threshold=%.2f, reranker_min_top_k=%s, hyde=%s, "
        "tavily_fallback=%s, top_k=%d",
        "enabled" if pipeline.agent is not None else "disabled",
        "enabled" if pipeline._validity_filter is not None else "disabled",
        getattr(pipeline._reranker, "score_threshold", float("nan"))
        if pipeline._reranker is not None
        else float("nan"),
        settings.reranker_min_top_k,
        "enabled" if settings.hyde_enabled else "disabled",
        "enabled" if settings.tavily_fallback_enabled else "disabled",
        top_k,
    )

    records: List[Dict[str, Any]] = []
    total = len(rows)
    logger.info("=== Re-running %d previously-hallucinated query(ies) ===", total)

    for idx, row in enumerate(rows, start=1):
        question = (row.get("question") or "").strip()
        if not question:
            logger.warning("[%d/%d] Skipping row with empty question.", idx, total)
            continue

        dataset = row.get("dataset", "")
        base = _base_dataset_name(dataset)
        gold_answer = (row.get("gold_answer") or "").strip()
        item = evidence_lookup.get(f"{base}\u0000{question}")
        relevant_ids = (
            e2e._as_list(item.get("evidence_chunk_ids", [])) if item else []
        )
        question_type = row.get("question_type", "")
        difficulty = row.get("difficulty", "")

        prev_faith = (row.get("self_eval_faithfulness") or "").strip()
        prev_ref = (row.get("ref_match") or "").strip()

        logger.info(
            "[%d/%d] %s | %r", idx, total, base, question[:60]
        )

        t0 = time.perf_counter()
        try:
            result = pipeline.query_v3(question, top_k=top_k)
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        except Exception as exc:
            logger.error("query_v3 crashed: %s", exc, exc_info=True)
            records.append(
                {
                    "dataset": dataset,
                    "question": question,
                    "question_type": question_type,
                    "difficulty": difficulty,
                    "gold_answer": gold_answer,
                    "generated_answer": f"ERROR: {exc}",
                    "prev_faithfulness": prev_faith,
                    "new_faithfulness": "error",
                    "faithfulness_changed": "",
                    "recovered": False,
                    "prev_ref_match": prev_ref,
                    "new_ref_match": "incorrect",
                    "mode": "error",
                    "route": "error",
                    "num_sources": 0,
                    "latency_ms": 0.0,
                    "retrieved_chunk_ids": "",
                    "relevant_chunk_ids": ",".join(relevant_ids),
                    "self_eval_relevance": "bad",
                    "self_eval_completeness": "incomplete",
                    "self_eval_reason": f"Pipeline crashed: {exc}",
                    "ref_match_reason": "Pipeline error",
                    "hyde_triggered": False,
                    **{f"hit@{k}": 0.0 for k in cutoffs},
                    **{f"recall@{k}": 0.0 for k in cutoffs},
                    **{f"ndcg@{k}": 0.0 for k in cutoffs},
                }
            )
            e2e._sleep_between_questions(idx, total, inter_question_sleep_s)
            continue

        generated_answer = result.get("answer") or ""
        sources = result.get("sources") or []
        pipeline_mode = result.get("mode") or "unknown"
        pipeline_route = result.get("route") or "unknown"
        num_sources = result.get("num_sources") or len(sources)
        timings = result.get("timings_ms") or {}

        retrieved_ids = [e2e._source_id(doc) for doc in sources if doc]
        retrieval_metrics = e2e.compute_all_metrics(
            retrieved_ids, relevant_ids, cutoffs
        )

        # Self-eval faithfulness (same SelfEvaluator + pipeline chat model).
        new_faith = "hallucinated"
        new_relevance = "bad"
        new_completeness = "incomplete"
        self_eval_reason = ""
        try:
            context_str = (
                e2e._format_context(sources)
                if sources
                else "(no context retrieved)"
            )
            eval_result = self_evaluator.evaluate(
                query=question,
                context=context_str,
                response=generated_answer,
            )
            new_faith = eval_result.get("faithfulness", "hallucinated")
            new_relevance = eval_result.get("relevance", "bad")
            new_completeness = eval_result.get("completeness", "incomplete")
            self_eval_reason = eval_result.get("reason", "")
        except Exception as exc:
            logger.warning("Self-evaluation failed: %s", exc)
            self_eval_reason = f"Self-eval crashed: {exc}"

        # Reference comparison (LLM judge), same as E2E eval.
        new_ref = "incorrect"
        ref_reason = ""
        if gold_answer:
            ref_result = e2e._compare_with_reference(
                client=judge_client,
                model=judge_model,
                question=question,
                reference=gold_answer,
                generated=generated_answer,
            )
            new_ref = ref_result.get("match", "incorrect")
            ref_reason = ref_result.get("reason", "")

        recovered = new_faith == "grounded"
        records.append(
            {
                "dataset": dataset,
                "question": question,
                "question_type": question_type,
                "difficulty": difficulty,
                "gold_answer": gold_answer,
                "generated_answer": generated_answer,
                "prev_faithfulness": prev_faith,
                "new_faithfulness": new_faith,
                "faithfulness_changed": (
                    "yes" if prev_faith and new_faith != prev_faith else "no"
                ),
                "recovered": recovered,
                "prev_ref_match": prev_ref,
                "new_ref_match": new_ref,
                "mode": pipeline_mode,
                "route": pipeline_route,
                "num_sources": num_sources,
                "latency_ms": round(
                    float(timings.get("pipeline_total", latency_ms)), 2
                ),
                "retrieved_chunk_ids": ",".join(retrieved_ids),
                "relevant_chunk_ids": ",".join(relevant_ids),
                "self_eval_relevance": new_relevance,
                "self_eval_completeness": new_completeness,
                "self_eval_reason": self_eval_reason,
                "ref_match_reason": ref_reason,
                "hyde_triggered": bool(timings.get("hyde_triggered", 0.0) > 0.0),
                **{k: v for k, v in retrieval_metrics.items() if "@" in k and (
                    k.startswith("hit") or k.startswith("recall") or k.startswith("ndcg")
                )},
            }
        )

        logger.info(
            "  ↳ Mode: %s | Route: %s | %s → %s%s | Ref: %s → %s | %.0fms",
            pipeline_mode,
            pipeline_route,
            prev_faith or "?",
            new_faith,
            " [RECOVERED]" if recovered else "",
            prev_ref or "?",
            new_ref,
            records[-1]["latency_ms"],
        )
        e2e._sleep_between_questions(idx, total, inter_question_sleep_s)

    summary = _build_summary(records, top_k=top_k, settings=settings, pipeline=pipeline)
    _save_outputs(records, summary, output_dir)
    return summary


def _build_summary(
    records: List[Dict[str, Any]],
    *,
    top_k: int,
    settings: Any,
    pipeline: Any,
) -> Dict[str, Any]:
    total = len(records)
    if total == 0:
        return {"total": 0}

    grounded = sum(1 for r in records if r["new_faithfulness"] == "grounded")
    partial = sum(
        1 for r in records if r["new_faithfulness"] == "partially_grounded"
    )
    still_halluc = sum(
        1 for r in records if r["new_faithfulness"] == "hallucinated"
    )
    errors = sum(1 for r in records if r["new_faithfulness"] == "error")
    ref_correct = sum(1 for r in records if r["new_ref_match"] == "correct")
    ref_partial = sum(1 for r in records if r["new_ref_match"] == "partial")

    return {
        "total": total,
        "input_all_hallucinated": True,
        "recovered_grounded": grounded,
        "recovered_grounded_rate": round(grounded / total, 4),
        "now_partially_grounded": partial,
        "still_hallucinated": still_halluc,
        "still_hallucinated_rate": round(still_halluc / total, 4),
        "errors": errors,
        "now_ref_correct": ref_correct,
        "now_ref_partial": ref_partial,
        "avg_latency_ms": round(
            sum(float(r["latency_ms"]) for r in records) / total, 1
        ),
        "run_config": {
            "pipeline": "frontend (api/main.py equivalent, query_v3 mode=auto)",
            "top_k": top_k,
            "agent_enabled": pipeline.agent is not None,
            "validity_filter_enabled": pipeline._validity_filter is not None,
            "reranker_score_threshold": getattr(
                pipeline._reranker, "score_threshold", None
            ),
            "reranker_table_score_threshold": getattr(
                pipeline._reranker, "table_score_threshold", None
            ),
            "reranker_min_top_k": settings.reranker_min_top_k,
            "hyde_enabled": settings.hyde_enabled,
            "tavily_fallback_enabled": settings.tavily_fallback_enabled,
            "web_fallback_on_no_info": settings.web_fallback_on_no_info,
            "web_fallback_on_dynamic": settings.web_fallback_on_dynamic,
            "llm_cache": False,
        },
    }


def _save_outputs(
    records: List[Dict[str, Any]],
    summary: Dict[str, Any],
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    csv_path = output_dir / "rerun_results.csv"
    if records:
        keys = list(records[0].keys())
        with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=keys)
            writer.writeheader()
            writer.writerows(records)
    logger.info("Wrote rerun results CSV → %s", csv_path)

    json_path = output_dir / "summary.json"
    json_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info("Wrote summary JSON → %s", json_path)

    if summary.get("total"):
        print("\n" + "=" * 70)
        print(" RERUN OF HALLUCINATED QUERIES — FRONTEND PIPELINE CONFIG")
        print("=" * 70)
        print(f"Total re-run:                 {summary['total']}")
        print(
            f"Recovered → Grounded:         {summary['recovered_grounded']} "
            f"({summary['recovered_grounded_rate'] * 100:.1f}%)"
        )
        print(f"Now Partially Grounded:       {summary['now_partially_grounded']}")
        print(
            f"Still Hallucinated:           {summary['still_hallucinated']} "
            f"({summary['still_hallucinated_rate'] * 100:.1f}%)"
        )
        print(f"Errors:                       {summary['errors']}")
        print(f"Now Ref-Match Correct:        {summary['now_ref_correct']}")
        print(f"Avg Latency:                  {summary['avg_latency_ms']} ms")
        print("=" * 70 + "\n")


# ─── Entry point ────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Re-run previously-hallucinated E2E queries through the production "
            "frontend pipeline config (query_v3, agent enabled, no eval overrides)."
        )
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help="CSV of hallucinated queries (default: hallucinated_queries.csv).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for rerun outputs (a timestamped subdir is created).",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=7,
        help="top_k passed to query_v3 (frontend ChatRequest default is 7).",
    )
    parser.add_argument(
        "--sample-n",
        type=int,
        default=None,
        help="Only re-run the first N rows (useful for smoke tests).",
    )
    parser.add_argument(
        "--no-timestamp",
        action="store_true",
        help="Write directly into --output-dir instead of a timestamped subdir.",
    )
    parser.add_argument(
        "--llm-rpm",
        type=float,
        default=e2e.DEFAULT_LLM_RPM,
        help="LLM requests-per-minute limit used to compute inter-question sleep.",
    )
    parser.add_argument(
        "--llm-calls-per-question",
        type=float,
        default=e2e.DEFAULT_LLM_CALLS_PER_QUESTION,
        help="Estimated LLM calls per evaluated question.",
    )
    parser.add_argument(
        "--rate-limit-buffer-s",
        type=float,
        default=e2e.DEFAULT_RATE_LIMIT_BUFFER_S,
        help="Extra seconds added to the computed inter-question sleep.",
    )
    parser.add_argument(
        "--inter-question-sleep-s",
        type=float,
        default=None,
        help="Override the computed inter-question sleep (seconds).",
    )
    args = parser.parse_args()

    rows = _read_hallucinated_rows(args.input)
    if args.sample_n is not None:
        rows = rows[: args.sample_n]
        logger.info("Limiting rerun to first %d row(s).", args.sample_n)

    inter_question_sleep_s = (
        args.inter_question_sleep_s
        if args.inter_question_sleep_s is not None
        else e2e._compute_inter_question_sleep_s(
            args.llm_rpm,
            args.llm_calls_per_question,
            args.rate_limit_buffer_s,
        )
    )

    output_dir = args.output_dir
    if not args.no_timestamp:
        output_dir = output_dir / datetime.now().strftime("%Y%m%d_%H%M%S")

    logger.info("Reading %d hallucinated row(s) from %s", len(rows), args.input)
    run_rerun(
        rows,
        output_dir,
        top_k=args.top_k,
        inter_question_sleep_s=inter_question_sleep_s,
    )


if __name__ == "__main__":
    main()
