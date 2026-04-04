"""Multilingual-E5-Large Embedding Model — via sentence-transformers."""

from __future__ import annotations

import logging
from typing import List, Optional

import torch
from sentence_transformers import SentenceTransformer

from embedding import BaseEmbedder

logger = logging.getLogger(__name__)


class E5MultilingualEmbedder(BaseEmbedder):
    """Wrapper around intfloat/multilingual-e5-large.

    E5 models require special prefixes:
      - query:   ``"query: <text>"``
      - passage: ``"passage: <text>"``
    This class adds the prefixes automatically in ``embed_query`` / ``embed_documents``.
    """

    DEFAULT_MODEL = "intfloat/multilingual-e5-large"
    QUERY_PREFIX = "query: "
    PASSAGE_PREFIX = "passage: "

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        device: Optional[str] = None,
        batch_size: int = 32,
        max_length: int = 512,
    ) -> None:
        self.model_name = model_name
        self.batch_size = batch_size
        self.max_length = max_length
        self._dimension = 1024

        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"

        logger.info(
            "Loading E5-multilingual model '%s' on %s", model_name, device
        )
        self._model = SentenceTransformer(
            model_name,
            device=device,
            model_kwargs={
                "low_cpu_mem_usage": True,
                "dtype": torch.float16,
            },
        )
        self._model.max_seq_length = max_length

    # ------------------------------------------------------------------
    # BaseEmbedder interface
    # ------------------------------------------------------------------

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, texts: List[str]) -> List[List[float]]:
        """Embed raw texts without any prefix (caller is responsible for prefixing)."""
        return self._encode(texts)

    def embed_query(self, text: str) -> List[float]:
        """Embed a single query with the ``query: `` prefix."""
        prefixed = f"{self.QUERY_PREFIX}{text}"
        return self._encode([prefixed])[0]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed document texts with the ``passage: `` prefix."""
        prefixed = [f"{self.PASSAGE_PREFIX}{t}" for t in texts]
        return self._encode(prefixed)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _encode(self, texts: List[str]) -> List[List[float]]:
        embeddings = self._model.encode(
            texts,
            batch_size=self.batch_size,
            show_progress_bar=False,
            normalize_embeddings=True,
        )
        return embeddings.tolist()
