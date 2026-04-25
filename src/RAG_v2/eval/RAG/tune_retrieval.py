"""
Hyperparameter Tuner — Grid search tối ưu fusion weights.

Chạy retrieval-only eval (không cần LLM) trên toàn bộ grid → nhanh.

Chạy:
    python eval/tune_retrieval.py

    # Chỉ tune collection ctdt
    python eval/tune_retrieval.py --collection ctdt

    # Tối ưu theo hit_rate thay vì MRR
    python eval/tune_retrieval.py --metric hit_rate

    # Thêm top_k=10 vào grid
    python eval/tune_retrieval.py --extra-topk 10

Env vars:
    QDRANT_HOST/PORT, ES_HOST/PORT — như các scripts khác
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from itertools import product
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
ES_HOST = os.getenv("ES_HOST", "localhost")
ES_PORT = int(os.getenv("ES_PORT", "9200"))

# ─── Search grid ─────────────────────────────────────────────────────────────
# Chỉnh sửa grid này để thêm/bớt giá trị cần sweep
GRID: Dict[str, List[Any]] = {
    "vector_weight":  [0.5, 0.6, 0.7, 0.8],
    "keyword_weight": [0.2, 0.3, 0.4, 0.5],
    "vector_pool_k":  [15, 20, 30],
    "keyword_pool_k": [15, 20, 30],
    "top_k":          [5],
}
# Bỏ qua nếu tổng weight > ngưỡng này
MAX_WEIGHT_SUM = 1.05


# ─── Load dataset ─────────────────────────────────────────────────────────────

def load_items(path: Path, collection: Optional[str]) -> List[Dict]:
    items = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    if collection:
        items = [it for it in items if it["collection"] == collection]
    return items


# ─── Retrieval metrics ────────────────────────────────────────────────────────

def _bare(rid: str) -> str:
    return rid.split("/")[-1] if "/" in rid else rid


def _eval_batch(
    items: List[Dict],
    searcher,
    bge,
    e5,
    top_k: int,
    vector_pool_k: int,
    keyword_pool_k: int,
    active_collections: List[str],
) -> Tuple[float, float]:
    """Trả về (hit_rate, mrr) cho một bộ config."""
    hits, rrs = [], []
    for item in items:
        try:
            bge_vec = bge.embed_query(item["question"])
            e5_vec = e5.embed_query(item["question"])
            retrieved = searcher.search(
                query=item["question"],
                bge_m3_query=bge_vec,
                e5_query=e5_vec,
                top_k=top_k,
                vector_pool_k=vector_pool_k,
                keyword_pool_k=keyword_pool_k,
                active_collections=[item["collection"]],
            )
            ret_ids = [r["id"] for r in retrieved]
            ref = set(item.get("context_ids", []))

            hit = any(_bare(rid) in ref or rid in ref for rid in ret_ids)
            hits.append(float(hit))

            rr = 0.0
            for rank, rid in enumerate(ret_ids, 1):
                if _bare(rid) in ref or rid in ref:
                    rr = 1.0 / rank
                    break
            rrs.append(rr)

        except Exception as e:
            logger.debug("Eval error: %s", e)
            hits.append(0.0)
            rrs.append(0.0)

    n = len(hits)
    return (sum(hits) / n if n else 0.0), (sum(rrs) / n if n else 0.0)


# ─── Grid search ──────────────────────────────────────────────────────────────

def run_grid_search(
    dataset_path: Path,
    filter_collection: Optional[str],
    target_metric: str,
    output_dir: Path,
    extra_topk: Optional[int] = None,
) -> Dict[str, Any]:
    from retrieval.multi_collection_search import MultiCollectionSearch
    from embedding.bge_m3 import BGEm3Embedder
    from embedding.e5_multilingual import E5MultilingualEmbedder

    items = load_items(dataset_path, filter_collection)
    if not items:
        raise ValueError("Không có items.")

    active_collections = list({it["collection"] for it in items})
    grid = GRID.copy()
    if extra_topk and extra_topk not in grid["top_k"]:
        grid["top_k"].append(extra_topk)

    logger.info(
        "Grid search | n=%d | collections=%s | target=%s",
        len(items), active_collections, target_metric,
    )

    logger.info("Loading embedders ...")
    bge = BGEm3Embedder()
    e5 = E5MultilingualEmbedder()

    param_names = list(grid.keys())
    combos = [
        c for c in product(*grid.values())
        if dict(zip(param_names, c))["vector_weight"]
           + dict(zip(param_names, c))["keyword_weight"] <= MAX_WEIGHT_SUM
    ]
    logger.info("Grid: %d combos hợp lệ", len(combos))

    best_score = -1.0
    best_config: Dict[str, Any] = {}
    all_results: List[Dict[str, Any]] = []

    for i, combo in enumerate(combos):
        cfg = dict(zip(param_names, combo))

        try:
            searcher = MultiCollectionSearch.from_collection_names(
                collection_names=active_collections,
                qdrant_host=QDRANT_HOST,
                qdrant_port=QDRANT_PORT,
                es_host=ES_HOST,
                es_port=ES_PORT,
                vector_weight=cfg["vector_weight"],
                keyword_weight=cfg["keyword_weight"],
            )
        except Exception as e:
            logger.error("Searcher init failed: %s", e)
            continue

        t0 = time.perf_counter()
        hit_rate, mrr = _eval_batch(
            items=items,
            searcher=searcher,
            bge=bge,
            e5=e5,
            top_k=cfg["top_k"],
            vector_pool_k=cfg["vector_pool_k"],
            keyword_pool_k=cfg["keyword_pool_k"],
            active_collections=active_collections,
        )
        elapsed = time.perf_counter() - t0

        score = mrr if target_metric == "mrr" else hit_rate
        entry = {
            **cfg,
            "hit_rate": round(hit_rate, 4),
            "mrr": round(mrr, 4),
            "elapsed_s": round(elapsed, 2),
        }
        all_results.append(entry)

        star = " ⭐" if score > best_score else ""
        logger.info(
            "[%d/%d] vw=%.1f kw=%.1f vpk=%d kpk=%d k=%d → hit=%.4f mrr=%.4f (%.1fs)%s",
            i + 1, len(combos),
            cfg["vector_weight"], cfg["keyword_weight"],
            cfg["vector_pool_k"], cfg["keyword_pool_k"], cfg["top_k"],
            hit_rate, mrr, elapsed, star,
        )

        if score > best_score:
            best_score = score
            best_config = {**entry}

    all_results.sort(key=lambda x: x[target_metric], reverse=True)

    summary = {
        "target_metric": target_metric,
        "best_score": round(best_score, 4),
        "best_config": best_config,
        "top_10": all_results[:10],
        "total_tested": len(all_results),
        "n_items": len(items),
        "filter_collection": filter_collection,
        "timestamp": datetime.now().isoformat(),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = output_dir / f"tuning_{ts}.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Results → %s", out)

    # Print report
    print(f"\n{'='*64}")
    print(f"  TUNING RESULTS  (target: {target_metric})")
    print(f"{'='*64}")
    print(f"\n  🏆 Best score: {best_score:.4f}")
    for k in ("vector_weight", "keyword_weight", "vector_pool_k", "keyword_pool_k", "top_k"):
        print(f"     {k:20s}: {best_config.get(k)}")

    print(f"\n  Top 5 configs:")
    header = f"  {'vw':>4} {'kw':>4} {'vpk':>4} {'kpk':>4} {'k':>3} │ {'hit':>7} {'mrr':>7}"
    print(header)
    print("  " + "─" * (len(header) - 2))
    for r in all_results[:5]:
        print(
            f"  {r['vector_weight']:>4.2f} {r['keyword_weight']:>4.2f} "
            f"{r['vector_pool_k']:>4d} {r['keyword_pool_k']:>4d} {r['top_k']:>3d} │ "
            f"{r['hit_rate']:>7.4f} {r['mrr']:>7.4f}"
        )
    print(f"\n{'='*64}\n")

    return summary


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Grid search retrieval hyperparameters")
    parser.add_argument("--dataset", default="eval/data/golden_dataset.jsonl")
    parser.add_argument("--collection", default=None, help="Chỉ tune 1 collection")
    parser.add_argument("--metric", choices=["mrr", "hit_rate"], default="mrr")
    parser.add_argument("--output-dir", default="eval/results")
    parser.add_argument("--extra-topk", type=int, default=None,
                        help="Thêm top_k value vào grid (vd: 10)")
    args = parser.parse_args()

    run_grid_search(
        dataset_path=Path(args.dataset),
        filter_collection=args.collection,
        target_metric=args.metric,
        output_dir=Path(args.output_dir),
        extra_topk=args.extra_topk,
    )


if __name__ == "__main__":
    main()