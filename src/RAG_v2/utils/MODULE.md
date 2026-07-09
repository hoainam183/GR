# Module: `utils`

Các helper dùng chung, nhẹ về phụ thuộc: lưu file, tracing request, chính sách index chunk, mở rộng thuật ngữ học thuật, parse email HUST, tách từ tiếng Việt, chuẩn hoá bảng/ngày, và vài script trích xuất dữ liệu.

## Files

### `storage.py`
Trừu tượng lưu trữ file upload; `StorageBackend` (ABC) và hiện thực `LocalStorage` ghi vào `{base_dir}/{doc_id}/`.
- `LocalStorage.save_upload()` — lưu PDF/DOCX đã upload (tên cố định `original.<ext>`, chống path traversal), trả path tương đối.
- `LocalStorage.save_text()` — lưu nội dung text (markdown/cleaned) theo suffix.
- `LocalStorage.read_text()` — đọc text, chặn đường dẫn thoát khỏi `base_dir`.
- `LocalStorage.delete_all()` — xoá toàn bộ thư mục của một document.

### `tracing.py`
Theo dõi thời gian từng stage trong vòng đời một request.
- `RequestTrace.stage()` — context manager tính thời gian một stage (cộng dồn nếu gọi nhiều lần).
- `RequestTrace.summary()` — trả dict tổng hợp (correlation_id, stages, total_ms, metadata, errors) để log/lưu Mongo.
- `RequestTrace.log_summary()` — log 1 dòng INFO xếp theo stage chậm nhất.
- `trace_stage()` — decorator (sync-only) tự tính thời gian hàm khi có kwarg `trace`.

### `chunk_indexing.py`
Chính sách quyết định chunk nào được embed/index và lưu Qdrant, dựa trên `metadata.level`.
- `is_indexable_chunk()` — True nếu chunk được index cho SEARCH (loại `parent`/`header`).
- `is_qdrant_storable()` — True nếu chunk được lưu Qdrant (chỉ loại `header`; parent vẫn lưu để fetch theo ID).

### `terminology.py`
Bảng thuật ngữ viết tắt HUST và hàm mở rộng viết tắt trong truy vấn.
- `TerminologyAlias` — dataclass cặp (thuật ngữ đầy đủ, viết tắt).
- `expand_academic_abbreviations()` — thêm alias song song (đầy đủ/viết tắt) vào text, idempotent, không đổi ý nghĩa.

### `parse_hust_email.py`
Suy ra thông tin sinh viên từ địa chỉ `@sis.hust.edu.vn`.
- `parse_hust_email()` — trả `{full_name, student_id, cohort, major}`; raise `ValueError` nếu sai domain hoặc thiếu số cuối.

### `vietnamese_segmenter.py`
Tách từ tiếng Việt (dùng underthesea nếu có, fallback từ điển từ ghép) để cải thiện BM25.
- `is_available()` — báo underthesea có sẵn hay không.
- `segment()` — tách text, nối các âm tiết của từ ghép bằng dấu gạch dưới.
- `segment_for_indexing()` — trả `"<gốc>\n<đã tách>"` để khớp cả cấp âm tiết lẫn cấp từ khi index.
- `segment_query()` — tách truy vấn tìm kiếm.
- `get_compound_variants()` — trả cả dạng gốc và dạng đã tách để tăng recall.

### `html_table_markdown.py`
Chuyển thẻ `<table>` HTML (BeautifulSoup) sang bảng Markdown, xử lý rowspan/colspan, để giữ cấu trúc 2D khi clean nội dung crawl.
- `convert_table_to_markdown()` — dựng grid từ dữ liệu bảng đã parse rồi render Markdown, xử lý header nhiều dòng và ô gộp.
- `table_to_markdown()` — render một thẻ `<table>` thành Markdown.
- `replace_tables_with_markdown()` — thay mọi `<table>` trong soup bằng bảng Markdown tại chỗ (xử lý bảng lồng từ trong ra ngoài).

### `vn_datetime.py`
Chuẩn hoá ngày và kíp thi trong lịch thi HUST (các định dạng d/m/yyyy, dd-mm-yyyy, datetime, serial Excel...).
- `normalize_exam_date()` — chuẩn hoá ô "Ngày" thành `(datetime|None, "DD/MM/YYYY"|None)`.
- `normalize_session()` — chuẩn hoá ô "Kíp thi" thành `(nhãn kíp, giờ bắt đầu)` tra theo `kip_time_map`.

### `extract_questions.py`
Script + thư viện trích trường `question` từ file JSONL dataset.
- `extract_questions()` — đọc JSONL, ghi câu hỏi (tuỳ chọn unique/JSONL), trả `(total, written, skipped)`.
- `main()` — entry point CLI với các cờ `--unique`, `--jsonl`.

### `extract_text.py`
Script nhỏ dump các giá trị `payload.text` từ JSON scroll của Qdrant ra `texts_quydinh.json`.
- `extract_texts()` — trích danh sách text từ dict `{result:{points}}` hoặc list points.

### `__init__.py`
Marker package (không export gì).
