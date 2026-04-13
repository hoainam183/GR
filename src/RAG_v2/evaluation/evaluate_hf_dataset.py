"""Evaluate RAG pipeline against the HuggingFace SFT dataset.

Dataset: wanduc0701/Sft_dataset_hust_regulation
Columns used:
  - instruction : the user question
  - input       : system prompt + RAG context (used as reference context)
  - output      : gold/reference answer
  - doc_type    : document category for breakdown analysis

Pipeline per question
---------------------
1.  RAGPipeline.query()   — retrieve + rerank + generate answer.
2.  SelfEvaluator         — judge relevance / faithfulness / completeness
                             against the retrieved context.
3.  Reference comparison  — LLM judge compares generated answer with the
                             gold ``output`` from the dataset.

Outputs
-------
- ``<output_dir>/hf_eval_results_<timestamp>.csv``   — per-question details
- ``<output_dir>/hf_eval_summary_<timestamp>.txt``   — aggregate stats

Usage::

    cd /Users/nam.nguyen/GR
    python src/RAG_v2/evaluation/evaluate_hf_dataset.py

Adjust CONFIG below as needed (no CLI required).
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI, RateLimitError

# ---------------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).resolve().parent.parent  # …/RAG_v2
sys.path.insert(0, str(_ROOT))

load_dotenv(_ROOT / ".env")

from pipeline.rag_pipeline import RAGPipeline  # noqa: E402


def _format_context(sources: list) -> str:
    """Format retrieved source documents into a single context string."""
    parts = []
    for i, doc in enumerate(sources, 1):
        text = doc.get("text", "")
        meta = doc.get("metadata", {})
        title = meta.get("title") or meta.get("source") or meta.get("file_name") or ""
        header = f"[{i}] {title}".strip() if title else f"[{i}]"
        parts.append(f"{header}\n{text}")
    return "\n\n".join(parts)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
CONFIG: Dict[str, Any] = {
    # HuggingFace dataset repo id
    "hf_dataset": "wanduc0701/Sft_dataset_hust_regulation",
    # Split to load ("train", "test", "validation", or None → default split)
    "hf_split": "train",
    # Limit number of questions (None = all)
    "sample_n": None,
    # Output directory (relative to RAG_v2 root, or absolute)
    "output_dir": "evaluation/data/hf_eval",
    # RAGPipeline collections to search
    "collections": ["stsv", "quydinh"],
    # Seconds to wait between questions to respect API rate limits
    "delay_s": 0.5,
    # LM Studio judge settings
    "judge_model": "qwen/qwen3-8b:2",
    "judge_base_url": "http://localhost:1234/v1",
    # Save checkpoint to CSV every N questions (0 = disable)
    "checkpoint_every": 50,
    # RAGPipeline overrides
    "pipeline_config": {
        "collections": ["stsv", "quydinh"],
        "top_k": 5,
    },
}

# ---------------------------------------------------------------------------
# Reference-comparison prompt (same as evaluate_llm_quality.py)
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_judge_client() -> OpenAI:
    """Build an OpenAI-compatible client pointing at LM Studio."""
    base_url = CONFIG.get("judge_base_url", "http://localhost:1234/v1")
    # LM Studio accepts any non-empty string as the API key
    return OpenAI(api_key="lm-studio", base_url=base_url)


def _compare_with_reference(
    client: OpenAI,
    model: str,
    question: str,
    reference: str,
    generated: str,
) -> Dict[str, str]:
    user_msg = _REF_COMPARE_USER.format(
        question=question, reference=reference, generated=generated
    )
    for attempt in range(3):
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
            break
        except RateLimitError:
            if attempt < 2:
                time.sleep(2.0 * (attempt + 1))
            else:
                raise
    raw = resp.choices[0].message.content.strip()
    return _parse_json_response(raw, fallback_match="incorrect")


def _parse_json_response(raw: str, fallback_match: str = "incorrect") -> Dict[str, str]:
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


def _resolve_output_dir() -> Path:
    out = Path(CONFIG["output_dir"])
    if not out.is_absolute():
        out = _ROOT / out
    out.mkdir(parents=True, exist_ok=True)
    return out


def _load_hf_dataset() -> pd.DataFrame:
    try:
        from datasets import load_dataset
    except ImportError:
        logger.error("Package 'datasets' not installed. Run: pip install datasets")
        sys.exit(1)

    logger.info("Loading HuggingFace dataset: %s …", CONFIG["hf_dataset"])
    split = CONFIG.get("hf_split", "train")
    ds = load_dataset(CONFIG["hf_dataset"], split=split)
    df = ds.to_pandas()

    required = {"instruction", "output"}
    missing = required - set(df.columns)
    if missing:
        logger.error("Dataset missing required columns: %s", missing)
        sys.exit(1)

    if CONFIG.get("sample_n"):
        df = df.head(int(CONFIG["sample_n"]))

    logger.info("Loaded %d rows (split=%s)", len(df), split)
    return df.reset_index(drop=True)


def _fmt_pct(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return "0.0%"
    return f"{100 * numerator / denominator:.1f}%"


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


def _build_summary(df_results: pd.DataFrame) -> str:
    lines: List[str] = []
    total = len(df_results)
    lines.append("=" * 68)
    lines.append("  HF DATASET EVALUATION — SUMMARY")
    lines.append(f"  Dataset : {CONFIG['hf_dataset']}")
    lines.append(f"  Date    : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"  Total questions evaluated: {total}")
    lines.append("=" * 68)

    # Self-eval pass rate
    n_pass = int(df_results["self_eval_pass"].sum())
    lines.append(
        f"\n[Self-Eval] Pass rate  : {n_pass}/{total}  ({_fmt_pct(n_pass, total)})"
    )
    for metric, col in [
        ("Relevance     — good      ", "self_eval_relevance"),
        ("Faithfulness  — grounded  ", "self_eval_faithfulness"),
        ("Completeness  — complete  ", "self_eval_completeness"),
    ]:
        good_vals = {"good", "grounded", "complete"}
        n = int((df_results[col].isin(good_vals)).sum())
        lines.append(f"  {metric}: {n}/{total}  ({_fmt_pct(n, total)})")

    # Reference comparison
    if "ref_match" in df_results.columns:
        n_correct = int((df_results["ref_match"] == "correct").sum())
        n_partial = int((df_results["ref_match"] == "partial").sum())
        n_incorrect = int((df_results["ref_match"] == "incorrect").sum())
        lines.append(
            f"\n[Ref Match] correct  : {n_correct}/{total}  ({_fmt_pct(n_correct, total)})"
        )
        lines.append(
            f"            partial  : {n_partial}/{total}  ({_fmt_pct(n_partial, total)})"
        )
        lines.append(
            f"            incorrect: {n_incorrect}/{total}  ({_fmt_pct(n_incorrect, total)})"
        )

    # Breakdown by doc_type
    if "doc_type" in df_results.columns:
        lines.append("\n[By doc_type]")
        for dtype in sorted(df_results["doc_type"].dropna().unique()):
            sub = df_results[df_results["doc_type"] == dtype]
            n_sub = len(sub)
            p = int(sub["self_eval_pass"].sum())
            c = (
                int((sub["ref_match"] == "correct").sum())
                if "ref_match" in sub.columns
                else 0
            )
            lines.append(
                f"  {dtype:<40}: pass {p}/{n_sub}  ({_fmt_pct(p, n_sub)})"
                + (
                    f"  |  ref-correct {c}/{n_sub}  ({_fmt_pct(c, n_sub)})"
                    if "ref_match" in sub.columns
                    else ""
                )
            )

    # Intent routing
    if "intent" in df_results.columns:
        lines.append("\n[Intent Routing]")
        for intent, cnt in df_results["intent"].value_counts().items():
            lines.append(f"  {intent:<12}: {cnt}")

    # Latency stats
    if "latency_ms" in df_results.columns:
        lat = df_results["latency_ms"].dropna()
        if len(lat) > 0:
            lines.append(
                f"\n[Latency]  mean={lat.mean():.0f} ms  "
                f"p50={lat.median():.0f} ms  "
                f"p95={lat.quantile(0.95):.0f} ms  "
                f"max={lat.max():.0f} ms"
            )

    lines.append("\n" + "=" * 68)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    output_dir = _resolve_output_dir()
    df = _load_hf_dataset()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    logger.info("Initialising RAGPipeline …")
    pipeline = RAGPipeline(config=CONFIG.get("pipeline_config", {}))

    logger.info("Reusing SelfEvaluator from RAGPipeline …")
    evaluator = pipeline._self_eval

    logger.info("Initialising reference-comparison judge …")
    judge_client = _build_judge_client()
    judge_model = CONFIG["judge_model"]

    records: List[Dict[str, Any]] = []
    checkpoint_every: int = int(CONFIG.get("checkpoint_every", 50))
    csv_path = output_dir / f"hf_eval_results_{timestamp}.csv"

    for idx, row in df.iterrows():
        question = str(row["instruction"])
        reference = str(row["output"])
        doc_type = str(row.get("doc_type", row.get("c_type", "")))

        logger.info("[%d/%d] Q: %s", idx + 1, len(df), question[:80])

        record: Dict[str, Any] = {
            "idx": idx + 1,
            "question": question,
            "reference_answer": reference,
            "doc_type": doc_type,
        }

        # ── Step 1: Generate answer via RAGPipeline
        try:
            t0 = time.perf_counter()
            result = pipeline.query(question)
            latency_ms = round((time.perf_counter() - t0) * 1000, 1)

            generated = result["answer"]
            sources = result["sources"]
            intent = result["intent"]
            num_sources = result["num_sources"]

            record.update(
                {
                    "generated_answer": generated,
                    "intent": intent,
                    "num_sources": num_sources,
                    "latency_ms": latency_ms,
                }
            )
            logger.info(
                "  Generated (%s, %d sources, %.0f ms)", intent, num_sources, latency_ms
            )

        except Exception as exc:
            logger.error("  RAGPipeline error: %s", exc)
            record.update(
                {
                    "generated_answer": "",
                    "intent": "error",
                    "num_sources": 0,
                    "latency_ms": 0,
                    "self_eval_pass": False,
                    "self_eval_relevance": "bad",
                    "self_eval_faithfulness": "hallucinated",
                    "self_eval_completeness": "incomplete",
                    "self_eval_reason": f"Pipeline error: {exc}",
                    "ref_match": "incorrect",
                    "ref_match_reason": "",
                }
            )
            records.append(record)
            continue

        # ── Step 2: Self-evaluation (context-based)
        try:
            context_str = (
                _format_context(sources) if sources else "(no context retrieved)"
            )
            eval_result = evaluator.evaluate(
                query=question,
                context=context_str,
                response=generated,
            )
            record.update(
                {
                    "self_eval_pass": eval_result.get("pass", False),
                    "self_eval_relevance": eval_result.get("relevance", "bad"),
                    "self_eval_faithfulness": eval_result.get(
                        "faithfulness", "hallucinated"
                    ),
                    "self_eval_completeness": eval_result.get(
                        "completeness", "incomplete"
                    ),
                    "self_eval_reason": eval_result.get("reason", ""),
                }
            )
            logger.info(
                "  Self-eval: pass=%s  rel=%s  faith=%s  comp=%s",
                eval_result.get("pass"),
                eval_result.get("relevance"),
                eval_result.get("faithfulness"),
                eval_result.get("completeness"),
            )
        except Exception as exc:
            logger.error("  SelfEvaluator error: %s", exc)
            record.update(
                {
                    "self_eval_pass": False,
                    "self_eval_relevance": "bad",
                    "self_eval_faithfulness": "hallucinated",
                    "self_eval_completeness": "incomplete",
                    "self_eval_reason": f"Eval error: {exc}",
                }
            )

        # ── Step 3: Reference comparison
        try:
            cmp = _compare_with_reference(
                judge_client, judge_model, question, reference, generated
            )
            record.update(
                {
                    "ref_match": cmp["match"],
                    "ref_match_reason": cmp["reason"],
                }
            )
            logger.info("  Ref match: %s — %s", cmp["match"], cmp["reason"][:80])
        except Exception as exc:
            logger.error("  Judge error: %s", exc)
            record.update({"ref_match": "error", "ref_match_reason": str(exc)})

        records.append(record)

        if CONFIG.get("delay_s", 0) > 0:
            time.sleep(CONFIG["delay_s"])

        # ── Checkpoint save every N questions
        if checkpoint_every > 0 and len(records) % checkpoint_every == 0:
            pd.DataFrame(records).to_csv(csv_path, index=False, encoding="utf-8-sig")
            logger.info(
                "[Checkpoint] %d/%d saved → %s", len(records), len(df), csv_path
            )

    # ── Final write
    df_results = pd.DataFrame(records)
    df_results.to_csv(csv_path, index=False, encoding="utf-8-sig")
    logger.info("Results saved → %s", csv_path)

    summary = _build_summary(df_results)
    print("\n" + summary)

    summary_path = output_dir / f"hf_eval_summary_{timestamp}.txt"
    summary_path.write_text(summary, encoding="utf-8")
    logger.info("Summary saved → %s", summary_path)


if __name__ == "__main__":
    main()
