"""Index parent-child chunks from data/ JSON files into Qdrant + Elasticsearch.

Reads parent-child JSON files from data/ctdt/ subfolders (and quydinh/admin_upload),
embeds each chunk with both BGE-M3 and E5, then upserts into Qdrant as named vectors.
Also indexes into Elasticsearch for BM25 hybrid search.

Parent-child relationship is preserved via metadata fields:
  - level: "parent" | "child"
  - parent_id: UUID of parent (for children) | null (for parents)
  - child_count: number of children (for parents only)

Strategy:
  - ALL chunks (parent + child) are indexed into Qdrant for vector search
  - At retrieval time, search is done on children; parent content is fetched
    as expanded context when needed (see parent_context.py)
  - The `level` payload field allows filtering parents out of search results

Usage from ``src/RAG_v2``::

    python scripts/index_parent_child.py
    python scripts/index_parent_child.py --collection ctdt --dry-run
    python scripts/index_parent_child.py --collection ctdt --subfolder soict
    python scripts/index_parent_child.py --collection quydinh
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import Settings

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

# Collections with parent-child data
# Each collection can have a flat config (subfolders + chunk_dir/pattern)
# OR a list of explicit sources via "multi_source" for collections with mixed folder structures.
PARENT_CHILD_SOURCES = {
    "ctdt": {
        "subfolders": ["soict", "cokhi", "dien-dientu", "hoa", "toan", "vatlieu"],
        "chunk_dir": "chunks_recursive_parent_child",
    },
    "quydinh": {
        "multi_source": [
            {
                "subfolder": "admin_upload",
                "chunk_dir": None,
                "pattern": "*_recursive_chunks.json",
            },
            {
                "subfolder": "olmocr",
                "chunk_dir": "chunks_recursive_parent_child_3",
                "pattern": None,
            },
        ]
    },
}


def discover_chunk_files(
    collection: str,
    subfolder: Optional[str] = None,
) -> List[Tuple[Path, str]]:
    """Discover all parent-child chunk JSON files for a collection.

    Returns:
        List of (file_path, subfolder_name) tuples.
    """
    source_config = PARENT_CHILD_SOURCES.get(collection)
    if not source_config:
        logger.warning("No parent-child sources configured for '%s'", collection)
        return []

    files: List[Tuple[Path, str]] = []

    # Support both flat config and multi_source list
    if "multi_source" in source_config:
        sources = source_config["multi_source"]
        if subfolder:
            sources = [s for s in sources if s["subfolder"] == subfolder]
    else:
        subfolders = [subfolder] if subfolder else source_config["subfolders"]
        sources = [
            {
                "subfolder": sf,
                "chunk_dir": source_config.get("chunk_dir"),
                "pattern": source_config.get("pattern"),
            }
            for sf in subfolders
        ]

    for src in sources:
        sf = src["subfolder"]
        base = DATA_DIR / collection / sf

        if src.get("chunk_dir"):
            chunk_dir = base / src["chunk_dir"]
            if chunk_dir.exists():
                for f in sorted(chunk_dir.glob("*.json")):
                    files.append((f, sf))
        elif src.get("pattern"):
            if base.exists():
                for f in sorted(base.glob(src["pattern"])):
                    files.append((f, sf))
        else:
            if base.exists():
                for f in sorted(base.glob("*.json")):
                    files.append((f, sf))

    return files


def load_chunks(file_path: Path) -> List[Dict[str, Any]]:
    """Load chunks from a JSON file."""
    with open(file_path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "chunks" in data:
        return data["chunks"]
    return [data]


def prepare_chunk_for_indexing(
    chunk: Dict[str, Any],
    collection: str,
    subfolder: str,
    source_file: str,
) -> Optional[Dict[str, Any]]:
    """Normalize a chunk dict for indexing.

    Returns:
        Dict with keys: id, text, metadata. None if invalid.
    """
    chunk_id = chunk.get("id")
    content = chunk.get("content", "")
    metadata = chunk.get("metadata", {})

    if not chunk_id or not content or not content.strip():
        return None

    # Enrich metadata with collection info
    enriched_meta = {
        **metadata,
        "collection": collection,
        "subfolder": subfolder,
        "source_file": source_file,
    }

    # Ensure critical parent-child fields exist
    enriched_meta.setdefault("level", "child")
    enriched_meta.setdefault("parent_id", None)
    enriched_meta.setdefault("chunk_type", "text")

    return {
        "id": chunk_id,
        "text": content,
        "metadata": enriched_meta,
    }


def index_to_qdrant(
    prepared_chunks: List[Dict[str, Any]],
    collection_name: str,
    settings: Settings,
    batch_size: int = 32,
) -> int:
    """Embed and upsert chunks into Qdrant.

    Args:
        prepared_chunks: List of dicts with keys: id, text, metadata.
        collection_name: Qdrant collection name.
        settings: Application settings.
        batch_size: Batch size for embedding + upsert.

    Returns:
        Number of chunks successfully indexed.
    """
    from embedding.bge_m3 import BGEm3Embedder
    from embedding.e5_multilingual import E5MultilingualEmbedder
    from retrieval.qdrant_store import QdrantStore

    logger.info("Initializing embedders...")
    bge = BGEm3Embedder()
    e5 = E5MultilingualEmbedder()

    logger.info(
        "Connecting to Qdrant at %s:%d, collection='%s'",
        settings.qdrant_host,
        settings.qdrant_port,
        collection_name,
    )
    qdrant_store = QdrantStore(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        collection_name=collection_name,
    )

    total_indexed = 0

    for batch_start in range(0, len(prepared_chunks), batch_size):
        batch = prepared_chunks[batch_start : batch_start + batch_size]
        texts = [c["text"] for c in batch]
        ids = [c["id"] for c in batch]
        metadatas = [c["metadata"] for c in batch]

        logger.info(
            "Embedding batch %d-%d / %d ...",
            batch_start,
            batch_start + len(batch),
            len(prepared_chunks),
        )
        t0 = time.perf_counter()
        bge_vectors = bge.embed(texts)
        e5_vectors = e5.embed(texts)
        embed_time = time.perf_counter() - t0

        logger.info("  Embedded in %.1fs, upserting to Qdrant...", embed_time)
        qdrant_store.index_documents(
            texts=texts,
            bge_m3_vectors=bge_vectors,
            e5_vectors=e5_vectors,
            metadatas=metadatas,
            ids=ids,
            batch_size=batch_size,
        )
        total_indexed += len(batch)

    return total_indexed


def index_to_elasticsearch(
    prepared_chunks: List[Dict[str, Any]],
    index_name: str,
    settings: Settings,
) -> int:
    """Index chunks into Elasticsearch for BM25 search.

    Args:
        prepared_chunks: List of dicts with keys: id, text, metadata.
        index_name: ES index name.
        settings: Application settings.

    Returns:
        Number of chunks indexed.
    """
    from retrieval.elasticsearch_store import ElasticsearchStore

    logger.info(
        "Connecting to Elasticsearch at %s:%d, index='%s'",
        settings.elasticsearch_host,
        settings.elasticsearch_port,
        index_name,
    )
    es_store = ElasticsearchStore(
        host=settings.elasticsearch_host,
        port=settings.elasticsearch_port,
        index_name=index_name,
    )

    # Only index searchable chunks (child/recursive/appendix) to ES for BM25.
    # Parent chunks are excluded — they're only needed in Qdrant for ID-based fetch.
    searchable_chunks = [
        c for c in prepared_chunks
        if str(c.get("metadata", {}).get("level", "child")).strip().lower()
        not in ("parent", "header")
    ]
    texts = [c["text"] for c in searchable_chunks]
    metadatas = [c["metadata"] for c in searchable_chunks]
    ids = [c["id"] for c in searchable_chunks]

    indexed = es_store.index_documents(texts, metadatas, ids)
    return indexed


def run_indexing(
    collection: str,
    subfolder: Optional[str] = None,
    dry_run: bool = False,
    skip_qdrant: bool = False,
    skip_es: bool = False,
    parents_only: bool = False,
) -> Dict[str, Any]:
    """Main indexing pipeline for parent-child chunks.

    Args:
        collection: Collection to index (ctdt, quydinh).
        subfolder: Optional specific subfolder to index.
        dry_run: If True, only report what would be indexed.
        skip_qdrant: Skip Qdrant indexing.
        skip_es: Skip Elasticsearch indexing.
        parents_only: Only index parent chunks (skip children already in Qdrant/ES).

    Returns:
        Stats dict with counts.
    """
    settings = Settings()
    files = discover_chunk_files(collection, subfolder)

    if not files:
        logger.warning("No parent-child chunk files found for '%s'", collection)
        return {"files": 0, "total_chunks": 0, "parents": 0, "children": 0}

    logger.info("Found %d chunk file(s) for '%s'", len(files), collection)

    # Load and prepare all chunks
    prepared_chunks: List[Dict[str, Any]] = []
    parent_count = 0
    child_count = 0

    for file_path, sf in files:
        raw_chunks = load_chunks(file_path)
        logger.info("  %s: %d chunks", file_path.name, len(raw_chunks))

        for chunk in raw_chunks:
            prepared = prepare_chunk_for_indexing(
                chunk,
                collection=collection,
                subfolder=sf,
                source_file=file_path.name,
            )
            if prepared:
                prepared_chunks.append(prepared)
                level = prepared["metadata"].get("level", "child")
                if level == "parent":
                    parent_count += 1
                else:
                    child_count += 1

    stats = {
        "files": len(files),
        "total_chunks": len(prepared_chunks),
        "parents": parent_count,
        "children": child_count,
    }

    logger.info(
        "Prepared %d chunks (%d parents, %d children)",
        len(prepared_chunks),
        parent_count,
        child_count,
    )

    if dry_run:
        logger.info("DRY RUN — no indexing performed.")
        return stats

    # Optionally filter to parent chunks only (children already exist in stores)
    qdrant_chunks = prepared_chunks
    if parents_only:
        qdrant_chunks = [c for c in prepared_chunks if c["metadata"].get("level") == "parent"]
        logger.info(
            "--parents-only: %d parent chunks selected (skipping %d children)",
            len(qdrant_chunks),
            len(prepared_chunks) - len(qdrant_chunks),
        )
        stats["parents_only"] = True

    # Index to Qdrant
    if not skip_qdrant:
        qdrant_count = index_to_qdrant(qdrant_chunks, collection, settings)
        stats["qdrant_indexed"] = qdrant_count
        logger.info("Qdrant: indexed %d chunks", qdrant_count)

    # Index to Elasticsearch (always skip parents; also skip if parents_only)
    if not skip_es and not parents_only:
        es_count = index_to_elasticsearch(prepared_chunks, collection, settings)
        stats["es_indexed"] = es_count
        logger.info("Elasticsearch: indexed %d chunks", es_count)

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Index parent-child chunks into Qdrant + Elasticsearch"
    )
    parser.add_argument(
        "--collection",
        type=str,
        default="ctdt",
        choices=list(PARENT_CHILD_SOURCES.keys()),
        help="Collection to index (default: ctdt)",
    )
    parser.add_argument(
        "--subfolder",
        type=str,
        default=None,
        help="Specific subfolder to index (e.g. soict)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only report what would be indexed, don't index",
    )
    parser.add_argument(
        "--skip-qdrant",
        action="store_true",
        help="Skip Qdrant indexing (ES only)",
    )
    parser.add_argument(
        "--skip-es",
        action="store_true",
        help="Skip Elasticsearch indexing (Qdrant only)",
    )
    parser.add_argument(
        "--parents-only",
        action="store_true",
        help="Only index parent chunks to Qdrant (skip children already indexed)",
    )
    args = parser.parse_args()

    stats = run_indexing(
        collection=args.collection,
        subfolder=args.subfolder,
        dry_run=args.dry_run,
        skip_qdrant=args.skip_qdrant,
        skip_es=args.skip_es,
        parents_only=args.parents_only,
    )

    print(f"\n{'='*50}")
    print("INDEXING COMPLETE")
    print(f"{'='*50}")
    for k, v in stats.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
