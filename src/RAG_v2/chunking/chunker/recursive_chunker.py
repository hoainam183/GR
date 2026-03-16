"""
Recursive Character Text Splitter Chunker

Chunker dùng RecursiveCharacterTextSplitter từ LangChain.
Phù hợp cho các tài liệu không có cấu trúc pháp lý (Điều/Chương),
ví dụ: Chương trình đào tạo (CTDT), tài liệu hướng dẫn, FAQ, v.v.

Strategy:
- Tách văn bản theo cấu trúc H2 section: mỗi section H2 là 1 parent chunk
- Nội dung trong mỗi section được tách thành child chunks (không overlap)
- Parent-child đảm bảo child.chunk_size ≤ parent.chunk_size
- Không dùng chunk_overlap vì ranh giới H2 đã cung cấp ngữ cảnh, overlap gây duplicate
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
        chunk_size: Kích thước tối đa của mỗi child chunk (default: 1024)
        chunk_overlap: Overlap giữa chunks (default: 0 — không dùng overlap vì
            strategy split trong từng H2 section; overlap gây duplicate chunks)
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
        chunk_overlap: int = 0,
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
            # Thuần text → re-split bằng text_splitter (không overlap)
            sub_splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=0,
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

    def _deduplicate_overlap_headings(self, content: str) -> str:
        """
        Remove duplicate headings caused by context injection + small-chunk merging.
        When the same heading (same level and text) appears twice in a chunk,
        remove only the second (duplicate) heading line, preserving all content
        before and after it.

        NOTE: The old strategy (remove everything from first to second heading)
        caused data loss when _inject_section_context added a heading prefix to a
        small chunk that was then merged with the preceding chunk. In that case
        'before' was empty (first heading at pos 0) and all of the first chunk's
        content was silently dropped. The new strategy only removes the duplicate
        heading line itself.
        """
        heading_re = re.compile(r"^(#{1,4})\s+(.+)$", re.MULTILINE)
        all_matches = list(heading_re.finditer(content))

        if len(all_matches) < 2:
            return content

        seen = {}
        for m in all_matches:
            key = (len(m.group(1)), m.group(2).strip())
            if key in seen:
                # Remove only the duplicate (second) heading line; keep all content
                before = content[: m.start()].rstrip("\n")
                after = content[m.end() :].lstrip("\n")
                if before and after:
                    content = before + "\n\n" + after
                elif before:
                    content = before
                else:
                    content = after
                return content.strip()
            seen[key] = m

        return content

    def _fix_section_metadata_from_content(self, chunk: Dict) -> None:
        """
        Override section_h2/h3/h4 metadata based on actual headings found
        in the chunk content. Uses the last heading of each level as the
        'effective' heading, preventing stale metadata when chunks span
        section boundaries due to overlap.
        """
        content = chunk["content"]
        metadata = chunk["metadata"]

        h2_matches = re.findall(r"^## (.+)$", content, re.MULTILINE)
        h3_matches = re.findall(r"^### (.+)$", content, re.MULTILINE)
        h4_matches = re.findall(r"^#### (.+)$", content, re.MULTILINE)

        changed = False

        if h2_matches:
            effective = h2_matches[-1].strip()
            if effective != metadata.get("section_h2"):
                metadata["section_h2"] = effective
                if not h3_matches:
                    metadata["section_h3"] = None
                if not h4_matches:
                    metadata["section_h4"] = None
                changed = True

        if h3_matches:
            effective = h3_matches[-1].strip()
            if effective != metadata.get("section_h3"):
                metadata["section_h3"] = effective
                if not h4_matches:
                    metadata["section_h4"] = None
                changed = True

        if h4_matches:
            effective = h4_matches[-1].strip()
            if effective != metadata.get("section_h4"):
                metadata["section_h4"] = effective
                changed = True

        if changed:
            metadata["hierarchy_path"] = self._build_section_path(
                {
                    "h1": metadata.get("section_h1"),
                    "h2": metadata.get("section_h2"),
                    "h3": metadata.get("section_h3"),
                    "h4": metadata.get("section_h4"),
                }
            )

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

    def _extract_h3_sections(self, text: str) -> List[Dict]:
        """
        Trích xuất các section h3 từ text (thường là nội dung của 1 section h2).
        Trả về list of {title, content, start_pos, end_pos}.
        """
        h3_pattern = re.compile(r"^### (.+)$", re.MULTILINE)
        h3_matches = list(h3_pattern.finditer(text))

        if not h3_matches:
            return []

        sections = []
        for i, m in enumerate(h3_matches):
            start = m.start()
            end = (
                h3_matches[i + 1].start()
                if i + 1 < len(h3_matches)
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

    def _set_chunk_type(self, chunk: Dict) -> None:
        """Đặt chunk_type metadata dựa trên nội dung chunk."""
        if chunk["metadata"].get("chunk_type") == "parent":
            return
        has_table = chunk["metadata"].get("has_table", False)
        has_heading = any(
            l.strip().startswith("#")
            for l in chunk["content"].split("\n")
            if l.strip()
        )
        if has_table:
            chunk["metadata"]["chunk_type"] = (
                "mixed" if has_heading else "table"
            )
        else:
            chunk["metadata"]["chunk_type"] = "text"

    def _find_parent_khoản(
        self, subitem_first_line: str, section_text: str
    ) -> Optional[str]:
        """
        Tìm khoản (numbered item) cha của một sub-item (a), b), c)...) trong section_text.
        Ví dụ: sub-item "b) Đối với sinh viên..." → trả về "3. Căn cứ kế hoạch..."

        Args:
            subitem_first_line: Dòng đầu tiên của sub-item (đã strip whitespace)
            section_text: Toàn bộ text của section đang được xử lý

        Returns:
            Text của khoản cha (dòng intro + continuation nếu multi-line) hoặc None
        """
        # Tìm vị trí của sub-item trong section_text
        search_key = subitem_first_line[:60]
        match = re.search(re.escape(search_key), section_text)
        if not match:
            return None

        text_before = section_text[: match.start()]

        # Tìm numbered item cuối cùng trước sub-item này
        # Pattern: dòng bắt đầu bằng chữ số + dấu chấm + khoảng trắng
        khoản_pattern = re.compile(r"^[ \t]*(\d+\.\s+.+)$", re.MULTILINE)
        khoản_matches = list(khoản_pattern.finditer(text_before))
        if not khoản_matches:
            return None

        last_match = khoản_matches[-1]
        khoản_text = last_match.group(1).strip()

        # Thu thập các dòng continuation (multi-line khoản, trước sub-item đầu tiên)
        khoản_end_pos = last_match.end()
        remainder = text_before[khoản_end_pos:]
        continuation_lines = []
        for line in remainder.split("\n"):
            stripped = line.strip()
            if not stripped:
                if continuation_lines:
                    break  # dừng tại dòng trống đầu tiên sau nội dung
                continue
            # Dừng nếu gặp numbered item mới hoặc sub-item mới
            if re.match(r"^\d+\.\s", stripped) or re.match(
                r"^[a-zđ]\)\s", stripped
            ):
                break
            continuation_lines.append(stripped)

        if continuation_lines:
            khoản_text = khoản_text + " " + " ".join(continuation_lines)

        return khoản_text.strip() or None

    def _inject_khoản_context(
        self, chunks: List[Dict], section_text: str
    ) -> List[Dict]:
        """
        Post-process: với mỗi child chunk bắt đầu bằng sub-item marker (a), b), c)...)
        mà không có context của khoản cha, tự động inject khoản cha vào đầu chunk.

        Giải quyết vấn đề: khi RecursiveCharacterTextSplitter cắt giữa khoản,
        các chunk con như "b) Đối với..." không có context của khoản 3 chứa nó.

        Args:
            chunks: Danh sách child chunks cần xử lý
            section_text: Text gốc của section đang được chunked (dùng để tìm khoản cha)

        Returns:
            Danh sách chunks đã được inject context
        """
        subitem_re = re.compile(r"^[a-zđ]\)\s")

        for chunk in chunks:
            content = chunk["content"]
            lines = content.split("\n")

            # Tìm dòng nội dung đầu tiên (skip headings)
            first_content_line = None
            heading_end_idx = 0
            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    first_content_line = stripped
                    heading_end_idx = i
                    break

            if first_content_line is None:
                continue

            # Chỉ xử lý chunks có dòng đầu là sub-item marker (a), b), ...)
            if not subitem_re.match(first_content_line):
                continue

            # Tìm khoản cha trong section_text
            parent_khoản = self._find_parent_khoản(
                first_content_line, section_text
            )
            if not parent_khoản:
                continue

            # Kiểm tra khoản cha đã có trong chunk chưa
            khoản_key = parent_khoản[:40].strip()
            if khoản_key in content:
                continue

            # Inject: tách heading và body, chèn khoản cha vào giữa
            heading_lines = lines[:heading_end_idx]
            body_lines = lines[heading_end_idx:]
            body = "\n".join(body_lines).strip()

            if heading_lines:
                new_content = (
                    "\n".join(heading_lines)
                    + "\n\n"
                    + parent_khoản
                    + "\n\n"
                    + body
                )
            else:
                new_content = parent_khoản + "\n\n" + body

            chunk["content"] = new_content.strip()
            chunk["metadata"]["chunk_size"] = len(chunk["content"])

        return chunks

    def _split_text_to_chunks(
        self,
        text: str,
        doc_title: Optional[str],
        headings: List[Dict],
        source: str,
        pos_offset: int = 0,
    ) -> List[Dict]:
        """
        Tách một đoạn text thành các child chunks với metadata.

        Được gọi cho từng H2 section riêng biệt để đảm bảo child chunks
        luôn nhỏ hơn hoặc bằng parent chunk (toàn bộ section H2).

        Args:
            text: Đoạn text cần tách (1 section H2, preamble, hoặc toàn bộ doc)
            doc_title: Tiêu đề document gốc
            headings: Danh sách headings trong TOÀN BỘ document (start_pos tuyệt đối)
            source: Tên file nguồn
            pos_offset: Vị trí bắt đầu của đoạn text này trong document gốc,
                        dùng để xác định section context chính xác.

        Returns:
            List of chunk dicts (chưa có parent_id, chunk_index, chunk_type)
        """
        if not text or not text.strip():
            return []

        # Bảo vệ bảng nếu cần
        table_map = {}
        processing_text = text
        if self.protect_tables:
            processing_text, table_map = self._protect_tables_in_text(text)

        # Split text (chunk_overlap=0 — đã cấu hình trong text_splitter)
        raw_chunks = self.text_splitter.split_text(processing_text)

        # Merge tiny chunks vào chunk kế tiếp
        merged_raw = []
        buffer = ""
        for rc in raw_chunks:
            if buffer:
                rc = buffer + "\n" + rc
                buffer = ""
            if len(rc.strip()) < self.min_chunk_size:
                buffer = rc
            else:
                merged_raw.append(rc)
        if buffer:
            if merged_raw:
                merged_raw[-1] = merged_raw[-1] + "\n" + buffer
            else:
                merged_raw.append(buffer)
        raw_chunks = merged_raw

        # Tạo chunks với metadata
        chunks = []
        text_pos = 0

        for idx, raw_content in enumerate(raw_chunks):
            content = raw_content
            if self.protect_tables and table_map:
                content = self._restore_tables(raw_content, table_map)

            # Tìm vị trí trong text cục bộ, dùng pos_offset để tra cứu section metadata
            non_table_lines = [
                l
                for l in content.split("\n")
                if l.strip() and not l.strip().startswith("|")
            ]
            search_key = (
                non_table_lines[0][:100].strip()
                if non_table_lines
                else content[:100].strip()
            )
            found_pos = text.find(search_key, text_pos)
            if found_pos >= 0:
                text_pos = found_pos

            # Dùng vị trí tuyệt đối để tra section metadata trong full document
            global_pos = text_pos + pos_offset
            section_ctx = self._find_section_for_position(global_pos, headings)
            hierarchy_path = self._build_section_path(section_ctx)
            has_table = self._detect_table_in_chunk(content)

            chunk = {
                "id": str(uuid.uuid4()),
                "chunk_id": "",  # re-indexed sau
                "readable_id": "",
                "content": content.strip(),
                "metadata": {
                    "doc_type": "curriculum",
                    "level": "child",
                    "doc_title": doc_title,
                    "source": source,
                    "section_h1": section_ctx.get("h1"),
                    "section_h2": section_ctx.get("h2"),
                    "section_h3": section_ctx.get("h3"),
                    "section_h4": section_ctx.get("h4"),
                    "hierarchy_path": hierarchy_path,
                    "chunk_index": 0,
                    "total_chunks": 0,
                    "chunk_size": len(content.strip()),
                    "has_table": has_table,
                    "parent_id": None,  # set bởi caller
                    "chunk_type": "text",  # set bởi caller via _set_chunk_type
                    "effective_date": None,
                    "expiry_date": None,
                    "applicable_cohort": None,
                    "applicable_major": None,
                    "document_type": "curriculum",
                },
            }
            chunks.append(chunk)
            text_pos += len(content)

        # Post-process: ghép lại table header cho chunk bắt đầu giữa bảng
        chunks = self._fix_mid_table_chunks(chunks)

        # Post-process: tách các chunk quá lớn (> chunk_size * 1.3)
        oversized_threshold = int(self.chunk_size * 1.3)
        final_chunks = []
        for chunk in chunks:
            if chunk["metadata"]["chunk_size"] > oversized_threshold:
                sub_contents = self._split_oversized_chunk(chunk["content"])
                for sub_content in sub_contents:
                    sub_content = sub_content.strip()
                    if not sub_content:
                        continue
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
                        sc = self._find_section_for_position(
                            fp + pos_offset, headings
                        )
                    else:
                        sc = {
                            "h1": chunk["metadata"]["section_h1"],
                            "h2": chunk["metadata"]["section_h2"],
                            "h3": chunk["metadata"]["section_h3"],
                            "h4": chunk["metadata"]["section_h4"],
                        }
                    hp = self._build_section_path(sc)
                    new_chunk = {
                        "id": str(uuid.uuid4()),
                        "chunk_id": "",
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

        # Fix stale section metadata dựa trên headings thực tế trong content
        for chunk in chunks:
            self._fix_section_metadata_from_content(chunk)

        # Inject heading context cho chunks không có heading (chỉ có table rows)
        if self.add_section_context:
            chunks = self._inject_section_context(chunks)

        # Merge chunks quá nhỏ vào chunk liền kề
        min_merge_size = max(self.min_chunk_size, 200)
        merge_limit = oversized_threshold
        merged = []
        for chunk in chunks:
            if (
                merged
                and merged[-1]["metadata"]["chunk_size"] < min_merge_size
                and merged[-1]["metadata"]["chunk_size"]
                + chunk["metadata"]["chunk_size"]
                <= merge_limit
            ):
                prev = merged.pop()
                chunk["content"] = prev["content"] + "\n\n" + chunk["content"]
                chunk["metadata"]["chunk_size"] = len(chunk["content"])
                chunk["metadata"]["has_table"] = (
                    prev["metadata"]["has_table"]
                    or chunk["metadata"]["has_table"]
                )
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

        # Deduplicate duplicate headings introduced by merging
        for chunk in chunks:
            original = chunk["content"]
            chunk["content"] = self._deduplicate_overlap_headings(
                chunk["content"]
            )
            if chunk["content"] != original:
                chunk["metadata"]["chunk_size"] = len(chunk["content"])
                self._fix_section_metadata_from_content(chunk)

        # Inject khoản (numbered-item) context for chunks starting with sub-item
        # markers (a), b), c)...) that lack their parent numbered-item intro.
        chunks = self._inject_khoản_context(chunks, text)

        return chunks

    def chunk_document(
        self, text: str, source: str = ""
    ) -> Tuple[List[Dict], Dict]:
        """
        Main chunking pipeline.

        Strategy: Structure-based parent-child chunking.
        - H2 sections → parent chunks (toàn bộ nội dung section)
        - Nội dung trong mỗi H2 section → child chunks (split với chunk_overlap=0)
        - Đảm bảo child.chunk_size ≤ parent.chunk_size
        - Không overlap: ranh giới H2 đã cung cấp ngữ cảnh

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
        h2_sections = self._extract_h2_sections(text)

        result_chunks: List[Dict] = []

        if not h2_sections:
            # Không có cấu trúc H2: toàn bộ document là orphan children
            orphans = self._split_text_to_chunks(
                text, doc_title, headings, source, pos_offset=0
            )
            for cc in orphans:
                cc["metadata"].setdefault("parent_id", None)
                self._set_chunk_type(cc)
            result_chunks = orphans
        else:
            # Preamble: text trước section H2 đầu tiên
            preamble_end = h2_sections[0]["start_pos"]
            preamble = text[:preamble_end].strip()
            if preamble:
                orphans = self._split_text_to_chunks(
                    preamble, doc_title, headings, source, pos_offset=0
                )
                for cc in orphans:
                    cc["metadata"].setdefault("parent_id", None)
                    self._set_chunk_type(cc)
                result_chunks.extend(orphans)

            # Xử lý từng H2 section: tạo parent + children từ trong section đó
            # Đảm bảo child.chunk_size ≤ parent.chunk_size vì children được split
            # từ nội dung section (không phải toàn bộ document)
            for section in h2_sections:
                section_content = section["content"]

                # Kiểm tra nếu H2 section quá lớn → fallback về H3 làm parent
                if len(section_content) > self.parent_chunk_max_chars:
                    h3_sections = self._extract_h3_sections(section_content)
                else:
                    h3_sections = []

                if h3_sections:
                    # --- Fallback: dùng H3 làm parent thay cho H2 ---
                    # Preamble trong H2 (text trước H3 đầu tiên)
                    h3_preamble_end = h3_sections[0]["start_pos"]
                    h2_preamble = section_content[:h3_preamble_end].strip()
                    if h2_preamble:
                        orphan_preamble = self._split_text_to_chunks(
                            h2_preamble,
                            doc_title,
                            headings,
                            source,
                            pos_offset=section["start_pos"],
                        )
                        for cc in orphan_preamble:
                            cc["metadata"].setdefault("parent_id", None)
                            self._set_chunk_type(cc)
                        result_chunks.extend(orphan_preamble)

                    for h3_section in h3_sections:
                        h3_abs_start = (
                            section["start_pos"] + h3_section["start_pos"]
                        )
                        h3_content = h3_section["content"]
                        truncated_h3 = self._truncate_content(
                            h3_content, self.parent_chunk_max_chars
                        )
                        h3_ctx = self._find_section_for_position(
                            h3_abs_start, headings
                        )
                        h3_hierarchy = self._build_section_path(h3_ctx)
                        h3_has_table = self._detect_table_in_chunk(truncated_h3)

                        h3_parent = {
                            "id": str(uuid.uuid4()),
                            "chunk_id": "",
                            "readable_id": "",
                            "content": truncated_h3,
                            "metadata": {
                                "doc_type": "curriculum",
                                "level": "parent",
                                "doc_title": doc_title,
                                "source": source,
                                "section_h1": h3_ctx.get("h1"),
                                "section_h2": h3_ctx.get("h2"),
                                "section_h3": h3_ctx.get("h3"),
                                "section_h4": None,
                                "hierarchy_path": h3_hierarchy,
                                "chunk_index": 0,
                                "total_chunks": 0,
                                "chunk_size": len(truncated_h3),
                                "chunk_type": "parent",
                                "has_table": h3_has_table,
                                "parent_id": None,
                                "child_count": 0,
                                "effective_date": None,
                                "expiry_date": None,
                                "applicable_cohort": None,
                                "applicable_major": None,
                                "document_type": "curriculum",
                            },
                        }

                        h3_children = self._split_text_to_chunks(
                            h3_content,
                            doc_title,
                            headings,
                            source,
                            pos_offset=h3_abs_start,
                        )
                        h3_parent["metadata"]["child_count"] = len(h3_children)
                        for cc in h3_children:
                            cc["metadata"]["parent_id"] = h3_parent["id"]
                            self._set_chunk_type(cc)

                        result_chunks.append(h3_parent)
                        result_chunks.extend(h3_children)

                else:
                    # --- Hành vi gốc: dùng H2 làm parent ---
                    truncated_content = self._truncate_content(
                        section_content, self.parent_chunk_max_chars
                    )
                    section_ctx = self._find_section_for_position(
                        section["start_pos"], headings
                    )
                    hierarchy_path = self._build_section_path(section_ctx)
                    has_table = self._detect_table_in_chunk(truncated_content)

                    parent = {
                        "id": str(uuid.uuid4()),
                        "chunk_id": "",
                        "readable_id": "",
                        "content": truncated_content,
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
                            "chunk_index": 0,
                            "total_chunks": 0,
                            "chunk_size": len(truncated_content),
                            "chunk_type": "parent",
                            "has_table": has_table,
                            "parent_id": None,
                            "child_count": 0,
                            "effective_date": None,
                            "expiry_date": None,
                            "applicable_cohort": None,
                            "applicable_major": None,
                            "document_type": "curriculum",
                        },
                    }

                    # Split NỘI DUNG section → children luôn nhỏ hơn parent
                    children = self._split_text_to_chunks(
                        section_content,
                        doc_title,
                        headings,
                        source,
                        pos_offset=section["start_pos"],
                    )
                    parent["metadata"]["child_count"] = len(children)
                    for cc in children:
                        cc["metadata"]["parent_id"] = parent["id"]
                        self._set_chunk_type(cc)

                    result_chunks.append(parent)
                    result_chunks.extend(children)

        # Re-index tất cả chunks
        for idx, chunk in enumerate(result_chunks):
            readable_id = f"chunk_{idx:04d}"
            chunk["chunk_id"] = readable_id
            chunk["readable_id"] = readable_id
            chunk["metadata"]["chunk_index"] = idx
            chunk["metadata"]["total_chunks"] = len(result_chunks)

        # Thống kê
        chunk_sizes = [c["metadata"]["chunk_size"] for c in result_chunks]
        parent_count = sum(
            1 for c in result_chunks if c["metadata"].get("level") == "parent"
        )
        child_count = sum(
            1
            for c in result_chunks
            if c["metadata"].get("parent_id") is not None
        )
        stats = {
            "total_chunks": len(result_chunks),
            "parent_chunks": parent_count,
            "child_chunks": child_count,
            "orphan_chunks": len(result_chunks) - parent_count - child_count,
            "avg_chunk_size": (
                sum(chunk_sizes) / len(chunk_sizes) if chunk_sizes else 0
            ),
            "min_chunk_size": min(chunk_sizes) if chunk_sizes else 0,
            "max_chunk_size": max(chunk_sizes) if chunk_sizes else 0,
            "chunks_with_tables": sum(
                1 for c in result_chunks if c["metadata"]["has_table"]
            ),
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "parent_chunk_max_chars": self.parent_chunk_max_chars,
        }

        return result_chunks, stats

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
