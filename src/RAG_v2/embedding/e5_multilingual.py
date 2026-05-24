"""Multilingual-E5-Large Embedding Model — via sentence-transformers."""

from __future__ import annotations

import hashlib
import logging
from collections import OrderedDict
from typing import Dict, List, Optional

import torch
from sentence_transformers import SentenceTransformer

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

        device = _resolve_torch_device(device)
        dtype = torch.float16 if device == "cuda" else torch.float32

        logger.info(
            "Loading E5-multilingual model '%s' on %s", model_name, device
        )
        self._model = SentenceTransformer(
            model_name,
            device=device,
            model_kwargs={
                "low_cpu_mem_usage": True,
                "dtype": dtype,
            },
        )
        self._model.max_seq_length = max_length
        self._query_cache = _EmbeddingCache(maxsize=512)

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
        cached = self._query_cache.get(text)
        if cached is not None:
            return cached
        prefixed = f"{self.QUERY_PREFIX}{text}"
        vec = self._encode([prefixed])[0]
        self._query_cache.put(text, vec)
        return vec

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
