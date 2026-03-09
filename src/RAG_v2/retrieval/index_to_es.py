"""Index các Qdrant collection vào Elasticsearch để hỗ trợ hybrid search.

Chỉnh sửa các biến cấu hình bên dưới rồi chạy:
    python retrieval/index_to_es.py
"""

from __future__ import annotations

import logging
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from qdrant_client import QdrantClient
from retrieval.elasticsearch_store import ElasticsearchStore

# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ============================================================
# CẤU HÌNH — chỉnh sửa tại đây
# ============================================================

# Danh sách (qdrant_collection, es_index) cần index.
# Nếu tên ES index giống tên collection thì chỉ cần ghi tên collection.
COLLECTIONS = [
    ("stsv", "stsv"),
    ("quydinh", "quydinh"),
    # ("ten_collection_moi", "ten_es_index_moi"),
]

# Xóa docs cũ trong ES trước khi index lại không?
FORCE_REINDEX = False

QDRANT_HOST = "localhost"
QDRANT_PORT = 6333
ES_HOST = "localhost"
ES_PORT = 9200

# ============================================================


# ---------------------------------------------------------------------------


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


def index_collection(
    qdrant: QdrantClient,
    collection: str,
    es_index: str,
    force: bool = False,
) -> None:
    """Index one Qdrant collection into one ES index."""
    logger.info("─" * 60)
    logger.info("Collection : %s  →  ES index : %s", collection, es_index)

    # Verify collection exists
    collections = [c.name for c in qdrant.get_collections().collections]
    if collection not in collections:
        logger.error("Qdrant collection '%s' not found. Skipping.", collection)
        return

    info = qdrant.get_collection(collection)
    total_points = info.points_count
    logger.info("Qdrant points : %d", total_points)

    es_store = ElasticsearchStore(
        host=ES_HOST, port=ES_PORT, index_name=es_index
    )

    if force:
        current_count = es_store.count()
        if current_count > 0:
            logger.info(
                "--force: deleting %d existing docs from '%s' ...",
                current_count,
                es_index,
            )
            es_store.client.delete_by_query(
                index=es_index,
                body={"query": {"match_all": {}}},
                refresh=True,
            )
            logger.info("Existing docs deleted.")

    texts: list[str] = []
    metadatas: list[dict] = []
    ids: list[str] = []

    logger.info("Scrolling points from Qdrant ...")
    for pt in scroll_all_points(qdrant, collection):
        payload = dict(pt.payload or {})
        text = payload.pop("text", "")
        texts.append(text)
        metadatas.append(payload)
        ids.append(str(pt.id))

    logger.info(
        "Indexing %d documents into ES index '%s' ...", len(texts), es_index
    )
    indexed = es_store.index_documents(texts, metadatas, ids)
    logger.info(
        "Done. Indexed %d / %d documents. Total in ES: %d",
        indexed,
        len(texts),
        es_store.count(),
    )


if __name__ == "__main__":
    logger.info("Connecting to Qdrant at %s:%d ...", QDRANT_HOST, QDRANT_PORT)
    qdrant = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

    for collection, es_index in COLLECTIONS:
        index_collection(
            qdrant=qdrant,
            collection=collection,
            es_index=es_index,
            force=FORCE_REINDEX,
        )

    logger.info("All done.")
