"""End-to-End (E2E) RAG Pipeline Evaluation Script

Evaluates the complete production RAG pipeline (routing, query reflection, subquery decomposition,
hybrid search, validity filters, reranking, HyDE fallback, parent expansion, and generation)
measuring both E2E retrieval quality and E2E generation quality.

Metrics:
- E2E Retrieval: Hit@K, Recall@K, Precision@K, MRR@K, NDCG@K for K in [3, 5, 7]
- E2E Generation: Faithfulness (Groundedness), Answer Relevance, Correctness (Match against Gold), Hallucination Rate
- Performance: Timing breakdowns (Routing, Search, Rerank, Generation, Self-Eval, HyDE) and Fallback tracking

Usage:
    # Run all datasets in evaluation/data folder
    python evaluation/evaluate_e2e_pipeline.py

    # Run a single dataset file
    python evaluation/evaluate_e2e_pipeline.py --dataset evaluation/data/ITE6_rag_evaluation_dataset_no_parent_evidence.json
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import math
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from openai import OpenAI

# Set up logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("evaluate_e2e_pipeline")

DEFAULT_LLM_RPM = 15.0
DEFAULT_LLM_CALLS_PER_QUESTION = 4.0
DEFAULT_RATE_LIMIT_BUFFER_S = 2.0

# ─── Ablation Study Config ─────────────────────────────────────────────────────
# Toggle individual pipeline components ON/OFF to isolate which cause the
# metric gap between E2E and raw (classifier) retrieval evaluation.
#
# Differences vs evaluate_retrieval_custom.py:
#   1. ComplexityRouter  — E2E classifies simple/complex before retrieval;
#                          classifier only uses CollectionSelector.
#   2. QueryReflector    — E2E rewrites the query with an LLM;
#                          classifier uses the raw question as-is.
#   3. Parent expansion  — NOTE: _expand_parent_context_post_rerank() does
#                          NOT insert new parent chunks into the ranked list.
#                          It only enriches each child chunk's metadata with
#                          parent_context text (for LLM context quality).
#                          List length and order are UNCHANGED, so this has
#                          NO effect on hit@K metrics.  The ablation flag
#                          below is kept for completeness but will not affect
#                          retrieval scores.
#   4. Reranker min_top_k — classifier always calls rerank(min_top_k=top_k)
#                          so it returns ≥ top_k results; E2E never passes
#                          min_top_k and can return fewer.
#   5. top_k mismatch    — E2E default is --top-k 7; classifier uses top_k=5.
#                          A larger reranker pool means more candidates compete,
#                          so relevant chunks can fall to rank 6-7 instead of 5.
#                          E.g. multi_001: a3b83b7b at rank 5 (classifier, k=5)
#                          vs rank 7 (E2E, k=7 + pool expansion to 12 chunks).
#
# Set a flag to True to DISABLE that component (isolate its contribution).
ABLATION_DISABLE_COMPLEXITY_ROUTER: bool = (
    False  # Force all queries → simple path
)
ABLATION_DISABLE_REFLECTION: bool = False  # Use raw query; skip QueryReflector
ABLATION_DISABLE_PARENT_EXPANSION: bool = (
    False  # No-op for hit@K: parent expansion only enriches metadata, does not reorder
)
ABLATION_FORCE_RERANKER_MIN_TOP_K: bool = (
    False  # Legacy hidden toggle; prefer --reranker-min-top-k.
)
ABLATION_FORCE_TOP_K_5: bool = (
    False  # Legacy hidden toggle; prefer --force-top-k-5.
)
# ───────────────────────────────────────────────────────────────────────────────

# Make project imports work when executed from any cwd
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from config.settings import Settings
from llm import create_llm
from llm.self_eval import SelfEvaluator
from pipeline.flows import _format_context
from pipeline.rag_pipeline import RAGPipeline

# ─── Helper Functions for Matching & Metrics ───────────────────────────────────


def _raw_id(value: Any) -> str:
    text = str(value or "").strip()
    return text.split("/", 1)[-1] if "/" in text else text


def _source_id(doc: Dict[str, Any]) -> str:
    """Return the stable evidence id used by dataset ``evidence_chunk_ids``."""
    metadata = (
        doc.get("metadata") if isinstance(doc.get("metadata"), dict) else {}
    )
    candidates = (
        doc.get("id"),
        doc.get("chunk_id"),
        doc.get("source_id"),
        metadata.get("chunk_id"),
        metadata.get("id"),
        metadata.get("doc_id"),
        metadata.get("document_id"),
    )
    for value in candidates:
        normalized = _raw_id(value)
        if normalized:
            return normalized
    return ""


def _as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [
            part.strip()
            for part in value.replace(";", ",").split(",")
            if part.strip()
        ]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def compute_metrics_for_k(
    retrieved_ids: List[str], relevant_ids: List[str], k: int
) -> Dict[str, float]:
    """Calculate evaluation metrics for a specific K cutoff."""
    retrieved_raw = [_raw_id(rid) for rid in retrieved_ids if rid]
    relevant_set = {_raw_id(rid) for rid in relevant_ids if rid}

    topk = retrieved_raw[:k]

    if not relevant_set:
        return {
            f"hit@{k}": 0.0,
            f"precision@{k}": 0.0,
            f"recall@{k}": 0.0,
            f"mrr@{k}": 0.0,
            f"ndcg@{k}": 0.0,
        }

    hits = [doc_id for doc_id in topk if doc_id in relevant_set]
    hit = 1.0 if hits else 0.0
    precision = len(set(hits)) / k if k > 0 else 0.0
    recall = len(set(hits)) / len(relevant_set)

    mrr = 0.0
    for rank, doc_id in enumerate(topk, start=1):
        if doc_id in relevant_set:
            mrr = 1.0 / rank
            break

    dcg = sum(
        1.0 / math.log2(rank + 1)
        for rank, doc_id in enumerate(topk, start=1)
        if doc_id in relevant_set
    )
    ideal_hits = min(len(relevant_set), k)
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
    ndcg = dcg / idcg if idcg else 0.0

    return {
        f"hit@{k}": round(hit, 4),
        f"precision@{k}": round(precision, 4),
        f"recall@{k}": round(recall, 4),
        f"mrr@{k}": round(mrr, 4),
        f"ndcg@{k}": round(ndcg, 4),
    }


def compute_all_metrics(
    retrieved_ids: List[str], relevant_ids: List[str], cutoffs: List[int]
) -> Dict[str, float]:
    metrics = {}
    for k in cutoffs:
        metrics.update(compute_metrics_for_k(retrieved_ids, relevant_ids, k))
    return metrics


def _safe_output_name(path: Path) -> str:
    """Create a filesystem-safe output folder name from a dataset filename."""
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", path.stem).strip("._-")
    return name or "dataset"


def _compute_inter_question_sleep_s(
    llm_rpm: float,
    llm_calls_per_question: float,
    buffer_s: float = DEFAULT_RATE_LIMIT_BUFFER_S,
) -> float:
    """Return seconds to sleep after each question to stay under an LLM RPM cap."""
    if llm_rpm <= 0 or llm_calls_per_question <= 0:
        return 0.0
    return round(
        (60.0 * llm_calls_per_question / llm_rpm) + max(buffer_s, 0.0), 2
    )


def _sleep_between_questions(
    current_idx: int,
    total_queries: int,
    sleep_s: float,
    *,
    sleep_after_last: bool = False,
) -> None:
    """Sleep between evaluation questions when another question is still pending."""
    if sleep_s <= 0:
        return
    if current_idx >= total_queries and not sleep_after_last:
        return
    logger.info(
        "Sleeping %.2fs before next question to respect LLM RPM limit.", sleep_s
    )
    time.sleep(sleep_s)


# ─── Dataset Loading ────────────────────────────────────────────────────────────


def load_dataset(dataset_path: Path) -> List[Dict[str, Any]]:
    if not dataset_path.exists():
        logger.error("Dataset file not found at %s", dataset_path)
        sys.exit(1)

    try:
        payload = json.loads(dataset_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or "items" not in payload:
            logger.error(
                "Invalid dataset format. Must contain an 'items' array."
            )
            sys.exit(1)
        return payload["items"]
    except Exception as exc:
        logger.exception("Failed to read dataset JSON from %s", dataset_path)
        sys.exit(1)


def resolve_dataset_paths(dataset_path: Path) -> List[Path]:
    """Return one or more dataset JSON files from a file or directory path."""
    if dataset_path.is_dir():
        paths = sorted(dataset_path.glob("*.json"))
        if not paths:
            logger.error("No JSON dataset files found in %s", dataset_path)
            sys.exit(1)
        return paths
    return [dataset_path]


# ─── Reference Comparison Judge (LLM-as-a-Judge) ───────────────────────────────

_REF_COMPARE_SYSTEM = """\
You are a strict evaluator comparing two Vietnamese-language answers to the same question.

Your task: decide whether the **Generated Answer** conveys the same correct
information as the **Reference Answer**.

Return a single JSON object with exactly these keys:
{
  "match": "correct" | "partial" | "incorrect",
  "reason": "<one sentence explaining the verdict>"
}

Definitions:
- "correct"   — the generated answer conveys all key facts from the reference answer
                 and adds no incorrect information.
- "partial"   — the generated answer captures some but not all key facts, or adds
                 minor inaccuracies.
- "incorrect" — the generated answer is missing most key facts or contains
                 significant inaccuracies.

Rules:
- Minor wording differences are acceptable (consider them "correct").
- Do NOT include any text outside the JSON object.
- Respond only in the JSON format specified above."""

_REF_COMPARE_USER = """\
### Question:
{question}

### Reference Answer:
{reference}

### Generated Answer:
{generated}

Compare the two answers:"""


def _build_judge_client(settings: Settings) -> OpenAI:
    """Build OpenAI-compatible client for reference comparisons using configured provider."""
    provider = settings.llm_provider
    if provider == "gemini":
        base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
        api_key = settings.google_api_key or os.environ.get(
            "GOOGLE_API_KEY", ""
        )
    elif provider == "lm_studio":
        base_url = settings.lm_studio_base_url
        api_key = "lm-studio"
    elif provider == "ollama":
        base_url = settings.ollama_base_url
        if not base_url.endswith("/v1"):
            base_url = f"{base_url}/v1"
        api_key = "ollama"
    elif provider == "openai":
        base_url = "https://api.openai.com/v1"
        api_key = settings.openai_api_key or os.environ.get(
            "OPENAI_API_KEY", ""
        )
    else:
        base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
        api_key = settings.google_api_key or os.environ.get(
            "GOOGLE_API_KEY", ""
        )

    if not api_key:
        raise EnvironmentError(
            f"API Key for LLM provider {provider!r} is not set in environment or .env file."
        )
    return OpenAI(api_key=api_key, base_url=base_url)


def _compare_with_reference(
    client: OpenAI,
    model: str,
    question: str,
    reference: str,
    generated: str,
) -> Dict[str, str]:
    """Ask the judge LLM to compare generated vs reference answer."""
    user_msg = _REF_COMPARE_USER.format(
        question=question, reference=reference, generated=generated
    )
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _REF_COMPARE_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.0,
            max_tokens=256,
        )
        raw = resp.choices[0].message.content.strip()
        return _parse_json_response(raw, fallback_match="incorrect")
    except Exception as exc:
        logger.warning("Reference comparison LLM call failed: %s", exc)
        return {"match": "incorrect", "reason": f"Judge call error: {exc}"}


def _parse_json_response(
    raw: str, fallback_match: str = "incorrect"
) -> Dict[str, str]:
    """Parse a JSON response, stripping optional markdown fences."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        cleaned = "\n".join(lines[1:end]).strip()
    try:
        data = json.loads(cleaned)
        return {
            "match": data.get("match", fallback_match),
            "reason": data.get("reason", ""),
        }
    except (json.JSONDecodeError, AttributeError):
        logger.warning("Failed to parse judge JSON: %r", raw[:200])
        return {"match": fallback_match, "reason": f"Parse error: {raw[:100]}"}


# ─── Evaluation Setup & Loop ──────────────────────────────────────────────────


def build_evaluation_runtime() -> (
    Tuple[Settings, RAGPipeline, SelfEvaluator, OpenAI]
):
    settings = Settings()

    logger.info("Initializing RAGPipeline (which builds RetrievalService) ...")
    pipeline = RAGPipeline(settings=settings)

    logger.info("Initializing SelfEvaluator ...")
    self_evaluator = SelfEvaluator(llm=pipeline._chat)

    logger.info("Initializing Reference comparison LLM client ...")
    judge_client = _build_judge_client(settings)

    return settings, pipeline, self_evaluator, judge_client


def run_evaluation(
    dataset_items: List[Dict[str, Any]],
    output_dir: Path,
    dataset_name: Optional[str] = None,
    settings: Optional[Settings] = None,
    pipeline: Optional[RAGPipeline] = None,
    self_evaluator: Optional[SelfEvaluator] = None,
    judge_client: Optional[OpenAI] = None,
    run_config: Optional[Dict[str, Any]] = None,
    inter_question_sleep_s: float = 0.0,
    sleep_after_last: bool = False,
) -> Dict[str, Any]:
    if (
        settings is None
        or pipeline is None
        or self_evaluator is None
        or judge_client is None
    ):
        settings, pipeline, self_evaluator, judge_client = (
            build_evaluation_runtime()
        )

    judge_model = settings.chat_model
    cutoffs = [3, 5, 7]
    records: List[Dict[str, Any]] = []

    total_queries = len(dataset_items)
    logger.info("=== Running E2E evaluation on %d queries ===", total_queries)

    for idx, item in enumerate(dataset_items, start=1):
        question = item["question"]
        gold_answer = item.get("gold_answer") or item.get("answer") or ""
        relevant_ids = _as_list(item.get("evidence_chunk_ids", []))
        question_type = item.get("question_type", "simple")
        difficulty = item.get("difficulty", "medium")
        item_id = item.get("id", f"case_{idx:03d}")

        logger.info(
            "[%d/%d] ID: %s | Question: '%s'",
            idx,
            total_queries,
            item_id,
            question[:50],
        )

        # 1. E2E query execution via production RAGPipeline
        #    Uses query_v3() — the same entrypoint that frontend/mobile API calls.
        #    This enables ComplexityRouter + QueryDecomposer for multi_source queries.
        t_start = time.perf_counter()
        try:
            result = pipeline.query_v3(question)
            latency_ms = round((time.perf_counter() - t_start) * 1000, 2)

            generated_answer = result.get("answer") or ""
            sources = result.get("sources") or []
            intent = result.get("intent") or "rag"
            pipeline_mode = result.get("mode") or "unknown"
            pipeline_route = result.get("route") or "unknown"
            num_sources = result.get("num_sources") or len(sources)
            timings = result.get("timings_ms") or {}

        except Exception as exc:
            logger.error("RAGPipeline query crashed: %s", exc, exc_info=True)
            record = {
                "id": item_id,
                "question": question,
                "question_type": question_type,
                "difficulty": difficulty,
                "gold_answer": gold_answer,
                "generated_answer": f"ERROR: {exc}",
                "retrieved_chunk_ids": "",
                "relevant_chunk_ids": ",".join(relevant_ids),
                "mode": "error",
                "route": "error",
                "intent": "error",
                "num_sources": 0,
                "latency_ms": 0,
                "routing_time_ms": 0.0,
                "search_time_ms": 0.0,
                "rerank_time_ms": 0.0,
                "generation_time_ms": 0.0,
                "self_eval_time_ms": 0.0,
                "hyde_time_ms": 0.0,
                "self_eval_pass": False,
                "self_eval_relevance": "bad",
                "self_eval_faithfulness": "hallucinated",
                "self_eval_completeness": "incomplete",
                "self_eval_reason": f"Pipeline crashed: {exc}",
                "ref_match": "incorrect",
                "ref_match_reason": "Pipeline error",
            }
            # Fill cutoffs with 0
            for k in cutoffs:
                record.update(
                    {
                        f"hit@{k}": 0.0,
                        f"precision@{k}": 0.0,
                        f"recall@{k}": 0.0,
                        f"mrr@{k}": 0.0,
                        f"ndcg@{k}": 0.0,
                    }
                )
            records.append(record)
            _sleep_between_questions(
                idx,
                total_queries,
                inter_question_sleep_s,
                sleep_after_last=sleep_after_last,
            )
            continue

        # 2. Extract final retrieved document IDs for retrieval metrics
        retrieved_ids = [_source_id(doc) for doc in sources if doc]
        retrieval_metrics = compute_all_metrics(
            retrieved_ids, relevant_ids, cutoffs
        )

        # 3. Quality Metrics Stage
        # A. Self-Evaluation using the pipeline's LLM
        self_eval_pass = False
        self_eval_relevance = "bad"
        self_eval_faithfulness = "hallucinated"
        self_eval_completeness = "incomplete"
        self_eval_reason = ""

        try:
            context_str = (
                _format_context(sources)
                if sources
                else "(no context retrieved)"
            )
            eval_result = self_evaluator.evaluate(
                query=question,
                context=context_str,
                response=generated_answer,
            )
            self_eval_pass = eval_result.get("pass", False)
            self_eval_relevance = eval_result.get("relevance", "bad")
            self_eval_faithfulness = eval_result.get(
                "faithfulness", "hallucinated"
            )
            self_eval_completeness = eval_result.get(
                "completeness", "incomplete"
            )
            self_eval_reason = eval_result.get("reason", "")
        except Exception as exc:
            logger.warning("Self-evaluation failed: %s", exc)
            self_eval_reason = f"Self-eval crashed: {exc}"

        # B. Reference Answer Comparison using CHAT_MODEL
        ref_match = "incorrect"
        ref_match_reason = ""
        if gold_answer:
            ref_result = _compare_with_reference(
                client=judge_client,
                model=judge_model,
                question=question,
                reference=gold_answer,
                generated=generated_answer,
            )
            ref_match = ref_result.get("match", "incorrect")
            ref_match_reason = ref_result.get("reason", "")

        # 4. Phase Latency Breakdown
        routing_time = round(
            float(timings.get("routing", 0.0))
            + float(timings.get("collection_routing", 0.0))
            + float(timings.get("tier3_domain_fallback", 0.0)),
            2,
        )
        search_time = round(float(timings.get("search", 0.0)), 2)
        rerank_time = round(
            float(timings.get("rerank", 0.0))
            + float(timings.get("rerank_fallback", 0.0)),
            2,
        )
        generation_time = round(float(timings.get("generate", 0.0)), 2)
        self_eval_time = round(float(timings.get("self_eval", 0.0)), 2)
        hyde_time = round(float(timings.get("hyde", 0.0)), 2)
        total_time = round(float(timings.get("pipeline_total", latency_ms)), 2)

        # Check if HyDE was actually triggered in E2E timings
        hyde_triggered = bool(timings.get("hyde_triggered", 0.0) > 0.0)

        record = {
            "id": item_id,
            "question": question,
            "question_type": question_type,
            "difficulty": difficulty,
            "gold_answer": gold_answer,
            "generated_answer": generated_answer,
            "retrieved_chunk_ids": ",".join(retrieved_ids),
            "relevant_chunk_ids": ",".join(relevant_ids),
            "mode": pipeline_mode,
            "route": pipeline_route,
            "intent": intent,
            "num_sources": num_sources,
            "latency_ms": total_time,
            "routing_time_ms": routing_time,
            "search_time_ms": search_time,
            "rerank_time_ms": rerank_time,
            "generation_time_ms": generation_time,
            "self_eval_time_ms": self_eval_time,
            "hyde_time_ms": hyde_time,
            "hyde_triggered": hyde_triggered,
            "self_eval_pass": self_eval_pass,
            "self_eval_relevance": self_eval_relevance,
            "self_eval_faithfulness": self_eval_faithfulness,
            "self_eval_completeness": self_eval_completeness,
            "self_eval_reason": self_eval_reason,
            "ref_match": ref_match,
            "ref_match_reason": ref_match_reason,
            **retrieval_metrics,
        }
        records.append(record)

        # Latency & quality output log
        logger.info(
            "  ↳ Mode: %s | Route: %s | FinalHit@5: %.2f | Faithfulness: %s | Match: %s | Latency: %.1fms%s",
            pipeline_mode,
            pipeline_route,
            retrieval_metrics["hit@5"],
            self_eval_faithfulness,
            ref_match,
            total_time,
            " [HyDE-Triggered]" if hyde_triggered else "",
        )
        _sleep_between_questions(
            idx,
            total_queries,
            inter_question_sleep_s,
            sleep_after_last=sleep_after_last,
        )

    # Aggregate results
    summary = build_summary_report(records)
    if dataset_name:
        summary["dataset"] = dataset_name
    if run_config:
        summary["run_config"] = run_config

    # Save files
    save_outputs(records, summary, output_dir)
    return summary


# ─── Summaries & Exporters ────────────────────────────────────────────────────


def _average_metrics(recs: List[Dict[str, Any]]) -> Dict[str, float]:
    if not recs:
        return {}
    stage_keys = {"self_eval_pass", "hyde_triggered"}
    numeric_keys = []

    # Identify retrieval keys like hit@3, recall@5 etc.
    for key, value in recs[0].items():
        if "@" in key or key in stage_keys:
            if isinstance(value, (int, float, bool)):
                numeric_keys.append(key)

    return {
        key: round(float(sum(float(r[key]) for r in recs) / len(recs)), 4)
        for key in numeric_keys
    }


def build_summary_report(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    total_queries = len(records)
    if total_queries == 0:
        return {}

    overall_metrics = _average_metrics(records)
    avg_latency = round(
        sum(r["latency_ms"] for r in records) / total_queries, 1
    )
    avg_routing = round(
        sum(r["routing_time_ms"] for r in records) / total_queries, 1
    )
    avg_search = round(
        sum(r["search_time_ms"] for r in records) / total_queries, 1
    )
    avg_rerank = round(
        sum(r["rerank_time_ms"] for r in records) / total_queries, 1
    )
    avg_gen = round(
        sum(r["generation_time_ms"] for r in records) / total_queries, 1
    )
    avg_self_eval = round(
        sum(r["self_eval_time_ms"] for r in records) / total_queries, 1
    )

    # HyDE stats
    hyde_count = sum(1 for r in records if r["hyde_triggered"])
    hyde_rate = round(hyde_count / total_queries, 4)

    # E2E Quality aggregation
    # Relevance rate (good)
    relevance_good = sum(
        1 for r in records if r["self_eval_relevance"] == "good"
    )
    relevance_rate = round(relevance_good / total_queries, 4)

    # Faithfulness (grounded)
    faith_grounded = sum(
        1 for r in records if r["self_eval_faithfulness"] == "grounded"
    )
    faithfulness_rate = round(faith_grounded / total_queries, 4)

    # Hallucination count/rate
    hallucination_count = sum(
        1 for r in records if r["self_eval_faithfulness"] == "hallucinated"
    )
    hallucination_rate = round(hallucination_count / total_queries, 4)

    # Completeness (complete)
    complete_count = sum(
        1 for r in records if r["self_eval_completeness"] == "complete"
    )
    completeness_rate = round(complete_count / total_queries, 4)

    # Reference Match (correct / partial / incorrect)
    ref_correct = sum(1 for r in records if r["ref_match"] == "correct")
    ref_partial = sum(1 for r in records if r["ref_match"] == "partial")
    ref_incorrect = sum(1 for r in records if r["ref_match"] == "incorrect")

    ref_correct_rate = round(ref_correct / total_queries, 4)
    ref_partial_rate = round(ref_partial / total_queries, 4)
    ref_incorrect_rate = round(ref_incorrect / total_queries, 4)

    # Breakdowns by question_type
    type_breakdown = {}
    qtypes = sorted(
        list(set(r["question_type"] for r in records if r.get("question_type")))
    )
    for qt in qtypes:
        sub_recs = [r for r in records if r["question_type"] == qt]
        type_breakdown[qt] = {
            "count": len(sub_recs),
            "metrics": _average_metrics(sub_recs),
            "avg_latency_ms": round(
                sum(r["latency_ms"] for r in sub_recs) / len(sub_recs), 1
            ),
            "ref_correct_rate": round(
                sum(1 for r in sub_recs if r["ref_match"] == "correct")
                / len(sub_recs),
                4,
            ),
            "faithfulness_rate": round(
                sum(
                    1
                    for r in sub_recs
                    if r["self_eval_faithfulness"] == "grounded"
                )
                / len(sub_recs),
                4,
            ),
        }

    # Breakdowns by difficulty
    diff_breakdown = {}
    difficulties = sorted(
        list(set(r["difficulty"] for r in records if r.get("difficulty")))
    )
    for diff in difficulties:
        sub_recs = [r for r in records if r["difficulty"] == diff]
        diff_breakdown[diff] = {
            "count": len(sub_recs),
            "metrics": _average_metrics(sub_recs),
            "avg_latency_ms": round(
                sum(r["latency_ms"] for r in sub_recs) / len(sub_recs), 1
            ),
            "ref_correct_rate": round(
                sum(1 for r in sub_recs if r["ref_match"] == "correct")
                / len(sub_recs),
                4,
            ),
            "faithfulness_rate": round(
                sum(
                    1
                    for r in sub_recs
                    if r["self_eval_faithfulness"] == "grounded"
                )
                / len(sub_recs),
                4,
            ),
        }

    # Breakdowns by pipeline mode (rag_v2, rag_v2_decomposed, agent, chitchat, etc.)
    mode_breakdown = {}
    modes = sorted(list(set(r.get("mode", "unknown") for r in records)))
    for mode in modes:
        sub_recs = [r for r in records if r.get("mode", "unknown") == mode]
        mode_breakdown[mode] = {
            "count": len(sub_recs),
            "metrics": _average_metrics(sub_recs),
            "avg_latency_ms": round(
                sum(r["latency_ms"] for r in sub_recs) / len(sub_recs), 1
            ),
            "ref_correct_rate": round(
                sum(1 for r in sub_recs if r["ref_match"] == "correct")
                / len(sub_recs),
                4,
            ),
            "faithfulness_rate": round(
                sum(
                    1
                    for r in sub_recs
                    if r["self_eval_faithfulness"] == "grounded"
                )
                / len(sub_recs),
                4,
            ),
        }

    return {
        "total_queries": total_queries,
        "avg_latency_ms": avg_latency,
        "avg_routing_ms": avg_routing,
        "avg_search_ms": avg_search,
        "avg_rerank_ms": avg_rerank,
        "avg_generation_ms": avg_gen,
        "avg_self_eval_ms": avg_self_eval,
        "hyde_count": hyde_count,
        "hyde_rate": hyde_rate,
        "overall_metrics": overall_metrics,
        "relevance_rate": relevance_rate,
        "faithfulness_rate": faithfulness_rate,
        "completeness_rate": completeness_rate,
        "hallucination_count": hallucination_count,
        "hallucination_rate": hallucination_rate,
        "ref_correct_rate": ref_correct_rate,
        "ref_partial_rate": ref_partial_rate,
        "ref_incorrect_rate": ref_incorrect_rate,
        "by_question_type": type_breakdown,
        "by_difficulty": diff_breakdown,
        "by_mode": mode_breakdown,
    }


def save_outputs(
    records: List[Dict[str, Any]],
    summary: Dict[str, Any],
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Save detailed query results CSV
    csv_path = output_dir / "query_results.csv"
    if records:
        keys = list(records[0].keys())
        with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(records)
    logger.info("Wrote detailed results CSV → %s", csv_path)

    # 2. Save summary JSON
    json_path = output_dir / "summary.json"
    json_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info("Wrote summary JSON → %s", json_path)

    # 3. Save Markdown report
    md_path = output_dir / "report.md"

    lines = [
        "# RAG E2E Pipeline Quality Evaluation Report",
        "",
        f"- **Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- **Total Queries Evaluated**: `{summary['total_queries']}`",
        "",
        "## E2E Generation Metrics (LLM Quality)",
        "",
        "| Metric | Score (Rate) | Details / Counts |",
        "| :--- | :---: | :--- |",
        f"| **Faithfulness (Grounded)** | `{summary['faithfulness_rate']*100:.2f}%` | `{summary['total_queries'] - summary['hallucination_count']}` grounded responses |",
        f"| **Answer Relevance** | `{summary['relevance_rate']*100:.2f}%` | Relevance of answer to question |",
        f"| **Completeness** | `{summary['completeness_rate']*100:.2f}%` | Context facts coverage rate |",
        f"| **Hallucination Rate** | `{summary['hallucination_rate']*100:.2f}%` | `{summary['hallucination_count']}` ungrounded/hallucinated claims |",
        f"| **Correctness (Ref Match Correct)** | `{summary['ref_correct_rate']*100:.2f}%` | Fully correct against golden reference answer |",
        f"| **Ref Match Partial** | `{summary['ref_partial_rate']*100:.2f}%` | Partially matches reference answer |",
        f"| **Ref Match Incorrect** | `{summary['ref_incorrect_rate']*100:.2f}%` | Missing facts / completely incorrect |",
        "",
        "## E2E Retrieval Metrics (After E2E Orchestration)",
        "",
        "| Metric | Score (Average) |",
        "| :--- | :---: |",
    ]

    run_config = summary.get("run_config") or {}
    if run_config:
        config_lines = [
            "## Run Config",
            "",
            "| Key | Value |",
            "| :--- | :--- |",
        ]
        config_lines.extend(
            f"| `{key}` | `{value}` |" for key, value in run_config.items()
        )
        config_lines.append("")
        lines[5:5] = config_lines

    for metric, score in summary["overall_metrics"].items():
        if "@" in metric:
            lines.append(f"| **{metric}** | `{score * 100:.2f}%` |")

    lines.extend(
        [
            "",
            "## Performance & Latency Breakdowns",
            "",
            "| Phase / Event | Avg Latency / Trigger Rate |",
            "| :--- | :---: |",
            f"| **Total Latency** | `{summary['avg_latency_ms']} ms` |",
            f"| Routing Latency | `{summary['avg_routing_ms']} ms` |",
            f"| Search Latency | `{summary['avg_search_ms']} ms` |",
            f"| Rerank Latency | `{summary['avg_rerank_ms']} ms` |",
            f"| Generation Latency | `{summary['avg_generation_ms']} ms` |",
            f"| Self-Evaluation Latency | `{summary['avg_self_eval_ms']} ms` |",
            f"| **HyDE Fallback Trigger Rate** | `{summary['hyde_rate'] * 100:.2f}%` (`{summary['hyde_count']}` queries) |",
            "",
            "## Breakdown by Question Type",
            "",
            "| Type | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |",
            "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
        ]
    )

    for qt, info in summary["by_question_type"].items():
        m = info["metrics"]
        lines.append(
            f"| **{qt}** | {info['count']} | `{m.get('hit@5', 0.0)*100:.1f}%` | `{m.get('recall@5', 0.0)*100:.1f}%` | `{m.get('ndcg@5', 0.0)*100:.1f}%` | "
            f"`{info['faithfulness_rate']*100:.1f}%` | `{info['ref_correct_rate']*100:.1f}%` | `{info['avg_latency_ms']} ms` |"
        )

    lines.extend(
        [
            "",
            "## Breakdown by Difficulty",
            "",
            "| Difficulty | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |",
            "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
        ]
    )

    for diff, info in summary["by_difficulty"].items():
        m = info["metrics"]
        lines.append(
            f"| **{diff}** | {info['count']} | `{m.get('hit@5', 0.0)*100:.1f}%` | `{m.get('recall@5', 0.0)*100:.1f}%` | `{m.get('ndcg@5', 0.0)*100:.1f}%` | "
            f"`{info['faithfulness_rate']*100:.1f}%` | `{info['ref_correct_rate']*100:.1f}%` | `{info['avg_latency_ms']} ms` |"
        )

    # Mode breakdown section
    if summary.get("by_mode"):
        lines.extend(
            [
                "",
                "## Breakdown by Pipeline Mode",
                "",
                "| Mode | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |",
                "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
            ]
        )
        for mode, info in summary["by_mode"].items():
            m = info["metrics"]
            lines.append(
                f"| **{mode}** | {info['count']} | `{m.get('hit@5', 0.0)*100:.1f}%` | `{m.get('recall@5', 0.0)*100:.1f}%` | `{m.get('ndcg@5', 0.0)*100:.1f}%` | "
                f"`{info['faithfulness_rate']*100:.1f}%` | `{info['ref_correct_rate']*100:.1f}%` | `{info['avg_latency_ms']} ms` |"
            )

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info("Wrote E2E report report.md → %s", md_path)

    # 4. Print beautiful console report
    print("\n" + "=" * 70)
    print(" END-TO-END RAG PIPELINE EVALUATION SUMMARY")
    print("=" * 70)
    print(f"Total Queries:                {summary['total_queries']}")
    print(f"Avg Latency (Total):          {summary['avg_latency_ms']} ms")
    print(
        f"HyDE Fallback Rate:           {summary['hyde_rate'] * 100:.2f}% ({summary['hyde_count']} triggers)"
    )
    print("-" * 70)
    print(
        f"Faithfulness (Grounded):      {summary['faithfulness_rate'] * 100:.2f}%"
    )
    print(
        f"Answer Relevance:             {summary['relevance_rate'] * 100:.2f}%"
    )
    print(
        f"Correctness (Fully Match):    {summary['ref_correct_rate'] * 100:.2f}%"
    )
    print(
        f"Hallucination Rate:           {summary['hallucination_rate'] * 100:.2f}%"
    )
    print("-" * 70)
    for metric, score in summary["overall_metrics"].items():
        if "recall@5" in metric or "ndcg@5" in metric or "hit@5" in metric:
            print(f"{metric:<30} : {score * 100:.2f}%")
    print("=" * 70 + "\n")


def save_batch_summary(
    summaries: List[Dict[str, Any]],
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    total_queries = sum(int(s.get("total_queries", 0)) for s in summaries)
    total_hydes = sum(int(s.get("hyde_count", 0)) for s in summaries)
    total_hallucinations = sum(
        int(s.get("hallucination_count", 0)) for s in summaries
    )

    metric_names = sorted(
        {
            metric
            for summary in summaries
            for metric in (summary.get("overall_metrics") or {}).keys()
        }
    )
    overall_metrics = {}
    if total_queries:
        overall_metrics = {
            metric: round(
                sum(
                    float(
                        (summary.get("overall_metrics") or {}).get(metric, 0.0)
                    )
                    * int(summary.get("total_queries", 0))
                    for summary in summaries
                )
                / total_queries,
                4,
            )
            for metric in metric_names
        }

    def _weighted_average(key: str) -> float:
        if not total_queries:
            return 0.0
        return round(
            sum(
                float(summary.get(key, 0.0))
                * int(summary.get("total_queries", 0))
                for summary in summaries
            )
            / total_queries,
            4,
        )

    payload = {
        "dataset_count": len(summaries),
        "total_queries": total_queries,
        "avg_latency_ms": _weighted_average("avg_latency_ms"),
        "avg_routing_ms": _weighted_average("avg_routing_ms"),
        "avg_search_ms": _weighted_average("avg_search_ms"),
        "avg_rerank_ms": _weighted_average("avg_rerank_ms"),
        "avg_generation_ms": _weighted_average("avg_generation_ms"),
        "avg_self_eval_ms": _weighted_average("avg_self_eval_ms"),
        "hyde_count": total_hydes,
        "hyde_rate": (
            round(total_hydes / total_queries, 4) if total_queries else 0.0
        ),
        "relevance_rate": _weighted_average("relevance_rate"),
        "faithfulness_rate": _weighted_average("faithfulness_rate"),
        "completeness_rate": _weighted_average("completeness_rate"),
        "hallucination_count": total_hallucinations,
        "hallucination_rate": (
            round(total_hallucinations / total_queries, 4)
            if total_queries
            else 0.0
        ),
        "ref_correct_rate": _weighted_average("ref_correct_rate"),
        "ref_partial_rate": _weighted_average("ref_partial_rate"),
        "ref_incorrect_rate": _weighted_average("ref_incorrect_rate"),
        "overall_metrics": overall_metrics,
        "datasets": summaries,
    }

    path = output_dir / "batch_summary.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info("Wrote batch summary JSON → %s", path)


# ─── Entry Point ────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate RAG E2E quality and retrieval metrics."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=PROJECT_ROOT / "evaluation" / "data",
        help="Path to an evaluation JSON dataset file or a directory of JSON datasets.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "evaluation" / "results" / "e2e_custom_eval",
        help="Directory to save evaluation reports.",
    )
    parser.add_argument(
        "--top-k",
        "--k",
        type=int,
        default=7,
        help="Target top_k retrieved documents parameter for pipeline.",
    )
    parser.add_argument(
        "--force-top-k-5",
        action="store_true",
        help="Force top_k=5 to compare with classifier retrieval eval.",
    )
    parser.add_argument(
        "--reranker-min-top-k",
        type=int,
        default=None,
        help=(
            "Minimum reranked docs to keep via below-threshold fallback. "
            "Defaults to --top-k; use --disable-reranker-min-top-k to turn off."
        ),
    )
    parser.add_argument(
        "--disable-reranker-min-top-k",
        action="store_true",
        help="Disable min_top_k fallback in the reranker.",
    )
    parser.add_argument(
        "--reranker-score-threshold",
        type=float,
        default=-1.0,
        help="Score threshold override for non-table chunks during E2E eval.",
    )
    parser.add_argument(
        "--reranker-table-score-threshold",
        type=float,
        default=-1.0,
        help="Score threshold override for table chunks during E2E eval.",
    )
    parser.add_argument(
        "--raw-candidate-multiplier",
        type=float,
        default=4.0,
        help="Raw candidate pool multiplier before reranking.",
    )
    parser.add_argument(
        "--raw-candidate-min",
        type=int,
        default=20,
        help="Minimum raw candidate pool before reranking.",
    )
    parser.add_argument(
        "--vector-top-k",
        type=int,
        default=None,
        help="Override per-collection vector search limit for E2E eval.",
    )
    parser.add_argument(
        "--keyword-top-k",
        type=int,
        default=None,
        help="Override per-collection keyword search limit for E2E eval.",
    )
    parser.add_argument(
        "--vector-pool-k",
        type=int,
        default=None,
        help="Override global vector pool size before fusion for E2E eval.",
    )
    parser.add_argument(
        "--keyword-pool-k",
        type=int,
        default=None,
        help="Override global keyword pool size before fusion for E2E eval.",
    )
    parser.add_argument(
        "--low-conf-pool-expand",
        action="store_true",
        help="Double the raw candidate pool when router confidence is low.",
    )
    parser.add_argument(
        "--hyde-enabled",
        action="store_true",
        help="Enable HyDE post-rerank fallback during E2E eval.",
    )
    parser.add_argument(
        "--disable-decomposer",
        action="store_true",
        help="Disable QueryDecomposer for complex multi-source E2E paths.",
    )
    parser.add_argument(
        "--disable-complexity-router",
        action="store_true",
        help="Force all queries through the simple classic RAG path.",
    )
    parser.add_argument(
        "--disable-reflection",
        action="store_true",
        help="Use raw questions instead of QueryReflector rewrites.",
    )
    parser.add_argument(
        "--disable-parent-expansion",
        action="store_true",
        help="Disable parent context enrichment after reranking.",
    )
    parser.add_argument(
        "--sample-n",
        type=int,
        default=None,
        help="Limit the number of queries to evaluate per dataset (useful for testing).",
    )
    parser.add_argument(
        "--llm-rpm",
        type=float,
        default=DEFAULT_LLM_RPM,
        help="LLM requests-per-minute limit used to compute the default sleep.",
    )
    parser.add_argument(
        "--llm-calls-per-question",
        type=float,
        default=DEFAULT_LLM_CALLS_PER_QUESTION,
        help="Estimated number of LLM calls consumed by one evaluated question.",
    )
    parser.add_argument(
        "--rate-limit-buffer-s",
        type=float,
        default=DEFAULT_RATE_LIMIT_BUFFER_S,
        help="Extra seconds added to the computed inter-question sleep.",
    )
    parser.add_argument(
        "--inter-question-sleep-s",
        type=float,
        default=None,
        help=(
            "Seconds to sleep between questions. If omitted, computed from "
            "--llm-rpm, --llm-calls-per-question, and --rate-limit-buffer-s."
        ),
    )

    args = parser.parse_args()

    force_top_k_5 = args.force_top_k_5 or ABLATION_FORCE_TOP_K_5
    if force_top_k_5:
        args.top_k = 5

    if args.disable_reranker_min_top_k:
        effective_reranker_min_top_k = 0
    else:
        effective_reranker_min_top_k = (
            args.reranker_min_top_k
            if args.reranker_min_top_k is not None
            else args.top_k
        )

    disable_complexity_router = (
        args.disable_complexity_router or ABLATION_DISABLE_COMPLEXITY_ROUTER
    )
    disable_reflection = args.disable_reflection or ABLATION_DISABLE_REFLECTION
    disable_parent_expansion = (
        args.disable_parent_expansion or ABLATION_DISABLE_PARENT_EXPANSION
    )

    inter_question_sleep_s = (
        args.inter_question_sleep_s
        if args.inter_question_sleep_s is not None
        else _compute_inter_question_sleep_s(
            args.llm_rpm,
            args.llm_calls_per_question,
            args.rate_limit_buffer_s,
        )
    )
    min_interval_s = (
        60.0 * args.llm_calls_per_question / args.llm_rpm
        if args.llm_rpm > 0 and args.llm_calls_per_question > 0
        else 0.0
    )

    dataset_paths = resolve_dataset_paths(args.dataset)
    multi_dataset = len(dataset_paths) > 1 or args.dataset.is_dir()

    # Load system settings and override top_k
    settings, pipeline, self_evaluator, judge_client = (
        build_evaluation_runtime()
    )
    settings.top_k = args.top_k
    settings.reranker_top_k = args.top_k
    settings.reranker_min_top_k = effective_reranker_min_top_k
    settings.raw_candidate_multiplier = args.raw_candidate_multiplier
    settings.raw_candidate_min = args.raw_candidate_min
    settings.low_conf_pool_expand_enabled = args.low_conf_pool_expand
    settings.hyde_enabled = args.hyde_enabled
    settings.reranker_score_threshold = args.reranker_score_threshold
    settings.reranker_table_score_threshold = args.reranker_table_score_threshold
    pipeline._cfg["top_k"] = args.top_k
    pipeline._cfg["reranker_top_k"] = args.top_k
    pipeline._cfg["reranker_min_top_k"] = effective_reranker_min_top_k
    pipeline._cfg["raw_candidate_multiplier"] = args.raw_candidate_multiplier
    pipeline._cfg["raw_candidate_min"] = args.raw_candidate_min
    pipeline._cfg["low_conf_pool_expand_enabled"] = args.low_conf_pool_expand
    pipeline._cfg["hyde_enabled"] = args.hyde_enabled
    pipeline._cfg["reranker_score_threshold"] = args.reranker_score_threshold
    pipeline._cfg["reranker_table_score_threshold"] = (
        args.reranker_table_score_threshold
    )
    for attr_name, cfg_key in (
        ("vector_top_k", "vector_top_k"),
        ("keyword_top_k", "keyword_top_k"),
        ("vector_pool_k", "vector_pool_k"),
        ("keyword_pool_k", "keyword_pool_k"),
    ):
        override = getattr(args, attr_name)
        if override is not None:
            setattr(settings, attr_name, override)
            pipeline._cfg[cfg_key] = override

    # Keep ValidityFilter enabled so E2E evaluation matches the production
    # frontend/API retrieval path more closely.
    if pipeline._validity_filter is None:
        from retrieval.validity_filter import ValidityFilter

        pipeline._validity_filter = ValidityFilter()
    logger.info("ValidityFilter is ENABLED for E2E evaluation.")

    # Disable agent path so all queries go through RAG flow.
    # Agent returns URLs as sources (not chunk IDs), which causes retrieval
    # metrics to collapse to 0 for queries routed through the agent path.
    pipeline.agent = None
    logger.info(
        "Agent path has been DISABLED for E2E evaluation — all queries use RAG flow."
    )

    # Disable web/Tavily fallback so URL-based sources do not pollute retrieved_chunk_ids.
    # Web fallback injects Facebook/PDF URLs into sources which can never match
    # evidence chunk IDs in the dataset, causing false metric drops.
    settings.web_fallback_on_no_info = False
    settings.web_fallback_on_dynamic = False
    settings.tavily_fallback_enabled = False
    pipeline._cfg["web_fallback_on_no_info"] = False
    pipeline._cfg["web_fallback_on_dynamic"] = False
    pipeline._cfg["tavily_fallback_enabled"] = False
    logger.info("Web/Tavily fallback has been DISABLED for E2E evaluation.")

<<<<<<< HEAD
    # Patch the already-instantiated reranker object because create_reranker()
    # captured thresholds before the eval CLI overrides were applied.
=======
    # Enable HyDE and set Reranker score threshold to -1.0 dynamically.
    settings.hyde_enabled = True
    pipeline._cfg["hyde_enabled"] = True
    settings.reranker_score_threshold = -1.0
    pipeline._cfg["reranker_score_threshold"] = -1.0

    # CRITICAL: Also patch the already-instantiated reranker object.
    # create_reranker(settings) runs INSIDE build_evaluation_runtime() and
    # captures score_threshold at init time.  Mutating settings afterwards
    # does NOT propagate to the reranker instance, so we patch it directly.
>>>>>>> 5e24c8c0 (run evaluate)
    if pipeline._reranker is not None:
        pipeline._reranker.score_threshold = args.reranker_score_threshold
        pipeline._reranker.table_score_threshold = (
            args.reranker_table_score_threshold
        )
        logger.info(
            "Patched reranker instance: score_threshold=%.2f, "
            "table_score_threshold=%.2f",
            pipeline._reranker.score_threshold,
            pipeline._reranker.table_score_threshold,
        )

    # ── Apply ablation study overrides ──────────────────────────────────────
    _active_ablations: List[str] = []

    if disable_complexity_router:
        # Monkeypatch complexity_router.route() to always return "simple".
        # This removes the LLM-based complexity classification from query_v3()
        # so all queries follow the same simple → query() path as classifier eval.
        _orig_route = pipeline.complexity_router.route
        pipeline.complexity_router.route = lambda query, **kw: {  # type: ignore[method-assign]
            "tier": "simple",
            "reason": "ablation_forced_simple",
        }
        logger.info(
            "ABLATION [complexity_router=OFF]: All queries forced to 'simple' path."
        )
        _active_ablations.append("no_complexity_router")

    if disable_reflection:
        # Disable LLM-based query rewriting.  The raw question is used directly
        # for embedding search, matching classifier eval behaviour.
        settings.reflection_enabled = False
        pipeline._cfg["reflection_enabled"] = False
        logger.info(
            "ABLATION [reflection=OFF]: QueryReflector disabled — raw query used."
        )
        _active_ablations.append("no_reflection")

    if disable_parent_expansion:
        # Disable parent context expansion so the reranked list is NOT padded
        # with parent chunks.  Prevents relevant chunks from being pushed
        # beyond the @5 cutoff due to parent insertion.
        pipeline._cfg["parent_context_enabled"] = False
        logger.info(
            "ABLATION [parent_expansion=OFF]: Parent context expansion disabled."
        )
        _active_ablations.append("no_parent_expansion")

    if effective_reranker_min_top_k > 0:
        logger.info(
            "E2E config [reranker_min_top_k=%d]: reranker keeps below-threshold "
            "fallback docs up to top_k.",
            effective_reranker_min_top_k,
        )
        _active_ablations.append(f"min_top_k_{effective_reranker_min_top_k}")

    if force_top_k_5:
        logger.info(
            "ABLATION [top_k=5]: top_k forced to 5 to match classifier eval."
        )
        _active_ablations.append("top_k_5")

    if args.hyde_enabled:
        _active_ablations.append("hyde")
    if args.low_conf_pool_expand:
        _active_ablations.append("low_conf_pool")
    if args.raw_candidate_multiplier != 4.0:
        _active_ablations.append(f"raw_x{args.raw_candidate_multiplier:g}")
    if args.raw_candidate_min != 20:
        _active_ablations.append(f"raw_min_{args.raw_candidate_min}")
    if args.vector_pool_k is not None:
        _active_ablations.append(f"vp_{args.vector_pool_k}")
    if args.keyword_pool_k is not None:
        _active_ablations.append(f"kp_{args.keyword_pool_k}")
    if args.vector_top_k is not None:
        _active_ablations.append(f"vt_{args.vector_top_k}")
    if args.keyword_top_k is not None:
        _active_ablations.append(f"kt_{args.keyword_top_k}")
    if args.disable_decomposer:
        pipeline._decomposer = None
        logger.info("E2E config [decomposer=OFF]: QueryDecomposer disabled.")
        _active_ablations.append("no_decomposer")

    if _active_ablations:
        logger.info("Active ablations: %s", ", ".join(_active_ablations))
    else:
        logger.info(
            "No ablations active — running full production E2E pipeline."
        )
    # ─────────────────────────────────────────────────────────────────────────

    logger.info(
<<<<<<< HEAD
        "E2E eval config: query_v3, top_k=%d, min_top_k=%d, raw_candidate=%gx/%d, "
        "vector_top/pool=%s/%s, keyword_top/pool=%s/%s, "
        "HyDE=%s, low_conf_pool=%s, reranker_threshold=%.2f, "
        "table_threshold=%.2f, ValidityFilter/Agent/WebFallback disabled.",
        args.top_k,
        effective_reranker_min_top_k,
        args.raw_candidate_multiplier,
        args.raw_candidate_min,
        pipeline._cfg.get("vector_top_k"),
        pipeline._cfg.get("vector_pool_k"),
        pipeline._cfg.get("keyword_top_k"),
        pipeline._cfg.get("keyword_pool_k"),
        args.hyde_enabled,
        args.low_conf_pool_expand,
        args.reranker_score_threshold,
        args.reranker_table_score_threshold,
=======
        "E2E eval config: query_v3 (production flow), HyDE enabled, "
        "reranker_score_threshold=-1.0, ValidityFilter enabled, "
        "Agent/WebFallback disabled."
>>>>>>> 5e24c8c0 (run evaluate)
    )
    logger.info(
        "Rate-limit guard: llm_rpm=%.2f, llm_calls_per_question=%.2f, "
        "minimum_interval=%.2fs, inter_question_sleep=%.2fs.",
        args.llm_rpm,
        args.llm_calls_per_question,
        min_interval_s,
        inter_question_sleep_s,
    )

    summaries: List[Dict[str, Any]] = []
    logger.info(
        "Found %d dataset file(s) for E2E evaluation.", len(dataset_paths)
    )
    run_config = {
        "top_k": args.top_k,
        "reranker_min_top_k": effective_reranker_min_top_k,
        "reranker_score_threshold": args.reranker_score_threshold,
        "reranker_table_score_threshold": args.reranker_table_score_threshold,
        "raw_candidate_multiplier": args.raw_candidate_multiplier,
        "raw_candidate_min": args.raw_candidate_min,
        "vector_top_k": pipeline._cfg.get("vector_top_k"),
        "keyword_top_k": pipeline._cfg.get("keyword_top_k"),
        "vector_pool_k": pipeline._cfg.get("vector_pool_k"),
        "keyword_pool_k": pipeline._cfg.get("keyword_pool_k"),
        "low_conf_pool_expand_enabled": args.low_conf_pool_expand,
        "hyde_enabled": args.hyde_enabled,
        "decomposer_enabled": not args.disable_decomposer,
        "reflection_enabled": not disable_reflection,
        "complexity_router_enabled": not disable_complexity_router,
        "parent_context_enabled": not disable_parent_expansion,
        "agent_enabled": False,
        "web_fallback_enabled": False,
        "validity_filter_enabled": False,
    }

    for dataset_index, dataset_path in enumerate(dataset_paths, start=1):
        logger.info("Loading dataset from %s ...", dataset_path)
        dataset_items = load_dataset(dataset_path)
        if args.sample_n is not None:
            logger.info(
                "Limiting evaluation to first %d queries as requested.",
                args.sample_n,
            )
            dataset_items = dataset_items[: args.sample_n]

        # Include active ablation names in the output folder so different
        # ablation runs never overwrite each other.
        _ablation_suffix = (
            ("__" + "_".join(_active_ablations)) if _active_ablations else ""
        )
        dataset_output_dir = args.output_dir / (
            _safe_output_name(dataset_path) + _ablation_suffix
        )

        summary = run_evaluation(
            dataset_items=dataset_items,
            output_dir=dataset_output_dir,
            dataset_name=dataset_path.name,
            settings=settings,
            pipeline=pipeline,
            self_evaluator=self_evaluator,
            judge_client=judge_client,
            run_config=run_config,
            inter_question_sleep_s=inter_question_sleep_s,
            sleep_after_last=dataset_index < len(dataset_paths),
        )
        summaries.append(summary)

    if multi_dataset:
        save_batch_summary(summaries, args.output_dir)


if __name__ == "__main__":
    main()
