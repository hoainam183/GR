"""Data Update Pipeline - ingest documents and sync store metadata.

This script demonstrates how to automate data ingestion:
1. Embeds new documents using the pipeline's embedders.
2. Upserts to Qdrant/Elasticsearch.
3. Optionally syncs edited chunk metadata to Qdrant/Elasticsearch.
4. Reloads the ValidityFilter via API to hot-swap the superseded document list.

Usage::

    python scripts/update_data.py --doc path/to/new_regulation.txt --collection quydinh
    python scripts/update_data.py --metadata-only --target both
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Assume API is running locally
API_URL = "http://localhost:8000"


def ingest_document(filepath: Path, collection: str) -> None:
    """Mock ingestion function."""
    logger.info("Ingesting %s into collection '%s'...", filepath.name, collection)
    # In a real scenario, this would:
    # 1. Read and chunk the file
    # 2. Call BGEm3Embedder and E5MultilingualEmbedder
    # 3. Upsert to Qdrant/ES via MultiCollectionSearch
    logger.info("Document chunked and embedded.")
    logger.info("Upserted to vector store.")


def sync_metadata(
    target: str,
    dry_run: bool = False,
    collections: Optional[List[str]] = None,
) -> None:
    """Sync edited chunk metadata to Qdrant and/or Elasticsearch."""
    from scripts.update_metadata import main as update_metadata_main

    logger.info("Syncing metadata to %s...", target)
    update_metadata_main(
        dry_run=dry_run,
        target=target,
        collections=collections,
    )


def trigger_validity_reload() -> None:
    """Call the API to reload the validity filter registry."""
    import requests

    logger.info("Triggering API validity filter reload...")
    try:
        # Note: the /api/admin/reload-validity endpoint needs to be added to main.py
        resp = requests.post(f"{API_URL}/api/admin/reload-validity", timeout=5)
        resp.raise_for_status()
        logger.info("API validity filter reloaded successfully: %s", resp.json())
    except Exception as exc:
        logger.error("Failed to reload API validity filter: %s", exc)


def main():
    parser = argparse.ArgumentParser(description="Update RAG Data")
    parser.add_argument("--doc", type=str, help="Path to document")
    parser.add_argument("--collection", type=str, help="Target collection")
    parser.add_argument(
        "--metadata-only",
        action="store_true",
        help="Only sync metadata from chunk JSON files; skip document ingest.",
    )
    parser.add_argument(
        "--sync-metadata",
        action="store_true",
        help="Sync metadata after document ingest.",
    )
    parser.add_argument(
        "--target",
        choices=["both", "qdrant", "elasticsearch"],
        default="both",
        help="Metadata sync target.",
    )
    parser.add_argument(
        "--metadata-collection",
        action="append",
        dest="metadata_collections",
        help="Only sync this metadata collection. Can be passed multiple times.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show metadata sync plan without writing to stores.",
    )
    parser.add_argument("--skip-reload", action="store_true", help="Skip API reload")

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if args.metadata_only:
        sync_metadata(
            target=args.target,
            dry_run=args.dry_run,
            collections=args.metadata_collections,
        )
    else:
        if not args.doc or not args.collection:
            parser.error("--doc and --collection are required unless --metadata-only is set")

        doc_path = Path(args.doc)
        if not doc_path.exists():
            logger.error("Document not found: %s", doc_path)
            sys.exit(1)

        ingest_document(doc_path, args.collection)

        if args.sync_metadata:
            sync_metadata(
                target=args.target,
                dry_run=args.dry_run,
                collections=args.metadata_collections,
            )

    if not args.skip_reload:
        trigger_validity_reload()

    logger.info("Data update complete.")


if __name__ == "__main__":
    main()
