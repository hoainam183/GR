from typing import List, Dict, Optional
import re
import uuid


class ArticleLegalChunkerPyMuPDF:
    """
    Chunker for Vietnamese legal documents converted by PyMuPDF4LLM.

    Key differences from Docling version:
    - Detects **CHƯƠNG** and **Điều** (bold) instead of markdown headers (#)
    - Handles PyMuPDF's specific formatting quirks

    Strategy:
    - 1 chunk for entire header
    - Parent: 1 điều (hoặc nhiều điều nhỏ merged)
    - Children: Các khoản trong điều (~500-1000 chars)
    - Chapter context in every chunk
    - Table protection
    """

    def __init__(
        self,
        min_child_size: int = 500,
        max_child_size: int = 1000,
        parent_size_limit: int = 4000,
        split_threshold: int = 1500,  # Only create children if article > this
        chunk_overlap: int = 0,  # No overlap by default for clean splits
    ):
        self.min_child_size = min_child_size
        self.max_child_size = max_child_size
        self.parent_size_limit = parent_size_limit
        self.split_threshold = split_threshold
        self.chunk_overlap = chunk_overlap
        self.reset_state()

    def reset_state(self):
        """Reset all tracking state"""
        self.current_chapter = None
        self.current_chapter_full = None
        self.current_chapter_intro = []
        self.current_article = None
        self.current_article_full = None
        self.current_article_lines = []
        self.articles = []
        self.chunks = []
        self.parsing_phase = "header"

    def parse(self, text: str) -> List[Dict]:
        """Main parsing function"""
        self.reset_state()

        lines = text.split("\n")
        header_lines = []

        for line in lines:
            line_stripped = line.strip()

            if not line_stripped:
                continue

            # === HEADER PHASE ===
            if self.parsing_phase == "header":
                if self._is_chapter(line_stripped) or self._is_article(
                    line_stripped
                ):
                    if header_lines:
                        self._save_header_chunk(header_lines)
                    self.parsing_phase = "body"
                else:
                    header_lines.append(line_stripped)
                    continue

            # === BODY PHASE ===
            if self._is_chapter(line_stripped):
                self._handle_chapter(line_stripped)
            elif self._is_article(line_stripped):
                self._handle_article(line_stripped)
            else:
                self._handle_content_line(line_stripped)

        # Save last article
        self._save_current_article()

        # Create parent-child chunks
        self._create_parent_child_chunks()

        return self.chunks

    # ========================================================================
    # DETECTION METHODS - PYMUPDF4LLM SPECIFIC
    # ========================================================================

    def _is_chapter(self, line: str) -> bool:
        """
        Detect chapter heading in PyMuPDF4LLM format
        Examples:
        - **CHƯƠNG I**
        - **Chương I**
        - **CHƯƠNG I: TÊN CHƯƠNG**
        """
        # Remove any leading/trailing whitespace and asterisks
        cleaned = line.strip().strip("*").strip()
        return bool(re.match(r"^CHƯƠNG\s+[IVX\d]+", cleaned, re.IGNORECASE))

    def _is_article(self, line: str) -> bool:
        """
        Detect article heading in PyMuPDF4LLM format
        Examples:
        - **Điều 1.**
        - **Điều 1. Tiêu đề**
        - **Điều 10. Title**
        """
        cleaned = line.strip().strip("*").strip()
        return bool(re.match(r"^Điều\s+\d+", cleaned))

    def _is_numbered_point(self, line: str) -> bool:
        """
        Detect numbered points: 1. 2. 3.
        """
        return bool(re.match(r"^\d+\.\s+", line.strip()))

    def _is_lettered_point(self, line: str) -> bool:
        """
        Detect lettered points: a) b) c)
        """
        return bool(re.match(r"^[a-z]\)\s+", line.strip()))

    # ========================================================================
    # HANDLER METHODS
    # ========================================================================

    def _handle_chapter(self, line: str):
        """Handle chapter detection"""
        self._save_current_article()

        # Clean bold markers
        self.current_chapter_full = line.strip().strip("*").strip()

        # Extract chapter number
        chapter_match = re.search(
            r"CHƯƠNG\s+([IVX]+|\d+)", self.current_chapter_full, re.IGNORECASE
        )
        self.current_chapter = chapter_match.group(1) if chapter_match else None

        # Keep chapter intro for all articles
        self.current_chapter_intro = [self.current_chapter_full]

    def _handle_article(self, line: str):
        """Handle article detection"""
        self._save_current_article()

        # Clean bold markers
        self.current_article_full = line.strip().strip("*").strip()

        # Extract article number
        article_match = re.match(r"Điều\s+(\d+)", self.current_article_full)
        self.current_article = (
            f"Điều {article_match.group(1)}" if article_match else None
        )

        # Start new article with chapter context
        self.current_article_lines = []

        if self.current_chapter_intro:
            self.current_article_lines.extend(self.current_chapter_intro)
            self.current_article_lines.append("")

        self.current_article_lines.append(self.current_article_full)

    def _handle_content_line(self, line: str):
        """Handle regular content lines"""
        if self.current_article is not None:
            self.current_article_lines.append(line)
        elif self.current_chapter is not None:
            self.current_chapter_intro.append(line)

    # ========================================================================
    # SAVE METHODS
    # ========================================================================

    def _save_header_chunk(self, lines: List[str]):
        """Save document header as a single chunk"""
        content = "\n".join(lines).strip()

        if not content:
            return

        metadata = {
            "doc_type": "legal_document",
            "level": "header",
            "chunk_size": len(content),
            "source_format": "pymupdf4llm",
        }

        self.chunks.append({"content": content, "metadata": metadata})

    def _save_current_article(self):
        """Save current article to articles list"""
        if not self.current_article_lines:
            return

        content = "\n".join(self.current_article_lines).strip()

        if not content:
            return

        article_data = {
            "content": content,
            "chapter": self.current_chapter,
            "chapter_full": self.current_chapter_full,
            "article": self.current_article,
            "article_full": self.current_article_full,
            "size": len(content),
        }

        self.articles.append(article_data)
        self.current_article_lines = []

    # ========================================================================
    # TABLE DETECTION
    # ========================================================================

    def _has_table(self, text: str) -> bool:
        """Detect markdown table"""
        lines = text.split("\n")
        table_lines = [line for line in lines if "|" in line]
        return len(table_lines) >= 2

    def _extract_tables(self, text: str) -> tuple[List[str], List[str]]:
        """Split text into table and non-table parts"""
        lines = text.split("\n")
        parts = []
        tables = []
        current_part = []
        current_table = []
        in_table = False

        for line in lines:
            if "|" in line:
                if not in_table:
                    if current_part:
                        parts.append("\n".join(current_part))
                        current_part = []
                    in_table = True
                    current_table = [line]
                else:
                    current_table.append(line)
            else:
                if in_table:
                    tables.append("\n".join(current_table))
                    in_table = False
                    current_table = []
                current_part.append(line)

        if in_table and current_table:
            tables.append("\n".join(current_table))
        if current_part:
            parts.append("\n".join(current_part))

        return parts, tables

    # ========================================================================
    # PARENT-CHILD CHUNK CREATION
    # ========================================================================

    def _create_parent_child_chunks(self):
        """Create parent and child chunks from articles"""
        for article in self.articles:
            parent_chunk, child_chunks = self._process_article(article)

            self.chunks.append(parent_chunk)
            self.chunks.extend(child_chunks)

    def _process_article(self, article: Dict) -> tuple[Dict, List[Dict]]:
        """Process one article into parent + children chunks"""
        content = article["content"]
        has_table = self._has_table(content)

        # Create parent chunk
        parent_chunk = {
            "content": content,
            "metadata": {
                "doc_type": "legal_document",
                "level": "parent",
                "chapter": article["chapter"],
                "chapter_full": article["chapter_full"] or "",
                "article": article["article"],
                "article_full": article["article_full"] or "",
                "chunk_size": article["size"],
                "has_table": has_table,
                "source_format": "pymupdf4llm",
            },
        }

        # Create child chunks. Every article MUST yield ≥1 child: search runs
        # on children only (parents are excluded from results by the
        # `must_not level=parent` filter and skipped by ES), so a parent
        # without any child would be unreachable. This mirrors
        # RecursiveChunker / ArticleLevelLegalChunker.
        child_chunks: List[Dict] = []

        if article["size"] > self.split_threshold:
            # Large article - split into multiple children
            if has_table:
                child_chunks = self._split_with_table_protection(
                    content, article
                )
            else:
                child_chunks = self._split_article_into_children(
                    content, article
                )
        else:
            # Small/medium article - 1 child = whole article. child==parent
            # content is intended: search hits the child, then expands to the
            # parent for broader context.
            child_chunks = [
                {
                    "content": content,
                    "metadata": {
                        "doc_type": "legal_document",
                        "level": "child",
                        "chapter": article["chapter"],
                        "chapter_full": article["chapter_full"] or "",
                        "article": article["article"],
                        "article_full": article["article_full"] or "",
                        "chunk_size": article["size"],
                        "has_table": has_table,
                        "source_format": "pymupdf4llm",
                    },
                }
            ]

        return parent_chunk, child_chunks

    def _split_article_into_children(
        self, content: str, article: Dict
    ) -> List[Dict]:
        """Split article into child chunks by numbered sections"""
        lines = content.split("\n")

        # Find article title line
        title_line = None
        content_start = 0
        for i, line in enumerate(lines):
            cleaned = line.strip().strip("*").strip()
            if "Điều" in cleaned and re.match(r"^Điều\s+\d+", cleaned):
                title_line = line
                content_start = i + 1
                break

        # Split by numbered sections (1. 2. 3.)
        sections = []
        current_section = []

        for line in lines[content_start:]:
            stripped = line.strip()

            # Check if new numbered section starts
            if self._is_numbered_point(stripped):
                if current_section:
                    sections.append("\n".join(current_section))
                current_section = [line]
            else:
                current_section.append(line)

        if current_section:
            sections.append("\n".join(current_section))

        # Group sections into chunks
        child_chunks = []
        current_chunk = []
        current_size = 0

        chapter_overhead = len(article.get("chapter_full") or "") + 4

        for section in sections:
            section_size = len(section)

            if (
                current_size + section_size + chapter_overhead
                > self.max_child_size
                and current_chunk
            ):
                chunk_content = self._build_child_content(
                    title_line, "\n".join(current_chunk), article
                )
                child_chunks.append(
                    self._create_child_chunk(chunk_content, article)
                )

                # FIX: Proper overlap - only overlap last N characters, not entire section
                if self.chunk_overlap > 0 and current_chunk:
                    # Get last overlap_size chars from previous chunk
                    last_content = "\n".join(current_chunk)
                    if len(last_content) > self.chunk_overlap:
                        overlap_text = last_content[-self.chunk_overlap :]
                        # Start new chunk with overlap + new section
                        current_chunk = [overlap_text, section]
                        current_size = self.chunk_overlap + section_size
                    else:
                        # Previous chunk smaller than overlap - keep it all
                        current_chunk = [current_chunk[-1], section]
                        current_size = len(current_chunk[-1]) + section_size
                else:
                    current_chunk = [section]
                    current_size = section_size
            else:
                current_chunk.append(section)
                current_size += section_size

        if current_chunk:
            chunk_content = self._build_child_content(
                title_line, "\n".join(current_chunk), article
            )
            child_chunks.append(
                self._create_child_chunk(chunk_content, article)
            )

        return child_chunks

    def _split_with_table_protection(
        self, content: str, article: Dict
    ) -> List[Dict]:
        """Split article but keep tables intact"""
        parts, tables = self._extract_tables(content)

        if article["size"] <= self.max_child_size * 1.5:
            return [
                {
                    "content": content,
                    "metadata": {
                        "doc_type": "legal_document",
                        "level": "child",
                        "chapter": article["chapter"],
                        "chapter_full": article["chapter_full"] or "",
                        "article": article["article"],
                        "article_full": article["article_full"] or "",
                        "chunk_size": article["size"],
                        "has_table": True,
                        "source_format": "pymupdf4llm",
                    },
                }
            ]

        child_chunks = []

        # Get article title
        lines = content.split("\n")
        title_line = None
        for line in lines:
            cleaned = line.strip().strip("*").strip()
            if "Điều" in cleaned and re.match(r"^Điều\s+\d+", cleaned):
                title_line = line
                break

        # Split non-table parts
        for part in parts:
            if len(part.strip()) < 50:
                continue

            part_chunks = self._split_article_into_children(
                f"{title_line}\n\n{part}" if title_line else part, article
            )
            child_chunks.extend(part_chunks)

        # Add table chunks
        for table in tables:
            table_content = f"{title_line}\n\n{table}" if title_line else table
            child_chunks.append(
                {
                    "content": table_content,
                    "metadata": {
                        "doc_type": "legal_document",
                        "level": "child",
                        "chapter": article["chapter"],
                        "chapter_full": article["chapter_full"] or "",
                        "article": article["article"],
                        "article_full": article["article_full"] or "",
                        "chunk_size": len(table_content),
                        "has_table": True,
                        "is_table_chunk": True,
                        "source_format": "pymupdf4llm",
                    },
                }
            )

        return (
            child_chunks
            if child_chunks
            else [
                {
                    "content": content,
                    "metadata": {
                        "doc_type": "legal_document",
                        "level": "child",
                        "chapter": article["chapter"],
                        "chapter_full": article["chapter_full"] or "",
                        "article": article["article"],
                        "article_full": article["article_full"] or "",
                        "chunk_size": article["size"],
                        "has_table": True,
                        "source_format": "pymupdf4llm",
                    },
                }
            ]
        )

    def _build_child_content(
        self, title: str, sections: str, article: Dict
    ) -> str:
        """Build child chunk content with proper context"""
        parts = []

        if title:
            parts.append(title)

        parts.append(sections)

        return "\n\n".join(parts)

    def _create_child_chunk(self, content: str, article: Dict) -> Dict:
        """Create a child chunk dictionary"""
        return {
            "content": content,
            "metadata": {
                "doc_type": "legal_document",
                "level": "child",
                "chapter": article["chapter"],
                "chapter_full": article["chapter_full"] or "",
                "article": article["article"],
                "article_full": article["article_full"] or "",
                "chunk_size": len(content),
                "source_format": "pymupdf4llm",
            },
        }

    # ========================================================================
    # POST-PROCESSING
    # ========================================================================

    def _parent_key(self, meta: Dict, idx: int) -> str:
        """Build the chapter/article key used to match a child to its parent."""
        id_parts = []
        if meta.get("chapter"):
            id_parts.append(f"c{meta['chapter']}")
        if meta.get("article"):
            article_num = re.search(r"\d+", meta["article"])
            if article_num:
                id_parts.append(f"a{article_num.group()}")
        return "_".join(id_parts) if id_parts else f"parent_{idx}"

    def add_chunk_ids(self, chunks: List[Dict]) -> List[Dict]:
        """Assign IDs and wire parent-child links.

        Emits the SAME schema as ``RecursiveChunker`` so the indexing pipeline
        (``document_pipeline.embed_and_index``) can link children to parents
        and ``ParentContextExpander`` can fetch parent context:
        - every chunk gets a stable uuid ``id``
        - parent/header → ``metadata.parent_id = None``
        - child → ``metadata.parent_id`` = the parent's uuid ``id``

        ``readable_id``/``chunk_id`` are kept for debugging only; the pipeline
        keys off ``id`` and ``metadata.parent_id``.
        """
        parent_id_by_key: Dict[str, str] = {}  # parent_key → parent uuid id
        parent_chunk_by_key: Dict[str, Dict] = {}  # parent_key → parent chunk
        child_counter: Dict[str, int] = {}

        for idx, chunk in enumerate(chunks):
            chunk["id"] = str(uuid.uuid4())
            chunk["chunk_id"] = idx

            meta = chunk["metadata"]
            level = meta.get("level")

            if level == "header":
                chunk["readable_id"] = "header"
                meta["parent_id"] = None

            elif level == "parent":
                key = self._parent_key(meta, idx)
                chunk["readable_id"] = f"parent_{key}"
                meta["parent_id"] = None
                meta["child_count"] = 0
                parent_id_by_key[key] = chunk["id"]
                parent_chunk_by_key[key] = chunk
                child_counter[key] = 0

            elif level == "child":
                key = self._parent_key(meta, idx)
                child_num = child_counter.get(key, 0)
                child_counter[key] = child_num + 1
                chunk["readable_id"] = f"child_{key}_c{child_num}"
                # Link to the parent uuid emitted above. None when no matching
                # parent exists — the child stays indexable, just without
                # parent-context expansion (mirrors RecursiveChunker orphans).
                meta["parent_id"] = parent_id_by_key.get(key)
                parent = parent_chunk_by_key.get(key)
                if parent is not None:
                    parent["metadata"]["child_count"] = (
                        parent["metadata"].get("child_count", 0) + 1
                    )

        return chunks

    def validate_chunks(self, chunks: List[Dict]) -> Dict:
        """Validate and generate statistics"""
        if not chunks:
            return {"total_chunks": 0, "error": "No chunks generated"}

        stats = {
            "total_chunks": len(chunks),
            "total_chars": sum(c["metadata"]["chunk_size"] for c in chunks),
            "avg_chunk_size": sum(c["metadata"]["chunk_size"] for c in chunks)
            / len(chunks),
            "min_chunk_size": min(c["metadata"]["chunk_size"] for c in chunks),
            "max_chunk_size": max(c["metadata"]["chunk_size"] for c in chunks),
            "source_format": "pymupdf4llm",
        }

        # Count by level
        levels = {}
        for chunk in chunks:
            level = chunk["metadata"].get("level", "unknown")
            levels[level] = levels.get(level, 0) + 1
        stats["by_level"] = levels

        # Parent-child relationships
        parents = [c for c in chunks if c["metadata"].get("level") == "parent"]
        children = [c for c in chunks if c["metadata"].get("level") == "child"]
        stats["parent_chunks"] = len(parents)
        stats["child_chunks"] = len(children)

        # Tables
        stats["chunks_with_tables"] = sum(
            1 for c in chunks if c["metadata"].get("has_table")
        )

        # Size distribution
        stats["size_distribution"] = {
            "0-500": sum(
                1 for c in chunks if c["metadata"]["chunk_size"] < 500
            ),
            "500-1000": sum(
                1 for c in chunks if 500 <= c["metadata"]["chunk_size"] < 1000
            ),
            "1000-2000": sum(
                1 for c in chunks if 1000 <= c["metadata"]["chunk_size"] < 2000
            ),
            "2000-3000": sum(
                1 for c in chunks if 2000 <= c["metadata"]["chunk_size"] < 3000
            ),
            "3000+": sum(
                1 for c in chunks if c["metadata"]["chunk_size"] >= 3000
            ),
        }

        return stats

    # ========================================================================
    # MAIN PIPELINE
    # ========================================================================

    def chunk_document(self, text: str) -> tuple[List[Dict], Dict]:
        """
        Complete chunking pipeline
        Returns: (chunks, statistics)
        """
        chunks = self.parse(text)
        chunks = self.add_chunk_ids(chunks)
        stats = self.validate_chunks(chunks)

        return chunks, stats

    def save_chunks(self, chunks: List[Dict], output_path: str):
        """Save chunks to JSON file"""
        import json
        from pathlib import Path

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(chunks, f, ensure_ascii=False, indent=2)

        print(f"💾 Đã lưu {len(chunks)} chunks vào: {output_path}")
