"""
cluster_engine.py — Embed + Cluster chunks để tìm nhóm liên quan.

Pipeline:
  1. Nhận list chunks (dict với keys: chunk_id, content)
  2. Embed bằng BGE-M3 (sentence-transformers, local)
  3. KMeans clustering → gán cluster_id cho mỗi chunk
  4. Cung cấp API để lấy nhóm chunks liên quan

Dùng bởi ragass_generator.py để tạo Multi-chunk questions.
"""

from __future__ import annotations

import logging
import math
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# ─── Config ──────────────────────────────────────────────────────────────────

def _get_default_device() -> str:
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
    except ImportError:
        pass
    return "cpu"

EMBED_MODEL    = "BAAI/bge-m3"
EMBED_DEVICE   = _get_default_device()          # Tự động chọn mps cho Mac Apple Silicon hoặc cuda cho Nvidia GPU
CHUNKS_PER_CLUSTER = 5          # trung bình ~5 chunks/cluster
MIN_CLUSTER_SIZE   = 2          # cluster phải có ít nhất 2 chunks (cho multi-chunk)


# ─── ClusterEngine ────────────────────────────────────────────────────────────


class ClusterEngine:
    """
    Nhóm chunks liên quan bằng embedding + KMeans.

    Usage:
        engine = ClusterEngine()
        engine.fit(chunks)  # chunks: List[Dict] có keys chunk_id, content
        clusters = engine.get_cluster_map()   # Dict[int, List[Dict]]
        related  = engine.get_related_chunks("some-chunk-id", top_k=3)
    """

    def __init__(
        self,
        embed_model: str = EMBED_MODEL,
        device: str = EMBED_DEVICE,
        chunks_per_cluster: int = CHUNKS_PER_CLUSTER,
        min_cluster_size: int = MIN_CLUSTER_SIZE,
        seed: int = 42,
    ) -> None:
        self.embed_model_name = embed_model
        self.device = device
        self.chunks_per_cluster = chunks_per_cluster
        self.min_cluster_size = min_cluster_size
        self.seed = seed

        self._embedder = None
        self._chunks: List[Dict] = []
        self._embeddings: Optional[np.ndarray] = None
        self._labels: Optional[np.ndarray] = None
        self._id_to_idx: Dict[str, int] = {}
        self._cluster_map: Dict[int, List[Dict]] = {}
        self._is_fitted = False

    # ── Public API ────────────────────────────────────────────────────────────

    def fit(self, chunks: List[Dict]) -> "ClusterEngine":
        """
        Embed và cluster toàn bộ chunks.

        Args:
            chunks: List[Dict] với keys: chunk_id (str), content (str).
                    Các key khác (metadata, v.v.) sẽ được giữ nguyên.

        Returns:
            self (cho phép chaining)
        """
        if not chunks:
            raise ValueError("chunks rỗng — không thể fit ClusterEngine.")

        logger.info("ClusterEngine: fit với %d chunks (model=%s)", len(chunks), self.embed_model_name)
        self._chunks = chunks
        self._id_to_idx = {c["chunk_id"]: i for i, c in enumerate(chunks)}

        # 1. Embed
        self._embeddings = self._embed_all(chunks)

        # 2. KMeans
        n_clusters = max(2, len(chunks) // self.chunks_per_cluster)
        self._labels = self._kmeans_cluster(self._embeddings, n_clusters)

        # 3. Build cluster map (chỉ giữ clusters đủ lớn)
        self._cluster_map = self._build_cluster_map()

        self._is_fitted = True
        n_valid = sum(1 for cid, grp in self._cluster_map.items() if len(grp) >= self.min_cluster_size)
        logger.info(
            "ClusterEngine: %d clusters tổng, %d clusters có >= %d chunks (dùng được cho multi-chunk)",
            len(self._cluster_map), n_valid, self.min_cluster_size,
        )
        return self

    def get_cluster_map(self) -> Dict[int, List[Dict]]:
        """
        Trả về mapping cluster_id → list chunks trong cluster đó.
        Chỉ bao gồm clusters có ít nhất `min_cluster_size` chunks.
        """
        self._assert_fitted()
        return {
            cid: grp
            for cid, grp in self._cluster_map.items()
            if len(grp) >= self.min_cluster_size
        }

    def get_related_chunks(self, chunk_id: str, top_k: int = 3) -> List[Dict]:
        """
        Lấy top_k chunks liên quan nhất đến chunk_id (cùng cluster + sort cosine sim).

        Args:
            chunk_id: ID của chunk gốc.
            top_k: Số chunk liên quan muốn lấy (không tính chunk gốc).

        Returns:
            List chunks liên quan, sorted by cosine similarity (cao → thấp).
            Trả về [] nếu chunk_id không có trong index hoặc cluster chỉ có 1 chunk.
        """
        self._assert_fitted()

        if chunk_id not in self._id_to_idx:
            logger.warning("chunk_id '%s' không tìm thấy trong index.", chunk_id)
            return []

        idx = self._id_to_idx[chunk_id]
        assert self._labels is not None
        cluster_id = int(self._labels[idx])
        cluster_chunks = self._cluster_map.get(cluster_id, [])

        # Loại chunk gốc
        candidates = [c for c in cluster_chunks if c["chunk_id"] != chunk_id]
        if not candidates:
            return []

        # Sort by cosine similarity so sánh với chunk gốc
        assert self._embeddings is not None
        anchor_vec = self._embeddings[idx]
        scored: List[Tuple[float, Dict]] = []
        for c in candidates:
            cidx = self._id_to_idx[c["chunk_id"]]
            sim = _cosine_sim(anchor_vec, self._embeddings[cidx])
            scored.append((sim, c))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scored[:top_k]]

    def get_cluster_id(self, chunk_id: str) -> Optional[int]:
        """Trả về cluster_id của chunk, hoặc None nếu không tìm thấy."""
        self._assert_fitted()
        if chunk_id not in self._id_to_idx:
            return None
        assert self._labels is not None
        return int(self._labels[self._id_to_idx[chunk_id]])

    def get_multi_chunk_groups(
        self,
        min_size: int = 2,
        max_size: int = 3,
    ) -> List[List[Dict]]:
        """
        Trả về tất cả valid groups (cluster) để dùng cho multi-chunk questions.
        Mỗi group có từ `min_size` đến `max_size` chunks.

        Nếu cluster > max_size, sẽ chia thành nhiều sub-group (sliding window).
        """
        self._assert_fitted()
        groups: List[List[Dict]] = []

        for cluster_id, cluster_chunks in self._cluster_map.items():
            if len(cluster_chunks) < min_size:
                continue

            if len(cluster_chunks) <= max_size:
                groups.append(cluster_chunks)
            else:
                # Sliding window để tạo sub-groups
                for i in range(0, len(cluster_chunks) - min_size + 1, max_size):
                    sub = cluster_chunks[i: i + max_size]
                    if len(sub) >= min_size:
                        groups.append(sub)

        logger.info("ClusterEngine: %d multi-chunk groups khả dụng", len(groups))
        return groups

    def stats(self) -> Dict:
        """Thống kê về clusters."""
        self._assert_fitted()
        sizes = [len(v) for v in self._cluster_map.values()]
        valid_sizes = [s for s in sizes if s >= self.min_cluster_size]
        return {
            "total_chunks": len(self._chunks),
            "total_clusters": len(self._cluster_map),
            "valid_clusters": len(valid_sizes),
            "avg_cluster_size": round(np.mean(sizes), 2) if sizes else 0,
            "max_cluster_size": max(sizes) if sizes else 0,
            "min_cluster_size": min(sizes) if sizes else 0,
        }

    # ── Private helpers ───────────────────────────────────────────────────────

    def _assert_fitted(self) -> None:
        if not self._is_fitted:
            raise RuntimeError("ClusterEngine chưa được fit. Gọi .fit(chunks) trước.")

    def _get_embedder(self):
        if self._embedder is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError:
                raise ImportError(
                    "Cần cài sentence-transformers:\n"
                    "  pip install sentence-transformers"
                )
            logger.info("ClusterEngine: Loading embedding model '%s' (device=%s)...", self.embed_model_name, self.device)
            self._embedder = SentenceTransformer(self.embed_model_name, device=self.device)
            logger.info("ClusterEngine: Model loaded.")
        return self._embedder

    def _embed_all(self, chunks: List[Dict]) -> np.ndarray:
        """Embed toàn bộ chunks, trả về numpy array (N, D)."""
        embedder = self._get_embedder()
        texts = [c["content"] for c in chunks]
        logger.info("ClusterEngine: Embedding %d texts...", len(texts))
        embeddings = embedder.encode(
            texts,
            batch_size=32,
            show_progress_bar=True,
            normalize_embeddings=True,
        )
        logger.info("ClusterEngine: Done embedding. Shape=%s", embeddings.shape)
        return embeddings

    def _kmeans_cluster(self, embeddings: np.ndarray, n_clusters: int) -> np.ndarray:
        """Chạy KMeans, trả về array labels (N,)."""
        try:
            from sklearn.cluster import KMeans
        except ImportError:
            raise ImportError(
                "Cần cài scikit-learn:\n"
                "  pip install scikit-learn"
            )
        n_clusters = min(n_clusters, len(embeddings))
        logger.info("ClusterEngine: KMeans với n_clusters=%d...", n_clusters)
        km = KMeans(n_clusters=n_clusters, random_state=self.seed, n_init="auto")
        labels = km.fit_predict(embeddings)
        logger.info("ClusterEngine: KMeans done.")
        return labels

    def _build_cluster_map(self) -> Dict[int, List[Dict]]:
        """Tạo mapping cluster_id → list chunks."""
        cluster_map: Dict[int, List[Dict]] = {}
        for i, chunk in enumerate(self._chunks):
            assert self._labels is not None
            cid = int(self._labels[i])
            cluster_map.setdefault(cid, []).append(chunk)
        return cluster_map


# ─── Utilities ────────────────────────────────────────────────────────────────


def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity giữa 2 vectors (đã normalized → dot product)."""
    return float(np.dot(a, b))


# ─── CLI test ──────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    import json, sys
    from pathlib import Path

    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")

    # Test với stsv chunks
    test_file = Path(__file__).parent.parent.parent / "data/stsv/chunks/stsv_all_chunks.json"
    if not test_file.exists():
        print(f"File không tìm thấy: {test_file}")
        sys.exit(1)

    with open(test_file, encoding="utf-8") as f:
        raw_chunks = json.load(f)

    # Chuẩn hóa sang dict {chunk_id, content, ...}
    chunks = [
        {"chunk_id": c["chunk_id"], "content": c["content"], "metadata": c.get("metadata", {})}
        for c in raw_chunks
        if len(c.get("content", "")) >= 100
    ][:50]  # Test với 50 chunks đầu

    print(f"Test với {len(chunks)} chunks...")
    engine = ClusterEngine()
    engine.fit(chunks)

    print("\n📊 Stats:", json.dumps(engine.stats(), ensure_ascii=False, indent=2))

    groups = engine.get_multi_chunk_groups()
    print(f"\n✅ {len(groups)} multi-chunk groups")
    if groups:
        print(f"\nSample group (cluster {engine.get_cluster_id(groups[0][0]['chunk_id'])}):")
        for c in groups[0]:
            print(f"  • [{c['chunk_id'][:8]}...] {c['content'][:80]}...")
