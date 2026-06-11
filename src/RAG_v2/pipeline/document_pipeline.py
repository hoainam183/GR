"""Admin Document Processing Pipeline — Phase 3.

Orchestrates the full document lifecycle: convert → clean → chunk → embed → index.
Reuses existing modules — NO new ML/NLP code.

Each step updates ``DocumentRecord.status`` in MongoDB and is designed to be
called from FastAPI ``BackgroundTasks``.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from config.settings import Settings
from models.database import DOCUMENTS_COLLECTION, DOCUMENT_CHUNKS_COLLECTION
from utils.chunk_indexing import is_indexable_chunk, is_qdrant_storable
from utils.storage import LocalStorage

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# Chunker strategy → class mapping
# ═══════════════════════════════════════════════════════════════════════════════

# Strategies that accept plain markdown text
_TEXT_STRATEGIES = {"recursive", "hierarchical", "olmocr"}

# Strategies designed for specific JSON formats (kehoach/stsv crawled data).
# When used in the admin upload pipeline (PDF → markdown), these fall back
# to RecursiveChunker since the text doesn't match the expected JSON schema.
_JSON_STRATEGIES = {"kehoach", "stsv"}

# Valid PDF converter names
VALID_CONVERTERS = {"pymupdf4llm", "docling"}


def _create_chunker(strategy: str, converter: str = "pymupdf4llm") -> Any:
    """Instantiate a chunker based on strategy name.

    Args:
        strategy: Chunking strategy name.
        converter: PDF converter that was used (``pymupdf4llm`` or ``docling``).
                   Affects which hierarchical chunker variant is selected.

    Returns:
        A chunker instance with a ``chunk_document`` method.
    """
    if strategy == "recursive":
        from chunking.chunker.recursive_chunker import RecursiveChunker

        return RecursiveChunker(
            chunk_size=1024,
            chunk_overlap=0,
            protect_tables=True,
            add_section_context=True,
        )
    elif strategy == "hierarchical":
        if converter == "pymupdf4llm":
            from chunking.chunker.hierarchical_legal_chunker_pymupdf import (
                ArticleLegalChunkerPyMuPDF,
            )

            return ArticleLegalChunkerPyMuPDF()
        else:
            # docling produces markdown headers (#), use the docling variant
            from chunking.chunker.hierarchical_legal_chunker import (
                ArticleLevelLegalChunker,
            )

            return ArticleLevelLegalChunker()
    elif strategy == "olmocr":
        from chunking.chunker.olmocr_legal_chunker import OlmOcrLegalChunker

        return OlmOcrLegalChunker()
    else:
        # kehoach/stsv/unknown → fallback to recursive for PDF uploads
        from chunking.chunker.recursive_chunker import RecursiveChunker

        logger.info(
            "Strategy '%s' not suitable for PDF text; falling back to recursive.",
            strategy,
        )
        return RecursiveChunker(
            chunk_size=1024,
            chunk_overlap=0,
            protect_tables=True,
            add_section_context=True,
        )


def _run_chunker(
    chunker: Any, text: str, source: str, strategy: str
) -> Tuple[List[Dict], Dict]:
    """Run a chunker and normalise the return value to (chunks, stats).

    Different chunker classes have different signatures:
    - RecursiveChunker.chunk_document(text, source) → (chunks, stats)
    - HierarchicalLegalChunker.chunk_document(text) → (chunks, stats)
    - OlmOcrLegalChunker.chunk_document(text) → (chunks, stats)
    - Base DocumentChunker.chunk_document(text) → chunks (list only)
    """
    if strategy == "recursive":
        result = chunker.chunk_document(text, source)
    elif strategy in ("hierarchical", "olmocr"):
        result = chunker.chunk_document(text)
    else:
        # Fallback strategies also use RecursiveChunker
        result = chunker.chunk_document(text, source)

    # Normalise: some chunkers return (chunks, stats), others return just chunks
    if isinstance(result, tuple) and len(result) == 2:
        chunks, stats = result
    else:
        chunks = result if isinstance(result, list) else []
        stats = {"total_chunks": len(chunks)}

    logger.info(
        "Chunker (strategy=%s) produced %d raw chunks.", strategy, len(chunks)
    )
    return chunks, stats


# ═══════════════════════════════════════════════════════════════════════════════
# DocumentPipeline
# ═══════════════════════════════════════════════════════════════════════════════


class DocumentPipeline:
    """Orchestrates admin document processing: convert → clean → chunk → embed → index.

    All heavy resources (embedders, vector stores) are lazy-loaded to avoid
    startup cost when the pipeline isn't used.

    Parameters:
        settings: Application settings.
        storage: File storage backend (defaults to LocalStorage).
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        storage: Optional[LocalStorage] = None,
    ) -> None:
        self._settings = settings or Settings()
        self._storage = storage or LocalStorage(base_dir=self._settings.upload_dir)

        # Lazy-loaded heavy resources
        self._bge_embedder: Any = None
        self._e5_embedder: Any = None

    # ------------------------------------------------------------------
    # Lazy resource accessors
    # ------------------------------------------------------------------

    def _get_bge_embedder(self) -> Any:
        if self._bge_embedder is None:
            from embedding.bge_m3 import BGEm3Embedder

            self._bge_embedder = BGEm3Embedder()
            logger.info("BGE-M3 embedder loaded.")
        return self._bge_embedder

    def _get_e5_embedder(self) -> Any:
        if self._e5_embedder is None:
            from embedding.e5_multilingual import E5MultilingualEmbedder

            self._e5_embedder = E5MultilingualEmbedder()
            logger.info("E5-multilingual embedder loaded.")
        return self._e5_embedder

    def _get_qdrant_store(self, collection_name: str) -> Any:
        from retrieval.qdrant_store import QdrantStore

        return QdrantStore(
            host=self._settings.qdrant_host,
            port=self._settings.qdrant_port,
            collection_name=collection_name,
        )

    def _get_es_store(self, collection_name: str) -> Any:
        from retrieval.elasticsearch_store import ElasticsearchStore

        return ElasticsearchStore(
            host=self._settings.elasticsearch_host,
            port=self._settings.elasticsearch_port,
            index_name=collection_name,
        )

    # ------------------------------------------------------------------
    # Helper: update document status in MongoDB
    # ------------------------------------------------------------------

    async def _update_status(
        self,
        db: AsyncIOMotorDatabase,
        doc_id: str,
        status: str,
        extra_fields: Optional[Dict[str, Any]] = None,
    ) -> None:
        update: Dict[str, Any] = {"status": status}
        if extra_fields:
            update.update(extra_fields)
        await db[DOCUMENTS_COLLECTION].update_one(
            {"_id": ObjectId(doc_id)},
            {"$set": update},
        )

    async def _fail(
        self, db: AsyncIOMotorDatabase, doc_id: str, error: str
    ) -> None:
        await self._update_status(
            db, doc_id, "failed", {"error_message": error}
        )

    async def _get_doc(
        self, db: AsyncIOMotorDatabase, doc_id: str
    ) -> Optional[Dict]:
        return await db[DOCUMENTS_COLLECTION].find_one(
            {"_id": ObjectId(doc_id)}
        )

    # ------------------------------------------------------------------
    # Step 1: Convert PDF → Markdown
    # ------------------------------------------------------------------

    async def convert_pdf(
        self,
        doc_id: str,
        db: AsyncIOMotorDatabase,
        converter: str = "pymupdf4llm",
    ) -> None:
        """Convert a PDF document to markdown.

        Args:
            doc_id: Document ID.
            db: Motor database instance.
            converter: Converter to use — ``"pymupdf4llm"`` (default) or
                ``"docling"``.

        Updates status: ``converting`` → ``converted`` (or ``failed``).
        """
        try:
            doc = await self._get_doc(db, doc_id)
            if doc is None:
                return

            await self._update_status(
                db,
                doc_id,
                "converting",
                {"error_message": None, "converter": converter},
            )

            pdf_path = self._storage.base_dir / doc["file_path"]

            if converter == "docling":
                from document_loader.pdf_to_markdown.converters.docling_converter import (
                    DoclingConverter,
                )

                conv = DoclingConverter(
                    output_dir=str(self._storage.base_dir / doc_id)
                )
                result = conv.convert(pdf_path)
                from pathlib import Path as _Path

                markdown = _Path(result["markdown_path"]).read_text(
                    encoding="utf-8"
                )
            else:
                # Default: pymupdf4llm
                import pymupdf4llm

                markdown = pymupdf4llm.to_markdown(str(pdf_path))

            md_rel = await self._storage.save_text(
                markdown, doc_id, "markdown.md"
            )

            await self._update_status(
                db,
                doc_id,
                "converted",
                {
                    "markdown_path": md_rel,
                    "converter": converter,
                    "converted_at": datetime.now(timezone.utc),
                },
            )
            logger.info(
                "Converted document %s to markdown (converter=%s).",
                doc_id,
                converter,
            )
        except Exception as exc:
            logger.exception("Convert failed for document %s", doc_id)
            await self._fail(db, doc_id, str(exc))

    # ------------------------------------------------------------------
    # Step 2: Clean Markdown
    # ------------------------------------------------------------------

    async def clean(self, doc_id: str, db: AsyncIOMotorDatabase) -> None:
        """Clean converted markdown content.

        Updates status: ``cleaning`` → ``cleaned`` (or ``failed``).
        """
        try:
            doc = await self._get_doc(db, doc_id)
            if doc is None:
                return

            await self._update_status(
                db, doc_id, "cleaning", {"error_message": None}
            )

            if not doc.get("markdown_path"):
                raise ValueError("No markdown content to clean")

            raw_md = await self._storage.read_text(doc["markdown_path"])

            from document_loader.clean_markdown import clean_markdown
            cleaned = clean_markdown(raw_md)

            cleaned_rel = await self._storage.save_text(
                cleaned, doc_id, "cleaned.md"
            )

            await self._update_status(
                db,
                doc_id,
                "cleaned",
                {
                    "cleaned_path": cleaned_rel,
                    "cleaned_at": datetime.now(timezone.utc),
                },
            )
            logger.info("Cleaned markdown for document %s.", doc_id)
        except Exception as exc:
            logger.exception("Clean failed for document %s", doc_id)
            await self._fail(db, doc_id, str(exc))

    # ------------------------------------------------------------------
    # Step 3: Chunk
    # ------------------------------------------------------------------

    async def chunk(
        self, doc_id: str, strategy: str, db: AsyncIOMotorDatabase
    ) -> None:
        """Chunk document content using the given strategy.

        Stores chunks in the ``document_chunks`` MongoDB collection.
        Updates status: ``chunking`` → ``chunked`` (or ``failed``).
        """
        try:
            doc = await self._get_doc(db, doc_id)
            if doc is None:
                return

            await self._update_status(
                db,
                doc_id,
                "chunking",
                {
                    "error_message": None,
                    "chunking_strategy": strategy,
                    "chunks_reviewed": False,
                },
            )

            # Prefer cleaned content, fall back to markdown
            text_path = doc.get("cleaned_path") or doc.get("markdown_path")
            if not text_path:
                raise ValueError("No text content available for chunking")

            text_content = await self._storage.read_text(text_path)

            # Create chunker and run
            chunker = _create_chunker(strategy, converter=doc.get("converter", "pymupdf4llm"))
            raw_chunks, stats = _run_chunker(
                chunker, text_content, doc.get("filename", ""), strategy
            )

            # FALLBACK: If hierarchical/olmocr produces 0 chunks (e.g. not a legal doc), fallback to recursive
            if not raw_chunks and strategy in ("hierarchical", "olmocr"):
                logger.warning(
                    "Strategy '%s' produced 0 chunks for doc %s. Falling back to 'recursive'.",
                    strategy,
                    doc_id,
                )
                strategy = "recursive"
                chunker = _create_chunker(strategy, converter=doc.get("converter", "pymupdf4llm"))
                raw_chunks, stats = _run_chunker(
                    chunker, text_content, doc.get("filename", ""), strategy
                )

            logger.info(
                "Chunker returned %d raw chunks for document %s.",
                len(raw_chunks),
                doc_id,
            )

            # Clear previous chunks for this strategy
            await db[DOCUMENT_CHUNKS_COLLECTION].delete_many(
                {"document_id": ObjectId(doc_id), "metadata.strategy": strategy}
            )

            # Insert new chunks
            chunk_ids: List[str] = []
            skipped = 0
            dump_chunks = []
            for idx, ch in enumerate(raw_chunks):
                chunk_obj_id = ObjectId()
                chunk_uuid = str(uuid.uuid5(uuid.NAMESPACE_OID, str(chunk_obj_id)))
                
                # Extract content from chunk dict
                content = ch.get("content", "")
                if not content:
                    skipped += 1
                    logger.warning(
                        "Chunk %d for document %s has empty content (keys=%s), skipping.",
                        idx,
                        doc_id,
                        list(ch.keys()),
                    )
                    continue

                # Build metadata — merge chunker metadata with pipeline metadata
                chunk_meta = ch.get("metadata", {})
                chunk_meta.update(
                    {
                        "strategy": strategy,
                        "document_id": doc_id,
                        "filename": doc["filename"],
                        "collection": doc["collection"],
                    }
                )
                # Preserve chunker-assigned ID for parent_id remapping in embed_and_index
                chunker_original_id = ch.get("id", "")
                if chunker_original_id:
                    chunk_meta["chunker_original_id"] = chunker_original_id
                # Merge admin-provided metadata overrides
                if doc.get("metadata_overrides"):
                    chunk_meta.update(doc["metadata_overrides"])

                await db[DOCUMENT_CHUNKS_COLLECTION].insert_one(
                    {
                        "_id": chunk_obj_id,
                        "document_id": ObjectId(doc_id),
                        "chunk_index": idx,
                        "content": content,
                        "metadata": chunk_meta,
                        "qdrant_id": chunk_uuid,
                    }
                )
                chunk_ids.append(str(chunk_obj_id))
                
                dump_dict = {
                    "id": chunk_uuid,
                    "chunk_id": ch.get("chunk_id", f"chunk_{idx:04d}"),
                    "readable_id": ch.get("readable_id", f"chunk_{idx:04d}"),
                    "content": content,
                    "metadata": chunk_meta
                }
                dump_chunks.append(dump_dict)

            if skipped:
                logger.warning(
                    "Document %s: skipped %d empty chunks out of %d.",
                    doc_id,
                    skipped,
                    len(raw_chunks),
                )

            # Dump chunks for debugging
            try:
                import json
                from pathlib import Path

                # Project-relative path (RAG_v2/data/quydinh/admin_upload); no
                # hardcoded per-developer absolute paths.
                dump_dir = (
                    Path(__file__).resolve().parent.parent
                    / "data"
                    / "quydinh"
                    / "admin_upload"
                )
                dump_dir.mkdir(parents=True, exist_ok=True)
                dump_file = dump_dir / f"{doc_id}_{strategy}_chunks.json"
                with open(dump_file, "w", encoding="utf-8") as f:
                    json.dump(dump_chunks, f, ensure_ascii=False, indent=2)
                logger.info("Dumped %d debug chunks to %s", len(dump_chunks), dump_file)
            except Exception as e:
                logger.warning("Failed to dump chunks for debug: %s", str(e))

            # CRITICAL FIX: fail if no valid chunks were produced
            if not chunk_ids:
                raise ValueError(
                    f"Chunking produced 0 valid chunks "
                    f"(strategy={strategy}, raw_chunks={len(raw_chunks)}, "
                    f"skipped={skipped})"
                )

            await self._update_status(
                db,
                doc_id,
                "chunked",
                {
                    "chunk_count": len(chunk_ids),
                    "chunk_ids": chunk_ids,
                    "chunks_reviewed": False,
                    "chunked_at": datetime.now(timezone.utc),
                },
            )
            logger.info(
                "Chunked document %s: %d chunks (strategy=%s).",
                doc_id,
                len(chunk_ids),
                strategy,
            )
        except Exception as exc:
            logger.exception("Chunk failed for document %s", doc_id)
            await self._fail(db, doc_id, str(exc))

    # ------------------------------------------------------------------
    # Step 4: Embed + Index
    # ------------------------------------------------------------------

    async def embed_and_index(
        self, doc_id: str, db: AsyncIOMotorDatabase
    ) -> None:
        """Embed chunks with BGE-M3 + E5 and index into Qdrant + Elasticsearch.

        Each chunk's metadata includes ``document_id`` for cleanup on DELETE.
        Updates status: ``embedding`` → ``indexed`` (or ``failed``).
        """
        try:
            doc = await self._get_doc(db, doc_id)
            if doc is None:
                return

            if not doc.get("chunks_reviewed", False):
                raise ValueError("Chunks must be approved before indexing")

            await self._update_status(
                db, doc_id, "embedding", {"error_message": None}
            )

            chunk_ids = doc.get("chunk_ids", [])
            if not chunk_ids:
                raise ValueError("No chunks to index")

            # Load all chunks from MongoDB
            cursor = (
                db[DOCUMENT_CHUNKS_COLLECTION]
                .find({"document_id": ObjectId(doc_id)})
                .sort("chunk_index", 1)
            )
            chunks = [c async for c in cursor]

            if not chunks:
                raise ValueError("No chunks found in database")

            # --- Separate ES vs Qdrant chunk sets ---
            # ES: only child/recursive/appendix (searchable via BM25)
            es_chunks = [c for c in chunks if is_indexable_chunk(c)]
            # Qdrant: parent + child (parent stored for ID-based expansion,
            # excluded from search by must_not level=parent filter)
            qdrant_chunks = [c for c in chunks if is_qdrant_storable(c)]

            skipped_chunks = len(chunks) - len(qdrant_chunks)
            if skipped_chunks:
                logger.info(
                    "Skipping %d non-storable header chunk(s) for document %s.",
                    skipped_chunks,
                    doc_id,
                )
            if not qdrant_chunks:
                raise ValueError("No indexable chunks found in database")

            # --- Build parent_id remapping ---
            # RecursiveChunker assigns uuid4() as parent.id (stored as chunker_original_id)
            # Qdrant uses uuid5(NAMESPACE_OID, MongoDB_ObjectId) as point ID
            # Map: chunker_original_id → qdrant_point_id for parent chunks
            parent_id_remap: Dict[str, str] = {}
            for c in qdrant_chunks:
                meta = c.get("metadata", {})
                level = str(meta.get("level", "")).strip().lower()
                if level == "parent":
                    chunker_id = meta.get("chunker_original_id", "")
                    qdrant_id = c.get("qdrant_id", str(uuid.uuid5(uuid.NAMESPACE_OID, str(c["_id"]))))
                    if chunker_id:
                        parent_id_remap[chunker_id] = qdrant_id

            # Remap children's metadata.parent_id to actual Qdrant point IDs
            remapped_count = 0
            for c in qdrant_chunks:
                meta = c.get("metadata", {})
                old_pid = meta.get("parent_id")
                if old_pid and old_pid in parent_id_remap:
                    meta["parent_id"] = parent_id_remap[old_pid]
                    remapped_count += 1
            if remapped_count:
                logger.info(
                    "Remapped parent_id for %d child chunks (document %s).",
                    remapped_count,
                    doc_id,
                )

            # --- Embed and index to Qdrant (parent + child) ---
            qdrant_texts = [c["content"] for c in qdrant_chunks]
            qdrant_metadatas = [c.get("metadata", {}) for c in qdrant_chunks]
            qdrant_ids = [c.get("qdrant_id", str(uuid.uuid5(uuid.NAMESPACE_OID, str(c["_id"])))) for c in qdrant_chunks]

            logger.info(
                "Embedding %d chunks (%d parents) for document %s...",
                len(qdrant_texts),
                len(parent_id_remap),
                doc_id,
            )
            bge_embedder = self._get_bge_embedder()
            e5_embedder = self._get_e5_embedder()

            bge_vectors = bge_embedder.embed_documents(qdrant_texts)
            e5_vectors = e5_embedder.embed_documents(qdrant_texts)

            collection_name = doc["collection"]
            qdrant_store = self._get_qdrant_store(collection_name)
            qdrant_store.index_documents(
                texts=qdrant_texts,
                bge_m3_vectors=bge_vectors,
                e5_vectors=e5_vectors,
                metadatas=qdrant_metadatas,
                ids=qdrant_ids,
            )

            # --- Index to Elasticsearch (child/recursive/appendix only) ---
            if es_chunks:
                es_texts = [c["content"] for c in es_chunks]
                es_metadatas = [c.get("metadata", {}) for c in es_chunks]
                es_ids = [c.get("qdrant_id", str(uuid.uuid5(uuid.NAMESPACE_OID, str(c["_id"])))) for c in es_chunks]

                es_store = self._get_es_store(collection_name)
                es_store.index_documents(
                    texts=es_texts,
                    metadatas=es_metadatas,
                    ids=es_ids,
                )

            await self._update_status(
                db,
                doc_id,
                "indexed",
                {"indexed_at": datetime.now(timezone.utc)},
            )
            logger.info(
                "Indexed %d chunks (%d parents) for document %s into '%s'.",
                len(qdrant_texts),
                len(parent_id_remap),
                doc_id,
                collection_name,
            )
            try:
                from evaluation.post_index import trigger_post_index_eval

                trigger_post_index_eval(
                    self._settings,
                    reason="document_indexed",
                    document_id=doc_id,
                    collection=collection_name,
                )
            except Exception:
                logger.warning("Post-index eval trigger failed", exc_info=True)
        except Exception as exc:
            logger.exception("Index failed for document %s", doc_id)
            await self._fail(db, doc_id, str(exc))

    # ------------------------------------------------------------------
    # Full pipeline (all steps sequentially)
    # ------------------------------------------------------------------

    async def run_full_pipeline(
        self,
        doc_id: str,
        db: AsyncIOMotorDatabase,
        converter: str = "pymupdf4llm",
    ) -> None:
        """Run convert → clean → chunk sequentially.

        Stops on first failure. Indexing waits for admin chunk approval.
        """
        # Step 1: Convert
        await self.convert_pdf(doc_id, db, converter=converter)
        doc = await self._get_doc(db, doc_id)
        if doc is None or doc["status"] == "failed":
            return

        # Step 2: Clean
        await self.clean(doc_id, db)
        doc = await self._get_doc(db, doc_id)
        if doc is None or doc["status"] == "failed":
            return

        # Step 3: Chunk
        strategy = doc.get("chunking_strategy") or "recursive"
        await self.chunk(doc_id, strategy, db)
        doc = await self._get_doc(db, doc_id)
        if doc is None or doc["status"] == "failed":
            return

    # ------------------------------------------------------------------
    # Cleanup: delete indexed data from vector stores
    # ------------------------------------------------------------------

    async def delete_indexed_data(
        self, doc_id: str, collection_name: str
    ) -> None:
        """Remove a document's indexed data from Qdrant and Elasticsearch.

        Safe to call even if the document was never indexed.
        """
        try:
            qdrant_store = self._get_qdrant_store(collection_name)
            qdrant_store.delete_by_metadata("document_id", doc_id)
        except Exception:
            logger.warning(
                "Failed to delete from Qdrant for doc %s", doc_id, exc_info=True
            )

        try:
            es_store = self._get_es_store(collection_name)
            es_store.delete_by_metadata("document_id", doc_id)
        except Exception:
            logger.warning(
                "Failed to delete from ES for doc %s", doc_id, exc_info=True
            )

    # ------------------------------------------------------------------
    # Rollback
    # ------------------------------------------------------------------

    async def rollback(self, doc_id: str, db: AsyncIOMotorDatabase) -> None:
        """Rollback the document to its previous logical state.
        
        Cleans up artifacts (files, DB chunks, vector store points) created
        by the step that is being rolled back.
        """
        doc = await self._get_doc(db, doc_id)
        if doc is None:
            raise ValueError(f"Document {doc_id} not found")

        status = doc.get("status")

        def _delete_file_safely(rel_path: Optional[str]) -> None:
            if not rel_path:
                return
            try:
                p = self._storage.base_dir / rel_path
                if p.exists():
                    p.unlink()
            except Exception:
                logger.warning("Failed to delete file %s during rollback", rel_path, exc_info=True)

        if status in ("indexed", "embedding"):
            await self.delete_indexed_data(doc_id, doc.get("collection", ""))
            await self._update_status(db, doc_id, "chunked", {"indexed_at": None, "error_message": None})
            logger.info("Rolled back document %s from %s to chunked.", doc_id, status)

        elif status in ("chunked", "chunking"):
            await db[DOCUMENT_CHUNKS_COLLECTION].delete_many({"document_id": ObjectId(doc_id)})
            await self._update_status(db, doc_id, "cleaned", {
                "chunked_at": None,
                "chunk_count": None,
                "chunk_ids": None,
                "chunking_strategy": None,
                "error_message": None
            })
            logger.info("Rolled back document %s from %s to cleaned.", doc_id, status)

        elif status in ("cleaned", "cleaning"):
            _delete_file_safely(doc.get("cleaned_path"))
            await self._update_status(db, doc_id, "converted", {
                "cleaned_at": None,
                "cleaned_path": None,
                "cleaned_reviewed": False,
                "error_message": None
            })
            logger.info("Rolled back document %s from %s to converted.", doc_id, status)

        elif status in ("converted", "converting"):
            _delete_file_safely(doc.get("markdown_path"))
            await self._update_status(db, doc_id, "uploaded", {
                "converted_at": None,
                "markdown_path": None,
                "markdown_reviewed": False,
                "error_message": None
            })
            logger.info("Rolled back document %s from %s to uploaded.", doc_id, status)

        elif status == "failed":
            if doc.get("chunked_at"):
                await self.delete_indexed_data(doc_id, doc.get("collection", ""))
                await self._update_status(db, doc_id, "chunked", {"indexed_at": None, "error_message": None})
                logger.info("Rolled back failed document %s to chunked.", doc_id)
            elif doc.get("cleaned_at"):
                await db[DOCUMENT_CHUNKS_COLLECTION].delete_many({"document_id": ObjectId(doc_id)})
                await self._update_status(db, doc_id, "cleaned", {
                    "chunked_at": None,
                    "chunk_count": None,
                    "chunk_ids": None,
                    "chunking_strategy": None,
                    "error_message": None
                })
                logger.info("Rolled back failed document %s to cleaned.", doc_id)
            elif doc.get("converted_at"):
                _delete_file_safely(doc.get("cleaned_path"))
                await self._update_status(db, doc_id, "converted", {
                    "cleaned_at": None,
                    "cleaned_path": None,
                    "cleaned_reviewed": False,
                    "error_message": None
                })
                logger.info("Rolled back failed document %s to converted.", doc_id)
            else:
                _delete_file_safely(doc.get("markdown_path"))
                await self._update_status(db, doc_id, "uploaded", {
                    "converted_at": None,
                    "markdown_path": None,
                    "markdown_reviewed": False,
                    "error_message": None
                })
                logger.info("Rolled back failed document %s to uploaded.", doc_id)
        else:
            raise ValueError(f"Cannot rollback document {doc_id} from status '{status}'")
