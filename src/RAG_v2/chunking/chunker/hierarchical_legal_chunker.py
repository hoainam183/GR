from typing import List, Dict, Optional
import re
from langchain_text_splitters import RecursiveCharacterTextSplitter


class ArticleLevelLegalChunker:
    """
    Chunker for Vietnamese legal documents with Parent-Child architecture.
    Strategy:
    - 1 chunk for entire header
    - Parent: 1 điều (hoặc nhiều điều nhỏ merged)
    - Children: Các khoản trong điều, hoặc điều nhỏ merged (~500-1000 chars)
    - Chapter context in every chunk
    - Table protection
    """

    def __init__(
        self,
        min_child_size: int = 500,
        max_child_size: int = 1000,
        parent_size_limit: int = 4000,
        chunk_overlap: int = 150,
    ):
        self.min_child_size = min_child_size
        self.max_child_size = max_child_size
        self.parent_size_limit = parent_size_limit
        self.chunk_overlap = chunk_overlap
        self.reset_state()

    def reset_state(self):
        """Reset all tracking state"""
        self.current_chapter = None
        self.current_chapter_full = None
        self.current_chapter_intro = []  # Lines before first article in chapter
        self.current_article = None
        self.current_article_full = None
        self.current_article_lines = []
        self.articles = []  # Store all parsed articles
        self.chunks = []  # Final output chunks
        self.parsing_phase = "header"  # "header" or "body"

    def parse(self, text: str) -> List[Dict]:
        """Main parsing function"""
        self.reset_state()

        lines = text.split("\n")
        header_lines = []

        for line in lines:
            line_stripped = line.strip()

            # Skip empty lines
            if not line_stripped:
                continue

            # === HEADER PHASE ===
            if self.parsing_phase == "header":
                # Check if we're entering body (first Chapter or Article)
                if self._is_chapter(line_stripped) or self._is_article(
                    line_stripped
                ):
                    # Save header chunk
                    if header_lines:
                        self._save_header_chunk(header_lines)
                    self.parsing_phase = "body"
                    # Fall through to process this line as body
                else:
                    header_lines.append(line_stripped)
                    continue

            # === BODY PHASE ===
            if self._is_chapter(line_stripped):
                self._handle_chapter(line_stripped)
            elif self._is_article(line_stripped):
                self._handle_article(line_stripped)
            else:
                # Regular content line
                self._handle_content_line(line_stripped)

        # Save last article
        self._save_current_article()

        # Create parent-child chunks from articles
        self._create_parent_child_chunks()

        return self.chunks

    # ========================================================================
    # DETECTION METHODS
    # ========================================================================

    def _is_chapter(self, line: str) -> bool:
        """Detect chapter heading"""
        # Matches: "# CHƯƠNG I", "## CHƯƠNG I", "CHƯƠNG I"
        return bool(re.match(r"^#*\s*CHƯƠNG\s+[IVX\d]+", line))

    def _is_article(self, line: str) -> bool:
        """Detect article heading"""
        # Matches: "## Điều 1", "Điều 1. Title"
        return bool(re.match(r"^##?\s*Điều\s+\d+", line))

    # ========================================================================
    # HANDLER METHODS
    # ========================================================================

    def _handle_chapter(self, line: str):
        """Handle chapter detection - keep chapter for all articles"""
        # Save previous article before starting new chapter
        self._save_current_article()

        # Extract chapter info
        self.current_chapter_full = line.replace("#", "").strip()
        chapter_match = re.search(
            r"CHƯƠNG\s+([IVX]+|\d+)", self.current_chapter_full
        )
        self.current_chapter = chapter_match.group(1) if chapter_match else None

        # Keep chapter intro for ALL articles in this chapter
        self.current_chapter_intro = [self.current_chapter_full]

    def _handle_article(self, line: str):
        """Handle article detection - always include chapter context"""
        # Save previous article
        self._save_current_article()

        # Extract article info
        self.current_article_full = line.replace("#", "").strip()
        article_match = re.match(r"Điều\s+(\d+)", self.current_article_full)
        self.current_article = (
            f"Điều {article_match.group(1)}" if article_match else None
        )

        # Start new article with chapter context
        self.current_article_lines = []

        # ALWAYS add chapter intro if we're in a chapter
        if self.current_chapter_intro:
            self.current_article_lines.extend(self.current_chapter_intro)
            self.current_article_lines.append("")  # Empty line separator
            # DON'T clear - keep for next articles too!

        self.current_article_lines.append(self.current_article_full)

    def _handle_content_line(self, line: str):
        """Handle regular content lines"""
        if self.current_article is not None:
            # We're inside an article - add to article buffer
            self.current_article_lines.append(line)
        elif self.current_chapter is not None:
            # We're in a chapter but before first article - chapter intro
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
        }

        self.chunks.append({"content": content, "metadata": metadata})

    def _save_current_article(self):
        """Save current article to articles list (not creating chunks yet)"""
        if not self.current_article_lines:
            return

        content = "\n".join(self.current_article_lines).strip()

        if not content:
            return

        # Store article with metadata
        article_data = {
            "content": content,
            "chapter": self.current_chapter,
            "chapter_full": self.current_chapter_full,
            "article": self.current_article,
            "article_full": self.current_article_full,
            "size": len(content),
        }

        self.articles.append(article_data)

        # Reset article state
        self.current_article_lines = []

    # ========================================================================
    # TABLE DETECTION
    # ========================================================================

    def _has_table(self, text: str) -> bool:
        """Detect markdown table"""
        lines = text.split("\n")
        table_lines = [line for line in lines if "|" in line]
        return len(table_lines) >= 2  # At least header + 1 row

    def _extract_tables(self, text: str) -> tuple[List[str], List[str]]:
        """Split text into table and non-table parts"""
        lines = text.split("\n")
        parts = []
        tables = []
        current_part = []
        current_table = []  # ⚠️ Missing initialization
        in_table = False

        for line in lines:
            if "|" in line:
                if not in_table:
                    # Start of table
                    if current_part:
                        parts.append("\n".join(current_part))
                        current_part = []
                    in_table = True
                    current_table = [line]  # ✅ Initialize here
                else:
                    current_table.append(line)
            else:
                if in_table:
                    # End of table
                    tables.append("\n".join(current_table))
                    in_table = False
                    current_table = []  # ✅ Reset
                current_part.append(line)

        # Handle remaining
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

            # Add parent
            self.chunks.append(parent_chunk)

            # Add children
            self.chunks.extend(child_chunks)

    def _process_article(self, article: Dict) -> tuple[Dict, List[Dict]]:
        """Process one article into parent + children chunks"""
        content = article["content"]

        # Check if article has table
        has_table = self._has_table(content)

        # Create parent chunk (full article)
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
            },
        }

        # Create child chunks
        child_chunks = []

        if article["size"] <= self.max_child_size:
            # Small article - create 1 child = whole article
            child_chunks.append(
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
                    },
                }
            )
        else:
            # Large article - split into sections
            if has_table:
                # Protect table - split around it
                child_chunks = self._split_with_table_protection(
                    content, article
                )
            else:
                # Normal split
                child_chunks = self._split_article_into_children(
                    content, article
                )

        return parent_chunk, child_chunks

    def _split_article_into_children(
        self, content: str, article: Dict
    ) -> List[Dict]:
        """Split article into child chunks by sections"""
        lines = content.split("\n")

        # Find article title line
        title_line = None
        content_start = 0
        for i, line in enumerate(lines):
            if "Điều" in line and re.match(r"^.*Điều\s+\d+", line):
                title_line = line
                content_start = i + 1
                break

        # Split by numbered sections (1. 2. 3. etc.)
        sections = []
        current_section = []

        for line in lines[content_start:]:
            # Check if new section starts
            if re.match(r"^\d+\.", line.strip()):
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

        # Include chapter context in size calculation
        chapter_overhead = (
            len(article.get("chapter_full") or "") + 4
        )  # +4 for newlines

        for section in sections:
            section_size = len(section)

            # Check if adding this section exceeds max size
            if (
                current_size + section_size + chapter_overhead
                > self.max_child_size
                and current_chunk
            ):
                # Save current chunk
                chunk_content = self._build_child_content(
                    title_line, "\n".join(current_chunk), article
                )
                child_chunks.append(
                    self._create_child_chunk(chunk_content, article)
                )

                # Start new chunk with overlap (last section)
                if self.chunk_overlap > 0:
                    current_chunk = [current_chunk[-1], section]
                    current_size = len(current_chunk[-1]) + section_size
                else:
                    current_chunk = [section]
                    current_size = section_size
            else:
                current_chunk.append(section)
                current_size += section_size

        # Save last chunk
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

        child_chunks = []

        # Strategy: Keep table with minimal surrounding context
        # If article too large, split non-table parts

        if (
            article["size"] <= self.max_child_size * 1.5
        ):  # Allow 50% overflow for tables
            # Article not too large - keep as single child
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
                    },
                }
            ]

        # Article too large - need to split
        # Keep table in one chunk, split other parts

        # Get article title
        lines = content.split("\n")
        title_line = None
        for line in lines:
            if "Điều" in line and re.match(r"^.*Điều\s+\d+", line):
                title_line = line
                break

        # Split non-table parts normally
        for i, part in enumerate(parts):
            if len(part.strip()) < 50:  # Skip very short parts
                continue

            part_chunks = self._split_article_into_children(
                f"{title_line}\n\n{part}" if title_line else part, article
            )
            child_chunks.extend(part_chunks)

        # Add table chunks (each table as separate child)
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
                        "is_table_chunk": True,  # Flag for table chunks
                    },
                }
            )

        return (
            child_chunks
            if child_chunks
            else [
                # Fallback: if splitting failed, keep as one child
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
                    },
                }
            ]
        )

    def _build_child_content(
        self, title: str, sections: str, article: Dict
    ) -> str:
        """Build child chunk content with proper context"""
        parts = []

        # Always include chapter if available
        # (Already in content from _handle_article, but ensure consistency)

        # Add article title
        if title:
            parts.append(title)

        # Add sections
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
            },
        }

    # ========================================================================
    # POST-PROCESSING
    # ========================================================================

    def add_chunk_ids(self, chunks: List[Dict]) -> List[Dict]:
        """Add sequential and readable IDs to chunks with parent-child tracking"""
        parent_counter = {}
        child_counter = {}

        for idx, chunk in enumerate(chunks):
            chunk["chunk_id"] = idx

            meta = chunk["metadata"]
            level = meta.get("level")

            if level == "header":
                chunk["readable_id"] = "header"
                chunk["parent_id"] = None

            elif level == "parent":
                # Parent chunk ID
                id_parts = []
                if meta.get("chapter"):
                    id_parts.append(f"c{meta['chapter']}")
                if meta.get("article"):
                    article_num = re.search(r"\d+", meta["article"])
                    if article_num:
                        id_parts.append(f"a{article_num.group()}")

                parent_id = "_".join(id_parts) if id_parts else f"parent_{idx}"
                chunk["readable_id"] = f"parent_{parent_id}"
                chunk["parent_id"] = None

                # Track for children
                parent_counter[parent_id] = chunk["readable_id"]
                child_counter[parent_id] = 0

            elif level == "child":
                # Child chunk ID
                id_parts = []
                if meta.get("chapter"):
                    id_parts.append(f"c{meta['chapter']}")
                if meta.get("article"):
                    article_num = re.search(r"\d+", meta["article"])
                    if article_num:
                        id_parts.append(f"a{article_num.group()}")

                parent_key = "_".join(id_parts) if id_parts else f"parent_{idx}"

                # Get parent_id
                parent_id = parent_counter.get(
                    parent_key, f"parent_{parent_key}"
                )

                # Increment child counter
                child_num = child_counter.get(parent_key, 0)
                child_counter[parent_key] = child_num + 1

                chunk["readable_id"] = f"child_{parent_key}_c{child_num}"
                chunk["parent_id"] = parent_id

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
        }

        # Count by level
        levels = {}
        for chunk in chunks:
            level = chunk["metadata"].get("level", "unknown")
            levels[level] = levels.get(level, 0) + 1
        stats["by_level"] = levels

        # Count parent-child relationships
        parents = [c for c in chunks if c["metadata"].get("level") == "parent"]
        children = [c for c in chunks if c["metadata"].get("level") == "child"]
        stats["parent_chunks"] = len(parents)
        stats["child_chunks"] = len(children)

        # Articles with tables
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
        # Parse document
        chunks = self.parse(text)

        # Add IDs
        chunks = self.add_chunk_ids(chunks)

        # Validate
        stats = self.validate_chunks(chunks)

        return chunks, stats

    def save_chunks(self, chunks: List[Dict], output_path: str):
        """Save chunks to JSON file"""
        import json
        from pathlib import Path

        # Ensure output directory exists
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Save chunks
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(chunks, f, ensure_ascii=False, indent=2)

        print(f"💾 Đã lưu {len(chunks)} chunks vào: {output_path}")
