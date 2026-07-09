# Module: `scripts`

Tập hợp các script vận hành (CLI/one-off) cho pipeline RAG: crawl dữ liệu, build catalog, tải model, sinh dữ liệu eval, index chunk vào Qdrant/Elasticsearch, đồng bộ metadata, audit metadata, thiết lập index MongoDB và tìm kiếm thử.

## Files

### `auto_crawler.py`
Pipeline tự động đa nguồn (KeHoach + QuyDinh): crawl → clean → chunk → stage duyệt → index (Qdrant + ES) → retention, kèm auto-heal bài cũ có bảng và staging pending review qua MongoDB.
- `GenericCrawler.crawl_new()` — crawl tăng dần các bài mới/đã cập nhật từ ctt.hust.edu.vn.
- `ChunkProcessor.chunk_articles()` — chunk bài viết bằng `KeHoachChunker`, gán nhãn source.
- `DualIndexer.index_chunks()` — embed BGE-M3 + E5 rồi upsert vào Qdrant và Elasticsearch.
- `RetentionManager.cleanup()` — xoá bài quá hạn khỏi JSON, chunks và các store.
- `AutoCrawlPipeline._run_single_pipeline()` — điều phối toàn bộ một pipeline và trả summary.
- `index_staged_crawler_run()` — index một crawler run đã duyệt trong Mongo vào Qdrant/ES.

### `build_course_catalog.py`
Dựng artifact ánh xạ tên học phần → mã học phần từ bảng markdown CTĐT, gom theo `major_code`, ghi ra `query/models/course_catalog.json`.
- `build_catalog()` — quét các file markdown CTĐT và dựng catalog theo major.
- `_parse_course_row()` — trích (mã, tên, tín chỉ, kỳ) từ một hàng bảng markdown.
- `_major_code_for()` — đọc `major_code` phổ biến nhất từ file `*_chunks.json` cùng cấp.
- `main()` — build catalog, ghi file JSON và chạy probe kiểm tra nhanh.

### `download_models.py`
Script chạy một lần để pre-download các model ML local (E5, BGE-M3, BGE reranker) về cache HuggingFace trước khi khởi động backend. Là một script tuần tự, không có hàm.

### `generate_routing_eval_from_chunks.py`
Đọc các file chunk trong `data/`, dùng Gemini sinh câu hỏi sinh viên thực tế cho từng chunk và lưu bộ dữ liệu eval tổng hợp.
- `main()` — nạp chunk, gọi LLM sinh câu hỏi, lọc trùng và ghi `synthetic_100_eval.json`.

### `index_kehoach.py`
Nạp `kehoach_all_chunks.json`, embed BGE-M3 + E5 và upsert vào collection Qdrant `kehoach` theo chế độ tăng dần.
- `load_chunks()` — đọc file chunk JSON.
- `filter_new_chunks()` — chỉ giữ chunk có ID chưa tồn tại trong collection.
- `index_chunks()` — embed và upsert theo batch.
- `main()` — điều phối load → embed → filter → index.

### `index_parent_child.py`
Index các chunk parent-child từ `data/ctdt/*` và `quydinh` vào Qdrant (named vectors) và Elasticsearch (BM25), giữ quan hệ cha-con qua metadata.
- `discover_chunk_files()` — tìm các file chunk parent-child theo cấu hình collection.
- `prepare_chunk_for_indexing()` — chuẩn hoá và enrich metadata cho một chunk.
- `index_to_qdrant()` — embed và upsert chunk vào Qdrant.
- `index_to_elasticsearch()` — index chunk searchable (bỏ parent/header) vào ES.
- `run_indexing()` — điều phối pipeline index cho một collection.

### `index_quydinh.py`
Nạp mọi `*_chunks.json` trong một thư mục (mặc định olmocr), lọc chunk indexable rồi embed + upsert vào Qdrant theo chế độ tăng dần.
- `load_chunks_from_dir()` — gộp các file chunk trong thư mục, lọc theo policy indexable.
- `filter_new_chunks()` — bỏ chunk đã có ID trong collection.
- `index_chunks()` — embed BGE-M3 + E5 và upsert theo batch.
- `main()` — điều phối load → embed → filter → index.

### `index_stsv.py`
Nạp `stsv_all_chunks.json`, embed BGE-M3 + E5 và upsert vào collection Qdrant `stsv` (hỗ trợ CLI đổi path/collection/batch).
- `load_chunks()` — đọc file chunk JSON.
- `index_chunks()` — embed và upsert theo batch.
- `parse_args()` — khai báo tham số CLI.
- `main()` — điều phối load → embed → index.

### `index_to_es.py`
Re-index các collection Qdrant sang Elasticsearch cho hybrid BM25, có smoke test plugin phân tích tiếng Việt và enrich metadata theo từng collection.
- `scroll_all_points()` — duyệt toàn bộ point trong một collection Qdrant.
- `enrich_collection_metadata()` — thêm metadata hỗ trợ BM25 theo collection (course/semester).
- `smoke_test_vietnamese_plugin()` — kiểm tra plugin `vi_analyzer` đã cài và hoạt động.
- `index_collection()` — index một collection Qdrant vào một ES index.
- `main()` — chạy smoke test rồi index các collection được chọn.

### `metadata_audit.py`
Quét các file JSON trong `data/`, báo cáo độ phủ và fill rate của các field metadata theo từng collection, kèm gợi ý enrich.
- `scan_collection()` — quét một thư mục collection và thống kê field metadata.
- `generate_suggestions()` — sinh gợi ý cải thiện dựa trên field quan trọng thiếu/thấp.
- `run_audit()` — chạy audit đầy đủ, in tóm tắt và ghi báo cáo JSON.

### `search_multi.py`
Script chạy thử hybrid search trên nhiều collection (stsv + quydinh) với tham số cấu hình cứng, in kết quả kèm điểm chi tiết.
- `print_results()` — in kết quả search kèm điểm vector/keyword/RRF cho một query.

### `setup_mongo_indexes.py`
Tạo các index MongoDB cho collection `agent_traces` phục vụ truy vết agent.
- `setup_agent_trace_indexes()` — tạo index trên `session_id`, `created_at`, `tool_names_sequence`.
- `main()` — đọc tham số URI/DB rồi tạo index và in tên.

### `update_data.py`
Pipeline cập nhật dữ liệu: ingest tài liệu (mock), đồng bộ metadata và reload ValidityFilter qua API.
- `ingest_document()` — hàm ingest tài liệu (hiện là mock minh hoạ).
- `sync_metadata()` — gọi `update_metadata.main()` để đồng bộ metadata chunk.
- `trigger_validity_reload()` — gọi API reload registry ValidityFilter.
- `main()` — điều phối theo cờ CLI (metadata-only / ingest / reload).

### `update_metadata.py`
Đồng bộ metadata từ các file `*_chunks.json` đã sửa vào Qdrant + Elasticsearch theo ID mà không re-embed (hỗ trợ overwrite hoặc merge).
- `load_chunks()` — nạp chunk theo `source_type` (file/dir/ctdt_multi) và lọc theo level.
- `build_pairs()` — dựng danh sách (id, payload) cho overwrite hoặc merge.
- `update_collection()` — cập nhật payload Qdrant và/hoặc ES cho một collection.
- `main()` — lặp qua các collection cấu hình và cập nhật theo target.

### `__init__.py`
File rỗng, đánh dấu `scripts` là một Python package.
