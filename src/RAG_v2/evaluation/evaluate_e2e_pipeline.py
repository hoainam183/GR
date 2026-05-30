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
    metadata = doc.get("metadata") if isinstance(doc.get("metadata"), dict) else {}
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
        return [part.strip() for part in value.replace(";", ",").split(",") if part.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def compute_metrics_for_k(retrieved_ids: List[str], relevant_ids: List[str], k: int) -> Dict[str, float]:
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


def compute_all_metrics(retrieved_ids: List[str], relevant_ids: List[str], cutoffs: List[int]) -> Dict[str, float]:
    metrics = {}
    for k in cutoffs:
        metrics.update(compute_metrics_for_k(retrieved_ids, relevant_ids, k))
    return metrics


def _safe_output_name(path: Path) -> str:
    """Create a filesystem-safe output folder name from a dataset filename."""
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", path.stem).strip("._-")
    return name or "dataset"


# ─── Dataset Loading ────────────────────────────────────────────────────────────

def load_dataset(dataset_path: Path) -> List[Dict[str, Any]]:
    if not dataset_path.exists():
        logger.error("Dataset file not found at %s", dataset_path)
        sys.exit(1)
        
    try:
        payload = json.loads(dataset_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or "items" not in payload:
            logger.error("Invalid dataset format. Must contain an 'items' array.")
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
        api_key = settings.google_api_key or os.environ.get("GOOGLE_API_KEY", "")
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
        api_key = settings.openai_api_key or os.environ.get("OPENAI_API_KEY", "")
    else:
        base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
        api_key = settings.google_api_key or os.environ.get("GOOGLE_API_KEY", "")
        
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


def _parse_json_response(raw: str, fallback_match: str = "incorrect") -> Dict[str, str]:
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

def build_evaluation_runtime() -> Tuple[Settings, RAGPipeline, SelfEvaluator, OpenAI]:
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
) -> Dict[str, Any]:
    if settings is None or pipeline is None or self_evaluator is None or judge_client is None:
        settings, pipeline, self_evaluator, judge_client = build_evaluation_runtime()
        
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
        
        logger.info("[%d/%d] ID: %s | Question: '%s'", idx, total_queries, item_id, question[:50])
        
        # 1. E2E query execution via production RAGPipeline
        t_start = time.perf_counter()
        try:
            result = pipeline.query(question)
            latency_ms = round((time.perf_counter() - t_start) * 1000, 2)
            
            generated_answer = result.get("answer") or ""
            sources = result.get("sources") or []
            intent = result.get("intent") or "rag"
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
                record.update({
                    f"hit@{k}": 0.0,
                    f"precision@{k}": 0.0,
                    f"recall@{k}": 0.0,
                    f"mrr@{k}": 0.0,
                    f"ndcg@{k}": 0.0,
                })
            records.append(record)
            continue
            
        # 2. Extract final retrieved document IDs for retrieval metrics
        retrieved_ids = [_source_id(doc) for doc in sources if doc]
        retrieval_metrics = compute_all_metrics(retrieved_ids, relevant_ids, cutoffs)
        
        # 3. Quality Metrics Stage
        # A. Self-Evaluation using the pipeline's LLM
        self_eval_pass = False
        self_eval_relevance = "bad"
        self_eval_faithfulness = "hallucinated"
        self_eval_completeness = "incomplete"
        self_eval_reason = ""
        
        try:
            context_str = _format_context(sources) if sources else "(no context retrieved)"
            eval_result = self_evaluator.evaluate(
                query=question,
                context=context_str,
                response=generated_answer,
            )
            self_eval_pass = eval_result.get("pass", False)
            self_eval_relevance = eval_result.get("relevance", "bad")
            self_eval_faithfulness = eval_result.get("faithfulness", "hallucinated")
            self_eval_completeness = eval_result.get("completeness", "incomplete")
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
            float(timings.get("routing", 0.0)) + 
            float(timings.get("collection_routing", 0.0)) + 
            float(timings.get("tier3_domain_fallback", 0.0)),
            2
        )
        search_time = round(float(timings.get("search", 0.0)), 2)
        rerank_time = round(float(timings.get("rerank", 0.0)) + float(timings.get("rerank_fallback", 0.0)), 2)
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
            **retrieval_metrics
        }
        records.append(record)
        
        # Latency & quality output log
        logger.info(
            "  ↳ FinalHit@5: %.2f | Faithfulness: %s | Match: %s | Latency: %.1fms%s",
            retrieval_metrics["hit@5"],
            self_eval_faithfulness,
            ref_match,
            total_time,
            " [HyDE-Triggered]" if hyde_triggered else "",
        )
        
    # Aggregate results
    summary = build_summary_report(records)
    if dataset_name:
        summary["dataset"] = dataset_name
        
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
    avg_latency = round(sum(r["latency_ms"] for r in records) / total_queries, 1)
    avg_routing = round(sum(r["routing_time_ms"] for r in records) / total_queries, 1)
    avg_search = round(sum(r["search_time_ms"] for r in records) / total_queries, 1)
    avg_rerank = round(sum(r["rerank_time_ms"] for r in records) / total_queries, 1)
    avg_gen = round(sum(r["generation_time_ms"] for r in records) / total_queries, 1)
    avg_self_eval = round(sum(r["self_eval_time_ms"] for r in records) / total_queries, 1)
    
    # HyDE stats
    hyde_count = sum(1 for r in records if r["hyde_triggered"])
    hyde_rate = round(hyde_count / total_queries, 4)
    
    # E2E Quality aggregation
    # Relevance rate (good)
    relevance_good = sum(1 for r in records if r["self_eval_relevance"] == "good")
    relevance_rate = round(relevance_good / total_queries, 4)
    
    # Faithfulness (grounded)
    faith_grounded = sum(1 for r in records if r["self_eval_faithfulness"] == "grounded")
    faithfulness_rate = round(faith_grounded / total_queries, 4)
    
    # Hallucination count/rate
    hallucination_count = sum(1 for r in records if r["self_eval_faithfulness"] == "hallucinated")
    hallucination_rate = round(hallucination_count / total_queries, 4)
    
    # Completeness (complete)
    complete_count = sum(1 for r in records if r["self_eval_completeness"] == "complete")
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
    qtypes = sorted(list(set(r["question_type"] for r in records if r.get("question_type"))))
    for qt in qtypes:
        sub_recs = [r for r in records if r["question_type"] == qt]
        type_breakdown[qt] = {
            "count": len(sub_recs),
            "metrics": _average_metrics(sub_recs),
            "avg_latency_ms": round(sum(r["latency_ms"] for r in sub_recs) / len(sub_recs), 1),
            "ref_correct_rate": round(sum(1 for r in sub_recs if r["ref_match"] == "correct") / len(sub_recs), 4),
            "faithfulness_rate": round(sum(1 for r in sub_recs if r["self_eval_faithfulness"] == "grounded") / len(sub_recs), 4)
        }
        
    # Breakdowns by difficulty
    diff_breakdown = {}
    difficulties = sorted(list(set(r["difficulty"] for r in records if r.get("difficulty"))))
    for diff in difficulties:
        sub_recs = [r for r in records if r["difficulty"] == diff]
        diff_breakdown[diff] = {
            "count": len(sub_recs),
            "metrics": _average_metrics(sub_recs),
            "avg_latency_ms": round(sum(r["latency_ms"] for r in sub_recs) / len(sub_recs), 1),
            "ref_correct_rate": round(sum(1 for r in sub_recs if r["ref_match"] == "correct") / len(sub_recs), 4),
            "faithfulness_rate": round(sum(1 for r in sub_recs if r["self_eval_faithfulness"] == "grounded") / len(sub_recs), 4)
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
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
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
    
    for metric, score in summary["overall_metrics"].items():
        if "@" in metric:
            lines.append(f"| **{metric}** | `{score * 100:.2f}%` |")
            
    lines.extend([
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
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |"
    ])
    
    for qt, info in summary["by_question_type"].items():
        m = info["metrics"]
        lines.append(
            f"| **{qt}** | {info['count']} | `{m.get('hit@5', 0.0)*100:.1f}%` | `{m.get('recall@5', 0.0)*100:.1f}%` | `{m.get('ndcg@5', 0.0)*100:.1f}%` | "
            f"`{info['faithfulness_rate']*100:.1f}%` | `{info['ref_correct_rate']*100:.1f}%` | `{info['avg_latency_ms']} ms` |"
        )
        
    lines.extend([
        "",
        "## Breakdown by Difficulty",
        "",
        "| Difficulty | Count | Hit@5 | Recall@5 | NDCG@5 | Faithfulness | Ref Correct | Avg Latency |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |"
    ])
    
    for diff, info in summary["by_difficulty"].items():
        m = info["metrics"]
        lines.append(
            f"| **{diff}** | {info['count']} | `{m.get('hit@5', 0.0)*100:.1f}%` | `{m.get('recall@5', 0.0)*100:.1f}%` | `{m.get('ndcg@5', 0.0)*100:.1f}%` | "
            f"`{info['faithfulness_rate']*100:.1f}%` | `{info['ref_correct_rate']*100:.1f}%` | `{info['avg_latency_ms']} ms` |"
        )
        
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info("Wrote E2E report report.md → %s", md_path)
    
    # 4. Print beautiful console report
    print("\n" + "="*70)
    print(" END-TO-END RAG PIPELINE EVALUATION SUMMARY")
    print("="*70)
    print(f"Total Queries:                {summary['total_queries']}")
    print(f"Avg Latency (Total):          {summary['avg_latency_ms']} ms")
    print(f"HyDE Fallback Rate:           {summary['hyde_rate'] * 100:.2f}% ({summary['hyde_count']} triggers)")
    print("-"*70)
    print(f"Faithfulness (Grounded):      {summary['faithfulness_rate'] * 100:.2f}%")
    print(f"Answer Relevance:             {summary['relevance_rate'] * 100:.2f}%")
    print(f"Correctness (Fully Match):    {summary['ref_correct_rate'] * 100:.2f}%")
    print(f"Hallucination Rate:           {summary['hallucination_rate'] * 100:.2f}%")
    print("-"*70)
    for metric, score in summary["overall_metrics"].items():
        if "recall@5" in metric or "ndcg@5" in metric or "hit@5" in metric:
            print(f"{metric:<30} : {score * 100:.2f}%")
    print("="*70 + "\n")


def save_batch_summary(
    summaries: List[Dict[str, Any]],
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    total_queries = sum(int(s.get("total_queries", 0)) for s in summaries)
    total_hydes = sum(int(s.get("hyde_count", 0)) for s in summaries)
    total_hallucinations = sum(int(s.get("hallucination_count", 0)) for s in summaries)

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
                    float((summary.get("overall_metrics") or {}).get(metric, 0.0))
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
                float(summary.get(key, 0.0)) * int(summary.get("total_queries", 0))
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
        "hyde_rate": round(total_hydes / total_queries, 4) if total_queries else 0.0,
        "relevance_rate": _weighted_average("relevance_rate"),
        "faithfulness_rate": _weighted_average("faithfulness_rate"),
        "completeness_rate": _weighted_average("completeness_rate"),
        "hallucination_count": total_hallucinations,
        "hallucination_rate": round(total_hallucinations / total_queries, 4) if total_queries else 0.0,
        "ref_correct_rate": _weighted_average("ref_correct_rate"),
        "ref_partial_rate": _weighted_average("ref_partial_rate"),
        "ref_incorrect_rate": _weighted_average("ref_incorrect_rate"),
        "overall_metrics": overall_metrics,
        "datasets": summaries,
    }

    path = output_dir / "batch_summary.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Wrote batch summary JSON → %s", path)


# ─── Entry Point ────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate RAG E2E quality and retrieval metrics.")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=PROJECT_ROOT / "evaluation" / "data",
        help="Path to an evaluation JSON dataset file or a directory of JSON datasets."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "evaluation" / "results" / "e2e_custom_eval",
        help="Directory to save evaluation reports."
    )
    parser.add_argument(
        "--top-k", "--k",
        type=int,
        default=7,
        help="Target top_k retrieved documents parameter for pipeline."
    )
    parser.add_argument(
        "--sample-n",
        type=int,
        default=None,
        help="Limit the number of queries to evaluate per dataset (useful for testing)."
    )
    
    args = parser.parse_args()

    dataset_paths = resolve_dataset_paths(args.dataset)
    multi_dataset = len(dataset_paths) > 1 or args.dataset.is_dir()

    # Load system settings and override top_k
    settings, pipeline, self_evaluator, judge_client = build_evaluation_runtime()
    settings.top_k = args.top_k
    pipeline._cfg["top_k"] = args.top_k

    # Disable ValidityFilter for evaluation as requested
    pipeline._validity_filter = None
    logger.info("ValidityFilter has been disabled for E2E evaluation.")


    summaries: List[Dict[str, Any]] = []
    logger.info("Found %d dataset file(s) for E2E evaluation.", len(dataset_paths))
    
    for dataset_path in dataset_paths:
        logger.info("Loading dataset from %s ...", dataset_path)
        dataset_items = load_dataset(dataset_path)
        if args.sample_n is not None:
            logger.info("Limiting evaluation to first %d queries as requested.", args.sample_n)
            dataset_items = dataset_items[:args.sample_n]
            
        dataset_output_dir = args.output_dir / _safe_output_name(dataset_path)

        summary = run_evaluation(
            dataset_items=dataset_items,
            output_dir=dataset_output_dir,
            dataset_name=dataset_path.name,
            settings=settings,
            pipeline=pipeline,
            self_evaluator=self_evaluator,
            judge_client=judge_client,
        )
        summaries.append(summary)

    if multi_dataset:
        save_batch_summary(summaries, args.output_dir)


if __name__ == "__main__":
    main()

