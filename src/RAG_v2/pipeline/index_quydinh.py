"""
Index Quydinh chunks into Qdrant
=================================
Loads all *_chunks.json files from a folder (default:
data/quydinh/olmocr/chunks_recursive_parent_child), embeds each chunk
with BGE-M3 + E5, then upserts them into the Qdrant collection.

Because Qdrant upsert is idempotent by point-ID, running this script a
second time (or adding new files) will NOT overwrite existing points that
have different IDs.

Usage (from RAG_v2/):
    python pipeline/index_quydinh.py
    python pipeline/index_quydinh.py --collection quydinh --batch-size 16
    python pipeline/index_quydinh.py --chunks-dir data/stsv/chunks_recursive_parent_child --collection stsv
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent  # …/RAG_v2
sys.path.insert(0, str(PROJECT_ROOT))

from embedding.bge_m3 import BGEm3Embedder
from embedding.e5_multilingual import E5MultilingualEmbedder
from retrieval.qdrant_store import QdrantStore

# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

DEFAULT_CHUNKS_DIR = (
    PROJECT_ROOT
    / "data"
    / "quydinh"
    / "olmocr"
    / "chunks_recursive_parent_child"
)
DEFAULT_COLLECTION = "quydinh"
DEFAULT_BATCH_SIZE = 32


# ---------------------------------------------------------------------------


def load_chunks_from_dir(chunks_dir: Path) -> List[Dict[str, Any]]:
    """Load and merge all *_chunks.json files in *chunks_dir*, filtering only child chunks."""
    json_files = sorted(chunks_dir.glob("*_chunks.json"))
    if not json_files:
        raise FileNotFoundError(f"No *_chunks.json files found in {chunks_dir}")

    all_chunks: List[Dict[str, Any]] = []
    for path in json_files:
        logger.info("  Loading %s", path.name)
        with open(path, "r", encoding="utf-8") as f:
            chunks = json.load(f)
        # Filter to only include child chunks (level == "child")
        child_chunks = [
            c for c in chunks if c.get("metadata", {}).get("level") == "child"
        ]
        all_chunks.extend(child_chunks)
        logger.info(
            "    -> %d child chunks (running total: %d)",
            len(child_chunks),
            len(all_chunks),
        )

    logger.info(
        "Total child chunks loaded: %d from %d files.",
        len(all_chunks),
        len(json_files),
    )
    return all_chunks


def embed_batch(
    texts: List[str],
    bge: BGEm3Embedder,
    e5: E5MultilingualEmbedder,
) -> tuple[List[List[float]], List[List[float]]]:
    bge_vecs = bge.embed_documents(texts)
    e5_vecs = e5.embed_documents(texts)
    return bge_vecs, e5_vecs


def index_chunks(
    chunks: List[Dict[str, Any]],
    store: QdrantStore,
    bge: BGEm3Embedder,
    e5: E5MultilingualEmbedder,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> None:
    total = len(chunks)
    logger.info("Indexing %d chunks in batches of %d …", total, batch_size)

    indexed = 0
    for start in range(0, total, batch_size):
        batch = chunks[start : start + batch_size]

        texts = [c["content"] for c in batch]
        # Prefer the UUID "id" field; fall back to "chunk_id" string
        ids = [c.get("id") or c["chunk_id"] for c in batch]
        metadatas = [c.get("metadata", {}) for c in batch]

        t0 = time.perf_counter()
        bge_vecs, e5_vecs = embed_batch(texts, bge, e5)
        embed_sec = time.perf_counter() - t0

        store.index_documents(
            texts=texts,
            bge_m3_vectors=bge_vecs,
            e5_vectors=e5_vecs,
            metadatas=metadatas,
            ids=ids,
        )

        indexed += len(batch)
        logger.info(
            "[%d/%d] batch upserted (embed=%.2fs, size=%d)",
            indexed,
            total,
            embed_sec,
            len(batch),
        )

    logger.info(
        "Done. %d documents stored in collection '%s'.",
        total,
        store.collection_name,
    )


# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Index quydinh (or any) chunks folder into Qdrant"
    )
    parser.add_argument(
        "--chunks-dir",
        type=Path,
        default=DEFAULT_CHUNKS_DIR,
        help="Directory containing *_chunks.json files",
    )
    parser.add_argument(
        "--collection",
        default=DEFAULT_COLLECTION,
        help="Qdrant collection name (default: quydinh)",
    )
    parser.add_argument(
        "--qdrant-host",
        default="localhost",
        help="Qdrant host",
    )
    parser.add_argument(
        "--qdrant-port",
        type=int,
        default=6333,
        help="Qdrant port",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help="Number of chunks per embedding + upsert batch",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # 1. Load all chunks from the folder
    chunks = load_chunks_from_dir(args.chunks_dir)

    # 2. Init embedders
    logger.info("Loading BGE-M3 embedder …")
    bge = BGEm3Embedder()

    logger.info("Loading E5-multilingual embedder …")
    e5 = E5MultilingualEmbedder()

    # 3. Init Qdrant store  (_ensure_collection creates it if not exists)
    logger.info(
        "Connecting to Qdrant at %s:%d, collection='%s' …",
        args.qdrant_host,
        args.qdrant_port,
        args.collection,
    )
    store = QdrantStore(
        host=args.qdrant_host,
        port=args.qdrant_port,
        collection_name=args.collection,
    )

    # 4. Embed + index
    index_chunks(chunks, store, bge, e5, batch_size=args.batch_size)


if __name__ == "__main__":
    main()
