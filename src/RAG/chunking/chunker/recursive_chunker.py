"""
Recursive Character Text Splitter Chunker

Chunker dùng RecursiveCharacterTextSplitter từ LangChain.
Phù hợp cho các tài liệu không có cấu trúc pháp lý (Điều/Chương),
ví dụ: Chương trình đào tạo (CTDT), tài liệu hướng dẫn, FAQ, v.v.

Strategy:
- Tách văn bản theo thứ tự ưu tiên: markdown heading > paragraph > sentence > word
- Giữ overlap giữa các chunks để đảm bảo ngữ cảnh liền mạch
- Bảo vệ bảng markdown (không tách giữa bảng)
- Thêm metadata: section heading, vị trí chunk, có bảng hay không
"""

from typing import List, Dict, Optional, Tuple
import re
import uuid
from langchain_text_splitters import RecursiveCharacterTextSplitter


class RecursiveChunker:
    """
    Recursive Character Text Splitter for Vietnamese educational documents.

    Sử dụng RecursiveCharacterTextSplitter với separators tối ưu cho
    tài liệu tiếng Việt dạng markdown (CTDT, hướng dẫn, v.v.)

    Parameters:
        chunk_size: Kích thước tối đa của mỗi chunk (default: 1024)
        chunk_overlap: Số ký tự overlap giữa 2 chunks liên tiếp (default: 150)
        protect_tables: Bảo vệ bảng markdown, không tách giữa bảng (default: True)
        add_section_context: Thêm heading context vào mỗi chunk (default: True)
    """

    MARKDOWN_SEPARATORS = [
        "\n# ",  # H1 heading
        "\n## ",  # H2 heading
        "\n### ",  # H3 heading
        "\n#### ",  # H4 heading
        "\n---\n",  # Horizontal rule (section separator)
        "\n\n",  # Paragraph break
        "\n",  # Line break
        ". ",  # Sentence boundary
        ", ",  # Clause boundary
        " ",  # Word boundary
        "",  # Character fallback
    ]

    def __init__(
        self,
        chunk_size: int = 1024,
        chunk_overlap: int = 150,
        protect_tables: bool = True,
        add_section_context: bool = True,
        min_chunk_size: int = 50,
        parent_chunk_max_chars: int = 10000,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.protect_tables = protect_tables
        self.add_section_context = add_section_context
        self.min_chunk_size = min_chunk_size
        self.parent_chunk_max_chars = parent_chunk_max_chars

        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=self.MARKDOWN_SEPARATORS,
            is_separator_regex=False,
        )

    def _extract_document_title(self, text: str) -> Optional[str]:
        """Trích xuất tiêu đề document từ heading đầu tiên"""
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("# "):
                return line.lstrip("# ").strip()
        return None

    def _extract_section_headings(self, text: str) -> List[Dict]:
        """
        Trích xuất tất cả headings và vị trí của chúng.
        Returns list of {level, title, start_pos}
        """
        headings = []
        for match in re.finditer(r"^(#{1,4})\s+(.+)$", text, re.MULTILINE):
            headings.append(
                {
                    "level": len(match.group(1)),
                    "title": match.group(2).strip(),
                    "start_pos": match.start(),
                }
            )
        return headings

    def _find_section_for_position(
        self, pos: int, headings: List[Dict]
    ) -> Dict[str, Optional[str]]:
        """
        Tìm section heading chứa vị trí pos trong document.
        Trả về hierarchy: h1, h2, h3, h4
        """
        context = {"h1": None, "h2": None, "h3": None, "h4": None}

        for heading in headings:
            if heading["start_pos"] <= pos:
                level = heading["level"]
                key = f"h{level}"
                context[key] = heading["title"]
                # Reset child headings khi gặp parent mới
                for child_level in range(level + 1, 5):
                    context[f"h{child_level}"] = None
            else:
                break

        return context

    def _detect_table_in_chunk(self, text: str) -> bool:
        """Kiểm tra chunk có chứa bảng markdown không"""
        lines = text.strip().split("\n")
        for line in lines:
            if line.strip().startswith("|") and "|" in line.strip()[1:]:
                return True
        return False

    def _chunk_starts_mid_table(self, content: str) -> bool:
        """
        Kiểm tra chunk có bắt đầu giữa bảng không (thiếu dòng header).
        Dấu hiệu: dòng đầu là table row nhưng dòng thứ 2 không phải separator |---|.
        """
        lines = [l for l in content.strip().split("\n") if l.strip()]
        if not lines or not lines[0].strip().startswith("|"):
            return False
        if len(lines) < 2:
            return True  # chỉ có 1 dòng table → không có header/separator
        second_line = lines[1].strip()
        is_separator = bool(re.match(r"^\|[\s\-|:]+\|$", second_line))
        return not is_separator

    def _find_table_header_in_text(self, text: str) -> Optional[str]:
        """
        Tìm cặp (header + separator) của bảng cuối cùng xuất hiện trong text.
        Trả về 2 dòng: 'header_row\nseparator_row' hoặc None.
        """
        lines = text.split("\n")
        for i in range(len(lines) - 1, 0, -1):
            line = lines[i].strip()
            if re.match(r"^\|[\s\-|:]+\|$", line):  # separator line
                if lines[i - 1].strip().startswith("|"):
                    return lines[i - 1] + "\n" + lines[i]
        return None

    def _fix_mid_table_chunks(self, chunks: List[Dict]) -> List[Dict]:
        """
        Post-process: với mỗi chunk bắt đầu giữa bảng (thiếu header),
        tìm và ghép lại header từ chunk trước đó.
        """
        for i in range(1, len(chunks)):
            content = chunks[i]["content"]
            if self._chunk_starts_mid_table(content):
                header = self._find_table_header_in_text(
                    chunks[i - 1]["content"]
                )
                if header:
                    chunks[i]["content"] = header + "\n" + content
                    chunks[i]["metadata"]["chunk_size"] = len(
                        chunks[i]["content"]
                    )
                    chunks[i]["metadata"]["has_table"] = True
        return chunks

    def _split_table_by_rows(
        self, table_text: str, max_rows_per_chunk: int = 0
    ) -> List[str]:
        """
        Tách bảng thành nhiều phần, mỗi phần có header + separator + N rows.
        Nếu max_rows_per_chunk=0 thì tự tính dựa trên chunk_size.
        """
        lines = table_text.strip().split("\n")
        # Tìm header + separator
        header_line = None
        separator_line = None
        data_rows = []

        for i, line in enumerate(lines):
            if not line.strip().startswith("|"):
                continue
            if separator_line is None:
                if re.match(r"^\|[\s\-|:]+\|$", line.strip()):
                    separator_line = line
                elif header_line is None:
                    header_line = line
                else:
                    # Không có separator -> tất cả là data rows
                    data_rows.append(header_line)
                    header_line = line
            else:
                data_rows.append(line)

        if not header_line or not separator_line or not data_rows:
            return [table_text]

        header_block = header_line + "\n" + separator_line
        header_len = len(header_block) + 1  # +1 for \n

        if max_rows_per_chunk <= 0:
            avg_row_len = (
                sum(len(r) for r in data_rows) / len(data_rows)
                if data_rows
                else 50
            )
            available = (
                self.chunk_size - header_len - 100
            )  # margin cho heading context
            max_rows_per_chunk = max(3, int(available / (avg_row_len + 1)))

        sub_tables = []
        for start in range(0, len(data_rows), max_rows_per_chunk):
            batch = data_rows[start : start + max_rows_per_chunk]
            sub_table = header_block + "\n" + "\n".join(batch)
            sub_tables.append(sub_table)

        return sub_tables

    def _split_oversized_chunk(self, content: str) -> List[str]:
        """
        Tách 1 chunk quá lớn thành nhiều sub-chunks.

        Strategy:
        1. Tách theo section headings (###, ####) nếu có
        2. Với mỗi section con: nếu vẫn > chunk_size → tách bảng theo rows
        3. Với section thuần text > chunk_size → re-split bằng text_splitter
        """
        if len(content.strip()) <= self.chunk_size:
            return [content]

        # Bước 1: Tách theo section headings (### hoặc ####)
        section_pattern = re.compile(r"(?=\n#{3,4}\s+)", re.MULTILINE)
        sections = section_pattern.split(content)
        # Nếu phần đầu tiên rỗng (content bắt đầu bằng heading) thì bỏ
        sections = [s for s in sections if s.strip()]

        if len(sections) <= 1:
            # Không có sub-sections → tách trực tiếp
            return self._split_single_section(content)

        # Bước 2: Gom sections nhỏ lại, tách sections lớn
        result = []
        buffer = ""
        for section in sections:
            candidate = (
                (buffer + "\n" + section).strip() if buffer else section.strip()
            )
            if len(candidate) <= self.chunk_size:
                buffer = candidate
            else:
                # Flush buffer nếu có
                if buffer:
                    result.append(buffer)
                    buffer = ""
                # Section này có thể vẫn quá lớn
                if len(section.strip()) > self.chunk_size:
                    sub_parts = self._split_single_section(section.strip())
                    result.extend(sub_parts)
                else:
                    buffer = section.strip()
        if buffer:
            result.append(buffer)

        return result

    def _split_single_section(self, content: str) -> List[str]:
        """
        Tách một section đơn (không có sub-headings) quá lớn.
        - Nếu chứa bảng: tách bảng theo rows, giữ header + context trước bảng
        - Nếu thuần text: re-split bằng RecursiveCharacterTextSplitter
        """
        if len(content.strip()) <= self.chunk_size:
            return [content]

        # Kiểm tra có bảng không
        table_match = re.search(r"((?:^\|.+\|$\n?)+)", content, re.MULTILINE)

        if table_match:
            # Tách phần text trước bảng (heading + mô tả)
            prefix = content[: table_match.start()].strip()
            table_text = table_match.group(0).strip()
            suffix = content[table_match.end() :].strip()

            # Tách bảng theo rows
            sub_tables = self._split_table_by_rows(table_text)

            result = []
            for i, sub_table in enumerate(sub_tables):
                if i == 0 and prefix:
                    # Chunk đầu: prefix (heading) + phần bảng đầu
                    chunk_content = prefix + "\n\n" + sub_table
                else:
                    # Các chunk sau: chỉ bảng (đã có header)
                    if prefix:
                        # Thêm heading context ngắn gọn (chỉ dòng heading đầu)
                        heading_lines = [
                            l
                            for l in prefix.split("\n")
                            if l.strip().startswith("#")
                        ]
                        heading_ctx = heading_lines[-1] if heading_lines else ""
                        if heading_ctx:
                            chunk_content = heading_ctx + "\n\n" + sub_table
                        else:
                            chunk_content = sub_table
                    else:
                        chunk_content = sub_table
                result.append(chunk_content)

            if suffix:
                # Ghép suffix vào chunk cuối nếu đủ chỗ, không thì tạo chunk mới
                if (
                    result
                    and len(result[-1]) + len(suffix) + 2 <= self.chunk_size
                ):
                    result[-1] = result[-1] + "\n\n" + suffix
                else:
                    result.append(suffix)

            return result
        else:
            # Thuần text → re-split bằng text_splitter
            sub_splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                separators=self.MARKDOWN_SEPARATORS,
            )
            return sub_splitter.split_text(content)

    def _inject_section_context(self, chunks: List[Dict]) -> List[Dict]:
        """
        Với chunk không có heading nào trong content (chỉ có table rows),
        thêm dòng heading context từ metadata vào đầu chunk.
        Giúp cải thiện chất lượng embedding và khả năng hiểu của LLM.
        """
        for chunk in chunks:
            content = chunk["content"]
            # Kiểm tra chunk có heading nào không
            has_heading = any(
                l.strip().startswith("#")
                for l in content.split("\n")
                if l.strip()
            )
            if has_heading:
                continue

            # Xây dựng heading context từ metadata (ưu tiên h3 > h2 > h1)
            ctx_parts = []
            for key in ["section_h3", "section_h4"]:
                val = chunk["metadata"].get(key)
                if val:
                    level = 3 if key == "section_h3" else 4
                    ctx_parts.append("#" * level + " " + val)

            if not ctx_parts:
                # Nếu không có h3/h4, dùng h2
                h2 = chunk["metadata"].get("section_h2")
                if h2:
                    ctx_parts.append("## " + h2)

            if ctx_parts:
                # Chỉ lấy heading cuối (cụ thể nhất) để không thừa
                heading_ctx = ctx_parts[-1]
                chunk["content"] = heading_ctx + "\n\n" + content
                chunk["metadata"]["chunk_size"] = len(chunk["content"])

        return chunks

    def _protect_tables_in_text(self, text: str) -> Tuple[str, Dict[str, str]]:
        """
        Thay thế bảng markdown bằng placeholder để tránh bị tách giữa bảng.
        Chỉ bảo vệ bảng có kích thước <= chunk_size.
        Bảng lớn hơn sẽ được giữ nguyên để text splitter tách.

        Returns: (text_with_placeholders, placeholder_to_table_map)
        """
        table_map = {}
        table_pattern = re.compile(
            r"((?:^\|.+\|$\n?)+)",
            re.MULTILINE,
        )

        def replace_table(match):
            table_text = match.group(0)
            # Chỉ bảo vệ bảng nhỏ hơn chunk_size
            if len(table_text) <= self.chunk_size:
                placeholder = f"__TABLE_{len(table_map):04d}__"
                table_map[placeholder] = table_text
                return placeholder
            # Bảng lớn hơn chunk_size -> để nguyên cho splitter xử lý
            return table_text

        protected_text = table_pattern.sub(replace_table, text)
        return protected_text, table_map

    def _restore_tables(self, text: str, table_map: Dict[str, str]) -> str:
        """Khôi phục bảng từ placeholder"""
        for placeholder, table_text in table_map.items():
            text = text.replace(placeholder, table_text)
        return text

    def _build_section_path(self, section_ctx: Dict[str, Optional[str]]) -> str:
        """Xây dựng hierarchy path từ section context"""
        parts = []
        for key in ["h1", "h2", "h3", "h4"]:
            if section_ctx.get(key):
                parts.append(section_ctx[key])
        return " > ".join(parts) if parts else ""

    def _extract_h2_sections(self, text: str) -> List[Dict]:
        """
        Trích xuất các section h2 từ document.
        Trả về list of {title, content, start_pos, end_pos}.
        Mỗi section bao gồm nội dung từ heading h2 đến heading h2 kế tiếp.
        """
        h2_pattern = re.compile(r"^## (.+)$", re.MULTILINE)
        h2_matches = list(h2_pattern.finditer(text))

        if not h2_matches:
            return []

        sections = []
        for i, m in enumerate(h2_matches):
            start = m.start()
            end = (
                h2_matches[i + 1].start()
                if i + 1 < len(h2_matches)
                else len(text)
            )
            section_content = text[start:end].strip()
            sections.append(
                {
                    "title": m.group(1).strip(),
                    "content": section_content,
                    "start_pos": start,
                    "end_pos": end,
                }
            )
        return sections

    def _truncate_content(self, content: str, max_chars: int) -> str:
        """
        Cắt content tại giới hạn max_chars, ưu tiên cắt tại ranh giới tự nhiên.
        Thêm marker '...[truncated]' nếu bị cắt.
        """
        if len(content) <= max_chars:
            return content

        # Tìm điểm cắt tự nhiên gần max_chars nhất
        # Ưu tiên: paragraph break > line break > sentence boundary
        truncated = content[:max_chars]

        # Tìm paragraph break cuối cùng
        last_para = truncated.rfind("\n\n")
        if last_para > max_chars * 0.7:
            return truncated[:last_para].strip() + "\n\n...[truncated]"

        # Tìm line break cuối cùng
        last_line = truncated.rfind("\n")
        if last_line > max_chars * 0.7:
            return truncated[:last_line].strip() + "\n\n...[truncated]"

        # Tìm sentence boundary
        last_sentence = truncated.rfind(". ")
        if last_sentence > max_chars * 0.7:
            return truncated[: last_sentence + 1].strip() + "\n\n...[truncated]"

        return truncated.strip() + "\n\n...[truncated]"

    def _create_parent_chunks(
        self,
        text: str,
        doc_title: Optional[str],
        headings: List[Dict],
        source: str = "",
    ) -> List[Dict]:
        """
        Tạo parent chunks ở cấp h2 section.
        Mỗi parent chunk chứa toàn bộ nội dung section h2 (truncate nếu > max_chars).

        Returns:
            List of parent chunk dicts
        """
        h2_sections = self._extract_h2_sections(text)
        parent_chunks = []

        for section in h2_sections:
            content = section["content"]

            # Truncate nếu quá dài
            content = self._truncate_content(
                content, self.parent_chunk_max_chars
            )

            # Xác định section context
            section_ctx = self._find_section_for_position(
                section["start_pos"], headings
            )
            hierarchy_path = self._build_section_path(section_ctx)

            # Xác định chunk_type dựa trên nội dung
            has_table = self._detect_table_in_chunk(content)
            if has_table:
                has_heading = any(
                    l.strip().startswith("#")
                    for l in content.split("\n")
                    if l.strip()
                )
                chunk_type = "mixed" if has_heading else "table"
            else:
                chunk_type = "text"

            parent_chunk = {
                "id": str(uuid.uuid4()),
                "chunk_id": "",  # sẽ được cập nhật sau khi re-index
                "readable_id": "",
                "content": content,
                "metadata": {
                    "doc_type": "curriculum",
                    "level": "parent",
                    "doc_title": doc_title,
                    "source": source,
                    "section_h1": section_ctx.get("h1"),
                    "section_h2": section_ctx.get("h2"),
                    "section_h3": None,
                    "section_h4": None,
                    "hierarchy_path": hierarchy_path,
                    "chunk_index": 0,  # sẽ cập nhật
                    "total_chunks": 0,  # sẽ cập nhật
                    "chunk_size": len(content),
                    "chunk_type": "parent",
                    "has_table": has_table,
                    "parent_id": None,
                    "child_count": 0,  # sẽ cập nhật
                },
            }
            parent_chunks.append(parent_chunk)

        return parent_chunks

    def _link_parent_child(
        self, parent_chunks: List[Dict], child_chunks: List[Dict]
    ) -> List[Dict]:
        """
        Liên kết child chunks với parent chunks dựa trên section_h2.
        Chèn parent chunk trước các child chunks của nó.
        Trả về list chunks đã sắp xếp (parent trước, children sau).

        Để tránh lỗi khi chunk vượt ranh giới section (do overlap), section_h2
        được xác định từ content thực tế (last ## heading trong content) thay vì
        chỉ dựa vào metadata section_h2 có thể sai.
        """

        def _effective_h2(chunk: Dict) -> Optional[str]:
            """Trích xuất section_h2 thực tế từ content của chunk.
            Ưu tiên ## heading cuối cùng xuất hiện trong content.
            Fallback về metadata section_h2 nếu không tìm thấy."""
            h2_matches = re.findall(
                r"^## (.+)$", chunk["content"], re.MULTILINE
            )
            if h2_matches:
                # Lấy heading cuối cùng (heading 'hiện tại' của nội dung)
                effective = h2_matches[-1].strip()
                # Cập nhật luôn metadata nếu khác
                if effective != chunk["metadata"].get("section_h2"):
                    chunk["metadata"]["section_h2"] = effective
                    # Rebuild hierarchy_path
                    chunk["metadata"]["hierarchy_path"] = " > ".join(
                        p
                        for p in [
                            chunk["metadata"].get("section_h1"),
                            effective,
                            chunk["metadata"].get("section_h3"),
                            chunk["metadata"].get("section_h4"),
                        ]
                        if p
                    )
                return effective
            return chunk["metadata"].get("section_h2")

        # Build map: section_h2 -> parent chunk
        h2_to_parent = {}
        for pc in parent_chunks:
            h2 = pc["metadata"].get("section_h2")
            if h2:
                h2_to_parent[h2] = pc

        # Group child chunks by effective section_h2 (từ content)
        h2_to_children = {}
        orphan_children = []
        for cc in child_chunks:
            h2 = _effective_h2(cc)
            if h2 and h2 in h2_to_parent:
                h2_to_children.setdefault(h2, []).append(cc)
            else:
                orphan_children.append(cc)

        # Sắp xếp: orphan chunks đầu tiên, sau đó mỗi group là [parent, children...]
        result = []

        # Thêm orphan children (chunks không thuộc section h2 nào)
        result.extend(orphan_children)

        # Thêm parent + children theo thứ tự xuất hiện
        for pc in parent_chunks:
            h2 = pc["metadata"].get("section_h2")
            children = h2_to_children.get(h2, [])
            parent_id = pc["id"]

            # Cập nhật child_count cho parent
            pc["metadata"]["child_count"] = len(children)

            # Thêm parent chunk
            result.append(pc)

            # Cập nhật mỗi child chunk
            for cc in children:
                cc["metadata"]["parent_id"] = parent_id
                # Xác định chunk_type
                if cc["metadata"].get("has_table"):
                    if any(
                        l.strip().startswith("#")
                        for l in cc["content"].split("\n")
                        if l.strip()
                    ):
                        cc["metadata"]["chunk_type"] = "mixed"
                    else:
                        cc["metadata"]["chunk_type"] = "table"
                else:
                    cc["metadata"]["chunk_type"] = "text"
                result.append(cc)

        # Cũng set chunk_type cho orphan children
        for cc in orphan_children:
            if "chunk_type" not in cc["metadata"]:
                if cc["metadata"].get("has_table"):
                    if any(
                        l.strip().startswith("#")
                        for l in cc["content"].split("\n")
                        if l.strip()
                    ):
                        cc["metadata"]["chunk_type"] = "mixed"
                    else:
                        cc["metadata"]["chunk_type"] = "table"
                else:
                    cc["metadata"]["chunk_type"] = "text"
            cc["metadata"].setdefault("parent_id", None)

        return result

    def chunk_document(
        self, text: str, source: str = ""
    ) -> Tuple[List[Dict], Dict]:
        """
        Main chunking pipeline.

        Args:
            text: Nội dung markdown cần chunk
            source: Tên file nguồn (optional, để thêm vào metadata)

        Returns:
            Tuple of (chunks, stats)
        """
        if not text or not text.strip():
            return [], {"total_chunks": 0}

        doc_title = self._extract_document_title(text)
        headings = self._extract_section_headings(text)

        # Bảo vệ bảng nếu cần
        table_map = {}
        processing_text = text
        if self.protect_tables:
            processing_text, table_map = self._protect_tables_in_text(text)

        # Split text
        raw_chunks = self.text_splitter.split_text(processing_text)

        # Merge small chunks vào chunk kế tiếp
        merged_chunks = []
        buffer = ""
        for rc in raw_chunks:
            if buffer:
                rc = buffer + "\n" + rc
                buffer = ""
            if len(rc.strip()) < self.min_chunk_size:
                buffer = rc
            else:
                merged_chunks.append(rc)
        if buffer:
            if merged_chunks:
                merged_chunks[-1] = merged_chunks[-1] + "\n" + buffer
            else:
                merged_chunks.append(buffer)
        raw_chunks = merged_chunks

        # Tạo chunks với metadata
        # QUAN TRỌNG: track position trong text GỐC (không phải processing_text)
        # để section metadata khớp đúng với headings positions.
        chunks = []
        text_pos = 0

        for idx, raw_content in enumerate(raw_chunks):
            # Khôi phục bảng nếu cần
            content = raw_content
            if self.protect_tables and table_map:
                content = self._restore_tables(raw_content, table_map)

            # Tìm vị trí trong text GỐC để xác định section
            # Ưu tiên dùng non-table lines để tránh placeholder gây lệch offset
            search_start = max(0, text_pos - self.chunk_overlap)
            non_table_lines = [
                l
                for l in content.split("\n")
                if l.strip() and not l.strip().startswith("|")
            ]
            if non_table_lines:
                search_key = non_table_lines[0][:100].strip()
            else:
                search_key = content[:100].strip()

            found_pos = text.find(search_key, search_start)
            if found_pos >= 0:
                text_pos = found_pos
            # else: giữ nguyên text_pos (ước lượng tiếp theo)

            # Xác định section context
            section_ctx = self._find_section_for_position(text_pos, headings)
            hierarchy_path = self._build_section_path(section_ctx)

            # Detect bảng
            has_table = self._detect_table_in_chunk(content)

            # Tạo chunk ID
            chunk_id = str(uuid.uuid4())
            readable_id = f"chunk_{idx:04d}"

            chunk = {
                "id": chunk_id,
                "chunk_id": readable_id,
                "readable_id": readable_id,
                "content": content.strip(),
                "metadata": {
                    "doc_type": "curriculum",
                    "level": "recursive",
                    "doc_title": doc_title,
                    "source": source,
                    "section_h1": section_ctx.get("h1"),
                    "section_h2": section_ctx.get("h2"),
                    "section_h3": section_ctx.get("h3"),
                    "section_h4": section_ctx.get("h4"),
                    "hierarchy_path": hierarchy_path,
                    "chunk_index": idx,
                    "total_chunks": len(raw_chunks),
                    "chunk_size": len(content.strip()),
                    "has_table": has_table,
                },
            }

            chunks.append(chunk)
            text_pos += len(content) - self.chunk_overlap

        # Post-process: ghép lại table header cho các chunk bắt đầu giữa bảng
        chunks = self._fix_mid_table_chunks(chunks)

        # Post-process: tách các chunk quá lớn (> chunk_size * 1.3)
        # Giữ tolerance 30% để không tách những chunk chỉ vượt nhẹ
        oversized_threshold = int(self.chunk_size * 1.3)
        final_chunks = []
        for chunk in chunks:
            if chunk["metadata"]["chunk_size"] > oversized_threshold:
                sub_contents = self._split_oversized_chunk(chunk["content"])
                for sub_idx, sub_content in enumerate(sub_contents):
                    sub_content = sub_content.strip()
                    if not sub_content:
                        continue
                    # Xác định section cho sub-chunk
                    # Tìm position trong text gốc
                    non_table = [
                        l
                        for l in sub_content.split("\n")
                        if l.strip() and not l.strip().startswith("|")
                    ]
                    sk = (
                        non_table[0][:100].strip()
                        if non_table
                        else sub_content[:100].strip()
                    )
                    fp = text.find(sk)
                    if fp >= 0:
                        sc = self._find_section_for_position(fp, headings)
                    else:
                        # Fallback: kế thừa metadata từ chunk gốc
                        sc = {
                            "h1": chunk["metadata"]["section_h1"],
                            "h2": chunk["metadata"]["section_h2"],
                            "h3": chunk["metadata"]["section_h3"],
                            "h4": chunk["metadata"]["section_h4"],
                        }
                    hp = self._build_section_path(sc)

                    new_chunk = {
                        "id": str(uuid.uuid4()),
                        "chunk_id": "",  # sẽ cập nhật sau
                        "readable_id": "",
                        "content": sub_content,
                        "metadata": {
                            **chunk["metadata"],
                            "section_h1": sc.get("h1"),
                            "section_h2": sc.get("h2"),
                            "section_h3": sc.get("h3"),
                            "section_h4": sc.get("h4"),
                            "hierarchy_path": hp,
                            "chunk_size": len(sub_content),
                            "has_table": self._detect_table_in_chunk(
                                sub_content
                            ),
                        },
                    }
                    final_chunks.append(new_chunk)
            else:
                final_chunks.append(chunk)

        chunks = final_chunks

        # Post-process: inject section heading context cho chunks thiếu heading
        # Giúp embedding + LLM hiểu ngữ cảnh khi chunk chỉ có table rows
        if self.add_section_context:
            chunks = self._inject_section_context(chunks)

        # Post-process: merge chunks quá nhỏ (< min_merge_size) vào chunk liền kề
        # Ưu tiên merge vào chunk SAU (vì chunk nhỏ thường là heading intro)
        # Cho phép merge tới oversized_threshold (1.3x chunk_size) để tránh orphan chunks
        min_merge_size = max(self.min_chunk_size, 200)
        merge_limit = oversized_threshold  # cho phép merge tới 1.3x chunk_size
        merged = []
        for chunk in chunks:
            if (
                merged
                and merged[-1]["metadata"]["chunk_size"] < min_merge_size
                and merged[-1]["metadata"]["chunk_size"]
                + chunk["metadata"]["chunk_size"]
                <= merge_limit
            ):
                # Merge chunk trước (nhỏ) vào chunk hiện tại
                prev = merged.pop()
                chunk["content"] = prev["content"] + "\n\n" + chunk["content"]
                chunk["metadata"]["chunk_size"] = len(chunk["content"])
                chunk["metadata"]["has_table"] = (
                    prev["metadata"]["has_table"]
                    or chunk["metadata"]["has_table"]
                )
                # Giữ section metadata của chunk đầu tiên (heading intro)
                for key in [
                    "section_h1",
                    "section_h2",
                    "section_h3",
                    "section_h4",
                ]:
                    if prev["metadata"].get(key) and not chunk["metadata"].get(
                        key
                    ):
                        chunk["metadata"][key] = prev["metadata"][key]
                chunk["metadata"]["hierarchy_path"] = self._build_section_path(
                    {
                        "h1": chunk["metadata"]["section_h1"],
                        "h2": chunk["metadata"]["section_h2"],
                        "h3": chunk["metadata"]["section_h3"],
                        "h4": chunk["metadata"]["section_h4"],
                    }
                )
            merged.append(chunk)

        # Xử lý chunk cuối nếu quá nhỏ
        if (
            len(merged) > 1
            and merged[-1]["metadata"]["chunk_size"] < min_merge_size
        ):
            last = merged.pop()
            merged[-1]["content"] = (
                merged[-1]["content"] + "\n\n" + last["content"]
            )
            merged[-1]["metadata"]["chunk_size"] = len(merged[-1]["content"])
            merged[-1]["metadata"]["has_table"] = (
                merged[-1]["metadata"]["has_table"]
                or last["metadata"]["has_table"]
            )

        chunks = merged

        # ================================================================
        # Tạo parent chunks ở cấp h2 và liên kết parent-child
        # ================================================================
        parent_chunks = self._create_parent_chunks(
            text, doc_title, headings, source
        )
        if parent_chunks:
            chunks = self._link_parent_child(parent_chunks, chunks)

        # Re-index tất cả chunks
        for idx, chunk in enumerate(chunks):
            readable_id = f"chunk_{idx:04d}"
            chunk["chunk_id"] = readable_id
            chunk["readable_id"] = readable_id
            chunk["metadata"]["chunk_index"] = idx
            chunk["metadata"]["total_chunks"] = len(chunks)

        # Thống kê
        chunk_sizes = [c["metadata"]["chunk_size"] for c in chunks]
        parent_count = sum(
            1 for c in chunks if c["metadata"].get("level") == "parent"
        )
        child_count = sum(
            1 for c in chunks if c["metadata"].get("parent_id") is not None
        )
        stats = {
            "total_chunks": len(chunks),
            "parent_chunks": parent_count,
            "child_chunks": child_count,
            "orphan_chunks": len(chunks) - parent_count - child_count,
            "avg_chunk_size": (
                sum(chunk_sizes) / len(chunk_sizes) if chunk_sizes else 0
            ),
            "min_chunk_size": min(chunk_sizes) if chunk_sizes else 0,
            "max_chunk_size": max(chunk_sizes) if chunk_sizes else 0,
            "chunks_with_tables": sum(
                1 for c in chunks if c["metadata"]["has_table"]
            ),
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "parent_chunk_max_chars": self.parent_chunk_max_chars,
        }

        return chunks, stats

    def save_chunks(self, chunks: List[Dict], output_path: str):
        """Lưu chunks ra file JSON"""
        import json
        from pathlib import Path

        print(f"💾 Đang lưu {len(chunks)} chunks...")
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(chunks, f, ensure_ascii=False, indent=2)

        print(f"✅ Đã lưu: {output_path}")

    def print_stats(self, stats: Dict):
        """In thống kê chunking"""
        print(f"\n📊 Recursive Chunking Statistics:")
        print(
            f"   - Chunk size: {stats['chunk_size']}, Overlap: {stats['chunk_overlap']}"
        )
        print(f"   - Tổng chunks: {stats['total_chunks']}")
        if stats.get("parent_chunks"):
            print(f"   - Parent chunks: {stats['parent_chunks']}")
            print(f"   - Child chunks: {stats['child_chunks']}")
            print(f"   - Orphan chunks: {stats['orphan_chunks']}")
            print(
                f"   - Parent max chars: {stats.get('parent_chunk_max_chars', 'N/A')}"
            )
        print(f"   - Avg size: {stats['avg_chunk_size']:.0f} chars")
        print(f"   - Min size: {stats['min_chunk_size']} chars")
        print(f"   - Max size: {stats['max_chunk_size']} chars")
        print(f"   - Chunks có bảng: {stats['chunks_with_tables']}")
