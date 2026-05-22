"""Contextual Retrieval — LLM-based chunk contextualization at indexing time.

Implements Anthropic-style contextual retrieval: each chunk is enriched with
a 1-2 sentence LLM-generated context prefix that describes **where the chunk
sits within the parent document**.  This dramatically improves retrieval
accuracy because:

1. Chunks that lost structural context during splitting regain it.
2. BM25 keyword search benefits from additional semantic terms.
3. Vector embeddings capture document-level positioning.

This module is designed to run ONCE during indexing — not at query time.
The enriched chunks are then embedded and stored in Qdrant/ES.

Usage::

    from chunking.contextualizer import ChunkContextualizer

    ctx = ChunkContextualizer(llm=gemini_flash)
    enriched_chunks = ctx.contextualize(chunks, doc_metadata)
    # → Each chunk.content now starts with "[context prefix]\\n..."
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_CONTEXT_PROMPT_TEMPLATE = (
    "Bạn đang phân tích tài liệu sau:\n"
    "  Tiêu đề: {title}\n"
    "  Loại: {doc_type}\n"
    "  Bộ sưu tập: {collection}\n"
    "{hierarchy_line}"
    "\n"
    "Đoạn text trích xuất:\n"
    '"""\n{chunk_text}\n"""\n'
    "\n"
    "Viết MỘT câu ngắn (dưới 30 từ) mô tả ngữ cảnh của đoạn text trên "
    "trong tài liệu. Chỉ trả lời câu mô tả, không giải thích thêm."
)


class ChunkContextualizer:
    """Enrich chunks with LLM-generated contextual prefixes.

    Parameters:
        llm: Any LLM with a ``generate(prompt: str) -> str`` method.
        max_chunk_preview: Max characters of chunk text sent to LLM (saves tokens).
        skip_parent_chunks: If True, skip chunks with level="parent".
        batch_size: Process chunks in batches of this size (for logging).
    """

    def __init__(
        self,
        llm: Any,
        max_chunk_preview: int = 500,
        skip_parent_chunks: bool = True,
        batch_size: int = 10,
    ) -> None:
        self.llm = llm
        self.max_chunk_preview = max_chunk_preview
        self.skip_parent_chunks = skip_parent_chunks
        self.batch_size = batch_size

    def contextualize(
        self,
        chunks: List[Dict[str, Any]],
        doc_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Add contextual prefix to each chunk's content.

        Args:
            chunks: List of chunk dicts with at minimum ``content`` and ``metadata`` keys.
            doc_metadata: Document-level metadata (title, doc_type, collection).

        Returns:
            The same list of chunks with ``content`` modified in-place
            (contextual prefix prepended).  Chunks that fail contextualization
            are returned unchanged.
        """
        doc_metadata = doc_metadata or {}
        title = doc_metadata.get("title", "Không rõ")
        doc_type = doc_metadata.get("doc_type", "Tài liệu học thuật")
        collection = doc_metadata.get("collection", "")

        enriched_count = 0
        skipped_count = 0

        for i, chunk in enumerate(chunks):
            metadata = chunk.get("metadata", {})

            # Skip parent chunks (they're not indexed for retrieval)
            if self.skip_parent_chunks and metadata.get("level") == "parent":
                skipped_count += 1
                continue

            # Skip very short chunks (likely headers or separators)
            content = chunk.get("content", "")
            if len(content.strip()) < 50:
                skipped_count += 1
                continue

            hierarchy = metadata.get("hierarchy_path", "")
            hierarchy_line = f"  Vị trí: {hierarchy}\n" if hierarchy else ""

            prompt = _CONTEXT_PROMPT_TEMPLATE.format(
                title=title,
                doc_type=doc_type,
                collection=collection,
                hierarchy_line=hierarchy_line,
                chunk_text=content[: self.max_chunk_preview],
            )

            try:
                context = self.llm.generate(prompt)
                if context and context.strip():
                    context = context.strip().rstrip(".")
                    chunk["content"] = f"[{context}]\n{content}"
                    enriched_count += 1
                else:
                    skipped_count += 1
            except Exception as exc:
                logger.warning(
                    "Contextualization failed for chunk %d: %s", i, exc
                )
                skipped_count += 1

            # Progress logging
            if (i + 1) % self.batch_size == 0:
                logger.info(
                    "Contextualized %d/%d chunks (enriched=%d, skipped=%d)",
                    i + 1,
                    len(chunks),
                    enriched_count,
                    skipped_count,
                )

        logger.info(
            "Contextualization complete: %d enriched, %d skipped out of %d total",
            enriched_count,
            skipped_count,
            len(chunks),
        )
        return chunks

    def contextualize_single(
        self,
        chunk_text: str,
        doc_title: str = "",
        hierarchy_path: str = "",
        collection: str = "",
    ) -> str:
        """Contextualize a single chunk (convenience method for testing).

        Args:
            chunk_text: Raw chunk text.
            doc_title: Parent document title.
            hierarchy_path: Chunk's position in document hierarchy.
            collection: Target collection name.

        Returns:
            Enriched text with contextual prefix, or original text on failure.
        """
        if len(chunk_text.strip()) < 50:
            return chunk_text

        hierarchy_line = f"  Vị trí: {hierarchy_path}\n" if hierarchy_path else ""
        prompt = _CONTEXT_PROMPT_TEMPLATE.format(
            title=doc_title or "Không rõ",
            doc_type="Tài liệu học thuật",
            collection=collection,
            hierarchy_line=hierarchy_line,
            chunk_text=chunk_text[: self.max_chunk_preview],
        )

        try:
            context = self.llm.generate(prompt)
            if context and context.strip():
                context = context.strip().rstrip(".")
                return f"[{context}]\n{chunk_text}"
        except Exception as exc:
            logger.warning("Single contextualization failed: %s", exc)

        return chunk_text
