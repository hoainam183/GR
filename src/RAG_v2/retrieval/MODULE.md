# Module: `retrieval`

Lớp truy hồi hybrid: kết hợp vector search (Qdrant, hai vector BGE-M3 + E5) với BM25 (Elasticsearch, phân tích tiếng Việt) qua RRF/linear fusion, có tiền lọc metadata theo collection, chọn collection theo domain, mở rộng ngữ cảnh cha, giải chéo tham chiếu điều/khoản, lọc văn bản hết hiệu lực và HyDE fallback.

## Files

### `__init__.py`
Export các lớp chính và factory `create_retriever(settings)` tạo `MultiCollectionSearch` từ danh sách collection trong settings.

### `base.py`
Định nghĩa interface trừu tượng cho mọi retriever.
- `BaseRetriever.search()` — method trừu tượng truy hồi tài liệu liên quan cho query.

### `config.py`
Hằng số cấu hình mặc định cho HyDE post-rerank fallback (`HYDE_ENABLED`, `HYDE_MIN_RESULTS`, `HYDE_CONFIDENCE_THRESHOLD`), phản chiếu trong `Settings`.

### `qdrant_store.py`
Quản lý collection Qdrant với hai named-vector (`bge_m3`, `e5`): tạo collection, index, tìm kiếm fuse hai vector, lookup và cập nhật/xóa payload.
- `QdrantStore.search()` — query batch hai vector rồi fuse điểm có trọng số.
- `QdrantStore.index_documents()` — upsert điểm với hai vector + payload theo batch.
- `QdrantStore.get_by_metadata()` — scroll lookup nhanh theo filter payload.
- `QdrantStore.update_metadata_by_filter()` — cập nhật payload cho các điểm khớp filter.
- `QdrantStore._fuse_results()` — max-normalize theo model và cộng điểm có trọng số.

### `elasticsearch_store.py`
Quản lý index Elasticsearch BM25 với analyzer tiếng Việt (plugin CocCoc `vi_tokenizer`, fallback standard), synonym/stopword, và `search_text` làm sạch Markdown.
- `ElasticsearchStore.keyword_search()` — BM25 multi-match + boost key-phrase, fallback fuzzy.
- `ElasticsearchStore.index_documents()` — bulk-index chunk kèm dựng `search_text`.
- `ElasticsearchStore.metadata_filter_search()` — filter-only trả về danh sách doc ID (bước tiền lọc).
- `ElasticsearchStore.get_latest_chunk_ids_by_date()` — lấy ID chunk mới nhất theo `date_str` (freshness kehoach).
- `ElasticsearchStore.resolve_chunk_ids_for_qdrant()` — ánh xạ ID metadata sang ES `_id` cho Qdrant.

### `hybrid_search.py`
Gộp kết quả vector Qdrant + BM25 ES cho một collection bằng RRF (chủ yếu dùng cho test/debug; luồng chính gọi trực tiếp qua `MultiCollectionSearch`).
- `HybridSearch.search()` — chạy vector + keyword rồi fuse RRF, lọc ngưỡng, cắt top-K.
- `HybridSearch._rrf_fuse()` — hợp nhất hai danh sách theo rank có trọng số.
- `rrf_score()` — tính điểm Reciprocal Rank Fusion cho một rank.

### `multi_collection_search.py`
Chạy hybrid search song song (threadpool) trên nhiều collection, tiền lọc metadata → `HasIdCondition` cho Qdrant, rồi fuse toàn cục (linear hoặc RRF) kèm bonus recency cho kehoach.
- `MultiCollectionSearch.search()` — điều phối tiền lọc, fetch song song, pooling và fusion toàn cục.
- `MultiCollectionSearch.from_collection_names()` — factory dựng store/HybridSearch theo tên collection.
- `MultiCollectionSearch._resolve_filter_with_fallback()` — chạy chuỗi fallback ES metadata, dựng filter Qdrant/ES.
- `MultiCollectionSearch._score_fusion()` — fuse linear max-normalize có trọng số + recency.
- `MultiCollectionSearch._score_fusion_rrf()` — fuse theo rank RRF, rescale recency về thang RRF.
- `MultiCollectionSearch._resolve_fusion_weights()` — nghiêng trọng số về keyword cho query dạng môn học.

### `metadata_filters.py`
Trích filter metadata theo từng collection (chuỗi fallback ES) trước hybrid search; chứa bảng mã ngành ↔ tên ngành, chuẩn hóa/nhận diện mã ngành, khóa và ngày.
- `build_collection_filters()` — dựng `CollectionFilter` cho từng collection từ query/major/cohort.
- `CtdtFilterExtractor.extract()` / `QuyDinhFilterExtractor.extract()` / `KeHoachFilterExtractor.extract()` — logic filter cho ctdt/quydinh/kehoach.
- `enrich_major_references_for_query()` — bơm cặp mã↔tên ngành vào query truy hồi.
- `strip_major_from_query_for_retrieval()` — bỏ nhắc ngành khi đã lọc bằng metadata.
- `expand_major_in_query_for_reranking()` — thay mã ngành bằng tên đầy đủ để rerank tốt hơn.
- `kehoach_recency_bonus()` — tính điểm cộng recency cho tài liệu kehoach.

### `collection_selector.py`
Chọn các collection cần tìm dựa trên kết quả phân loại domain và tín hiệu query; nới rộng collection theo trait (quy định/thủ tục/lịch...).
- `CollectionSelector.select()` — ánh xạ domain→collection, mở rộng fallback khi confidence thấp.
- `augment_collections_for_query()` — thêm quydinh/stsv/ctdt/kehoach theo tín hiệu query.
- `_should_add_kehoach_low_confidence()` — quyết định thêm kehoach khi routing biên.

### `query_expander.py`
Sinh 2-3 biến thể truy vấn (gốc / tập trung entity / chỉ chủ đề) để tăng recall trước khi rerank.
- `MultiQueryExpander.expand()` — sinh danh sách biến thể query.
- `MultiQueryExpander._build_entity_query()` — dựng query ngắn ưu tiên entity cho BM25.
- `MultiQueryExpander._build_topic_query()` — bỏ entity để mở rộng phủ ngữ nghĩa.

### `hyde.py`
HyDE fallback: sinh câu trả lời giả định qua LLM, embed nó và dùng vector đó cho vòng tìm thứ hai khi recall thấp.
- `HyDEExpander.generate_embedding()` — sinh giả thuyết rồi embed thành vector.
- `HyDEExpander.generate_hypothesis()` — gọi LLM tạo câu trả lời giả định (fallback về query gốc).
- `should_use_hyde()` — quyết định có kích hoạt HyDE theo số kết quả/điểm rerank.

### `parent_context.py`
Mở rộng kết quả con bằng nội dung chunk cha (pattern "search trên con, đọc từ cha"); cache expander theo cấu hình để tái dùng kết nối Qdrant.
- `ParentContextExpander.expand_with_parents()` — gắn `parent_context` cho các chunk con.
- `ParentContextExpander._fetch_parents()` — fetch chunk cha theo ID từ Qdrant.
- `get_parent_expander()` — trả expander đã cache theo `(host, port, max_chars)`.

### `reference_resolver.py`
Quét chunk tìm tham chiếu chéo tiếng Việt ("khoản 1 Điều 5", "xem Điều 12") và chèn các điều/khoản được tham chiếu cùng tài liệu vào ngay sau chunk.
- `ReferenceResolver.resolve()` — quét kết quả, giải tham chiếu và bổ sung chunk (có dedup).
- `extract_references()` — trích các tham chiếu điều/khoản từ text.
- `ReferenceResolver._lookup_by_metadata()` — scroll Qdrant cùng `document_id` tìm điều đúng.
- `ReferenceResolver._lookup_by_search()` — fallback tìm semantic khi metadata không khớp.

### `validity_filter.py`
Loại các chunk thuộc văn bản đã bị thay thế dựa trên `data/document_lineage.json`, chạy sau rerank; có bảo vệ tối thiểu số kết quả.
- `ValidityFilter.filter()` — bỏ chunk thuộc doc superseded, giữ tối thiểu `min_results`.
- `ValidityFilter.is_superseded()` — khớp mờ source với pattern văn bản đã thay thế.
- `ValidityFilter.reload()` — nạp lại registry sau khi cập nhật dữ liệu.

### `exam_schedule_store.py`
ES store riêng cho lịch thi (bảng có cấu trúc): filter keyword mã/phòng/kíp, trường `date` thật cho khoảng ngày, và `search_text` cho tên môn.
- `ExamScheduleESStore.search()` — chạy query bool và sắp theo ngày/kíp (hoặc điểm khi tìm theo tên).
- `ExamScheduleESStore.build_query()` — dựng bool query từ các filter (tách được để test).
- `ExamScheduleESStore.index_records()` — bulk-index các dòng lịch thi.
- `ExamScheduleESStore.delete_by_source_file()` — xóa các dòng đã index từ một file nguồn.

### `search_stsv.py`
Script demo chạy hybrid search thật trên collection `stsv` với vài query mẫu và in top-5 kết quả.
- `main()` — nạp embedder, kết nối store, chạy `HybridSearch.search()` và in kết quả.

### `index_stsv_to_es.py`
Script tiện ích scroll toàn bộ điểm từ một collection Qdrant và index sang Elasticsearch cho hybrid search.
- `main()` — scroll Qdrant, gom text/metadata/id rồi gọi `index_documents`.
- `scroll_all_points()` — generator duyệt toàn bộ điểm trong collection Qdrant.
