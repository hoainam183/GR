"""Reranker threshold calibration.

Runs real queries (with evidence_chunk_id labels) through hybrid retrieval, then
reranks the candidate pool PERMISSIVELY (no threshold) so every candidate keeps
its raw rerank logit. Labels each candidate relevant/irrelevant by evidence id
and reports the score distribution + a threshold grid, so a production
``reranker_score_threshold`` can be chosen from data rather than guessed.

Run from src/RAG_v2:
    python evaluation/reranker_threshold_calib.py --max-queries 24 --pool 20
"""

from __future__ import annotations

import argparse
import ast
import glob
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import Settings

ALL_COLLECTIONS = ["stsv", "quydinh", "kehoach", "ctdt"]
# A diverse spread across regulation / curriculum / schedule / support datasets.
DATASET_GLOBS = [
    "qd_hoc_bong_kkht_2023_rag_eval_dataset_30.json",
    "qcdt_2025_5445_qd_dhbk_rag_eval_dataset_30.json",
    "qd_ngoai_ngu_tu_k68_cq_rag_eval_dataset_30.json",
    "ITE6_rag_evaluation_dataset_no_parent_evidence.json",
    "IT2_rag_evaluation_dataset_no_parent_evidence.json",
    "ky_thuat_co_khi_rag_eval_dataset_30.json",
    "kehoach_list_all_chunks_rag_eval_dataset_100.json",
    "chinh_sach_ho_tro_sv_khuyet_tat_rag_eval_dataset_30.json",
]


def _strip_id(raw: str) -> str:
    text = str(raw).strip()
    return text.split("/", 1)[-1] if "/" in text else text


def _parse_evidence(value: Any) -> set[str]:
    if isinstance(value, list):
        items = value
    else:
        try:
            items = ast.literal_eval(str(value))
        except Exception:
            items = []
    return {_strip_id(x) for x in items if str(x).strip()}


def _load_queries(per_dataset: int) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    base = PROJECT_ROOT / "evaluation" / "data"
    for name in DATASET_GLOBS:
        for path in glob.glob(str(base / name)):
            try:
                data = json.load(open(path, encoding="utf-8"))
            except Exception:
                continue
            items = data.get("items", data) if isinstance(data, dict) else data
            picked = 0
            for it in items:
                ev = _parse_evidence(it.get("evidence_chunk_ids"))
                q = str(it.get("question") or "").strip()
                if not q or not ev:
                    continue
                if str(it.get("is_answerable", "True")).lower() == "false":
                    continue
                out.append({"question": q, "evidence": ev, "src": Path(path).name})
                picked += 1
                if picked >= per_dataset:
                    break
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-queries", type=int, default=24)
    ap.add_argument("--per-dataset", type=int, default=3)
    ap.add_argument("--pool", type=int, default=20, help="fused candidate pool size per query")
    ap.add_argument("--output", default="evaluation/reranker_calib_results.json")
    args = ap.parse_args()

    from retrieval.service import RetrievalService

    settings = Settings()
    service = RetrievalService.from_settings(settings)
    if service.reranker is None:
        print("No reranker configured; aborting.")
        return

    queries = _load_queries(args.per_dataset)[: args.max_queries]
    print(f"Calibrating on {len(queries)} labelled queries (pool={args.pool})")

    samples: List[Dict[str, Any]] = []  # {score, relevant, src}
    relevant_in_pool = 0
    relevant_total_pooled = 0

    for i, case in enumerate(queries):
        q = case["question"]
        try:
            cands = service.search(
                q, collections=ALL_COLLECTIONS, top_k=args.pool, rerank=False
            )
            scored = service.reranker.rerank(
                q, cands, top_k=len(cands),
                score_threshold=-1e9, table_score_threshold=-1e9,
            )
        except Exception as exc:
            print(f"  [{i}] error: {exc}")
            continue
        pooled_rel = 0
        for d in scored:
            rid = _strip_id(d.get("id", ""))
            rel = rid in case["evidence"]
            if rel:
                pooled_rel += 1
            samples.append(
                {"score": float(d.get("rerank_score", 0.0)), "relevant": rel, "src": case["src"]}
            )
        relevant_total_pooled += pooled_rel
        relevant_in_pool += 1 if pooled_rel else 0
        print(f"  [{i+1}/{len(queries)}] {pooled_rel} relevant in pool | {q[:55]}")

    rel_scores = sorted(s["score"] for s in samples if s["relevant"])
    irr_scores = sorted(s["score"] for s in samples if not s["relevant"])

    def pct(xs: List[float], p: float) -> float:
        if not xs:
            return float("nan")
        k = max(0, min(len(xs) - 1, int(round(p / 100.0 * (len(xs) - 1)))))
        return round(xs[k], 3)

    # Threshold grid: for each t, recall of relevant docs (kept/total relevant in
    # pool) and precision among kept docs.
    grid = [round(t, 2) for t in [-1.0, -0.5, 0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]]
    grid_rows = []
    n_rel = len(rel_scores)
    for t in grid:
        kept = [s for s in samples if s["score"] >= t]
        kept_rel = sum(1 for s in kept if s["relevant"])
        recall = kept_rel / n_rel if n_rel else 0.0
        precision = kept_rel / len(kept) if kept else 0.0
        grid_rows.append({
            "threshold": t,
            "recall_relevant": round(recall, 3),
            "precision_kept": round(precision, 3),
            "kept_total": len(kept),
        })

    report = {
        "n_queries": len(queries),
        "relevant_pooled_total": relevant_total_pooled,
        "queries_with_relevant_in_pool": relevant_in_pool,
        "relevant_scores": {
            "n": n_rel, "min": pct(rel_scores, 0), "p10": pct(rel_scores, 10),
            "p25": pct(rel_scores, 25), "median": pct(rel_scores, 50),
            "p75": pct(rel_scores, 75), "max": pct(rel_scores, 100),
        },
        "irrelevant_scores": {
            "n": len(irr_scores), "p50": pct(irr_scores, 50),
            "p75": pct(irr_scores, 75), "p90": pct(irr_scores, 90),
            "p95": pct(irr_scores, 95), "max": pct(irr_scores, 100),
        },
        "threshold_grid": grid_rows,
    }
    out = PROJECT_ROOT / args.output
    json.dump(report, open(out, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print("\n=== RELEVANT score percentiles ===", report["relevant_scores"])
    print("=== IRRELEVANT score percentiles ===", report["irrelevant_scores"])
    print("=== threshold grid (recall_rel / precision / kept) ===")
    for r in grid_rows:
        print(f"  t={r['threshold']:>5}  recall={r['recall_relevant']:.3f}  "
              f"precision={r['precision_kept']:.3f}  kept={r['kept_total']}")
    print(f"\nSaved -> {out}")


if __name__ == "__main__":
    main()
