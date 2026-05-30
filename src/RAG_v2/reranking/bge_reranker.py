"""BGE Reranker — cross-encoder reranking with BAAI/bge-reranker-v2-m3."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import torch
from FlagEmbedding import FlagReranker

from reranking.base import BaseReranker, register_reranker

logger = logging.getLogger(__name__)


def _resolve_torch_device(device: Optional[str]) -> str:
    """Resolve runtime device with CUDA first, then Apple MPS, then CPU."""
    if device:
        return device
    if torch.cuda.is_available():
        return "cuda"
    mps_backend = getattr(torch.backends, "mps", None)
    if mps_backend is not None and mps_backend.is_available():
        return "mps"
    return "cpu"

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
        score_threshold: float = 0.0,
        table_score_threshold: float = -3.0,
    ) -> None:
        self.model_name = model_name
        self.batch_size = batch_size
        self.top_k = top_k
        self.score_threshold = score_threshold
        self.table_score_threshold = table_score_threshold
        self.last_stats: Dict[str, Any] = {}

        device = _resolve_torch_device(device)
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
        score_threshold: Optional[float] = None,
        table_score_threshold: Optional[float] = None,
        min_top_k: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Rerank *documents* against *query* and return the top-K.

        Each document dict **must** contain a ``"text"`` key.  The returned
        list contains threshold-passing documents first, followed by optional
        below-threshold fallback documents when ``min_top_k`` is set.  Each
        dict is augmented with a ``"rerank_score"`` field.

        Args:
            query: The user query.
            documents: Candidate documents from retrieval stage.
            top_k: Override instance default for number of results.
            score_threshold: Override instance default score threshold.
            min_top_k: Keep at least this many scored documents, capped by
                ``top_k``, by appending below-threshold candidates if needed.

        Returns:
            Up to top-K documents after threshold filtering, with optional
            below-threshold fallback documents appended when ``min_top_k`` is
            set and the strict filtered result is too small.
        """
        if not documents:
            return []

        top_k = top_k or self.top_k
        threshold = score_threshold if score_threshold is not None else self.score_threshold
        table_thresh = table_score_threshold if table_score_threshold is not None else getattr(self, "table_score_threshold", threshold)

        # Build (query, doc_text) pairs — prepend metadata for richer context
        pairs = [(query, self._enrich_text_for_reranking(doc)) for doc in documents]

        # Compute relevance scores
        scores = self._model.compute_score(pairs, batch_size=self.batch_size)
        if scores is None:
            scores = []

        # compute_score returns a single float when len(pairs) == 1
        if isinstance(scores, (int, float)):
            scores = [scores]

        # Attach score and sort
        scored_docs: List[Dict[str, Any]] = []
        for doc, score in zip(documents, scores):
            enriched = {**doc, "rerank_score": float(score)}
            scored_docs.append(enriched)

        scored_docs.sort(key=lambda d: d["rerank_score"], reverse=True)

        # Apply per-document score threshold BEFORE top_k truncation.
        # This prevents table docs (with relaxed table_score_threshold) from
        # being excluded when higher-ranked non-table docs (all failing the
        # stricter default threshold) fill the top_k slots first.
        filtered = []
        threshold_dropped = 0
        for d in scored_docs:
            has_table = d.get("metadata", {}).get("has_table", False)
            doc_thresh = table_thresh if has_table else threshold
            if d["rerank_score"] >= doc_thresh:
                filtered.append(d)
            else:
                threshold_dropped += 1

        # Now apply top_k on the threshold-passing documents.  Keep this
        # strict list separately so evaluation can measure threshold impact.
        strict_top_docs = filtered[:top_k]
        top_docs = list(strict_top_docs)

        fallback_used = False
        fallback_count = 0
        if min_top_k:
            target_count = min(top_k, int(min_top_k), len(scored_docs))
            if len(top_docs) < target_count:
                selected_ids = {id(doc) for doc in top_docs}
                for doc in scored_docs:
                    if id(doc) in selected_ids:
                        continue
                    top_docs.append(doc)
                    selected_ids.add(id(doc))
                    if len(top_docs) >= target_count:
                        break
                fallback_count = len(top_docs) - len(strict_top_docs)
                fallback_used = fallback_count > 0

        all_scores = [float(d["rerank_score"]) for d in scored_docs]
        self.last_stats = {
            "rerank_candidate_count": len(scored_docs),
            "rerank_threshold_dropped_count": threshold_dropped,
            "rerank_dropped_count": max(0, len(scored_docs) - len(top_docs)),
            "rerank_passing_count": len(filtered),
            "rerank_strict_returned_count": len(strict_top_docs),
            "rerank_strict_returned_ids": [
                self._doc_id_for_stats(doc) for doc in strict_top_docs
            ],
            "rerank_threshold_fallback_used": fallback_used,
            "rerank_threshold_fallback_count": fallback_count,
            "rerank_returned_count": len(top_docs),
            "rerank_score_min": round(min(all_scores), 6) if all_scores else 0.0,
            "rerank_score_max": round(max(all_scores), 6) if all_scores else 0.0,
            "rerank_score_mean": (
                round(sum(all_scores) / len(all_scores), 6) if all_scores else 0.0
            ),
        }

        if len(filtered) < len(scored_docs):
            logger.info(
                "Score thresholds (default=%.2f, table=%.2f) dropped %d doc(s) → %d passing → top %d",
                threshold,
                table_thresh,
                len(scored_docs) - len(filtered),
                len(filtered),
                len(top_docs),
            )
        if fallback_used:
            logger.info(
                "min_top_k fallback appended %d below-threshold doc(s) → top %d",
                fallback_count,
                len(top_docs),
            )

        logger.info(
            "Reranked %d docs → top %d (best=%.4f, worst=%.4f)",
            len(documents),
            len(top_docs),
            top_docs[0]["rerank_score"] if top_docs else 0.0,
            top_docs[-1]["rerank_score"] if top_docs else 0.0,
        )

        return top_docs

    # ------------------------------------------------------------------
    # Metadata enrichment
    # ------------------------------------------------------------------

    @staticmethod
    def _doc_id_for_stats(doc: Dict[str, Any]) -> str:
        metadata = doc.get("metadata") if isinstance(doc.get("metadata"), dict) else {}
        for value in (
            doc.get("id"),
            doc.get("chunk_id"),
            doc.get("source_id"),
            metadata.get("chunk_id"),
            metadata.get("id"),
            metadata.get("doc_id"),
            metadata.get("document_id"),
        ):
            text = str(value or "").strip()
            if text:
                return text.split("/", 1)[-1] if "/" in text else text
        return ""

    @staticmethod
    def _enrich_text_for_reranking(doc: Dict[str, Any]) -> str:
        """Prepend metadata context to document text for richer cross-encoder scoring.

        Cross-encoders like BGE work best when both query and document share
        explicit semantic cues.  Hierarchy paths, major names, and document
        titles give the model structural context that raw chunk text alone
        often lacks.
        """
        meta = doc.get("metadata") or {}
        prefix_parts: List[str] = []
        if meta.get("hierarchy_path"):
            prefix_parts.append(meta["hierarchy_path"])
        if meta.get("major_code"):
            prefix_parts.append(f"Ngành: {meta['major_code']}")
        if meta.get("title"):
            prefix_parts.append(f"Tài liệu: {meta['title']}")
        prefix = " | ".join(prefix_parts)
        text = doc.get("text", "")
        return f"{prefix}\n{text}" if prefix else text
