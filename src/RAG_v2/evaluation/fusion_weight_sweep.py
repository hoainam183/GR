"""Fusion Weight Sweep — find optimal vector/keyword weight combination.

Systematically evaluates different vector_weight / keyword_weight ratios
against a golden dataset to find the combination that maximizes retrieval
quality metrics (nDCG@10, MRR@10, Recall@50).

Usage from ``src/RAG_v2``::

    python evaluation/fusion_weight_sweep.py
    python evaluation/fusion_weight_sweep.py --steps 11
    python evaluation/fusion_weight_sweep.py --output evaluation/fusion_sweep_results.json

Requires: working Qdrant + Elasticsearch + embedding models.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import Settings


@dataclass
class SweepResult:
    vector_weight: float
    keyword_weight: float
    ndcg_at_10: float = 0.0
    mrr_at_10: float = 0.0
    recall_at_50: float = 0.0
    avg_latency_ms: float = 0.0
    num_queries: int = 0

    @property
    def combined_score(self) -> float:
        """Weighted combination: 50% nDCG + 30% MRR + 20% Recall."""
        return 0.5 * self.ndcg_at_10 + 0.3 * self.mrr_at_10 + 0.2 * self.recall_at_50

    def to_dict(self) -> Dict[str, Any]:
        return {
            "vector_weight": round(self.vector_weight, 2),
            "keyword_weight": round(self.keyword_weight, 2),
            "ndcg_at_10": round(self.ndcg_at_10, 4),
            "mrr_at_10": round(self.mrr_at_10, 4),
            "recall_at_50": round(self.recall_at_50, 4),
            "combined_score": round(self.combined_score, 4),
            "avg_latency_ms": round(self.avg_latency_ms, 1),
            "num_queries": self.num_queries,
        }


def _load_golden_dataset(path: Path) -> List[Dict[str, Any]]:
    """Load golden test cases."""
    if not path.exists():
        raise FileNotFoundError(f"Golden dataset not found: {path}")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        for key in ("cases", "test_cases", "rows"):
            if key in data:
                return data[key]
    if isinstance(data, list):
        return data
    raise ValueError(f"Cannot parse golden dataset: {path}")


def _get_expected_ids(case: Dict[str, Any]) -> List[str]:
    """Extract expected document IDs from a test case."""
    raw = case.get("expected_source_ids") or case.get("relevant_doc_ids") or []
    if isinstance(raw, str):
        raw = [p.strip() for p in raw.replace(";", ",").split(",")]
    if not isinstance(raw, list):
        return []
    results = []
    for item in raw:
        text = str(item).strip()
        if "/" in text:
            text = text.split("/", 1)[-1]
        if text:
            results.append(text)
    return results


def _dcg(relevances: List[float], k: int) -> float:
    """Discounted Cumulative Gain at k."""
    total = 0.0
    for i, rel in enumerate(relevances[:k]):
        total += rel / math.log2(i + 2)
    return total


def _ndcg_at_k(ranked_ids: List[str], expected_ids: List[str], k: int = 10) -> float:
    """Normalized DCG at k (binary relevance)."""
    if not expected_ids:
        return 0.0
    expected_set = set(expected_ids)
    relevances = [1.0 if rid in expected_set else 0.0 for rid in ranked_ids[:k]]
    ideal = sorted(relevances, reverse=True)
    dcg = _dcg(relevances, k)
    idcg = _dcg(ideal, k)
    if idcg == 0:
        # If we have expected IDs but none in top-k, compute ideal from expected count
        ideal_full = [1.0] * min(len(expected_ids), k)
        idcg = _dcg(ideal_full, k)
    return dcg / idcg if idcg > 0 else 0.0


def _mrr_at_k(ranked_ids: List[str], expected_ids: List[str], k: int = 10) -> float:
    """Mean Reciprocal Rank at k."""
    if not expected_ids:
        return 0.0
    expected_set = set(expected_ids)
    for i, rid in enumerate(ranked_ids[:k]):
        if rid in expected_set:
            return 1.0 / (i + 1)
    return 0.0


def _recall_at_k(ranked_ids: List[str], expected_ids: List[str], k: int = 50) -> float:
    """Recall at k."""
    if not expected_ids:
        return 0.0
    expected_set = set(expected_ids)
    found = sum(1 for rid in ranked_ids[:k] if rid in expected_set)
    return found / len(expected_set)


def run_sweep(
    steps: int = 11,
    golden_path: Path | None = None,
    output_path: Path | None = None,
) -> List[SweepResult]:
    """Run the fusion weight sweep.

    Args:
        steps: Number of weight steps (e.g. 11 → 0.0, 0.1, ..., 1.0)
        golden_path: Path to golden dataset JSON.
        output_path: Path to save results JSON.

    Returns:
        List of SweepResult sorted by combined_score descending.
    """
    from retrieval.multi_collection_search import MultiCollectionSearch
    from retrieval.service import RetrievalService

    golden_path = golden_path or (PROJECT_ROOT / "eval" / "golden_dataset.json")
    output_path = output_path or (PROJECT_ROOT / "evaluation" / "fusion_sweep_results.json")

    cases = _load_golden_dataset(golden_path)
    print(f"Loaded {len(cases)} test cases from {golden_path}")

    settings = Settings()
    service = RetrievalService.from_settings(settings)

    results: List[SweepResult] = []

    for step in range(steps):
        vector_w = round(step / (steps - 1), 2)
        keyword_w = round(1.0 - vector_w, 2)

        # Override weights in settings
        settings.vector_weight = vector_w
        settings.keyword_weight = keyword_w

        print(f"\n--- Testing vector={vector_w:.2f}, keyword={keyword_w:.2f} ---")

        sweep_result = SweepResult(
            vector_weight=vector_w,
            keyword_weight=keyword_w,
        )

        ndcg_scores: List[float] = []
        mrr_scores: List[float] = []
        recall_scores: List[float] = []
        latencies: List[float] = []

        for case in cases:
            query = case.get("query", "")
            expected = _get_expected_ids(case)
            if not query or not expected:
                continue

            collections = case.get("collections") or ["stsv", "quydinh", "kehoach", "ctdt"]

            t0 = time.perf_counter()
            try:
                search_results = service.search(
                    query=query,
                    collection_names=collections,
                    top_k=50,
                )
            except Exception as exc:
                print(f"  Error for query '{query[:40]}...': {exc}")
                continue
            elapsed_ms = (time.perf_counter() - t0) * 1000
            latencies.append(elapsed_ms)

            ranked_ids = []
            for r in search_results:
                raw_id = str(r.get("id", ""))
                if "/" in raw_id:
                    raw_id = raw_id.split("/", 1)[-1]
                ranked_ids.append(raw_id)

            ndcg_scores.append(_ndcg_at_k(ranked_ids, expected))
            mrr_scores.append(_mrr_at_k(ranked_ids, expected))
            recall_scores.append(_recall_at_k(ranked_ids, expected))

        if ndcg_scores:
            sweep_result.ndcg_at_10 = sum(ndcg_scores) / len(ndcg_scores)
            sweep_result.mrr_at_10 = sum(mrr_scores) / len(mrr_scores)
            sweep_result.recall_at_50 = sum(recall_scores) / len(recall_scores)
            sweep_result.avg_latency_ms = sum(latencies) / len(latencies) if latencies else 0
            sweep_result.num_queries = len(ndcg_scores)

        print(
            f"  nDCG@10={sweep_result.ndcg_at_10:.4f}  "
            f"MRR@10={sweep_result.mrr_at_10:.4f}  "
            f"Recall@50={sweep_result.recall_at_50:.4f}  "
            f"Combined={sweep_result.combined_score:.4f}  "
            f"Latency={sweep_result.avg_latency_ms:.0f}ms"
        )
        results.append(sweep_result)

    # Sort by combined score
    results.sort(key=lambda r: r.combined_score, reverse=True)

    # Save results
    output_data = {
        "sweep_config": {"steps": steps, "metric": "0.5*nDCG + 0.3*MRR + 0.2*Recall"},
        "best": results[0].to_dict() if results else None,
        "all_results": [r.to_dict() for r in results],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to {output_path}")

    if results:
        best = results[0]
        print(f"\n{'='*60}")
        print(f"BEST: vector={best.vector_weight:.2f}, keyword={best.keyword_weight:.2f}")
        print(f"  nDCG@10={best.ndcg_at_10:.4f}  MRR@10={best.mrr_at_10:.4f}  "
              f"Recall@50={best.recall_at_50:.4f}")
        print(f"  Combined Score={best.combined_score:.4f}")
        print(f"{'='*60}")
        print(f"\nRecommendation: set vector_weight={best.vector_weight} "
              f"and keyword_weight={best.keyword_weight} in .env or config/settings.py")

    return results


def main():
    parser = argparse.ArgumentParser(description="Fusion weight sweep")
    parser.add_argument("--steps", type=int, default=11, help="Number of weight steps (default: 11)")
    parser.add_argument("--golden", type=str, default=None, help="Path to golden dataset")
    parser.add_argument("--output", type=str, default=None, help="Path for output JSON")
    args = parser.parse_args()

    golden = Path(args.golden) if args.golden else None
    output = Path(args.output) if args.output else None

    run_sweep(steps=args.steps, golden_path=golden, output_path=output)


if __name__ == "__main__":
    main()
