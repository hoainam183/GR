"""
Sync metadata tu chunk JSON files -> Qdrant (khong re-embed)
=============================================================
Script doc cac file *_chunks.json da duoc chinh sua metadata, sau do
overwrite payload trong Qdrant cho tung diem theo ID — vectors khong bi
thay doi.

Cau truc payload trong Qdrant: {**metadata, "text": content}
  -> overwrite_payload se thay toan bo payload (ca text lan metadata)
  -> merge mode (overwrite=False) chi cap nhat cac field metadata moi

Cach dung (tu RAG_v2/):
    python pipeline/update_metadata.py          # chay theo CONFIG
    python pipeline/update_metadata.py --dry-run  # chi in ra khong update
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent  # .../RAG_v2
sys.path.insert(0, str(PROJECT_ROOT))

from retrieval.qdrant_store import QdrantStore

# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

DATA = PROJECT_ROOT / "data"

# ---------------------------------------------------------------------------
# Config — chinh tham so tai day, khong dung CLI
# ---------------------------------------------------------------------------
CONFIG = {
    "qdrant_host": "localhost",
    "qdrant_port": 6333,
    "batch_size": 100,

    # overwrite=True  -> thay toan bo payload (metadata + text) bang du lieu moi tu chunk file
    # overwrite=False -> chi cap nhat/them cac field metadata, giu nguyen cac field cu con lai
    "overwrite": True,

    # Danh sach collection can update — comment dong nao khong can
    "collections": [
        {
            "name": "stsv",
            # file don, flat chunks — dung "chunk_id" lam point ID
            "source": DATA / "stsv" / "chunks" / "stsv_all_chunks.json",
            "source_type": "file",       # "file" | "dir" | "ctdt_multi"
            "id_field": "chunk_id",      # field chua Qdrant point ID
            "level_filter": None,        # None = lay tat ca chunks
        },
        {
            "name": "kehoach",
            "source": DATA / "kehoach" / "chunks" / "kehoach_all_chunks.json",
            "source_type": "file",
            "id_field": "chunk_id",
            "level_filter": None,
        },
        {
            "name": "quydinh",
            "source": DATA / "quydinh" / "olmocr" / "chunks_recursive_parent_child_3",
            "source_type": "dir",
            "id_field": "id",
            "level_filter": "child",
        },
        {
            "name": "quydinh",
            "source": DATA / "quydinh" / "chunks" / "quydinh_all_chunks.json",
            "source_type": "file",
            "id_field": "chunk_id",
            "level_filter": None,
        },
        {
            "name": "ctdt",
            # ctdt co nhieu sub-folder, moi cai la mot source dir
            # -> quet toan bo data/ctdt/*/chunks_recursive_parent_child/
            "source": DATA / "ctdt",
            "source_type": "ctdt_multi", # special: quet */chunks_recursive_parent_child/
            "id_field": "id",
            "level_filter": "child",
        },
    ],
}


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def _load_file(path: Path) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_chunks(col: Dict[str, Any]) -> List[Dict[str, Any]]:
    source_type = col["source_type"]
    source = Path(col["source"])
    level_filter = col.get("level_filter")
    id_field = col["id_field"]

    raw: List[Dict[str, Any]] = []

    if source_type == "file":
        logger.info("  Loading file: %s", source)
        raw = _load_file(source)

    elif source_type == "dir":
        json_files = sorted(source.glob("*_chunks.json"))
        if not json_files:
            raise FileNotFoundError(f"No *_chunks.json in {source}")
        for p in json_files:
            logger.info("  Loading %s", p.name)
            raw.extend(_load_file(p))

    elif source_type == "ctdt_multi":
        # quet data/ctdt/*/chunks_recursive_parent_child/*.json
        for subdir in sorted(source.iterdir()):
            chunk_dir = subdir / "chunks_recursive_parent_child"
            if not chunk_dir.is_dir():
                continue
            for p in sorted(chunk_dir.glob("*_chunks.json")):
                logger.info("  Loading %s/%s", subdir.name, p.name)
                raw.extend(_load_file(p))

    else:
        raise ValueError(f"Unknown source_type: {source_type!r}")

    # Filter by level if needed
    if level_filter:
        before = len(raw)
        raw = [c for c in raw if c.get("metadata", {}).get("level") == level_filter]
        logger.info(
            "  Level filter '%s': %d -> %d chunks",
            level_filter, before, len(raw),
        )

    # Validate ID field exists
    missing = sum(1 for c in raw if not c.get(id_field))
    if missing:
        logger.warning("  %d chunks missing '%s' field — will be skipped", missing, id_field)

    logger.info("  Collection '%s': %d chunks loaded.", col["name"], len(raw))
    return raw


# ---------------------------------------------------------------------------
# Build (id, payload) pairs
# ---------------------------------------------------------------------------

def build_pairs(
    chunks: List[Dict[str, Any]],
    id_field: str,
    overwrite: bool,
) -> List[Tuple[str, Dict[str, Any]]]:
    """Build list of (point_id, payload_dict) for Qdrant update.

    When overwrite=True:  payload = {**metadata, "text": content}
                          Full replace — text field preserved.
    When overwrite=False: payload = {**metadata}
                          Merge — only metadata fields updated.
    """
    pairs: List[Tuple[str, Dict[str, Any]]] = []
    for c in chunks:
        point_id = c.get(id_field)
        if not point_id:
            continue
        meta = c.get("metadata", {})
        if overwrite:
            # Include "text" so overwrite_payload does not erase the content
            payload: Dict[str, Any] = {**meta, "text": c.get("content", "")}
        else:
            payload = dict(meta)
        pairs.append((str(point_id), payload))
    return pairs


# ---------------------------------------------------------------------------
# Core update
# ---------------------------------------------------------------------------

def update_collection(
    col: Dict[str, Any],
    store: QdrantStore,
    batch_size: int,
    overwrite: bool,
    dry_run: bool = False,
) -> None:
    collection_name = col["name"]
    logger.info("=== Collection: %s ===", collection_name)

    chunks = load_chunks(col)
    if not chunks:
        logger.warning("  No chunks to update for '%s'.", collection_name)
        return

    pairs = build_pairs(chunks, col["id_field"], overwrite)
    logger.info(
        "  Updating %d point(s) in '%s' (overwrite=%s) ...",
        len(pairs), collection_name, overwrite,
    )

    if dry_run:
        logger.info("  [DRY-RUN] Skipping actual Qdrant write.")
        if pairs:
            logger.info(
                "  Sample — id=%s, payload_keys=%s",
                pairs[0][0], list(pairs[0][1].keys()),
            )
        return

    store.update_metadata_batch(pairs, overwrite=overwrite, batch_size=batch_size)
    logger.info("  Done: '%s'.", collection_name)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(dry_run: bool = False) -> None:
    cfg = CONFIG

    for col in cfg["collections"]:
        store = QdrantStore(
            host=cfg["qdrant_host"],
            port=cfg["qdrant_port"],
            collection_name=str(col["name"]),
        )
        update_collection(
            col=col,
            store=store,
            batch_size=cfg["batch_size"],
            overwrite=cfg["overwrite"],
            dry_run=dry_run,
        )

    logger.info("All collections updated.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Sync chunk metadata -> Qdrant without re-embedding."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be updated without writing to Qdrant.",
    )
    args = parser.parse_args()
    main(dry_run=args.dry_run)
