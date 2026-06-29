"""Rejudge evaluation results with faithful context reconstruction.

Re-evaluates rows with errors (crashes, parse errors) in existing CSV results
WITHOUT re-running the pipeline (keeps generated_answer and retrieval metrics).

For self-eval metrics (relevance, faithfulness, completeness), the script:
  1. Uses ``retrieved_chunk_ids`` to fetch original chunks from Qdrant by ID.
  2. Applies parent context expansion (via ``ParentContextExpander``) exactly
     like the production pipeline does post-rerank.
  3. Formats context with ``_format_context`` (with parent context prepended).
  4. Re-runs ``SelfEvaluator.evaluate(question, context, answer)``.

For correctness (ref_match), the script re-runs the LLM-as-judge comparison
against gold_answer.

This ensures the rejudging uses the SAME context enrichment pipeline as
production, so the evaluation is fair and consistent.

Usage (within .venv at RAG_v2):

    # Rejudge a single result directory (e.g. result_dual_RRF)
    python -m evaluation.rejudge_with_context \
        --input-dir evaluation/result_dual_RRF \
        --judge-provider gemini \
        --inter-question-sleep-s 4.5

    # Rejudge with a specific judge model
    python -m evaluation.rejudge_with_context \
        --input-dir evaluation/result_dual_RRF \
        --judge-provider deepseek \
        --judge-model deepseek-chat

    # Dry run: list errors without re-evaluating
    python -m evaluation.rejudge_with_context \
        --input-dir evaluation/result_dual_RRF \
        --dry-run
"""

from __future__ import annotations

import argparse
import copy
import csv
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from config.settings import Settings
from evaluation.evaluate import (
    _build_judge_client,
    _compare_with_reference,
    _empty_self_eval,
    aggregate,
    save_outputs,
)
from llm import create_llm
from llm.self_eval import SelfEvaluator
from pipeline.flows import _format_context
from retrieval.parent_context import ParentContextExpander
from retrieval.qdrant_store import QdrantStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("evaluation.rejudge_with_context")


# ─── Error detection ────────────────────────────────────────────────────────


def _is_error_row(record: Dict[str, Any]) -> Tuple[bool, str]:
    """Detect whether a CSV row needs rejudging.

    Returns (needs_rejudge, reason_category).
    """
    ref_reason = str(record.get("ref_match_reason", "")).lower()
    eval_reason = str(record.get("self_eval_reason", "")).lower()
    answer = str(record.get("generated_answer", ""))

    if answer.startswith("ERROR"):
        return True, "pipeline_crash"
    if "crashed" in eval_reason or "judge call error" in eval_reason:
        return True, "eval_crash"
    if "judge call error" in ref_reason:
        return True, "ref_judge_error"
    if "parse error" in ref_reason:
        return True, "ref_parse_error"

    return False, "ok"


# ─── Qdrant chunk lookup (multi-collection) ─────────────────────────────────


def _build_qdrant_stores(settings: Settings) -> Dict[str, QdrantStore]:
    """Create a QdrantStore for each configured collection."""
    stores: Dict[str, QdrantStore] = {}
    for coll in settings.collections:
        stores[coll] = QdrantStore(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
            collection_name=coll,
        )
    return stores


def _fetch_chunks_by_ids(
    chunk_ids: List[str],
    stores: Dict[str, QdrantStore],
) -> List[Dict[str, Any]]:
    """Fetch chunk data from Qdrant by ID, searching across all collections.

    Returns list of dicts: ``{"id", "text", "metadata", "collection"}``
    in the same order as the input IDs. Missing IDs are skipped.
    """
    if not chunk_ids:
        return []

    # Deduplicate while preserving order
    seen: Set[str] = set()
    unique_ids: List[str] = []
    for cid in chunk_ids:
        if cid and cid not in seen:
            seen.add(cid)
            unique_ids.append(cid)

    found: Dict[str, Dict[str, Any]] = {}

    for coll_name, store in stores.items():
        remaining = [cid for cid in unique_ids if cid not in found]
        if not remaining:
            break

        try:
            points = store.get_by_ids(remaining)
            for point in points:
                pid = point["id"]
                point["collection"] = coll_name
                found[pid] = point
        except Exception as exc:
            logger.warning(
                "Failed to fetch IDs from collection '%s': %s",
                coll_name,
                exc,
            )

    # Return in original order
    result = [found[cid] for cid in unique_ids if cid in found]
    if len(result) < len(unique_ids):
        missing = [cid for cid in unique_ids if cid not in found]
        logger.warning(
            "Could not find %d/%d chunk IDs in any collection: %s",
            len(missing),
            len(unique_ids),
            missing[:5],
        )

    return result


# ─── Parent context expansion (faithful to production) ───────────────────────


def _expand_parent_context(
    chunks: List[Dict[str, Any]],
    settings: Settings,
) -> List[Dict[str, Any]]:
    """Apply parent context expansion to fetched chunks.

    Groups chunks by collection and expands each group, exactly
    like ``_expand_parent_context_post_rerank`` does in production.
    """
    if not chunks:
        return chunks

    # Quick check: any child with parent_id?
    has_parent = any(
        c.get("metadata", {}).get("parent_id")
        and str(c.get("metadata", {}).get("level", "child")).strip().lower()
        == "child"
        for c in chunks
    )
    if not has_parent:
        return chunks

    try:
        expander = ParentContextExpander(
            qdrant_host=settings.qdrant_host,
            qdrant_port=settings.qdrant_port,
            max_parent_chars=settings.parent_max_chars,
        )

        # Group by collection
        collection_groups: Dict[str, List[int]] = {}
        for idx, chunk in enumerate(chunks):
            coll = chunk.get("collection", "") or chunk.get("metadata", {}).get(
                "collection", ""
            )
            if coll:
                collection_groups.setdefault(coll, []).append(idx)

        for coll, indices in collection_groups.items():
            group = [chunks[i] for i in indices]
            expanded = expander.expand_with_parents(group, coll)
            for i, exp in zip(indices, expanded):
                chunks[i] = exp

    except Exception:
        logger.warning(
            "Parent context expansion failed, continuing without parent",
            exc_info=True,
        )

    return chunks


# ─── Build context string (faithful to production _format_context) ───────────


def _build_context_from_chunk_ids(
    chunk_ids_str: str,
    stores: Dict[str, QdrantStore],
    settings: Settings,
) -> Tuple[str, List[Dict[str, Any]]]:
    """Reconstruct the context string from retrieved_chunk_ids.

    Returns (context_string, sources_list).
    """
    chunk_ids = [
        cid.strip()
        for cid in chunk_ids_str.split(",")
        if cid.strip()
    ]

    if not chunk_ids:
        return "(no context retrieved)", []

    # Fetch chunks from Qdrant
    sources = _fetch_chunks_by_ids(chunk_ids, stores)

    if not sources:
        return "(no context retrieved)", []

    # Apply parent context expansion (exactly like production)
    sources = _expand_parent_context(sources, settings)

    # Format context (exactly like production _format_context)
    context = _format_context(sources)

    return context, sources


# ─── Core rejudge logic ─────────────────────────────────────────────────────


def _rejudge_record(
    record: Dict[str, Any],
    error_category: str,
    stores: Dict[str, QdrantStore],
    settings: Settings,
    self_evaluator: SelfEvaluator,
    judge_client: Any,
    judge_model: str,
) -> Dict[str, Any]:
    """Re-evaluate a single errored record without re-running the pipeline."""
    updated = dict(record)
    question = record.get("question", "")
    answer = record.get("generated_answer", "")
    gold_answer = record.get("gold_answer", "")

    # For pipeline crashes, answer itself is "ERROR: ..." — cannot evaluate
    if answer.startswith("ERROR"):
        logger.info("  → Skipping self-eval (answer is ERROR)")
        updated.update(_empty_self_eval("Pipeline crash — no valid answer"))
        # Still try ref_match since we have gold_answer
        if gold_answer:
            ref = _compare_with_reference(
                judge_client, judge_model, question, gold_answer, answer
            )
            updated["ref_match"] = ref.get("match", "incorrect")
            updated["ref_match_reason"] = ref.get("reason", "")
        return updated

    # Rebuild context from retrieved_chunk_ids for self-eval
    retrieved_ids_str = record.get("retrieved_chunk_ids", "")
    context, sources = _build_context_from_chunk_ids(
        retrieved_ids_str, stores, settings
    )

    # Re-run self-evaluation (relevance, faithfulness, completeness)
    if error_category in ("eval_crash", "pipeline_crash"):
        try:
            eval_result = self_evaluator.evaluate(
                query=question,
                context=context,
                response=answer,
            )
            updated["self_eval_pass"] = eval_result.get("pass", False)
            updated["self_eval_relevance"] = eval_result.get("relevance", "bad")
            updated["self_eval_faithfulness"] = eval_result.get(
                "faithfulness", "hallucinated"
            )
            updated["self_eval_completeness"] = eval_result.get(
                "completeness", "incomplete"
            )
            updated["self_eval_reason"] = eval_result.get("reason", "")
        except Exception as exc:
            logger.warning("Self-eval failed during rejudge: %s", exc)
            updated.update(_empty_self_eval(f"Rejudge self-eval error: {exc}"))

    # Re-run correctness judge (ref_match)
    if error_category in ("ref_judge_error", "ref_parse_error", "eval_crash", "pipeline_crash"):
        if gold_answer:
            ref = _compare_with_reference(
                judge_client, judge_model, question, gold_answer, answer
            )
            updated["ref_match"] = ref.get("match", "incorrect")
            updated["ref_match_reason"] = ref.get("reason", "")
        else:
            updated["ref_match"] = "n/a"
            updated["ref_match_reason"] = "No gold_answer provided."

    return updated


# ─── Cast CSV string values back to proper types ────────────────────────────


def _cast_record_types(record: Dict[str, Any]) -> None:
    """Fix types for numeric fields read from CSV as strings."""
    try:
        record["latency_ms"] = float(record.get("latency_ms", 0.0))
    except (ValueError, TypeError):
        record["latency_ms"] = 0.0

    for key in record:
        if "@" in key:
            try:
                record[key] = float(record[key])
            except (ValueError, TypeError):
                pass

    # Boolean fields
    for bool_key in ("self_eval_pass",):
        val = record.get(bool_key)
        if isinstance(val, str):
            record[bool_key] = val.lower() in ("true", "1", "yes")


# ─── Main runner ─────────────────────────────────────────────────────────────


def run_rejudge(
    input_dir: Path,
    judge_provider: str,
    judge_model: Optional[str],
    inter_question_sleep_s: float,
    dry_run: bool,
) -> None:
    """Rejudge all error rows in result CSVs under ``input_dir``."""

    # Build settings and judge
    settings = Settings()

    if judge_provider:
        settings.llm_provider = judge_provider
    if judge_model:
        settings.chat_model = judge_model
    elif judge_provider == "deepseek":
        settings.chat_model = "deepseek-v4-flash"
    elif judge_provider == "gemini":
        settings.chat_model = "gemini-3.1-flash-lite"
    elif judge_provider == "openai":
        settings.chat_model = "gpt-4o-mini"
    elif judge_provider == "lm_studio":
        settings.chat_model = "local-model"

    model_name = settings.chat_model
    logger.info(
        "Judge: provider=%s, model=%s",
        settings.llm_provider,
        model_name,
    )

    if not dry_run:
        # Build self-evaluator (uses the configured LLM)
        judge_llm = create_llm(settings)
        self_evaluator = SelfEvaluator(llm=judge_llm)
        judge_client = _build_judge_client(settings)

        # Build Qdrant stores for chunk lookup
        qdrant_stores = _build_qdrant_stores(settings)
        logger.info(
            "Connected to Qdrant collections: %s",
            list(qdrant_stores.keys()),
        )
    else:
        self_evaluator = None  # type: ignore[assignment]
        judge_client = None
        qdrant_stores = {}

    # Find CSVs to process
    csv_files: List[Path] = []
    if (input_dir / "query_results.csv").exists():
        csv_files = [input_dir / "query_results.csv"]
    else:
        csv_files = sorted(input_dir.glob("*/query_results.csv"))

    if not csv_files:
        logger.error("No query_results.csv found in %s", input_dir)
        return

    logger.info("Found %d dataset(s) to inspect.", len(csv_files))

    total_rejudged = 0
    total_skipped = 0

    for csv_file in csv_files:
        dataset_name = csv_file.parent.name
        logger.info("=== Inspecting %s ===", dataset_name)

        # Read records
        records: List[Dict[str, Any]] = []
        with csv_file.open("r", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                records.append(row)

        # Identify error rows
        error_indices: List[Tuple[int, str]] = []
        for idx, record in enumerate(records):
            is_err, category = _is_error_row(record)
            if is_err:
                error_indices.append((idx, category))

        if not error_indices:
            logger.info("  No errors found — skipping.")
            continue

        logger.info(
            "  Found %d error(s) out of %d rows.",
            len(error_indices),
            len(records),
        )

        if dry_run:
            for idx, category in error_indices:
                rec = records[idx]
                logger.info(
                    "  [DRY] #%d id=%s category=%s question=%s",
                    idx + 1,
                    rec.get("id", "?"),
                    category,
                    str(rec.get("question", ""))[:60],
                )
            continue

        # Rejudge each error row
        for seq, (idx, category) in enumerate(error_indices, start=1):
            rec = records[idx]
            logger.info(
                "  [%d/%d] Rejudging id=%s (%s): %s",
                seq,
                len(error_indices),
                rec.get("id", "?"),
                category,
                str(rec.get("question", ""))[:60],
            )

            updated = _rejudge_record(
                record=rec,
                error_category=category,
                stores=qdrant_stores,
                settings=settings,
                self_evaluator=self_evaluator,
                judge_client=judge_client,
                judge_model=model_name,
            )
            records[idx] = updated
            total_rejudged += 1

            logger.info(
                "    → faith=%s, relevance=%s, ref_match=%s",
                updated.get("self_eval_faithfulness", "?"),
                updated.get("self_eval_relevance", "?"),
                updated.get("ref_match", "?"),
            )

            if inter_question_sleep_s > 0 and seq < len(error_indices):
                time.sleep(inter_question_sleep_s)

        # Cast types and re-aggregate
        for record in records:
            _cast_record_types(record)

        summary = aggregate(records)
        summary["dataset"] = dataset_name

        # Save (overwrites the original CSV, summary, and report)
        save_outputs(records, summary, csv_file.parent)
        logger.info("  ✓ Updated %s (%d rejudged)", dataset_name, len(error_indices))

    logger.info(
        "\nDone. Rejudged %d rows total, %d skipped.",
        total_rejudged,
        total_skipped,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Rejudge error rows in evaluation CSVs with faithful "
            "parent-context reconstruction from Qdrant."
        ),
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        required=True,
        help=(
            "Directory containing dataset subdirs with query_results.csv "
            "(e.g. evaluation/result_dual_RRF)."
        ),
    )
    parser.add_argument(
        "--judge-provider",
        type=str,
        default="gemini",
        help="LLM provider for the judge (e.g., gemini, deepseek).",
    )
    parser.add_argument(
        "--judge-model",
        type=str,
        default=None,
        help="Chat model for the judge (overrides provider default).",
    )
    parser.add_argument(
        "--inter-question-sleep-s",
        type=float,
        default=4.5,
        help="Seconds to sleep between questions (rate limit protection).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only list errors without re-evaluating.",
    )
    args = parser.parse_args()

    run_rejudge(
        input_dir=args.input_dir,
        judge_provider=args.judge_provider,
        judge_model=args.judge_model,
        inter_question_sleep_s=args.inter_question_sleep_s,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
