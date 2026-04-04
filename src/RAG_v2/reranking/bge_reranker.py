"""BGE Reranker — cross-encoder reranking with BAAI/bge-reranker-v2-m3."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import torch
from FlagEmbedding import FlagReranker

from reranking.base import BaseReranker, register_reranker

logger = logging.getLogger(__name__)

# ─── Constants ──────────────────────────────────────────────────────────────────
DEFAULT_MODEL = "BAAI/bge-reranker-v2-m3"
DEFAULT_TOP_K = 5


# ═══════════════════════════════════════════════════════════════════════════════
@register_reranker("bge")
class BGEReranker(BaseReranker):
    """Cross-encoder reranker using BAAI/bge-reranker-v2-m3.

    Scores every (query, document) pair independently and returns
    documents sorted by relevance score.

    Parameters:
        model_name: HuggingFace model id for the reranker.
        device: ``"cuda"`` or ``"cpu"``; auto-detected when *None*.
        use_fp16: Use half-precision on CUDA for faster inference.
        batch_size: Pairs processed per forward pass.
        top_k: Default number of top documents to keep after reranking.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        device: Optional[str] = None,
        use_fp16: Optional[bool] = None,
        batch_size: int = 32,
        top_k: int = DEFAULT_TOP_K,
    ) -> None:
        self.model_name = model_name
        self.batch_size = batch_size
        self.top_k = top_k

        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device

        if use_fp16 is None:
            use_fp16 = device == "cuda"

        logger.info(
            "Loading BGE reranker '%s' on %s (fp16=%s)",
            model_name,
            device,
            use_fp16,
        )
        self._model = FlagReranker(model_name, device=device, use_fp16=use_fp16)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Rerank *documents* against *query* and return the top-K.

        Each document dict **must** contain a ``"text"`` key.  The returned
        list is sorted by descending relevance score, each dict augmented
        with a ``"rerank_score"`` field.

        Args:
            query: The user query.
            documents: Candidate documents from retrieval stage.
            top_k: Override instance default for number of results.

        Returns:
            Top-K documents sorted by rerank score (descending).
        """
        if not documents:
            return []

        top_k = top_k or self.top_k

        # Build (query, doc_text) pairs
        pairs = [[query, doc["text"]] for doc in documents]

        # Compute relevance scores
        scores = self._model.compute_score(pairs, batch_size=self.batch_size)

        # compute_score returns a single float when len(pairs) == 1
        if isinstance(scores, (int, float)):
            scores = [scores]

        # Attach score and sort
        scored_docs: List[Dict[str, Any]] = []
        for doc, score in zip(documents, scores):
            enriched = {**doc, "rerank_score": float(score)}
            scored_docs.append(enriched)

        scored_docs.sort(key=lambda d: d["rerank_score"], reverse=True)

        logger.info(
            "Reranked %d docs → top %d (best=%.4f, worst=%.4f)",
            len(documents),
            min(top_k, len(scored_docs)),
            scored_docs[0]["rerank_score"] if scored_docs else 0.0,
            (
                scored_docs[min(top_k, len(scored_docs)) - 1]["rerank_score"]
                if scored_docs
                else 0.0
            ),
        )

        return scored_docs[:top_k]
