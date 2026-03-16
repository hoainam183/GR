"""Ensemble Embedding — weighted average of multiple embedders."""

from __future__ import annotations

import logging
from typing import List, Optional

import numpy as np

from embedding import BaseEmbedder

logger = logging.getLogger(__name__)


class EnsembleEmbedder(BaseEmbedder):
    """Combine multiple BaseEmbedder instances via weighted average.

    All child embedders **must** produce vectors of the same dimension.

    Args:
        embedders: Ordered list of BaseEmbedder instances.
        weights: Optional list of floats (same length as *embedders*).
                 If ``None``, equal weights are used.
    """

    def __init__(
        self,
        embedders: List[BaseEmbedder],
        weights: Optional[List[float]] = None,
    ) -> None:
        if not embedders:
            raise ValueError("At least one embedder is required.")

        dims = {e.dimension for e in embedders}
        if len(dims) > 1:
            raise ValueError(
                f"All embedders must share the same dimension, got {dims}"
            )

        self._embedders = embedders
        self._dimension = embedders[0].dimension

        if weights is None:
            weights = [1.0 / len(embedders)] * len(embedders)
        else:
            if len(weights) != len(embedders):
                raise ValueError("weights length must match embedders length.")
            total = sum(weights)
            weights = [w / total for w in weights]

        self._weights = np.array(weights, dtype=np.float64)
        logger.info(
            "EnsembleEmbedder: %d embedders, weights=%s, dim=%d",
            len(embedders),
            self._weights.tolist(),
            self._dimension,
        )

    # ------------------------------------------------------------------
    # BaseEmbedder interface
    # ------------------------------------------------------------------

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, texts: List[str]) -> List[List[float]]:
        return self._weighted_average("embed", texts)

    def embed_query(self, text: str) -> List[float]:
        vectors = [e.embed_query(text) for e in self._embedders]
        arr = np.array(vectors, dtype=np.float64)  # (n_embedders, dim)
        combined = np.dot(self._weights, arr)  # (dim,)
        # L2-normalize the combined vector
        norm = np.linalg.norm(combined)
        if norm > 0:
            combined = combined / norm
        return combined.tolist()

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self._weighted_average("embed_documents", texts)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _weighted_average(
        self, method: str, texts: List[str]
    ) -> List[List[float]]:
        """Compute weighted average across embedders for a batch.

        Args:
            method: Name of the BaseEmbedder method to call.
            texts: Input texts.

        Returns:
            List of L2-normalized combined vectors.
        """
        # all_vecs shape: (n_embedders, n_texts, dim)
        all_vecs = np.array(
            [getattr(e, method)(texts) for e in self._embedders],
            dtype=np.float64,
        )
        # weighted sum → (n_texts, dim)
        combined = np.tensordot(self._weights, all_vecs, axes=([0], [0]))
        # L2-normalize each row
        norms = np.linalg.norm(combined, axis=1, keepdims=True)
        norms = np.where(norms > 0, norms, 1.0)
        combined = combined / norms
        return combined.tolist()
