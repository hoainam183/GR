import re, os
from typing import List


def is_toc_table_row(line: str) -> bool:
    """
    Kiểm tra một dòng bảng có phải là dòng mục lục (TOC) hay không.
    Tiêu chí:
    - Có nhiều dấu chấm liên tiếp (3 trở lên) và kết thúc bằng số trang (ví dụ: '...27' hoặc '... 27 |')
    - Hoặc dòng không bắt đầu bằng '|' nhưng có pattern tương tự (nội dung TOC không ở dạng bảng).
    """
    s = line.strip()

    # Nếu dòng rỗng thì không phải TOC
    if not s:
        return False

    # Pattern: có chuỗi dấu chấm dài và số ở cuối (có thể có '|' ở cuối)
    # ví dụ: "| Điều 45...27 |"  hoặc "Điều 45....27"
    if re.search(r"\.{3,}\s*\d+\s*(\||$)", s):
        return True

    return False


def clean_markdown(text: str) -> str:
    """
    Làm sạch nội dung Markdown trích xuất từ PDF quy định hoặc tài liệu tương tự.
    - Bỏ phần MỤC LỤC (TOC)
    - Giữ nguyên bảng thật trong nội dung
    - Giữ nguyên chú thích
    - Chuẩn hóa khoảng trắng và dòng
    """
    lines = text.splitlines()
    cleaned_lines = []
    in_toc = False  # cờ để bỏ qua phần MỤC LỤC

    for line in lines:
        raw_line = line
        line = line.strip()

        # Nếu gặp tiêu đề MỤC LỤC → bật cờ bỏ qua
        if re.match(r"^#{1,3}\s*MỤC LỤC", line, re.IGNORECASE):
            in_toc = True
            continue

        # Nếu đang trong MỤC LỤC, bỏ qua các dòng cho đến khi gặp tiêu đề mới
        if in_toc:
            if re.match(r"^#{1,3}\s+", line):  # gặp tiêu đề thật → dừng bỏ qua
                in_toc = False
            else:
                # bỏ các dòng bảng hoặc dòng chấm trong TOC
                if re.match(r"^\|.*\|$", line) or re.match(
                    r"^[\|\-\. ]+$", line
                ):
                    continue
                if "Điều" in line or "CHƯƠNG" in line:
                    continue
                # bỏ qua TOC, không append
                continue

        # Giữ lại chú thích, bảng, và tiêu đề thật
        # Loại bỏ các dòng chỉ chứa ký tự căn dòng
        if re.match(r"^[\-\|_\.]{5,}$", line):
            continue

        # Chuẩn hóa khoảng trắng dư
        line = re.sub(r"\s+", " ", line)

        cleaned_lines.append(line or raw_line)

    # Ghép lại, chuẩn hóa số dòng trống
    cleaned_text = "\n".join(cleaned_lines)
    cleaned_text = re.sub(r"\n{3,}", "\n\n", cleaned_text).strip()

    return cleaned_text


if __name__ == "__main__":
    BASE_DIR = os.path.dirname(
        os.path.abspath(__file__)
    )  # thư mục chứa script này

    input_file = os.path.join(BASE_DIR, ".", "output", "QCDT-2023.md")
    output_file = os.path.join(BASE_DIR, ".", "output", "QCDT-2023_clean.md")

    with open(input_file, "r", encoding="utf-8") as f:
        raw_text = f.read()

    cleaned = clean_markdown(raw_text)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(cleaned)

    print("✅ Đã làm sạch file markdown và lưu vào:", output_file)
