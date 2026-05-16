"""Evaluate the current retrieval pipeline against the golden dataset.

This runner measures the production retrieval stack, not isolated experiments:
Settings -> RetrievalService/create_retriever -> QueryRouter/CollectionSelector
-> MultiCollectionSearch -> configured reranker.

Usage from ``src/RAG_v2``:
    python3 evaluation/evaluate_current_pipeline.py
    python3 evaluation/evaluate_current_pipeline.py --golden eval/golden_dataset.json --k 10
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
from evaluation.eval_schemas import load_relevance_labels
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


def _compact_sources(results: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in results:
        meta = dict(row.get("metadata") or {})
        out.append(
            {
                "id": row.get("id"),
                "collection": row.get("collection") or meta.get("collection"),
                "score": row.get("rerank_score", row.get("score", 0.0)),
                "text": str(row.get("text") or row.get("content") or "")[:1500],
                "metadata": {
                    key: meta.get(key)
                    for key in (
                        "source",
                        "filename",
                        "source_file",
                        "document_id",
                        "doc_id",
                        "doc_title",
                        "title",
                        "major_code",
                        "applicable_cohort",
                        "date_str",
                    )
                    if meta.get(key) is not None
                },
            }
        )
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


def _precision_at_k(retrieved: List[str], relevant: set[str], k: int) -> float:
    if not relevant or k <= 0:
        return 0.0
    return len(set(retrieved[:k]) & relevant) / min(k, len(retrieved[:k]) or k)


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


def _graded_ndcg_at_k(retrieved: List[str], labels: Dict[str, int], k: int) -> float:
    if not labels:
        return 0.0
    gains = [max(0, int(labels.get(_raw_id(doc_id), 0))) for doc_id in retrieved[:k]]
    ideal = sorted((max(0, int(value)) for value in labels.values()), reverse=True)
    idcg = sum(((2**gain) - 1) / math.log2(rank + 1) for rank, gain in enumerate(ideal[:k], start=1))
    if not idcg:
        return 0.0
    dcg = sum(((2**gain) - 1) / math.log2(rank + 1) for rank, gain in enumerate(gains, start=1))
    return dcg / idcg


def _graded_mrr_at_k(retrieved: List[str], labels: Dict[str, int], k: int) -> float:
    if not labels:
        return 0.0
    for rank, doc_id in enumerate(retrieved[:k], start=1):
        if int(labels.get(_raw_id(doc_id), 0)) > 0:
            return 1.0 / rank
    return 0.0


def _graded_recall_at_k(retrieved: List[str], labels: Dict[str, int], k: int) -> float:
    relevant = {doc_id for doc_id, relevance in labels.items() if int(relevance) > 0}
    if not relevant:
        return 0.0
    retrieved_raw = {_raw_id(doc_id) for doc_id in retrieved[:k]}
    return len(retrieved_raw & relevant) / len(relevant)


def _graded_precision_at_k(retrieved: List[str], labels: Dict[str, int], k: int) -> float:
    relevant = {doc_id for doc_id, relevance in labels.items() if int(relevance) > 0}
    if not relevant or k <= 0:
        return 0.0
    retrieved_top = [_raw_id(doc_id) for doc_id in retrieved[:k]]
    return len(set(retrieved_top) & relevant) / min(k, len(retrieved_top) or k)


def _percentile(values: List[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = int(math.ceil((pct / 100.0) * len(ordered))) - 1
    index = max(0, min(index, len(ordered) - 1))
    return ordered[index]


def _load_retrieval_cases(path: Path, max_cases: int = 0) -> List[Dict[str, Any]]:
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    cases = data.get("test_cases", []) if isinstance(data, dict) else data
    out = [
        case
        for case in cases
        if isinstance(case, dict) and case.get("category") == "retrieval"
    ]
    return out[:max_cases] if max_cases else out


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
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, float]]:
    timings: Dict[str, float] = {}

    t0 = time.perf_counter()
    bge_vec = service.bge_embedder.embed_query(query)
    timings["embed_bge_ms"] = round((time.perf_counter() - t0) * 1000, 2)

    t0 = time.perf_counter()
    e5_vec = service.e5_embedder.embed_query(query)
    timings["embed_e5_ms"] = round((time.perf_counter() - t0) * 1000, 2)

    raw_candidate_k = max(k * 4, 50)
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
        return candidates[:k], candidates[:50], timings

    t0 = time.perf_counter()
    reranked = service.reranker.rerank(query=query, documents=candidates, top_k=k)
    timings["rerank_ms"] = round((time.perf_counter() - t0) * 1000, 2)
    return reranked, candidates[:50], timings


def evaluate(
    golden_path: Path,
    k: int,
    output_path: Optional[Path],
    max_cases: int = 0,
    labels_path: Optional[Path] = None,
) -> Dict[str, Any]:
    settings = Settings()
    service = RetrievalService.from_settings(settings)
    router = QueryRouter(mode=settings.router_mode, embedder=service.bge_embedder)
    selector = CollectionSelector()

    cases = _load_retrieval_cases(golden_path, max_cases=max_cases)
    relevance_labels = load_relevance_labels(labels_path)
    rows: List[Dict[str, Any]] = []
    latencies: List[float] = []
    stage_latencies: Dict[str, List[float]] = {}

    for case in cases:
        query = str(case.get("query", "")).strip()
        expected_collection = str(case.get("expected_collection", "") or "")
        expected_keywords = case.get("expected_keywords") or []
        expected_ids = _expected_ids(case)
        case_labels = relevance_labels.get(str(case.get("id") or ""), {})

        collections, routed = _route_collections(
            router=router,
            selector=selector,
            query=query,
        )

        t0 = time.perf_counter()
        results, raw_results, timings = _search_once(
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
        raw_retrieved_ids = _retrieved_ids(raw_results)
        result_collections = _result_collections(results)
        collection_hit = (
            expected_collection in result_collections if expected_collection else False
        )
        keyword_hit = _keyword_hit(results, list(expected_keywords))

        if case_labels:
            recall_at_k = _graded_recall_at_k(retrieved_ids, case_labels, k)
            raw_recall_at_50 = _graded_recall_at_k(raw_retrieved_ids, case_labels, 50)
            context_precision = _graded_precision_at_k(retrieved_ids, case_labels, k)
            context_recall = recall_at_k
            mrr_at_k = _graded_mrr_at_k(retrieved_ids, case_labels, k)
            ndcg_at_k = _graded_ndcg_at_k(retrieved_ids, case_labels, k)
            relevant_count = sum(1 for rel in case_labels.values() if rel > 0)
            rel2_count = sum(1 for rel in case_labels.values() if rel >= 2)
            metric_source = "relevance_labels"
        else:
            recall_at_k = _recall_at_k(retrieved_ids, expected_ids, k)
            raw_recall_at_50 = _recall_at_k(raw_retrieved_ids, expected_ids, 50)
            context_precision = _precision_at_k(retrieved_ids, expected_ids, k)
            context_recall = recall_at_k
            mrr_at_k = _mrr_at_k(retrieved_ids, expected_ids, k)
            ndcg_at_k = _ndcg_at_k(retrieved_ids, expected_ids, k)
            relevant_count = len(expected_ids)
            rel2_count = len(expected_ids)
            metric_source = "expected_source_ids"

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
            "label_count": len(case_labels),
            "relevant_count": relevant_count,
            "rel2_count": rel2_count,
            "metric_source": metric_source,
            "retrieved_ids": retrieved_ids,
            "raw_retrieved_ids": raw_retrieved_ids,
            "sources": _compact_sources(results),
            "recall_at_k": recall_at_k,
            "raw_recall_at_50": raw_recall_at_50,
            "context_precision": context_precision,
            "context_recall": context_recall,
            "mrr_at_k": mrr_at_k,
            "ndcg_at_k": ndcg_at_k,
            "latency_ms": total_ms,
            "timings_ms": timings,
        }
        rows.append(row)

    source_rows = [
        row for row in rows
        if row["expected_source_ids"] or row.get("label_count", 0) > 0
    ]
    summary = {
        "golden": str(golden_path),
        "labels": str(labels_path) if labels_path else None,
        "k": k,
        "n_cases": len(rows),
        "n_source_labeled_cases": len(source_rows),
        "n_relevance_labeled_cases": sum(1 for row in rows if row.get("label_count", 0) > 0),
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
        "raw_recall_at_50": (
            sum(row["raw_recall_at_50"] for row in source_rows) / len(source_rows)
            if source_rows else 0.0
        ),
        "context_precision": (
            sum(row["context_precision"] for row in source_rows) / len(source_rows)
            if source_rows else 0.0
        ),
        "context_recall": (
            sum(row["context_recall"] for row in source_rows) / len(source_rows)
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
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--max-cases", type=int, default=0)
    parser.add_argument(
        "--labels",
        type=Path,
        default=PROJECT_ROOT / "evaluation" / "search_strategy_labels.jsonl",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "evaluation" / "current_pipeline_results.json",
    )
    args = parser.parse_args()

    payload = evaluate(
        args.golden,
        args.k,
        args.output,
        max_cases=args.max_cases,
        labels_path=args.labels,
    )
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    if args.output:
        print(f"Wrote detailed results to {args.output}")


if __name__ == "__main__":
    main()
