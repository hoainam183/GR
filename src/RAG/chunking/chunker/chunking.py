from typing import List, Dict, Optional
import re
from pathlib import Path
import json


def parse_legal_document_structure(markdown_text: str) -> List[Dict]:
    """
    Parse văn bản pháp lý với cấu trúc phân cấp đầy đủ

    Structure hierarchy:
    - Title (Tiêu đề: QUY CHẾ ĐÀO TẠO)
    - Chapter (Chương: # CHƯƠNG I)
    - Article (Điều: ## Điều 1)
    - Clause (Khoản: 1., 2., 3.)
    - SubClause (Khoản con: a), b), c)...)

    Args:
        markdown_text: Nội dung markdown
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
    current_depth = 0  # Track depth: 0=clause (1., 2.), 1=sub-clause (a), b))

    lines = markdown_text.split("\n")

    def save_current_clause():
        """Lưu khoản hiện tại vào chunks"""
        if not current_clause_lines:
            return

        content = "\n".join(current_clause_lines).strip()
        if not content:
            return

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
            # Save previous clause before starting new title
            if current_clause_num is not None:
                save_current_clause()
                current_clause_lines = []
                current_clause_num = None
            current_title = line_stripped.replace("##", "").strip()
            current_depth = 0
            continue

        # Detect Chapter (# CHƯƠNG)
        if re.match(r"^#\s+CHƯƠNG", line_stripped):
            # Save previous clause before starting new chapter
            if current_clause_num is not None:
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
            current_depth = 0
            continue

        # Detect Article (## Điều)
        if re.match(r"^##\s+Điều", line_stripped):
            # Save previous clause before starting new article
            if current_clause_num is not None:
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
            current_depth = 0
            continue

        # Detect Main Clause (1., 2., 3., ...)
        # Pattern: dòng bắt đầu với số và dấu chấm, hoặc "- a)" cho các danh sách con
        clause_match = re.match(r"^(\d+)\.\s+", line_stripped)
        if clause_match:
            # Save previous clause
            if current_clause_num is not None:
                save_current_clause()

            # Start new clause
            current_clause_num = clause_match.group(1)
            current_clause_lines = [line_stripped]
            current_depth = 0
            continue

        # Detect Sub-clause (a), b), c), ...)
        # These lines often start with "- a)", "- b)" or directly with "a)"
        subclause_match = re.match(r"^[-–]?\s*([a-z][\))])\s+", line_stripped)
        if subclause_match and current_clause_num is not None:
            # Part of current clause, add to it
            current_clause_lines.append(line_stripped)
            current_depth = 1
            continue

        # Table detection (line starting with | or containing table structure)
        if line_stripped.startswith("|") or (
            current_clause_num is not None
            and (line_stripped.startswith("|") or "---" in line_stripped)
        ):
            if current_clause_num is not None:
                current_clause_lines.append(line_stripped)
            continue

        # Content continuation of current clause
        # This handles multi-line clauses
        if current_clause_num is not None and line_stripped:
            current_clause_lines.append(line_stripped)

    # Save last clause
    if current_clause_num is not None:
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

    Ưu tiên giữ lại cấu trúc danh sách và bảng

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
        # Ưu tiên tách theo các đơn vị logic
        separators=[
            "\n\n",  # Tách giữa các đoạn
            "\n",  # Tách giữa các dòng
            "(?<=\.)\\s+(?=[a-z])",  # Tách giữa các câu
            "(?<=,)\\s+",  # Tách sau dấu phẩy
            " ",  # Tách theo từ
            "",  # Fallback: tách theo ký tự
        ],
    )

    final_chunks = []

    for idx, chunk in enumerate(chunks):
        content = chunk["content"]
        metadata = chunk["metadata"]

        # Check nếu có bảng - không nên split các bảng
        if metadata.get("has_table"):
            final_chunks.append(chunk)
            continue

        # Nếu chunk quá lớn
        if len(content) > max_chunk_size * 1.5:
            sub_contents = text_splitter.split_text(content)

            for sub_idx, sub_content in enumerate(sub_contents):
                # Filter out very small chunks (< 50 chars)
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
            # Chunk size OK
            chunk["metadata"]["is_split"] = False
            final_chunks.append(chunk)

    return final_chunks


def chunk_markdown_with_hierarchy(
    markdown_path: str,
    chunk_size: int = 1200,
    chunk_overlap: int = 200,
) -> List[Dict]:
    """
    Main function: Chunk markdown file với preserve hierarchy

    Args:
        markdown_path: Đường dẫn file markdown
        chunk_size: Kích thước chunk tối đa
        chunk_overlap: Số ký tự overlap giữa chunks

    Returns:
        List of chunks với metadata đầy đủ
    """
    print(f"\n🔪 Bắt đầu chunking: {markdown_path}")

    # 1. Đọc markdown
    with open(markdown_path, "r", encoding="utf-8") as f:
        markdown_text = f.read()

    # 3. Parse document structure
    chunks = parse_legal_document_structure(markdown_text)
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
    avg_size = sum(chunk_sizes) / len(chunk_sizes) if chunk_sizes else 0

    # Đếm theo content type
    content_types = Counter(
        [c["metadata"].get("content_type", "unknown") for c in chunks]
    )

    # Đếm chunks có bảng
    chunks_with_tables = sum(
        1 for c in chunks if c["metadata"].get("has_table")
    )

    # Đếm chunks có danh sách
    chunks_with_lists = sum(1 for c in chunks if c["metadata"].get("has_list"))

    # Đếm chunks được split
    split_chunks = sum(1 for c in chunks if c["metadata"].get("is_split"))

    print(f"📊 Validation Results:")
    print(f"   - Tổng chunks: {total_chunks}")
    print(f"   - Avg chunk size: {avg_size:.0f} chars")
    print(f"   - Min size: {min(chunk_sizes) if chunk_sizes else 0}")
    print(f"   - Max size: {max(chunk_sizes) if chunk_sizes else 0}")
    print(f"   - Chunks được split: {split_chunks}")
    print(f"   - Chunks có bảng: {chunks_with_tables}")
    print(f"   - Chunks có danh sách: {chunks_with_lists}")
    print(f"\n   Content types:")
    for ctype, count in content_types.most_common():
        print(f"      {ctype}: {count}")

    # Warning nếu có chunks quá lớn/nhỏ
    too_large = [c for c in chunks if c["metadata"]["chunk_size"] > 1500]
    too_small = [c for c in chunks if c["metadata"]["chunk_size"] < 50]

    if too_large:
        print(
            f"\n⚠️  Warning: {len(too_large)} chunks > 1500 chars (có thể cần split thêm)"
        )
    if too_small:
        print(f"⚠️  Warning: {len(too_small)} chunks < 50 chars (quá nhỏ)")

    # Distribution stats
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
        ">1500": sum(1 for c in chunks if c["metadata"]["chunk_size"] >= 1500),
    }

    print(f"\n   📈 Distribution by size:")
    for range_label, count in ranges.items():
        percentage = (count / total_chunks * 100) if total_chunks > 0 else 0
        print(f"      {range_label} chars: {count} ({percentage:.1f}%)")


# Test chunking
def main_pipeline(output_dir: str = "../chunks_by_articles"):
    """
    Pipeline đầy đủ: PDF → Markdown → Chunks
    """
    # stats = convert_pdf_to_markdown(pdf_path, output_dir)
    markdown_path = "../output_docling_clean/QCDT_2025_5445_QD-DHBK.clean.md"

    # Step 2: Chunk Markdown
    print("\nSTEP 2: Chunking Markdown")
    print("-" * 60)
    chunks = chunk_markdown_with_hierarchy(
        markdown_path, chunk_size=1200, chunk_overlap=200
    )

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
    chunks = main_pipeline()
