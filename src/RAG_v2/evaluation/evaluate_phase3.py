"""Phase 3 Evaluation Pipeline — Retrieval + Generation + Self-Eval with Gemini.

Reads an evaluation dataset CSV (produced by eval_dataset_builder), runs
hybrid retrieval, generates an answer for each query with Gemini, then
self-evaluates each answer with a Gemini judge.  Writes an enriched CSV and
a summary CSV to ``evaluation/data/phase3_results/``.

Pipeline per query
------------------
1. Hybrid search  (BGE-M3 + E5 Qdrant  +  Elasticsearch BM25)
2. Compute retrieval metrics  (hit@1, hit@k, P@k, R@k, MRR)
3. Generate answer with Gemini  (RAG prompt from llm/prompts.py)
4. Self-evaluate answer with Gemini  (self-eval prompt from llm/prompts.py)

Usage::

    python evaluation/evaluate_phase3.py
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------------

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

load_dotenv(_ROOT / ".env")

import google.generativeai as genai  # noqa: E402 — after sys.path

from embedding.bge_m3 import BGEm3Embedder  # noqa: E402
from embedding.e5_multilingual import E5MultilingualEmbedder  # noqa: E402
from llm.prompts import (  # noqa: E402
    RAG_SYSTEM_PROMPT,
    RAG_USER_TEMPLATE,
    SELF_EVAL_SYSTEM_PROMPT,
    SELF_EVAL_USER_TEMPLATE,
)
from retrieval.multi_collection_search import (
    MultiCollectionSearch,
)  # noqa: E402

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
# Config — chỉnh tham số tại đây, không dùng CLI
# ---------------------------------------------------------------------------

CONFIG: Dict[str, Any] = {
    # Eval dataset CSV — None → tự tìm file mới nhất trong eval_dataset_builder/data/
    "eval_csv": None,
    # Thư mục lưu kết quả
    "output_dir": "evaluation/data/phase3_results",
    # Retrieval
    "collections": ["quydinh"],
    "es_indexes": None,  # None → dùng collections
    "top_k": 15,  # số chunk trả về sau fusion
    "vector_top_k": 20,  # candidates từ Qdrant mỗi collection
    "keyword_top_k": 20,  # candidates từ Elasticsearch mỗi collection
    "vector_pool_k": 15,  # global pool sau khi sort theo vector score
    "keyword_pool_k": 15,  # global pool sau khi sort theo BM25 score
    "vector_weight": 0.8,  # weight cho vector score trong fusion
    "keyword_weight": 0.2,  # weight cho BM25 score trong fusion
    "qdrant_host": "localhost",
    "qdrant_port": 6333,
    "es_host": "localhost",
    "es_port": 9200,
    # Metric cutoff
    "k": 5,
    # Gemini
    "gemini_model": "gemini-3.1-flash-lite",
    "gemini_api_key": None,  # None → đọc GEMINI_API_KEY từ env
    # Pipeline switches
    "skip_generation": False,  # True → chỉ đánh giá retrieval, không generate
    "skip_self_eval": False,  # True → không chạy self-eval
    # Embedding
    "no_bge": False,
    "no_e5": False,
}

# ---------------------------------------------------------------------------
# Directory helpers
# ---------------------------------------------------------------------------

_EVAL_DIR = Path(__file__).resolve().parent
_BUILDER_DATA_DIR = _ROOT / "eval_dataset_builder" / "data"


def _resolve_eval_csv() -> Path:
    """Return the eval CSV path from CONFIG or auto-discover the latest one."""
    if CONFIG["eval_csv"]:
        p = Path(CONFIG["eval_csv"])
        if not p.is_absolute():
            p = _ROOT / p
        return p

    candidates = sorted(
        _BUILDER_DATA_DIR.glob("*.csv"), key=lambda f: f.stat().st_mtime
    )
    if not candidates:
        logger.error("No CSV files found in %s", _BUILDER_DATA_DIR)
        sys.exit(1)
    chosen = candidates[-1]
    logger.info("Auto-selected eval CSV: %s", chosen.name)
    return chosen


def _resolve_output_dir() -> Path:
    out = Path(CONFIG["output_dir"])
    if not out.is_absolute():
        out = _ROOT / out
    out.mkdir(parents=True, exist_ok=True)
    return out


# ---------------------------------------------------------------------------
# Metric helpers  (identical to evaluate_retrieval.py)
# ---------------------------------------------------------------------------


def _parse_relevant_ids(raw: Any) -> Set[str]:
    if not isinstance(raw, str) or not raw.strip():
        return set()
    # Strip JSON-style brackets/quotes if present
    cleaned = raw.strip().lstrip("[").rstrip("]")
    parts = [
        s.strip().strip('"').strip("'")
        for s in cleaned.replace(";", ",").split(",")
    ]
    return {s for s in parts if s}


def compute_metrics(
    retrieved_ids: List[str],
    relevant_ids: Set[str],
    k: int,
) -> Dict[str, float]:
    if not relevant_ids:
        return {
            "hit@1": 0,
            "hit@k": 0,
            "precision@k": 0.0,
            "recall@k": 0.0,
            "mrr": 0.0,
        }

    top1 = retrieved_ids[:1]
    topk = retrieved_ids[:k]

    hit1 = int(bool(set(top1) & relevant_ids))
    hitk = int(bool(set(topk) & relevant_ids))
    prec = len(set(topk) & relevant_ids) / k if k > 0 else 0.0
    rec = len(set(topk) & relevant_ids) / len(relevant_ids)

    mrr = 0.0
    for rank, doc_id in enumerate(retrieved_ids, start=1):
        if doc_id in relevant_ids:
            mrr = 1.0 / rank
            break

    return {
        "hit@1": hit1,
        "hit@k": hitk,
        "precision@k": round(prec, 4),
        "recall@k": round(rec, 4),
        "mrr": round(mrr, 4),
    }


# ---------------------------------------------------------------------------
# Gemini helpers
# ---------------------------------------------------------------------------


def _init_gemini() -> genai.GenerativeModel:
    api_key = CONFIG["gemini_api_key"] or os.getenv("GEMINI_API_KEY")
    if not api_key or api_key == "your-gemini-api-key-here":
        logger.error(
            "GEMINI_API_KEY not set. Add it to .env or set CONFIG['gemini_api_key']."
        )
        sys.exit(1)
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(CONFIG["gemini_model"])
    logger.info("Gemini model '%s' initialised.", CONFIG["gemini_model"])
    return model


def _gemini_generate(
    model: genai.GenerativeModel, system: str, user: str
) -> str:
    """Send a system+user prompt to Gemini and return the text response."""
    combined = f"{system}\n\n{user}"
    response = model.generate_content(combined)
    return response.text.strip()


def generate_rag_answer(
    model: genai.GenerativeModel, query: str, context: str
) -> Tuple[str, float]:
    """Generate a RAG answer using Gemini.

    Returns:
        Tuple of (answer_text, latency_ms).
    """
    user_prompt = RAG_USER_TEMPLATE.format(context=context, query=query)
    t0 = time.perf_counter()
    answer = _gemini_generate(model, RAG_SYSTEM_PROMPT, user_prompt)
    latency_ms = round((time.perf_counter() - t0) * 1000, 1)
    return answer, latency_ms


def self_evaluate(
    model: genai.GenerativeModel, query: str, context: str, response: str
) -> Tuple[Dict[str, Any], float]:
    """Self-evaluate a generated answer using Gemini.

    Returns:
        Tuple of (eval_result_dict, latency_ms).
    """
    user_prompt = SELF_EVAL_USER_TEMPLATE.format(
        query=query, context=context, response=response
    )
    t0 = time.perf_counter()
    raw = _gemini_generate(model, SELF_EVAL_SYSTEM_PROMPT, user_prompt)
    latency_ms = round((time.perf_counter() - t0) * 1000, 1)

    result = _parse_self_eval(raw)
    return result, latency_ms


def _parse_self_eval(raw: str) -> Dict[str, Any]:
    # Gemini sometimes wraps JSON in markdown code blocks — strip them
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        # Drop first and last fence lines
        inner = (
            "\n".join(lines[1:-1])
            if lines[-1].strip() == "```"
            else "\n".join(lines[1:])
        )
        cleaned = inner.strip()

    try:
        data = json.loads(cleaned)
        return {
            "pass": bool(data.get("pass", False)),
            "relevance": data.get("relevance", "bad"),
            "faithfulness": data.get("faithfulness", "hallucinated"),
            "completeness": data.get("completeness", "incomplete"),
            "reason": data.get("reason", ""),
        }
    except (json.JSONDecodeError, AttributeError):
        logger.warning("Failed to parse self-eval JSON: %r", raw[:200])
        return {
            "pass": False,
            "relevance": "bad",
            "faithfulness": "hallucinated",
            "completeness": "incomplete",
            "reason": f"Parse error: {raw[:200]}",
        }


# ---------------------------------------------------------------------------
# Context formatter
# ---------------------------------------------------------------------------


def _format_context(results: List[Dict[str, Any]]) -> str:
    """Format retrieved chunks into a context string for the LLM."""
    parts: List[str] = []
    for i, r in enumerate(results, start=1):
        meta = r.get("metadata", {})
        source = meta.get("source", meta.get("file_name", "unknown"))
        text = r.get("text", "").strip()
        parts.append(f"[{i}] ({source})\n{text}")
    return "\n\n---\n\n".join(parts)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------


def main() -> None:
    eval_csv = _resolve_eval_csv()
    output_dir = _resolve_output_dir()
    k = CONFIG["k"]
    collections = CONFIG["collections"]
    es_indexes = CONFIG["es_indexes"] or collections

    logger.info("Eval CSV : %s", eval_csv)
    logger.info("Output   : %s", output_dir)

    df = pd.read_csv(eval_csv)
    required_cols = {"id", "query", "relevant_doc_ids"}
    missing = required_cols - set(df.columns)
    if missing:
        logger.error("Eval CSV missing required columns: %s", missing)
        sys.exit(1)
    logger.info("Loaded %d queries from %s", len(df), eval_csv.name)

    # ------------------------------------------------------------------
    # Initialise Gemini
    # ------------------------------------------------------------------
    gemini_model: Optional[genai.GenerativeModel] = None
    if not CONFIG["skip_generation"]:
        gemini_model = _init_gemini()

    # ------------------------------------------------------------------
    # Load embedding models
    # ------------------------------------------------------------------
    bge_embedder: Optional[BGEm3Embedder] = None
    e5_embedder: Optional[E5MultilingualEmbedder] = None

    if not CONFIG["no_bge"]:
        logger.info("Loading BGE-M3 …")
        bge_embedder = BGEm3Embedder()
        logger.info("BGE-M3 loaded.")

    if not CONFIG["no_e5"]:
        logger.info("Loading E5-multilingual …")
        e5_embedder = E5MultilingualEmbedder()
        logger.info("E5 loaded.")

    if bge_embedder is None or e5_embedder is None:
        logger.error(
            "Both BGE-M3 and E5 embedders are required for hybrid search."
        )
        sys.exit(1)

    # ------------------------------------------------------------------
    # Initialise MultiCollectionSearch
    # ------------------------------------------------------------------
    logger.info(
        "Building MultiCollectionSearch  (collections=%s, vec_w=%.1f, kw_w=%.1f) …",
        collections,
        CONFIG["vector_weight"],
        CONFIG["keyword_weight"],
    )
    try:
        searcher = MultiCollectionSearch.from_collection_names(
            collection_names=collections,
            es_index_names=es_indexes,
            qdrant_host=CONFIG["qdrant_host"],
            qdrant_port=CONFIG["qdrant_port"],
            es_host=CONFIG["es_host"],
            es_port=CONFIG["es_port"],
            vector_weight=CONFIG["vector_weight"],
            keyword_weight=CONFIG["keyword_weight"],
        )
        logger.info("  ✓ MultiCollectionSearch ready.")
    except Exception as exc:
        logger.error("Failed to initialise MultiCollectionSearch: %s", exc)
        sys.exit(1)

    # ------------------------------------------------------------------
    # Per-query evaluation loop
    # ------------------------------------------------------------------
    rows: List[Dict[str, Any]] = []

    for row_idx, row in df.iterrows():
        query = str(row["query"]).strip()
        relevant_ids = _parse_relevant_ids(row.get("relevant_doc_ids", ""))
        row_id = row.get("id", row_idx)

        logger.info("[%d/%d] Query: %r", row_idx + 1, len(df), query[:80])

        # ── 1. Retrieval ─────────────────────────────────────────────────
        t0 = time.perf_counter()
        try:
            bge_vec = bge_embedder.embed_query(query)
            e5_vec = e5_embedder.embed_query(query)
            results = searcher.search(
                query=query,
                bge_m3_query=bge_vec,
                e5_query=e5_vec,
                top_k=CONFIG["top_k"],
                vector_top_k=CONFIG["vector_top_k"],
                keyword_top_k=CONFIG["keyword_top_k"],
                vector_pool_k=CONFIG["vector_pool_k"],
                keyword_pool_k=CONFIG["keyword_pool_k"],
            )
        except Exception as exc:
            logger.warning("  Retrieval failed: %s", exc)
            results = []
        retrieval_latency_ms = round((time.perf_counter() - t0) * 1000, 1)

        # Strip collection prefix  (e.g. "quydinh/abc-def" → "abc-def")
        retrieved_ids = [r["id"].split("/", 1)[-1] for r in results]
        retrieved_scores = [round(r.get("score", 0.0), 4) for r in results]

        # ── 2. Retrieval metrics ─────────────────────────────────────────
        metrics = compute_metrics(retrieved_ids, relevant_ids, k)
        logger.info(
            "  Retrieval  hit@1=%d  hit@%d=%d  P@%d=%.3f  R@%d=%.3f  MRR=%.3f  lat=%.1fms",
            metrics["hit@1"],
            k,
            metrics["hit@k"],
            k,
            metrics["precision@k"],
            k,
            metrics["recall@k"],
            metrics["mrr"],
            retrieval_latency_ms,
        )

        # ── 3. Build context ─────────────────────────────────────────────
        context_str = _format_context(results) if results else ""

        # ── 4. Generate answer ───────────────────────────────────────────
        generated_answer = ""
        generation_latency_ms = 0.0

        if gemini_model is not None and not CONFIG["skip_generation"]:
            if context_str:
                try:
                    generated_answer, generation_latency_ms = (
                        generate_rag_answer(gemini_model, query, context_str)
                    )
                    logger.info(
                        "  Generation  %d chars  lat=%.1fms",
                        len(generated_answer),
                        generation_latency_ms,
                    )
                except Exception as exc:
                    logger.warning("  Generation failed: %s", exc)
            else:
                generated_answer = (
                    "[No context retrieved — answer not generated]"
                )

        # ── 5. Self-evaluation ───────────────────────────────────────────
        eval_result: Dict[str, Any] = {
            "pass": None,
            "relevance": "",
            "faithfulness": "",
            "completeness": "",
            "reason": "",
        }
        self_eval_latency_ms = 0.0

        if (
            gemini_model is not None
            and not CONFIG["skip_self_eval"]
            and generated_answer
            and not generated_answer.startswith("[No context")
        ):
            try:
                eval_result, self_eval_latency_ms = self_evaluate(
                    gemini_model, query, context_str, generated_answer
                )
                logger.info(
                    "  Self-eval   pass=%s  rel=%s  faith=%s  compl=%s  lat=%.1fms",
                    eval_result["pass"],
                    eval_result["relevance"],
                    eval_result["faithfulness"],
                    eval_result["completeness"],
                    self_eval_latency_ms,
                )
            except Exception as exc:
                logger.warning("  Self-eval failed: %s", exc)

        # ── 6. Accumulate row ────────────────────────────────────────────
        rows.append(
            {
                "id": row_id,
                "query": query,
                "query_type": row.get("query_type", ""),
                "difficulty": row.get("difficulty", ""),
                "expected_answer": row.get("expected_answer", ""),
                "relevant_doc_ids": row.get("relevant_doc_ids", ""),
                # Retrieval
                "retrieved_doc_ids": ",".join(retrieved_ids),
                "retrieved_scores": ",".join(str(s) for s in retrieved_scores),
                "retrieval_latency_ms": retrieval_latency_ms,
                # Metrics
                "hit@1": metrics["hit@1"],
                f"hit@{k}": metrics["hit@k"],
                f"precision@{k}": metrics["precision@k"],
                f"recall@{k}": metrics["recall@k"],
                "mrr": metrics["mrr"],
                # Generation
                "generated_answer": generated_answer,
                "generation_latency_ms": generation_latency_ms,
                # Self-eval
                "self_eval_pass": eval_result["pass"],
                "self_eval_relevance": eval_result["relevance"],
                "self_eval_faithfulness": eval_result["faithfulness"],
                "self_eval_completeness": eval_result["completeness"],
                "self_eval_reason": eval_result["reason"],
                "self_eval_latency_ms": self_eval_latency_ms,
            }
        )

    # ------------------------------------------------------------------
    # Save results CSV
    # ------------------------------------------------------------------
    result_df = pd.DataFrame(rows)
    ts = time.strftime("%Y%m%d_%H%M%S")
    out_csv = output_dir / f"phase3_results_{ts}.csv"
    result_df.to_csv(out_csv, index=False)
    logger.info("Results written → %s", out_csv)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    n = len(result_df)
    if n == 0:
        logger.warning("No rows to summarise.")
        return

    logger.info("\n" + "=" * 60)
    logger.info("PHASE 3 EVALUATION SUMMARY  (%d queries)", n)
    logger.info("=" * 60)

    # Retrieval summary
    logger.info(
        "Retrieval  hit@1=%.3f  hit@%d=%.3f  P@%d=%.3f  R@%d=%.3f  MRR=%.3f  avg_lat=%.1fms",
        result_df["hit@1"].mean(),
        k,
        result_df[f"hit@{k}"].mean(),
        k,
        result_df[f"precision@{k}"].mean(),
        k,
        result_df[f"recall@{k}"].mean(),
        result_df["mrr"].mean(),
        result_df["retrieval_latency_ms"].mean(),
    )

    # Generation summary
    if not CONFIG["skip_generation"]:
        answered = result_df[result_df["generated_answer"].str.len() > 0]
        logger.info(
            "Generation  answered=%d/%d  avg_lat=%.1fms",
            len(answered),
            n,
            result_df["generation_latency_ms"].mean(),
        )

    # Self-eval summary
    if not CONFIG["skip_self_eval"]:
        evaluated = result_df[result_df["self_eval_pass"].notna()]
        if len(evaluated):
            pass_rate = evaluated["self_eval_pass"].mean()
            logger.info(
                "Self-eval   evaluated=%d/%d  pass_rate=%.1f%%  avg_lat=%.1fms",
                len(evaluated),
                n,
                pass_rate * 100,
                evaluated["self_eval_latency_ms"].mean(),
            )

            # Breakdown by self_eval_pass
            for val, label in [(True, "PASS"), (False, "FAIL")]:
                count = int((evaluated["self_eval_pass"] == val).sum())
                logger.info(
                    "  %s: %d (%.1f%%)",
                    label,
                    count,
                    count / len(evaluated) * 100,
                )

    logger.info("=" * 60)

    # Save summary CSV
    summary_rows = [
        {
            "metric": "n_queries",
            "value": n,
        },
        {
            "metric": "hit@1",
            "value": round(float(result_df["hit@1"].mean()), 4),
        },
        {
            "metric": f"hit@{k}",
            "value": round(float(result_df[f"hit@{k}"].mean()), 4),
        },
        {
            "metric": f"precision@{k}",
            "value": round(float(result_df[f"precision@{k}"].mean()), 4),
        },
        {
            "metric": f"recall@{k}",
            "value": round(float(result_df[f"recall@{k}"].mean()), 4),
        },
        {"metric": "mrr", "value": round(float(result_df["mrr"].mean()), 4)},
        {
            "metric": "avg_retrieval_latency_ms",
            "value": round(float(result_df["retrieval_latency_ms"].mean()), 1),
        },
    ]
    if not CONFIG["skip_generation"]:
        summary_rows.append(
            {
                "metric": "avg_generation_latency_ms",
                "value": round(
                    float(result_df["generation_latency_ms"].mean()), 1
                ),
            }
        )
    if not CONFIG["skip_self_eval"]:
        evaluated = result_df[result_df["self_eval_pass"].notna()]
        if len(evaluated):
            summary_rows.extend(
                [
                    {
                        "metric": "self_eval_pass_rate",
                        "value": round(
                            float(evaluated["self_eval_pass"].mean()), 4
                        ),
                    },
                    {
                        "metric": "avg_self_eval_latency_ms",
                        "value": round(
                            float(evaluated["self_eval_latency_ms"].mean()), 1
                        ),
                    },
                ]
            )

    summary_df = pd.DataFrame(summary_rows)
    summary_csv = output_dir / f"phase3_summary_{ts}.csv"
    summary_df.to_csv(summary_csv, index=False)
    logger.info("Summary written → %s", summary_csv)


if __name__ == "__main__":
    main()
