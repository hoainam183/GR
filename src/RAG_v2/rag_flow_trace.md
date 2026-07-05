# Luồng Xử Lý (Trace) Của Một Query Phức Tạp Trong Hệ Thống RAG_v2

Sơ đồ dấu vết (trace) chi tiết khi một câu hỏi (query) đi từ lúc người dùng gửi API cho đến lúc nhận được câu trả lời từ LLM. Giả định đây là một query đặc biệt đi qua đầy đủ tất cả các bước của hệ thống: Routing → Reflection/Rewrite → Decomposition → Retrieval → Reranking → HyDE → Web Search fallback → LLM Generation → Response mapping.

> **Edge case riêng — lịch thi (Mục 7.7):** câu hỏi lịch thi theo môn cụ thể (vd "phòng thi CH1012 ở đâu") đi theo một nhánh hoàn toàn khác: routing (Mục 1) đưa nó sang Agent thay vì RAG, nhưng bản thân việc tra cứu lại **bỏ qua toàn bộ** Reflection/Decomposition/Retrieval-Qdrant/Reranking/HyDE (Mục 3-7) — nó là một structured lookup thẳng vào Elasticsearch riêng (`exam_schedules` index), không phải vector search. Câu hỏi lịch thi CHUNG (không nêu môn cụ thể, vd "lịch thi cuối kì") thì vẫn đi đúng luồng RAG v2 cổ điển qua collection `kehoach`.

> Tài liệu này đã được đối chiếu trực tiếp với source code (không suy đoán). Mọi tên hàm, số dòng, hằng số, giá trị mặc định đều được đọc từ code thực tế tại thời điểm viết.

---

## 1. Tiếp nhận Request & Khởi tạo Pipeline

- **File:** `api/routes/chat.py` — có **4 endpoint**, không chỉ 2 như hay bị nhầm:

| Function | Route | Gọi pipeline |
|---|---|---|
| `chat()` (L97) | `POST /chat` | `mode=agent` → `pipeline.query_agent(require_agent=True)`; `mode=rag` → `pipeline.query()`; `mode=auto`/mặc định → `pipeline.query_v3()`. Nếu agent không sẵn sàng khi `mode=agent`, endpoint này trả lỗi HTTP 503 (không fallback). |
| `chat_v3()` (L217) | `POST /chat/v3` **và** `POST /api/chat/v3` (cùng một hàm, đăng ký 2 route) | `mode=rag` → `pipeline.query()`; `mode=agent` → `pipeline.query_agent(require_agent=False)` — nếu `pipeline.agent is None` thì fallback sang `pipeline.query(mode="rag_v2_fallback")` (khác `chat()` — ở đây có fallback, không raise lỗi); mặc định/`auto` → `pipeline.query_v3()`. |
| `suggest_questions()` (L349) | `GET /chat/suggest` | Không gọi pipeline — trả danh sách gợi ý tĩnh/heuristic. |
| `chat_stream()` (L398) | `POST /chat/stream` | Luôn gọi `pipeline.query_stream()`, chạy trong background thread qua `loop.run_in_executor`, kết quả đẩy vào `asyncio.Queue` và forward thành SSE frame. |

- **File:** `pipeline/rag_pipeline.py`, class `RAGPipeline` (định nghĩa L71):
  - `query()` — L427: luồng RAG v2 cổ điển, không stream. Nhận thêm `pre_ref_result`/`pre_reflection_ms` để `query_v3()` có thể truyền reflection đã tính sẵn, tránh chạy reflection 2 lần. Gọi `rag_flow()` (từ `pipeline/flows/coordinators.py`) ở khoảng L508-509.
  - `query_agent()` — L563.
  - `query_v3()` — L795, thứ tự thực thi thật:
    1. Chạy reflection trước (`self._run_reflection`) trừ khi `skip_reflection=True` — để routing thấy câu hỏi đã mở rộng/viết lại, không phải câu gốc.
    2. `route, subtype = self._decide_complexity(reflected_question, history)` (L831) — quyết định 3 tầng (xem chi tiết bên dưới), **không phải** một lời gọi `complexity_router` đơn lẻ.
    3. Nếu `route == "chitchat"` → trả lời có sẵn cục bộ qua `self._handle_chitchat()`, **không retrieval**, `mode="chitchat"`.
    4. Nếu `route == "simple"` **hoặc** `runtime.agent is None` (agent bị tắt) → gọi `self.query(...)`, gán `result["mode"]="rag_v2"`, `result["route"]=route`. Nghĩa là dù router phân loại "complex", nếu agent không khả dụng thì vẫn rơi về nhánh RAG thường.
    5. Ngược lại (route == "complex" và agent khả dụng) → gọi `self.query_agent(..., route_label="complex", require_agent=False, complexity_subtype=subtype, ...)`.
  - `query_stream()` — L1129: cùng cấu trúc reflection → `_decide_complexity()` → phân nhánh như `query_v3`, nhưng stream: chitchat stream trực tiếp từ LLM; simple/rag dùng `rag_flow_stream()`; complex dùng LangGraph agent (câu trả lời gửi thành 1 chunk, kèm các event `{"type":"status"}` báo tiến độ). Ghi metadata cuối vào dict `metadata_out` do caller truyền vào (không dùng `self.last_*`) — thiết kế này chủ đích để tránh race condition giữa các request đồng thời trên cùng một pipeline singleton.

  **Bộ định tuyến độ phức tạp — `_decide_complexity()` (L1044-1101):** đây là **cascade 3 tầng**, không phải một `complexity_router` duy nhất:
  - **Tier 0** — `self.complexity_router.route(reflected_question)`, với `self.complexity_router = ComplexityRouter()` (`query/complexity_router.py`, khởi tạo L186). Thuần regex/pattern, trả `{"tier": "chitchat"|"simple"|"complex"|"unknown", "complex_subtype", "query_signals"}` (`ComplexityRouter.route`, L216-465). Nếu tier ≠ `"unknown"` → quyết định luôn, dừng ở đây.
    - **Tier 0, bước "1b" — fast-path lịch thi (mới)** (`query/complexity_router.py:251-273`, chạy ngay sau chitchat, trước mọi check Tier 0 khác): khớp `_FOLDED_EXAM_RE` (L122-126, regex trên text đã fold dấu: `"lich thi"`, `"phong thi"` — có negative lookahead loại `"phong thi nghiem"` = phòng thí nghiệm —, `"kip thi"`, `"ngay thi"`, `"thi mon"`, `"mon thi"`, `"ma lop thi"`, `"dot thi"`, `"thi ngay"`, `"thi khi nao"`, `"thi vao"`, `"thi hom nao"`, `"thi luc nao"`) **VÀ** thoả specificity guard (L132-150): câu hỏi khớp `_EXAM_INHERENTLY_SPECIFIC_RE` (các cụm tự thân đã cụ thể như `"thi mon"`/`"mon thi"`/`"ma lop thi"`...) **HOẶC** khớp `_EXAM_SPECIFIC_SIGNALS_RE` (mã môn `AA1234`, `"mon <tên>"`, mã khóa `Kxx`, ngày `d/m`, `"nhom N"`, `"tuan nay/toi/sau/truoc"`, `"thang N"`, `"ngay N"`). Khi khớp → trả ngay `{"tier": "complex", "reason": "signals: exam_schedule_lookup", "complex_subtype": "general", ...}`, đưa câu hỏi sang Agent (`query_agent()`) mà **không** qua Tier 1/Tier 2. Câu hỏi CHUNG kiểu `"lịch thi cuối kì"` (không có tín hiệu cụ thể nào) **không** thoả guard này → tiếp tục rơi qua các bước Tier 0 khác rồi Tier 1/2 như bình thường; ở tầng Agent Planner, câu hỏi chung như vậy được LLM planner tự route vào `ke_hoach`, không vào `lich_thi` (xem Mục 7.7).
  - **Tier 1** — chỉ chạy nếu Tier 0 trả `"unknown"`. Gọi `self._router.route(reflected_question)` với `self._router = QueryRouter(mode=cfg.get("router_mode", "classifier"), embedder=self._bge)` (khởi tạo L145) — **chính là bộ phân loại intent/domain ở Mục 2**, được tái sử dụng ở đây chỉ để lấy tín hiệu domain đa nhãn. Nếu `routing["intent"] != "rag"` → `"simple"`. Ngược lại kiểm tra có ≥2 domain active (`_count_active_domains`) hoặc tín hiệu `multi_domain` xác định hay không; nếu không → `"simple"`.
  - **Tier 2** — chỉ chạy nếu ≥2 domain/`multi_domain` được kích hoạt ở Tier 1. Gọi `self._classify_complexity_llm()` (LLM judge qua `chat.generate(..., mode="chitchat")`), trả `"simple"` hoặc `"complex"` + subtype (`comparison`/`multi_source`/`general`), mặc định `"simple"` nếu parse/exception lỗi.

  Lưu ý: còn một "Tier-3" khác (`_llm_domain_classify`, L891) dùng để **phân giải domain** (không phải complexity) trong luồng router intent/domain — là cơ chế khác, không nên nhầm lẫn với 3 tier trên.

---

## 2. Intent Routing (Phân loại Query)

- **File:** `query/router.py`, class `QueryRouter` (L108), method:
  ```python
  def route(self, query: str, chat_history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]
  ```
  (L151-173)
  - **Intents** (`VALID_INTENTS`, L29): `{"chitchat", "rag", "tool_search"}`.
  - **Domains** (`VALID_DOMAINS`, L30): `{"ctdt", "quydinh", "kehoach", "stsv"}` — **không đổi**, vẫn chỉ 4 domain.
  - > **Lưu ý:** `lich_thi` (lịch thi/exam schedule) **không** phải domain thứ 5 ở đây và **không** nằm trong `VALID_DOMAINS`. Nó là một collection riêng chỉ tồn tại ở tầng **Agent Planner-Executor** (`ReActAgent._VALID_COLLECTIONS`, `agent/react_agent.py:95-97`), hoàn toàn bỏ qua `QueryRouter`, Tier-1 domain classifier, `MultiCollectionSearch` và Qdrant. Xem Mục 7.7.
  - **Cơ chế — được chọn ở constructor, KHÔNG phải "LLM hoặc ML" tùy ý; mặc định production là ML, không phải LLM:**
    - `mode="classifier"` (**mặc định** — pipeline khởi tạo `QueryRouter(mode=cfg.get("router_mode", "classifier"), ...)` tại `rag_pipeline.py:145`) → `_route_classifier()` (L179-245): dùng `DomainClassifier` dựa trên embedding (BGE-M3 + bộ phân loại đa nhãn đã huấn luyện, ~10-50ms, không tốn LLM call). Có cơ chế **two-pass**: Pass 1 route trên câu hỏi thô; Pass 2 (ghép thêm lịch sử hội thoại qua `build_routing_input`) chỉ chạy nếu confidence Pass 1 `< 0.65` (`_TWO_PASS_CONFIDENCE_THRESHOLD`) **và** câu hỏi ngắn (`< 8` từ) — giữ lại pass nào có confidence cao hơn.
    - `mode="llm"` → `_route_llm()` (L251-279): gọi LLM chat completion với `ROUTER_SYSTEM_PROMPT` + few-shot `ROUTER_FEW_SHOT` (cả hai định nghĩa tại `query/prompts.py`, dòng 7 và 40), parse JSON qua `_parse_response()`. Chỉ được dùng khi config `router_mode` set tường minh là `"llm"`.
  - **Domain labeling không phải là bước LLM thứ hai** (ở chế độ classifier mặc định) — domain trả về ngay trong cùng một lần gọi classifier (key `domains`/`domain`). Có tồn tại một bước LLM phân giải domain riêng (`RAGPipeline._llm_domain_classify`, `pipeline/rag_pipeline.py:891`) nhưng nó nằm ở **tầng pipeline**, chỉ chạy như fallback Tier-3 cho kết quả classifier confidence thấp (~5% số query theo docstring), **không nằm trong** `QueryRouter.route()`.

---

## 3. Query Reflection (Rewrite, Extract & Expand)

- **File:** `query/reflection.py`, class `QueryReflector.reflect()` (L1202-1480). Thứ tự thực thi thật (khác thứ tự trực giác) — 17 bước:

  1. **`_strip_pii_and_noise(query)`** (định nghĩa L165, gọi L1233) — xóa mã số sinh viên (MSSV), câu tự giới thiệu tên riêng ("Em là Nguyễn Văn A"), lời cảm ơn/kết thúc ("em xin cảm ơn ạ"), và các cụm xưng hô ("Kính gửi thầy cô", "Ban cố vấn..."). **Không** xóa lời chào mở đầu kiểu "Chào thầy" như tên gọi "lời chào" dễ gây hiểu lầm.
  2. Regex phát hiện mã môn học người dùng gõ tay (`_COURSE_CODE_RE`, L1234) → `user_typed_course_code`.
  3. `_merge_user_major_into_context` (194) + `_merge_profile_context` (619, gọi L1244) → gộp `user_context`/`user_major`/`user_profile` thành `merged_profile`.
  4. **Cổng gọi LLM** (`_needs_llm_rewrite`, L1264): LLM **chỉ** được gọi khi `chat_history` không rỗng **HOẶC** câu hỏi khớp `_has_profile_dependent_signal` (regex sở hữu cách hẹp, vd "của tôi", "ngành này"). Nếu không, **bỏ qua LLM hoàn toàn** (passthrough) — phần lớn câu hỏi độc lập, không có lịch sử không bao giờ chạm LLM ở bước này.
  5. Nếu cần LLM: `_build_user_prompt` (1508) dựng `user_prompt` từ `REWRITE_WITH_HISTORY_TEMPLATE`/`REWRITE_NO_HISTORY_TEMPLATE`, chèn `user_profile` (câu ngắn kiểu "sinh viên ngành X (CODE), Khóa K65") + `chat_history` + câu hỏi đã strip. Gọi `self._client.chat.completions.create(model=self.model, messages=[{"role":"system","content":REWRITE_SYSTEM_PROMPT}, {"role":"user","content":user_prompt}], ...)` có retry/backoff khi gặp `RateLimitError`/503. Client là `OpenAI`-SDK trỏ tới endpoint theo `settings.reflection_provider` (mặc định **`gemini`**, `base_url=https://generativelanguage.googleapis.com/v1beta/openai/`, model mặc định `gemini-3.1-flash-lite`; cũng hỗ trợ `lm_studio`/`ollama`/`openai`).
  6. **Guardrail "anti-bleeding freshness"** (1340-1354): nếu câu hỏi mang tính "mới nhất/gần đây" và không có tín hiệu profile-dependent, không có phạm vi học thuật trong câu gốc, nhưng LLM lại tự thêm phạm vi (ngành/khóa/kỳ/năm) → **revert về câu trước-LLM**.
  7. `_strip_institution_name_leak` (471, gọi L1356) — Rule 18: xóa tên trường (Bách Khoa Hà Nội/HUST) mà LLM tự chèn thêm nếu câu gốc của người dùng không hề nhắc tới.
  8. `_rewrite_comparison_followup` (418, gọi L1366) — rewrite tất định (không LLM) cho câu hỏi so sánh tiếp nối ngắn (vd "so về học phí"), ghi đè `rewritten` nếu resolve được 2 mã ngành.
  9. **`_extract_entities(query, user_context=merged_profile, history=chat_history)`** (763, gọi L1384) — thuần regex/dict (không LLM), chạy trên **câu gốc đã strip**, không phải câu đã rewrite.
  10. Guardrail 1 (1392): nếu `_PERSONAL_REFS` vẫn còn trong `rewritten` → `_enforce_major_reference_rewrite` (209) ép thay thế "ngành của tôi"/"chương trình này"... bằng ngành đã xác thực trong profile.
  11. Guardrail 2 (1401): `_preserve_curriculum_placement_verb` (970) — hoàn tác việc LLM đổi "học" → "đăng ký" khi hỏi về vị trí môn trong chương trình.
  12. Guardrail 3 (1413): `_expand_major_codes_in_query` (450) — tất định mở rộng mã ngành trần thành cặp mã+tên (vd "IT1" → "IT1 (Khoa học máy tính)"), bỏ qua nếu bước 8 (comparison-followup) đã áp dụng.
  13. Guardrail 3b (1419): `_revert_major_code_conflation` (524) — Rule 19: nếu kết quả rewrite có ≥2 mã ngành nhưng không có từ khóa so sánh tường minh và câu gốc chỉ nhắc 1 ngành → xóa mã ngành cũ (từ lượt hội thoại trước) bị "dính" lại.
  14. **Terminology expansion** (1428-1430): `expand_academic_abbreviations(rewritten)` từ `utils/terminology.py` — chạy **trước** bước khớp mã môn.
  15. Khớp/giữ mã môn học (1432-1438): nếu người dùng gõ mã môn tường minh → `_preserve_explicit_course_code` (1105) khôi phục nếu LLM làm sai lệch; ngược lại gọi `_apply_catalog_course_match(entities, rewritten)` (741) để điền `entities["course_code"]`/`course_name`/`course_name_folded`/`course_alias_folded` từ `query/course_catalog.py`.
  16. Guardrail 4 — chèn mã môn (1445): `_inject_course_code` (1040) chèn mã vừa xác định ngay sau tên môn/alias khớp được trong câu (vd "Mạng máy tính được học..." → "Mạng máy tính (IT3080) được học..."); có xử lý trường hợp mã đã tồn tại sẵn cạnh tên môn (không nhân đôi) và ưu tiên thay thế alias bằng tên đầy đủ khi chèn.
  17. Trả về dict: `original, stripped, rewritten, prompt, entities, reflection_candidate, reflection_guardrail_reverted, reflection_rejected_scope, reflection_institution_leak_reverted, reflection_major_conflation_reverted, terminology_expanded`.

  > Lưu ý quan trọng: `_extract_entities`/`_apply_catalog_course_match` được gọi **2 lần** trong luồng thật — lần 1 ở bước 9 (trên câu trước-guardrail, chủ yếu lấy `major_code` phục vụ các guardrail sau) và lần 2 ở bước 15 (trên câu `rewritten` gần cuối, để thực sự phục vụ chèn mã môn).

  `entities` thực tế gồm: `major_code`, `major_name`, `user_major_code`/`user_major_name` (chỉ từ profile, bất biến), `target_major_code`/`target_major_name` (ngành được nhắc tường minh trong câu hỏi hiện tại), `cohort`, `year_of_study`, `course_code`, `course_name`, `course_name_folded`, `course_alias_folded`, `semester`, `academic_year` — tách biệt ngành-của-user và ngành-được-hỏi là thiết kế chủ đích (tránh một câu "em học Cơ điện tử" giữa hội thoại ghi đè ngành đã xác thực trong profile).

- **File:** `query/course_catalog.py` — `lookup_course_code(query_text, major_code)` (L238): **không phải dict lookup thuần, không phải fuzzy/edit-distance** — là khớp chuỗi con theo ranh giới từ, đã fold dấu, **có phạm vi theo ngành**:
  - Bắt buộc có `major_code` (trả `None` nếu thiếu) — vì cùng tên môn có thể ánh xạ mã khác nhau theo từng ngành (vd "Mạng máy tính" → `IT3080` cho IT1/IT2/IT-E6 nhưng `IT3080E` cho IT-E7).
  - Nạp catalog JSON dựng sẵn (`query/models/course_catalog.json`, build bởi `scripts/build_course_catalog.py`), key theo mã ngành, sắp xếp tên dài nhất trước.
  - Fold văn bản câu hỏi (`fold_vietnamese_text`), thử khớp tên chính xác đã fold với regex ranh giới từ (`_phrase_matches`) trước; trả kết quả ngay khi khớp tên chính xác.
  - Nếu không khớp tên, fallback sang **alias viết tắt** sinh tự động (`_course_aliases`): biến thể số La Mã/Ả Rập, bỏ tiền tố "lập trình "/"tiếng ", alias hậu tố TOEIC, và bảng cứng `_COMMON_COURSE_ALIASES` (vd "cơ sở dữ liệu" → "csdl", "mạng máy tính" → "mmt"). Alias được lọc qua `_is_safe_generated_alias` (alias 1 từ phải nằm trong allow-list `_SAFE_SINGLE_TOKEN_ALIASES`; alias nhiều từ phải ≥6 ký tự) để tránh khớp quá rộng.
  - Nếu nhiều alias khớp, `_unique_code_match` chỉ chấp nhận nếu tất cả alias khớp dài nhất đều trỏ về **cùng một mã môn** — khớp mơ hồ trả về `None`.

- **File:** `utils/terminology.py` — `expand_academic_abbreviations()`:
  - Từ điển `HUST_TERMINOLOGY_ALIASES` (L19): 6 cặp `TerminologyAlias(full, abbr)`: `nghiên cứu sinh↔NCS`, `điểm rèn luyện↔ĐRL`, `nghiên cứu khoa học↔NCKH`, `thời khóa biểu↔TKB`, `học viên cao học↔HVCH`, `chương trình đào tạo↔CTĐT`.
  - Hành vi **2 chiều và cộng thêm**, không phải chỉ append 1 chiều: nếu văn bản có **cụm đầy đủ** mà chưa có viết tắt → append viết tắt trong ngoặc sau cụm đầy đủ (`"chương trình đào tạo"` → `"chương trình đào tạo (CTĐT)"`); ngược lại nếu chỉ có **viết tắt** → append cụm đầy đủ trong ngoặc sau viết tắt (`"CTĐT"` → `"CTĐT (chương trình đào tạo)"`). Nếu cả hai đã có sẵn thì không làm gì (idempotent).
  - So khớp (`_contains_term`) đã fold dấu + ranh giới từ; thay thế (`_replace_term_once`) giữ nguyên chữ hoa/thường gốc của cụm khớp được (dùng `{match}`), không phải chuỗi hardcode.

---

## 4. Xử lý Metadata Filters & Phân rã (Decomposition)

- **File:** `pipeline/flows/coordinators.py` — `rag_flow()` (L170, đồng bộ) và `rag_flow_stream()` (L1330, hàm riêng, có `_search_once` riêng tại L1639, logic gần như trùng lặp).
- Sau reflection + routing collection (L283-515):
  - `_should_strip_major_for_retrieval()` — định nghĩa tại **`pipeline/flows/retrieval_helpers.py:51`** (không phải trong `coordinators.py` hay `metadata_filters.py`), gọi tại `coordinators.py:444` — chỉ strip khi có `resolved_major` **VÀ** (không có `target_collections` **HOẶC** `target_collections` không chứa `"quydinh"` — vì `quydinh` không có metadata filter theo `major_code` nên cần giữ tên ngành trong text để khớp từ khóa/ngữ nghĩa).
  - Nếu đúng điều kiện: `strip_major_from_query_for_retrieval()` (`retrieval/metadata_filters.py:986`) loại cụm nhắc ngành (mã/tên) dựa trên `_resolve_major_code` + `_build_major_labels`, chỉ chấp nhận kết quả nếu còn ≥2 từ không thuộc `_GENERIC_WORDS`.
  - Sau đó (L484-514), pipeline **luôn thử 2 loại decomposition riêng biệt**:
    1. `build_major_comparison_subqueries_for_retrieval(search_query)` (`metadata_filters.py:903`): phát hiện câu **so sánh ngành** bằng regex `_COMPARE_HINT_RE` (khớp "so sánh", "khác nhau", "khác gì", "đối chiếu", "phân biệt"...) kết hợp `extract_major_codes()` (regex `_MAJOR_CODE_MENTION_RE`/`_MAJOR_CODE_FUZZY_RE` nhận diện mã ngành như IT-E6, MI2, EE-E5). Chỉ trigger nếu tìm được **≥2 mã ngành khác nhau** và có compare-hint. **Thuần regex, không dùng LLM.** Kết quả: list `(subquery, major_code)`, mỗi subquery = `"{topic đã bóc scaffold} của ngành {major_code}"`.
    2. **Chỉ khi KHÔNG** có major-comparison, mới thử `build_cohort_comparison_subqueries_for_retrieval(retrieval_query)` (`metadata_filters.py:854`) — logic tương tự nhưng theo **khóa học** (`extract_cohort_codes`, regex `Kxx`/`khóa xx`), sinh subquery dạng `"{topic} cho {cohort}"`. (Nhánh này hoàn toàn vắng mặt trong bản tài liệu trước.)

## 5. Vector & BM25 Embedding (Quá trình mã hóa)

- **File:** `pipeline/flows/coordinators.py` — `_search_once()` (L521, và bản thứ hai gần như trùng tại L1639 dùng cho `rag_flow_stream`).
- Với mỗi query cần tìm kiếm (câu gốc, hoặc từng subquery nếu có decomposition), hàm gọi **TUẦN TỰ**: `bge_embedder.embed_query(local_query)` (L530) rồi **sau đó** `e5_embedder.embed_query(local_query)` (L537) — hai lệnh gọi đồng bộ (sync), nối tiếp nhau trên cùng một thread. **Không chạy song song** (không dùng `ThreadPoolExecutor`, `asyncio.gather`, hay bất kỳ cơ chế concurrency nào ở bước này) — điểm này khác với mô tả "gọi đồng thời" trước đây. Mỗi lệnh gọi được đo riêng (`timings_ms["embed_bge"]`, `timings_ms["embed_e5"]`), cộng dồn qua các vòng lặp subquery.
- `bge_embedder` là instance `BGEm3Embedder` (`embedding/bge_m3.py`) và `e5_embedder` là instance `E5MultilingualEmbedder` (`embedding/e5_multilingual.py`), cả hai kế thừa `BaseEmbedder` (`embedding/base.py`), khởi tạo một lần trong `pipeline/rag_pipeline.py` và truyền vào `rag_flow`/`rag_flow_stream` làm tham số.
- Sau khi có `bge_vec` và `e5_vec`, `_search_once` gọi `searcher.search(...)` (instance `MultiCollectionSearch`, `retrieval/multi_collection_search.py:224`), truyền `bge_m3_query=bge_vec, e5_query=e5_vec` cùng `top_k`, `vector_top_k`, `keyword_top_k`, `vector_pool_k`, `keyword_pool_k`, `active_collections`, `resolved_major`, `resolved_cohort`, `disable_metadata_filter_collections`, `fusion_mode`. Embedding và search là **hai bước tách biệt**: `MultiCollectionSearch.search()` không tự embed — nó nhận vector đã tính sẵn (cho vector search) và văn bản thô (cho BM25/Elasticsearch).

---

## 6. Hybrid Retrieval (Quá trình Truy xuất)

- **File:** `retrieval/multi_collection_search.py` — `MultiCollectionSearch.search()` (L224-568).
  - **Filter (bước 0 — trước khi search):** `build_collection_filters()` (`metadata_filters.py:1390`) không chỉ là "major_code hoặc applicable_cohort" — đây là **registry riêng cho từng collection** (`_COLLECTION_FILTER_REGISTRY`, L1380):
    - `ctdt`: chuỗi fallback ES — (1) `major_code` exact → (2) `major_name` exact → (3) `major_code` exact HOẶC thiếu field (chunk dùng chung) → nếu cả 3 đều 0 kết quả thì bỏ filter.
    - `quydinh`: `applicable_cohort` exact (danh sách, vd `["K63","K64"]`) HOẶC thiếu field → bỏ filter nếu 0 kết quả.
    - `kehoach`: nếu câu hỏi có tháng/năm cụ thể → ES wildcard trên `date_str` (định dạng `D/M/YYYY`); nếu không có ngày cụ thể nhưng có ý định "mới nhất/gần đây" → `sort_by_date_desc=True` (lấy 200 ID mới nhất qua `get_latest_chunk_ids_by_date`); nếu không có tín hiệu nào → không filter (nhưng vẫn có recency bonus ở bước fusion).
    - `stsv`: **không có filter metadata nào** (chủ đích, ghi rõ trong registry).
    - Cơ chế: mỗi filter ES trong chuỗi fallback được thử tuần tự (`_resolve_filter_with_fallback`, L677-811); ID khớp được đưa vào Qdrant qua `HasIdCondition` để giới hạn vector search, cùng filter đó tái sử dụng làm ES term filter cho keyword search. Có fallback riêng khi ES index rỗng (thay bằng Qdrant payload filter, L781-804).
  - **Thực thi song song (bước 1-2):** `ThreadPoolExecutor(max_workers=4 mặc định)` chạy `_fetch_one(name, hybrid)` cho **từng collection song song** (L443-487, dùng `as_completed`). **Đính chính quan trọng:** song song thực sự là **giữa các collection**, không phải giữa Vector và Keyword trong cùng một collection — bên trong mỗi `_fetch_one`, `hybrid.qdrant.search()` (vector) chạy trước rồi mới đến `hybrid.es.keyword_search()` (BM25), **tuần tự** trên cùng một thread (L419-439). Sau khi fetch xong, kết quả gộp toàn cục, sắp theo raw score, khử trùng theo ID, giữ top `vector_pool_k`/`keyword_pool_k`.
  - **Fusion (bước 5):** 2 chế độ qua tham số `fusion_mode`:
    - `"linear"` (mặc định của *chữ ký hàm* `search()`, L240): `_score_fusion()` — chuẩn hoá **max-normalization** (không phải min-max) từng pool về [0,1] rồi cộng có trọng số: `score = vector_weight*norm_vector + keyword_weight*norm_keyword + kehoach_recency_bonus`.
    - `"rrf"`: `_score_fusion_rrf()` dùng đúng `rrf_score(rank, k)` từ `hybrid_search.py`: **`rrf_score(rank, k) = 1.0 / (k + rank)`** (rank đánh số từ 1). Công thức: `score = vector_weight*rrf_score(vector_rank, rrf_k) + keyword_weight*rrf_score(keyword_rank, rrf_k)`, cộng thêm recency bonus đã rescale, rồi nhân `(rrf_k+1)` để đưa về thang [0,1].
    - **Giá trị k thực tế ở production = 10** (`self.rrf_k` lấy từ `settings.fusion_rrf_k=10`, `config/settings.py:155`, qua `create_retriever()` — `retrieval/__init__.py:29-40`, dòng 37: `rrf_k=settings.fusion_rrf_k`). **Không phải k=60** — 60 chỉ là default tham số của `HybridSearch.__init__`/`rrf_score()`, nhưng class `HybridSearch.search()` (single-collection) tự ghi chú trong docstring là **"không dùng trong luồng chính"**, chỉ phục vụ unit test/debug.
    - **Chế độ production:** `Settings.fusion_mode = "rrf"` (`settings.py:154`) là mặc định hệ thống; `rag_flow()` gọi `searcher.search(..., fusion_mode=cfg.get("fusion_mode", "rrf"))` (`coordinators.py:564`) — nên dù chữ ký `search()` mặc định `"linear"`, đường đi production luôn dùng `"rrf"` với `k=10`.
  - **Mở rộng ngữ cảnh (sibling expansion):** `_expand_with_siblings_pre_rerank()` (`pipeline/flows/retrieval_helpers.py:202-284`), gọi tại `coordinators.py:701-714`, **chỉ chạy khi `cfg["sibling_expansion_enabled"]` bật** (mặc định **tắt** — `Settings.sibling_expansion_enabled=False`, `settings.py:277`). Logic: lấy top `expand_top_n=3` candidate theo fusion score, tra `metadata.source` + `metadata.chunk_index`, tìm chunk liền kề trong khoảng `±window=1` qua `searcher.get_by_metadata()` (payload filter theo `source`+`chunk_index` chính xác), giới hạn tổng `max_expansion=6` sibling mới. Sibling được gán điểm = 50% điểm chunk gốc (`doc["score"] * 0.5`), đánh dấu `_expansion_source`. Chạy **trước** rerank.

---

## 7. Reranking (Đánh giá & Xếp hạng lại)

- **Chuẩn bị query:** `expand_major_in_query_for_reranking()` (gọi tại `coordinators.py:719-721`, định nghĩa `metadata_filters.py:1052-1102`). Logic thật: resolve `major_code` từ query/`resolved_major`, tra `MAJOR_CODE_TO_NAME`, và **THAY THẾ** (không phải chèn thêm) mã ngành/alias bằng tên đầy đủ trong query (vd `"IT1"` → `"CNTT: Khoa học Máy tính"`) để cross-encoder (huấn luyện trên văn bản tự nhiên) không bị nhiễu bởi mã nội bộ. Chỉ xử lý `major`, không xử lý `cohort`.
- **File:** `reranking/bge_reranker.py` — class `BGEReranker` (L35), `rerank()` (L93-117, wrapper thread-safe) gọi `_rerank_impl()` (L119-254):
  - Model: `BAAI/bge-reranker-v2-m3` qua `FlagEmbedding.FlagReranker` (L10, 29, 87), tự chọn device CUDA → MPS (Apple Silicon) → CPU.
  - `rerank()` bọc `_rerank_impl()` trong `threading.Lock()` vì tokenizer của `FlagReranker` không thread-safe.
  - Tính điểm: enrich text mỗi doc qua `_enrich_text_for_reranking()` (prepend `hierarchy_path`, `"Ngành: {major_code}"`, `"Tài liệu: {title}"`), tạo cặp `(query, enriched_text)`, gọi `self._model.compute_score(pairs, batch_size=32)` — **logit thô**, không phải xác suất.
  - **Ngưỡng lọc** (áp dụng TRƯỚC khi cắt top_k, L175-187): so `score_threshold` (mặc định `Settings.reranker_score_threshold=0.0`) hoặc `table_score_threshold` nếu `metadata.has_table=True` (mặc định production `Settings.reranker_table_score_threshold=-1.0`, khác default nội bộ class là `-3.0` do bị override qua `_reranker_kwargs`).
  - **`min_top_k` fallback** (L196-208): nếu số doc qua ngưỡng ít hơn `min(top_k, min_top_k)`, bổ sung thêm doc dưới ngưỡng theo điểm giảm dần cho đủ số lượng. `min_top_k` mặc định `Settings.reranker_min_top_k=3`.
- **Fallback/retry trong `rag_flow()`** (`coordinators.py:716-807`) — **2 tầng**, không phải 1:
  1. Rerank lần 1 với `rerank_query` (đã qua reflection + `expand_major_in_query_for_reranking`).
  2. `_best_rerank_score = _best_explicit_rerank_score(reranked)` (max của `rerank_score`, `rerank_scoring.py:161-170`).
  3. `_rerank_quality_ok = bool(reranked) and (best_score is None or best_score >= 0.0)`.
  4. Nếu `raw_results` không rỗng nhưng `_rerank_quality_ok` là False (rerank trả rỗng, HOẶC điểm cao nhất `< 0.0`) → **retry rerank với `query=question`** (câu hỏi gốc của user, không phải câu đã reflect/rewrite). `timings_ms["rerank_fallback"] = 1`.
  5. Nếu retry đó **vẫn** rỗng hoặc điểm cao nhất vẫn `< 0.0` → **fallback cuối**: bỏ hẳn reranker, lấy top `top_k_value` từ `raw_results` sắp theo **fusion score** giảm dần, không áp threshold nào. `timings_ms["rerank_raw_fallback"] = 1`.
  - Ngưỡng chính xác là **`rerank_score >= 0.0`** — chỉ nhằm loại trường hợp "toàn bộ candidate bị đánh giá không liên quan" (điểm âm), không phải ngưỡng chất lượng cao.

---

## 7.5. HyDE (Fallback Retrieval — Hypothetical Document Embeddings)

HyDE không chạy mặc định, chỉ kích hoạt khi kết quả rerank quá kém.

- **File:** `pipeline/flows/hyde.py` — `_should_trigger_hyde()` (L28-73), `_hyde_fallback_post_rerank()` (L76-175). `retrieval/hyde.py` chứa `HyDEExpander` và một helper `should_use_hyde()` **dự trữ, không được dùng** trong luồng chính.
- **Điều kiện kích hoạt:** `hyde_enabled=True` (mặc định `True`, `settings.py:283`) **VÀ** một trong: (1) `reranked` rỗng, (2) điểm rerank cao nhất `< 0.0`, (3) `reranker.last_stats["rerank_strict_returned_count"]` (hoặc `len(reranked)` nếu thiếu stats) `< hyde_min_results` (mặc định **3**, `settings.py:284`). Lưu ý: `hyde_confidence_threshold=0.3` (`settings.py:285`) tồn tại trong config nhưng là **cờ dự trữ chưa dùng**, không được nối vào điều kiện trigger thật (do điểm cross-encoder là logit thô chưa chuẩn hoá, một ngưỡng 0.3 cố định sẽ trigger gần như mọi query).
- **Quá trình chạy HyDE (đã xác nhận đúng, kể cả điểm bất đối xứng embedding):**
  1. `HyDEExpander.generate_hypothesis()` gọi `chat_model.generate()` với prompt học thuật tiếng Việt HUST (150-200 từ), cắt còn tối đa 800 ký tự; lỗi/rỗng thì fallback về câu hỏi gốc.
  2. **`hyde_vec = hyde.generate_embedding(retrieval_query)`** — câu trả lời giả định (hypothesis) được nhúng bằng **BGE**. **`e5_vec = e5_embedder.embed_query(retrieval_query)`** — câu hỏi **gốc** (không phải hypothesis) được nhúng bằng **E5**. Đây là thiết kế bất đối xứng thật sự, đã xác minh từng dòng code.
  3. Thực hiện `searcher.search(...)` lần 2 (second-pass) với `bge_m3_query=hyde_vec, e5_query=e5_vec`.
  4. `_dedup_retrieval_candidates(reranked + hyde_results, ...)` gộp + khử trùng vào pool cũ.
  5. Toàn bộ pool đã trộn được **rerank lại từ đầu** qua `reranker.rerank(...)` (hoặc sắp theo raw score nếu không có reranker).
  - Mọi exception trong bước này đều bị bắt và trả về `reranked` gốc không đổi (fail-safe).

---

## 7.6. Web Search (Tavily Fallback & Agent Mode)

### RAG Mode thông thường (`rag_flow`)

- **File:** `pipeline/flows/coordinators.py`, `pipeline/flows/tavily.py`, `pipeline/flows/web_fallback.py`.
- Toàn bộ được gate bởi `cfg.get("tavily_fallback_enabled", False)` — **mặc định TẮT** (`settings.py:199`), không tự động bật.
- **Hai điểm quyết định riêng biệt**, không phải một:
  1. **Trước khi generate** (`_build_pre_generation_web_decision`, `web_fallback.py:328`): trigger Tavily *trước khi* LLM sinh câu trả lời, khi: không có source nội bộ nào, HOẶC câu hỏi mang tính thời sự chưa giải quyết (tài liệu `kehoach` thiếu/cũ, kiểm tra `date_str` trong 90 ngày khi `freshness_tavily_check_enabled`), HOẶC câu hỏi "động" (route vào collection `kehoach` hoặc khớp regex dynamic-query) mà không có confidence nội bộ cao, HOẶC confidence retrieval thấp (đã xảy ra rerank fallback). Điểm rerank nội bộ cao (`web_bypass_min_local_score`, mặc định 0.5) sẽ chặn (suppress) các trigger dynamic/freshness.
  2. **Sau khi generate** (`_build_answer_quality_gate`, `web_fallback.py:434`): trigger khi câu trả lời chứa tín hiệu "không tìm thấy thông tin", HOẶC không có source nào, HOẶC `SelfEvaluator.evaluate()` (`llm/self_eval.py`) trả `should_web_search=True` với `answer_status` thuộc `{insufficient, stale_risk}` (self-eval bản thân chỉ chạy khi `top_score < self_eval_min_top_score`, mặc định logit thô 100.0 — nghĩa là self-eval chỉ chạy khi confidence retrieval có vẻ yếu). Có thể bị chặn bởi `_has_local_exact_policy_evidence` khi đã có bằng chứng bảng/quy định nội bộ mạnh.
  3. **Retry bằng bằng chứng nội bộ** (`can_retry_with_local_evidence`, L1120) — nằm giữa 2 bước trên: nếu gate muốn gọi Tavily nhưng đã có bằng chứng nội bộ mạnh (và không phải trường hợp no-sources/dynamic/freshness), LLM được **hỏi lại một lần bằng context nội bộ** trước khi thực sự gọi Tavily.
- "AnswerQualityGate" **không phải là một class** — đó là hàm `_build_answer_quality_gate` kết hợp kết quả `SelfEvaluator` với các tín hiệu heuristic khác.
- **Domain restriction không chỉ "HUST"**: `include_domains` (`tavily.py:140-144`) = `HUST_OFFICIAL_DOMAINS + HUST_EXTENDED_DOMAINS + EDU_AUTHORITATIVE_DOMAINS`, trong đó `EDU_AUTHORITATIVE_DOMAINS = ["moet.gov.vn"]` (Bộ GD&ĐT Việt Nam).

### Agent Mode (`pipeline.query_agent()`)

- **File:** `agent/react_agent.py`, `agent/tool_adapters.py`.
- **Collection vocabulary của Agent khác với `VALID_DOMAINS` ở Mục 2** — Planner-Executor dùng 5 tên riêng (`ReActAgent._VALID_COLLECTIONS`, `react_agent.py:95-97`): `quy_dinh`, `chuong_trinh`, `ke_hoach`, `ho_tro_sv` (4 tên này map 1-1 sang tên Qdrant collection thật qua `COLLECTION_MAP`, `agent/tool_adapters.py:41-46`: `quy_dinh→quydinh`, `chuong_trinh→ctdt`, `ke_hoach→kehoach`, `ho_tro_sv→stsv`) và **`lich_thi`** (`EXAM_COLLECTION`, `tool_adapters.py:52`) — tên thứ 5 này chủ đích **không** có trong `COLLECTION_MAP` vì nó không map sang Qdrant collection nào cả. `_valid_plan_steps()` (`react_agent.py:575-589`) loại ngay các step mà LLM planner sinh ra với `collection` không thuộc 5 tên này. Chi tiết đầy đủ về `lich_thi` ở Mục 7.7.
- `needs_web` **không** phải do một bộ dò "tính thời sự" riêng đặt — đây là field boolean do chính **LLM planner** xuất ra trong lần gọi sinh kế hoạch JSON duy nhất (`_planner_node`, prompt tại `agent/prompts.py:61`: hướng dẫn set `needs_web=true` cho thông tin thời gian thực như lịch/deadline/thông báo, `false` cho quy chế/chương trình ổn định).
- **`needs_web=true` một mình chưa đủ để trigger web search.** Trong `_executor_node` (`react_agent.py:414`): `if plan.get("needs_web") and not tool_messages:` — web search chỉ chạy như **fallback khi toàn bộ các bước retrieval RAG nội bộ trả về rỗng** (`tool_messages` rỗng). Đây là fallback-cuối-cùng theo thiết kế (có comment tường minh, và test `test_web_not_called_when_rag_has_results`, `test_web_called_as_fallback_when_rag_empty` trong `tests/test_agent_langgraph.py` xác nhận).
- `web_search_for_executor()` (`tool_adapters.py:597`) bọc `_web_search()` (L559), vẫn bị gate bởi `settings.tavily_fallback_enabled` (cùng công tắc với RAG mode) — nếu tắt, trả chuỗi `"[Web fallback dang tat ...]"` được coi như rỗng, không lọt vào bước synthesis.
- Kết quả web (nếu có) trở thành một `ToolMessage` đưa vào `_synthesize_node`, kết hợp với kết quả tool nội bộ không rỗng (nếu có) để sinh câu trả lời cuối.

---

## 7.7. Lịch Thi (Exam Schedule) — Structured Lookup, Bỏ Qua Toàn Bộ Retrieval Qdrant

> Đây là một **hệ thống con song song** (parallel subsystem) với toàn bộ Mục 4-8 phía trên — `lich_thi` không phải Qdrant collection, không qua `MultiCollectionSearch`, không BGE/E5 embedding, không reranker, không HyDE, không sibling expansion, không `metadata_filters.py`. Nó là một tra cứu có cấu trúc (structured lookup) thẳng vào Elasticsearch (Mongo làm nguồn ghi), chỉ tồn tại trong nhánh **Agent Planner-Executor** (Mục 7.6) — nhánh RAG v2 cổ điển (`rag_flow()`) không có khái niệm này.

### 7.7.1. Kích hoạt — khi nào một câu hỏi đi vào `lich_thi`

- **Bước 1 (routing, Mục 1):** fast-path "1b" của `ComplexityRouter.route()` (`query/complexity_router.py:251-273`) chỉ quyết định **"đi Agent hay RAG"** (trả `tier="complex"`) — nó **không** tự chọn collection `lich_thi`.
- **Bước 2 (chọn collection, tại Agent):** `_planner_node` (`agent/react_agent.py:294`) gọi LLM planner với `PLANNER_SYSTEM_PROMPT` (`agent/prompts.py:29-93`) — LLM này mới thực sự quyết định step nào dùng `"collection": "lich_thi"`. Prompt phân biệt rõ (L32-43):
  - **`lich_thi`** — CHỈ dùng khi câu hỏi nêu RÕ môn/mã môn/ngày cụ thể/nhóm thi (vd "lịch thi CH1012", "phòng thi IT3080E", "thi môn Giải tích ngày nào").
  - **`ke_hoach`** — câu hỏi CHUNG về lịch thi ("lịch thi cuối kì", "khi nào thi cuối kỳ", "lịch thi kỳ hè") không nêu môn cụ thể → vẫn dùng `ke_hoach` (tài liệu kế hoạch thi chung của học kỳ, retrieval qua nhánh Qdrant ở Mục 4-8), **không** phải `lich_thi`. Đây chính là điểm rơi cho câu hỏi chung bị fast-path 1b bỏ qua ở Mục 1.
  - Với step dùng `lich_thi`, prompt yêu cầu **GIỮ NGUYÊN** trong `query` các từ "giữa kì/giữa kỳ", "cuối kì/cuối kỳ", mã khóa (Kxx), mốc thời gian ("tuần này/tuần tới", "tháng N") — vì bộ lọc lịch thi (7.7.3) trích các thông tin này trực tiếp từ chuỗi `query`, không qua entity extraction chung của Mục 3.
  - `agent/react_agent.py:95-97` — `_VALID_COLLECTIONS = frozenset({"quy_dinh", "chuong_trinh", "ke_hoach", "ho_tro_sv", "lich_thi"})`; nếu LLM planner hallucinate tên collection khác, step đó bị `_valid_plan_steps()` (L575-589) loại thầm lặng, không raise lỗi.

### 7.7.2. Executor — dispatch bỏ qua vector search

- `execute_retrieval_plan()` (`agent/tool_adapters.py:818-873`), trong `_run(i, step)` (L834) rẽ nhánh ngay tại dispatch (L835): `if step.get("collection") == EXAM_COLLECTION:` → gọi `_exam_schedule_search(...)` (structured DB lookup); **else** → `_rag_search(...)` (nhánh Qdrant bình thường cho 4 collection còn lại). Đây là điểm rẽ nhánh duy nhất — mọi collection khác trong Agent Mode đi qua `_rag_search` như Mục 4-8, chỉ riêng `lich_thi` đi tắt.
- Gọi với `top_k=None` (L846) — cố ý **không** giới hạn theo `top_k` cấp chat (kích thước dành cho vector retrieval); mặc định `exam_schedule_search_top_k=500` (`config/settings.py:337`) đủ trả hầu hết tập kết quả khớp.
- Cohort **bị bỏ qua có chủ đích** ở tầng planner: dù step có `cohort_hint` (thường lấy từ profile sinh viên), `_run()` **không** truyền `cohort_hint` vào `_exam_schedule_search` (L841-847 chỉ truyền `query`, `subject_code`, `exam_date`, `exam_type`) — cohort chỉ được `_exam_schedule_search` tự trích lại từ **chuỗi `query` gốc** (7.7.3), để tránh profile sinh viên âm thầm thu hẹp kết quả tra cứu lịch thi của người khác.

### 7.7.3. Trích lọc filter — `_extract_exam_filters()` (`tool_adapters.py:653-691`)

Thuần regex trên `query` đã strip PII + fold dấu, **không LLM**:
- `subject_code` — `_SUBJECT_CODE_RE` (`AA\d{3,4}`, vd `CH1012`).
- `exam_type` — `_CUOI_KY_RE`/`_GIUA_KY_RE` (L61-62), check "cuối" **trước** "giữa" (nếu câu hỏi nêu cả hai, nghiêng về cuối kỳ).
- `exam_date` (một ngày, `_DATE_TOKEN_RE`) **hoặc** `exam_date_from`/`exam_date_to` qua `_extract_date_range()` (`tool_adapters.py:624-650`) — xử lý "tuần này"/"tuần tới"/"tuần sau" (neo theo `date.today()` thật) và "tháng N[/YYYY]".
- `cohort` — khớp trên chuỗi query gốc chưa fold, dùng lại ở `_exam_schedule_search` (L772-775), **không** lấy từ planner/profile (xem 7.7.2).
  - > **Lưu ý (shadowing, đã xác nhận từng dòng code):** `tool_adapters.py` có **2 định nghĩa** `_COHORT_RE` ở module scope — L60: `r"\bK\d{2,3}[A-Za-z]?\b"` (có chữ hậu tố tùy chọn, dành riêng cho lịch thi theo comment tại L58-59) và **L143 (định nghĩa sau, đè lên)**: `r"\bK\d{2,3}\b"` (không cho phép chữ hậu tố). Vì Python resolve tên global tại thời điểm **gọi**, không phải tại định nghĩa, mọi nơi dùng `_COHORT_RE` — kể cả trong lịch thi (`_extract_exam_filters` L686, `_exam_schedule_search` L773) và trong `_extract_cohort()` dùng cho 4 collection RAG khác (L1029-1031) — đều chạy bản L143. Bản L60 là **dead code**, không bao giờ được gọi. Hệ quả thực tế: câu hỏi chứa mã khóa có hậu tố chữ liền sau số (vd `"K70C"`, `"K67S"` — đúng dạng ví dụ trong `SYNTHESIS_PROMPT`, xem 7.7.6) sẽ **không** được regex này nhận diện làm cohort token (vì `\b` không khớp giữa chữ số và chữ cái liền sau); `has_cohort_token` (7.7.4) sẽ là `False` cho các câu hỏi đó, khiến pipeline rơi vào fallback BM25-theo-tên-môn thay vì được coi là "đã có tín hiệu thu hẹp qua mã khóa".
- Fallback BM25 theo tên môn (`subject_name`): chỉ áp dụng khi câu hỏi **không** có `subject_code` VÀ **không** có token cohort khớp được (L686-690) — nếu có mã khóa trần (dạng không hậu tố chữ), bỏ fallback theo tên để câu như "lịch thi K70 cuối kì" không bị lọc nhầm bởi cụm tên môn rỗng.

### 7.7.4. Guard chặn tra cứu quá rộng

- `_exam_schedule_search()` (`tool_adapters.py:735-812`) có 2 lớp chặn trước khi query ES:
  1. Không filter nào có giá trị (`not any(filters.values())`, L777) → trả `"[Loi: Khong xac dinh duoc mon/ngay thi tu cau hoi]"`.
  2. Chỉ có `exam_type` (vd chỉ "cuối kỳ") mà **không** có filter thu hẹp nào khác (`subject_code`/`subject_name`/`exam_date(_from/_to)`/`exam_room`/`group`/`cohort` — `_narrowing_keys`, L783-790) → trả câu nhắc người dùng cung cấp tên/mã môn/ngày/mã khóa, **không** query ES (tránh trả ngẫu nhiên top-K dòng không liên quan khi câu hỏi chung dạng "lịch thi cuối kỳ" lẫn lọt qua được guard đặc trưng ở Mục 1 nhờ một tín hiệu khác).
- Fallback theo tên khi mã môn sai/không khớp: tra theo `subject_code` mà `rows` rỗng (L801-809) → thử lại bằng `subject_name` (chuỗi query đã strip PII), giữ nguyên `exam_type`/`cohort` đã xác định — bắt các trường hợp gõ sai mã môn nhưng đúng tên môn.

### 7.7.5. Truy vấn Elasticsearch — `ExamScheduleESStore` (`retrieval/exam_schedule_store.py`)

- Index riêng `exam_schedules` (`config/settings.py:334`, đổi được qua `exam_schedule_es_index`) — **tách hoàn toàn** khỏi index chunk tài liệu (`ElasticsearchStore`), vì dữ liệu lịch thi có dạng bảng cố định (13 cột), không phải văn bản tự do.
- `build_query()` (L223-297, testable độc lập): filter chính xác (`subject_code`, `exam_type`, `exam_room`, `group`, `exam_date`/khoảng ngày, và `cohort` — dùng `prefix` match để "K70" vẫn khớp bản ghi "K70C") đi vào `filter` clause (không ảnh hưởng score). `subject_name` (BM25 trên `subject_name^2` + `search_text`) đi vào **`should`** (booster) nếu đã có `subject_code`, nhưng vào **`must`** (bắt buộc, là discriminator chính) nếu **không** có `subject_code` — tránh trường hợp chỉ có `exam_type` + tên môn optional trả về dòng ngẫu nhiên sắp theo ngày.
- Sort (`search()`, L299-342): tra theo tên môn mà không có ngày cụ thể → sort theo `_score` (BM25) trước, để môn được hỏi không bị dòng ngày sớm hơn đẩy khỏi top-K; ngược lại (có `subject_code`/ngày cụ thể) → sort theo `exam_date` rồi `start_time` tăng dần.
- Field ES: `exam_date` kiểu `date` (chấp ISO/`dd/MM/yyyy`/epoch millis); còn lại `keyword` (`subject_code`, `exam_type`, `exam_room`, `exam_session`, `start_time`, `group`, `cohort`, `exam_week`, `weekday`, `exam_batch`, `mgmt_class_code`, `exam_class_code`, `exam_date_str`, `source_file`) — dùng chung Vietnamese analyzer/synonym/stopword với `ElasticsearchStore`, tự fallback sang tokenizer `standard` nếu thiếu plugin tiếng Việt.

### 7.7.6. Kết quả trả về cho LLM

- `_format_exam_results()` (`tool_adapters.py:694-732`): mỗi dòng ES → một dòng text `"[i] {mã} — {tên} | {ngày/kíp thi} | Phòng {phòng} | Nhóm {nhóm} | Đợt {đợt} | Ghi chú: {note}"`.
- `SYNTHESIS_PROMPT` (`agent/prompts.py:10-24`) có đoạn hướng dẫn riêng cho lịch thi (L21-24): mỗi dòng `"[i] ..."` là **một slot thi riêng** (khác nhóm/khác đối tượng); trường `"Ghi chú"` cho biết **đối tượng** được thi slot đó (ngành/chương trình/mã khóa, vd `"Kỹ thuật máy tính-MĐ1,2-K68S"`, `"*Việt Nhật K67S"`) — bắt buộc phải trình bày; LLM **không được** gộp các slot trùng ngày/giờ/phòng thành "tất cả các nhóm" mà bỏ mất Ghi chú riêng của từng slot.

### 7.7.7. Runtime & hạ tầng (khác biệt so với Qdrant path)

- `_AdapterRuntime.exam_es_store` (`tool_adapters.py:155`) được dựng **độc lập** khỏi `RetrievalService` — cả `_build_runtime()` (lazy fallback, L214-243) và `inject_from_retrieval_service()` (đường dùng chung với pipeline, L261-289) đều tự gọi `_build_exam_es_store(settings)` (L189-211) riêng, vì index lịch thi không được `RetrievalService` expose sẵn.
- Kết nối ES thất bại (`ConnectionError` hoặc bất kỳ exception) → `_build_exam_es_store` **không raise**, trả `None` và log warning — `_exam_schedule_search` khi đó trả `"[Loi: Kho du lieu lich thi chua san sang]"` (degrade gracefully) thay vì crash toàn bộ Agent.
- Retry-relax của Executor (`_relaxed_steps`, `react_agent.py:558-573`) drop `major_hint`/`cohort_hint` khi TOÀN BỘ step đều rỗng — áp dụng đồng nhất cho mọi collection, nhưng với `lich_thi` gần như luôn là no-op: planner được hướng dẫn không set `major_hint`/`cohort_hint` cho step `lich_thi` (7.7.1), và `_run()` cũng không truyền `cohort_hint` cho exam tool (7.7.2).

### 7.7.8. Ingestion — Admin upload lịch thi (khác hoàn toàn pipeline `/admin/documents`)

- **File:** `api/routes/exam_schedules.py`. Endpoint `POST /admin/exam-schedules` (L62-123, `require_admin`): nhận `file` (`.pdf`/`.xlsx`/`.xlsm`, `_ALLOWED_SUFFIXES` L47) + `exam_type` tùy chọn qua multipart form (`_ALLOWED_EXAM_TYPES = ("giua_ky", "cuoi_ky")`, L48; 400 nếu giá trị khác). Đây **không** phải state machine convert→clean→chunk→embed như `/admin/documents` — file được lưu đĩa (`uploads/exam_schedules/{doc_id}.{ext}`, `_save_upload` L51-59) rồi parse **đồng bộ ngay trong request** (`ingest_exam_schedule`), trả `201 + ParseReport` cho admin thấy ngay số dòng parse được/bị skip.
- **Parse:** `services/exam_schedule_parser.py` — `parse_exam_workbook()`/`_async()` (L359-445) dispatch theo đuôi file: `load_pdf_rows` (pdfplumber, PDF dạng bảng text) hoặc `load_workbook_rows` (openpyxl) — cùng schema 13-cột cố định qua `_DEFAULT_COLUMN_MAP`/`settings.exam_schedule_column_map` (2 layout tên cột khác nhau được alias vào cùng field, vd `"ma lop qt"`/`"ma lop"` → `mgmt_class_code`). **Không dùng LLM** để parse.
- **`exam_type` auto-detect:** `detect_exam_type(banner_text, filename)` (L250-264) — nếu admin không chọn tường minh, suy ra từ banner PDF/tên file bằng `_GIUA_KY_RE`/`_CUOI_KY_RE`; banner nêu **cả hai** kỳ hoặc **không** kỳ nào → trả `None` (không đoán khi mơ hồ), để trống trên record.
- **Idempotent theo `source_file`:** `ingest_exam_schedule()` (`services/exam_schedule_service.py:59-135`) — file parse ra **0 dòng hợp lệ** → **giữ nguyên** dữ liệu cũ (không xóa gì, tránh 1 lần upload lỗi xóa sạch lịch thi đang có, L84-99). Ngược lại: xóa hết dòng cũ cùng `source_file` ở **cả** Mongo (`EXAM_SCHEDULES_COLLECTION`) và ES (`delete_by_source_file`) rồi insert dòng mới — re-upload cùng file sẽ **thay thế** (replace), không cộng dồn/trùng lặp.
- **Blocking I/O offload:** mọi lệnh gọi Elasticsearch (sync client) trong service này được bọc `anyio.to_thread.run_sync` (`services/exam_schedule_service.py:107-109, 121-123, 169-171`); Mongo dùng driver async (Motor) trực tiếp, không cần offload.
- Endpoint bổ trợ: `GET /admin/exam-schedules/summary` (L152-186, đếm `total_rows`/`distinct_subjects`/`distinct_exam_dates`/theo từng `source_file`) và `DELETE /admin/exam-schedules?source_file=...` (L189-217, xóa cả Mongo + ES + file trên đĩa, idempotent — file không tồn tại trả về count 0, không 404).

---

## 8. Chuẩn bị LLM Context (Nhúng Chunks vào Prompt)

- **File:** `pipeline/flows/context.py` — `_format_context()` (L49-153): gộp các document/chunk đã rerank thành chuỗi context, giới hạn theo ký tự (không phải token): mỗi doc tối đa `per_doc_char_limit` (mặc định **1500** ký tự — `_DEFAULT_CONTEXT_DOC_CHAR_LIMIT`), tổng ngân sách `total_char_budget` (mặc định **8000** ký tự — `_DEFAULT_CONTEXT_TOTAL_CHAR_BUDGET`, tự nhân hệ số khi truy vấn dạng liệt kê — `_resolve_context_budget`, L156). Chunk là "sibling" (từ sibling expansion, đánh dấu `_expansion_source`) được giới hạn thấp hơn (**800** ký tự, chia ngân sách 70/30 với doc chính). Mỗi chunk được chèn header metadata (`Mã ngành`, `Ngành` — ưu tiên tên chuẩn theo `MAJOR_CODE_TO_NAME` nếu lệch với metadata lưu trữ, `Khóa`, `Ngày đăng` với `kehoach`, `URL` nếu là link http(s) thật để LLM có thể trích dẫn Markdown link). Có khử trùng `parent_context` khi nhiều chunk con chia sẻ cùng `parent_id` (chỉ render ngữ cảnh section cha một lần). Dừng thêm doc khi vượt `total_char_budget`; ghi trace `context_chars`/`context_docs_used`/`context_docs_dropped` nếu `trace_out` được truyền vào.
- Khi có kết quả Tavily, `_merge_local_and_web_context()` (cùng file) gộp context nội bộ + context web, kèm hướng dẫn tường minh cho LLM: ưu tiên nguồn nội bộ cho câu hỏi quy chế/chương trình đào tạo/điều kiện tốt nghiệp, chỉ dùng `web_live_context` khi nguồn nội bộ không có thông tin hoặc cần xác nhận dữ liệu thời gian thực (lịch thi, thông báo mới).
- **File:** `llm/prompts.py` — `build_rag_messages(query, context, history)` (L228-265): trả về `[{"role":"system","content":RAG_SYSTEM_PROMPT}, {"role":"user","content": ...}]`. Chọn 1 trong 2 template tùy có `history` hay không: có history → `RAG_USER_WITH_HISTORY_TEMPLATE` (L70-80, điền `history`/`context`/`query`); không có history → `RAG_USER_TEMPLATE` (L61-68, chỉ điền `context`/`query`). `history` được format qua `_format_history()` (L220-225), trong đó **markdown link trong các turn cũ bị strip về text thuần** (`_strip_markdown_links`, regex `_MARKDOWN_LINK_RE`) để tránh LLM chép lại link cũ/hỏng từ lượt hội thoại trước.
  - **Điểm quan trọng thường bị hiểu sai:** hàm này được `rag_flow()` gọi **riêng** ở `coordinators.py:1007` — nhưng chỉ để dựng `llm_prompt_str` phục vụ **trace/debug**, KHÔNG phải object thực sự gửi cho LLM. Lệnh `chat_model.generate()` (L1017-1022) nhận trực tiếp `query`/`context`/`history`/`mode` — mỗi provider LLM cụ thể (vd `GeminiLLM.generate()`, `llm/gemini.py:66-119`) tự gọi lại `build_rag_messages()` một lần nữa bên trong (`self._build_messages(...)`) để dựng message list thật sự gửi API.

---

## 9. LLM Generation (Sinh câu trả lời)

- **File:** `llm/base.py` — `BaseLLM` (abstract, `generate()`/`generate_stream()`), mọi provider phải kế thừa.
- **File:** `llm/__init__.py` — `create_llm(settings)` (L31) chọn provider theo `settings.llm_provider`. Provider đã đăng ký thật sự: **`deepseek`** (`llm/deepseek.py`, **mặc định**), **`gemini`** (`llm/gemini.py`), **`lm_studio`** (`llm/lm_studio.py`) — không phải "OpenAI/Gemini" chung chung như hay bị mô tả. `pipeline/rag_pipeline.py:150` khởi tạo `self._chat: BaseLLM = create_llm(settings)` — đây là instance thật sự dùng làm `chat_model` trong `rag_flow()`.
  - **Mặc định production: `chat_model = "deepseek-v4-flash"` qua provider DeepSeek** (`config/settings.py:65-137`), chọn có chủ đích cho chất lượng sinh câu trả lời. **Gemini được dùng cho reflection/rewrite câu hỏi (Mục 3) và tổng hợp câu trả lời agent, KHÔNG phải cho generation RAG chính** — đây là 2 lời gọi LLM khác nhau, dùng model khác nhau.
  - Lưu ý tránh nhầm lẫn: `llm/chat_model.py` có định nghĩa alias `ChatModel = GeminiLLM` (giữ lại "for backwards compatibility" theo comment trong `llm/__init__.py`) — alias này **không** được `RAGPipeline` sử dụng để tạo `chat_model` (pipeline luôn dùng `create_llm(settings)` ở trên); đây là export cũ, không phản ánh provider thật đang chạy.
  - Cả 3 provider (`GeminiLLM`, `DeepSeekLLM`, `LMStudioLLM`) đều dùng chung SDK `openai.OpenAI`, chỉ khác `base_url` (Gemini: endpoint OpenAI-compatible của Google; DeepSeek: endpoint OpenAI-compatible riêng; LM Studio: `http://localhost:1234/v1`) — không có provider nào gọi thẳng `api.openai.com`.
- **File:** `pipeline/flows/coordinators.py`, bên trong `rag_flow()` (L1004-1050) — **cơ chế retry context-length**:
  1. Gọi `chat_model.generate(query=question, context=full_context, history=trimmed, mode="rag")`.
  2. Nếu lỗi, kiểm tra `_is_context_length_error(exc)` (`pipeline/flows/common.py:142-145` — so khớp chuỗi lỗi (không phân biệt hoa/thường) với các marker: `"context length"`, `"maximum context length"`, `"too many tokens"`, `"tokens to keep"`, `"prompt is too long"`, `"context_length_exceeded"`). Nếu **không** phải lỗi context-length → **raise lại ngay**, không nuốt lỗi khác.
  3. Nếu đúng là lỗi context-length: dựng `reduced_context = _format_context(reranked[:2], per_doc_char_limit=600, total_char_budget=1500)`, cắt history còn tối đa 3 turn (`_trim_history(history, limit=3)`), gọi lại `generate()` **một lần**.
  4. Nếu lần retry đó **vẫn** báo lỗi context-length → raise `RuntimeError` bằng tiếng Việt yêu cầu người dùng bắt đầu phiên mới hoặc hỏi ngắn gọn hơn; lỗi khác thì raise nguyên trạng.
  5. Retry thành công → `timings_ms["context_recovery"] = 1.0`.
- **Giá trị trả về:** `chat_model.generate()` bản thân chỉ trả về **một chuỗi text** (câu trả lời) — **không** trả về dict chứa `sources`/`timings_ms`. Dict kết quả đầy đủ (`question`, `answer`, `sources`, `num_sources`, `intent`, `model_name`, `target_collections`, `collection_scores`, `reflected_question`, `timings_ms`, `routing_probabilities`, `reflection_prompt`, `llm_prompt`, `applied_filters`, `collection_results`, `fusion_weights`, `context_trace`, `rerank_trace`, `answer_status`, `answer_quality_gate`, `tools_used`, `tool_calls`, ...) được `rag_flow()` tự lắp ráp ở câu lệnh `return` cuối cùng (`coordinators.py:1273+`), với `answer` đã qua `_strip_raw_urls()`.

---

## 10. Định dạng Response & Trả về cho User

- **File:** `api/routes/chat.py` (import `ChatResponseMapper` tại L23) — **dùng 2 phương thức mapper khác nhau tuỳ endpoint**, không phải một đường đi chung:
  - `chat()` (`POST /chat`, L196) → `ChatResponseMapper.to_chat_response(result, fallback_question=..., session_id=...)` — dựng đầy đủ model Pydantic `ChatResponse`.
  - `chat_v3()` và các nhánh của nó (L271, 306, 324, 341) → `ChatResponseMapper.normalize_v3_result(result, session_id)` — trả về **dict thuần** đã chuẩn hoá key, **không** dựng instance `ChatResponse` — nghĩa là response của `/chat/v3` là JSON "lỏng" hơn, không qua validate Pydantic nghiêm ngặt.
- **File:** `api/response_mapper.py` — class `ChatResponseMapper` (L68), toàn bộ method là `@staticmethod`:
  - `to_chat_response()` (L74-181): gọi `normalize_v3_result()` bên trong trước, sau đó chuyển `retrieved_documents`/`sources` thành các object `RetrievedDocument` (`rank`, `content`, `score`, `hybrid_score`, `rerank_score`, `vector_score`, `keyword_score`, `collection`, `metadata`), dựng các sub-model `AgentToolCall`/`AgentTracePayload`/`FilterInfo`/`CollectionResult` qua helper riêng (`to_tool_call_models`, `to_agent_trace_model`, `to_filter_models`, `to_collection_result_models`), và backfill `tools_used`/`tool_calls` từ `agent_trace` khi dict pipeline gốc chưa set trực tiếp.
  - `normalize_v3_result()` (L184-223): set default (`session_id`, `retrieved_documents` từ `sources` qua `_to_retrieved_documents`, `num_documents`, `tools_used=[]`, `tool_calls=[]`, `iterations=0`, `agent_trace=None`) và backfill `tool_calls`/`tools_used` từ `agent_trace` nếu có — đảm bảo shape ổn định cho UI trace/debug mà không cần validate Pydantic đầy đủ.
