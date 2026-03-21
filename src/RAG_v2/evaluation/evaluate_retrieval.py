"""Retrieval Evaluation — compare BGE-M3, E5 (Qdrant) and BM25 (Elasticsearch).

Runs each retrieval method independently against every query in every CSV
dataset inside the ``evaluation/`` folder, then writes per-query result CSVs
and per-dataset summary CSVs into three sub-folders:
    evaluation/bge_m3/
    evaluation/e5/
    evaluation/elasticsearch/

Usage::

    python evaluation/evaluate_retrieval.py
"""

from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd
from elasticsearch import Elasticsearch
from qdrant_client import QdrantClient
from qdrant_client import models as qmodels

# Make project imports work when executed from any cwd
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from embedding.bge_m3 import BGEm3Embedder
from embedding.e5_multilingual import E5MultilingualEmbedder
from reranking.bge_reranker import BGEReranker
from retrieval.multi_collection_search import MultiCollectionSearch

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
CONFIG = {
    "collections": ["stsv", "quydinh"],
    "es_indexes": None,  # None → dùng collections
    "k": 5,
    "top_k": 20,
    "qdrant_host": "localhost",
    "qdrant_port": 6333,
    "es_host": "localhost",
    "es_port": 9200,
    "datasets": None,  # None → tất cả CSV trong evaluation/
    "no_bge": True,
    "no_e5": True,
    "no_es": True,
    "no_hybrid": False,
    "no_rerank": False,
    # rerank_pool_k: số doc từ hybrid đưa vào reranker (nên >= top_k)
    "rerank_pool_k": 20,
    "score_threshold": 0.6,
    # hybrid_score_threshold: lọc kết quả hybrid theo RRF score tối thiểu
    "hybrid_score_threshold": 0.2,
    # Danh sách cấu hình hybrid để test — mỗi config sinh ra một method riêng.
    # vector_weight + keyword_weight không cần tổng = 1 (min-max normalize độc lập).
    # vector_pool_k: số doc giữ lại từ pool vector toàn cục.
    # keyword_pool_k: số doc giữ lại từ pool keyword toàn cục.
    "hybrid_configs": [
        {
            "vector_weight": 1.0,
            "keyword_weight": 0.0,
            "vector_pool_k": 15,
            "keyword_pool_k": 15,
        },
        {
            "vector_weight": 0.8,
            "keyword_weight": 0.2,
            "vector_pool_k": 15,
            "keyword_pool_k": 15,
        },
        {
            "vector_weight": 0.7,
            "keyword_weight": 0.3,
            "vector_pool_k": 15,
            "keyword_pool_k": 15,
        },
    ],
}

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EVAL_DIR = Path(__file__).resolve().parent
RESULT_DIRS: Dict[str, Path] = {
    "bge_m3": EVAL_DIR / "bge_m3",
    "e5": EVAL_DIR / "e5",
    "elasticsearch": EVAL_DIR / "elasticsearch",
}


def _hybrid_label(cfg: Dict[str, Any]) -> str:
    """Build a filesystem-safe label from a hybrid config dict."""
    vw = cfg["vector_weight"]
    kw = cfg["keyword_weight"]
    vp = cfg.get("vector_pool_k", 15)
    kp = cfg.get("keyword_pool_k", 15)
    return f"hybrid_v{vw:.1f}_k{kw:.1f}_vp{vp}_kp{kp}"


# Columns written to per-query result CSV
RESULT_COLUMNS = [
    "id",
    "query",
    "query_type",
    "difficulty",
    "relevant_doc_ids",
    "retrieved_doc_ids",
    "retrieved_scores",
    "hit@1",
    "hit@k",
    "precision@k",
    "recall@k",
    "mrr",
    "latency_ms",
]

# Columns written to per-dataset summary CSV
SUMMARY_COLUMNS = [
    "dataset",
    "n_queries",
    "hit@1",
    "hit@k",
    "precision@k",
    "recall@k",
    "mrr",
    "avg_latency_ms",
]


# ---------------------------------------------------------------------------
# Metric helpers
# ---------------------------------------------------------------------------


def parse_relevant_ids(raw: Any) -> Set[str]:
    """Parse comma-separated UUIDs from a CSV cell into a set."""
    if not isinstance(raw, str) or not raw.strip():
        return set()
    return {s.strip() for s in raw.replace(";", ",").split(",") if s.strip()}


def compute_metrics(
    retrieved_ids: List[str],
    relevant_ids: Set[str],
    k: int,
) -> Dict[str, float]:
    """Return hit@1, hit@k, precision@k, recall@k, MRR for one query.

    Args:
        retrieved_ids: Ordered list of retrieved document IDs (all ranks).
        relevant_ids: Set of ground-truth relevant document IDs.
        k: Cutoff for precision/recall/hit metrics.

    Returns:
        Dict with keys ``hit@1``, ``hit@k``, ``precision@k``,
        ``recall@k``, ``mrr``.
    """
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
# Single-vector Qdrant search (BGE-M3 or E5)
# ---------------------------------------------------------------------------


def qdrant_single_vector_search(
    clients: List[Tuple[str, QdrantClient]],
    query_vector: List[float],
    vector_name: str,
    top_k: int,
    score_threshold: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """Search across multiple Qdrant collections with a single named vector.

    Results from all collections are merged and globally re-ranked by score.

    Args:
        clients: List of ``(collection_name, QdrantClient)`` pairs.
        query_vector: Dense query embedding.
        vector_name: Named vector to use (``"bge_m3"`` or ``"e5"``).
        top_k: Number of results to return.
        score_threshold: Optional minimum cosine similarity.

    Returns:
        List of dicts sorted by score (descending):
        ``{"id", "text", "metadata", "score"}``
    """
    all_hits: List[Dict[str, Any]] = []

    for col_name, client in clients:
        try:
            resp = client.query_points(
                collection_name=col_name,
                query=query_vector,
                using=vector_name,
                limit=top_k,
                score_threshold=score_threshold,
                with_payload=True,
            )
            for hit in resp.points:
                payload = dict(hit.payload or {})
                text = payload.pop("text", "")
                all_hits.append(
                    {
                        "id": str(hit.id),
                        "text": text,
                        "metadata": payload,
                        "score": float(hit.score),
                        "collection": col_name,
                    }
                )
        except Exception:
            logger.exception(
                "Qdrant search failed for collection='%s', vector='%s'",
                col_name,
                vector_name,
            )

    # Global rank by score (higher = better)
    all_hits.sort(key=lambda x: x["score"], reverse=True)

    # Deduplicate by text (keep highest-score copy)
    seen_texts: set = set()
    deduped: List[Dict[str, Any]] = []
    for item in all_hits:
        key = item["text"].strip()
        if key not in seen_texts:
            seen_texts.add(key)
            deduped.append(item)

    return deduped[:top_k]


# ---------------------------------------------------------------------------
# Elasticsearch BM25 search across multiple indices
# ---------------------------------------------------------------------------


def es_keyword_search(
    es_client: Elasticsearch,
    index_names: List[str],
    query: str,
    top_k: int,
) -> List[Dict[str, Any]]:
    """BM25 search across multiple Elasticsearch indices.

    Args:
        es_client: Connected Elasticsearch client.
        index_names: List of index names to search.
        query: User query string.
        top_k: Number of results to return.

    Returns:
        List of dicts sorted by BM25 score (descending):
        ``{"id", "text", "metadata", "score"}``
    """
    index_pattern = ",".join(index_names)
    try:
        resp = es_client.search(
            index=index_pattern,
            size=top_k,
            query={
                "multi_match": {
                    "query": query,
                    "fields": ["text^1.0", "title^1.5"],
                    "type": "best_fields",
                    "fuzziness": "AUTO",
                }
            },
        )
    except Exception:
        logger.exception("Elasticsearch search failed for query='%s'", query)
        return []

    results: List[Dict[str, Any]] = []
    for hit in resp["hits"]["hits"]:
        source = dict(hit["_source"])
        text = source.pop("text", "")
        results.append(
            {
                "id": hit["_id"],
                "text": text,
                "metadata": source,
                "score": float(hit["_score"]),
                "collection": hit.get("_index", ""),
            }
        )
    return results


# ---------------------------------------------------------------------------
# Per-dataset evaluation
# ---------------------------------------------------------------------------


def evaluate_dataset(
    csv_path: Path,
    method: str,
    search_fn,
    k: int,
) -> Tuple[pd.DataFrame, Dict[str, float]]:
    """Evaluate one method on one dataset CSV.

    Args:
        csv_path: Path to the evaluation CSV.
        method: One of ``"bge_m3"``, ``"e5"``, ``"elasticsearch"``.
        search_fn: Callable ``(query_str) -> List[{"id", "score", ...}]``.
        k: Metric cutoff.

    Returns:
        Tuple of (per-query DataFrame, aggregate metrics dict).
    """
    df = pd.read_csv(csv_path)
    required = {"id", "query", "relevant_doc_ids"}
    missing = required - set(df.columns)
    if missing:
        logger.warning(
            "Skipping %s — missing columns: %s", csv_path.name, missing
        )
        return pd.DataFrame(), {}

    rows: List[Dict[str, Any]] = []

    for _, row in df.iterrows():
        query: str = str(row["query"]).strip()
        relevant_ids = parse_relevant_ids(row.get("relevant_doc_ids", ""))

        t0 = time.perf_counter()
        results = search_fn(query)
        latency_ms = round((time.perf_counter() - t0) * 1000, 1)

        # Strip optional "collection/" namespace prefix added by MultiCollectionSearch
        retrieved_ids = [r["id"].split("/", 1)[-1] for r in results]
        retrieved_scores = [round(r["score"], 4) for r in results]

        metrics = compute_metrics(retrieved_ids, relevant_ids, k)

        rows.append(
            {
                "id": row.get("id", ""),
                "query": query,
                "query_type": row.get("query_type", ""),
                "difficulty": row.get("difficulty", ""),
                "relevant_doc_ids": row.get("relevant_doc_ids", ""),
                "retrieved_doc_ids": ",".join(retrieved_ids),
                "retrieved_scores": ",".join(str(s) for s in retrieved_scores),
                "hit@1": metrics["hit@1"],
                "hit@k": metrics["hit@k"],
                "precision@k": metrics["precision@k"],
                "recall@k": metrics["recall@k"],
                "mrr": metrics["mrr"],
                "latency_ms": latency_ms,
            }
        )

    print(rows[0])
    result_df = pd.DataFrame(rows, columns=RESULT_COLUMNS)

    n = len(result_df)
    if n == 0:
        return result_df, {}

    aggregate: Dict[str, Any] = {
        "dataset": csv_path.stem,
        "n_queries": n,
        "hit@1": round(result_df["hit@1"].mean(), 4),
        "hit@k": round(result_df["hit@k"].mean(), 4),
        "precision@k": round(result_df["precision@k"].mean(), 4),
        "recall@k": round(result_df["recall@k"].mean(), 4),
        "mrr": round(result_df["mrr"].mean(), 4),
        "avg_latency_ms": round(result_df["latency_ms"].mean(), 1),
    }

    return result_df, aggregate


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    collections: List[str] = CONFIG["collections"]
    es_indexes: List[str] = CONFIG["es_indexes"] or collections
    k: int = CONFIG["k"]
    top_k: int = CONFIG["top_k"]
    score_threshold: Optional[float] = CONFIG["score_threshold"]

    # ------------------------------------------------------------------
    # Discover dataset CSVs
    # ------------------------------------------------------------------
    if CONFIG["datasets"]:
        csv_paths = [
            (EVAL_DIR / "data" / "quydinh") / f for f in CONFIG["datasets"]
        ]
    else:
        csv_paths = sorted(
            p
            for p in (EVAL_DIR / "data" / "quydinh").glob("*.csv")
            # Exclude any result CSVs that might already be in the folder root
        )

    if not csv_paths:
        logger.error("No CSV datasets found in %s", EVAL_DIR)
        sys.exit(1)

    logger.info(
        "Found %d dataset(s): %s", len(csv_paths), [p.name for p in csv_paths]
    )

    # ------------------------------------------------------------------
    # Initialise Qdrant clients (one per collection)
    # ------------------------------------------------------------------
    need_qdrant = (
        not (CONFIG["no_bge"] and CONFIG["no_e5"]) or not CONFIG["no_hybrid"]
    )
    need_es = not CONFIG["no_es"] or not CONFIG["no_hybrid"]

    qdrant_clients: List[Tuple[str, QdrantClient]] = []
    if need_qdrant:
        logger.info(
            "Connecting to Qdrant at %s:%d …",
            CONFIG["qdrant_host"],
            CONFIG["qdrant_port"],
        )
        for col in collections:
            try:
                client = QdrantClient(
                    host=CONFIG["qdrant_host"], port=CONFIG["qdrant_port"]
                )
                # Quick health-check
                client.get_collection(col)
                qdrant_clients.append((col, client))
                logger.info("  ✓ Connected to collection '%s'", col)
            except Exception as exc:
                logger.warning(
                    "  ✗ Cannot reach collection '%s': %s — skipped.", col, exc
                )

        if not qdrant_clients and need_qdrant:
            logger.error(
                "No Qdrant collections available. Set no_bge, no_e5, and no_hybrid to True to skip."
            )
            sys.exit(1)

    # ------------------------------------------------------------------
    # Load embedding models
    # ------------------------------------------------------------------
    bge_embedder: Optional[BGEm3Embedder] = None
    e5_embedder: Optional[E5MultilingualEmbedder] = None

    if qdrant_clients and (not CONFIG["no_bge"] or not CONFIG["no_hybrid"]):
        logger.info("Loading BGE-M3 model …")
        bge_embedder = BGEm3Embedder()
        logger.info("BGE-M3 loaded.")

    if qdrant_clients and (not CONFIG["no_e5"] or not CONFIG["no_hybrid"]):
        logger.info("Loading E5-multilingual model …")
        e5_embedder = E5MultilingualEmbedder()
        logger.info("E5 loaded.")

    # ------------------------------------------------------------------
    # Initialise Elasticsearch client
    # ------------------------------------------------------------------
    es_client: Optional[Elasticsearch] = None
    if need_es:
        logger.info(
            "Connecting to Elasticsearch at %s:%d …",
            CONFIG["es_host"],
            CONFIG["es_port"],
        )
        try:
            es_client = Elasticsearch(
                hosts=[f"http://{CONFIG['es_host']}:{CONFIG['es_port']}"]
            )
            if not es_client.ping():
                raise ConnectionError("Ping failed")
            logger.info("  ✓ Elasticsearch connected.")
        except Exception as exc:
            logger.warning("  ✗ Elasticsearch unavailable: %s — skipped.", exc)
            es_client = None

    # ------------------------------------------------------------------
    # Build search functions
    # ------------------------------------------------------------------

    def bge_search(query: str) -> List[Dict[str, Any]]:
        vec = bge_embedder.embed_query(query)
        return qdrant_single_vector_search(
            qdrant_clients, vec, "bge_m3", top_k, score_threshold
        )

    def e5_search(query: str) -> List[Dict[str, Any]]:
        vec = e5_embedder.embed_query(query)
        return qdrant_single_vector_search(
            qdrant_clients, vec, "e5", top_k, score_threshold
        )

    def es_search(query: str) -> List[Dict[str, Any]]:
        return es_keyword_search(es_client, es_indexes, query, top_k)

    methods_to_run: Dict[str, Any] = {}
    if bge_embedder is not None:
        methods_to_run["bge_m3"] = bge_search
    if e5_embedder is not None:
        methods_to_run["e5"] = e5_search
    if es_client is not None:
        methods_to_run["elasticsearch"] = es_search

    # ------------------------------------------------------------------
    # Build hybrid search methods (MultiCollectionSearch)
    # ------------------------------------------------------------------
    if (
        not CONFIG["no_hybrid"]
        and bge_embedder is not None
        and e5_embedder is not None
        and es_client is not None
    ):
        logger.info(
            "Building %d hybrid search config(s) …",
            len(CONFIG["hybrid_configs"]),
        )
        for hcfg in CONFIG["hybrid_configs"]:
            label = _hybrid_label(hcfg)
            try:
                multi_searcher = MultiCollectionSearch.from_collection_names(
                    collection_names=collections,
                    es_index_names=(
                        es_indexes if es_indexes != collections else None
                    ),
                    qdrant_host=CONFIG["qdrant_host"],
                    qdrant_port=CONFIG["qdrant_port"],
                    es_host=CONFIG["es_host"],
                    es_port=CONFIG["es_port"],
                    vector_weight=hcfg["vector_weight"],
                    keyword_weight=hcfg["keyword_weight"],
                )
            except Exception as exc:
                logger.warning(
                    "  ✗ Could not build hybrid '%s': %s — skipped.", label, exc
                )
                continue

            # Capture loop variables in closure
            def _make_hybrid_fn(
                searcher: MultiCollectionSearch,
                bge_emb: BGEm3Embedder,
                e5_emb: E5MultilingualEmbedder,
                tk: int,
                vp: int,
                kp: int,
                hybrid_score_thr: float,
            ):
                def _fn(query: str) -> List[Dict[str, Any]]:
                    bge_vec = bge_emb.embed_query(query)
                    e5_vec = e5_emb.embed_query(query)
                    results = searcher.search(
                        query=query,
                        bge_m3_query=bge_vec,
                        e5_query=e5_vec,
                        top_k=tk,
                        vector_top_k=tk,
                        keyword_top_k=tk,
                        vector_pool_k=vp,
                        keyword_pool_k=kp,
                    )
                    if hybrid_score_thr is not None:
                        results = [
                            r for r in results if r["score"] >= hybrid_score_thr
                        ]
                    return results

                return _fn

            methods_to_run[label] = _make_hybrid_fn(
                multi_searcher,
                bge_embedder,
                e5_embedder,
                top_k,
                hcfg.get("vector_pool_k", 15),
                hcfg.get("keyword_pool_k", 15),
                CONFIG.get("hybrid_score_threshold"),
            )
            RESULT_DIRS[label] = EVAL_DIR / label
            logger.info(
                "  ✓ Hybrid config '%s' ready  (vec_w=%.1f  kw_w=%.1f  vec_pool=%d  kw_pool=%d)",
                label,
                hcfg["vector_weight"],
                hcfg["keyword_weight"],
                hcfg.get("vector_pool_k", 15),
                hcfg.get("keyword_pool_k", 15),
            )
    elif CONFIG["no_hybrid"]:
        logger.info("Hybrid search disabled (no_hybrid=True).")
    else:
        logger.info(
            "Hybrid search skipped — requires BGE-M3, E5, and Elasticsearch to all be available."
        )

    # ------------------------------------------------------------------
    # Build reranked variants of hybrid methods
    # ------------------------------------------------------------------
    reranker: Optional[BGEReranker] = None
    if not CONFIG["no_rerank"] and not CONFIG["no_hybrid"]:
        logger.info("Loading BGE reranker …")
        try:
            reranker = BGEReranker(top_k=CONFIG["rerank_pool_k"])
            logger.info("BGE reranker loaded.")
        except Exception as exc:
            logger.warning("Could not load BGE reranker: %s — skipping.", exc)

    if reranker is not None:
        # Build reranked versions of all existing hybrid methods
        hybrid_method_labels = [
            label
            for label in list(methods_to_run.keys())
            if label.startswith("hybrid_")
        ]
        for label in hybrid_method_labels:
            reranked_label = f"{label}_reranked"
            pool_k = CONFIG["rerank_pool_k"]
            reranked_label_key = reranked_label

            # Capture variables for closure
            def _make_reranked_fn2(
                _base_label: str,
                _reranker: BGEReranker,
                _hcfg: Dict[str, Any],
                _bge_emb: BGEm3Embedder,
                _e5_emb: E5MultilingualEmbedder,
                _collections: List[str],
                _es_idxs: List[str],
                _pool_k: int,
                _score_threshold: Optional[float],
                _qdrant_host: str,
                _qdrant_port: int,
                _es_host: str,
                _es_port: int,
            ):
                try:
                    _searcher = MultiCollectionSearch.from_collection_names(
                        collection_names=_collections,
                        es_index_names=(
                            _es_idxs if _es_idxs != _collections else None
                        ),
                        qdrant_host=_qdrant_host,
                        qdrant_port=_qdrant_port,
                        es_host=_es_host,
                        es_port=_es_port,
                        vector_weight=_hcfg["vector_weight"],
                        keyword_weight=_hcfg["keyword_weight"],
                    )
                except Exception as exc:
                    logger.warning(
                        "Could not build searcher for reranked '%s': %s",
                        _base_label,
                        exc,
                    )
                    return None

                def _fn(query: str) -> List[Dict[str, Any]]:
                    bge_vec = _bge_emb.embed_query(query)
                    e5_vec = _e5_emb.embed_query(query)
                    candidates = _searcher.search(
                        query=query,
                        bge_m3_query=bge_vec,
                        e5_query=e5_vec,
                        top_k=_pool_k,
                        vector_top_k=_pool_k,
                        keyword_top_k=_pool_k,
                        vector_pool_k=_hcfg.get("vector_pool_k", 15),
                        keyword_pool_k=_hcfg.get("keyword_pool_k", 15),
                        score_threshold=_score_threshold,
                    )
                    return _reranker.rerank(query, candidates)

                return _fn

            if (
                bge_embedder is not None
                and e5_embedder is not None
                and es_client is not None
            ):
                # Find matching hybrid config by label
                matching_hcfg = next(
                    (
                        h
                        for h in CONFIG["hybrid_configs"]
                        if _hybrid_label(h) == label
                    ),
                    None,
                )
                if matching_hcfg is not None:
                    reranked_fn = _make_reranked_fn2(
                        label,
                        reranker,
                        matching_hcfg,
                        bge_embedder,
                        e5_embedder,
                        collections,
                        es_indexes,
                        pool_k,
                        score_threshold,
                        CONFIG["qdrant_host"],
                        CONFIG["qdrant_port"],
                        CONFIG["es_host"],
                        CONFIG["es_port"],
                    )
                    if reranked_fn is not None:
                        methods_to_run[reranked_label_key] = reranked_fn
                        RESULT_DIRS[reranked_label_key] = (
                            EVAL_DIR / reranked_label_key
                        )
                        logger.info(
                            "  ✓ Reranked method '%s' ready.",
                            reranked_label_key,
                        )

    if not methods_to_run:
        logger.error("No retrieval methods are available. Aborting.")
        sys.exit(1)

    logger.info("Methods to evaluate: %s", list(methods_to_run.keys()))

    # ------------------------------------------------------------------
    # Evaluate each method on each dataset
    # ------------------------------------------------------------------
    all_summaries: Dict[str, List[Dict[str, Any]]] = {
        m: [] for m in methods_to_run
    }

    for csv_path in csv_paths:
        logger.info("=== Dataset: %s ===", csv_path.name)

        for method, search_fn in methods_to_run.items():
            logger.info("  [%s] evaluating …", method)

            result_df, aggregate = evaluate_dataset(
                csv_path, method, search_fn, k
            )

            if result_df.empty:
                logger.warning("  [%s] No results — skipped.", method)
                continue

            # Save per-query CSV
            out_dir = RESULT_DIRS[method]
            out_dir.mkdir(parents=True, exist_ok=True)
            out_csv = out_dir / f"{csv_path.stem}_{method}.csv"
            result_df.to_csv(out_csv, index=False)
            logger.info(
                "  [%s] wrote %s",
                method,
                out_csv.relative_to(EVAL_DIR.parent.parent),
            )

            # Log aggregate
            logger.info(
                "  [%s] hit@1=%.3f  hit@%d=%.3f  P@%d=%.3f  R@%d=%.3f  MRR=%.3f  avg_lat=%.1fms",
                method,
                aggregate["hit@1"],
                k,
                aggregate["hit@k"],
                k,
                aggregate["precision@k"],
                k,
                aggregate["recall@k"],
                aggregate["mrr"],
                aggregate["avg_latency_ms"],
            )

            all_summaries[method].append(aggregate)

    # ------------------------------------------------------------------
    # Write per-method summary CSV
    # ------------------------------------------------------------------
    for method, summaries in all_summaries.items():
        if not summaries:
            continue
        summary_df = pd.DataFrame(summaries, columns=list(summaries[0].keys()))

        # Append a totals row (mean across datasets)
        totals = {
            "dataset": "OVERALL",
            "n_queries": summary_df["n_queries"].sum(),
            "hit@1": round(summary_df["hit@1"].mean(), 4),
            "hit@k": round(summary_df["hit@k"].mean(), 4),
            "precision@k": round(summary_df["precision@k"].mean(), 4),
            "recall@k": round(summary_df["recall@k"].mean(), 4),
            "mrr": round(summary_df["mrr"].mean(), 4),
            "avg_latency_ms": round(summary_df["avg_latency_ms"].mean(), 1),
        }
        summary_df = pd.concat(
            [summary_df, pd.DataFrame([totals])], ignore_index=True
        )

        out_path = RESULT_DIRS[method] / f"summary_{method}.csv"
        summary_df.to_csv(out_path, index=False)
        logger.info("Summary written → %s", out_path)

    # ------------------------------------------------------------------
    # Cross-method comparison (one row per dataset × method)
    # ------------------------------------------------------------------
    comparison_rows: List[Dict[str, Any]] = []
    for method, summaries in all_summaries.items():
        for s in summaries:
            row = {"method": method, **s}
            comparison_rows.append(row)

    if comparison_rows:
        comp_df = pd.DataFrame(comparison_rows)
        comp_path = EVAL_DIR / "comparison_all_methods.csv"
        comp_df.to_csv(comp_path, index=False)
        logger.info("Cross-method comparison → %s", comp_path)

    logger.info("Done.")


if __name__ == "__main__":
    main()
