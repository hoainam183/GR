"""Re-index Qdrant collections into Elasticsearch for hybrid BM25 search.

Examples:
    .venv/bin/python scripts/index_to_es.py --recreate --collections stsv quydinh kehoach ctdt
    .venv/bin/python scripts/index_to_es.py --smoke-test-only
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
from typing import Iterable

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from elasticsearch import Elasticsearch
from qdrant_client import QdrantClient

from retrieval.elasticsearch_store import ElasticsearchStore

# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

DEFAULT_COLLECTIONS = {
    "stsv": "stsv",
    "quydinh": "quydinh",
    "kehoach": "kehoach",
    "ctdt": "ctdt",
}

DEFAULT_QDRANT_HOST = "localhost"
DEFAULT_QDRANT_PORT = 6333
DEFAULT_ES_HOST = "localhost"
DEFAULT_ES_PORT = 9200

# Regex patterns for metadata extraction during indexing
COURSE_REGEX = re.compile(r"\*\*(?:([A-Z]{2,3}\d{4}[A-Za-z]?)\s+)(.*?)\*\*")
SEM_REGEX = re.compile(r"(học kỳ\s*(?:[IVX]+|\d+)|\bhk\s*\d+|kỳ\s*\d+)", re.IGNORECASE)
YEAR_REGEX = re.compile(
    r"(năm học\s*\d{4}\s*-\s*\d{4}|năm\s*\d{4}\s*-\s*\d{4}|\d{4}\s*-\s*\d{4})",
    re.IGNORECASE,
)

NON_SEARCHABLE_ES_LEVELS = {"parent", "header"}


def scroll_all_points(
    client: QdrantClient,
    collection: str,
    batch_size: int = 200,
) -> Iterable:
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


def is_searchable_es_payload(payload: dict) -> bool:
    """Return True when this Qdrant payload should be searchable in ES."""
    level = str(payload.get("level", "child") or "child").strip().lower()
    return level not in NON_SEARCHABLE_ES_LEVELS


def enrich_collection_metadata(collection: str, text: str, payload: dict) -> dict:
    """Add collection-specific BM25 helper metadata."""
    payload = dict(payload)
    payload.setdefault("collection", collection)

    if collection == "ctdt":
        match = COURSE_REGEX.search(text)
        if match:
            payload["course_code"] = match.group(1).strip()
            payload["course_name"] = match.group(2).strip()
    elif collection == "kehoach":
        sem_match = SEM_REGEX.search(text)
        year_match = YEAR_REGEX.search(text)
        sem_parts = []
        if sem_match:
            sem_parts.append(sem_match.group(0).strip())
        if year_match:
            sem_parts.append(year_match.group(0).strip())
        if sem_parts:
            payload["semester"] = " ".join(sem_parts)

    return payload


def smoke_test_vietnamese_plugin(host: str, port: int) -> tuple[bool, str]:
    """Verify the Vietnamese analysis plugin is installed and usable."""
    client = Elasticsearch(hosts=[f"http://{host}:{port}"])
    if not client.ping():
        return False, f"Cannot connect to Elasticsearch at {host}:{port}"

    try:
        nodes = client.nodes.info(metric="plugins")
        plugin_names = [
            str(plugin.get("name", ""))
            for node in nodes.get("nodes", {}).values()
            for plugin in node.get("plugins", [])
        ]
        plugin_seen = any("vietnamese" in name.lower() for name in plugin_names)
    except Exception as exc:  # noqa: BLE001
        return False, f"GET /_nodes/plugins failed: {exc}"

    if not plugin_seen:
        return False, f"Vietnamese plugin not found in node plugins: {plugin_names}"

    sample = "tín chỉ tích lũy đồ án tốt nghiệp"
    try:
        analyzed = client.indices.analyze(analyzer="vi_analyzer", text=sample)
    except Exception as exc:  # noqa: BLE001
        return False, f"POST /_analyze with vi_analyzer failed: {exc}"

    tokens = [str(token.get("token", "")) for token in analyzed.get("tokens", [])]
    token_text = " | ".join(tokens).lower()
    expected_hits = sum(
        1
        for phrase in ("tín chỉ", "tích lũy", "đồ án", "tốt nghiệp")
        if phrase in token_text
    )
    if expected_hits < 2:
        return False, f"vi_analyzer tokenization looks wrong: {tokens}"

    return True, f"Vietnamese plugin OK. tokens={tokens}"


def index_collection(
    qdrant: QdrantClient,
    collection: str,
    es_index: str,
    es_host: str,
    es_port: int,
    recreate: bool = False,
    force: bool = False,
    batch_size: int = 500,
) -> None:
    """Index one Qdrant collection into one ES index."""
    logger.info("-" * 60)
    logger.info("Collection : %s  ->  ES index : %s", collection, es_index)

    collections = [c.name for c in qdrant.get_collections().collections]
    if collection not in collections:
        logger.error("Qdrant collection '%s' not found. Skipping.", collection)
        return

    info = qdrant.get_collection(collection)
    total_points = info.points_count
    logger.info("Qdrant points : %d", total_points)

    es_store = ElasticsearchStore(host=es_host, port=es_port, index_name=es_index)

    if recreate:
        logger.info("--recreate: deleting and recreating ES index '%s' ...", es_index)
        es_store.recreate_index()
    elif force:
        current_count = es_store.count()
        if current_count > 0:
            logger.info("--force: deleting %d existing docs from '%s' ...", current_count, es_index)
            es_store.client.delete_by_query(
                index=es_index,
                body={"query": {"match_all": {}}},
                refresh=True,
            )
            logger.info("Existing docs deleted.")

    texts: list[str] = []
    metadatas: list[dict] = []
    ids: list[str] = []
    skipped_non_searchable = 0

    logger.info("Scrolling points from Qdrant ...")
    for pt in scroll_all_points(qdrant, collection):
        payload = dict(pt.payload or {})
        if not is_searchable_es_payload(payload):
            skipped_non_searchable += 1
            continue

        text = str(payload.pop("text", "") or "")
        payload = enrich_collection_metadata(collection, text, payload)

        texts.append(text)
        metadatas.append(payload)
        ids.append(str(pt.id))

    if skipped_non_searchable:
        logger.info("Skipped %d parent/header point(s) for ES search index.", skipped_non_searchable)

    logger.info("Indexing %d documents into ES index '%s' ...", len(texts), es_index)
    indexed = es_store.index_documents(texts, metadatas, ids, batch_size=batch_size)
    logger.info(
        "Done. Indexed %d / %d documents. Total in ES: %d",
        indexed,
        len(texts),
        es_store.count(),
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--collections",
        nargs="+",
        default=list(DEFAULT_COLLECTIONS),
        help="Qdrant collections to index. Default: stsv quydinh kehoach ctdt.",
    )
    parser.add_argument("--qdrant-host", default=DEFAULT_QDRANT_HOST)
    parser.add_argument("--qdrant-port", type=int, default=DEFAULT_QDRANT_PORT)
    parser.add_argument("--es-host", default=DEFAULT_ES_HOST)
    parser.add_argument("--es-port", type=int, default=DEFAULT_ES_PORT)
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Delete and recreate each ES index before indexing.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Legacy mode: delete existing docs by match_all instead of recreating the index.",
    )
    parser.add_argument(
        "--allow-analyzer-fallback",
        action="store_true",
        help="Allow indexing even when vi_analyzer smoke test fails.",
    )
    parser.add_argument(
        "--smoke-test-only",
        action="store_true",
        help="Only run the vi_analyzer plugin smoke test.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    ok, message = smoke_test_vietnamese_plugin(args.es_host, args.es_port)
    if ok:
        logger.info(message)
    else:
        logger.error(message)
        if args.smoke_test_only:
            raise SystemExit(1)
        if args.recreate and not args.allow_analyzer_fallback:
            raise SystemExit(
                "Refusing to recreate/re-index without vi_analyzer. "
                "Start the ES 8.7 Vietnamese plugin image or pass "
                "--allow-analyzer-fallback for local fallback testing."
            )

    if args.smoke_test_only:
        return

    logger.info("Connecting to Qdrant at %s:%d ...", args.qdrant_host, args.qdrant_port)
    qdrant = QdrantClient(host=args.qdrant_host, port=args.qdrant_port)

    for collection in args.collections:
        es_index = DEFAULT_COLLECTIONS.get(collection, collection)
        index_collection(
            qdrant=qdrant,
            collection=collection,
            es_index=es_index,
            es_host=args.es_host,
            es_port=args.es_port,
            recreate=args.recreate,
            force=args.force,
            batch_size=args.batch_size,
        )

    logger.info("All done.")


if __name__ == "__main__":
    main()
