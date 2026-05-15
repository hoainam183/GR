"""Evaluate the current retrieval pipeline against the golden dataset.

This runner measures the production retrieval stack, not isolated experiments:
Settings -> RetrievalService/create_retriever -> QueryRouter/CollectionSelector
-> MultiCollectionSearch -> configured reranker.

Usage from ``src/RAG_v2``:
    python3 evaluation/evaluate_current_pipeline.py
    python3 evaluation/evaluate_current_pipeline.py --golden eval/golden_dataset.json --k 5
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import Settings
from query.router import QueryRouter
from retrieval.collection_selector import CollectionSelector
from retrieval.service import RetrievalService


def _raw_id(value: Any) -> str:
    text = str(value or "").strip()
    return text.split("/", 1)[-1] if "/" in text else text


def _expected_ids(case: Dict[str, Any]) -> set[str]:
    raw = case.get("expected_source_ids") or case.get("relevant_doc_ids") or []
    if isinstance(raw, str):
        raw = [part.strip() for part in raw.replace(";", ",").split(",")]
    if not isinstance(raw, list):
        return set()
    return {_raw_id(item) for item in raw if _raw_id(item)}


def _retrieved_ids(results: Iterable[Dict[str, Any]]) -> List[str]:
    return [_raw_id(row.get("id")) for row in results if _raw_id(row.get("id"))]


def _result_collections(results: Iterable[Dict[str, Any]]) -> set[str]:
    out: set[str] = set()
    for row in results:
        meta = row.get("metadata") or {}
        collection = row.get("collection") or meta.get("collection")
        if collection:
            out.add(str(collection))
    return out


def _keyword_hit(results: Iterable[Dict[str, Any]], keywords: List[str]) -> bool:
    if not keywords:
        return False
    haystack = "\n".join(
        f"{row.get('text') or row.get('content') or ''}\n{row.get('metadata') or {}}"
        for row in results
    ).lower()
    return all(str(keyword).lower() in haystack for keyword in keywords)


def _recall_at_k(retrieved: List[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    return len(set(retrieved[:k]) & relevant) / len(relevant)


def _mrr_at_k(retrieved: List[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    for rank, doc_id in enumerate(retrieved[:k], start=1):
        if doc_id in relevant:
            return 1.0 / rank
    return 0.0


def _ndcg_at_k(retrieved: List[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    dcg = 0.0
    for rank, doc_id in enumerate(retrieved[:k], start=1):
        if doc_id in relevant:
            dcg += 1.0 / math.log2(rank + 1)
    ideal_hits = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
    return dcg / idcg if idcg else 0.0


def _percentile(values: List[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = int(math.ceil((pct / 100.0) * len(ordered))) - 1
    index = max(0, min(index, len(ordered) - 1))
    return ordered[index]


def _load_retrieval_cases(path: Path) -> List[Dict[str, Any]]:
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    cases = data.get("test_cases", []) if isinstance(data, dict) else data
    return [
        case
        for case in cases
        if isinstance(case, dict) and case.get("category") == "retrieval"
    ]


def _route_collections(
    *,
    router: QueryRouter,
    selector: CollectionSelector,
    query: str,
) -> tuple[List[str], Dict[str, Any]]:
    try:
        routed = router.route(query)
        domain = routed.get("domain")
        domains = routed.get("domains") or ([domain] if domain else [])
        collections = selector.select(
            domain=domain,
            domains=domains,
            confidence=float(routed.get("confidence", 0.0) or 0.0),
        )
        return collections, routed
    except Exception as exc:
        return [], {"error": str(exc)}


def _search_once(
    *,
    service: RetrievalService,
    query: str,
    collections: Optional[List[str]],
    k: int,
) -> tuple[List[Dict[str, Any]], Dict[str, float]]:
    timings: Dict[str, float] = {}

    t0 = time.perf_counter()
    bge_vec = service.bge_embedder.embed_query(query)
    timings["embed_bge_ms"] = round((time.perf_counter() - t0) * 1000, 2)

    t0 = time.perf_counter()
    e5_vec = service.e5_embedder.embed_query(query)
    timings["embed_e5_ms"] = round((time.perf_counter() - t0) * 1000, 2)

    raw_candidate_k = max(k * 4, 40)
    t0 = time.perf_counter()
    candidates = service.searcher.search(
        query=query,
        bge_m3_query=bge_vec,
        e5_query=e5_vec,
        top_k=raw_candidate_k,
        vector_top_k=service.settings.vector_top_k,
        keyword_top_k=service.settings.keyword_top_k,
        vector_pool_k=service.settings.vector_pool_k,
        keyword_pool_k=service.settings.keyword_pool_k,
        active_collections=collections or None,
    )
    timings["search_ms"] = round((time.perf_counter() - t0) * 1000, 2)

    if service.reranker is None:
        return candidates[:k], timings

    t0 = time.perf_counter()
    reranked = service.reranker.rerank(query=query, documents=candidates, top_k=k)
    timings["rerank_ms"] = round((time.perf_counter() - t0) * 1000, 2)
    return reranked, timings


def evaluate(golden_path: Path, k: int, output_path: Optional[Path]) -> Dict[str, Any]:
    settings = Settings()
    service = RetrievalService.from_settings(settings)
    router = QueryRouter(mode=settings.router_mode, embedder=service.bge_embedder)
    selector = CollectionSelector()

    cases = _load_retrieval_cases(golden_path)
    rows: List[Dict[str, Any]] = []
    latencies: List[float] = []
    stage_latencies: Dict[str, List[float]] = {}

    for case in cases:
        query = str(case.get("query", "")).strip()
        expected_collection = str(case.get("expected_collection", "") or "")
        expected_keywords = case.get("expected_keywords") or []
        expected_ids = _expected_ids(case)

        collections, routed = _route_collections(
            router=router,
            selector=selector,
            query=query,
        )

        t0 = time.perf_counter()
        results, timings = _search_once(
            service=service,
            query=query,
            collections=collections,
            k=k,
        )
        total_ms = round((time.perf_counter() - t0) * 1000, 2)
        latencies.append(total_ms)
        for stage, value in timings.items():
            stage_latencies.setdefault(stage, []).append(value)

        retrieved_ids = _retrieved_ids(results)
        result_collections = _result_collections(results)
        collection_hit = (
            expected_collection in result_collections if expected_collection else False
        )
        keyword_hit = _keyword_hit(results, list(expected_keywords))

        row = {
            "id": case.get("id"),
            "query": query,
            "routed": routed,
            "target_collections": collections,
            "expected_collection": expected_collection,
            "retrieved_collections": sorted(result_collections),
            "collection_hit": collection_hit,
            "keyword_hit": keyword_hit,
            "expected_source_ids": sorted(expected_ids),
            "retrieved_ids": retrieved_ids,
            "recall_at_k": _recall_at_k(retrieved_ids, expected_ids, k),
            "mrr_at_k": _mrr_at_k(retrieved_ids, expected_ids, k),
            "ndcg_at_k": _ndcg_at_k(retrieved_ids, expected_ids, k),
            "latency_ms": total_ms,
            "timings_ms": timings,
        }
        rows.append(row)

    source_rows = [row for row in rows if row["expected_source_ids"]]
    summary = {
        "golden": str(golden_path),
        "k": k,
        "n_cases": len(rows),
        "n_source_labeled_cases": len(source_rows),
        "collection_accuracy": (
            sum(1 for row in rows if row["collection_hit"]) / len(rows)
            if rows else 0.0
        ),
        "keyword_hit_rate": (
            sum(1 for row in rows if row["keyword_hit"]) / len(rows)
            if rows else 0.0
        ),
        "recall_at_k": (
            sum(row["recall_at_k"] for row in source_rows) / len(source_rows)
            if source_rows else 0.0
        ),
        "mrr_at_k": (
            sum(row["mrr_at_k"] for row in source_rows) / len(source_rows)
            if source_rows else 0.0
        ),
        "ndcg_at_k": (
            sum(row["ndcg_at_k"] for row in source_rows) / len(source_rows)
            if source_rows else 0.0
        ),
        "latency_p50_ms": _percentile(latencies, 50),
        "latency_p95_ms": _percentile(latencies, 95),
        "stage_latency_p50_ms": {
            stage: _percentile(values, 50)
            for stage, values in stage_latencies.items()
        },
        "stage_latency_p95_ms": {
            stage: _percentile(values, 95)
            for stage, values in stage_latencies.items()
        },
    }
    payload = {"summary": summary, "rows": rows}

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)

    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--golden",
        type=Path,
        default=PROJECT_ROOT / "eval" / "golden_dataset.json",
    )
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "evaluation" / "current_pipeline_results.json",
    )
    args = parser.parse_args()

    payload = evaluate(args.golden, args.k, args.output)
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    if args.output:
        print(f"Wrote detailed results to {args.output}")


if __name__ == "__main__":
    main()
