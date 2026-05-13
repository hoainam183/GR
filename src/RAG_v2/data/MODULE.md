# Data Module

Module này quản lý toàn bộ dữ liệu đầu vào cho hệ thống RAG (Retrieval-Augmented Generation), bao gồm dữ liệu thô, dữ liệu đã làm sạch và các file chunks đã được vector hóa/sẵn sàng để indexing.

## 1. Nguồn dữ liệu (Data Sources)

Dữ liệu được thu thập từ các nguồn chính thống của Đại học Bách khoa Hà Nội, chia thành 4 nhóm chính:

| Nhóm | Mô tả | Nguồn | Định dạng gốc |
| :--- | :--- | :--- | :--- |
| **stsv** | Sổ tay sinh viên | [sv-ctt.hust.edu.vn](https://sv-ctt.hust.edu.vn) | HTML/JSON (Crawl) |
| **quydinh** | Các văn bản quy định, quy chế đào tạo | Ban Đào tạo / CTSV | HTML (Crawl) / PDF (Scan) |
| **ctdt** | Chương trình đào tạo các ngành/viện | [soict.hust.edu.vn](https://soict.hust.edu.vn) | PDF/Docx |
| **kehoach** | Thông báo, kế hoạch học tập, thời khóa biểu | [ctt.hust.edu.vn](https://ctt.hust.edu.vn) | HTML (Crawl) |

## 2. Chiến lược Chunking


Tùy vào đặc thù cấu trúc của từng loại dữ liệu, các chiến lược chunking khác nhau được áp dụng:

### 2.1. Semantic/Section-based Chunking (Dùng cho `stsv`, `kehoach`, một phần `quydinh`)
*   Dữ liệu được chia theo các mục (Section) hoặc bài viết có sẵn trên trang web.
*   Mỗi chunk thường tương ứng với một chủ đề con hoặc một thông báo hoàn chỉnh về ý nghĩa.
*   **Công cụ**: Custom script sử dụng BeautifulSoup, Regex và Python scripts (`crawl.py`).

### 2.2. Recursive Parent-Child Chunking (Dùng cho `ctdt`, một phần `quydinh`)
*   Dữ liệu từ các file PDF/Docx được phân tách dựa trên cấu trúc tiêu đề (Header H1 -> H4) của Markdown.
*   Duy trì mối quan hệ cha-con (Parent-Child) để hỗ trợ retrieval theo ngữ cảnh rộng hơn (Parent Retrieval).
*   Sử dụng Metadata để lưu trữ đường dẫn phân cấp (`hierarchy_path`), và mối quan hệ giữa các Node (`parent_id`, `child_count`).
*   **Công cụ**: `olmocr` (convert PDF sang Markdown), custom recursive splitters.

## 3. Cấu trúc Chunk và Metadata Schema

Mỗi chunk được lưu trữ dưới dạng một Object JSON. Cấu trúc cơ bản luôn bao gồm `chunk_id` (hoặc `id`), `content` và `metadata`. Các trường metadata được thiết kế chi tiết để phục vụ pre-filtering và reranking.

### 3.1. Metadata nhóm `stsv` (Sổ tay sinh viên)
*   **Trường định danh**: `doc_id`, `type_doc`, `title`.
*   **Trường ngữ cảnh**: `section_context`, `item_label`.
*   **Trường meta-info**: `time_create`, `chunk_index`, `total_chunks`, `chunk_size`, `has_links`.

### 3.2. Metadata nhóm `kehoach` (Kế hoạch)
*   **Trường định danh**: `baiviet_id`, `url`, `title`.
*   **Trường ngữ cảnh**: `category`, `tag_in_title`, `date_str`, `source_list_path`, `section_label`.
*   **Trường meta-info**: `source`, `chunk_index`, `total_chunks`, `chunk_size`.

### 3.3. Metadata nhóm `quydinh` (Quy định, Quy chế)
**Đối với dạng Web Crawl (tương tự Kế hoạch):**
*   `baiviet_id`, `title`, `url`, `category`, `date_str`, `applicable_cohort`, `applicable_major`...

**Đối với dạng Recursive PDF/Scan:**
*   **Trường định danh**: `doc_title`, `doc_type`, `document_type`.
*   **Trường phân cấp (Hierarchy)**: `level` (parent/child), `hierarchy_path`, `section_h1` đến `section_h4`.
*   **Trường quan hệ**: `parent_id`, `child_count`.
*   **Trường meta-info**: `chunk_index`, `total_chunks`, `chunk_size`, `chunk_type`, `has_table`.
*   **Trường Scope/Effectiveness**: `effective_date`, `expiry_date`, `applicable_cohort`, `applicable_major`.

### 3.4. Metadata nhóm `ctdt` (Chương trình đào tạo)
Sử dụng chung schema đệ quy với `quydinh`, nhưng có thêm các trường đặc thù ngành học:
*   `major_name` (Ví dụ: "Khoa học máy tính").
*   `major_code` (Ví dụ: "IT1").

## 4. Ví dụ đại diện (Representative Examples)

### Ví dụ 1: Loại `stsv` (Semantic Chunk)
```json
{
  "chunk_id": "2f651316-3663-45ae-b365-47b65a6b3d58",
  "content": "[[Ban Đào tạo] Hướng dẫn thủ tục, biểu mẫu, thắc mắc về học tập, học phí. | Sổ tay SV | I. Giới thiệu chung]\nI. Giới thiệu chung\nBan Đào tạo tiếp nhận các đề xuất, thắc mắc, phản hồi của sinh viên qua thư điện tử (email), hạn chế tối đa việc sinh viên phải lên gặp trực tiếp...",
  "metadata": {
    "doc_id": 69,
    "title": "[Ban Đào tạo] Hướng dẫn thủ tục, biểu mẫu, thắc mắc về học tập, học phí.",
    "type_doc": "Sổ tay SV",
    "time_create": "2026-01-09 09:05:27",
    "section_context": "I. Giới thiệu chung",
    "item_label": null,
    "chunk_index": 0,
    "total_chunks": 36,
    "chunk_size": 681,
    "has_links": false
  }
}
```

### Ví dụ 2: Loại `ctdt` (Recursive Parent Chunk)
```json
{
  "id": "f839d577-3086-478b-b6e5-2a70f646f64d",
  "chunk_id": "chunk_0001",
  "readable_id": "chunk_0001",
  "content": "## CỬ NHÂN KHOA HỌC MÁY TÍNH\n### Trường Đại học Bách Khoa Hà Nội – Viện Công nghệ Thông tin và Truyền thông\n...",
  "metadata": {
    "doc_type": "curriculum",
    "level": "parent",
    "doc_title": "CHƯƠNG TRÌNH GIÁO DỤC ĐẠI HỌC 2017",
    "source": "",
    "section_h1": "CHƯƠNG TRÌNH GIÁO DỤC ĐẠI HỌC 2017",
    "section_h2": "CỬ NHÂN KHOA HỌC MÁY TÍNH",
    "section_h3": null,
    "section_h4": null,
    "hierarchy_path": "CHƯƠNG TRÌNH GIÁO DỤC ĐẠI HỌC 2017 > CỬ NHÂN KHOA HỌC MÁY TÍNH",
    "chunk_index": 1,
    "total_chunks": 108,
    "chunk_size": 413,
    "chunk_type": "parent",
    "has_table": true,
    "parent_id": null,
    "child_count": 1,
    "effective_date": null,
    "expiry_date": null,
    "applicable_cohort": null,
    "applicable_major": null,
    "document_type": "curriculum",
    "major_name": "Khoa học máy tính",
    "major_code": "IT1"
  }
}
```

### Ví dụ 3: Loại `kehoach` (Kế hoạch / Thông báo)
```json
{
  "chunk_id": "1c439f64-e234-44b2-9d7c-b416ba23fd81",
  "content": "[TIẾP NHẬN TRỞ LẠI HỌCTỪ KỲ HÈ 20253...]\nLịch tiếp nhận trở lại học từ kỳ hè năm 2025-2026 (20253)...",
  "metadata": {
    "baiviet_id": 28237,
    "title": "TIẾP NHẬN TRỞ LẠI HỌCTỪ KỲ HÈ 20253 VÀ KỲ 1 NĂM HỌC 2026-2027 (20261)",
    "category": "ĐTĐH",
    "tag_in_title": "DTDH",
    "date_str": "5/5/2026",
    "url": "https://ctt.hust.edu.vn/DisplayWeb/DisplayKeHoach?kehoach=28237",
    "source": "kehoach",
    "section_label": null,
    "chunk_index": 0,
    "chunk_size": 1000,
    "total_chunks": 2,
    "source_list_path": "/DisplayWeb/DisplayListKeHoach"
  }
}
```

## 5. Quản lý phiên bản (Lineage)

File `document_lineage.json` lưu trữ lịch sử cập nhật của các văn bản. Khi một quy định mới được ban hành (ví dụ: Quy chế 2025 thay thế Quy chế 2023), hệ thống sẽ dựa vào file này để:
1. Đánh dấu các chunk cũ là `superseded`.
2. Ưu tiên các chunk từ tài liệu `active` trong quá trình retrieval.
