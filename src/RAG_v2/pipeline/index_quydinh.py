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
    PROJECT_ROOT / "data" / "ctdt" / "vatlieu" / "chunks_recursive_parent_child"
)
DEFAULT_COLLECTION = "ctdt"
DEFAULT_BATCH_SIZE = 32

# ---------------------------------------------------------------------------
# Config — chỉnh tham số tại đây, không dùng CLI
# ---------------------------------------------------------------------------
CONFIG = {
    "chunks_dir": DEFAULT_CHUNKS_DIR,
    "collection": DEFAULT_COLLECTION,
    "qdrant_host": "localhost",
    "qdrant_port": 6333,
    "batch_size": DEFAULT_BATCH_SIZE,
}


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


def filter_new_chunks(
    chunks: List[Dict[str, Any]],
    store: QdrantStore,
    check_batch_size: int = 100,
) -> List[Dict[str, Any]]:
    """Return only chunks whose IDs are NOT yet in the collection.

    Uses Qdrant ``retrieve`` in batches to check existence without
    loading vectors — fast even for large collections.
    """
    ids = [c.get("id") or c["chunk_id"] for c in chunks]

    existing_ids: set = set()
    for start in range(0, len(ids), check_batch_size):
        batch_ids = ids[start : start + check_batch_size]
        results = store.client.retrieve(
            collection_name=store.collection_name,
            ids=batch_ids,
            with_payload=False,
            with_vectors=False,
        )
        existing_ids.update(str(r.id) for r in results)

    new_chunks = [
        c for c, id_ in zip(chunks, ids) if str(id_) not in existing_ids
    ]
    logger.info(
        "Incremental check: %d already indexed, %d new chunks to add.",
        len(existing_ids),
        len(new_chunks),
    )
    return new_chunks


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


def main() -> None:
    # 1. Load all chunks from the folder
    chunks = load_chunks_from_dir(CONFIG["chunks_dir"])

    # 2. Init embedders
    logger.info("Loading BGE-M3 embedder …")
    bge = BGEm3Embedder()

    logger.info("Loading E5-multilingual embedder …")
    e5 = E5MultilingualEmbedder()

    # 3. Init Qdrant store  (_ensure_collection creates it if not exists)
    logger.info(
        "Connecting to Qdrant at %s:%d, collection='%s' …",
        CONFIG["qdrant_host"],
        CONFIG["qdrant_port"],
        CONFIG["collection"],
    )
    store = QdrantStore(
        host=CONFIG["qdrant_host"],
        port=CONFIG["qdrant_port"],
        collection_name=CONFIG["collection"],
    )

    # 4. Filter out already-indexed chunks (incremental mode)
    new_chunks = filter_new_chunks(chunks, store)
    if not new_chunks:
        logger.info(
            "Nothing to index — all chunks already exist in the collection."
        )
        return

    # 5. Embed + index only new chunks
    index_chunks(new_chunks, store, bge, e5, batch_size=CONFIG["batch_size"])


def delete_collection() -> None:
    store = QdrantStore(
        host=CONFIG["qdrant_host"],
        port=CONFIG["qdrant_port"],
        collection_name=CONFIG["collection"],
    )
    store.delete_collection()


if __name__ == "__main__":
    # delete_collection()
    main()
