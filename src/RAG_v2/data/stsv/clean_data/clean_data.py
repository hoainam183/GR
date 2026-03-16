import json
import os
import re
import unicodedata
from bs4 import BeautifulSoup


def remove_accents(text: str) -> str:
    """Loại bỏ dấu tiếng Việt và chuyển thành ASCII."""
    # Chuẩn hóa Unicode NFD để tách dấu
    nfkd = unicodedata.normalize("NFD", text)
    # Loại bỏ các ký tự dấu (combining marks)
    without_accents = "".join(
        c for c in nfkd if unicodedata.category(c) != "Mn"
    )
    # Xử lý đặc biệt cho đ/Đ
    without_accents = without_accents.replace("đ", "d").replace("Đ", "D")
    return without_accents


def title_to_filename(title: str) -> str:
    """Chuyển title thành tên file hợp lệ dạng snake_case."""
    # Loại bỏ dấu tiếng Việt
    name = remove_accents(title)
    # Chuyển thường
    name = name.lower()
    # Loại bỏ các ký tự đặc biệt, giữ lại chữ cái, số và khoảng trắng
    name = re.sub(r"[^a-z0-9\s]", "", name)
    # Thay khoảng trắng (nhiều) thành dấu gạch dưới
    name = re.sub(r"\s+", "_", name.strip())
    # Loại bỏ dấu gạch dưới thừa
    name = re.sub(r"_+", "_", name)
    return name + ".json"


def clean_html(html_text: str) -> str:
    """Dùng BeautifulSoup để làm sạch HTML, giữ lại đường link dạng Markdown."""
    if not html_text:
        return ""
    soup = BeautifulSoup(html_text, "html.parser")

    # Chuyển thẻ <a> thành dạng Markdown [text](url) trước khi lấy text
    for a_tag in soup.find_all("a"):
        href = a_tag.get("href", "")
        link_text = a_tag.get_text(strip=True)
        if href:
            if link_text:
                a_tag.replace_with(f" [{link_text}]({href}) ")
            else:
                a_tag.replace_with(f" {href} ")
        else:
            a_tag.replace_with(link_text)

    # Lấy text, dùng \n để phân tách các block element
    text = soup.get_text(separator="\n")
    # Loại bỏ dòng trắng thừa và khoảng trắng thừa
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]  # Bỏ dòng rỗng
    return "\n".join(lines)


def main():
    # Đường dẫn
    input_file = os.path.join(os.path.dirname(__file__), "data.json")
    output_dir = os.path.join(os.path.dirname(__file__), "output")

    # Tạo folder output
    os.makedirs(output_dir, exist_ok=True)

    # Đọc file JSON
    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    documents = data.get("WebTitleLst", [])
    print(f"Tìm thấy {len(documents)} documents trong data.json")

    count = 0
    for doc in documents:
        title = doc.get("Title", "")
        description = doc.get("Description", "")

        if not title:
            print(
                f"  [SKIP] DocumentID={doc.get('DocumentID')} - không có Title"
            )
            continue

        # Làm sạch description
        cleaned_description = clean_html(description)

        # Tạo tên file từ title
        filename = title_to_filename(title)

        # Tạo nội dung file output
        output_data = {
            "DocumentID": doc.get("DocumentID"),
            "Title": title,
            "TypeDoc": doc.get("TypeDoc", ""),
            "Description": cleaned_description,
            "CreaterID": doc.get("CreaterID", ""),
            "TimeCreate": doc.get("TimeCreate", ""),
            "Status": doc.get("Status", 0),
        }

        # Ghi file
        output_path = os.path.join(output_dir, filename)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=4)

        count += 1
        print(f"  [OK] {filename}")

    print(f"\nHoàn thành! Đã tạo {count} file trong folder 'output/'")


if __name__ == "__main__":
    main()
