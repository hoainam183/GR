"""Evaluate LLM response quality for the RAG v2 pipeline.

Pipeline per question
---------------------
1.  RAGPipeline.query()   — retrieve + rerank + generate answer.
2.  SelfEvaluator         — judge relevance / faithfulness / completeness
                             against the retrieved context.
3.  Reference comparison  — LLM judge compares generated answer with the
                             ground-truth reference answer.

Outputs
-------
- ``<output_dir>/llm_quality_results_<timestamp>.csv``  — per-question details
- ``<output_dir>/llm_quality_summary_<timestamp>.txt``  — aggregate stats

Usage::

    cd D:/GR/src/RAG_v2
    python evaluation/evaluate_llm_quality.py

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
from openai import OpenAI

# ---------------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).resolve().parent.parent  # …/RAG_v2
sys.path.insert(0, str(_ROOT))

load_dotenv(_ROOT / ".env")

from llm.self_eval import SelfEvaluator  # noqa: E402
from pipeline.rag_pipeline import RAGPipeline  # noqa: E402

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
    # Input dataset — absolute or relative to RAG_v2 root
    "eval_csv": str(
        _ROOT.parent.parent / "evaluate_data" / "rag_evaluation_dataset.csv"
    ),
    # Output directory (relative to RAG_v2 root, or absolute)
    "output_dir": "evaluation/data/llm_quality",
    # RAGPipeline collections to search
    "collections": ["stsv", "quydinh"],
    # Limit number of questions (None = all)
    "sample_n": None,
    # Seconds to wait between questions to respect API rate limits
    "delay_s": 2.0,
    # Gemini model for reference-comparison judge
    "judge_model": "gemini-3.1-flash-lite",
    # RAGPipeline overrides  (merged into RAGPipeline.CONFIG)
    "pipeline_config": {
        "collections": ["stsv", "quydinh"],
        "top_k": 5,
    },
}

# ---------------------------------------------------------------------------
# Reference-comparison prompt
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
_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


def _build_judge_client() -> OpenAI:
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GOOGLE_API_KEY not set in environment / .env file."
        )
    return OpenAI(api_key=api_key, base_url=_GEMINI_BASE_URL)


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


def _resolve_output_dir() -> Path:
    out = Path(CONFIG["output_dir"])
    if not out.is_absolute():
        out = _ROOT / out
    out.mkdir(parents=True, exist_ok=True)
    return out


def _load_dataset() -> pd.DataFrame:
    csv_path = Path(CONFIG["eval_csv"])
    if not csv_path.exists():
        logger.error("Eval CSV not found: %s", csv_path)
        sys.exit(1)
    df = pd.read_csv(csv_path)
    required = {"question", "answer"}
    missing = required - set(df.columns)
    if missing:
        logger.error("Eval CSV missing required columns: %s", missing)
        sys.exit(1)
    if CONFIG.get("sample_n"):
        df = df.head(int(CONFIG["sample_n"]))
    logger.info("Loaded %d questions from %s", len(df), csv_path.name)
    return df.reset_index(drop=True)


def _fmt_pct(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return "0.0%"
    return f"{100 * numerator / denominator:.1f}%"


# ---------------------------------------------------------------------------
# Summary printer / writer
# ---------------------------------------------------------------------------


def _build_summary(df_results: pd.DataFrame) -> str:
    lines: List[str] = []
    total = len(df_results)
    lines.append("=" * 68)
    lines.append("  LLM RESPONSE QUALITY EVALUATION — SUMMARY")
    lines.append(f"  Date : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"  Total questions evaluated: {total}")
    lines.append("=" * 68)

    # ── Overall pass rate (self-eval)
    n_pass = int(df_results["self_eval_pass"].sum())
    lines.append(
        f"\n[Self-Eval] Pass rate  : {n_pass}/{total}  ({_fmt_pct(n_pass, total)})"
    )

    for metric, col in [
        ("Relevance  — good   ", "self_eval_relevance"),
        ("Faithfulness — grounded", "self_eval_faithfulness"),
        ("Completeness — complete", "self_eval_completeness"),
    ]:
        good_vals = {"good", "grounded", "complete"}
        n = int((df_results[col].isin(good_vals)).sum())
        lines.append(f"  {metric}: {n}/{total}  ({_fmt_pct(n, total)})")

    # ── Reference comparison match rate
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

    # ── Breakdown by difficulty
    if "difficulty" in df_results.columns:
        lines.append("\n[By Difficulty]")
        for diff in sorted(df_results["difficulty"].dropna().unique()):
            sub = df_results[df_results["difficulty"] == diff]
            n_sub = len(sub)
            p = int(sub["self_eval_pass"].sum())
            lines.append(
                f"  {diff:<10}: pass {p}/{n_sub}  ({_fmt_pct(p, n_sub)})",
            )

    # ── Breakdown by question_type
    if "question_type" in df_results.columns:
        lines.append("\n[By Question Type]")
        for qtype in sorted(df_results["question_type"].dropna().unique()):
            sub = df_results[df_results["question_type"] == qtype]
            n_sub = len(sub)
            p = int(sub["self_eval_pass"].sum())
            c = (
                int((sub["ref_match"] == "correct").sum())
                if "ref_match" in sub.columns
                else 0
            )
            lines.append(
                f"  {qtype:<15}: pass {p}/{n_sub}  ({_fmt_pct(p, n_sub)})"
                + (
                    f"  |  ref-correct {c}/{n_sub}  ({_fmt_pct(c, n_sub)})"
                    if "ref_match" in sub.columns
                    else ""
                )
            )

    # ── Intent routing breakdown
    if "intent" in df_results.columns:
        lines.append("\n[Intent Routing]")
        for intent, cnt in df_results["intent"].value_counts().items():
            lines.append(f"  {intent:<12}: {cnt}")

    lines.append("\n" + "=" * 68)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    output_dir = _resolve_output_dir()
    df = _load_dataset()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # ── Initialise pipeline components
    logger.info("Initialising RAGPipeline …")
    pipeline = RAGPipeline(config=CONFIG.get("pipeline_config", {}))

    logger.info("Initialising SelfEvaluator …")
    evaluator = SelfEvaluator()

    logger.info("Initialising reference-comparison judge …")
    judge_client = _build_judge_client()
    judge_model = CONFIG["judge_model"]

    # ── Evaluation loop
    records: List[Dict[str, Any]] = []

    for idx, row in df.iterrows():
        question = str(row["question"])
        reference = str(row["answer"])
        qtype = row.get("question_type", "")
        difficulty = row.get("difficulty", "")
        doc_source = row.get("document_source", "")

        logger.info("[%d/%d] Q: %s", idx + 1, len(df), question[:80])

        record: Dict[str, Any] = {
            "idx": idx + 1,
            "question": question,
            "reference_answer": reference,
            "question_type": qtype,
            "difficulty": difficulty,
            "document_source": doc_source,
        }

        # ── Step 1 : Generate answer via RAGPipeline
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
                "  Generated (%s, %d sources, %.0f ms)",
                intent,
                num_sources,
                latency_ms,
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

        # ── Step 2 : Self-evaluation (context-based)
        try:
            from pipeline.rag_pipeline import _format_context  # reuse helper

            context_str = (
                _format_context(sources)
                if sources
                else "(no context retrieved)"
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
                "  Self-eval: pass=%s, rel=%s, faith=%s, comp=%s",
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
                    "self_eval_reason": f"Evaluator error: {exc}",
                }
            )

        # ── Step 3 : Reference comparison
        try:
            ref_result = _compare_with_reference(
                client=judge_client,
                model=judge_model,
                question=question,
                reference=reference,
                generated=generated,
            )
            record.update(
                {
                    "ref_match": ref_result.get("match", "incorrect"),
                    "ref_match_reason": ref_result.get("reason", ""),
                }
            )
            logger.info("  Ref match: %s", ref_result.get("match"))
        except Exception as exc:
            logger.error("  Reference comparison error: %s", exc)
            record.update(
                {
                    "ref_match": "incorrect",
                    "ref_match_reason": f"Judge error: {exc}",
                }
            )

        records.append(record)

        # Rate-limit guard
        if CONFIG["delay_s"] > 0:
            time.sleep(CONFIG["delay_s"])

    # ── Write results CSV
    df_results = pd.DataFrame(records)
    results_csv = output_dir / f"llm_quality_results_{timestamp}.csv"
    df_results.to_csv(results_csv, index=False, encoding="utf-8-sig")
    logger.info("Results saved → %s", results_csv)

    # ── Write summary text
    summary_text = _build_summary(df_results)
    summary_path = output_dir / f"llm_quality_summary_{timestamp}.txt"
    summary_path.write_text(summary_text, encoding="utf-8")
    logger.info("Summary saved → %s", summary_path)

    print("\n")
    print(summary_text)


if __name__ == "__main__":
    main()
