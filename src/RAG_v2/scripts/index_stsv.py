"""
Index STSV chunks into Qdrant
==============================
Loads stsv_all_chunks.json, embeds each chunk with BGE-M3 + E5,
then upserts them into the Qdrant collection.

Usage (from RAG_v2/):
    python pipeline/index_stsv.py
    python pipeline/index_stsv.py --batch-size 16 --collection university_docs
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
# Ensure project root is on sys.path so sibling packages resolve correctly
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

# Default paths / settings
DEFAULT_CHUNKS_PATH = (
    PROJECT_ROOT / "data" / "stsv" / "chunks" / "stsv_all_chunks.json"
)
DEFAULT_COLLECTION = "stsv"
DEFAULT_BATCH_SIZE = 32


# ---------------------------------------------------------------------------


def load_chunks(path: Path) -> List[Dict[str, Any]]:
    logger.info("Loading chunks from %s", path)
    with open(path, "r", encoding="utf-8") as f:
        chunks = json.load(f)
    logger.info("Loaded %d chunks.", len(chunks))
    return chunks


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
        ids = [c["chunk_id"] for c in batch]
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
        description="Index STSV chunks into Qdrant"
    )
    parser.add_argument(
        "--chunks-path",
        type=Path,
        default=DEFAULT_CHUNKS_PATH,
        help="Path to stsv_all_chunks.json",
    )
    parser.add_argument(
        "--collection",
        default=DEFAULT_COLLECTION,
        help="Qdrant collection name",
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

    # 1. Load chunks
    chunks = load_chunks(args.chunks_path)

    # 2. Init embedders
    logger.info("Loading BGE-M3 embedder …")
    bge = BGEm3Embedder()

    logger.info("Loading E5-multilingual embedder …")
    e5 = E5MultilingualEmbedder()

    # 3. Init Qdrant store
    logger.info(
        "Connecting to Qdrant at %s:%d …", args.qdrant_host, args.qdrant_port
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
