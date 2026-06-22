import re
import os
from typing import List


def is_toc_table_row(line: str) -> bool:
    """Kiểm tra dòng có phải TOC hay không"""
    s = line.strip()
    if not s:
        return False
    # Cải tiến: kiểm tra dấu chấm kết thúc với số
    if re.search(r"\.{3,}\s*\d+\s*(\||$)", s):
        return True
    return False


def clean_markdown(text: str) -> str:
    """Làm sạch Markdown"""
    lines = text.splitlines()
    cleaned_lines = []
    in_toc = False
    # Số dòng "không giống mục lục" liên tiếp trong vùng TOC. Dùng để chặn
    # việc xoá tràn: chỉ một heading "MỤC LỤC" không được phép nuốt toàn bộ
    # phần thân còn lại nếu sau nó không có heading mới.
    non_toc_streak = 0

    for line in lines:
        raw_line = line
        line = line.strip()

        # Bắt đầu vùng MỤC LỤC
        if re.match(r"^#{1,3}\s*MỤC LỤC", line, re.IGNORECASE):
            in_toc = True
            non_toc_streak = 0
            continue

        if in_toc:
            if re.match(r"^#{1,3}\s+", line):
                # Gặp tiêu đề mới → kết thúc TOC, xử lý dòng này như bình thường.
                in_toc = False
            elif is_toc_table_row(line) or not line:
                # Mục lục thật (dotted-leader) hoặc dòng trống → bỏ.
                non_toc_streak = 0
                continue
            else:
                # Dòng nội dung thật: bỏ tối đa 2 dòng; nếu có ≥3 dòng nội dung
                # liên tiếp thì coi như TOC đã hết và giữ lại từ dòng này.
                non_toc_streak += 1
                if non_toc_streak >= 3:
                    in_toc = False
                else:
                    continue

        # Bỏ dòng chỉ có ký tự căn dòng (nhưng giữ bảng)
        if re.match(r"^[\-_\.]{5,}$", line):  # Bỏ dòng gạch, không phải bảng
            continue

        # Chuẩn hóa khoảng trắng - nhưng giữ nguyên dòng bảng
        if not line.startswith("|"):
            line = re.sub(r"\s+", " ", line)
        else:
            # Cho dòng bảng: chỉ chuẩn hóa khoảng trắng trong cell
            line = re.sub(r"\s+\|", " |", line)
            line = re.sub(r"\|\s+", "| ", line)

        cleaned_lines.append(line or raw_line)

    # Ghép lại
    cleaned_text = "\n".join(cleaned_lines)
    cleaned_text = re.sub(r"\n{3,}", "\n\n", cleaned_text).strip()

    return cleaned_text


if __name__ == "__main__":
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(BASE_DIR, "../output_docling_clean")

    # Kiểm tra thư mục output có tồn tại
    if not os.path.isdir(output_dir):
        print(f"❌ Lỗi: Không tìm thấy thư mục {output_dir}")
        exit(1)

    # Tìm tất cả file .md trong output
    md_files = [f for f in os.listdir(output_dir) if f.endswith(".md")]

    if not md_files:
        print(f"⚠️  Không có file .md trong {output_dir}")
        exit(0)

    print(f"📂 Tìm thấy {len(md_files)} file markdown\n")

    processed_count = 0
    for md_file in md_files:
        input_file = os.path.join(output_dir, md_file)
        output_file = os.path.join(
            output_dir, md_file.replace(".md", "_clean.md")
        )

        # Bỏ qua file đã làm sạch
        if "_clean.md" in md_file:
            print(f"⏭️  Bỏ qua: {md_file} (đã làm sạch)")
            continue

        try:
            with open(input_file, "r", encoding="utf-8") as f:
                raw_text = f.read()

            cleaned = clean_markdown(raw_text)

            with open(output_file, "w", encoding="utf-8") as f:
                f.write(cleaned)

            file_size_before = len(raw_text)
            file_size_after = len(cleaned)
            reduction_percent = (1 - file_size_after / file_size_before) * 100

            print(f"✅ {md_file}")
            print(
                f"   📊 {file_size_before:,} → {file_size_after:,} bytes ({reduction_percent:.1f}% giảm)"
            )
            print(f"   💾 {output_file}\n")

            processed_count += 1

        except FileNotFoundError:
            print(f"❌ Lỗi: Không tìm thấy file {input_file}")
        except Exception as e:
            print(f"❌ Lỗi xử lý {md_file}: {str(e)}")

    print(f"\n{'='*50}")
    print(f"✨ Hoàn thành! Đã xử lý {processed_count}/{len(md_files)} file")
