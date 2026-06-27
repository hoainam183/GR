"""RAG evaluation — retrieval + end-to-end (e2e) quality metrics.

Chạy lại đúng pipeline production (`/chat/v3` → ``RAGPipeline.query_v3``) trên các
dataset ở ``evaluation/data/*.json`` và đo:

- **Retrieval**: hit@K, precision@K, recall@K, MRR@K, nDCG@K cho K ∈ {3, 5, 7}
  (so retrieved source-id với ``evidence_chunk_ids``).
- **E2E generation**:
    - Groundedness / Faithfulness + Hallucination, Relevance, Completeness — qua
      :class:`llm.self_eval.SelfEvaluator` (LLM judge dùng chat model của pipeline).
    - Correctness — so câu trả lời với ``gold_answer`` qua LLM judge riêng.

Config được giữ **đúng như production** (agent bật, HyDE bật, ValidityFilter bật,
reranker_score_threshold=0.0, reranker_min_top_k=3, top_k=7). Điểm khác duy nhất:
tắt LLM/Redis cache để luôn đo câu trả lời tươi.

Usage (chạy trong .venv tại RAG_v2):

    python -m evaluation.evaluate                                   # toàn bộ evaluation/data
    python -m evaluation.evaluate --dataset evaluation/data/hbkkht_rag_dataset.json
    python -m evaluation.evaluate --dataset evaluation/data/hbkkht_rag_dataset.json --sample-n 3
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("evaluation.evaluate")

# Make project imports work when executed from any cwd.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from config.settings import Settings  # noqa: E402
from llm.self_eval import SelfEvaluator  # noqa: E402
from pipeline.flows import _format_context  # noqa: E402
from pipeline.rag_pipeline import RAGPipeline  # noqa: E402

CUTOFFS: Tuple[int, ...] = (3, 5, 7)
DEFAULT_TOP_K = 7


# ─── ID normalisation & matching ───────────────────────────────────────────────


def _raw_id(value: Any) -> str:
    """Strip a ``collection/`` prefix and surrounding whitespace from an id."""
    text = str(value or "").strip()
    return text.split("/", 1)[-1] if "/" in text else text


def _source_id(doc: Dict[str, Any]) -> str:
    """Return the chunk id used by dataset ``evidence_chunk_ids`` for a source doc."""
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
    """Coerce evidence ids (list / comma string / scalar) into a clean list."""
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
    text = str(value).strip()
    return [text] if text else []


# ─── Retrieval metrics ──────────────────────────────────────────────────────────


def compute_metrics_for_k(
    retrieved_ids: List[str], relevant_ids: List[str], k: int
) -> Dict[str, float]:
    """Hit/precision/recall/MRR/nDCG at a single cutoff ``k``."""
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

    hits = {doc_id for doc_id in topk if doc_id in relevant_set}
    hit = 1.0 if hits else 0.0
    precision = len(hits) / k if k > 0 else 0.0
    recall = len(hits) / len(relevant_set)

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
    retrieved_ids: List[str], relevant_ids: List[str], cutoffs: Tuple[int, ...]
) -> Dict[str, float]:
    """Aggregate :func:`compute_metrics_for_k` across all cutoffs."""
    metrics: Dict[str, float] = {}
    for k in cutoffs:
        metrics.update(compute_metrics_for_k(retrieved_ids, relevant_ids, k))
    return metrics


# ─── Correctness judge (LLM-as-a-judge vs gold_answer) ──────────────────────────

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


def _parse_json_response(
    raw: str, fallback_match: str = "incorrect"
) -> Dict[str, str]:
    """Parse a JSON judge response, stripping optional ```` ``` ```` fences."""
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


def _build_judge_client(settings: Settings) -> OpenAI:
    """Build an OpenAI-compatible client for the correctness judge from settings."""
    provider = settings.llm_provider
    if provider == "lm_studio":
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
    elif provider == "deepseek":
        base_url = "https://api.deepseek.com"
        api_key = settings.deepseek_api_key or os.environ.get("DEEPSEEK_API_KEY", "")
    else:  # gemini (default) and any unknown provider
        base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
        api_key = settings.google_api_key or os.environ.get("GOOGLE_API_KEY", "")

    if not api_key:
        raise EnvironmentError(
            f"API key for judge provider {provider!r} is not set in env or .env."
        )
    return OpenAI(api_key=api_key, base_url=base_url)


def _compare_with_reference(
    client: OpenAI,
    model: str,
    question: str,
    reference: str,
    generated: str,
) -> Dict[str, str]:
    """Ask the judge LLM to compare the generated answer vs the gold answer."""
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
        return _parse_json_response(resp.choices[0].message.content.strip())
    except Exception as exc:  # noqa: BLE001 — judge failures must not abort the run
        logger.warning("Reference comparison LLM call failed: %s", exc)
        return {"match": "incorrect", "reason": f"Judge call error: {exc}"}


# ─── Dataset loading ────────────────────────────────────────────────────────────


def load_dataset(dataset_path: Path) -> List[Dict[str, Any]]:
    """Read the ``items`` array from an ``evaluation/data`` dataset file."""
    payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or "items" not in payload:
        raise ValueError(f"Dataset {dataset_path} must be an object with 'items'.")
    return payload["items"]


def resolve_dataset_paths(dataset_path: Path) -> List[Path]:
    """Return one or more dataset JSON files from a file or directory path."""
    if dataset_path.is_dir():
        paths = sorted(dataset_path.glob("*.json"))
        if not paths:
            raise FileNotFoundError(f"No JSON datasets found in {dataset_path}")
        return paths
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset not found: {dataset_path}")
    return [dataset_path]


def _safe_output_name(path: Path) -> str:
    """Create a filesystem-safe folder name from a dataset filename."""
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", path.stem).strip("._-")
    return name or "dataset"


# ─── Runtime (matches production /chat/v3 config) ───────────────────────────────


def build_runtime(
    fusion_mode: str = "rrf",
    vector_model: str = "dual",
    retrieval_mode: str = "hybrid",
    disable_rerank: bool = False,
) -> Tuple[Settings, RAGPipeline, SelfEvaluator, OpenAI]:
    """Build the production-config pipeline plus the judges used for scoring.

    Uses plain ``Settings()`` (same as ``api/main.py``) so retrieval and
    generation behave exactly like the live ``/chat/v3`` system. The only
    deviation is disabling the LLM/Redis cache so every answer is generated
    fresh rather than served from cache.
    """
    settings = Settings()
    # Fresh answers only — do not read cached responses during evaluation.
    settings.use_redis_cache = False
    settings.redis_enabled = False
    # Ghi đè fusion_mode theo argparse để benchmark
    settings.fusion_mode = fusion_mode

    if vector_model == "bge":
        settings.vector_bge_weight = 1.0
        settings.vector_e5_weight = 0.0
    elif vector_model == "e5":
        settings.vector_bge_weight = 0.0
        settings.vector_e5_weight = 1.0
    else:
        settings.vector_bge_weight = 0.5
        settings.vector_e5_weight = 0.5

    if retrieval_mode == "vector_only":
        settings.vector_weight = 1.0
        settings.keyword_weight = 0.0
        settings.keyword_top_k = 0
        settings.keyword_pool_k = 0
    elif retrieval_mode == "keyword_only":
        settings.vector_weight = 0.0
        settings.keyword_weight = 1.0
        settings.vector_top_k = 0
        settings.vector_pool_k = 0

    if disable_rerank:
        settings.reranker_provider = "none"

    logger.info("Initializing RAGPipeline (production config, cache off) ...")
    pipeline = RAGPipeline(settings=settings, mongo_logger=None, llm_cache=None)

    # Independent judge instance — production may run with self_eval disabled,
    # but we always score groundedness offline on the produced answer/context.
    self_evaluator = SelfEvaluator(llm=pipeline._chat)
    judge_client = _build_judge_client(settings)
    return settings, pipeline, self_evaluator, judge_client


# ─── Per-item evaluation ────────────────────────────────────────────────────────


def _empty_self_eval(reason: str) -> Dict[str, Any]:
    return {
        "self_eval_pass": False,
        "self_eval_relevance": "bad",
        "self_eval_faithfulness": "hallucinated",
        "self_eval_completeness": "incomplete",
        "self_eval_reason": reason,
    }


def _score_quality(
    question: str,
    sources: List[Dict[str, Any]],
    answer: str,
    gold_answer: str,
    self_evaluator: SelfEvaluator,
    judge_client: OpenAI,
    judge_model: str,
) -> Dict[str, Any]:
    """Compute groundedness/hallucination/relevance/completeness + correctness."""
    quality: Dict[str, Any] = {}

    try:
        context = _format_context(sources) if sources else "(no context retrieved)"
        result = self_evaluator.evaluate(
            query=question, context=context, response=answer
        )
        quality.update(
            {
                "self_eval_pass": result.get("pass", False),
                "self_eval_relevance": result.get("relevance", "bad"),
                "self_eval_faithfulness": result.get(
                    "faithfulness", "hallucinated"
                ),
                "self_eval_completeness": result.get(
                    "completeness", "incomplete"
                ),
                "self_eval_reason": result.get("reason", ""),
            }
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Self-evaluation failed: %s", exc)
        quality.update(_empty_self_eval(f"Self-eval crashed: {exc}"))

    if gold_answer:
        ref = _compare_with_reference(
            judge_client, judge_model, question, gold_answer, answer
        )
        quality["ref_match"] = ref.get("match", "incorrect")
        quality["ref_match_reason"] = ref.get("reason", "")
    else:
        quality["ref_match"] = "n/a"
        quality["ref_match_reason"] = "No gold_answer provided."
    return quality


def evaluate_item(
    item: Dict[str, Any],
    pipeline: RAGPipeline,
    self_evaluator: SelfEvaluator,
    judge_client: OpenAI,
    judge_model: str,
    top_k: int = DEFAULT_TOP_K,
) -> Dict[str, Any]:
    """Run one dataset item through the production pipeline and score it."""
    question = item["question"]
    gold_answer = item.get("gold_answer") or item.get("answer") or ""
    relevant_ids = _as_list(item.get("evidence_chunk_ids", []))
    base = {
        "id": item.get("id", ""),
        "question": question,
        "question_type": item.get("question_type", "simple"),
        "difficulty": item.get("difficulty", "medium"),
        "gold_answer": gold_answer,
        "relevant_chunk_ids": ",".join(relevant_ids),
    }

    t_start = time.perf_counter()
    try:
        # Identical call to api/routes/chat.py /chat/v3.
        result = pipeline.query_v3(
            question=question,
            history=None,
            top_k=top_k,
            session_id=None,
            user_context=None,
        )
    except Exception as exc:  # noqa: BLE001 — one bad item must not abort the run
        logger.error("Pipeline crashed on %s: %s", base["id"], exc, exc_info=True)
        record = {
            **base,
            "generated_answer": f"ERROR: {exc}",
            "retrieved_chunk_ids": "",
            "mode": "error",
            "intent": "error",
            "num_sources": 0,
            "latency_ms": 0.0,
            **_empty_self_eval(f"Pipeline crashed: {exc}"),
            "ref_match": "incorrect",
            "ref_match_reason": "Pipeline error",
            **compute_all_metrics([], relevant_ids, CUTOFFS),
        }
        return record

    latency_ms = round((time.perf_counter() - t_start) * 1000, 2)
    answer = result.get("answer") or ""
    sources = result.get("sources") or []
    retrieved_ids = [_source_id(doc) for doc in sources if doc]

    record = {
        **base,
        "generated_answer": answer,
        "retrieved_chunk_ids": ",".join(retrieved_ids),
        "mode": result.get("mode") or "unknown",
        "intent": result.get("intent") or "rag",
        "num_sources": result.get("num_sources") or len(sources),
        "latency_ms": round(
            float((result.get("timings_ms") or {}).get("pipeline_total", latency_ms)),
            2,
        ),
        **_score_quality(
            question,
            sources,
            answer,
            gold_answer,
            self_evaluator,
            judge_client,
            judge_model,
        ),
        **compute_all_metrics(retrieved_ids, relevant_ids, CUTOFFS),
    }
    logger.info(
        "  ↳ [%s] mode=%s hit@5=%.2f recall@5=%.2f faith=%s match=%s %.0fms",
        record["id"],
        record["mode"],
        record["hit@5"],
        record["recall@5"],
        record["self_eval_faithfulness"],
        record["ref_match"],
        record["latency_ms"],
    )
    return record


# ─── Aggregation ────────────────────────────────────────────────────────────────


def _rate(records: List[Dict[str, Any]], key: str, value: str) -> float:
    if not records:
        return 0.0
    return round(sum(1 for r in records if r.get(key) == value) / len(records), 4)


def _avg_at_metrics(records: List[Dict[str, Any]]) -> Dict[str, float]:
    """Average all ``metric@k`` retrieval scores across records."""
    if not records:
        return {}
    keys = [k for k, v in records[0].items() if "@" in k and isinstance(v, (int, float))]
    return {
        key: round(sum(float(r[key]) for r in records) / len(records), 4)
        for key in keys
    }


def _breakdown(
    records: List[Dict[str, Any]], field: str
) -> Dict[str, Dict[str, Any]]:
    groups = sorted({r.get(field, "") for r in records if r.get(field)})
    out: Dict[str, Dict[str, Any]] = {}
    for value in groups:
        subset = [r for r in records if r.get(field) == value]
        out[value] = {
            "count": len(subset),
            "metrics": _avg_at_metrics(subset),
            "faithfulness_rate": _rate(subset, "self_eval_faithfulness", "grounded"),
            "ref_correct_rate": _rate(subset, "ref_match", "correct"),
            "avg_latency_ms": round(
                sum(r["latency_ms"] for r in subset) / len(subset), 1
            ),
        }
    return out


def aggregate(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Roll per-item records up into an evaluation summary."""
    total = len(records)
    if total == 0:
        return {"total_queries": 0}
    return {
        "total_queries": total,
        "avg_latency_ms": round(sum(r["latency_ms"] for r in records) / total, 1),
        "overall_metrics": _avg_at_metrics(records),
        "relevance_rate": _rate(records, "self_eval_relevance", "good"),
        "faithfulness_rate": _rate(records, "self_eval_faithfulness", "grounded"),
        "completeness_rate": _rate(records, "self_eval_completeness", "complete"),
        "hallucination_rate": _rate(
            records, "self_eval_faithfulness", "hallucinated"
        ),
        "hallucination_count": sum(
            1 for r in records if r["self_eval_faithfulness"] == "hallucinated"
        ),
        "ref_correct_rate": _rate(records, "ref_match", "correct"),
        "ref_partial_rate": _rate(records, "ref_match", "partial"),
        "ref_incorrect_rate": _rate(records, "ref_match", "incorrect"),
        "by_question_type": _breakdown(records, "question_type"),
        "by_difficulty": _breakdown(records, "difficulty"),
    }


# ─── Output writers ─────────────────────────────────────────────────────────────


def _render_report(summary: Dict[str, Any]) -> str:
    lines = [
        "# RAG Evaluation Report (production config)",
        "",
        f"- **Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- **Total queries**: `{summary['total_queries']}`",
        f"- **Avg latency**: `{summary['avg_latency_ms']} ms`",
        "",
        "## E2E generation quality",
        "",
        "| Metric | Score |",
        "| :--- | :---: |",
        f"| Groundedness (Faithfulness) | `{summary['faithfulness_rate'] * 100:.2f}%` |",
        f"| Hallucination rate | `{summary['hallucination_rate'] * 100:.2f}%` ({summary['hallucination_count']}) |",
        f"| Answer relevance | `{summary['relevance_rate'] * 100:.2f}%` |",
        f"| Completeness | `{summary['completeness_rate'] * 100:.2f}%` |",
        f"| Correctness vs gold (correct) | `{summary['ref_correct_rate'] * 100:.2f}%` |",
        f"| Correctness vs gold (partial) | `{summary['ref_partial_rate'] * 100:.2f}%` |",
        f"| Correctness vs gold (incorrect) | `{summary['ref_incorrect_rate'] * 100:.2f}%` |",
        "",
        "## Retrieval metrics (averaged)",
        "",
        "| Metric | Score |",
        "| :--- | :---: |",
    ]
    for metric, score in summary["overall_metrics"].items():
        lines.append(f"| {metric} | `{score * 100:.2f}%` |")

    for title, field in (
        ("Breakdown by question type", "by_question_type"),
        ("Breakdown by difficulty", "by_difficulty"),
    ):
        lines += [
            "",
            f"## {title}",
            "",
            "| Group | Count | Hit@5 | Recall@5 | nDCG@5 | Faithfulness | Ref correct | Avg latency |",
            "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
        ]
        for name, info in summary[field].items():
            m = info["metrics"]
            lines.append(
                f"| {name} | {info['count']} | `{m.get('hit@5', 0.0) * 100:.1f}%` | "
                f"`{m.get('recall@5', 0.0) * 100:.1f}%` | `{m.get('ndcg@5', 0.0) * 100:.1f}%` | "
                f"`{info['faithfulness_rate'] * 100:.1f}%` | `{info['ref_correct_rate'] * 100:.1f}%` | "
                f"`{info['avg_latency_ms']} ms` |"
            )
    return "\n".join(lines) + "\n"


def save_outputs(
    records: List[Dict[str, Any]],
    summary: Dict[str, Any],
    output_dir: Path,
) -> None:
    """Write per-query CSV, summary JSON and a Markdown report."""
    output_dir.mkdir(parents=True, exist_ok=True)

    csv_path = output_dir / "query_results.csv"
    if records:
        with csv_path.open("w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(records[0].keys()))
            writer.writeheader()
            writer.writerows(records)

    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output_dir / "report.md").write_text(_render_report(summary), encoding="utf-8")
    logger.info("Wrote results → %s", output_dir)


# ─── Dataset runner & entrypoint ────────────────────────────────────────────────


def run_dataset(
    dataset_path: Path,
    output_dir: Path,
    pipeline: RAGPipeline,
    self_evaluator: SelfEvaluator,
    judge_client: OpenAI,
    judge_model: str,
    top_k: int = DEFAULT_TOP_K,
    sample_n: Optional[int] = None,
    inter_question_sleep_s: float = 0.0,
) -> Dict[str, Any]:
    """Evaluate every item in one dataset file and persist the outputs."""
    items = load_dataset(dataset_path)
    if sample_n is not None:
        items = items[:sample_n]

    logger.info("=== %s: %d queries ===", dataset_path.name, len(items))
    records: List[Dict[str, Any]] = []
    for idx, item in enumerate(items, start=1):
        logger.info("[%d/%d] %s", idx, len(items), item.get("question", "")[:60])
        records.append(
            evaluate_item(
                item, pipeline, self_evaluator, judge_client, judge_model, top_k
            )
        )
        if inter_question_sleep_s > 0 and idx < len(items):
            time.sleep(inter_question_sleep_s)

    summary = aggregate(records)
    summary["dataset"] = dataset_path.name
    save_outputs(records, summary, output_dir)
    return summary


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate RAG retrieval + e2e quality with production config."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=PROJECT_ROOT / "evaluation" / "data",
        help="Dataset JSON file or directory (default: evaluation/data).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "evaluation" / "results",
        help="Directory for evaluation reports.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=DEFAULT_TOP_K,
        help="top_k passed to query_v3 (production default: 7).",
    )
    parser.add_argument(
        "--sample-n",
        type=int,
        default=None,
        help="Only evaluate the first N items per dataset (smoke test).",
    )
    parser.add_argument(
        "--inter-question-sleep-s",
        type=float,
        default=16.0,  # Gemini free tier RPM = 15 (1 req / 4s). Each query takes ~4 LLM calls -> 16s sleep
        help="Seconds to sleep between questions to respect LLM rate limits.",
    )
    parser.add_argument(
        "--fusion-mode",
        type=str,
        default="rrf",
        choices=["rrf", "linear"],
        help="Retrieval fusion strategy: 'rrf' or 'linear'. Default: rrf",
    )
    parser.add_argument(
        "--vector-model",
        type=str,
        default="dual",
        choices=["bge", "e5", "dual"],
        help="Vector model to evaluate: 'bge', 'e5', or 'dual'. Default: dual",
    )
    parser.add_argument(
        "--retrieval-mode",
        type=str,
        default="hybrid",
        choices=["hybrid", "vector_only", "keyword_only"],
        help="Retrieval mode: 'hybrid', 'vector_only', or 'keyword_only'. Default: hybrid",
    )
    parser.add_argument(
        "--disable-rerank",
        action="store_true",
        help="Run without reranker (sets reranker_provider to 'none').",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    dataset_paths = resolve_dataset_paths(args.dataset)
    settings, pipeline, self_evaluator, judge_client = build_runtime(
        fusion_mode=args.fusion_mode,
        vector_model=args.vector_model,
        retrieval_mode=args.retrieval_mode,
        disable_rerank=args.disable_rerank,
    )
    judge_model = settings.chat_model

    # Adjust output directory based on fusion mode and vector model
    fusion_suffix = "RRF" if args.fusion_mode == "rrf" else "linear"
    out_name = f"result_{args.vector_model}_{fusion_suffix}"
    if args.retrieval_mode != "hybrid":
        out_name += f"_{args.retrieval_mode}"
    if args.disable_rerank:
        out_name += "_no_rerank"
        
    output_base = args.output_dir.parent / out_name

    logger.info("Found %d dataset file(s).", len(dataset_paths))
    for dataset_path in dataset_paths:
        run_dataset(
            dataset_path=dataset_path,
            output_dir=output_base / _safe_output_name(dataset_path),
            pipeline=pipeline,
            self_evaluator=self_evaluator,
            judge_client=judge_client,
            judge_model=judge_model,
            top_k=args.top_k,
            sample_n=args.sample_n,
            inter_question_sleep_s=args.inter_question_sleep_s,
        )


if __name__ == "__main__":
    main()
