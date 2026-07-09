# Module: `chunking`

Chuyển nguồn Markdown/plain-text/JSON đã làm sạch thành các chunk truy hồi kèm metadata. Gồm nhiều class chunker (mỗi loại nguồn một class), pipeline batch/CLI offline, làm giàu metadata tài liệu và contextualize chunk bằng LLM (tuỳ chọn).

## Files

### `contextualizer.py`
Làm giàu chunk bằng tiền tố ngữ cảnh do LLM sinh, chạy một lần lúc index (Contextual Retrieval kiểu Anthropic).
- `ChunkContextualizer.contextualize()` — thêm câu ngữ cảnh vào đầu `content` từng chunk (bỏ qua parent và chunk quá ngắn).
- `ChunkContextualizer.contextualize_single()` — contextualize một chunk đơn (tiện cho test).

### `enrich_metadata.py`
Trích và ghi metadata cấu trúc hoá cho chunk CTDT (ngày hiệu lực, khoá áp dụng, ngành, loại tài liệu) từ tên file + vùng tiêu đề.
- `extract_document_metadata()` — gom toàn bộ metadata (effective_date, expiry_date, applicable_cohort, applicable_major, document_type).
- `extract_applicable_major()` — suy ngành theo trường "Ngành đào tạo"/"Tên chương trình", H1/H2, map mã chương trình, keyword tên file.
- `classify_document_type()` — phân loại loại CTĐT chỉ từ filename + heading tiêu đề.
- `enrich_chunks()` — ghi 5 trường metadata vào mọi chunk.
- `process_ctdt_directory()` — duyệt cây `ctdt_root/<khoa>/{clean_data,chunks_...}` và enrich từng cặp file.
- `process_fill_empty_source()` — điền `metadata.source` rỗng bằng tên file cho quydinh + ctdt.

### `standalone_pipeline.py`
Pipeline PDF → Markdown → chunk cực gọn, không phụ thuộc phức tạp (chỉ PyMuPDF `fitz`).
- `standalone_pipeline()` — chạy full: extract text, fix tiếng Việt, chunk, lưu markdown + chunks JSON.
- `simple_pdf_to_markdown()` — trích text từ PDF bằng PyMuPDF.
- `simple_chunk_by_article()` — chunk theo "Điều" hoặc theo đoạn nếu không có điều.

### `batch_standalone.py`
Chạy `standalone_pipeline` cho mọi PDF trong một thư mục.
- `batch_process()` — duyệt các file `.pdf`, chunk từng file và in tổng kết.

### `batch_process_pymupdf.py`
Batch chunk các file `.md` (nguồn PyMuPDF4LLM) bằng `ArticleLegalChunkerPyMuPDF`, lưu chunks + báo cáo.
- `batch_process_pymupdf_documents()` — chunk mọi `.md`, lưu JSON và `processing_summary.json`.
- `process_with_different_configs()` — thử nhiều cấu hình (conservative/standard/aggressive).

### `chunker/recursive_chunker.py`
`RecursiveChunker` — chunker parent/child theo section H2 cho Markdown (dùng thật cho ctdt + quydinh); bảo vệ bảng, không overlap.
- `chunk_document()` — pipeline chính: tách H2→parent, split child, trả `(chunks, stats)`.
- `_split_text_to_chunks()` — tách một đoạn thành child kèm metadata + hàng loạt bước hậu xử lý.
- `_build_parent_with_children()` — tạo 1 parent + các child từ một đoạn nội dung.
- `_split_oversized_chunk()` / `_hard_resplit()` — tách chunk quá lớn, đảm bảo không mảnh nào vượt `chunk_size*1.3`.
- `_inject_khoản_context()` — chèn khoản cha cho child bắt đầu bằng điểm con `a) b) c)`.
- `_merge_heading_only_chunks()` — gộp chunk chỉ chứa heading vào chunk kế bên.

### `chunker/olmocr_legal_chunker.py`
`OlmOcrLegalChunker` — chunker văn bản pháp quy từ OLM-OCR (không có markdown heading); dùng thật cho quydinh OLM-OCR, có xử lý phụ lục và fallback recursive.
- `chunk_document()` — pipeline có fallback: parse phân cấp nếu có cấu trúc Điều/Chương, ngược lại dùng RecursiveCharacterTextSplitter.
- `parse()` — parse theo phase header → body → appendix, tạo chunk và gán ID.
- `_process_article()` — tạo parent + child cho một Điều.
- `_fallback_recursive_chunk()` — chunk fallback khi không có cấu trúc pháp lý.
- `chunk_olmocr_file()` / `chunk_olmocr_folder()` — helper chunk một file / cả thư mục.

### `chunker/hierarchical_legal_chunker.py`
`ArticleLevelLegalChunker` — chunker văn bản pháp lý dạng Docling Markdown (heading `#`/`##`, CHƯƠNG/Điều), kiến trúc parent-child.
- `chunk_document()` — pipeline đầy đủ: parse → gán ID → validate, trả `(chunks, stats)`.
- `parse()` — tách header và các Điều, tạo parent-child chunk.
- `_process_article()` — tạo parent + child cho một Điều (nhỏ→1 child, lớn→tách theo khoản).
- `_split_with_table_protection()` — tách Điều nhưng giữ nguyên bảng.
- `add_chunk_ids()` — gán uuid `id` và nối `parent_id` theo cùng schema RecursiveChunker.

### `chunker/hierarchical_legal_chunker_pymupdf.py`
`ArticleLegalChunkerPyMuPDF` — biến thể pháp lý cho heading CHƯƠNG/Điều dạng in đậm `**...**` (nguồn PyMuPDF4LLM); có `split_threshold`, gắn `source_format="pymupdf4llm"`.
- `chunk_document()` — pipeline parse → add IDs → validate.
- `_process_article()` — chỉ tách child khi Điều lớn hơn `split_threshold`.
- `_split_article_into_children()` — tách theo mục số, hỗ trợ overlap theo ký tự.
- `add_chunk_ids()` — gán uuid `id` + `parent_id` (giống bản Docling).

### `chunker/kehoach_chunker.py`
`KeHoachChunker` — chunker cho JSON bài viết thông báo/kế hoạch crawl từ ctt.hust.edu.vn (`content_text`).
- `chunk_document()` — chunk một bài viết thành list chunk kèm metadata (`source="kehoach"`).
- `chunk_file()` — đọc file JSON (mảng hoặc dict) và chunk toàn bộ.
- `_segment()` — phân loại nội dung: ngắn→1 chunk, có mục số→tách mục, còn lại→recursive.
- `_split_text_table_aware()` — tách text không cắt giữa bảng (bảng lớn tách theo hàng).

### `chunker/stsv_chunker.py`
`STSVChunker` — chunker cho JSON Sổ tay Sinh viên (`Description`), nhận diện phần Roman (I. II.) và mục số.
- `chunk_document()` — chunk một dict STSV thành list chunk kèm metadata (`has_links`, `section_context`...).
- `chunk_file()` / `chunk_directory()` — chunk một file / cả thư mục JSON.
- `_segment()` — chọn chiến lược: ngắn / Roman+mục số / mục số / văn xuôi.
- `_split_by_numbered_items()` — tách theo mục số với sequential-tracking, gộp mục ngắn.

### `chunker/markdown_table.py`
Helper thuần xử lý bảng Markdown khi chunk (dùng chung cho nhiều chunker): phát hiện, bảo vệ, tách và vá bảng.
- `has_markdown_table()` / `starts_mid_table()` — nhận biết text có bảng / bắt đầu giữa bảng.
- `protect_tables()` / `restore_tables()` — thay bảng nhỏ bằng placeholder rồi khôi phục để không bị cắt giữa bảng.
- `split_table_by_rows()` — tách bảng lớn theo hàng, lặp lại header + heading cho mỗi mảnh.
- `fix_mid_table_chunks()` — chèn lại header+separator cho chunk bị cắt mất đầu bảng.

### `chunker/base_chunker.py`
`DocumentChunker` (ABC) — lớp cơ sở tham chiếu cho chiến lược chunk; không class production nào kế thừa.
- `chunk_document()` — pipeline mẫu: parse → post-process → split oversized → add IDs.
- `validate_chunks()` / `save_chunks()` — thống kê và lưu chunks ra JSON.

### `chunker/chunking.py`
Code cũ (dead code): helper hàm parse văn bản pháp lý chỉ nhận heading `## Điều`, hardcode đường dẫn, dùng `print`; không được pipeline nào import.
- `parse_legal_document_structure()` — parse cấu trúc phân cấp (title/chương/điều/khoản).
- `chunk_markdown_with_hierarchy()` — hàm chính đọc file markdown và trả chunks.

### `chunker/_init_.py`
File init lỗi tên (`_init_.py` thay vì `__init__.py`) và import sai tên class; không dùng làm package init thật (caller import module cụ thể trực tiếp).
