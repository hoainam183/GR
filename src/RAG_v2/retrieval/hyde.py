"""HyDE (Hypothetical Document Embedding) — fallback for low-recall queries.

When initial retrieval returns few or low-confidence results, HyDE generates
a hypothetical answer to the query, embeds it, and uses that embedding for
a second-pass vector search.  The hypothesis embedding often captures the
semantic space of relevant documents better than the raw question embedding.

This module provides an optional fallback that integrates into the retrieval
service — it is NOT called on every query.  It activates only when:
  1. Initial retrieval returned fewer than ``min_results`` candidates, OR
  2. Reranker mean score falls below ``confidence_threshold``.

Usage::

    from retrieval.hyde import HyDEExpander

    hyde = HyDEExpander(llm=chat_model, embedder=bge_embedder)
    if should_use_hyde(initial_results, reranker_stats):
        hyde_vec = hyde.generate_embedding(query)
        # Use hyde_vec for second-pass vector search
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Default Vietnamese academic domain prompt template
_HYPOTHESIS_PROMPT_VI = (
    "Bạn là trợ lý học thuật của Đại học Bách khoa Hà Nội (HUST). "
    "Hãy viết một đoạn trả lời ngắn gọn (150-200 từ) cho câu hỏi sau "
    "như thể bạn đang trích dẫn từ tài liệu chính thức của trường:\n\n"
    "Câu hỏi: {query}\n\n"
    "Trả lời:"
)


class HyDEExpander:
    """Generate hypothetical document embeddings for improved recall.

    Parameters:
        llm: Any LLM instance with a ``generate(prompt: str) -> str`` method.
        embedder: Any embedder instance with an ``embed_query(text: str) -> List[float]`` method.
        prompt_template: Template with ``{query}`` placeholder for hypothesis generation.
        max_hypothesis_len: Truncate hypothesis to this many characters before embedding.
    """

    def __init__(
        self,
        llm: Any,
        embedder: Any,
        prompt_template: Optional[str] = None,
        max_hypothesis_len: int = 800,
    ) -> None:
        self.llm = llm
        self.embedder = embedder
        self.prompt_template = prompt_template or _HYPOTHESIS_PROMPT_VI
        self.max_hypothesis_len = max_hypothesis_len

    def generate_hypothesis(self, query: str) -> str:
        """Generate a hypothetical answer to the query.

        Args:
            query: The user's search query.

        Returns:
            A hypothetical answer string (may be truncated).
        """
        prompt = self.prompt_template.format(query=query)
        try:
            hypothesis = self.llm.generate(prompt)
            if not hypothesis or not hypothesis.strip():
                logger.warning("HyDE: LLM returned empty hypothesis for query: %s", query[:60])
                return query  # fallback to original query
            return hypothesis[: self.max_hypothesis_len]
        except Exception as exc:
            logger.error("HyDE generation failed: %s — falling back to raw query", exc)
            return query

    def generate_embedding(self, query: str) -> List[float]:
        """Generate a HyDE embedding: hypothesis → embed.

        Args:
            query: The user's search query.

        Returns:
            Dense vector embedding of the hypothetical answer.
        """
        hypothesis = self.generate_hypothesis(query)
        logger.info("HyDE hypothesis (first 100 chars): %s", hypothesis[:100])
        return self.embedder.embed_query(hypothesis)


def should_use_hyde(
    results: List[Dict[str, Any]],
    reranker_stats: Optional[Dict[str, Any]] = None,
    *,
    min_results: int = 3,
    confidence_threshold: float = 0.3,
) -> bool:
    """Determine whether HyDE fallback should be triggered.

    Args:
        results: Initial retrieval results (post-rerank if available).
        reranker_stats: Stats dict from reranker (``last_stats``).
        min_results: Trigger HyDE if fewer results than this.
        confidence_threshold: Trigger HyDE if mean rerank score is below this.

    Returns:
        True if HyDE should be attempted.
    """
    if len(results) < min_results:
        logger.info(
            "HyDE trigger: only %d results (threshold=%d)",
            len(results),
            min_results,
        )
        return True

    if reranker_stats:
        mean_score = reranker_stats.get("rerank_score_mean", 1.0)
        if mean_score < confidence_threshold:
            logger.info(
                "HyDE trigger: reranker mean=%.4f < threshold=%.4f",
                mean_score,
                confidence_threshold,
            )
            return True

    return False
