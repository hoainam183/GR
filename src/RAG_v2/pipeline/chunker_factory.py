"""Chunker strategy factory: strategy->class mapping and chunk-run normalisation."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

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
VALID_CONVERTERS = {"pymupdf4llm", "docling", "pdfplumber"}

# Chunk-metadata keys owned by the pipeline. Admin-supplied ``metadata_overrides``
# must never clobber these — doing so breaks search filtering (``level``),
# parent-context expansion (``parent_id``), Qdrant point identity (``qdrant_id``),
# and cleanup-by-``document_id``.
PROTECTED_CHUNK_META_KEYS = frozenset(
    {
        "strategy",
        "document_id",
        "filename",
        "collection",
        "parent_id",
        "level",
        "qdrant_id",
        "chunker_original_id",
        "id",
    }
)


def _sanitize_metadata_overrides(
    overrides: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Drop protected keys from admin metadata overrides, logging any rejected."""
    if not overrides:
        return {}
    safe = {k: v for k, v in overrides.items() if k not in PROTECTED_CHUNK_META_KEYS}
    rejected = [k for k in overrides if k in PROTECTED_CHUNK_META_KEYS]
    if rejected:
        logger.warning(
            "Ignored protected metadata_overrides keys: %s", sorted(rejected)
        )
    return safe


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
