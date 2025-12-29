from typing import List, Dict, Optional
import re
from pathlib import Path
import json


# Bước 3: Chunking với LangChain
def extract_footnotes_from_docling_json(json_path: str) -> dict:
    """
    Extract footnotes từ Docling JSON metadata

    Args:
        json_path: Đường dẫn file JSON metadata từ Docling

    Returns:
        dict: {footnote_number: {content, page_no, full_text}}
    """
    print(f"📖 Đọc Docling metadata từ: {json_path}")

    with open(json_path, "r", encoding="utf-8") as f:
        docling_metadata = json.load(f)

    footnotes = {}

    # Traverse metadata tree để tìm footnotes
    def traverse(node):
        if isinstance(node, dict):
            # Check nếu là footnote
            if node.get("label") == "footnote":
                text = node.get("text", "")
                # Extract footnote number (e.g., "1  Quy chế..." -> "1")
                match = re.match(r"^(\d+)\s+(.+)", text, re.DOTALL)
                if match:
                    number = match.group(1)
                    content = match.group(2).strip()

                    # Get page number from prov
                    page_no = None
                    if "prov" in node and len(node["prov"]) > 0:
                        page_no = node["prov"][0].get("page_no")

                    footnotes[number] = {
                        "content": content,
                        "page_no": page_no,
                        "full_text": text,
                    }

            # Traverse children
            for key, value in node.items():
                if isinstance(value, (dict, list)):
                    traverse(value)

        elif isinstance(node, list):
            for item in node:
                traverse(item)

    traverse(docling_metadata)
    for key, value in footnotes.items():
        if isinstance(value, dict):
            for field in ["content", "full_text"]:
                if field in value and isinstance(value[field], str):
                    value[field] = re.sub(
                        r"\s{2,}", " ", (value[field])
                    ).strip()
    return footnotes


def remove_footnotes_from_markdown(markdown_text: str, footnotes: Dict) -> str:
    """
    Xóa footnotes khỏi markdown content

    Args:
        markdown_text: Full markdown text
        footnotes: Dict footnotes từ extract_footnotes_from_docling_json()
                   Format: {
                       "1": {
                           "content": "...",
                           "page_no": 4,
                           "full_text": "1  Quy chế..."
                       }
                   }

    Returns:
        Cleaned markdown text (không có footnotes)
    """
    print(f"\n🧹 Bắt đầu xóa footnotes khỏi markdown...")
    print(f"📊 Input markdown size: {len(markdown_text)} chars")
    print(f"📝 Số footnotes cần xóa: {len(footnotes)}")

    cleaned_text = markdown_text
    removed_count = 0
    not_found = []

    # Sort footnotes theo số thứ tự để xóa có thứ tự
    sorted_footnotes = sorted(footnotes.items(), key=lambda x: int(x[0]))

    for number, data in sorted_footnotes:
        full_text = data["full_text"]
        original_length = len(cleaned_text)

        print(f"\n🔍 Đang xóa footnote {number}:")
        print(f"   Text: {full_text[:60]}...")

        # Try multiple patterns để tìm và xóa footnote
        patterns = [
            full_text,  # Exact match
            f"\n\n{full_text}",  # Với double newline prefix
            f"\n{full_text}",  # Với single newline prefix
            f"{full_text}\n\n",  # Với double newline suffix
            f"{full_text}\n",  # Với single newline suffix
            f"\n\n{full_text}\n\n",  # Với both sides double newline
            f"\n{full_text}\n",  # Với both sides single newline
        ]

        found = False
        for idx, pattern in enumerate(patterns):
            if pattern in cleaned_text:
                cleaned_text = cleaned_text.replace(
                    pattern, "", 1
                )  # Replace only first occurrence
                new_length = len(cleaned_text)
                removed_chars = original_length - new_length

                print(
                    f"   ✅ Found với pattern {idx} - Xóa {removed_chars} chars"
                )
                removed_count += 1
                found = True
                break

        if not found:
            print(f"   ❌ Không tìm thấy trong markdown")
            not_found.append(number)

    # Clean up multiple consecutive newlines (tối đa 2 newlines liên tiếp)
    print(f"\n🧼 Cleaning up multiple newlines...")
    before_cleanup = len(cleaned_text)
    cleaned_text = re.sub(r"\n{3,}", "\n\n", cleaned_text)
    after_cleanup = len(cleaned_text)
    print(f"   Removed {before_cleanup - after_cleanup} extra newline chars")

    # Summary
    print(f"\n" + "=" * 60)
    print(f"✅ SUMMARY:")
    print(f"   - Original size: {len(markdown_text)} chars")
    print(f"   - Cleaned size: {len(cleaned_text)} chars")
    print(f"   - Removed: {len(markdown_text) - len(cleaned_text)} chars")
    print(f"   - Footnotes removed: {removed_count}/{len(footnotes)}")

    if not_found:
        print(f"   ⚠️  Footnotes không tìm thấy: {not_found}")
    print("=" * 60 + "\n")

    return cleaned_text


# ============= TEST FUNCTION =============


def test_remove_footnotes():
    """
    Hàm test để kiểm tra remove_footnotes_from_markdown
    """
    # Sample markdown text
    markdown_text = """# Quy chế Đào tạo

2. Chương trình đào tạo (sau đây gọi tắt là CTĐT) được xây dựng theo đơn vị tín chỉ và là bản thiết kế cho toàn bộ quá trình đào tạo của một ngành. Chương trình thể hiện rõ trình độ đào tạo; đối tượng đào tạo, điều kiện nhập học và điều kiện tốt nghiệp; mục tiêu đào tạo, chuẩn kiến thức, kỹ năng của người học khi tốt nghiệp; nội dung (chương trình giảng dạy); kế hoạch đào tạo theo thời gian học tập chuẩn; phương pháp và hình thức đào tạo; cách thức đánh giá kết quả học tập; các điều kiện thực hiện chương trình.

1 Quy chế đào tạo trình độ đại học, ban hành theo Thông tư số 08/2021/TT-BGDĐT ngày 18 tháng 3 năm 2021 của Bộ trưởng Bộ Giáo dục và Đào tạo.

2 Quy chế tuyển sinh và đào tạo trình độ thạc sĩ, ban hành theo Thông tư số 23/2021/TT-BGDĐT ngày 30 tháng 8 năm 2021 của Bộ trưởng Bộ Giáo dục và Đào tạo.     

3 Quy chế tuyển sinh và đào tạo trình độ tiến sĩ, ban hành theo Thông tư số 18/2021/TT-BGDĐT ngày 28 tháng 6 năm 2021 của Bộ trưởng Bộ Giáo dục và Đào tạo.     

4 Danh mục thống kê ngành đào tạo của giáo dục đại học ban hành theo Thông tư số 09/2022/TT-BGDĐT ngày 06 tháng 6 năm 2022 của Bộ trưởng Bộ Giáo dục và Đào tạo.

3. CTĐT tích hợp là chương trình được thiết kế tổng thể theo hướng tích hợp kiến thức của hai bậc trình độ, đảm bảo học tập liên tục giữa các bậc đào tạo nhằm tối ưu hóa thời gian đào tạo cho người học. Chương trình tích hợp cử nhân-kỹ sư có thời gian thiết kế là 5,5 năm và khối lượng học tập 180 TC; bao gồm hai bậc trình độ: Cử nhân (thời gian đào tạo 4 năm, trình độ đại học, cấp bằng cử nhân) và Kỹ sư (thời gian đào tạo 1,5 năm, cấp bằng kỹ sư, tương đương trình độ thạc sĩ). Tính tích hợp được thể hiện bằng việc thiết kế các mô đun học phần trong chương trình cử nhân có kiến thức nền tảng liên quan chặt chẽ đến các chuyên ngành kỹ sư.

Nội dung khác...
"""

    # Sample footnotes dict (như bạn đã có)
    footnotes = {
        "1": {
            "content": "Quy chế đào tạo trình độ đại học, ban hành theo Thông tư số 08/2021/TT-BGDĐT ngày 18 tháng 3 năm 2021 của Bộ trưởng Bộ Giáo dục và Đào tạo.",
            "page_no": 4,
            "full_text": "1 Quy chế đào tạo trình độ đại học, ban hành theo Thông tư số 08/2021/TT-BGDĐT ngày 18 tháng 3 năm 2021 của Bộ trưởng Bộ Giáo dục và Đào tạo.",
        },
        "2": {
            "content": "Quy chế tuyển sinh và đào tạo trình độ thạc sĩ, ban hành theo Thông tư số 23/2021/TT-BGDĐT ngày 30 tháng 8 năm 2021 của Bộ trưởng Bộ Giáo dục và Đào tạo.",
            "page_no": 4,
            "full_text": "2 Quy chế tuyển sinh và đào tạo trình độ thạc sĩ, ban hành theo Thông tư số 23/2021/TT-BGDĐT ngày 30 tháng 8 năm 2021 của Bộ trưởng Bộ Giáo dục và Đào tạo.",
        },
        "3": {
            "content": "Quy chế tuyển sinh và đào tạo trình độ tiến sĩ, ban hành theo Thông tư số 18/2021/TT-BGDĐT ngày 28 tháng 6 năm 2021 của Bộ trưởng Bộ Giáo dục và Đào tạo.",
            "page_no": 4,
            "full_text": "3 Quy chế tuyển sinh và đào tạo trình độ tiến sĩ, ban hành theo Thông tư số 18/2021/TT-BGDĐT ngày 28 tháng 6 năm 2021 của Bộ trưởng Bộ Giáo dục và Đào tạo.",
        },
    }

    # Test remove function
    cleaned = remove_footnotes_from_markdown(markdown_text, footnotes)

    # Print result
    print("\n" + "=" * 60)
    print("📄 CLEANED MARKDOWN:")
    print("=" * 60)
    print(cleaned)
    print("=" * 60)

    # Verify footnotes removed
    print("\n🔍 VERIFICATION:")
    for number in footnotes.keys():
        still_exists = footnotes[number]["full_text"] in cleaned
        status = "❌ VẪN CÒN" if still_exists else "✅ ĐÃ XÓA"
        print(f"   Footnote {number}: {status}")


def extract_footnote_numbers(text: str) -> List[str]:
    """
    Trích xuất các số footnote từ text
    Pattern: số đơn lẻ ở cuối câu, trước dấu chấm hoặc giữa các số khác

    Args:
        text: Nội dung cần tìm footnote

    Returns:
        List các số footnote tìm thấy
    """
    # Pattern: số nằm giữa khoảng trắng, có thể theo sau là số khác hoặc dấu chấm
    # VD: "ban hành 1 2 3 ." hoặc "quản lý 4 ."
    pattern = r"\s(\d+)(?=\s+\d+|\s*\.)"
    matches = re.findall(pattern, text)
    return list(set(matches))  # Loại bỏ duplicate


def parse_legal_document_structure(
    markdown_text: str, footnotes: Optional[Dict[str, str]] = None
) -> List[Dict]:
    """
    Parse văn bản pháp lý với cấu trúc phân cấp đầy đủ

    Structure hierarchy:
    - Title (Tiêu đề: QUY CHẾ ĐÀO TẠO)
    - Chapter (Chương: # CHƯƠNG I)
    - Article (Điều: ## Điều 1)
    - Clause (Khoản: 1., 2., 3.)

    Args:
        markdown_text: Nội dung markdown
        footnotes: Dict mapping footnote number -> footnote content

    Returns:
        List of chunks với metadata đầy đủ
    """
    chunks = []

    # State tracking
    current_title = None
    current_chapter = None
    current_chapter_full = None
    current_article = None
    current_article_full = None

    # Temporary storage cho clause hiện tại
    current_clause_num = None
    current_clause_lines = []

    lines = markdown_text.split("\n")

    def save_current_clause():
        """Lưu khoản hiện tại vào chunks"""
        if not current_clause_lines:
            return

        content = "\n".join(current_clause_lines).strip()
        if not content:
            return

        # Trích xuất footnote numbers
        footnote_refs = extract_footnote_numbers(content)

        # Build metadata
        metadata = {
            "doc_type": "legal_document",
            "level": "clause",
            "title": current_title,
            "chapter": current_chapter,
            "chapter_full": current_chapter_full,
            "article": current_article,
            "article_full": current_article_full,
            "clause": current_clause_num,
            "chunk_size": len(content),
        }

        # Add hierarchy path for easy filtering
        hierarchy_parts = []
        if current_chapter:
            hierarchy_parts.append(current_chapter)
        if current_article:
            hierarchy_parts.append(current_article)
        if current_clause_num:
            hierarchy_parts.append(f"Khoản {current_clause_num}")

        metadata["hierarchy_path"] = " > ".join(hierarchy_parts)

        # Add footnotes if available
        if footnote_refs:
            metadata["footnote_refs"] = footnote_refs
            if footnotes:
                metadata["footnotes"] = {
                    num: footnotes.get(num, "") for num in footnote_refs
                }

        chunks.append({"content": content, "metadata": metadata})

    for line in lines:
        line_stripped = line.strip()

        # Skip empty lines
        if not line_stripped:
            continue

        # Detect Title (##) - không phải Điều
        if line_stripped.startswith("## ") and not line_stripped.startswith(
            "## Điều"
        ):
            current_title = line_stripped.replace("##", "").strip()
            continue

        # Detect Chapter (# CHƯƠNG)
        if re.match(r"^#\s+CHƯƠNG", line_stripped):
            # Save previous clause before starting new chapter
            save_current_clause()
            current_clause_lines = []
            current_clause_num = None

            current_chapter_full = line_stripped.replace("#", "").strip()
            # Extract chapter number: "CHƯƠNG I" -> "I"
            chapter_match = re.search(
                r"CHƯƠNG\s+([IVX]+|\d+)", current_chapter_full
            )
            current_chapter = (
                chapter_match.group(1)
                if chapter_match
                else current_chapter_full
            )
            current_article = None
            current_article_full = None
            continue

        # Detect Article (## Điều)
        if re.match(r"^##\s+Điều", line_stripped):
            # Save previous clause before starting new article
            save_current_clause()
            current_clause_lines = []
            current_clause_num = None

            current_article_full = line_stripped.replace("##", "").strip()
            # Extract article number and title: "Điều 1. Phạm vi..." -> "Điều 1"
            article_match = re.match(r"(Điều\s+\d+)", current_article_full)
            current_article = (
                article_match.group(1)
                if article_match
                else current_article_full
            )
            continue

        # Detect Clause (1., 2., 3.)
        clause_match = re.match(
            r"^(\d+)\.\s+([A-ZĐÁÀẢÃẠÂẤẦẨẪẬĂẮẰẲẴẶÉÈẺẼẸÊẾỀỂỄỆ].*)", line_stripped
        )
        if clause_match:
            # Save previous clause
            save_current_clause()

            # Start new clause
            current_clause_num = clause_match.group(1)
            current_clause_lines = [line_stripped]
            continue

        # Content continuation of current clause
        if current_clause_num:
            current_clause_lines.append(line_stripped)

    # Save last clause
    save_current_clause()

    return chunks


def handle_articles_without_clauses(chunks: List[Dict]) -> List[Dict]:
    """
    Xử lý các Điều không có khoản (chỉ có 1 đoạn văn)

    Args:
        chunks: List chunks đã parse

    Returns:
        List chunks đã được xử lý
    """
    # Group chunks by article
    articles = {}
    for chunk in chunks:
        article = chunk["metadata"].get("article")
        if article:
            if article not in articles:
                articles[article] = []
            articles[article].append(chunk)

    # Check các article chỉ có 1 clause hoặc không có clause
    # (có thể cần xử lý đặc biệt)

    return chunks


def split_oversized_chunks(
    chunks: List[Dict], max_chunk_size: int = 1200, chunk_overlap: int = 200
) -> List[Dict]:
    """
    Split các chunks quá lớn thành sub-chunks nhỏ hơn

    Args:
        chunks: List chunks cần xử lý
        max_chunk_size: Kích thước tối đa của chunk
        chunk_overlap: Overlap giữa các sub-chunks

    Returns:
        List chunks đã được split
    """
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=max_chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", ". ", ", ", " ", ""],
    )

    final_chunks = []

    for idx, chunk in enumerate(chunks):
        content = chunk["content"]
        metadata = chunk["metadata"]

        # Nếu chunk quá lớn
        if len(content) > max_chunk_size * 1.5:
            sub_contents = text_splitter.split_text(content)

            for sub_idx, sub_content in enumerate(sub_contents):
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
            final_chunks.append(chunk)

    return final_chunks


def chunk_markdown_with_hierarchy(
    markdown_path: str,
    docling_json_path: str,
    chunk_size: int = 1200,
    chunk_overlap: int = 200,
) -> List[Dict]:
    """
    Main function: Chunk markdown file với preserve hierarchy

    Args:
        markdown_path: Đường dẫn file markdown
        docling_json_path: Đường dẫn file JSON chứa footnotes
        chunk_size: Kích thước chunk tối đa
        chunk_overlap: Số ký tự overlap giữa chunks

    Returns:
        List of chunks với metadata đầy đủ
    """
    print(f"\n🔪 Bắt đầu chunking: {markdown_path}")

    # 1. Đọc markdown
    with open(markdown_path, "r", encoding="utf-8") as f:
        markdown_text = f.read()

    # 2. Extract và remove footnotes
    # (Giả sử bạn đã có 2 hàm này)

    footnotes = extract_footnotes_from_docling_json(docling_json_path)
    cleaned_markdown = remove_footnotes_from_markdown(markdown_text, footnotes)

    print(f"📝 Đã extract {len(footnotes)} footnotes")

    # 3. Parse document structure
    chunks = parse_legal_document_structure(cleaned_markdown, footnotes)
    print(f"📑 Đã parse: {len(chunks)} chunks từ cấu trúc văn bản")

    # 4. Handle special cases
    chunks = handle_articles_without_clauses(chunks)

    # 5. Split oversized chunks
    chunks = split_oversized_chunks(chunks, chunk_size, chunk_overlap)
    print(f"✂️  Đã split chunks lớn: {len(chunks)} chunks cuối cùng")

    # 6. Add chunk IDs
    for idx, chunk in enumerate(chunks):
        chunk["chunk_id"] = f"chunk_{idx:04d}"

        # Add readable ID based on hierarchy
        meta = chunk["metadata"]
        id_parts = []
        if meta.get("chapter"):
            id_parts.append(f"c{meta['chapter']}")
        if meta.get("article"):
            # "Điều 1" -> "a1"
            article_num = re.search(r"\d+", meta["article"])
            if article_num:
                id_parts.append(f"a{article_num.group()}")
        if meta.get("clause"):
            id_parts.append(f"cl{meta['clause']}")

        if id_parts:
            chunk["readable_id"] = "_".join(id_parts)

    # 7. Print statistics
    print("\n📊 Thống kê chunking:")
    print(f"   - Tổng số chunks: {len(chunks)}")

    # Count by level
    levels = {}
    for chunk in chunks:
        level = chunk["metadata"].get("level", "unknown")
        levels[level] = levels.get(level, 0) + 1

    for level, count in levels.items():
        print(f"   - {level}: {count} chunks")

    # Chunk size stats
    sizes = [chunk["metadata"]["chunk_size"] for chunk in chunks]
    print(
        f"   - Chunk size: min={min(sizes)}, max={max(sizes)}, avg={sum(sizes)//len(sizes)}"
    )

    print(f"\n✅ Hoàn thành chunking!\n")

    return chunks


# Bước 4: Enrich Metadata & Extract Keywords
from collections import Counter


def extract_keywords(text: str, top_n: int = 5) -> List[str]:
    """Extract keywords đơn giản với TF"""
    # Loại bỏ stopwords tiếng Việt cơ bản
    stopwords = {
        "là",
        "của",
        "và",
        "có",
        "được",
        "trong",
        "theo",
        "các",
        "để",
        "với",
        "về",
        "này",
        "đó",
        "đã",
        "từ",
        "cho",
        "khi",
        "như",
        "một",
        "trên",
        "bởi",
        "tại",
        "những",
        "người",
        "hoặc",
        "phải",
        "không",
    }

    # Tokenize đơn giản
    words = re.findall(r"\b\w+\b", text.lower())

    # Filter stopwords và từ ngắn
    words = [w for w in words if w not in stopwords and len(w) > 3]

    # Đếm frequency
    word_freq = Counter(words)

    # Return top keywords
    return [word for word, _ in word_freq.most_common(top_n)]


def enrich_chunks_metadata(chunks: List[Dict]) -> List[Dict]:
    """Enrich metadata với đầy đủ thông tin"""

    for chunk in chunks:
        content = chunk["content"]
        metadata = chunk["metadata"]

        # 1. Detect applies_to CHÍNH XÁC
        if (
            "tiến sĩ" in content.lower()
            or "nghiên cứu sinh" in content.lower()
            or "ncs" in content.lower()
        ):
            metadata["applies_to"] = "nghien_cuu_sinh"
        elif "thạc sĩ" in content.lower():
            metadata["applies_to"] = "hoc_vien_thac_si"
        elif "kỹ sư" in content.lower():
            metadata["applies_to"] = "hoc_vien_ky_su"
        elif "sinh viên" in content.lower():
            metadata["applies_to"] = "sinh_vien"
        else:
            metadata["applies_to"] = "chung"

        # 2. Detect content type ĐÚNG
        if "điều kiện" in content.lower():
            if any(
                word in content.lower() for word in ["tốt nghiệp", "bảo vệ"]
            ):
                metadata["content_type"] = "requirement"
            else:
                metadata["content_type"] = "regulation"
        elif "quy trình" in content.lower() or "thủ tục" in content.lower():
            metadata["content_type"] = "procedure"
        elif "hình thức" in content.lower() and "xử lý" in content.lower():
            metadata["content_type"] = "penalty"
        elif "|" in content and "---" in content:
            metadata["content_type"] = "table"
        else:
            metadata["content_type"] = "general"

        # 3. Extract cross-references
        article_refs = re.findall(r"Điều\s+(\d+)", content)
        if article_refs:
            metadata["article_refs"] = list(set(article_refs))

        section_refs = re.findall(r"khoản\s+(\d+)", content.lower())
        if section_refs:
            metadata["section_refs"] = list(set(section_refs))

        # 4. Detect list structure
        if re.search(r"^[a-z]\)", content, re.MULTILINE):
            metadata["has_list"] = True
            metadata["list_type"] = "alphabetic"
        elif re.search(r"^\d+\.", content, re.MULTILINE):
            metadata["has_list"] = True
            metadata["list_type"] = "numeric"

        # 5. Mark incomplete chunks
        if content.strip().startswith(("-", "a)", "b)", "c)")):
            metadata["requires_context"] = True
            metadata["warning"] = (
                "Chunk bắt đầu giữa list, cần đọc chunks trước"
            )

        # 6. Extract entities
        metadata["entities"] = {
            "numbers": re.findall(
                r"\d+[,.]?\d*\s*(?:TC|điểm|tháng|năm|tuần)", content
            ),
            "deadlines": re.findall(
                r"trong (?:vòng|thời hạn) \d+.*?(?:ngày|tháng|tuần)", content
            ),
        }

    return chunks


# Bước 5: Save Chunks và Validate
def save_chunks(chunks: List[Dict], output_path: str = "./output/chunks.json"):
    """Lưu chunks ra file JSON"""
    print(f"💾 Đang lưu {len(chunks)} chunks...")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)

    print(f"✅ Đã lưu: {output_path}\n")


def validate_chunks(chunks: List[Dict]):
    """Validate chất lượng chunks"""
    print("🔍 Validating chunks...\n")

    # Thống kê
    total_chunks = len(chunks)
    chunk_sizes = [c["metadata"]["chunk_size"] for c in chunks]
    avg_size = sum(chunk_sizes) / len(chunk_sizes)

    # Đếm theo content type
    content_types = Counter(
        [c["metadata"].get("content_type", "unknown") for c in chunks]
    )

    # Đếm footnotes
    chunks_with_footnotes = sum(
        1 for c in chunks if c["metadata"].get("footnote_refs")
    )

    print(f"📊 Validation Results:")
    print(f"   - Tổng chunks: {total_chunks}")
    print(f"   - Avg chunk size: {avg_size:.0f} chars")
    print(f"   - Min size: {min(chunk_sizes)}")
    print(f"   - Max size: {max(chunk_sizes)}")
    print(f"   - Chunks có footnotes: {chunks_with_footnotes}")
    print(f"\n   Content types:")
    for ctype, count in content_types.most_common():
        print(f"      {ctype}: {count}")

    # Warning nếu có chunks quá lớn/nhỏ
    too_large = [c for c in chunks if c["metadata"]["chunk_size"] > 1000]
    too_small = [c for c in chunks if c["metadata"]["chunk_size"] < 100]

    if too_large:
        print(f"\n⚠️  Warning: {len(too_large)} chunks > 1000 chars")
    if too_small:
        print(f"⚠️  Warning: {len(too_small)} chunks < 100 chars")


# Test chunking
def main_pipeline(pdf_path: str, output_dir: str = "../chunks_by_articles"):
    """
    Pipeline đầy đủ: PDF → Markdown → Chunks
    """
    print("=" * 60)
    print("🚀 DOCLING CHUNKING PIPELINE")
    print("=" * 60 + "\n")

    # Step 1: Convert PDF to Markdown
    print("STEP 1: Converting PDF to Markdown")
    print("-" * 60)
    # stats = convert_pdf_to_markdown(pdf_path, output_dir)
    markdown_path = "../output_docling_clean/QCDT_2025_5445_QD-DHBK.clean.md"

    # Step 2: Chunk Markdown
    print("\nSTEP 2: Chunking Markdown")
    print("-" * 60)
    docling_json_path = "../output_docling/QCDT_2025_5445_QD-DHBK_metadata.json"
    chunks = chunk_markdown_with_hierarchy(
        markdown_path, docling_json_path, chunk_size=1200, chunk_overlap=200
    )

    # Step 3: Enrich Metadata
    print("STEP 3: Enriching Metadata")
    print("-" * 60)
    chunks = enrich_chunks_metadata(chunks)

    # Step 4: Validate
    print("STEP 4: Validating Chunks")
    print("-" * 60)
    validate_chunks(chunks)

    # Step 5: Save
    print("\nSTEP 5: Saving Chunks")
    print("-" * 60)
    chunks_path = Path(output_dir) / "chunks.json"
    save_chunks(chunks, str(chunks_path))

    # Summary
    print("\n" + "=" * 60)
    print("✅ PIPELINE COMPLETED!")
    print("=" * 60)
    print(f"\nOutput files:")
    print(f"   📄 Markdown: {markdown_path}")
    print(f"   📦 Chunks: {chunks_path}")
    # print(f"   📊 Metadata: {stats['json_path']}")
    print(f"\nTotal chunks: {len(chunks)}")
    print("=" * 60)

    return chunks


# Bước 7: Utility Functions để Explore Chunks
def search_chunks(chunks: List[Dict], query: str) -> List[Dict]:
    """Tìm kiếm chunks theo keyword"""
    query_lower = query.lower()
    results = []

    for chunk in chunks:
        if query_lower in chunk["content"].lower():
            results.append(chunk)

    return results


def get_chunk_by_article(chunks: List[Dict], article_number: int) -> List[Dict]:
    """Lấy chunks theo số Điều"""
    results = []

    for chunk in chunks:
        article = chunk["metadata"].get("article", "")
        if f"Điều {article_number}" in article:
            results.append(chunk)

    return results


def print_chunk_preview(chunk: Dict):
    """In preview của một chunk"""
    print("\n" + "=" * 60)
    print(f"Chunk ID: {chunk['chunk_id']}")
    print("-" * 60)
    print(
        f"Metadata: {json.dumps(chunk['metadata'], ensure_ascii=False, indent=2)}"
    )
    print("-" * 60)
    print(f"Content:\n{chunk['content'][:500]}...")
    print("=" * 60)


# Chạy pipeline
if __name__ == "__main__":
    pdf_path = "QCDT-2023.pdf"
    chunks = main_pipeline(pdf_path)
