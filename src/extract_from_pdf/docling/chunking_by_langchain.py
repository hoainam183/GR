import json
import re
from typing import List, Dict
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)


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


def chunk_markdown_with_hierarchy(
    markdown_path: str,
    docling_json_path: str,
    chunk_size: int = 1200,
    chunk_overlap: int = 200,
) -> List[Dict]:
    """
    Chunk markdown file với preserve hierarchy

    Args:
        markdown_path: Đường dẫn file markdown
        chunk_size: Kích thước chunk tối đa (tokens)
        chunk_overlap: Số tokens overlap giữa chunks

    Returns:
        List of chunks với metadata
    """
    print(f"\n🔪 Bắt đầu chunking: {markdown_path}")

    # Đọc markdown content
    with open(markdown_path, "r", encoding="utf-8") as f:
        markdown_text = f.read()

    footnotes = extract_footnotes_from_docling_json(docling_json_path)
    cleaned_markdown = remove_footnotes_from_markdown(markdown_text, footnotes)

    # Define headers để split
    headers_to_split_on = [
        ("#", "chapter"),  # Chương
        ("##", "article"),  # Điều
        ("###", "section"),  # Khoản/Mục
        ("####", "subsection"),  # Tiểu mục
    ]

    # Khởi tạo MarkdownHeaderTextSplitter
    markdown_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=headers_to_split_on,
        strip_headers=False,  # Giữ headers trong content
    )

    # Split theo headers
    header_splits = markdown_splitter.split_text(cleaned_markdown)

    print(f"📑 Đã split theo headers: {len(header_splits)} chunks")

    # Split thêm nếu chunks quá lớn
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    # Process từng chunk
    final_chunks = []

    for idx, doc in enumerate(header_splits):
        content = doc.page_content
        metadata = doc.metadata

        # Nếu chunk quá lớn, split thêm
        if len(content) > chunk_size * 2:
            sub_chunks = text_splitter.split_text(content)

            for sub_idx, sub_content in enumerate(sub_chunks):
                chunk_data = {
                    "chunk_id": f"chunk_{idx}_{sub_idx}",
                    "content": sub_content,
                    "metadata": {
                        **metadata,
                        "parent_chunk": idx,
                        "sub_chunk": sub_idx,
                        "chunk_size": len(sub_content),
                    },
                }
                final_chunks.append(chunk_data)
        else:
            chunk_data = {
                "chunk_id": f"chunk_{idx}",
                "content": content,
                "metadata": {**metadata, "chunk_size": len(content)},
            }
            final_chunks.append(chunk_data)

    # Thêm metadata về footnotes
    for chunk in final_chunks:
        # Tìm footnote references trong content
        footnote_refs = re.findall(r"\[\^(\d+)\]", chunk["content"])
        if footnote_refs:
            chunk["metadata"]["footnote_refs"] = list(set(footnote_refs))

    print(f"✅ Hoàn thành chunking: {len(final_chunks)} chunks\n")

    return final_chunks


if __name__ == "__main__":
    markdown_path = "./output/QCDT-2023_clean.md"
    docling_json_path = "./output/QCDT-2023_metadata.json"
    chunks = chunk_markdown_with_hierarchy(
        markdown_path, docling_json_path, chunk_size=1200, chunk_overlap=200
    )

    # Test với sample data
    # test_remove_footnotes()

    # Hoặc sử dụng với data thật của bạn:
    """
    # Giả sử bạn đã có:
    with open("document.md", "r", encoding="utf-8") as f:
        markdown_text = f.read()
    
    footnotes = extract_footnotes_from_docling_json("metadata.json")
    
    # Xóa footnotes
    cleaned_markdown = remove_footnotes_from_markdown(markdown_text, footnotes)
    
    # Lưu cleaned markdown
    with open("cleaned_document.md", "w", encoding="utf-8") as f:
        f.write(cleaned_markdown)
    """
