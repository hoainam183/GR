"""Index the 'stsv' Qdrant collection into Elasticsearch for hybrid search.

Usage (from RAG_v2/ or retrieval/ directory):
    python retrieval/index_stsv_to_es.py
    # or
    python index_stsv_to_es.py
"""

from __future__ import annotations

import sys
import os

# Allow running from any cwd inside RAG_v2
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from qdrant_client import QdrantClient
from retrieval.elasticsearch_store import ElasticsearchStore

QDRANT_HOST = "localhost"
QDRANT_PORT = 6333
COLLECTION = "quydinh"

ES_HOST = "localhost"
ES_PORT = 9200
ES_INDEX = "quydinh"


def scroll_all_points(
    client: QdrantClient, collection: str, batch_size: int = 200
):
    """Yield all points from a Qdrant collection via scrolling."""
    offset = None
    while True:
        results, next_offset = client.scroll(
            collection_name=collection,
            limit=batch_size,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        yield from results
        if next_offset is None:
            break
        offset = next_offset


def main() -> None:
    print(f"Connecting to Qdrant at {QDRANT_HOST}:{QDRANT_PORT} ...")
    qdrant = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    info = qdrant.get_collection(COLLECTION)
    total_points = info.points_count
    print(f"Collection '{COLLECTION}': {total_points} points")

    print(f"Connecting to Elasticsearch at {ES_HOST}:{ES_PORT} ...")
    es_store = ElasticsearchStore(
        host=ES_HOST, port=ES_PORT, index_name=ES_INDEX
    )

    # Scroll and collect all points
    texts: list[str] = []
    metadatas: list[dict] = []
    ids: list[str] = []

    print(f"Scrolling {total_points} points from Qdrant ...")
    for pt in scroll_all_points(qdrant, COLLECTION):
        payload = dict(pt.payload or {})
        text = payload.pop("text", "")
        texts.append(text)
        metadatas.append(payload)
        ids.append(str(pt.id))

    print(f"Indexing {len(texts)} documents into ES index '{ES_INDEX}' ...")
    indexed = es_store.index_documents(texts, metadatas, ids)
    print(f"Done. Indexed {indexed}/{len(texts)} documents.")
    print(f"Total docs in ES: {es_store.count()}")


if __name__ == "__main__":
    main()
