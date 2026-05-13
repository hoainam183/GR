"""Admin document upload & pipeline management endpoints.

All endpoints require ``role == 'admin'`` (enforced via ``require_admin``).
Background pipeline steps return **202 Accepted** immediately and update
``DocumentRecord.status`` asynchronously.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Annotated, Optional

from bson import ObjectId
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from motor.motor_asyncio import AsyncIOMotorDatabase

from auth.rbac import require_admin
from models.database import (
    DOCUMENTS_COLLECTION,
    DOCUMENT_CHUNKS_COLLECTION,
    get_database,
)
from models.document import AuditEntry, DocumentRecord
from models.user import UserDocument
from schemas.document import (
    CHUNKER_INFO,
    COLLECTION_CHUNKER_MAP,
    CONVERTER_INFO,
    VALID_COLLECTIONS,
    VALID_CONVERTERS,
    ChunkPreview,
    ChunksResponse,
    CleanedContent,
    DocumentDetail,
    DocumentListResponse,
    MarkdownContent,
)
from utils.storage import LocalStorage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

# Module-level singletons (lazy-initialised)
_storage: LocalStorage | None = None
_pipeline: "DocumentPipeline | None" = None


def _get_storage() -> LocalStorage:
    global _storage
    if _storage is None:
        from config.settings import Settings

        settings = Settings()
        _storage = LocalStorage(base_dir=settings.upload_dir)
    return _storage


def _get_pipeline() -> "DocumentPipeline":
    """Return a module-level DocumentPipeline singleton."""
    global _pipeline
    if _pipeline is None:
        from config.settings import Settings
        from pipeline.document_pipeline import DocumentPipeline

        settings = Settings()
        _pipeline = DocumentPipeline(settings=settings, storage=_get_storage())
    return _pipeline


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════


async def _get_doc_or_404(
    db: AsyncIOMotorDatabase, doc_id: str
) -> dict:
    """Fetch a document by ID or raise 404."""
    if not ObjectId.is_valid(doc_id):
        raise HTTPException(status_code=400, detail="Invalid document ID")
    doc = await db[DOCUMENTS_COLLECTION].find_one({"_id": ObjectId(doc_id)})
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


def _audit(action: str, user_id: str, details: dict | None = None) -> dict:
    """Create an audit log entry dict for ``$push``."""
    entry = AuditEntry(action=action, user_id=user_id, details=details)
    return entry.model_dump()


# ═══════════════════════════════════════════════════════════════════════════════
# POST /admin/documents — Upload PDF(s)
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/documents", status_code=status.HTTP_201_CREATED)
async def upload_documents(
    user: Annotated[UserDocument, Depends(require_admin)],
    db: AsyncIOMotorDatabase = Depends(get_database),
    files: list[UploadFile] = File(...),
    collection: str = Form(...),
    chunking_strategy: Optional[str] = Form(None),
    metadata_overrides: Optional[str] = Form(None),
):
    """Upload one or more PDF files for processing.

    Returns a list of created document records.
    """
    import json

    from config.settings import Settings

    settings = Settings()

    # Validate collection
    if collection not in VALID_COLLECTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid collection. Must be one of: {sorted(VALID_COLLECTIONS)}",
        )

    # Validate batch size
    if len(files) > settings.max_upload_batch:
        raise HTTPException(
            status_code=400,
            detail=f"Max {settings.max_upload_batch} files per batch",
        )

    # Parse metadata_overrides if provided as JSON string
    meta = {}
    if metadata_overrides:
        try:
            meta = json.loads(metadata_overrides)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid metadata_overrides JSON")

    # Suggest chunking strategy if not provided
    strategy = chunking_strategy or COLLECTION_CHUNKER_MAP.get(collection, "recursive")

    storage = _get_storage()
    created = []

    for f in files:
        # Validate file type
        if not f.filename or not f.filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=400,
                detail=f"Only PDF files are allowed. Got: {f.filename!r}",
            )

        # Read content to check size
        content = await f.read()
        file_size = len(content)
        await f.seek(0)  # Reset for storage save

        if file_size > settings.max_upload_size_mb * 1024 * 1024:
            raise HTTPException(
                status_code=400,
                detail=f"File {f.filename!r} exceeds {settings.max_upload_size_mb}MB limit",
            )

        # Create an ObjectId for the document
        doc_id = str(ObjectId())

        # Save file
        file_path = await storage.save_upload(f, doc_id)

        # Build document record
        now = datetime.now(timezone.utc)
        doc_record = {
            "_id": ObjectId(doc_id),
            "filename": f.filename,
            "file_size": file_size,
            "file_path": file_path,
            "collection": collection,
            "status": "uploaded",
            "uploaded_by": ObjectId(str(user.id)),
            "uploaded_at": now,
            "markdown_path": None,
            "cleaned_path": None,
            "chunk_count": None,
            "chunk_ids": None,
            "chunking_strategy": strategy,
            "markdown_reviewed": False,
            "cleaned_reviewed": False,
            "chunks_reviewed": False,
            "metadata_overrides": meta,
            "error_message": None,
            "converted_at": None,
            "cleaned_at": None,
            "chunked_at": None,
            "indexed_at": None,
            "audit_log": [_audit("upload", str(user.id), {"filename": f.filename})],
        }

        await db[DOCUMENTS_COLLECTION].insert_one(doc_record)
        created.append(DocumentDetail.from_document(doc_record))

    return [d.model_dump() for d in created]


# ═══════════════════════════════════════════════════════════════════════════════
# GET /admin/documents — List documents
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/documents")
async def list_documents(
    user: Annotated[UserDocument, Depends(require_admin)],
    db: AsyncIOMotorDatabase = Depends(get_database),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    collection_filter: Optional[str] = Query(None, alias="collection"),
):
    """List documents with pagination and optional filters."""
    query: dict = {}
    if status_filter:
        query["status"] = status_filter
    if collection_filter:
        query["collection"] = collection_filter

    total = await db[DOCUMENTS_COLLECTION].count_documents(query)
    skip = (page - 1) * limit
    cursor = (
        db[DOCUMENTS_COLLECTION]
        .find(query)
        .sort("uploaded_at", -1)
        .skip(skip)
        .limit(limit)
    )
    docs = [DocumentDetail.from_document(d) async for d in cursor]

    return DocumentListResponse(
        documents=docs, total=total, page=page, limit=limit
    ).model_dump()


# ═══════════════════════════════════════════════════════════════════════════════
# GET /admin/documents/{id} — Document detail
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/documents/{doc_id}")
async def get_document(
    doc_id: str,
    user: Annotated[UserDocument, Depends(require_admin)],
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Get full document detail (used for polling status)."""
    doc = await _get_doc_or_404(db, doc_id)
    return DocumentDetail.from_document(doc).model_dump()


# ═══════════════════════════════════════════════════════════════════════════════
# DELETE /admin/documents/{id} — Delete + cleanup
# ═══════════════════════════════════════════════════════════════════════════════


@router.delete("/documents/{doc_id}")
async def delete_document(
    doc_id: str,
    user: Annotated[UserDocument, Depends(require_admin)],
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Delete a document and clean up all associated data."""
    doc = await _get_doc_or_404(db, doc_id)

    # Remove from vector stores (if indexed)
    if doc.get("status") == "indexed" and doc.get("chunk_ids"):
        pipeline = _get_pipeline()
        await pipeline.delete_indexed_data(doc_id, doc["collection"])

    # Remove chunks from MongoDB
    await db[DOCUMENT_CHUNKS_COLLECTION].delete_many(
        {"document_id": ObjectId(doc_id)}
    )

    # Remove files from disk
    storage = _get_storage()
    await storage.delete_all(doc_id)

    # Remove document record
    await db[DOCUMENTS_COLLECTION].delete_one({"_id": ObjectId(doc_id)})

    return {"detail": "Document deleted", "id": doc_id}


# ═══════════════════════════════════════════════════════════════════════════════
# POST /admin/documents/{id}/rollback — Rollback document state
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/documents/{doc_id}/rollback", status_code=status.HTTP_200_OK)
async def rollback_document(
    doc_id: str,
    user: Annotated[UserDocument, Depends(require_admin)],
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Rollback a document to its previous logical state.
    
    This will clean up any artifacts (files, chunks, vectors) from the current
    or failed step and revert the document status.
    """
    doc = await _get_doc_or_404(db, doc_id)
    
    if doc.get("status") == "uploaded":
        raise HTTPException(
            status_code=400,
            detail="Cannot rollback document that is only in 'uploaded' state."
        )

    pipeline = _get_pipeline()
    try:
        await pipeline.rollback(doc_id, db)
    except Exception as e:
        logger.exception("Failed to rollback document %s", doc_id)
        raise HTTPException(
            status_code=500,
            detail=f"Rollback failed: {str(e)}"
        )
        
    await db[DOCUMENTS_COLLECTION].update_one(
        {"_id": ObjectId(doc_id)},
        {"$push": {"audit_log": _audit("rollback", str(user.id))}},
    )

    return {"detail": "Document rolled back successfully", "id": doc_id}

# ═══════════════════════════════════════════════════════════════════════════════
# POST /admin/documents/{id}/convert — PDF → Markdown (background)
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/documents/{doc_id}/convert", status_code=status.HTTP_202_ACCEPTED)
async def convert_document(
    doc_id: str,
    user: Annotated[UserDocument, Depends(require_admin)],
    db: AsyncIOMotorDatabase = Depends(get_database),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    converter: Optional[str] = Query(None, description="Converter: pymupdf4llm or docling"),
):
    """Trigger PDF → Markdown conversion in background.

    Query params:
        converter: PDF converter to use (default ``pymupdf4llm``).
    """
    doc = await _get_doc_or_404(db, doc_id)

    if doc["status"] not in ("uploaded", "failed"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot convert document in status '{doc['status']}'",
        )

    effective_converter = converter or "pymupdf4llm"
    if effective_converter not in VALID_CONVERTERS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid converter. Must be one of: {sorted(VALID_CONVERTERS)}",
        )

    await db[DOCUMENTS_COLLECTION].update_one(
        {"_id": ObjectId(doc_id)},
        {
            "$set": {
                "status": "converting",
                "error_message": None,
                "converter": effective_converter,
            },
            "$push": {
                "audit_log": _audit(
                    "convert", str(user.id), {"converter": effective_converter}
                )
            },
        },
    )

    background_tasks.add_task(_bg_convert, doc_id, effective_converter, db)

    return {
        "doc_id": doc_id,
        "status": "converting",
        "converter": effective_converter,
    }


async def _bg_convert(
    doc_id: str, converter: str, db: AsyncIOMotorDatabase
) -> None:
    """Background: convert PDF to markdown via DocumentPipeline."""
    pipeline = _get_pipeline()
    await pipeline.convert_pdf(doc_id, db, converter=converter)


# ═══════════════════════════════════════════════════════════════════════════════
# GET /admin/documents/{id}/markdown — Get markdown for review
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/documents/{doc_id}/markdown")
async def get_markdown(
    doc_id: str,
    user: Annotated[UserDocument, Depends(require_admin)],
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Get converted markdown content for review."""
    doc = await _get_doc_or_404(db, doc_id)
    if not doc.get("markdown_path"):
        raise HTTPException(status_code=404, detail="Markdown not available yet")

    storage = _get_storage()
    content = await storage.read_text(doc["markdown_path"])
    return {"content": content}


# ═══════════════════════════════════════════════════════════════════════════════
# PUT /admin/documents/{id}/markdown — Edit/approve markdown
# ═══════════════════════════════════════════════════════════════════════════════


@router.put("/documents/{doc_id}/markdown")
async def update_markdown(
    doc_id: str,
    body: MarkdownContent,
    user: Annotated[UserDocument, Depends(require_admin)],
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Edit and/or approve the converted markdown."""
    doc = await _get_doc_or_404(db, doc_id)

    storage = _get_storage()
    md_path = await storage.save_text(body.content, doc_id, "markdown.md")

    await db[DOCUMENTS_COLLECTION].update_one(
        {"_id": ObjectId(doc_id)},
        {
            "$set": {
                "markdown_path": md_path,
                "markdown_reviewed": True,
            },
            "$push": {"audit_log": _audit("approve_markdown", str(user.id))},
        },
    )
    return {"detail": "Markdown updated and approved"}


# ═══════════════════════════════════════════════════════════════════════════════
# POST /admin/documents/{id}/clean — Clean markdown (background)
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/documents/{doc_id}/clean", status_code=status.HTTP_202_ACCEPTED)
async def clean_document(
    doc_id: str,
    user: Annotated[UserDocument, Depends(require_admin)],
    db: AsyncIOMotorDatabase = Depends(get_database),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """Trigger markdown cleaning in background."""
    doc = await _get_doc_or_404(db, doc_id)

    if doc["status"] not in ("converted", "failed"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot clean document in status '{doc['status']}'",
        )

    if not doc.get("markdown_path"):
        raise HTTPException(status_code=409, detail="No markdown to clean")

    await db[DOCUMENTS_COLLECTION].update_one(
        {"_id": ObjectId(doc_id)},
        {
            "$set": {"status": "cleaning", "error_message": None},
            "$push": {"audit_log": _audit("clean", str(user.id))},
        },
    )

    background_tasks.add_task(_bg_clean, doc_id, db)

    return {"doc_id": doc_id, "status": "cleaning"}


async def _bg_clean(doc_id: str, db: AsyncIOMotorDatabase) -> None:
    """Background: clean markdown content via DocumentPipeline."""
    pipeline = _get_pipeline()
    await pipeline.clean(doc_id, db)


# ═══════════════════════════════════════════════════════════════════════════════
# GET /admin/documents/{id}/cleaned — Get cleaned content for review
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/documents/{doc_id}/cleaned")
async def get_cleaned(
    doc_id: str,
    user: Annotated[UserDocument, Depends(require_admin)],
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Get cleaned markdown content for review."""
    doc = await _get_doc_or_404(db, doc_id)
    if not doc.get("cleaned_path"):
        raise HTTPException(status_code=404, detail="Cleaned content not available yet")

    storage = _get_storage()
    content = await storage.read_text(doc["cleaned_path"])
    return {"content": content}


# ═══════════════════════════════════════════════════════════════════════════════
# PUT /admin/documents/{id}/cleaned — Edit/approve cleaned
# ═══════════════════════════════════════════════════════════════════════════════


@router.put("/documents/{doc_id}/cleaned")
async def update_cleaned(
    doc_id: str,
    body: CleanedContent,
    user: Annotated[UserDocument, Depends(require_admin)],
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Edit and/or approve cleaned markdown."""
    doc = await _get_doc_or_404(db, doc_id)

    storage = _get_storage()
    cleaned_rel = await storage.save_text(body.content, doc_id, "cleaned.md")

    await db[DOCUMENTS_COLLECTION].update_one(
        {"_id": ObjectId(doc_id)},
        {
            "$set": {
                "cleaned_path": cleaned_rel,
                "cleaned_reviewed": True,
            },
            "$push": {"audit_log": _audit("approve_cleaned", str(user.id))},
        },
    )
    return {"detail": "Cleaned content updated and approved"}


# ═══════════════════════════════════════════════════════════════════════════════
# POST /admin/documents/{id}/chunk — Chunk document (background)
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/documents/{doc_id}/chunk", status_code=status.HTTP_202_ACCEPTED)
async def chunk_document(
    doc_id: str,
    user: Annotated[UserDocument, Depends(require_admin)],
    db: AsyncIOMotorDatabase = Depends(get_database),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    strategy: Optional[str] = Query(None),
):
    """Trigger chunking in background. Optionally override strategy via query param."""
    doc = await _get_doc_or_404(db, doc_id)

    if doc["status"] not in ("cleaned", "converted", "failed"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot chunk document in status '{doc['status']}'",
        )

    # Use the provided strategy or fall back to the document's stored strategy
    effective_strategy = strategy or doc.get("chunking_strategy") or "recursive"

    await db[DOCUMENTS_COLLECTION].update_one(
        {"_id": ObjectId(doc_id)},
        {
            "$set": {
                "status": "chunking",
                "chunking_strategy": effective_strategy,
                "error_message": None,
            },
            "$push": {
                "audit_log": _audit(
                    "chunk", str(user.id), {"strategy": effective_strategy}
                )
            },
        },
    )

    background_tasks.add_task(_bg_chunk, doc_id, effective_strategy, db)

    return {"doc_id": doc_id, "status": "chunking", "strategy": effective_strategy}


async def _bg_chunk(
    doc_id: str, strategy: str, db: AsyncIOMotorDatabase
) -> None:
    """Background: chunk document content via DocumentPipeline."""
    pipeline = _get_pipeline()
    await pipeline.chunk(doc_id, strategy, db)


# ═══════════════════════════════════════════════════════════════════════════════
# GET /admin/documents/{id}/chunks — Get chunks (paginated)
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/documents/{doc_id}/chunks")
async def get_chunks(
    doc_id: str,
    user: Annotated[UserDocument, Depends(require_admin)],
    db: AsyncIOMotorDatabase = Depends(get_database),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    strategy: Optional[str] = Query(None, description="Filter by chunking strategy"),
):
    """Get paginated chunks for review.

    Query params:
        strategy: Filter chunks by strategy name (for side-by-side comparison).
    """
    doc = await _get_doc_or_404(db, doc_id)

    # Build filter
    chunk_filter: dict = {"document_id": ObjectId(doc_id)}
    strategy_filter = strategy
    if strategy_filter:
        chunk_filter["metadata.strategy"] = strategy_filter

    total = await db[DOCUMENT_CHUNKS_COLLECTION].count_documents(chunk_filter)
    skip = (page - 1) * limit
    cursor = (
        db[DOCUMENT_CHUNKS_COLLECTION]
        .find(chunk_filter)
        .sort("chunk_index", 1)
        .skip(skip)
        .limit(limit)
    )

    chunks = []
    sizes = []
    async for c in cursor:
        chunks.append(
            ChunkPreview(
                chunk_id=str(c["_id"]),
                chunk_index=c["chunk_index"],
                content=c["content"],
                metadata=c.get("metadata", {}),
            )
        )
        sizes.append(len(c["content"]))

    # Compute stats from all chunks (not just this page)
    all_sizes_cursor = db[DOCUMENT_CHUNKS_COLLECTION].find(
        {"document_id": ObjectId(doc_id)}, {"content": 1}
    )
    all_sizes = [len(c["content"]) async for c in all_sizes_cursor]

    stats = {}
    if all_sizes:
        stats = {
            "avg_size": round(sum(all_sizes) / len(all_sizes)),
            "min_size": min(all_sizes),
            "max_size": max(all_sizes),
            "total_chars": sum(all_sizes),
        }

    return ChunksResponse(
        chunks=chunks,
        total=total,
        page=page,
        limit=limit,
        strategy=strategy_filter or doc.get("chunking_strategy", "unknown"),
        stats=stats,
    ).model_dump()


# ═══════════════════════════════════════════════════════════════════════════════
# GET /admin/documents/{id}/chunk-strategies — List chunk sets
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/documents/{doc_id}/chunk-strategies")
async def list_chunk_strategies(
    doc_id: str,
    user: Annotated[UserDocument, Depends(require_admin)],
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """List available chunk sets (strategies) for side-by-side comparison."""
    await _get_doc_or_404(db, doc_id)

    pipeline_agg = [
        {"$match": {"document_id": ObjectId(doc_id)}},
        {
            "$group": {
                "_id": "$metadata.strategy",
                "count": {"$sum": 1},
                "avg_size": {"$avg": {"$strLenCP": "$content"}},
            }
        },
    ]
    cursor = db[DOCUMENT_CHUNKS_COLLECTION].aggregate(pipeline_agg)
    strategies = []
    async for doc_agg in cursor:
        strategies.append(
            {
                "strategy": doc_agg["_id"] or "unknown",
                "chunk_count": doc_agg["count"],
                "avg_size": round(doc_agg["avg_size"]) if doc_agg["avg_size"] else 0,
            }
        )
    return {"strategies": strategies}


# ═══════════════════════════════════════════════════════════════════════════════
# POST /admin/documents/{id}/chunks/select — Finalize a strategy
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/documents/{doc_id}/chunks/select")
async def select_chunk_strategy(
    doc_id: str,
    user: Annotated[UserDocument, Depends(require_admin)],
    db: AsyncIOMotorDatabase = Depends(get_database),
    strategy: str = Query(..., description="The strategy to keep"),
):
    """Finalize a chunking strategy: keep its chunks and delete all others."""
    doc = await _get_doc_or_404(db, doc_id)

    # Delete chunks from other strategies
    delete_result = await db[DOCUMENT_CHUNKS_COLLECTION].delete_many(
        {
            "document_id": ObjectId(doc_id),
            "metadata.strategy": {"$ne": strategy},
        }
    )

    # Update document with the selected strategy
    remaining = await db[DOCUMENT_CHUNKS_COLLECTION].count_documents(
        {"document_id": ObjectId(doc_id)}
    )
    remaining_ids_cursor = db[DOCUMENT_CHUNKS_COLLECTION].find(
        {"document_id": ObjectId(doc_id)}, {"_id": 1}
    )
    remaining_ids = [str(c["_id"]) async for c in remaining_ids_cursor]

    await db[DOCUMENTS_COLLECTION].update_one(
        {"_id": ObjectId(doc_id)},
        {
            "$set": {
                "chunking_strategy": strategy,
                "chunk_count": remaining,
                "chunk_ids": remaining_ids,
            },
            "$push": {
                "audit_log": _audit(
                    "select_strategy",
                    str(user.id),
                    {"strategy": strategy, "deleted_other": delete_result.deleted_count},
                )
            },
        },
    )

    return {
        "detail": f"Selected strategy '{strategy}'",
        "kept_chunks": remaining,
        "deleted_chunks": delete_result.deleted_count,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# PUT /admin/documents/{id}/chunks — Approve chunks
# ═══════════════════════════════════════════════════════════════════════════════


@router.put("/documents/{doc_id}/chunks")
async def approve_chunks(
    doc_id: str,
    user: Annotated[UserDocument, Depends(require_admin)],
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Mark chunks as reviewed/approved."""
    await _get_doc_or_404(db, doc_id)

    await db[DOCUMENTS_COLLECTION].update_one(
        {"_id": ObjectId(doc_id)},
        {
            "$set": {"chunks_reviewed": True},
            "$push": {"audit_log": _audit("approve_chunks", str(user.id))},
        },
    )
    return {"detail": "Chunks approved"}


# ═══════════════════════════════════════════════════════════════════════════════
# POST /admin/documents/{id}/index — Embed + index (background)
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/documents/{doc_id}/index", status_code=status.HTTP_202_ACCEPTED)
async def index_document(
    doc_id: str,
    user: Annotated[UserDocument, Depends(require_admin)],
    db: AsyncIOMotorDatabase = Depends(get_database),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """Trigger embedding + indexing in background."""
    doc = await _get_doc_or_404(db, doc_id)

    if doc["status"] not in ("chunked", "failed"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot index document in status '{doc['status']}'",
        )

    if not doc.get("chunk_ids"):
        raise HTTPException(status_code=409, detail="No chunks to index")

    await db[DOCUMENTS_COLLECTION].update_one(
        {"_id": ObjectId(doc_id)},
        {
            "$set": {"status": "embedding", "error_message": None},
            "$push": {"audit_log": _audit("index", str(user.id))},
        },
    )

    background_tasks.add_task(_bg_index, doc_id, db)

    return {"doc_id": doc_id, "status": "embedding"}


async def _bg_index(doc_id: str, db: AsyncIOMotorDatabase) -> None:
    """Background: embed + index chunks via DocumentPipeline."""
    pipeline = _get_pipeline()
    await pipeline.embed_and_index(doc_id, db)


# ═══════════════════════════════════════════════════════════════════════════════
# POST /admin/documents/{id}/pipeline — Full auto pipeline (background)
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/documents/{doc_id}/pipeline", status_code=status.HTTP_202_ACCEPTED)
async def run_full_pipeline(
    doc_id: str,
    user: Annotated[UserDocument, Depends(require_admin)],
    db: AsyncIOMotorDatabase = Depends(get_database),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """Run the full pipeline (convert → clean → chunk → index) in background."""
    doc = await _get_doc_or_404(db, doc_id)

    if doc["status"] not in ("uploaded", "failed"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot run pipeline on document in status '{doc['status']}'",
        )

    await db[DOCUMENTS_COLLECTION].update_one(
        {"_id": ObjectId(doc_id)},
        {
            "$set": {"status": "converting", "error_message": None},
            "$push": {"audit_log": _audit("pipeline", str(user.id))},
        },
    )

    background_tasks.add_task(_bg_full_pipeline, doc_id, db)

    return {"doc_id": doc_id, "status": "converting"}


async def _bg_full_pipeline(doc_id: str, db: AsyncIOMotorDatabase) -> None:
    """Background: run all pipeline steps via DocumentPipeline."""
    pipeline = _get_pipeline()
    await pipeline.run_full_pipeline(doc_id, db)


# ═══════════════════════════════════════════════════════════════════════════════
# GET /admin/converters — List available converters
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/converters")
async def list_converters(
    user: Annotated[UserDocument, Depends(require_admin)],
):
    """Return available PDF → Markdown converters."""
    return {"converters": CONVERTER_INFO}


# ═══════════════════════════════════════════════════════════════════════════════
# GET /admin/chunkers — List available chunker strategies
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/chunkers")
async def list_chunkers(
    user: Annotated[UserDocument, Depends(require_admin)],
    collection: Optional[str] = Query(None),
):
    """Return available chunker strategies, optionally filtered by collection."""
    if collection:
        filtered = [
            c for c in CHUNKER_INFO if collection in c.get("collections", [])
        ]
        return {"chunkers": filtered}
    return {"chunkers": CHUNKER_INFO}
