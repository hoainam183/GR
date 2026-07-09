# Module: `pipeline`

Điều phối toàn bộ luồng RAG end-to-end (định tuyến → truy hồi → rerank → sinh câu trả lời) và luồng xử lý tài liệu admin (convert → clean → chunk → embed → index). `RAGPipeline` là singleton chạy request người dùng; `DocumentPipeline` chạy nền cho quản trị viên.

## Files

### `__init__.py`
Lazy re-export `RAGPipeline` và `DocumentPipeline` qua `__getattr__` để tránh import nặng khi chưa dùng.

### `rag_pipeline.py`
Lớp `RAGPipeline` — điểm vào chính cho truy vấn người dùng: khởi tạo retrieval service dùng chung, router, reflector, chat LLM, self-eval, agent; và triển khai định tuyến 3 tầng độ phức tạp.
- `query()` — chạy 1 truy vấn không streaming (route → chitchat/rag flow), log MongoDB.
- `query_stream()` — stream token theo nhánh chitchat / complex (agent) / simple (rag), xuất metadata qua `metadata_out`.
- `query_v3()` — điểm vào thông minh: reflection trước, rồi quyết định độ phức tạp để chọn simple/complex/chitchat.
- `query_agent()` — ép chạy qua agent, tự fallback về RAG v2 khi agent lỗi/tắt.
- `_decide_complexity()` — quyết định simple/complex qua 3 tầng (regex Tier0 → ML Tier1 → LLM Tier2).
- `_llm_domain_classify()` — Tier-3: gọi LLM phân loại domain khi classifier tự tin thấp.
- `commit_llm_config_reload()` / `prepare_llm_config_reload()` — hot-swap cấu hình LLM lúc chạy.

### `rag_helpers.py`
Hàm phụ trợ cho pipeline: cổng kích hoạt Tier-3, tiện ích timing và cache key.
- `_should_trigger_tier3()` — quyết định có gọi fallback LLM domain hay không (bỏ qua khi 1 domain trội rõ).
- `_build_cache_key()` — tạo cache key gọn từ câu hỏi + 2 lượt lịch sử gần nhất.
- `_chunk_for_stream()` — cắt câu trả lời đã hoàn tất thành mảnh nhỏ để stream mượt.
- `_merge_timings()` / `_log_timings()` — gộp và log breakdown thời gian theo stage.

### `rag_runtime.py`
Dựng runtime cho pipeline: chuyển `Settings` sang cfg dict, xây Tavily tool, và bó các thành phần LLM để hot-swap.
- `_settings_to_cfg()` — map `Settings` sang cfg dict mà các flow mong đợi.
- `_build_tavily_tool()` — tạo client web-search khi có API key hợp lệ.
- `_should_enable_self_evaluator()` — quyết định bật self-eval (không tự bật theo Tavily).
- `_PreparedLLMRuntime` — dataclass đóng gói cfg/chat/self_eval/reflector/agent/tavily cho hot swap.

### `chunker_factory.py`
Ánh xạ chiến lược chunking → lớp chunker và chuẩn hóa kết quả chunk; bảo vệ các key metadata quan trọng khỏi override của admin.
- `_create_chunker()` — tạo chunker theo strategy (recursive/hierarchical/olmocr), fallback recursive cho PDF.
- `_run_chunker()` — chạy chunker và chuẩn hóa về `(chunks, stats)`.
- `_sanitize_metadata_overrides()` — loại bỏ các key được bảo vệ khỏi metadata admin cung cấp.

### `document_pipeline.py`
Lớp `DocumentPipeline` — điều phối vòng đời tài liệu admin qua MongoDB, mỗi bước cập nhật `status` và chạy được từ `BackgroundTasks`; tài nguyên nặng (embedder, store) lazy-load.
- `convert_pdf()` — convert PDF/DOCX → markdown (pymupdf4llm/docling/pdfplumber, fallback OCR khi rỗng).
- `clean()` / `llm_clean()` — làm sạch markdown bằng regex, và tùy chọn reformat cấu trúc bằng LLM.
- `chunk()` — chunk nội dung, lưu chunk vào MongoDB, fallback recursive khi 0 chunk.
- `embed_and_index()` — embed BGE-M3 + E5 rồi index vào Qdrant + Elasticsearch, remap parent_id.
- `run_full_pipeline()` — chạy tuần tự convert → clean → chunk, dừng khi lỗi.
- `rollback()` / `delete_indexed_data()` — lùi trạng thái tài liệu và xóa dữ liệu đã index.
- `set_shared_embedders()` — tái dùng embedder query-time để tránh OOM khi load trùng.

### `flows/__init__.py`
Package re-export toàn bộ API lịch sử của `pipeline.flows` từ các submodule.

### `flows/coordinators.py`
Các orchestrator luồng: chitchat và RAG (bản thường + streaming) — ghép reflection, embed, search, rerank, HyDE, validity filter, self-eval, Tavily fallback, cache.
- `rag_flow()` — luồng RAG đầy đủ non-streaming (reflect → search → rerank → generate → self-eval → web fallback).
- `rag_flow_stream()` — biến thể streaming: truy hồi chạy trước rồi stream phần sinh câu trả lời.
- `chitchat_flow()` / `chitchat_flow_stream()` — luồng chitchat gọi thẳng chat model, không truy hồi.
- `_chunk_cached_answer()` — cắt câu trả lời cache thành mảnh để render SSE dần.

### `flows/common.py`
Tiện ích cấp thấp và các hàm đọc cfg dùng chung giữa các submodule flow.
- `_cfg_bool()` / `_cfg_int()` / `_cfg_float()` / `_cfg_str_list()` — đọc cfg an toàn với fallback.
- `_fold_vietnamese()` — bỏ dấu tiếng Việt để so khớp text bền vững.
- `_is_context_length_error()` — nhận diện lỗi vượt context length của LLM.
- `_elapsed_ms()` / `_log_timings()` — đo và log thời gian.

### `flows/context.py`
Định dạng context, giải ngân sách ký tự và gộp context nội bộ với web.
- `_format_context()` — chuyển tài liệu truy hồi thành chuỗi context giới hạn theo ngân sách, chèn metadata ngành/khóa/URL, dedup parent.
- `_resolve_context_budget()` — tính `(per_doc_limit, total_budget)` theo loại truy vấn.
- `_merge_local_and_web_context()` — ghép context nội bộ và context web Tavily có hướng dẫn ưu tiên.

### `flows/history.py`
Cắt tỉa lịch sử hội thoại theo số lượng và ngân sách ký tự.
- `_trim_history()` — giữ các lượt gần nhất trong giới hạn message-count và char budget.

### `flows/profile.py`
Trích xuất hồ sơ sinh viên từ hội thoại và dựng ghi chú profile cho bước sinh câu trả lời.
- `_profile_note_for_generation()` — quyết định và dựng ghi chú profile chèn vào context sinh câu trả lời.
- `_extract_session_profile()` / `_extract_session_profile_dict()` — quét lịch sử lấy ngành/năm/khóa/GPA.
- `_should_prepend_profile_note()` — chỉ chèn profile khi câu hỏi phụ thuộc profile cá nhân.

### `flows/retrieval_helpers.py`
Helper truy hồi: top_k, candidate pool, kwargs reranker, mở rộng sibling/parent, dedup, sắp xếp.
- `_resolve_top_k()` — tăng top_k cho truy vấn liệt kê danh sách.
- `_resolve_candidate_pool()` — nới pool ứng viên khi routing thiếu tự tin.
- `_expand_parent_context_post_rerank()` / `_expand_with_siblings_pre_rerank()` — mở rộng chunk cha/anh em.
- `_dedup_retrieval_candidates()` — khử trùng theo id, giữ ứng viên điểm cao nhất.
- `_build_collection_scores()` — xây điểm truy vấn xếp hạng cho các collection.

### `flows/rerank_scoring.py`
Cắt cliff điểm theo collection, dựng trace rerank và chấm điểm bằng chứng nội bộ.
- `_apply_score_cliff_per_collection()` — cắt tài liệu tại "vách" điểm số theo từng collection.
- `_build_rerank_trace()` / `_update_rerank_trace_after_fallback()` — dựng/cập nhật trace observability của reranker.
- `_best_explicit_rerank_score()` — điểm rerank cao nhất (None nếu không có).
- `_has_strong_local_evidence()` — có bằng chứng nội bộ đủ mạnh để retry local trước khi gọi web.

### `flows/hyde.py`
HyDE fallback sau rerank khi recall kém.
- `_should_trigger_hyde()` — quyết định chạy HyDE dựa trên số kết quả và điểm rerank.
- `_hyde_fallback_post_rerank()` — sinh giả thuyết, embed, search lại, gộp + rerank lại.

### `flows/tavily.py`
Thực thi search/extract Tavily và lắp ráp kết quả web fallback.
- `_tavily_search_context()` — search domain HUST chính thức (hoặc extract URL), trả context/sources/timings.
- `_tavily_fallback_result()` — search web rồi regenerate câu trả lời trên context web + nội bộ.
- `_tavily_results_to_docs()` — chuyển kết quả Tavily thành source doc chuẩn.
- `_extract_query_year()` — lấy năm học gần nhất trong truy vấn để lọc freshness.

### `flows/web_fallback.py`
Logic quyết định web/Tavily: phát hiện truy vấn động/freshness, khóa route kehoach, và answer quality gate.
- `_build_pre_generation_web_decision()` — quyết định lấy context web trước khi sinh câu trả lời.
- `_build_answer_quality_gate()` — quyết định RAG nội bộ có cần web fallback sau khi sinh.
- `_is_dynamic_web_query()` — nhận diện truy vấn có thể đổi nhanh hơn index nội bộ.
- `_should_lock_kehoach_route()` — khóa route về chỉ kehoach cho truy vấn lịch/freshness rõ ràng.
- `_answer_has_no_info_signal()` — phát hiện câu trả lời "không có thông tin" không cần gọi LLM.

### `flows/cache_policy.py`
Chính sách gating answer-cache và bypass query-cache.
- `_should_cache_final_answer()` — chỉ cache câu trả lời RAG nội bộ ổn định và đã trả lời đủ.
- `_should_bypass_query_cache()` — bỏ qua cache sớm cho dữ liệu động cần làm mới.
- `_build_cache_profile()` — tạo scope `major|cohort` cho cache key, tránh rò rỉ giữa sinh viên.

### `flows/title_match.py`
So khớp tiêu đề thông báo kehoach để gắn link nguồn.
- `_title_mentioned()` — kiểm tra tiêu đề có được nhắc trong câu trả lời (substring hoặc overlap bigram).
- `_normalize_for_match()` — chuẩn hóa text cho so khớp fuzzy.
- `_bigrams()` — sinh tập bigram từ danh sách token.

### `flows/url_sanitize.py`
Làm sạch URL trong câu trả lời (bản thường + streaming).
- `_sanitize_answer_urls()` — sửa link markdown, rút gọn anchor dài, bọc URL thô thành `[tại đây](url)`.
- `_StreamUrlSanitizer.feed()` / `.finalize()` — làm sạch URL inline theo từng chunk stream (buffer link/URL chưa hoàn chỉnh).
- `_raw_url_hold_index()` — xác định vị trí giữ lại đuôi buffer nghi là URL đang stream dở.
