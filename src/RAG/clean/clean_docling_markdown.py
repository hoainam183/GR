import re
import os
import logging
from pathlib import Path

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def remove_footnote_markers(text: str) -> str:
    """Xóa các marker footnote (¹, ², ³, ⁴, v.v...)"""
    # Xóa footnote markers từ giữa text
    text = re.sub(r"[⁰¹²³⁴⁵⁶⁷⁸⁹]+", "", text)
    return text


def remove_duplicate_headers(text: str) -> str:
    """Xóa các header dư thừa ở đầu file"""
    lines = text.splitlines()
    cleaned_lines = []
    header_patterns = {
        r"^##\s+(BỘ GIÁO DỤC|CỘNG HÒA|QUY CHẾ|QUYẾT ĐỊNH)",
    }

    header_count = {}

    for line in lines:
        # Kiểm tra nếu là header dư thừa
        is_duplicate_header = False
        for pattern in header_patterns:
            if re.match(pattern, line.strip(), re.IGNORECASE):
                header_key = line.strip().lower()
                if header_key in header_count:
                    is_duplicate_header = True
                    break
                header_count[header_key] = header_count.get(header_key, 0) + 1

        if not is_duplicate_header:
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


def normalize_dieu_format(text: str) -> str:
    """
    Normalize format Điều:
    - "- Điều 1." → "## Điều 1."
    - "Điều 1." → "## Điều 1." (nếu ở đầu dòng)
    """
    lines = text.splitlines()
    normalized_lines = []

    for line in lines:
        stripped = line.strip()

        # Pattern: - Điều X. Title hoặc Điều X. Title
        dieu_pattern = r"^[\-\s]*?(Điều\s+\d+\.\s+.*)$"
        match = re.match(dieu_pattern, stripped)

        if match:
            dieu_content = match.group(1)
            # Kiểm tra xem có phải đã là ## không
            if not stripped.startswith("##"):
                normalized_lines.append(f"## {dieu_content}")
            else:
                normalized_lines.append(line)
        else:
            normalized_lines.append(line)

    return "\n".join(normalized_lines)


def clean_markdown(text: str) -> str:
    """
    Làm sạch nội dung Markdown trích xuất từ PDF quy định hoặc tài liệu tương tự.
    - Xóa footnote markers (¹, ², ³...)
    - Xóa header dư thừa ở đầu
    - Normalize format Điều
    - Bỏ phần MỤC LỤC (TOC)
    - Giữ nguyên bảng thật trong nội dung
    - Chuẩn hóa khoảng trắng và dòng
    """
    # Bước 1: Xóa marker footnote
    text = remove_footnote_markers(text)
    logging.debug("✅ Xóa footnote markers")

    # Bước 2: Xóa header dư thừa
    text = remove_duplicate_headers(text)
    logging.debug("✅ Xóa header dư thừa")

    # Bước 3: Normalize format Điều
    text = normalize_dieu_format(text)
    logging.debug("✅ Normalize format Điều")

    # Bước 4: Xử lý cơ bản
    lines = text.splitlines()
    cleaned_lines = []
    in_toc = False

    for line in lines:
        raw_line = line
        line = line.strip()

        # Bỏ qua dòng rỗng/toàn khoảng trắng
        if not line:
            if cleaned_lines and cleaned_lines[-1] != "":
                cleaned_lines.append("")
            continue

        # Phát hiện bắt đầu MỤC LỤC
        if re.match(r"^#{1,3}\s*MỤC\s*LỤC", line, re.IGNORECASE):
            in_toc = True
            logging.debug("Phát hiện MỤC LỤC")
            continue

        # Xử lý phần MỤC LỤC
        if in_toc:
            if re.match(r"^#{1,3}\s+(?!.*MỤC\s*LỤC)", line):
                in_toc = False
            else:
                continue

        # Bỏ dòng chỉ chứa ký tự căn dòng
        if re.match(r"^[\-\|_\.]{5,}$", line):
            continue

        # Chuẩn hóa khoảng trắng dư thừa
        line = re.sub(r"\s+", " ", line).strip()

        if line:
            cleaned_lines.append(line)

    # Loại bỏ dòng trống thừa ở cuối
    while cleaned_lines and cleaned_lines[-1] == "":
        cleaned_lines.pop()

    cleaned_text = "\n".join(cleaned_lines)
    cleaned_text = re.sub(r"\n{3,}", "\n\n", cleaned_text)

    return cleaned_text


if __name__ == "__main__":
    BASE_DIR = Path(__file__).parent
    input_dir = BASE_DIR / ".." / "output_docling"
    output_dir = BASE_DIR / ".." / "output_docling_clean"

    # Chuẩn hóa đường dẫn
    input_dir = input_dir.resolve()
    output_dir = output_dir.resolve()

    # Tạo folder output nếu không tồn tại
    output_dir.mkdir(parents=True, exist_ok=True)

    # Lấy danh sách các file .md trong input_dir
    markdown_files = sorted([f.name for f in input_dir.glob("*.md")])

    if not markdown_files:
        logging.warning(f"Không tìm thấy file markdown trong: {input_dir}")
    else:
        processed_count = 0
        skipped_count = 0
        error_count = 0

        for md_file in markdown_files:
            input_file = input_dir / md_file
            base_name = md_file[:-3]  # loại bỏ .md
            output_file = output_dir / f"{base_name}.clean.md"

            # Kiểm tra nếu file đã được clean
            if output_file.exists():
                logging.info(f"⏭️ Bỏ qua: {md_file} (đã được clean)")
                skipped_count += 1
                continue

            try:
                # Đọc file input
                raw_text = input_file.read_text(encoding="utf-8")

                # Làm sạch markdown
                cleaned = clean_markdown(raw_text)

                # Ghi file output
                output_file.write_text(cleaned, encoding="utf-8")

                logging.info(f"✅ Xử lý: {md_file} → {output_file.name}")
                processed_count += 1

            except Exception as e:
                logging.error(
                    f"❌ Lỗi xử lý {md_file}: {str(e)}", exc_info=True
                )
                error_count += 1

        # Báo cáo kết quả
        print(f"\n{'='*50}")
        print(f"📊 BÁNG CÁO KẾT QUẢ")
        print(f"{'='*50}")
        print(f"✅ Xử lý:     {processed_count} file")
        print(f"⏭️  Bỏ qua:    {skipped_count} file")
        print(f"❌ Lỗi:       {error_count} file")
        print(f"📁 Output:    {output_dir}")
        print(f"{'='*50}")
