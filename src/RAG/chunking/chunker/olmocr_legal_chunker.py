"""
OLM OCR Legal Document Chunker
Chunker cho văn bản pháp quy từ OLM OCR (không có markdown heading)

Đặc điểm OLM OCR output:
- Không có markdown heading (#, ##)
- "CHƯƠNG", "Điều" xuất hiện dưới dạng text thuần
- Bảng markdown vẫn được giữ với format |...|
- Có thể có PHỤ LỤC ở cuối văn bản

Fallback:
- Nếu file không có cấu trúc Điều/Chương → sử dụng RecursiveCharacterTextSplitter
"""

from typing import List, Dict, Optional, Tuple
import re
from dataclasses import dataclass, field
from enum import Enum
from langchain_text_splitters import RecursiveCharacterTextSplitter


class ChunkLevel(Enum):
    HEADER = "header"
    PARENT = "parent"
    CHILD = "child"
    APPENDIX = "appendix"  # Phụ lục
    RECURSIVE = (
        "recursive"  # Fallback chunks from RecursiveCharacterTextSplitter
    )


@dataclass
class DocumentMetadata:
    """Metadata trích xuất từ header văn bản"""

    doc_number: Optional[str] = None
    doc_date: Optional[str] = None
    doc_title: Optional[str] = None
    doc_type: str = "quy_dinh"  # quy_che, quy_dinh, huong_dan, quyet_dinh
    issuing_authority: Optional[str] = None


@dataclass
class ChunkData:
    """Data structure cho mỗi chunk"""

    content: str
    level: ChunkLevel
    chapter: Optional[str] = None
    chapter_title: Optional[str] = None
    article: Optional[str] = None
    article_title: Optional[str] = None
    clause: Optional[str] = None  # Khoản
    has_table: bool = False
    is_appendix: bool = False
    appendix_number: Optional[str] = None
    chunk_id: Optional[int] = None
    readable_id: Optional[str] = None
    parent_id: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "content": self.content,
            "metadata": {
                "level": self.level.value,
                "chapter": self.chapter,
                "chapter_title": self.chapter_title or "",
                "article": self.article,
                "article_title": self.article_title or "",
                "clause": self.clause,
                "has_table": self.has_table,
                "is_appendix": self.is_appendix,
                "appendix_number": self.appendix_number,
                "chunk_size": len(self.content),
            },
            "chunk_id": self.chunk_id,
            "readable_id": self.readable_id,
            "parent_id": self.parent_id,
        }


class OlmOcrLegalChunker:
    """
    Chunker for Vietnamese legal documents from OLM OCR.

    Strategy:
    - Header: Phần đầu văn bản (Quyết định, căn cứ pháp lý)
    - Parent: 1 Điều đầy đủ + context Chương
    - Children: Các khoản trong Điều (~300-1000 chars)
    - Appendix: Các phụ lục (bảng, danh mục)

    Đặc điểm:
    - Không dựa vào markdown heading (#)
    - Detect "CHƯƠNG", "Điều" trong text thuần
    - Bảo vệ bảng markdown
    - Xử lý Phụ lục riêng
    """

    def __init__(
        self,
        min_child_size: int = 300,
        max_child_size: int = 1000,
        parent_size_limit: int = 4000,
        chunk_overlap: int = 100,
        fallback_chunk_size: int = 1000,
        fallback_chunk_overlap: int = 200,
    ):
        self.min_child_size = min_child_size
        self.max_child_size = max_child_size
        self.parent_size_limit = parent_size_limit
        self.chunk_overlap = chunk_overlap

        # Fallback settings for RecursiveCharacterTextSplitter
        self.fallback_chunk_size = fallback_chunk_size
        self.fallback_chunk_overlap = fallback_chunk_overlap

        # Regex patterns cho OLM OCR (không có #)
        self.patterns = {
            # CHƯƠNG I, CHƯƠNG II, Chương 1
            "chapter": re.compile(
                r"^(CHƯƠNG|Chương)\s+([IVX]+|\d+)\.?\s*(.*)$", re.MULTILINE
            ),
            # Điều 1, Điều 1., Điều 1. Title
            "article": re.compile(r"^Điều\s+(\d+)\.?\s*(.*)$", re.MULTILINE),
            # 1. 2. 3. (Khoản)
            "clause": re.compile(r"^(\d+)\.\s+(.+)$"),
            # a) b) c) hoặc a. b. c. (Điểm)
            "point": re.compile(r"^([a-z])[.)]\s+(.+)$"),
            # PHỤ LỤC 1, Phụ lục I
            "appendix": re.compile(
                r"^(PHỤ LỤC|Phụ lục)\s*(\d+|[IVX]+)?\.?\s*(.*)$", re.MULTILINE
            ),
            # Số văn bản: Số: 5445 /QĐ-ĐHBK
            "doc_number": re.compile(r"Số:\s*(\d+\s*/[A-ZĐ\-]+)"),
            # Ngày: ngày 28 tháng 5 năm 2025
            "doc_date": re.compile(
                r"ngày\s+(\d+)\s+tháng\s+(\d+)\s+năm\s+(\d+)"
            ),
        }

        self.reset_state()

    def reset_state(self):
        """Reset all tracking state"""
        self.doc_metadata = DocumentMetadata()
        self.current_chapter: Optional[str] = None
        self.current_chapter_title: Optional[str] = None
        self.current_article: Optional[str] = None
        self.current_article_title: Optional[str] = None
        self.current_article_lines: List[str] = []

        self.articles: List[Dict] = []
        self.appendices: List[Dict] = []
        self.chunks: List[ChunkData] = []

        self.parsing_phase = "header"  # header, body, appendix
        self.in_appendix = False
        self.current_appendix_num: Optional[str] = None
        self.current_appendix_lines: List[str] = []

    # ========================================================================
    # DETECTION METHODS (cho OLM OCR - không có #)
    # ========================================================================

    def _is_chapter(self, line: str) -> bool:
        """Detect chapter heading - không có # prefix"""
        line = line.strip()
        return bool(self.patterns["chapter"].match(line))

    def _is_article(self, line: str) -> bool:
        """Detect article heading - Điều X"""
        line = line.strip()
        return bool(self.patterns["article"].match(line))

    def _is_appendix(self, line: str) -> bool:
        """Detect appendix - PHỤ LỤC"""
        line = line.strip()
        return bool(self.patterns["appendix"].match(line))

    def _is_clause(self, line: str) -> bool:
        """Detect clause - 1. 2. 3."""
        line = line.strip()
        return bool(self.patterns["clause"].match(line))

    def _is_table_line(self, line: str) -> bool:
        """Detect markdown table line"""
        return "|" in line

    def _has_table(self, text: str) -> bool:
        """Check if text contains markdown table"""
        lines = text.split("\n")
        table_lines = [l for l in lines if self._is_table_line(l)]
        return len(table_lines) >= 2

    def _is_header_end_marker(self, line: str) -> bool:
        """Check if line marks end of header section"""
        line = line.strip()
        # Các dấu hiệu kết thúc header
        markers = [
            "QUYẾT ĐỊNH:",
            "QUY ĐỊNH",
            "QUY CHẾ",
            "HƯỚNG DẪN",
        ]
        return any(line.startswith(m) for m in markers)

    # ========================================================================
    # EXTRACTION METHODS
    # ========================================================================

    def _extract_chapter_info(self, line: str) -> Tuple[str, str]:
        """Extract chapter number and title"""
        match = self.patterns["chapter"].match(line.strip())
        if match:
            chapter_num = match.group(2)
            chapter_title = match.group(3).strip() if match.group(3) else ""
            return chapter_num, chapter_title
        return "", ""

    def _extract_article_info(self, line: str) -> Tuple[str, str]:
        """Extract article number and title"""
        match = self.patterns["article"].match(line.strip())
        if match:
            article_num = match.group(1)
            article_title = match.group(2).strip() if match.group(2) else ""
            return article_num, article_title
        return "", ""

    def _extract_appendix_info(self, line: str) -> Tuple[str, str]:
        """Extract appendix number and title"""
        match = self.patterns["appendix"].match(line.strip())
        if match:
            appendix_num = match.group(2) or "1"
            appendix_title = match.group(3).strip() if match.group(3) else ""
            return appendix_num, appendix_title
        return "1", ""

    def _extract_doc_metadata(self, header_text: str) -> DocumentMetadata:
        """Extract document metadata from header"""
        metadata = DocumentMetadata()

        # Extract doc number
        num_match = self.patterns["doc_number"].search(header_text)
        if num_match:
            metadata.doc_number = num_match.group(1).replace(" ", "")

        # Extract date
        date_match = self.patterns["doc_date"].search(header_text)
        if date_match:
            day, month, year = date_match.groups()
            metadata.doc_date = f"{day}/{month}/{year}"

        # Detect doc type
        header_lower = header_text.lower()
        if "quy chế" in header_lower:
            metadata.doc_type = "quy_che"
        elif "quy định" in header_lower:
            metadata.doc_type = "quy_dinh"
        elif "hướng dẫn" in header_lower:
            metadata.doc_type = "huong_dan"
        elif "quyết định" in header_lower:
            metadata.doc_type = "quyet_dinh"

        # Extract title (line after QUYẾT ĐỊNH)
        lines = header_text.split("\n")
        for i, line in enumerate(lines):
            if "QUYẾT ĐỊNH" in line:
                # Next non-empty line is likely the title
                for j in range(i + 1, min(i + 5, len(lines))):
                    if lines[j].strip() and not lines[j].strip().startswith(
                        "GIÁM ĐỐC"
                    ):
                        metadata.doc_title = lines[j].strip()
                        break
                break

        return metadata

    # ========================================================================
    # TABLE HANDLING
    # ========================================================================

    def _extract_tables(self, text: str) -> Tuple[List[str], List[str]]:
        """Split text into non-table parts and table parts"""
        lines = text.split("\n")
        parts = []
        tables = []
        current_part = []
        current_table = []
        in_table = False

        for line in lines:
            if self._is_table_line(line):
                if not in_table:
                    # Start of table
                    if current_part:
                        parts.append("\n".join(current_part))
                        current_part = []
                    in_table = True
                    current_table = [line]
                else:
                    current_table.append(line)
            else:
                if in_table:
                    # End of table
                    tables.append("\n".join(current_table))
                    in_table = False
                    current_table = []
                current_part.append(line)

        # Handle remaining
        if in_table and current_table:
            tables.append("\n".join(current_table))
        if current_part:
            parts.append("\n".join(current_part))

        return parts, tables

    # ========================================================================
    # MAIN PARSING
    # ========================================================================

    def parse(self, text: str) -> List[Dict]:
        """Main parsing function"""
        self.reset_state()

        lines = text.split("\n")
        header_lines = []

        for i, line in enumerate(lines):
            line_stripped = line.strip()

            # Skip empty lines trong header phase
            if not line_stripped and self.parsing_phase == "header":
                continue

            # === HEADER PHASE ===
            if self.parsing_phase == "header":
                # Check if entering body (first Chapter or Article)
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

            # === CHECK FOR APPENDIX ===
            if self._is_appendix(line_stripped):
                # Save current article before appendix
                self._save_current_article()
                self._save_current_appendix()

                self.parsing_phase = "appendix"
                self.in_appendix = True

                appendix_num, appendix_title = self._extract_appendix_info(
                    line_stripped
                )
                self.current_appendix_num = appendix_num
                self.current_appendix_lines = [line_stripped]
                continue

            # === APPENDIX PHASE ===
            if self.parsing_phase == "appendix":
                self.current_appendix_lines.append(line)
                continue

            # === BODY PHASE ===
            if self._is_chapter(line_stripped):
                self._handle_chapter(line_stripped)
            elif self._is_article(line_stripped):
                self._handle_article(line_stripped)
            else:
                self._handle_content_line(line)

        # Save last article and appendix
        self._save_current_article()
        self._save_current_appendix()

        # Create chunks from articles
        self._create_parent_child_chunks()

        # Create appendix chunks
        self._create_appendix_chunks()

        # Add IDs
        self._add_chunk_ids()

        return [chunk.to_dict() for chunk in self.chunks]

    # ========================================================================
    # HANDLER METHODS
    # ========================================================================

    def _handle_chapter(self, line: str):
        """Handle chapter detection"""
        # Save previous article
        self._save_current_article()

        # Extract chapter info
        chapter_num, chapter_title = self._extract_chapter_info(line)
        self.current_chapter = chapter_num
        self.current_chapter_title = f"CHƯƠNG {chapter_num}" + (
            f" {chapter_title}" if chapter_title else ""
        )

    def _handle_article(self, line: str):
        """Handle article detection"""
        # Save previous article
        self._save_current_article()

        # Extract article info
        article_num, article_title = self._extract_article_info(line)
        self.current_article = f"Điều {article_num}"
        self.current_article_title = article_title

        # Start new article
        self.current_article_lines = []

        # Add chapter context if available
        if self.current_chapter_title:
            self.current_article_lines.append(self.current_chapter_title)
            self.current_article_lines.append("")  # Separator

        # Add article line
        self.current_article_lines.append(line.strip())

    def _handle_content_line(self, line: str):
        """Handle regular content lines"""
        if self.current_article is not None:
            self.current_article_lines.append(line)

    # ========================================================================
    # SAVE METHODS
    # ========================================================================

    def _save_header_chunk(self, lines: List[str]):
        """Save document header as chunk"""
        content = "\n".join(lines).strip()
        if not content:
            return

        # Extract metadata
        self.doc_metadata = self._extract_doc_metadata(content)

        chunk = ChunkData(
            content=content,
            level=ChunkLevel.HEADER,
            has_table=self._has_table(content),
        )
        self.chunks.append(chunk)

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
            "chapter_title": self.current_chapter_title,
            "article": self.current_article,
            "article_title": self.current_article_title,
            "size": len(content),
            "has_table": self._has_table(content),
        }
        self.articles.append(article_data)

        # Reset
        self.current_article_lines = []

    def _save_current_appendix(self):
        """Save current appendix"""
        if not self.current_appendix_lines:
            return

        content = "\n".join(self.current_appendix_lines).strip()
        if not content:
            return

        appendix_data = {
            "content": content,
            "appendix_number": self.current_appendix_num,
            "size": len(content),
            "has_table": self._has_table(content),
        }
        self.appendices.append(appendix_data)

        # Reset
        self.current_appendix_lines = []
        self.current_appendix_num = None

    # ========================================================================
    # CHUNK CREATION
    # ========================================================================

    def _create_parent_child_chunks(self):
        """Create parent and child chunks from articles"""
        for article in self.articles:
            parent_chunk, child_chunks = self._process_article(article)
            self.chunks.append(parent_chunk)
            self.chunks.extend(child_chunks)

    def _process_article(
        self, article: Dict
    ) -> Tuple[ChunkData, List[ChunkData]]:
        """Process one article into parent + children chunks"""
        content = article["content"]
        has_table = article["has_table"]

        # Create parent chunk
        parent = ChunkData(
            content=content,
            level=ChunkLevel.PARENT,
            chapter=article["chapter"],
            chapter_title=article["chapter_title"],
            article=article["article"],
            article_title=article["article_title"],
            has_table=has_table,
        )

        # Create child chunks
        children = []

        if article["size"] <= self.max_child_size:
            # Small article - 1 child = whole article
            child = ChunkData(
                content=content,
                level=ChunkLevel.CHILD,
                chapter=article["chapter"],
                chapter_title=article["chapter_title"],
                article=article["article"],
                article_title=article["article_title"],
                has_table=has_table,
            )
            children.append(child)
        else:
            # Large article - split
            if has_table:
                children = self._split_with_table_protection(content, article)
            else:
                children = self._split_article_into_children(content, article)

        return parent, children

    def _split_article_into_children(
        self, content: str, article: Dict
    ) -> List[ChunkData]:
        """Split article into child chunks by clauses (khoản)"""
        lines = content.split("\n")

        # Find article title line
        title_line = None
        content_start = 0
        for i, line in enumerate(lines):
            if self._is_article(line.strip()):
                title_line = line.strip()
                content_start = i + 1
                break

        # Split by numbered clauses (1. 2. 3.)
        sections = []
        current_section = []

        for line in lines[content_start:]:
            if self._is_clause(line.strip()):
                if current_section:
                    sections.append("\n".join(current_section))
                current_section = [line]
            else:
                current_section.append(line)

        if current_section:
            sections.append("\n".join(current_section))

        # Group sections into chunks
        children = []
        current_chunk_lines = []
        current_size = 0

        chapter_context = article.get("chapter_title") or ""

        for section in sections:
            section_size = len(section)

            if (
                current_size + section_size > self.max_child_size
                and current_chunk_lines
            ):
                # Save current chunk
                chunk_content = self._build_child_content(
                    chapter_context, title_line, "\n".join(current_chunk_lines)
                )
                child = ChunkData(
                    content=chunk_content,
                    level=ChunkLevel.CHILD,
                    chapter=article["chapter"],
                    chapter_title=article["chapter_title"],
                    article=article["article"],
                    article_title=article["article_title"],
                )
                children.append(child)

                # Start new chunk with overlap
                if self.chunk_overlap > 0 and current_chunk_lines:
                    current_chunk_lines = [current_chunk_lines[-1], section]
                    current_size = len(current_chunk_lines[-1]) + section_size
                else:
                    current_chunk_lines = [section]
                    current_size = section_size
            else:
                current_chunk_lines.append(section)
                current_size += section_size

        # Save last chunk
        if current_chunk_lines:
            chunk_content = self._build_child_content(
                chapter_context, title_line, "\n".join(current_chunk_lines)
            )
            child = ChunkData(
                content=chunk_content,
                level=ChunkLevel.CHILD,
                chapter=article["chapter"],
                chapter_title=article["chapter_title"],
                article=article["article"],
                article_title=article["article_title"],
            )
            children.append(child)

        return (
            children
            if children
            else [
                ChunkData(
                    content=content,
                    level=ChunkLevel.CHILD,
                    chapter=article["chapter"],
                    chapter_title=article["chapter_title"],
                    article=article["article"],
                    article_title=article["article_title"],
                )
            ]
        )

    def _split_with_table_protection(
        self, content: str, article: Dict
    ) -> List[ChunkData]:
        """Split article but keep tables intact"""
        # If not too large, keep as single child
        if len(content) <= self.max_child_size * 1.5:
            return [
                ChunkData(
                    content=content,
                    level=ChunkLevel.CHILD,
                    chapter=article["chapter"],
                    chapter_title=article["chapter_title"],
                    article=article["article"],
                    article_title=article["article_title"],
                    has_table=True,
                )
            ]

        # Split around tables
        parts, tables = self._extract_tables(content)
        children = []

        # Get article title
        title_line = None
        for line in content.split("\n"):
            if self._is_article(line.strip()):
                title_line = line.strip()
                break

        # Process non-table parts
        for part in parts:
            if len(part.strip()) < 50:
                continue
            part_content = f"{title_line}\n\n{part}" if title_line else part
            child = ChunkData(
                content=part_content,
                level=ChunkLevel.CHILD,
                chapter=article["chapter"],
                chapter_title=article["chapter_title"],
                article=article["article"],
                article_title=article["article_title"],
            )
            children.append(child)

        # Add table chunks
        for table in tables:
            table_content = f"{title_line}\n\n{table}" if title_line else table
            child = ChunkData(
                content=table_content,
                level=ChunkLevel.CHILD,
                chapter=article["chapter"],
                chapter_title=article["chapter_title"],
                article=article["article"],
                article_title=article["article_title"],
                has_table=True,
            )
            children.append(child)

        return (
            children
            if children
            else [
                ChunkData(
                    content=content,
                    level=ChunkLevel.CHILD,
                    chapter=article["chapter"],
                    chapter_title=article["chapter_title"],
                    article=article["article"],
                    article_title=article["article_title"],
                    has_table=True,
                )
            ]
        )

    def _build_child_content(
        self, chapter_context: str, title: Optional[str], sections: str
    ) -> str:
        """Build child chunk content with context"""
        parts = []

        if chapter_context:
            parts.append(chapter_context)

        if title:
            parts.append(title)

        parts.append(sections)

        return "\n\n".join(parts)

    def _create_appendix_chunks(self):
        """Create chunks for appendices"""
        for appendix in self.appendices:
            content = appendix["content"]

            # Appendix thường chứa bảng - giữ nguyên hoặc split theo bảng
            if len(content) <= self.max_child_size * 2:
                # Keep as single chunk
                chunk = ChunkData(
                    content=content,
                    level=ChunkLevel.APPENDIX,
                    is_appendix=True,
                    appendix_number=appendix["appendix_number"],
                    has_table=appendix["has_table"],
                )
                self.chunks.append(chunk)
            else:
                # Split by tables
                parts, tables = self._extract_tables(content)

                # Add intro part if exists
                for part in parts:
                    if len(part.strip()) > 50:
                        chunk = ChunkData(
                            content=part,
                            level=ChunkLevel.APPENDIX,
                            is_appendix=True,
                            appendix_number=appendix["appendix_number"],
                        )
                        self.chunks.append(chunk)

                # Add each table as separate chunk
                for i, table in enumerate(tables):
                    chunk = ChunkData(
                        content=table,
                        level=ChunkLevel.APPENDIX,
                        is_appendix=True,
                        appendix_number=f"{appendix['appendix_number']}_table_{i+1}",
                        has_table=True,
                    )
                    self.chunks.append(chunk)

    # ========================================================================
    # ID MANAGEMENT
    # ========================================================================

    def _add_chunk_ids(self):
        """Add sequential and readable IDs to chunks"""
        parent_ids = {}
        child_counters = {}

        for idx, chunk in enumerate(self.chunks):
            chunk.chunk_id = idx

            if chunk.level == ChunkLevel.HEADER:
                chunk.readable_id = "header"
                chunk.parent_id = None

            elif chunk.level == ChunkLevel.PARENT:
                id_parts = []
                if chunk.chapter:
                    id_parts.append(f"c{chunk.chapter}")
                if chunk.article:
                    article_num = re.search(r"\d+", chunk.article)
                    if article_num:
                        id_parts.append(f"a{article_num.group()}")

                parent_key = "_".join(id_parts) if id_parts else f"parent_{idx}"
                chunk.readable_id = f"parent_{parent_key}"
                chunk.parent_id = None

                parent_ids[parent_key] = chunk.readable_id
                child_counters[parent_key] = 0

            elif chunk.level == ChunkLevel.CHILD:
                id_parts = []
                if chunk.chapter:
                    id_parts.append(f"c{chunk.chapter}")
                if chunk.article:
                    article_num = re.search(r"\d+", chunk.article)
                    if article_num:
                        id_parts.append(f"a{article_num.group()}")

                parent_key = "_".join(id_parts) if id_parts else f"parent_{idx}"
                chunk.parent_id = parent_ids.get(
                    parent_key, f"parent_{parent_key}"
                )

                child_num = child_counters.get(parent_key, 0)
                child_counters[parent_key] = child_num + 1
                chunk.readable_id = f"child_{parent_key}_c{child_num}"

            elif chunk.level == ChunkLevel.APPENDIX:
                chunk.readable_id = f"appendix_{chunk.appendix_number}"
                chunk.parent_id = None

    # ========================================================================
    # VALIDATION & STATISTICS
    # ========================================================================

    def validate_chunks(self, chunks: List[Dict]) -> Dict:
        """Validate and generate statistics"""
        if not chunks:
            return {
                "total_chunks": 0,
                "by_level": {},
                "avg_chunk_size": 0,
                "min_chunk_size": 0,
                "max_chunk_size": 0,
                "chunks_with_tables": 0,
                "appendix_chunks": 0,
                "error": "No chunks generated",
            }

        stats = {
            "total_chunks": len(chunks),
            "total_chars": sum(c["metadata"]["chunk_size"] for c in chunks),
            "avg_chunk_size": sum(c["metadata"]["chunk_size"] for c in chunks)
            / len(chunks),
            "min_chunk_size": min(c["metadata"]["chunk_size"] for c in chunks),
            "max_chunk_size": max(c["metadata"]["chunk_size"] for c in chunks),
            "doc_metadata": {
                "doc_number": self.doc_metadata.doc_number,
                "doc_date": self.doc_metadata.doc_date,
                "doc_title": self.doc_metadata.doc_title,
                "doc_type": self.doc_metadata.doc_type,
            },
        }

        # Count by level
        levels = {}
        for chunk in chunks:
            level = chunk["metadata"].get("level", "unknown")
            levels[level] = levels.get(level, 0) + 1
        stats["by_level"] = levels

        # Chunks with tables
        stats["chunks_with_tables"] = sum(
            1 for c in chunks if c["metadata"].get("has_table")
        )

        # Appendix count
        stats["appendix_chunks"] = sum(
            1 for c in chunks if c["metadata"].get("is_appendix")
        )

        # Size distribution
        stats["size_distribution"] = {
            "0-300": sum(
                1 for c in chunks if c["metadata"]["chunk_size"] < 300
            ),
            "300-500": sum(
                1 for c in chunks if 300 <= c["metadata"]["chunk_size"] < 500
            ),
            "500-1000": sum(
                1 for c in chunks if 500 <= c["metadata"]["chunk_size"] < 1000
            ),
            "1000-2000": sum(
                1 for c in chunks if 1000 <= c["metadata"]["chunk_size"] < 2000
            ),
            "2000+": sum(
                1 for c in chunks if c["metadata"]["chunk_size"] >= 2000
            ),
        }

        return stats

    # ========================================================================
    # FALLBACK CHUNKING (RecursiveCharacterTextSplitter)
    # ========================================================================

    def _has_legal_structure(self, text: str) -> bool:
        """Check if text has Điều/Chương structure"""
        has_article = bool(self.patterns["article"].search(text))
        has_chapter = bool(self.patterns["chapter"].search(text))
        return has_article or has_chapter

    def _fallback_recursive_chunk(self, text: str) -> List[Dict]:
        """
        Fallback chunking using RecursiveCharacterTextSplitter
        For documents without Điều/Chương structure
        """
        print(
            "⚠️  Không tìm thấy cấu trúc Điều/Chương, sử dụng RecursiveCharacterTextSplitter..."
        )

        # Create splitter with Vietnamese-friendly separators
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.fallback_chunk_size,
            chunk_overlap=self.fallback_chunk_overlap,
            separators=[
                "\n\n",  # Paragraph
                "\n",  # Line
                "。",  # Chinese period (sometimes in docs)
                ".",  # Period
                " ",  # Space
                "",  # Character
            ],
            length_function=len,
        )

        # Split text
        docs = splitter.create_documents([text])

        # Convert to our chunk format
        chunks = []
        for idx, doc in enumerate(docs):
            chunk_data = ChunkData(
                content=doc.page_content,
                level=ChunkLevel.RECURSIVE,
                has_table=self._has_table(doc.page_content),
                chunk_id=idx,
                readable_id=f"recursive_{idx}",
                parent_id=None,
            )
            chunks.append(chunk_data.to_dict())

        print(
            f"   ✓ Tạo được {len(chunks)} chunks từ RecursiveCharacterTextSplitter"
        )
        return chunks

    # ========================================================================
    # MAIN PIPELINE
    # ========================================================================

    def chunk_document(self, text: str) -> Tuple[List[Dict], Dict]:
        """
        Complete chunking pipeline with fallback

        Strategy:
        1. Check if document has Điều/Chương structure
        2. If YES → use hierarchical parsing
        3. If NO → fallback to RecursiveCharacterTextSplitter

        Returns: (chunks, statistics)
        """
        # Check for legal structure
        if self._has_legal_structure(text):
            # Use hierarchical parsing
            chunks = self.parse(text)

            # If parsing failed (no chunks), use fallback
            if not chunks:
                chunks = self._fallback_recursive_chunk(text)
        else:
            # No legal structure, use fallback directly
            chunks = self._fallback_recursive_chunk(text)

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

        print(f"💾 Saved {len(chunks)} chunks to: {output_path}")


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================


def chunk_olmocr_file(
    file_path: str, output_path: Optional[str] = None
) -> Tuple[List[Dict], Dict]:
    """
    Chunk a single OLM OCR markdown file

    Args:
        file_path: Path to markdown file
        output_path: Optional path to save chunks JSON

    Returns:
        (chunks, statistics)
    """
    from pathlib import Path

    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()

    chunker = OlmOcrLegalChunker()
    chunks, stats = chunker.chunk_document(text)

    if output_path:
        chunker.save_chunks(chunks, output_path)

    return chunks, stats


def chunk_olmocr_folder(
    folder_path: str, output_folder: str, pattern: str = "*.md"
) -> Dict:
    """
    Chunk all markdown files in a folder

    Args:
        folder_path: Path to folder with markdown files
        output_folder: Path to output folder for JSON files
        pattern: Glob pattern for files

    Returns:
        Summary statistics
    """
    from pathlib import Path

    input_folder = Path(folder_path)
    output_folder = Path(output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)

    summary = {"total_files": 0, "total_chunks": 0, "files": []}

    for file_path in input_folder.glob(pattern):
        print(f"📄 Processing: {file_path.name}")

        output_path = output_folder / f"{file_path.stem}_chunks.json"

        try:
            chunks, stats = chunk_olmocr_file(str(file_path), str(output_path))

            summary["total_files"] += 1
            summary["total_chunks"] += len(chunks)
            summary["files"].append(
                {"name": file_path.name, "chunks": len(chunks), "stats": stats}
            )

        except Exception as e:
            print(f"❌ Error processing {file_path.name}: {e}")
            summary["files"].append({"name": file_path.name, "error": str(e)})

    print(
        f"\n✅ Processed {summary['total_files']} files, {summary['total_chunks']} total chunks"
    )
    return summary


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python olmocr_legal_chunker.py <file.md>")
        print("  python olmocr_legal_chunker.py <folder> <output_folder>")
        sys.exit(1)

    from pathlib import Path

    input_path = Path(sys.argv[1])

    if input_path.is_file():
        # Single file
        output_path = input_path.with_suffix(".chunks.json")
        chunks, stats = chunk_olmocr_file(str(input_path), str(output_path))

        print(f"\n📊 Statistics:")
        print(f"  Total chunks: {stats['total_chunks']}")
        print(f"  By level: {stats['by_level']}")
        print(f"  Avg size: {stats['avg_chunk_size']:.0f} chars")
        print(f"  Tables: {stats['chunks_with_tables']}")

    elif input_path.is_dir():
        # Folder
        output_folder = (
            sys.argv[2] if len(sys.argv) > 2 else str(input_path / "chunks")
        )
        summary = chunk_olmocr_folder(str(input_path), output_folder)

        print(f"\n📊 Summary:")
        print(f"  Files: {summary['total_files']}")
        print(f"  Total chunks: {summary['total_chunks']}")
