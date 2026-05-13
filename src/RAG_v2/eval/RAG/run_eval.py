"""
RAGAS Evaluation Runner — Đánh giá chất lượng retrieval và generation.

Metrics:
  Retrieval (không cần LLM, --retrieval-only):
    - hit_rate@K     : % câu hỏi có ≥1 correct doc trong top-K
    - mrr@K          : Mean Reciprocal Rank
    - avg_latency_ms : Latency retrieval trung bình

  Generation (cần LLM judge, full mode):
    - context_precision  : Trong retrieved chunks, bao nhiêu % relevant?
    - context_recall     : Bao nhiêu % thông tin cần đã được retrieved?
    - faithfulness       : Câu trả lời có trung thực với context không?
    - answer_relevancy   : Câu trả lời có trả lời đúng câu hỏi không?

Chạy:
    # Nhanh — chỉ retrieval metrics, không cần LLM
    python eval/run_eval.py --retrieval-only

    # Đầy đủ với LM Studio (Qwen3 8B local)
    python eval/run_eval.py --llm lmstudio

    # Đầy đủ với Gemini
    python eval/run_eval.py --llm gemini

    # Chỉ 1 collection, top-10
    python eval/run_eval.py --retrieval-only --collection ctdt --top-k 10
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
ES_HOST     = os.getenv("ES_HOST", "localhost")
ES_PORT     = int(os.getenv("ES_PORT", "9200"))

DEFAULT_TOP_K = 5


# ─── Result dataclass ─────────────────────────────────────────────────────────


@dataclass
class EvalResult:
    question: str
    collection: str
    question_type: str
    ground_truth: str
    retrieved_ids: List[str]
    retrieved_texts: List[str]
    reference_ids: List[str]

    # Retrieval-only metrics
    hit: bool = False
    reciprocal_rank: float = 0.0
    retrieved_correct_count: int = 0
    retrieval_ms: float = 0.0

    # RAGAS metrics (None nếu --retrieval-only)
    context_precision: Optional[float] = None
    context_recall: Optional[float] = None
    faithfulness: Optional[float] = None
    answer_relevancy: Optional[float] = None
    generated_answer: Optional[str] = None

    # Which LLM backend was used
    llm_backend: str = ""


# ─── Retrieval helpers ────────────────────────────────────────────────────────


def _build_searcher(collections: List[str], vector_weight: float, keyword_weight: float):
    from retrieval.multi_collection_search import MultiCollectionSearch
    return MultiCollectionSearch.from_collection_names(
        collection_names=collections,
        qdrant_host=QDRANT_HOST, qdrant_port=QDRANT_PORT,
        es_host=ES_HOST, es_port=ES_PORT,
        vector_weight=vector_weight, keyword_weight=keyword_weight,
    )


def _build_embedders():
    from embedding.bge_m3 import BGEm3Embedder
    from embedding.e5_multilingual import E5MultilingualEmbedder
    logger.info("Loading BGE-M3 ...")
    bge = BGEm3Embedder()
    logger.info("Loading E5 ...")
    e5 = E5MultilingualEmbedder()
    return bge, e5


def _is_match(retrieved_id: str, reference_ids: set) -> bool:
    """Check match kể cả khi ID có prefix 'collection/'."""
    bare = retrieved_id.split("/")[-1] if "/" in retrieved_id else retrieved_id
    return bare in reference_ids or retrieved_id in reference_ids


def _hit_rate(retrieved_ids: List[str], ref_ids: set) -> bool:
    return any(_is_match(rid, ref_ids) for rid in retrieved_ids)


def _reciprocal_rank(retrieved_ids: List[str], ref_ids: set) -> float:
    for rank, rid in enumerate(retrieved_ids, 1):
        if _is_match(rid, ref_ids):
            return 1.0 / rank
    return 0.0


# ─── RAGAS helpers ────────────────────────────────────────────────────────────


def _ragas_score(
    question: str,
    contexts: List[str],
    generated_answer: str,
    ground_truth: str,
    judge,
) -> Dict[str, float]:
    from datasets import Dataset
    from ragas import evaluate
    from ragas.metrics import (
        context_precision,
        context_recall,
        faithfulness,
        answer_relevancy,
    )
    ds = Dataset.from_dict({
        "question":    [question],
        "contexts":    [contexts],
        "answer":      [generated_answer],
        "ground_truth":[ground_truth],
    })
    result: Any = evaluate(
        dataset=ds,
        metrics=[context_precision, context_recall, faithfulness, answer_relevancy],
        llm=judge.get_ragas_llm(),
        embeddings=judge.get_ragas_embeddings(),
        raise_exceptions=False,
    )
    return {
        "context_precision": float(result["context_precision"]),
        "context_recall":    float(result["context_recall"]),
        "faithfulness":      float(result["faithfulness"]),
        "answer_relevancy":  float(result["answer_relevancy"]),
    }


def _generate_answer(judge, question: str, contexts: List[str]) -> str:
    ctx_str = "\n\n---\n\n".join(contexts[:5])
    prompt = (
        f"Dựa vào các đoạn thông tin sau, trả lời câu hỏi của sinh viên một cách "
        f"ngắn gọn và chính xác. Chỉ dùng thông tin đã cung cấp.\n\n"
        f"Thông tin:\n{ctx_str}\n\n"
        f"Câu hỏi: {question}\n\nTrả lời:"
    )
    try:
        return judge.generate(prompt, max_tokens=512)
    except Exception as e:
        logger.warning("Answer generation failed: %s", e)
        return ""


# ─── Core eval ────────────────────────────────────────────────────────────────


def run_evaluation(
    dataset_path: Path,
    top_k: int = DEFAULT_TOP_K,
    filter_collection: Optional[str] = None,
    retrieval_only: bool = False,
    llm_backend: str = "auto",
    output_dir: Path = Path("eval/results"),
    vector_weight: float = 0.7,
    keyword_weight: float = 0.3,
    lmstudio_url: Optional[str] = None,
    lmstudio_model: Optional[str] = None,
) -> Dict[str, Any]:

    # Load dataset
    items = []
    with open(dataset_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))

    if filter_collection:
        items = [it for it in items if it["collection"] == filter_collection]
    if not items:
        raise ValueError("Dataset trống hoặc không có item nào match filter.")
    logger.info("Loaded %d items (filter_collection=%s)", len(items), filter_collection)

    # Init components
    active_cols = list({it["collection"] for it in items})
    bge, e5 = _build_embedders()
    searcher = _build_searcher(active_cols, vector_weight, keyword_weight)

    # Init LLM judge (chỉ nếu cần RAGAS)
    judge = None
    if not retrieval_only:
        if lmstudio_url:
            os.environ["LMSTUDIO_BASE_URL"] = lmstudio_url
        if lmstudio_model:
            os.environ["LMSTUDIO_MODEL"] = lmstudio_model
        from .llm_judge import LLMJudgeFactory
        judge = LLMJudgeFactory.create(llm_backend)
        logger.info("LLM judge: %s", judge.name)

    # Eval loop
    results: List[EvalResult] = []
    failed = 0

    for idx, item in enumerate(items):
        q = item["question"]
        ref_ids = set(item.get("context_ids", []))
        col = item["collection"]
        logger.info("[%d/%d] [%s] %s", idx + 1, len(items), col, q[:65])

        try:
            bge_vec = bge.embed_query(q)
            e5_vec  = e5.embed_query(q)

            t0 = time.perf_counter()
            retrieved = searcher.search(
                query=q,
                bge_m3_query=bge_vec,
                e5_query=e5_vec,
                top_k=top_k,
                active_collections=[col],
            )
            retrieval_ms = (time.perf_counter() - t0) * 1000

            r_ids   = [r["id"] for r in retrieved]
            r_texts = [r["text"] for r in retrieved]

            result = EvalResult(
                question=q,
                collection=col,
                question_type=item.get("question_type", "factoid"),
                ground_truth=item["ground_truth"],
                retrieved_ids=r_ids,
                retrieved_texts=r_texts,
                reference_ids=list(ref_ids),
                hit=_hit_rate(r_ids, ref_ids),
                reciprocal_rank=_reciprocal_rank(r_ids, ref_ids),
                retrieved_correct_count=sum(_is_match(rid, ref_ids) for rid in r_ids),
                retrieval_ms=retrieval_ms,
                llm_backend=judge.name if judge else "none",
            )

            if not retrieval_only and judge and r_texts:
                answer = _generate_answer(judge, q, r_texts)
                result.generated_answer = answer
                try:
                    scores = _ragas_score(q, r_texts, answer, item["ground_truth"], judge)
                    result.context_precision = scores["context_precision"]
                    result.context_recall    = scores["context_recall"]
                    result.faithfulness      = scores["faithfulness"]
                    result.answer_relevancy  = scores["answer_relevancy"]
                except Exception as e:
                    logger.warning("RAGAS scoring failed: %s", e)
                # Small delay để tránh rate limit khi dùng Gemini
                if "gemini" in judge.name:
                    time.sleep(1.0)

            results.append(result)

        except Exception as e:
            logger.error("Eval failed item %d: %s", idx, e, exc_info=True)
            failed += 1

    summary = _aggregate(results)
    summary["meta"] = {
        "total_items": len(items),
        "evaluated": len(results),
        "failed": failed,
        "top_k": top_k,
        "vector_weight": vector_weight,
        "keyword_weight": keyword_weight,
        "llm_backend": judge.name if judge else "none",
        "retrieval_only": retrieval_only,
        "timestamp": datetime.now().isoformat(),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    _save(results, summary, output_dir)
    _print_summary(summary)
    return summary


# ─── Aggregation ─────────────────────────────────────────────────────────────


def _safe_mean(vals):
    v = [x for x in vals if x is not None]
    return round(sum(v) / len(v), 4) if v else None


def _aggregate(results: List[EvalResult]) -> Dict[str, Any]:
    if not results:
        return {}

    def _col_metrics(rs):
        m = {
            "n": len(rs),
            "hit_rate": _safe_mean([float(r.hit) for r in rs]),
            "mrr":      _safe_mean([r.reciprocal_rank for r in rs]),
            "avg_latency_ms": _safe_mean([r.retrieval_ms for r in rs]),
        }
        if rs[0].context_precision is not None:
            m.update({
                "context_precision": _safe_mean([r.context_precision for r in rs]),
                "context_recall":    _safe_mean([r.context_recall for r in rs]),
                "faithfulness":      _safe_mean([r.faithfulness for r in rs]),
                "answer_relevancy":  _safe_mean([r.answer_relevancy for r in rs]),
            })
        return m

    per_col: Dict[str, list] = defaultdict(list)
    per_type: Dict[str, list] = defaultdict(list)
    for r in results:
        per_col[r.collection].append(r)
        per_type[r.question_type].append(r)

    return {
        "overall": _col_metrics(results),
        "per_collection": {col: _col_metrics(rs) for col, rs in per_col.items()},
        "per_question_type": {qt: _col_metrics(rs) for qt, rs in per_type.items()},
    }


# ─── Save & print ─────────────────────────────────────────────────────────────


def _save(results: List[EvalResult], summary: Dict, output_dir: Path) -> None:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Summary JSON
    sp = output_dir / f"summary_{ts}.json"
    sp.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Summary → %s", sp)

    # CSV per-item
    cp = output_dir / f"results_{ts}.csv"
    fields = [
        "question", "collection", "question_type", "hit", "reciprocal_rank",
        "retrieved_correct_count", "retrieval_ms",
        "context_precision", "context_recall", "faithfulness", "answer_relevancy",
        "ground_truth", "generated_answer", "llm_backend",
    ]
    with open(cp, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in results:
            w.writerow({k: getattr(r, k, "") for k in fields})
    logger.info("CSV → %s", cp)

    # Symlinks "latest"
    for src, dst in [(sp, output_dir/"summary_latest.json"), (cp, output_dir/"results_latest.csv")]:
        try:
            if dst.exists() or dst.is_symlink():
                dst.unlink()
            dst.symlink_to(src.name)
        except OSError:
            pass


def _print_summary(summary: Dict) -> None:
    SEP = "─" * 60
    print(f"\n{'='*60}\nRAGAS EVALUATION SUMMARY\n{'='*60}")

    meta = summary.get("meta", {})
    ov   = summary.get("overall", {})
    print(f"\n📊 OVERALL  (n={meta.get('evaluated','?')} | top_k={meta.get('top_k','?')} | llm={meta.get('llm_backend','?')})")
    print(SEP)
    for label, key in [
        ("Hit Rate@K", "hit_rate"), ("MRR@K", "mrr"), ("Avg Latency (ms)", "avg_latency_ms"),
        ("Context Precision", "context_precision"), ("Context Recall", "context_recall"),
        ("Faithfulness", "faithfulness"), ("Answer Relevancy", "answer_relevancy"),
    ]:
        val = ov.get(key)
        if val is not None:
            print(f"  {label:22s}: {val:.4f}")

    print(f"\n📁 PER COLLECTION\n{SEP}")
    for col, m in summary.get("per_collection", {}).items():
        print(f"\n  [{col}]  n={m['n']}")
        print(f"    Hit={m.get('hit_rate',0):.4f}  MRR={m.get('mrr',0):.4f}  Latency={m.get('avg_latency_ms',0):.0f}ms")
        if m.get("context_precision") is not None:
            print(f"    CtxPrec={m['context_precision']:.4f}  CtxRecall={m['context_recall']:.4f}")
            print(f"    Faith={m['faithfulness']:.4f}  AnsRel={m['answer_relevancy']:.4f}")

    print(f"\n❓ PER QUESTION TYPE\n{SEP}")
    for qt, m in summary.get("per_question_type", {}).items():
        print(f"  {qt:15s}  n={m['n']:3d}  Hit={m.get('hit_rate',0):.4f}  MRR={m.get('mrr',0):.4f}")
    print(f"\n{'='*60}\n")


# ─── CLI ──────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Run RAGAS evaluation")
    parser.add_argument("--dataset", default="eval/data/golden_dataset.jsonl")
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument("--collection", default=None, help="Chỉ eval 1 collection")
    parser.add_argument(
        "--retrieval-only", action="store_true",
        help="Chỉ đo hit_rate + MRR, bỏ qua RAGAS LLM metrics",
    )
    parser.add_argument(
        "--llm", choices=["gemini", "lmstudio", "auto"], default="auto",
        help="LLM judge backend (chỉ dùng khi không --retrieval-only)",
    )
    parser.add_argument("--output-dir", default="eval/results")
    parser.add_argument("--vector-weight", type=float, default=0.7)
    parser.add_argument("--keyword-weight", type=float, default=0.3)
    parser.add_argument("--lmstudio-url", default=None)
    parser.add_argument("--lmstudio-model", default=None)
    args = parser.parse_args()

    run_evaluation(
        dataset_path=Path(args.dataset),
        top_k=args.top_k,
        filter_collection=args.collection,
        retrieval_only=args.retrieval_only,
        llm_backend=args.llm,
        output_dir=Path(args.output_dir),
        vector_weight=args.vector_weight,
        keyword_weight=args.keyword_weight,
        lmstudio_url=args.lmstudio_url,
        lmstudio_model=args.lmstudio_model,
    )


if __name__ == "__main__":
    main()