from typing import List, Dict
from .base_chunker import DocumentChunker
import re


# =============================================================================
# HIERARCHICAL CHUNKER: For structured legal documents
# =============================================================================
class HierarchicalLegalChunker(DocumentChunker):
    """
    Chunker for legal documents with hierarchical structure:
    Title -> Chapter -> Article -> Clause -> SubClause
    """

    def __init__(self, chunk_size: int = 1200, chunk_overlap: int = 200):
        super().__init__(chunk_size, chunk_overlap)
        self.reset_state()

    def reset_state(self):
        """Reset tracking state"""
        self.current_title = None
        self.current_chapter = None
        self.current_chapter_full = None
        self.current_article = None
        self.current_article_full = None
        self.current_clause_num = None
        self.current_clause_lines = []
        self.current_depth = 0
        self.chunks = []

    def parse(self, text: str) -> List[Dict]:
        """Parse legal document structure"""
        self.reset_state()
        lines = text.split("\n")

        for line in lines:
            line_stripped = line.strip()

            if not line_stripped:
                continue

            # Detect different levels of hierarchy
            if self._is_title(line_stripped):
                self._handle_title(line_stripped)
            elif self._is_chapter(line_stripped):
                self._handle_chapter(line_stripped)
            elif self._is_article(line_stripped):
                self._handle_article(line_stripped)
            elif self._is_clause(line_stripped):
                self._handle_clause(line_stripped)
            elif self._is_subclause(line_stripped):
                self._handle_subclause(line_stripped)
            elif self._is_table_line(line_stripped):
                self._handle_table_line(line_stripped)
            else:
                self._handle_content_line(line_stripped)

        # Save last clause
        self._save_current_clause()

        return self.chunks

    def _is_title(self, line: str) -> bool:
        """Detect title (## but not ## Điều)"""
        return line.startswith("## ") and not line.startswith("## Điều")

    def _is_chapter(self, line: str) -> bool:
        """Detect chapter (# CHƯƠNG)"""
        return (line.startswith("## ") and not line.startswith("## Điều")) or (
            line.startswith("## CHƯƠNG")
        )

    def _is_article(self, line: str) -> bool:
        """Detect article (## Điều)"""
        return re.match(r"^##\s+Điều", line) is not None

    def _is_clause(self, line: str) -> bool:
        """Detect main clause (1., 2., 3., ...)"""
        return re.match(r"^(\d+)\.\s+", line) is not None

    def _is_subclause(self, line: str) -> bool:
        """Detect sub-clause (a), b), c), ...)"""
        return re.match(r"^[-–]?\s*([a-z][\))])\s+", line) is not None

    def _is_table_line(self, line: str) -> bool:
        """Detect table line"""
        return line.startswith("|") or "---" in line

    def _handle_title(self, line: str):
        """Handle title detection"""
        self._save_current_clause()
        self.current_title = line.replace("##", "").strip()
        self.current_depth = 0

    def _handle_chapter(self, line: str):
        """Handle chapter detection"""
        self._save_current_clause()
        self.current_chapter_full = line.replace("#", "").strip()

        chapter_match = re.search(
            r"CHƯƠNG\s+([IVX]+|\d+)", self.current_chapter_full
        )
        self.current_chapter = (
            chapter_match.group(1)
            if chapter_match
            else self.current_chapter_full
        )
        self.current_article = None
        self.current_article_full = None
        self.current_depth = 0

    def _handle_article(self, line: str):
        """Handle article detection"""
        self._save_current_clause()
        self.current_article_full = line.replace("##", "").strip()

        article_match = re.match(r"(Điều\s+\d+)", self.current_article_full)
        self.current_article = (
            article_match.group(1)
            if article_match
            else self.current_article_full
        )
        self.current_depth = 0

    def _handle_clause(self, line: str):
        """Handle clause detection"""
        clause_match = re.match(r"^(\d+)\.\s+", line)
        if clause_match:
            self._save_current_clause()
            self.current_clause_num = clause_match.group(1)
            self.current_clause_lines = [line]
            self.current_depth = 0

    def _handle_subclause(self, line: str):
        """Handle sub-clause detection"""
        if self.current_clause_num is not None:
            self.current_clause_lines.append(line)
            self.current_depth = 1

    def _handle_table_line(self, line: str):
        """Handle table line"""
        if self.current_clause_num is not None:
            self.current_clause_lines.append(line)

    def _handle_content_line(self, line: str):
        """Handle regular content continuation"""
        if self.current_clause_num is not None and line:
            self.current_clause_lines.append(line)

    def _save_current_clause(self):
        """Save current clause to chunks"""
        if not self.current_clause_lines:
            return

        content = "\n".join(self.current_clause_lines).strip()
        if not content:
            return

        # Build metadata
        metadata = {
            "doc_type": "legal_document",
            "level": "clause",
            "title": self.current_title,
            "chapter": self.current_chapter,
            "chapter_full": self.current_chapter_full,
            "article": self.current_article,
            "article_full": self.current_article_full,
            "clause": self.current_clause_num,
            "chunk_size": len(content),
        }

        # Build hierarchy path
        hierarchy_parts = []
        if self.current_chapter:
            hierarchy_parts.append(self.current_chapter)
        if self.current_article:
            hierarchy_parts.append(self.current_article)
        if self.current_clause_num:
            hierarchy_parts.append(f"Khoản {self.current_clause_num}")

        metadata["hierarchy_path"] = " > ".join(hierarchy_parts)

        self.chunks.append({"content": content, "metadata": metadata})

        # Reset clause state
        self.current_clause_lines = []

    def post_process_chunks(self, chunks: List[Dict]) -> List[Dict]:
        """Handle articles without clauses"""
        return self._handle_articles_without_clauses(chunks)

    def _handle_articles_without_clauses(
        self, chunks: List[Dict]
    ) -> List[Dict]:
        """Handle articles that don't have explicit clauses"""
        # Group chunks by article
        articles = {}
        for chunk in chunks:
            article = chunk["metadata"].get("article")
            if article:
                if article not in articles:
                    articles[article] = []
                articles[article].append(chunk)

        # Future enhancement: handle single-paragraph articles
        return chunks

    def split_oversized_chunks(self, chunks: List[Dict]) -> List[Dict]:
        """Split chunks exceeding size limit"""
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=len,
            separators=[
                "\n\n",
                "\n",
                "(?<=\\.)\\s+(?=[a-z])",
                "(?<=,)\\s+",
                " ",
                "",
            ],
        )

        final_chunks = []

        for idx, chunk in enumerate(chunks):
            content = chunk["content"]
            metadata = chunk["metadata"]

            # Don't split tables
            if metadata.get("has_table"):
                final_chunks.append(chunk)
                continue

            # Split if too large
            if len(content) > self.chunk_size * 1.5:
                sub_contents = text_splitter.split_text(content)

                for sub_idx, sub_content in enumerate(sub_contents):
                    if len(sub_content.strip()) < 50:
                        continue

                    sub_chunk = {
                        "content": sub_content,
                        "metadata": {
                            **metadata,
                            "is_split": True,
                            "parent_chunk_id": idx,
                            "sub_chunk_index": sub_idx,
                            "total_sub_chunks": len(sub_contents),
                            "chunk_size": len(sub_content),
                        },
                    }
                    final_chunks.append(sub_chunk)
            else:
                chunk["metadata"]["is_split"] = False
                final_chunks.append(chunk)

        return final_chunks

    def add_chunk_ids(self, chunks: List[Dict]) -> List[Dict]:
        """Add chunk IDs with readable hierarchy-based IDs"""
        chunks = super().add_chunk_ids(chunks)

        for chunk in chunks:
            meta = chunk["metadata"]
            id_parts = []

            if meta.get("chapter"):
                id_parts.append(f"c{meta['chapter']}")

            if meta.get("article"):
                article_num = re.search(r"\d+", meta["article"])
                if article_num:
                    id_parts.append(f"a{article_num.group()}")

            if meta.get("clause"):
                id_parts.append(f"cl{meta['clause']}")

            if id_parts:
                chunk["readable_id"] = "_".join(id_parts)

        return chunks

    def validate_chunks(self, chunks: List[Dict]) -> Dict:
        """Enhanced validation with legal document specifics"""
        stats = super().validate_chunks(chunks)

        if stats["total_chunks"] == 0:
            return stats

        # Count by level
        levels = {}
        for chunk in chunks:
            level = chunk["metadata"].get("level", "unknown")
            levels[level] = levels.get(level, 0) + 1

        stats["levels"] = levels

        # Count special features
        stats["chunks_with_tables"] = sum(
            1 for c in chunks if c["metadata"].get("has_table")
        )
        stats["chunks_with_lists"] = sum(
            1 for c in chunks if c["metadata"].get("has_list")
        )
        stats["split_chunks"] = sum(
            1 for c in chunks if c["metadata"].get("is_split")
        )

        # Size distribution
        ranges = {
            "50-200": sum(
                1 for c in chunks if 50 <= c["metadata"]["chunk_size"] < 200
            ),
            "200-500": sum(
                1 for c in chunks if 200 <= c["metadata"]["chunk_size"] < 500
            ),
            "500-1000": sum(
                1 for c in chunks if 500 <= c["metadata"]["chunk_size"] < 1000
            ),
            "1000-1500": sum(
                1 for c in chunks if 1000 <= c["metadata"]["chunk_size"] < 1500
            ),
            ">1500": sum(
                1 for c in chunks if c["metadata"]["chunk_size"] >= 1500
            ),
        }
        stats["size_distribution"] = ranges

        return stats
