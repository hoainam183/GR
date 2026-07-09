# Module: `query`

Tầng xử lý truy vấn: định tuyến intent/domain, phân loại độ phức tạp, viết lại (reflection) truy vấn, trích xuất tín hiệu/slot có cấu trúc, tra mã học phần theo ngành, và các prompt phục vụ router/reflection/LLM fallback.

## Files

### `__init__.py`
Re-export API công khai của tầng query (router, reflector, classifier, signals, structured query).

### `router.py`
Lớp `QueryRouter` — phân loại intent (chitchat/rag/tool_search) và domain, hỗ trợ 2 chế độ classifier (nhúng, zero-cost) hoặc llm (OpenAI).
- `route()` — trả về quyết định định tuyến `{intent, domain, domains, confidence}`.
- `_route_classifier()` — định tuyến 2-pass: pass 1 không lịch sử, pass 2 prepend lịch sử khi confidence thấp.
- `build_routing_input()` — prepend ngữ cảnh hội thoại cho câu hỏi follow-up ngắn / có đại từ chỉ định.
- `_route_llm()` / `_parse_response()` — định tuyến bằng LLM few-shot và parse JSON kết quả.

### `complexity_router.py`
Lớp `ComplexityRouter` — Tier-0 deterministic: phân câu hỏi thành chitchat / simple / complex / unknown bằng regex + tín hiệu.
- `route()` — trả `{tier, reason, confidence[, complex_subtype]}`; `unknown` để pipeline dùng ML/LLM tầng sau.
- `route_tier()` — trả nguyên chuỗi tier (unknown → simple) cho tương thích cũ.
- `_is_single_fact_policy_lookup()` — nhận diện tra cứu 1 sự thật/bảng giữ ở nhánh RAG.

### `domain_classifier.py`
Lớp `DomainClassifier` — classifier nhúng 2 tầng: Stage 1 intent (calibrated LR), Stage 2 domain đa nhãn (OvR LR) trên nhãn RAG.
- `predict()` — phân loại 1 truy vấn, trả intent/domain/domains/confidence/probabilities.
- `train()` — nhúng, huấn luyện cả 2 tầng và trả report đánh giá.
- `save()` / `load()` — lưu/nạp cả 2 classifier + MLB vào 1 file joblib (từ chối format cũ).

### `reflection.py`
Lớp `QueryReflector` — viết lại truy vấn thành standalone query bằng LLM (giải tham chiếu, giải mã lịch sử/profile) kèm hàng loạt guardrail deterministic chống rò rỉ ngữ cảnh và bảo toàn ý gốc.
- `reflect()` — strip PII, gọi LLM rewrite, rồi áp guardrail; trả `{original, rewritten, entities, prompt, ...}`.
- `extract_entities()` — wrapper công khai của trích xuất entity (không gọi LLM).
- `_extract_entities()` — trích major/cohort/course_code/semester theo thứ tự ưu tiên query→profile→history.
- `_revert_major_code_conflation()` — hoàn tác follow-up giữ nhầm mã ngành cũ thay vì thay bằng mã mới (Rule 19).
- `_inject_course_code()` — chèn mã học phần từ catalog vào sau tên môn trong query.
- `_strip_pii_and_noise()` — bỏ MSSV, tên riêng, lời cảm ơn/chào khỏi truy vấn.

### `signals.py`
Trích các tín hiệu truy vấn deterministic (dùng chung bởi router, selector, retriever) qua khớp mẫu accent-fold.
- `analyze_query_signals()` — phân tích truy vấn thành `QuerySignals` (personal_reference, eligibility, freshness, schedule, ...).
- `fold_vietnamese_text()` — bỏ dấu và lowercase để khớp mẫu.
- `extract_key_phrases()` — trích cụm từ ứng viên cho boost BM25 theo cụm.
- `_has_how_many_token()` — phân biệt "mấy" (how many) với "máy" (machine) sau khi bỏ dấu.

### `structured_query.py`
Trích slot có cấu trúc deterministic (mã học phần, mã ngành, khóa, từ loại trừ) trước truy hồi.
- `parse_structured_query()` — trả `StructuredQuery` với course_codes/major_codes/cohorts/exclude_terms.
- `text_contains_excluded_term()` — kiểm tra substring không dấu để lọc sau vector.
- `build_es_must_not_clauses()` — dựng mệnh đề `must_not` cho Elasticsearch từ các từ loại trừ.
- `normalize_query_text()` / `strip_diacritics()` — chuẩn hóa Unicode/dấu gạch và bỏ dấu.

### `course_catalog.py`
Tra mã học phần theo tên môn, luôn scope theo mã ngành (một tên môn có thể ứng nhiều mã ở các CTĐT khác nhau), nạp từ artifact `models/course_catalog.json`.
- `lookup_course_code()` — trả `{code, name, semester, credits}` cho tên môn khớp dài nhất theo ngành.
- `_course_aliases()` — sinh alias viết tắt an toàn (biến thể số La Mã/Ả Rập, shorthand thông dụng).
- `_unique_code_match()` — chỉ trả kết quả khi mọi ứng viên chung 1 mã.

### `prompts.py`
Chứa các prompt/few-shot cho router, reflection, và LLM fallback (chỉ dữ liệu chuỗi, không logic).

### `training_data.py`
Dữ liệu huấn luyện có nhãn cho domain classifier (mẫu single-label và multi-label) kèm hằng nhãn.
- `get_training_data()` — chuyển mẫu single-label sang định dạng multi-label `List[Tuple[str, List[str]]]`.

### `train_classifier.py`
Script CLI huấn luyện `DomainClassifier` và lưu model, kèm sanity check.
- `main()` — nạp data, khởi tạo embedder, train 2 tầng, in report, lưu model, chạy các case kiểm thử.
