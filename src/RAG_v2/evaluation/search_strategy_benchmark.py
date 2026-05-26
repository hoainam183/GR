"""Benchmark retrieval search strategies with LLM-judged relevance labels.

This runner implements the "LLM judge first, human audit later" loop:

1. Collect candidates from several retrieval strategies.
2. Ask a judge model to assign relevance labels 0/1/2 per query-document pair.
3. Cache labels in JSONL so future runs do not re-judge the same pairs.
4. Report nDCG@10, MRR@10, and Recall@50 overall and by query class.

Usage from ``src/RAG_v2``::

    python evaluation/search_strategy_benchmark.py
    python evaluation/search_strategy_benchmark.py --skip-judge
    python evaluation/search_strategy_benchmark.py --output evaluation/search_strategy_results.json
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from openai import OpenAI
from qdrant_client import models as qdrant_models

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import Settings
from query.structured_query import parse_structured_query, text_contains_excluded_term
from retrieval.service import RetrievalService

logger = logging.getLogger(__name__)

_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
_DEFAULT_GOLDEN = PROJECT_ROOT / "eval" / "golden_dataset.json"
_DEFAULT_LABELS = PROJECT_ROOT / "evaluation" / "search_strategy_labels.jsonl"
_DEFAULT_OUTPUT = PROJECT_ROOT / "evaluation" / "search_strategy_results.json"
_DEFAULT_REPORT = PROJECT_ROOT / "evaluation" / "search_strategy_report.md"

_COLLECTION_QUERY_CLASSES = {
    "quydinh": "policy",
    "ctdt": "course",
    "kehoach": "schedule",
    "stsv": "stsv_form",
}
_DOMAIN_QUERY_CLASSES = {
    **_COLLECTION_QUERY_CLASSES,
    "chitchat": "chitchat",
    "tool_search": "tool_search",
}
_DOMAIN_CLASSIFIER: Optional[Any] = None


@dataclass
class BenchmarkCase:
    id: str
    query: str
    query_class: str
    source: str = "golden"
    expected_source_ids: List[str] = field(default_factory=list)


@dataclass
class Candidate:
    id: str
    text: str
    score: float
    collection: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_result_row(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "score": self.score,
            "collection": self.collection,
            "metadata": self.metadata,
        }


def _raw_id(value: Any) -> str:
    text = str(value or "").strip()
    return text.split("/", 1)[-1] if "/" in text else text


def _candidate_id(collection: str, raw_id: Any) -> str:
    rid = _raw_id(raw_id)
    return f"{collection}/{rid}" if collection else rid


def _listify(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _expected_collections(case: Dict[str, Any]) -> List[str]:
    return _listify(case.get("expected_collections")) + _listify(
        case.get("expected_collection")
    )


def _classifier_query_class(query: str, fallback: str) -> str:
    global _DOMAIN_CLASSIFIER
    if _DOMAIN_CLASSIFIER is None:
        try:
            from query.domain_classifier import DomainClassifier

            _DOMAIN_CLASSIFIER = DomainClassifier()
            _DOMAIN_CLASSIFIER.load()
        except Exception as exc:
            logger.warning(
                "DomainClassifier unavailable for benchmark query_class fallback: %s",
                exc,
            )
            return fallback
    try:
        prediction = _DOMAIN_CLASSIFIER.predict(query)
    except Exception as exc:
        logger.warning("DomainClassifier query_class fallback failed: %s", exc)
        return fallback

    domain = prediction.get("domain") or prediction.get("label")
    return _DOMAIN_QUERY_CLASSES.get(str(domain), fallback)


def _case_query_class(
    case: Dict[str, Any],
    *,
    query: str,
    fallback: str = "general",
) -> str:
    explicit = str(case.get("query_class") or "").strip()
    if explicit:
        return explicit

    for collection in _expected_collections(case):
        qclass = _COLLECTION_QUERY_CLASSES.get(collection)
        if qclass:
            return qclass

    category = str(case.get("category") or "").strip()
    if category and category != "retrieval":
        return category

    if query:
        return _classifier_query_class(query, fallback)
    return fallback


def _expected_ids(case: Dict[str, Any]) -> List[str]:
    raw = case.get("expected_source_ids") or case.get("relevant_doc_ids") or []
    if isinstance(raw, str):
        raw = [part.strip() for part in raw.replace(";", ",").split(",")]
    if not isinstance(raw, list):
        return []
    return [_raw_id(item) for item in raw if _raw_id(item)]


def _load_json_or_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    if path.suffix == ".jsonl":
        with open(path, encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    if isinstance(payload, dict):
        for key in ("cases", "test_cases", "rows", "feedback"):
            if isinstance(payload.get(key), list):
                return payload[key]
    return payload if isinstance(payload, list) else []


def load_feedback_cases(path: Optional[Path]) -> List[BenchmarkCase]:
    """Load downvoted feedback exports as hard retrieval regression cases."""
    if path is None:
        return []

    cases: List[BenchmarkCase] = []
    for i, row in enumerate(_load_json_or_jsonl(path), start=1):
        rating = str(row.get("rating") or row.get("feedback") or "").lower()
        if rating and rating not in {"down", "bad", "negative", "thumbs_down"}:
            continue
        query = str(row.get("question") or row.get("query") or "").strip()
        if not query:
            continue
        case_id = str(row.get("id") or row.get("turn_id") or f"feedback_{i}")
        cases.append(
            BenchmarkCase(
                id=f"feedback_{case_id}",
                query=query,
                query_class=_case_query_class(row, query=query, fallback="feedback"),
                source="feedback",
                expected_source_ids=_expected_ids(row),
            )
        )
    return cases


def load_cases(
    path: Path,
    *,
    include_diagnostics: bool = True,
    feedback_cases: Optional[Path] = None,
) -> List[BenchmarkCase]:
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    raw_cases = payload.get("test_cases", []) if isinstance(payload, dict) else payload

    cases: List[BenchmarkCase] = []
    for item in raw_cases:
        if not isinstance(item, dict) or item.get("category") != "retrieval":
            continue
        query = str(item.get("query", "")).strip()
        if not query:
            continue
        cases.append(
            BenchmarkCase(
                id=str(item.get("id") or f"case_{len(cases) + 1}"),
                query=query,
                query_class=_case_query_class(item, query=query),
                source="golden",
                expected_source_ids=_expected_ids(item),
            )
        )

    if include_diagnostics:
        diagnostic_queries = [
            ("diag_no_diacritic_01", "hoc bong khuyen khich hoc tap", "typo_no_diacritic"),
            ("diag_no_diacritic_02", "cntt viet nhat co bao nhieu tin chi", "typo_no_diacritic"),
            (
                "diag_negation_01",
                "học phí nghiên cứu sinh không bao gồm học phần bổ sung",
                "negation",
            ),
            (
                "diag_negation_02",
                "môn học tự chọn IT-E6 không bao gồm đồ án tốt nghiệp",
                "negation",
            ),
            (
                "diag_comparison_01",
                "so sánh quy định ngoại ngữ của K70 và K67",
                "comparison",
            ),
        ]
        cases.extend(
            BenchmarkCase(id=cid, query=query, query_class=qclass, source="diagnostic")
            for cid, query, qclass in diagnostic_queries
        )

    cases.extend(load_feedback_cases(feedback_cases))
    return cases


def _dedup_candidates(candidates: Iterable[Candidate], limit: int) -> List[Candidate]:
    best: Dict[str, Candidate] = {}
    for candidate in candidates:
        existing = best.get(candidate.id)
        if existing is None or candidate.score > existing.score:
            best[candidate.id] = candidate
    ranked = sorted(best.values(), key=lambda row: row.score, reverse=True)
    return ranked[:limit]


def _round_robin_union(
    strategy_results: Dict[str, List[Candidate]],
    limit: int,
) -> List[Candidate]:
    """Build a judge pool without comparing scores across strategies."""
    out: List[Candidate] = []
    seen: set[str] = set()
    max_len = max((len(rows) for rows in strategy_results.values()), default=0)
    for rank in range(max_len):
        for rows in strategy_results.values():
            if rank >= len(rows):
                continue
            candidate = rows[rank]
            if candidate.id in seen:
                continue
            seen.add(candidate.id)
            out.append(candidate)
            if len(out) >= limit:
                return out
    return out


def _filter_excluded(candidates: Iterable[Candidate], query: str) -> List[Candidate]:
    exclude_terms = parse_structured_query(query).exclude_terms
    if not exclude_terms:
        return list(candidates)
    out: List[Candidate] = []
    for candidate in candidates:
        meta = candidate.metadata or {}
        haystack = " ".join(
            [
                candidate.text,
                str(meta.get("title", "") or ""),
                str(meta.get("course_code", "") or ""),
                str(meta.get("course_name", "") or ""),
            ]
        )
        if not text_contains_excluded_term(haystack, exclude_terms):
            out.append(candidate)
    return out


def _from_search_rows(rows: Iterable[Dict[str, Any]]) -> List[Candidate]:
    out: List[Candidate] = []
    for row in rows:
        collection = str(row.get("collection") or (row.get("metadata") or {}).get("collection") or "")
        out.append(
            Candidate(
                id=_candidate_id(collection, row.get("id")),
                text=str(row.get("text") or row.get("content") or ""),
                score=float(row.get("score") or row.get("rerank_score") or 0.0),
                collection=collection,
                metadata=dict(row.get("metadata") or {}),
            )
        )
    return out


def bm25_only(service: RetrievalService, query: str, limit: int) -> List[Candidate]:
    candidates: List[Candidate] = []
    exclude_terms = parse_structured_query(query).exclude_terms
    for collection, hybrid in service.searcher.searchers:
        rows = hybrid.es.keyword_search(
            query=query,
            top_k=limit,
            collection_name=collection,
            exclude_terms=exclude_terms,
        )
        for row in rows:
            candidates.append(
                Candidate(
                    id=_candidate_id(collection, row.get("id")),
                    text=str(row.get("text") or ""),
                    score=float(row.get("score") or 0.0),
                    collection=collection,
                    metadata=dict(row.get("metadata") or {}),
                )
            )
    return _dedup_candidates(_filter_excluded(candidates, query), limit)


def qdrant_single_vector(
    service: RetrievalService,
    query: str,
    vector_name: str,
    query_vector: List[float],
    limit: int,
) -> List[Candidate]:
    params = qdrant_models.SearchParams(hnsw_ef=128, exact=False)
    candidates: List[Candidate] = []
    for collection, hybrid in service.searcher.searchers:
        resp = hybrid.qdrant.client.query_points(
            collection_name=collection,
            query=query_vector,
            using=vector_name,
            limit=limit,
            search_params=params,
            with_payload=True,
        )
        for hit in resp.points:
            payload = dict(hit.payload or {})
            text = str(payload.pop("text", "") or "")
            candidates.append(
                Candidate(
                    id=_candidate_id(collection, hit.id),
                    text=text,
                    score=float(hit.score),
                    collection=collection,
                    metadata=payload,
                )
            )
    return _dedup_candidates(_filter_excluded(candidates, query), limit)


def hybrid_search(
    service: RetrievalService,
    query: str,
    bge_vec: List[float],
    e5_vec: List[float],
    limit: int,
    *,
    vector_weight: Optional[float] = None,
    keyword_weight: Optional[float] = None,
    fusion_mode: str = "linear",
    rerank: bool = False,
) -> List[Candidate]:
    searcher = service.searcher
    old_vector_weight = searcher.vector_weight
    old_keyword_weight = searcher.keyword_weight
    if vector_weight is not None:
        searcher.vector_weight = vector_weight
    if keyword_weight is not None:
        searcher.keyword_weight = keyword_weight
    try:
        rows = searcher.search(
            query=query,
            bge_m3_query=bge_vec,
            e5_query=e5_vec,
            top_k=limit,
            vector_top_k=service.settings.vector_top_k,
            keyword_top_k=service.settings.keyword_top_k,
            vector_pool_k=max(limit, service.settings.vector_pool_k),
            keyword_pool_k=max(limit, service.settings.keyword_pool_k),
            fusion_mode=fusion_mode,
        )
    finally:
        searcher.vector_weight = old_vector_weight
        searcher.keyword_weight = old_keyword_weight

    if rerank and service.reranker is not None:
        rows = service.reranker.rerank(query=query, documents=rows, top_k=limit)
    return _from_search_rows(rows)[:limit]


def make_strategies(args: argparse.Namespace) -> List[Tuple[str, Callable[..., List[Candidate]]]]:
    strategies: List[Tuple[str, Callable[..., List[Candidate]]]] = [
        ("bm25_only", lambda service, query, bge, e5, limit: bm25_only(service, query, limit)),
        ("bge_only", lambda service, query, bge, e5, limit: qdrant_single_vector(service, query, "bge_m3", bge, limit)),
        ("e5_only", lambda service, query, bge, e5, limit: qdrant_single_vector(service, query, "e5", e5, limit)),
        ("current_hybrid", lambda service, query, bge, e5, limit: hybrid_search(service, query, bge, e5, limit)),
        ("global_rrf", lambda service, query, bge, e5, limit: hybrid_search(service, query, bge, e5, limit, fusion_mode="rrf")),
    ]
    if not args.no_rerank:
        strategies.append(
            (
                "current_hybrid_reranked",
                lambda service, query, bge, e5, limit: hybrid_search(
                    service, query, bge, e5, limit, rerank=True
                ),
            )
        )
    for alpha in args.alpha:
        vector_weight = float(alpha)
        keyword_weight = round(1.0 - vector_weight, 4)
        strategies.append(
            (
                f"linear_v{vector_weight:.2f}_k{keyword_weight:.2f}",
                lambda service, query, bge, e5, limit, vw=vector_weight, kw=keyword_weight: hybrid_search(
                    service,
                    query,
                    bge,
                    e5,
                    limit,
                    vector_weight=vw,
                    keyword_weight=kw,
                ),
            )
        )
    return strategies


def load_label_cache(path: Path) -> Dict[Tuple[str, str], int]:
    labels: Dict[Tuple[str, str], int] = {}
    if not path.exists():
        return labels
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            labels[(str(row["case_id"]), str(row["doc_id"]))] = int(row["relevance"])
    return labels


def append_labels(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def make_judge(settings: Settings, model: Optional[str]) -> tuple[OpenAI, str]:
    api_key = settings.google_api_key
    if not api_key:
        raise RuntimeError(
            "GOOGLE_API_KEY is required for LLM judging. Use --skip-judge to run only with existing labels."
        )
    return OpenAI(api_key=api_key, base_url=_GEMINI_BASE_URL), model or settings.reflection_model


def judge_candidates(
    client: OpenAI,
    model: str,
    case: BenchmarkCase,
    candidates: List[Candidate],
) -> List[Dict[str, Any]]:
    compact_docs = []
    for candidate in candidates:
        meta = candidate.metadata or {}
        compact_docs.append(
            {
                "doc_id": candidate.id,
                "collection": candidate.collection,
                "title": meta.get("title") or meta.get("source") or "",
                "metadata": {
                    key: meta.get(key)
                    for key in ("major_code", "major_name", "applicable_cohort", "course_code", "course_name")
                    if meta.get(key)
                },
                "text": candidate.text[:900],
            }
        )

    system = (
        "You judge retrieval relevance for a Vietnamese university RAG system. "
        "Score each document for the query: 0=irrelevant, 1=partially relevant, "
        "2=directly answers or contains the needed evidence. Return JSON only."
    )
    user = {
        "query": case.query,
        "query_class": case.query_class,
        "documents": compact_docs,
        "output_schema": {
            "labels": [
                {
                    "doc_id": "same id from input",
                    "relevance": "0|1|2 integer",
                    "reason": "short reason",
                }
            ]
        },
    }
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
        ],
        temperature=0.0,
        max_tokens=4096,
    )
    raw = (response.choices[0].message.content or "").strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw.removeprefix("json").strip()
    data = json.loads(raw)
    labels = data.get("labels", [])
    out: List[Dict[str, Any]] = []
    candidate_ids = {candidate.id for candidate in candidates}
    for item in labels:
        doc_id = str(item.get("doc_id", ""))
        if doc_id not in candidate_ids:
            continue
        relevance = max(0, min(2, int(item.get("relevance", 0))))
        out.append(
            {
                "case_id": case.id,
                "query": case.query,
                "doc_id": doc_id,
                "relevance": relevance,
                "reason": str(item.get("reason", ""))[:300],
                "judge_model": model,
                "source": "llm_judge",
            }
        )
    return out


def _dcg(gains: List[int], k: int) -> float:
    score = 0.0
    for rank, gain in enumerate(gains[:k], start=1):
        score += ((2**gain) - 1) / math.log2(rank + 1)
    return score


def metrics_for_ranking(
    ranking: List[Candidate],
    labels: Dict[str, int],
    *,
    k: int = 10,
    recall_k: int = 50,
) -> Dict[str, float]:
    if not labels:
        return {"ndcg_at_10": 0.0, "mrr_at_10": 0.0, "recall_at_50": 0.0}

    def label_for(candidate: Candidate) -> int:
        return labels.get(candidate.id, labels.get(_raw_id(candidate.id), 0))

    ranked_gains = [label_for(candidate) for candidate in ranking]
    ideal_gains = sorted(labels.values(), reverse=True)
    idcg = _dcg(ideal_gains, k)
    ndcg = _dcg(ranked_gains, k) / idcg if idcg else 0.0

    mrr = 0.0
    for rank, candidate in enumerate(ranking[:k], start=1):
        if label_for(candidate) > 0:
            mrr = 1.0 / rank
            break

    relevant_ids = {doc_id for doc_id, rel in labels.items() if rel > 0}
    retrieved_ids = {candidate.id for candidate in ranking[:recall_k]}
    retrieved_raw_ids = {_raw_id(candidate.id) for candidate in ranking[:recall_k]}
    recall = (
        len((retrieved_ids | retrieved_raw_ids) & relevant_ids) / len(relevant_ids)
        if relevant_ids
        else 0.0
    )
    return {
        "ndcg_at_10": round(ndcg, 4),
        "mrr_at_10": round(mrr, 4),
        "recall_at_50": round(recall, 4),
    }


def _mean(rows: List[Dict[str, float]], key: str) -> float:
    return round(sum(row[key] for row in rows) / len(rows), 4) if rows else 0.0


def summarize(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_strategy: Dict[str, List[Dict[str, float]]] = {}
    by_strategy_class: Dict[str, Dict[str, List[Dict[str, float]]]] = {}
    for row in rows:
        strategy = row["strategy"]
        qclass = row["query_class"]
        metrics = row["metrics"]
        by_strategy.setdefault(strategy, []).append(metrics)
        by_strategy_class.setdefault(strategy, {}).setdefault(qclass, []).append(metrics)

    summary: Dict[str, Any] = {}
    for strategy, metric_rows in by_strategy.items():
        summary[strategy] = {
            "n_cases": len(metric_rows),
            "ndcg_at_10": _mean(metric_rows, "ndcg_at_10"),
            "mrr_at_10": _mean(metric_rows, "mrr_at_10"),
            "recall_at_50": _mean(metric_rows, "recall_at_50"),
            "by_query_class": {},
        }
        for qclass, class_rows in by_strategy_class[strategy].items():
            summary[strategy]["by_query_class"][qclass] = {
                "n_cases": len(class_rows),
                "ndcg_at_10": _mean(class_rows, "ndcg_at_10"),
                "mrr_at_10": _mean(class_rows, "mrr_at_10"),
                "recall_at_50": _mean(class_rows, "recall_at_50"),
            }
    return summary


def _best_strategy_by_metric(summary: Dict[str, Any], metric: str) -> tuple[str, float]:
    if not summary:
        return "", 0.0
    name, row = max(summary.items(), key=lambda item: item[1].get(metric, 0.0))
    return name, float(row.get(metric, 0.0))


def _format_metric_table(summary: Dict[str, Any]) -> str:
    lines = [
        "| Rank | Strategy | nDCG@10 | MRR@10 | Recall@50 |",
        "|---:|---|---:|---:|---:|",
    ]
    ranked = sorted(
        summary.items(),
        key=lambda item: item[1].get("ndcg_at_10", 0.0),
        reverse=True,
    )
    for rank, (name, row) in enumerate(ranked, start=1):
        lines.append(
            f"| {rank} | `{name}` | {row.get('ndcg_at_10', 0):.4f} | "
            f"{row.get('mrr_at_10', 0):.4f} | {row.get('recall_at_50', 0):.4f} |"
        )
    return "\n".join(lines)


def _format_query_class_table(summary: Dict[str, Any]) -> str:
    class_names = sorted(
        {
            qclass
            for row in summary.values()
            for qclass in row.get("by_query_class", {}).keys()
        }
    )
    lines = [
        "| Query class | Best nDCG@10 strategy | nDCG@10 | Best Recall@50 strategy | Recall@50 |",
        "|---|---|---:|---|---:|",
    ]
    for qclass in class_names:
        class_rows = [
            (
                strategy,
                row.get("by_query_class", {}).get(qclass, {}),
            )
            for strategy, row in summary.items()
            if qclass in row.get("by_query_class", {})
        ]
        best_ndcg_name, best_ndcg_row = max(
            class_rows, key=lambda item: item[1].get("ndcg_at_10", 0.0)
        )
        best_recall_name, best_recall_row = max(
            class_rows, key=lambda item: item[1].get("recall_at_50", 0.0)
        )
        lines.append(
            f"| `{qclass}` | `{best_ndcg_name}` | "
            f"{best_ndcg_row.get('ndcg_at_10', 0):.4f} | `{best_recall_name}` | "
            f"{best_recall_row.get('recall_at_50', 0):.4f} |"
        )
    return "\n".join(lines)


def format_markdown_run(payload: Dict[str, Any]) -> str:
    """Format one benchmark payload as an append-only Markdown run."""
    config = payload.get("config", {})
    summary = payload.get("summary", {})
    failures = payload.get("failures", [])
    best_ndcg = _best_strategy_by_metric(summary, "ndcg_at_10")
    best_mrr = _best_strategy_by_metric(summary, "mrr_at_10")
    best_recall = _best_strategy_by_metric(summary, "recall_at_50")
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")

    lines = [
        f"## Run - {timestamp}",
        "",
        f"- Golden: `{config.get('golden', '')}`",
        f"- Labels: `{config.get('labels', '')}`",
        f"- Cases: {next(iter(summary.values()), {}).get('n_cases', 0) if summary else 0}",
        f"- Strategies: {len(config.get('strategies', []))}",
        f"- Judge pool: {config.get('judge_pool')} | k: {config.get('k')} | recall_k: {config.get('recall_k')}",
        f"- Skip judge: `{config.get('skip_judge')}` | Failures: {len(failures)}",
        "",
        "### Overall Ranking",
        "",
        _format_metric_table(summary),
        "",
        "### Winners",
        "",
        f"- Best nDCG@10: `{best_ndcg[0]}` = {best_ndcg[1]:.4f}",
        f"- Best MRR@10: `{best_mrr[0]}` = {best_mrr[1]:.4f}",
        f"- Best Recall@50: `{best_recall[0]}` = {best_recall[1]:.4f}",
        "",
        "### Best By Query Class",
        "",
        _format_query_class_table(summary),
        "",
        "### Notes",
        "",
        "- Add manual interpretation here after inspecting changed rows and labels.",
        "- Keep this section append-only so runs remain comparable over time.",
        "",
    ]
    return "\n".join(lines)


def append_markdown_report(payload: Dict[str, Any], path: Path) -> None:
    """Append one benchmark run to the persistent Markdown report."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        header = (
            "# Search Strategy Benchmark Report\n\n"
            "This file is append-only. Each benchmark run adds a new section so "
            "retrieval changes can be compared over time.\n\n"
        )
        path.write_text(header, encoding="utf-8")

    with open(path, "a", encoding="utf-8") as handle:
        handle.write(format_markdown_run(payload))


def evaluate(args: argparse.Namespace) -> Dict[str, Any]:
    settings = Settings()
    service = RetrievalService.from_settings(settings)
    cases = load_cases(
        args.golden,
        include_diagnostics=not args.no_diagnostics,
        feedback_cases=args.feedback_cases,
    )
    label_cache = load_label_cache(args.labels)
    strategies = make_strategies(args)

    judge_client: Optional[OpenAI] = None
    judge_model = args.judge_model
    if not args.skip_judge:
        judge_client, judge_model = make_judge(settings, args.judge_model)

    rows: List[Dict[str, Any]] = []
    failures: List[Dict[str, Any]] = []

    for case in cases:
        started = time.perf_counter()
        bge_vec, e5_vec = service.embed_query(case.query)
        strategy_results: Dict[str, List[Candidate]] = {}

        for strategy_name, strategy_fn in strategies:
            t0 = time.perf_counter()
            try:
                candidates = strategy_fn(service, case.query, bge_vec, e5_vec, args.recall_k)
                strategy_results[strategy_name] = candidates
            except Exception as exc:
                failures.append(
                    {
                        "case_id": case.id,
                        "strategy": strategy_name,
                        "error": str(exc),
                    }
                )
                strategy_results[strategy_name] = []
            finally:
                elapsed = round((time.perf_counter() - t0) * 1000, 2)
                print(f"[{case.id}] {strategy_name}: {elapsed}ms")

        union_candidates = _round_robin_union(strategy_results, args.judge_pool)

        missing = [
            candidate
            for candidate in union_candidates
            if (case.id, candidate.id) not in label_cache
        ]
        if missing and judge_client is not None:
            judged_rows = judge_candidates(judge_client, judge_model, case, missing)
            append_labels(args.labels, judged_rows)
            for row in judged_rows:
                label_cache[(row["case_id"], row["doc_id"])] = int(row["relevance"])

        case_labels = {
            doc_id: rel
            for (case_id, doc_id), rel in label_cache.items()
            if case_id == case.id
        }
        if not case_labels and case.expected_source_ids:
            case_labels = {
                _candidate_id("", expected_id): 2 for expected_id in case.expected_source_ids
            }

        for strategy_name, candidates in strategy_results.items():
            metrics = metrics_for_ranking(
                candidates,
                case_labels,
                k=args.k,
                recall_k=args.recall_k,
            )
            rows.append(
                {
                    "case": asdict(case),
                    "strategy": strategy_name,
                    "query_class": case.query_class,
                    "metrics": metrics,
                    "retrieved": [candidate.to_result_row() for candidate in candidates[: args.k]],
                    "label_count": len(case_labels),
                    "latency_case_ms": round((time.perf_counter() - started) * 1000, 2),
                }
            )

    payload = {
        "config": {
            "golden": str(args.golden),
            "labels": str(args.labels),
            "k": args.k,
            "recall_k": args.recall_k,
            "judge_pool": args.judge_pool,
            "skip_judge": args.skip_judge,
            "feedback_cases": str(args.feedback_cases) if args.feedback_cases else None,
            "strategies": [name for name, _ in strategies],
        },
        "summary": summarize(rows),
        "rows": rows,
        "failures": failures,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    if not args.no_report_append:
        append_markdown_report(payload, args.report_md)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--golden", type=Path, default=_DEFAULT_GOLDEN)
    parser.add_argument("--labels", type=Path, default=_DEFAULT_LABELS)
    parser.add_argument("--output", type=Path, default=_DEFAULT_OUTPUT)
    parser.add_argument("--report-md", type=Path, default=_DEFAULT_REPORT)
    parser.add_argument("--judge-model", default=None)
    parser.add_argument(
        "--feedback-cases",
        type=Path,
        default=None,
        help="Optional JSON/JSONL export of feedback rows; down-rated rows become hard cases.",
    )
    parser.add_argument("--skip-judge", action="store_true")
    parser.add_argument("--no-report-append", action="store_true")
    parser.add_argument("--no-rerank", action="store_true")
    parser.add_argument("--no-diagnostics", action="store_true")
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--recall-k", type=int, default=50)
    parser.add_argument("--judge-pool", type=int, default=40)
    parser.add_argument(
        "--alpha",
        type=float,
        nargs="*",
        default=[0.2, 0.4, 0.6, 0.8],
        help="Vector weights for linear alpha sweep. Keyword weight is 1-alpha.",
    )
    args = parser.parse_args()

    payload = evaluate(args)
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    print(f"Wrote benchmark details to {args.output}")


if __name__ == "__main__":
    main()
