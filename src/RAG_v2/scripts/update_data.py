"""Data Update Pipeline — ingest new documents and reload validity filters.

This script demonstrates how to automate data ingestion:
1. Embeds new documents using the pipeline's embedders.
2. Upserts to Qdrant/Elasticsearch.
3. Reloads the ValidityFilter via API to hot-swap the superseded document list.

Usage::

    python scripts/update_data.py --doc path/to/new_regulation.txt --collection quydinh
"""

import argparse
import logging
import sys
from pathlib import Path
import requests

logger = logging.getLogger(__name__)

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


def trigger_validity_reload() -> None:
    """Call the API to reload the validity filter registry."""
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
    parser.add_argument("--doc", type=str, required=True, help="Path to document")
    parser.add_argument("--collection", type=str, required=True, help="Target collection")
    parser.add_argument("--skip-reload", action="store_true", help="Skip API reload")
    
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    
    doc_path = Path(args.doc)
    if not doc_path.exists():
        logger.error("Document not found: %s", doc_path)
        sys.exit(1)
        
    ingest_document(doc_path, args.collection)
    
    if not args.skip_reload:
        trigger_validity_reload()
        
    logger.info("Data update complete.")


if __name__ == "__main__":
    main()
