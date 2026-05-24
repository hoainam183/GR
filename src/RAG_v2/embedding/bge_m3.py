"""BGE-M3 Embedding Model — dense + sparse via FlagEmbedding."""

from __future__ import annotations

import hashlib
import logging
from collections import OrderedDict
from typing import Dict, List, Optional

import numpy as np
import torch
from FlagEmbedding import BGEM3FlagModel

from embedding import BaseEmbedder

logger = logging.getLogger(__name__)


class _EmbeddingCache:
    """Thread-safe LRU cache for embedding vectors.

    Avoids recomputing embeddings for repeated queries. Uses an OrderedDict
    for O(1) eviction of the least-recently-used entry.
    """

    def __init__(self, maxsize: int = 512) -> None:
        self._maxsize = maxsize
        self._cache: OrderedDict[str, List[float]] = OrderedDict()
        self._hits = 0
        self._misses = 0

    def _key(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def get(self, text: str) -> Optional[List[float]]:
        key = self._key(text)
        if key in self._cache:
            self._cache.move_to_end(key)
            self._hits += 1
            return self._cache[key]
        self._misses += 1
        return None

    def put(self, text: str, vector: List[float]) -> None:
        key = self._key(text)
        self._cache[key] = vector
        self._cache.move_to_end(key)
        if len(self._cache) > self._maxsize:
            self._cache.popitem(last=False)

    @property
    def stats(self) -> Dict[str, int]:
        return {"hits": self._hits, "misses": self._misses, "size": len(self._cache)}


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


class BGEm3Embedder(BaseEmbedder):
    """Wrapper around BAAI/bge-m3 for dense and sparse embeddings.

    Attributes:
        model_name: HuggingFace model identifier.
        _model: Loaded FlagEmbedding model instance.
        _dimension: Vector dimension (1024 for BGE-M3).
    """

    DEFAULT_MODEL = "BAAI/bge-m3"

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        use_fp16: bool = True,
        device: Optional[str] = None,
        batch_size: int = 32,
        max_length: int = 512,
    ) -> None:
        self.model_name = model_name
        self.batch_size = batch_size
        self.max_length = max_length
        self._dimension = 1024

        device = _resolve_torch_device(device)

        # FlagEmbedding fp16 acceleration is intended for CUDA only.
        if device != "cuda":
            use_fp16 = False

        logger.info(
            "Loading BGE-M3 model '%s' on %s (fp16=%s)",
            model_name,
            device,
            use_fp16,
        )
        self._model = BGEM3FlagModel(
            model_name,
            use_fp16=use_fp16,
            device=device,
        )
        self._query_cache = _EmbeddingCache(maxsize=512)

    # ------------------------------------------------------------------
    # BaseEmbedder interface
    # ------------------------------------------------------------------

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, texts: List[str]) -> List[List[float]]:
        """Return dense embeddings for a list of texts."""
        return self._encode_dense(texts)

    def embed_query(self, text: str) -> List[float]:
        cached = self._query_cache.get(text)
        if cached is not None:
            return cached
        vec = self._encode_dense([text])[0]
        self._query_cache.put(text, vec)
        return vec

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self._encode_dense(texts)

    # ------------------------------------------------------------------
    # Dense encoding
    # ------------------------------------------------------------------

    def _encode_dense(self, texts: List[str]) -> List[List[float]]:
        output = self._model.encode(
            texts,
            batch_size=self.batch_size,
            max_length=self.max_length,
            return_dense=True,
            return_sparse=False,
            return_colbert_vecs=False,
        )
        dense: np.ndarray = output["dense_vecs"]
        return dense.tolist()

    # ------------------------------------------------------------------
    # Sparse encoding (for keyword-matching / hybrid search)
    # ------------------------------------------------------------------

    def encode_sparse(self, texts: List[str]) -> List[Dict[int, float]]:
        """Return sparse (token-weight) embeddings.

        Each element is a dict mapping token-id → weight.
        Useful for keyword-level matching in Qdrant sparse vectors.
        """
        output = self._model.encode(
            texts,
            batch_size=self.batch_size,
            max_length=self.max_length,
            return_dense=False,
            return_sparse=True,
            return_colbert_vecs=False,
        )
        return output["lexical_weights"]

    # ------------------------------------------------------------------
    # Convenience: dense + sparse in one call
    # ------------------------------------------------------------------

    def encode_all(self, texts: List[str]) -> Dict[str, object]:
        """Return both dense and sparse representations.

        Returns:
            {"dense_vecs": List[List[float]], "lexical_weights": List[Dict[int, float]]}
        """
        output = self._model.encode(
            texts,
            batch_size=self.batch_size,
            max_length=self.max_length,
            return_dense=True,
            return_sparse=True,
            return_colbert_vecs=False,
        )
        return {
            "dense_vecs": (
                output["dense_vecs"].tolist()
                if isinstance(output["dense_vecs"], np.ndarray)
                else output["dense_vecs"]
            ),
            "lexical_weights": output["lexical_weights"],
        }
