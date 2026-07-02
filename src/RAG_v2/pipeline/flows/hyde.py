"""HyDE post-rerank fallback."""

from __future__ import annotations

import logging
import time

from typing import Any, Dict, Generator, List, Optional, Set

from .common import (
    _cfg_bool,
    _cfg_int,
    _elapsed_ms,
)
from .rerank_scoring import _best_explicit_rerank_score
from .retrieval_helpers import (
    _dedup_retrieval_candidates,
    _reranker_kwargs,
)

logger = logging.getLogger(__name__)



# â”€â”€ HyDE post-rerank fallback â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


def _should_trigger_hyde(
    reranked: List[Dict[str, Any]],
    reranker: Optional[Any],
    cfg: Dict[str, Any],
) -> bool:
    """Decide whether HyDE second-pass retrieval should run.

    Triggers when ``hyde_enabled`` is True AND retrieval recall looks poor:
      1. No documents survived reranking, OR
      2. The best explicit rerank score is negative (all docs irrelevant), OR
      3. Fewer than ``hyde_min_results`` documents survived (sparse recall).

    The ``hyde_confidence_threshold`` (mean-score) path of ``should_use_hyde``
    is intentionally NOT used here: cross-encoder rerank scores are unnormalised
    logits, so a fixed 0.3 mean threshold would fire on almost every query. It
    stays a reserved rollout flag.
    """
    if not _cfg_bool(cfg, "hyde_enabled", False):
        return False

    best = _best_explicit_rerank_score(reranked)
    if not reranked or (best is not None and best < 0.0):
        logger.info(
            "HyDE trigger: best rerank score=%.4f (negative or empty)",
            best if best is not None else -999.0,
        )
        return True

    min_results = _cfg_int(cfg, "hyde_min_results", 3)
    if len(reranked) < min_results:
        logger.info(
            "HyDE trigger: only %d result(s) < hyde_min_results=%d",
            len(reranked),
            min_results,
        )
        return True

    return False


def _hyde_fallback_post_rerank(
    *,
    reranked: List[Dict[str, Any]],
    raw_candidate_k: int,
    retrieval_query: str,
    rerank_query: str,
    top_k_value: int,
    bge_embedder: Any,
    e5_embedder: Any,
    searcher: Any,
    reranker: Optional[Any],
    chat_model: Any,
    target_collections: Optional[List[str]],
    resolved_major: Optional[str],
    resolved_cohort: Optional[str],
    cfg: Dict[str, Any],
    timings_ms: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Run HyDE second-pass retrieval and merge with existing results.

    1. Generate a hypothetical answer via LLM.
    2. Embed the hypothesis with BGE-M3 (E5 uses original query).
    3. Search with the HyDE vector.
    4. Merge + dedup with existing reranked pool.
    5. Re-rerank the merged pool.

    Returns the updated reranked list (or original if HyDE adds nothing).
    """
    from retrieval.hyde import HyDEExpander

    hyde_t0 = time.perf_counter()
    try:
        hyde = HyDEExpander(llm=chat_model, embedder=bge_embedder)
        hyde_vec = hyde.generate_embedding(retrieval_query)
        e5_vec = e5_embedder.embed_query(retrieval_query)

        search_kwargs: Dict[str, Any] = {
            "query": retrieval_query,
            "bge_m3_query": hyde_vec,
            "e5_query": e5_vec,
            "top_k": raw_candidate_k,
            "vector_top_k": cfg.get("vector_top_k", 20),
            "keyword_top_k": cfg.get("keyword_top_k", 20),
            "vector_pool_k": cfg.get("vector_pool_k", 15),
            "keyword_pool_k": cfg.get("keyword_pool_k", 15),
            "active_collections": target_collections,
        }
        if resolved_major:
            search_kwargs["resolved_major"] = resolved_major
        if resolved_cohort:
            search_kwargs["resolved_cohort"] = resolved_cohort

        hyde_results = searcher.search(**search_kwargs)

        if not hyde_results:
            logger.info("HyDE fallback: no new candidates found")
            timings_ms["hyde"] = _elapsed_ms(hyde_t0)
            timings_ms["hyde_triggered"] = 1.0
            timings_ms["hyde_new_candidates"] = 0.0
            return reranked

        # Merge + dedup with existing reranked pool
        merged = _dedup_retrieval_candidates(
            reranked + hyde_results,
            top_k=raw_candidate_k,
        )
        new_count = len(merged) - len(reranked)
        logger.info(
            "HyDE fallback: merged %d new candidates (total pool=%d)",
            max(new_count, 0),
            len(merged),
        )

        # Re-rerank the merged pool
        if reranker is not None:
            reranked = reranker.rerank(
                query=rerank_query,
                documents=merged,
                top_k=top_k_value,
                **_reranker_kwargs(cfg, top_k_value),
            )
        else:
            reranked = sorted(
                merged, key=lambda d: d.get("score", 0.0), reverse=True
            )[:top_k_value]

        timings_ms["hyde"] = _elapsed_ms(hyde_t0)
        timings_ms["hyde_triggered"] = 1.0
        timings_ms["hyde_new_candidates"] = float(max(new_count, 0))
        return reranked

    except Exception:
        logger.warning(
            "HyDE fallback failed, continuing with original results",
            exc_info=True,
        )
        timings_ms["hyde"] = _elapsed_ms(hyde_t0)
        timings_ms["hyde_failed"] = 1.0
        return reranked
