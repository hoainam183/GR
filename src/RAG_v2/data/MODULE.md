# Module: `data`

Kho dữ liệu nguồn của hệ RAG: tài liệu đã crawl/clean, kết quả chunking và một vài script chuẩn bị dữ liệu. Tổ chức theo từng loại tài liệu (chương trình đào tạo, kế hoạch, lịch thi, quy định, sổ tay sinh viên).

## Cấu trúc

### `ctdt/`
Chương trình đào tạo theo ngành (`soict`, `dien-dientu`, `cokhi`, `hoa`, `toan`, `vatlieu`). Mỗi ngành có `output_docling/` (parse thô), `clean_data/` (đã làm sạch) và `chunks_recursive_parent_child/` (chunk parent–child).

### `kehoach/`
Kế hoạch/bài viết crawl từ cổng CTT. Gồm dữ liệu (`kehoach_list_output_full.json`, `baiviet_output_full.json`), `chunks/` và các script crawl/xử lý: `crawl.py`, `crawl_detail.py`, `reprocess_content_text.py` (khôi phục link tương đối trong `content_text`).

### `quydinh/`
Quy định/quy chế. `olmocr/` (OCR), `output_full.json`, `chunks/`, `admin_upload/` (chunk từ tài liệu admin tải lên, dạng recursive/hierarchical theo id) và `tag_majors.py` (gắn tag ngành, gồm danh sách ngành CT tiên tiến/tiếng Anh).

### `stsv/`
Sổ tay sinh viên: nhiều file JSON theo chủ đề (thủ tục, biểu mẫu, hoạt động, cẩm nang...), `chunks/stsv_all_chunks.json` và `clean_data/` (`clean_data.py` làm sạch HTML/bỏ dấu, `data.json`).

### `lichthi/`
Lịch thi dạng PDF gốc (giữa kỳ/cuối kỳ) dùng cho pipeline nạp tài liệu.

### `document_lineage.json`
Bản ghi nguồn gốc/liên kết giữa các tài liệu đã nạp.
