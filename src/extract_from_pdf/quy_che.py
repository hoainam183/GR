import re
import json
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class Chunk:
    """Đại diện cho một chunk dữ liệu"""

    id: str
    text: str
    metadata: Dict

    def to_dict(self):
        return asdict(self)


class QuyCheDaoTaoExtractor:
    """Extract và chunk dữ liệu từ Quy chế đào tạo ĐHBK"""

    def __init__(self, text: str):
        self.text = text
        self.chunks = []

    def extract_chuong_mapping(self) -> Dict[int, str]:
        """Mapping từ số Điều sang Chương"""
        return {
            range(1, 10): "I - NHỮNG QUY ĐỊNH CHUNG",
            range(10, 21): "II - ĐÀO TẠO ĐẠI HỌC",
            range(21, 27): "III - ĐÀO TẠO KỸ SƯ",
            range(27, 36): "IV - ĐÀO TẠO THẠC SĨ",
            range(36, 46): "V - ĐÀO TẠO TIẾN SĨ",
            range(46, 48): "VI - TỔ CHỨC THỰC HIỆN",
        }

    def get_chuong(self, dieu_num: int) -> str:
        """Lấy tên chương từ số điều"""
        mapping = self.extract_chuong_mapping()
        for dieu_range, chuong in mapping.items():
            if dieu_num in dieu_range:
                return chuong
        return "Unknown"

    def extract_keywords(self, text: str) -> List[str]:
        """Trích xuất keywords từ text"""
        keywords_dict = {
            "tín chỉ": ["tín chỉ", "tc", "credit"],
            "điểm": ["điểm", "gpa", "cpa", "grade"],
            "tốt nghiệp": ["tốt nghiệp", "graduation", "bằng"],
            "học phí": ["học phí", "tuition", "phí"],
            "đăng ký": ["đăng ký", "registration"],
            "thi": ["thi", "exam", "kiểm tra"],
            "luận văn": ["luận văn", "thesis"],
            "luận án": ["luận án", "dissertation"],
            "đồ án": ["đồ án", "project"],
            "thạc sĩ": ["thạc sĩ", "master"],
            "tiến sĩ": ["tiến sĩ", "phd", "ncs"],
            "sinh viên": ["sinh viên", "student"],
            "học viên": ["học viên"],
            "cảnh báo": ["cảnh báo", "warning"],
            "thôi học": ["thôi học", "buộc thôi học"],
        }

        found_keywords = []
        text_lower = text.lower()
        for category, variants in keywords_dict.items():
            if any(variant in text_lower for variant in variants):
                found_keywords.append(category)

        return found_keywords

    def extract_applies_to(self, text: str) -> List[str]:
        """Xác định đối tượng áp dụng"""
        applies = []
        text_lower = text.lower()

        if any(
            term in text_lower for term in ["sinh viên", "đại học", "cử nhân"]
        ):
            applies.append("sinh viên đại học")
        if any(term in text_lower for term in ["học viên", "thạc sĩ"]):
            applies.append("học viên thạc sĩ")
        if any(term in text_lower for term in ["kỹ sư"]):
            applies.append("học viên kỹ sư")
        if any(
            term in text_lower for term in ["ncs", "nghiên cứu sinh", "tiến sĩ"]
        ):
            applies.append("nghiên cứu sinh")
        if not applies:
            applies.append("tất cả")

        return applies

    def extract_tables(self, text: str) -> Optional[str]:
        """Trích xuất và format bảng biểu"""
        # Pattern cho bảng điểm
        if "điểm học phần theo" in text.lower() and "điểm chữ" in text.lower():
            return "BẢNG QUY ĐỔI ĐIỂM"

        # Pattern cho bảng xếp loại
        if "xếp loại" in text.lower() and (
            "gpa" in text.lower() or "cpa" in text.lower()
        ):
            return "BẢNG XẾP LOẠI HỌC LỰC"

        # Pattern cho bảng thời gian
        if "thời gian" in text.lower() and "khối lượng" in text.lower():
            return "BẢNG THỜI GIAN VÀ KHỐI LƯỢNG HỌC TẬP"

        return None

    def extract_cross_references(self, text: str) -> List[str]:
        """Trích xuất các tham chiếu chéo"""
        refs = []

        # Pattern: "tại khoản X Điều Y"
        pattern1 = r"tại\s+khoản\s+(\d+)\s+Điều\s+(\d+)"
        refs.extend(
            [f"Điều {m[1]}, Khoản {m[0]}" for m in re.findall(pattern1, text)]
        )

        # Pattern: "theo quy định tại Điều X"
        pattern2 = r"theo.*?quy định.*?Điều\s+(\d+)"
        refs.extend([f"Điều {m}" for m in re.findall(pattern2, text)])

        # Pattern: "quy định tại điểm X khoản Y Điều Z"
        pattern3 = r"điểm\s+([a-z])\s+khoản\s+(\d+)\s+Điều\s+(\d+)"
        refs.extend(
            [
                f"Điều {m[2]}, Khoản {m[1]}, Điểm {m[0]}"
                for m in re.findall(pattern3, text)
            ]
        )

        return list(set(refs))

    def chunk_by_dieu_khoan(self) -> List[Chunk]:
        """Chunk chính theo Điều và Khoản"""
        chunks = []

        # Pattern để tách theo Điều
        dieu_pattern = r"Điều\s+(\d+)\.\s+([^\n]+)\n(.*?)(?=Điều\s+\d+\.|CHƯƠNG\s+[IVX]+|$)"

        for match in re.finditer(
            dieu_pattern, self.text, re.DOTALL | re.IGNORECASE
        ):
            dieu_num = int(match.group(1))
            dieu_title = match.group(2).strip()
            content = match.group(3).strip()
            content = re.sub(r"\s+", " ", content).strip()
            # Lấy chương
            chuong = self.get_chuong(dieu_num)

            # Tách theo khoản
            khoan_pattern = r"(\d+)\.\s*(.*?)(?=\s*\d+\.\s*|$)"
            khoans = re.findall(
                khoan_pattern, content, re.MULTILINE | re.DOTALL
            )

            if khoans:
                # Có khoản - tạo chunk cho từng khoản
                for khoan_num, khoan_content in khoans:
                    khoan_text = khoan_content.strip()

                    # Tách theo điểm (a, b, c...)
                    diem_pattern = r"^([a-z]|đ)\)\s+(.*?)(?=\n[a-z]\)|$)"
                    diems = re.findall(
                        diem_pattern, khoan_text, re.MULTILINE | re.DOTALL
                    )

                    if diems and len(khoan_text) > 5000:
                        # Nếu khoản quá dài và có nhiều điểm, tách theo điểm
                        for diem_char, diem_content in diems:
                            chunk_id = f"d{dieu_num}_k{khoan_num}_p{diem_char}"
                            full_text = f"""Điều {dieu_num}: {dieu_title}
                                            Khoản {khoan_num}, Điểm {diem_char}:
                                            {diem_content.strip()}

                                            [Chương: {chuong}]"""

                            metadata = {
                                "dieu": dieu_num,
                                "khoan": int(khoan_num),
                                "diem": diem_char,
                                "chuong": chuong,
                                "title": dieu_title,
                                "keywords": self.extract_keywords(full_text),
                                "applies_to": self.extract_applies_to(
                                    full_text
                                ),
                                "has_table": self.extract_tables(full_text),
                                "references": self.extract_cross_references(
                                    full_text
                                ),
                            }

                            chunks.append(Chunk(chunk_id, full_text, metadata))
                    else:
                        # Chunk theo khoản
                        chunk_id = f"d{dieu_num}_k{khoan_num}"
                        full_text = f"""Điều {dieu_num}: {dieu_title}
                                        Khoản {khoan_num}:
                                        {khoan_text}

                                        [Chương: {chuong}]"""

                        metadata = {
                            "dieu": dieu_num,
                            "khoan": int(khoan_num),
                            "chuong": chuong,
                            "title": dieu_title,
                            "keywords": self.extract_keywords(full_text),
                            "applies_to": self.extract_applies_to(full_text),
                            "has_table": self.extract_tables(full_text),
                            "references": self.extract_cross_references(
                                full_text
                            ),
                        }

                        chunks.append(Chunk(chunk_id, full_text, metadata))
            else:
                # Không có khoản - chunk toàn bộ điều
                chunk_id = f"d{dieu_num}"
                full_text = f"""Điều {dieu_num}: {dieu_title}
{content}

[Chương: {chuong}]"""

                metadata = {
                    "dieu": dieu_num,
                    "chuong": chuong,
                    "title": dieu_title,
                    "keywords": self.extract_keywords(full_text),
                    "applies_to": self.extract_applies_to(full_text),
                    "has_table": self.extract_tables(full_text),
                    "references": self.extract_cross_references(full_text),
                }

                chunks.append(Chunk(chunk_id, full_text, metadata))

        return chunks

    def extract_special_tables(self) -> List[Chunk]:
        """Trích xuất các bảng quan trọng thành chunks riêng"""
        chunks = []

        # Bảng quy đổi điểm
        if "Điểm học phần theo" in self.text:
            table_text = """BẢNG QUY ĐỔI ĐIỂM HỌC PHẦN (Điều 5, Khoản 6)

Thang 10 → Điểm chữ → Thang 4:
- 9.5-10.0 → A+ → 4.0
- 8.5-9.4 → A → 4.0
- 8.0-8.4 → B+ → 3.5
- 7.0-7.9 → B → 3.0
- 6.5-6.9 → C+ → 2.5
- 6.0-6.4 → C → 2.0
- 5.5-5.9 → D+ → 1.5
- 5.0-5.4 → D → 1.0
- 4.0-4.9 → D → 1.0
- 0.0-3.9 → F → 0

LƯU Ý:
- Điểm đạt: từ D trở lên (≥4.0)
- Học phần tốt nghiệp: phải từ C trở lên (≥5.0)
- Điểm liệt: <5 với đồ án/khóa luận tốt nghiệp, <3 với học phần khác"""

            chunks.append(
                Chunk(
                    "table_diem_quy_doi",
                    table_text,
                    {
                        "type": "table",
                        "table_name": "quy_doi_diem",
                        "dieu": 5,
                        "khoan": 6,
                        "keywords": ["điểm", "quy đổi", "gpa"],
                        "applies_to": ["tất cả"],
                    },
                )
            )

        # Bảng xếp loại học lực
        if "Xếp loại" in self.text and "GPA hoặc CPA" in self.text:
            table_text = """BẢNG XẾP LOẠI HỌC LỰC (Điều 12, Khoản 6)

GPA/CPA → Xếp loại:
- 3.60-4.00 → Xuất sắc
- 3.20-3.59 → Giỏi
- 2.50-3.19 → Khá
- 2.00-2.49 → Trung bình
- 1.00-1.99 → Yếu
- <1.00 → Kém

Áp dụng cho:
- GPA: Xếp loại học lực theo học kỳ
- CPA: Xếp loại học lực từ đầu khóa và xếp hạng tốt nghiệp"""

            chunks.append(
                Chunk(
                    "table_xep_loai",
                    table_text,
                    {
                        "type": "table",
                        "table_name": "xep_loai_hoc_luc",
                        "dieu": 12,
                        "khoan": 6,
                        "keywords": ["điểm", "xếp loại", "gpa", "cpa"],
                        "applies_to": ["tất cả"],
                    },
                )
            )

        # Bảng trình độ năm học
        if "Số TCTL" in self.text and "Trình độ" in self.text:
            table_text = """BẢNG TRÌNH ĐỘ NĂM HỌC (Điều 12, Khoản 5)

Số TC tích lũy → Trình độ năm học:
- <32 TC → Năm thứ nhất
- 32-63 TC → Năm thứ hai
- 64-95 TC → Năm thứ ba
- 96-127 TC → Năm thứ tư
- ≥128 TC → Năm thứ năm

Áp dụng: Sinh viên đại học"""

            chunks.append(
                Chunk(
                    "table_trinh_do_nam",
                    table_text,
                    {
                        "type": "table",
                        "table_name": "trinh_do_nam_hoc",
                        "dieu": 12,
                        "khoan": 5,
                        "keywords": ["tín chỉ", "năm học"],
                        "applies_to": ["sinh viên đại học"],
                    },
                )
            )

        return chunks

    def extract_all(self) -> List[Chunk]:
        """Trích xuất tất cả chunks"""
        chunks = []

        # 1. Chunks chính theo điều/khoản
        chunks.extend(self.chunk_by_dieu_khoan())

        # 2. Bảng biểu đặc biệt
        chunks.extend(self.extract_special_tables())

        self.chunks = chunks
        return chunks

    def save_to_json(self, filepath: str):
        """Lưu chunks ra file JSON"""
        data = {
            "metadata": {
                "document": "Quy chế đào tạo ĐHBK Hà Nội",
                "version": "QĐ 4600/QĐ-ĐHBK ngày 09/06/2023",
                "total_chunks": len(self.chunks),
                "created_at": datetime.now().isoformat(),
            },
            "chunks": [chunk.to_dict() for chunk in self.chunks],
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"✅ Đã lưu {len(self.chunks)} chunks vào {filepath}")

    def get_statistics(self) -> Dict:
        """Thống kê về chunks"""
        stats = {
            "total_chunks": len(self.chunks),
            "by_chuong": {},
            "by_keywords": {},
            "by_applies_to": {},
            "with_tables": 0,
            "with_references": 0,
        }

        for chunk in self.chunks:
            # By chương
            chuong = chunk.metadata.get("chuong", "Unknown")
            stats["by_chuong"][chuong] = stats["by_chuong"].get(chuong, 0) + 1

            # By keywords
            for kw in chunk.metadata.get("keywords", []):
                stats["by_keywords"][kw] = stats["by_keywords"].get(kw, 0) + 1

            # By applies_to
            for applies in chunk.metadata.get("applies_to", []):
                stats["by_applies_to"][applies] = (
                    stats["by_applies_to"].get(applies, 0) + 1
                )

            # Tables
            if chunk.metadata.get("has_table"):
                stats["with_tables"] += 1

            # References
            if chunk.metadata.get("references"):
                stats["with_references"] += 1

        return stats


# ====================== MAIN USAGE ======================


def main(text_content: str):
    """Hàm chính để chạy extraction"""

    print("🚀 Bắt đầu extract dữ liệu RAG từ Quy chế đào tạo ĐHBK...")

    # Khởi tạo extractor
    extractor = QuyCheDaoTaoExtractor(text_content)

    # Extract tất cả chunks
    chunks = extractor.extract_all()

    # Thống kê
    stats = extractor.get_statistics()
    print(f"\n📊 THỐNG KÊ:")
    print(f"  - Tổng số chunks: {stats['total_chunks']}")
    print(f"  - Chunks có bảng: {stats['with_tables']}")
    print(f"  - Chunks có tham chiếu: {stats['with_references']}")

    print(f"\n📚 Phân bố theo chương:")
    for chuong, count in sorted(stats["by_chuong"].items()):
        print(f"  - {chuong}: {count} chunks")

    print(f"\n🔑 Top keywords:")
    top_keywords = sorted(
        stats["by_keywords"].items(), key=lambda x: x[1], reverse=True
    )[:10]
    for kw, count in top_keywords:
        print(f"  - {kw}: {count} chunks")

    # Lưu ra file
    extractor.save_to_json("quy_che_rag_data.json")

    # In một vài chunks mẫu
    print(f"\n📝 MẪU CHUNKS:")
    for i, chunk in enumerate(chunks[:3], 1):
        print(f"\n--- Chunk {i} ---")
        print(f"ID: {chunk.id}")
        print(f"Text (100 ký tự đầu): {chunk.text[:100]}...")
        print(
            f"Metadata: {json.dumps(chunk.metadata, ensure_ascii=False, indent=2)}"
        )

    return extractor, chunks


# ====================== PDF EXTRACTION ======================


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text từ PDF file"""
    try:
        import PyPDF2

        print(f"📄 Đang đọc PDF: {pdf_path}")
        text = ""

        with open(pdf_path, "rb") as file:
            pdf_reader = PyPDF2.PdfReader(file)
            total_pages = len(pdf_reader.pages)
            print(f"   Tổng số trang: {total_pages}")

            for i, page in enumerate(pdf_reader.pages, 1):
                page_text = page.extract_text()
                text += page_text + "\n"
                if i % 10 == 0:
                    print(f"   Đã xử lý {i}/{total_pages} trang...")

        print(f"✅ Hoàn thành! Tổng {len(text)} ký tự\n")
        return text

    except ImportError:
        print("❌ Cần cài đặt PyPDF2: pip install PyPDF2")
        return None
    except Exception as e:
        print(f"❌ Lỗi khi đọc PDF: {e}")
        return None


def extract_text_from_pdf_advanced(pdf_path: str) -> str:
    """Extract text từ PDF với pdfplumber (tốt hơn cho tiếng Việt)"""
    try:
        import pdfplumber

        print(f"📄 Đang đọc PDF với pdfplumber: {pdf_path}")
        text = ""

        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            print(f"   Tổng số trang: {total_pages}")

            for i, page in enumerate(pdf.pages, 1):
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
                if i % 10 == 0:
                    print(f"   Đã xử lý {i}/{total_pages} trang...")

        print(f"✅ Hoàn thành! Tổng {len(text)} ký tự\n")
        return text

    except ImportError:
        print("❌ Cần cài đặt pdfplumber: pip install pdfplumber")
        print("   Đang fallback sang PyPDF2...")
        return extract_text_from_pdf(pdf_path)
    except Exception as e:
        print(f"❌ Lỗi khi đọc PDF: {e}")
        return None


# ====================== MAIN USAGE ======================

if __name__ == "__main__":
    import sys

    # Cách 1: Đọc từ file PDF
    pdf_file = "QCDT-2023.pdf"  # Thay đổi tên file nếu cần

    print("=" * 60)
    print("🚀 RAG DATA EXTRACTION - ĐHBK QUY CHẾ ĐÀO TẠO")
    print("=" * 60 + "\n")

    # Extract text từ PDF
    text_content = extract_text_from_pdf_advanced(pdf_file)

    if not text_content:
        print("\n❌ Không thể đọc file PDF. Vui lòng kiểm tra:")
        print("   1. File PDF tồn tại: QCDT-2023-upload.pdf")
        print("   2. Đã cài đặt: pip install pdfplumber PyPDF2")
        sys.exit(1)

    # Chạy extraction
    extractor, chunks = main(text_content)

    print("\n" + "=" * 60)
    print("✅ HOÀN THÀNH!")
    print("=" * 60)
    print(f"📁 File output: quy_che_rag_data.json")
    print(f"📊 Tổng chunks: {len(chunks)}")
    print("\n💡 Tiếp theo:")
    print("   - Load JSON vào vector database")
    print("   - Tạo embeddings cho từng chunk")
    print("   - Build RAG pipeline với LangChain/LlamaIndex")
