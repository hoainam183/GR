# Chiến lược Routing — RAG v2

Bản dịch tiếng Việt của `ROUTING_STRATEGY.md`. Nguồn xác minh: 2026-07-05, đọc trực tiếp `pipeline/rag_pipeline.py`, `pipeline/rag_helpers.py`, `query/complexity_router.py`, `query/router.py`, `query/domain_classifier.py`, `query/signals.py`, `query/prompts.py`, `query/training_data.py`, `query/train_classifier.py`, `embedding/bge_m3.py`, `retrieval/collection_selector.py`, `agent/react_agent.py`, `api/routes/chat.py`.

Tài liệu này mô tả **mọi quyết định routing** mà một câu hỏi đi qua, từ điểm vào HTTP đến việc chọn collection và đường thực thi agent, kèm trích dẫn `file:line` chính xác để có thể đối chiếu ngược lại với source bất cứ lúc nào.

Hệ thống có **hai router khác nhau**, dễ nhầm vì cả hai đều được gọi là "router":

1. **`ComplexityRouter`** (`query/complexity_router.py`) — quyết định *pipeline nào xử lý câu hỏi*: trả lời chitchat có sẵn, RAG v2 cổ điển, hay agent Planner-Executor. Kết quả: `chitchat` / `simple` / `complex` / `unknown`.
2. **`QueryRouter`** (`query/router.py`, dùng `DomainClassifier` trong `query/domain_classifier.py`) — quyết định *domain/collection kiến thức nào* mà một câu hỏi có intent RAG cần tra cứu. Kết quả: `intent` (`chitchat`/`rag`/`tool_search`) + `domains` (`ctdt`/`quydinh`/`kehoach`/`stsv`).

`RAGPipeline._decide_complexity` (`pipeline/rag_pipeline.py:1044`) **gộp cả hai router** thành một quyết định 3 tầng (cộng thêm tầng thứ 4, Tier-3, thuộc về cơ chế escalation domain-confidence riêng của `QueryRouter`, không liên quan complexity).

---

## 1. Điểm vào (Entry points)

| Điểm vào | File:line | Hành vi |
|---|---|---|
| `POST /chat` | `api/routes/chat.py:97` | `mode="auto"` (mặc định) → smart routing qua `query_v3`. `mode="agent"` ép dùng agent. `mode="rag"` ép dùng RAG v2 cổ điển, bỏ qua cả hai router. |
| `RAGPipeline.query_v3` | `pipeline/rag_pipeline.py:798` | Điểm vào smart, không streaming. Chạy reflection → `_decide_complexity` → điều phối tới handler chitchat / `query()` / `query_agent()`. |
| Nhánh gọi `RAGPipeline.rag_flow_stream` (đường streaming) | `pipeline/rag_pipeline.py:1190` | Cùng gọi `_decide_complexity`, bản streaming. Rẽ nhánh tại `pipeline/rag_pipeline.py:1254` (complex → agent) và `pipeline/rag_pipeline.py:1326` (simple/fallback → RAG v2). |

Cả hai điểm vào (streaming và không streaming) đều gọi reflection trước (`_run_reflection`, `pipeline/rag_pipeline.py:386`) để **routing luôn nhìn thấy câu hỏi đã được viết lại thành câu độc lập (reflected)**, chứ không phải mảnh câu follow-up thô. Điều này quan trọng vì cả regex Tier 0 lẫn phân loại domain Tier 1 đều chạy trên `reflected_question`, không phải `question` gốc.

---

## 2. Routing độ phức tạp (`ComplexityRouter`) — chitchat / simple / complex

Điểm vào: `RAGPipeline._decide_complexity(reflected_question, history)` — `pipeline/rag_pipeline.py:1044-1101`.

Đây là **cascade 3 tầng, rẻ nhất chạy trước**:

```
Tier 0  ComplexityRouter.route()          (regex/heuristic, ~0ms)
   │  tier != "unknown" ─────────────────────────────► trả (tier, subtype)
   ▼ tier == "unknown"
Tier 1  QueryRouter.route() trên câu đã reflect, KHÔNG dùng lịch sử chat
        (classifier embedding, ~10-50ms)
   │  intent != "rag" ───────────────────────────────► trả ("simple", None)
   │  <2 domain active VÀ không có tín hiệu multi_domain ──► trả ("simple", None)
   ▼  ≥2 domain active HOẶC có tín hiệu multi_domain
Tier 2  _classify_complexity_llm()          (LLM phán xử, ~12s, hiếm khi chạy)
        └──────────────────────────────────────────► trả (llm_tier, llm_subtype)
```

`_decide_complexity` **không bao giờ trả về `"unknown"`** — giá trị đó chỉ tồn tại nội bộ trong Tier 0, mang nghĩa "chuyển giao xuống tầng dưới quyết định".

### 2.1 Tier 0 — `ComplexityRouter.route()` (`query/complexity_router.py:216-467`)

Chạy một chuỗi kiểm tra cố định, có thứ tự. Khớp đầu tiên thắng; mỗi nhánh trả về ngay `{tier, reason, confidence, complex_subtype?, query_signals}`.

1. **Chitchat (đường tắt)** (`query/complexity_router.py:237-249`) — khớp `CHITCHAT_PATTERNS` (`query/complexity_router.py:24-32`): chào hỏi, cảm ơn, tạm biệt, "bạn là ai", các từ đồng ý ok/oke. Cắt luồng trước khi chạm vào bất kỳ bước retrieval nào. Được xử lý tiếp bởi `RAGPipeline._handle_chitchat` (`pipeline/rag_pipeline.py:1103`) — một bảng tra cứu câu trả lời có sẵn, không gọi LLM.

2. **Đường tắt lịch thi** (`query/complexity_router.py:258-273`) — `_FOLDED_EXAM_RE` (`query/complexity_router.py:122-126`) khớp "lịch thi", "phòng thi", "kíp thi"... (có negative lookahead để "phòng thí nghiệm" không bị khớp nhầm). Được chặn bởi **cổng tính cụ thể (specificity guard)**: chỉ kích hoạt khi câu hỏi có kèm mã môn cụ thể, khóa, ngày, hoặc nhóm (`_EXAM_SPECIFIC_SIGNALS_RE`, `query/complexity_router.py:132-144`), hoặc dùng cách diễn đạt vốn đã cụ thể như "thi môn X" (`_EXAM_INHERENTLY_SPECIFIC_RE`, `query/complexity_router.py:147-150`). Câu chung chung như "lịch thi cuối kì" (không có tín hiệu cụ thể) sẽ rơi xuống các tầng ML, và được route sang `kehoach`. Route thành `tier="complex"`, `complex_subtype="general"` để planner sinh ra một step `lich_thi` có cấu trúc.

3. **Liên từ yêu cầu lặp lại** (`query/complexity_router.py:279-291`) — từ "cho" xuất hiện ≥2 lần cộng với liên từ "và" → `complex/general` (câu hỏi ghép nhiều yêu cầu, ví dụ "cho tôi biết học phí và cho tôi biết lịch thi").

4. **Cổng tra cứu 1-sự-thật (single-fact policy lookup)** (`query/complexity_router.py:293-304`, hàm hỗ trợ `_is_single_fact_policy_lookup` tại `query/complexity_router.py:169-189`) — nếu câu hỏi có tín hiệu tra cứu (`query_signals.exact_policy_lookup`, `.table_lookup`, hoặc khớp `_FOLDED_SINGLE_FACT_RE`: "bao nhiêu", "bao lâu", "mức nào"...) **và** không có bất kỳ dấu hiệu nào trong số so sánh/đa chủ đề/nhiều dấu `?`/`≥3 "và"` — route thẳng `tier="simple"`, **bỏ qua hoàn toàn Tier 1-2**. Đây là chốt chặn chính chống lại việc đẩy nhầm câu hỏi sự thật đơn giản sang agent.

5. **Tín hiệu cá nhân + điều kiện** (`query/complexity_router.py:306-318`) — `query_signals.personal_reference AND query_signals.eligibility_check` (cả hai từ `analyze_query_signals`, `query/signals.py:198`) → `complex/multi_source`. Bắt được "điều kiện tốt nghiệp của tôi là gì".

6. **Bản không dấu (accent-folded) của #5** (`query/complexity_router.py:323-335`) — `_FOLDED_PERSONAL_ABILITY_RE` (`query/complexity_router.py:163-166`) bắt biến thể không dấu của #5 (ví dụ input mobile "toi co du dieu kien tot nghiep khong"), vì `analyze_query_signals` có thể không bắt hết mọi cách viết bỏ dấu.

7. **So sánh không dấu + ngữ cảnh chương trình** (`query/complexity_router.py:347-362`) — `_FOLDED_COMPARISON_RE` ("so sanh", "khac nhau", …) cộng với một token chương trình/khóa (`k\d{2,3}|nganh|chuong trinh|ctdt|hoc ky|quy dinh`) → `complex/comparison`.

8. **Liên từ nhiều bước** (`query/complexity_router.py:364-379`) — `" va "` cộng với động từ hành động ("cho biết", "liệt kê", "so sánh", "giải thích") → `complex/general`.

9. **`_COMPLEX_PATTERN_SPECS`** (`query/complexity_router.py:43-88`, kiểm tra tại `query/complexity_router.py:381-394`) — danh sách có thứ tự các cặp `(pattern, subtype)`, khớp đầu tiên thắng:
   - `comparison`: "so sánh" tường minh; hai mã khóa (`K65…K70`); hai mã chương trình (`IT-E6…IT-E7`); "khác nhau/khác biệt/giống nhau" đi kèm ngữ cảnh khóa/chương trình.
   - `multi_source`: "tương đương/chuyển đổi/thay thế" kết hợp với "đồ án/tốt nghiệp/xét tốt nghiệp" (câu hỏi ghép giữa tra cứu tương đương chương trình và điều kiện tốt nghiệp — cố tình route sang decomposition thay vì lập kế hoạch trực tiếp); cách diễn đạt khả năng/điều kiện cá nhân ("tôi/mình/em … có thể/đủ điều kiện/được không" — subtype `personal_check` riêng cũ đã bị loại bỏ để dùng chung `multi_source`, theo comment tại `query/complexity_router.py:70-76`); "đủ điều kiện"; "có thể/có được … tốt nghiệp/đăng ký/xét duyệt/nhận học bổng"; "môn/học phần … được/có đăng ký/mở"; "tất cả … điều kiện".
   - `general`: câu hỏi chỉ có từ khóa domain trơ trụi ("học bổng?", "quy định?"); "cho tôi biết về X"; "và" + "cho biết/liệt kê/so sánh/giải thích".

10. **Heuristic cấu trúc** (`query/complexity_router.py:397-450`, confidence `"medium"`, subtype luôn là `general`):
    - `word_count > 30` **và** có liên từ đa chủ đề (`_MULTI_TOPIC_RE`: "cũng", "ngoài ra", "đồng thời", "bên cạnh đó", "kết hợp") → `complex`. Câu dài nhưng *chỉ 1 chủ đề* (ví dụ mô tả chi tiết một quy trình) vẫn giữ `simple` — độ dài một mình không phải là tín hiệu.
    - Có hơn một dấu `?` trong câu → `complex`.
    - `≥3` lần xuất hiện `" và "` → `complex` (câu hỏi ghép nhiều phần).

11. **Rơi xuống cuối (fall-through)** (`query/complexity_router.py:452-467`) — không có tín hiệu Tier-0 nào quyết định → `tier="unknown"`, `confidence="low"`. Đây chính là thứ kích hoạt Tier 1/2 trong `_decide_complexity`.

Lưu ý: `ComplexityRouter.route_tier()` (`query/complexity_router.py:469-477`) là một wrapper tiện ích cũ (legacy) được dùng ở nơi khác (ví dụ `pipeline/rag_pipeline.py:601` bên trong `query_agent` để suy ra subtype khi agent được gọi trực tiếp mà không đi qua `_decide_complexity`) — nó gộp `"unknown"` thành `"simple"` vì không có quyền truy cập vào Tier 1-2.

#### Các hàm hỗ trợ tín hiệu (query signals) đứng sau Tier 0 (`query/signals.py`)

`analyze_query_signals(query)` (`query/signals.py:198-254`) tính ra một dataclass `QuerySignals` (`query/signals.py:16-34`) gồm các cờ boolean, tất cả đều nhận biết được việc bỏ dấu tiếng Việt qua `fold_vietnamese_text` (`query/signals.py:37-41`, giải mã NFD + loại bỏ dấu kết hợp + `đ`→`d`):

| Tín hiệu | Mục đích | Nhóm pattern |
|---|---|---|
| `personal_reference` | "của tôi/mình/em", "tôi đang học ngành…" | `_PERSONAL_PATTERNS` (`query/signals.py:76-84`) |
| `eligibility_check` | "đủ điều kiện", "xét tốt nghiệp", "chuẩn đầu ra" | `_ELIGIBILITY_PATTERNS` (`query/signals.py:86-93`) |
| `exact_policy_lookup` | "bao nhiêu", "học phí", "tín chỉ" **hoặc** nghĩa "mấy" (bao nhiêu) nhận biết dấu | `_EXACT_LOOKUP_PATTERNS` (`query/signals.py:97-101`) + `_has_how_many_token` (`query/signals.py:68-73`) |
| `table_lookup` | "bảng điểm", "mức học phí", "khung/phụ lục" | `_TABLE_LOOKUP_PATTERNS` (`query/signals.py:103-117`) |
| `procedural_support` | "chưa nhận được", "khiếu nại", "nộp đơn" | `_PROCEDURAL_PATTERNS` (`query/signals.py:119-129`) |
| `freshness` | "mới nhất", "gần đây", "kỳ mới" | `_FRESHNESS_PATTERNS` (`query/signals.py:131-134`) |
| `schedule_intent` | "lịch thi/học/đăng ký", "thời khóa biểu" | `_SCHEDULE_PATTERNS` (`query/signals.py:136-140`) |
| `deadline_intent` | "deadline", "hết hạn", "hạn nộp" | `_DEADLINE_PATTERNS` (`query/signals.py:142-147`) |
| `announcement_intent` | "thông báo", "danh sách được nhận", "kết quả xét" | `_ANNOUNCEMENT_PATTERNS` (`query/signals.py:150-160`) |
| `curriculum_semester_intent` | "môn X học/đăng ký vào kỳ mấy" (kỳ NÀO trong chương trình đào tạo chuẩn, thuộc ctdt) — phân biệt với `schedule_intent` (KHI NÀO mở đăng ký, thuộc kehoach) qua việc `_WHEN_OPENING_PATTERNS` triệt tiêu tín hiệu này, rồi được bật lại nếu có `_CTDT_CONTEXT_PATTERNS` | `query/signals.py:168-213` |
| `multi_domain` | suy ra từ: `(eligibility_check VÀ có ngữ cảnh chương trình)` HOẶC `(procedural_support VÀ (exact_policy_lookup HOẶC table_lookup))` HOẶC `graduation_rule` (tốt nghiệp/điều kiện + quy định/chương trình/ngành/tín chỉ) | `query/signals.py:231-240` |

**Va chạm đã được xử lý ở đây**: việc bỏ dấu tiếng Việt làm "mấy" (bao nhiêu) và "máy" (machine, như trong "Khoa học Máy tính") thu gọn về cùng một token đã bỏ dấu `"may"`. Một câu hỏi mang nghĩa "bao nhiêu" không được phép bị kích hoạt sai bởi tên ngành có chữ "máy". `_has_how_many_token` (`query/signals.py:64-73`) phân biệt bằng cách đếm số lần khớp `\bmay\b` (đã bỏ dấu) trừ đi số lần khớp `\bmáy\b` (có dấu) trừ tiếp số lần khớp "kỳ/thứ mấy" (hỏi thứ tự) — nhờ vậy tên ngành không bao giờ kích hoạt nhầm tra cứu "bao nhiêu", nhưng input không dấu từ mobile (nơi số lần khớp "máy" có dấu = 0) vẫn hoạt động đúng.

### 2.2 Tier 1 — Phân loại domain đa nhãn bằng ML (`pipeline/rag_pipeline.py:1067-1097`)

Chạy `self._router.route(reflected_question)` (không truyền `chat_history` — cố tình để tránh rò rỉ ngữ cảnh, khớp với `_reroute_reflected` tại `pipeline/rag_pipeline.py:323`). Đây là *cùng một* `QueryRouter` dùng để chọn domain/collection (§3), được tái sử dụng ở đây chỉ để đếm xem câu hỏi chạm bao nhiêu collection:

```python
routing = self._router.route(reflected_question)
if routing["intent"] != "rag":
    return "simple", None                       # chitchat/tool_search không bao giờ tới planner ở đây
spans_two_collections = self._count_active_domains(routing) >= 2   # rag_pipeline.py:979-989
if not (spans_two_collections or signals.get("multi_domain")):
    return "simple", None
```

`_count_active_domains` (`pipeline/rag_pipeline.py:979-989`) đếm các xác suất ≥ `MULTI_LABEL_THRESHOLD = 0.35` (`query/domain_classifier.py:49`). Đây là tín hiệu **entity-agnostic** (không phụ thuộc thực thể cụ thể) — nó đến từ phân bố xác suất của classifier đã huấn luyện, chứ không phải từ việc liệt kê tay mã ngành/chương trình trong regex.

**Cơ chế "cứu" ở ranh giới xác suất (borderline-margin rescue)** (`pipeline/rag_pipeline.py:1084-1096`): một câu hỏi tốt nghiệp/điều kiện có nêu tên chương trình cụ thể (ví dụ "điều kiện tốt nghiệp của IT-E6") đôi khi có domain thứ hai (quydinh) rơi ngay dưới ngưỡng 0.35 (quan sát thực tế trong production: ctdt 0.951, quydinh 0.300) — chỉ một collection vượt ngưỡng, và câu hỏi sẽ bị chốt sai thành `simple` trước khi kịp đến tầng phán xử Tier-2. Tín hiệu `multi_domain` tất định (deterministic) từ `query/signals.py` (bảng ở §2.1) được OR thêm vào chính để ngăn điều này — nó cho phép các câu hỏi kiểu này đến được Tier 2 mà không cần liệt kê tay từng mã ngành.

Nếu cả hai điều kiện đều không thỏa → `("simple", None)`. Đây là **đường thoát chiếm đa số** — hầu hết câu hỏi 1-sự-thật với một domain trội rõ ràng không bao giờ chạm tới LLM.

### 2.3 Tier 2 — LLM phán xử độ phức tạp (`RAGPipeline._classify_complexity_llm`, `pipeline/rag_pipeline.py:991-1042`)

Chỉ được gọi khi Tier 1 báo câu hỏi trải rộng ≥2 collection. Chi phí có giới hạn: đây là đường đắt (~1 lệnh gọi LLM), chỉ áp dụng cho các câu hỏi thực sự mập mờ.

- Prompt: `COMPLEXITY_CLASSIFICATION_PROMPT` (`query/prompts.py:402-431`). Yêu cầu tường minh LLM đánh giá **nhu cầu thông tin** (một sự thật đơn lẻ vs. nhiều nhu cầu riêng biệt vs. so sánh vs. nhiều bước), không bao giờ hỏi ngành/chương trình nào được nêu — nhờ vậy cùng một prompt tổng quát hóa cho mọi chương trình mà không cần sửa code. Các ví dụ few-shot nhúng sẵn trong prompt "đóng cứng" trường hợp kinh điển: "điều kiện tốt nghiệp" → luôn là `complex/multi_source` bất kể ngành nào, vì phải gộp quy định (ngoại ngữ, kỷ luật, CPA) với CTĐT (tín chỉ, môn bắt buộc).
- Phân tích phản hồi: dùng regex trích ra khối JSON `{...}` đầu tiên (`pipeline/rag_pipeline.py:1020-1021`) — phòng trường hợp LLM bọc JSON trong văn xuôi hoặc markdown fence.
- `subtype` được kiểm tra hợp lệ với tập `{"comparison", "multi_source", "general"}`; bất kỳ giá trị nào khác (kể cả thiếu key) sẽ mặc định thành `"multi_source"` (`pipeline/rag_pipeline.py:1027-1029`).
- **Mặc định an toàn khi lỗi (fail-safe)**: bất kỳ exception nào (lỗi LLM, JSON hỏng) → `{"tier": "simple", "subtype": None}` (`pipeline/rag_pipeline.py:1038-1042`). Tier-2 hỏng không bao giờ chặn câu trả lời — nó chỉ đơn giản bỏ qua đường agent.

### 2.4 Điều phối sau khi có kết quả cuối cùng

- `"chitchat"` → `RAGPipeline._handle_chitchat` (`pipeline/rag_pipeline.py:1103`), tra bảng chuỗi có sẵn theo từ khóa chào/cảm ơn/tạm biệt. Không retrieval, không LLM.
- `"simple"` (hoặc `runtime.agent is None`) → `RAGPipeline.query()` cổ điển → `rag_flow`/`rag_flow_stream` (`pipeline/rag_pipeline.py:852-868`, `pipeline/rag_pipeline.py:1326-1399`). Đây là lúc `QueryRouter`/`DomainClassifier` chạy *lại một lần nữa*, lần này để chọn domain/collection (§3) — có dùng lịch sử chat và Tier-3 fallback đang bật.
- `"complex"` → `RAGPipeline.query_agent()` (`pipeline/rag_pipeline.py:873-885`, bản streaming `pipeline/rag_pipeline.py:1254-1323`), truyền `complexity_subtype` để agent Planner-Executor biết dạng kế hoạch cần sinh ra (§4). Nếu `runtime.agent is None`, tự động rơi về RAG v2 (`pipeline/rag_pipeline.py:852`, `pipeline/rag_pipeline.py:1329-1333`) — hệ thống tắt agent vẫn xuống cấp mượt mà thay vì báo lỗi.

---

## 3. Routing domain/intent (`QueryRouter` + `DomainClassifier`) — chọn collection nào để tìm

Router này trả lời một **câu hỏi khác** với `ComplexityRouter`: không phải "canned/RAG/agent" mà là "câu hỏi này cần domain nào trong {ctdt, quydinh, kehoach, stsv}". Nó được gọi từ ba nơi, mỗi nơi có ngữ nghĩa lịch sử/cache khác nhau:

| Nơi gọi | File:line | Có dùng lịch sử? | Mục đích |
|---|---|---|---|
| Tier 1 của `_decide_complexity` | `pipeline/rag_pipeline.py:1071` | Không | Chỉ đếm domain active (§2.2) |
| `_route_with_cache` | `pipeline/rag_pipeline.py:291-321` | Có | Chọn collection thật cho đường `simple`, có cache TTL 45s và Tier-3 fallback |
| `_reroute_reflected` | `pipeline/rag_pipeline.py:323-380` | Không (cố tình) | Route lại câu đã reflect (độc lập) để chọn domain bên trong `rag_flow`/`rag_flow_stream`, tránh rò rỉ ngữ cảnh lịch sử |

### 3.1 `QueryRouter.route()` (`query/router.py:151-173`)

Hai chế độ, chọn khi khởi tạo (`query/router.py:122-145`):

- **`"classifier"` (mặc định, chi phí API bằng 0)** — ủy quyền cho `DomainClassifier` (§3.2/§3.3).
- **`"llm"`** — gọi OpenAI few-shot dùng `ROUTER_SYSTEM_PROMPT` + `ROUTER_FEW_SHOT` (`query/prompts.py:7-38, 40-...`). Phản hồi là JSON `{"intent": ..., "domains": [...]}`, được parse phòng thủ trong `_parse_response` (`query/router.py:292-321`) với fallback `DEFAULT_INTENT = "rag"` khi parse lỗi.

### 3.2 `_route_classifier` — routing hai lượt (`query/router.py:179-245`)

**Lượt 1** luôn route câu hỏi thô (đã chuẩn hóa NFC, `_normalize_query_for_classification`, `query/router.py:34-46`) không kèm lịch sử — các câu hỏi tự đủ nghĩa như "điều kiện đạt học bổng" phải luôn route nhất quán bất kể chủ đề hội thoại trước đó.

**Lượt 2** chỉ chạy khi có `chat_history` **và** `raw_confidence < 0.65` (`_TWO_PASS_CONFIDENCE_THRESHOLD`, `query/router.py:58`) **và** câu hỏi ngắn (`< 8` từ, `_TWO_PASS_SHORT_QUERY_WORDS`, `query/router.py:59`). Nó route lại với ngữ cảnh lịch sử được ghép thêm qua `build_routing_input` (`query/router.py:70-104`) và giữ lại kết quả của lượt nào có confidence cao hơn.

Bản thân `build_routing_input` có thêm một chốt chặn: nếu câu hỏi `≥6` từ **và** không chứa đại từ chỉ định/hồi chỉ tiếng Việt (`_DEMONSTRATIVE_RE`: "này", "đó", "vậy", "kia", "đấy", …, `query/router.py:64-67`), nó được coi là tự đủ nghĩa và lịch sử *không* được ghép thêm ngay cả bên trong lệnh gọi `build_routing_input` của Lượt 2 — tránh rò rỉ ngữ cảnh cho những câu hỏi tình cờ hơi ngắn nhưng đã đầy đủ nghĩa.

Cửa sổ ngữ cảnh: **5** lượt hội thoại gần nhất (`_CONTEXT_WINDOW = 5`, `query/router.py:52`) — tăng từ 2 vì các câu hỏi đăng ký nhiều lượt thường nhắc lại một môn học đã đề cập từ 3-4 lượt trước.

Ghi log confidence: `logger.log` ở mức `WARNING` khi `confidence < 0.55`, gắn tag `[LOW_CONF]`, phục vụ mục đích xây dựng histogram phân bố confidence trong production (`query/router.py:225-237`).

### 3.3 `DomainClassifier` — classifier embedding hai tầng (`query/domain_classifier.py`)

#### 3.3.1 Lựa chọn thuật toán, cho từng tầng

Cả hai tầng đều là **mô hình tuyến tính trên embedding cố định (frozen)**, không phải transformer fine-tune:

- **Embedder**: `BGEm3Embedder` (`embedding/bge_m3.py:68-90`), bọc quanh `BAAI/bge-m3` (`DEFAULT_MODEL`, `embedding/bge_m3.py:77`) — một mô hình embedding câu đa ngôn ngữ (hỗ trợ tiếng Việt), vector dense 1024 chiều (`embedding/bge_m3.py:90`). Embedder được chia sẻ/tái sử dụng (truyền vào qua `DomainClassifier(embedder=...)`) thay vì tải lại mỗi lần khởi tạo classifier — `query/domain_classifier.py:71-90` chỉ lazy-load nếu không được truyền vào.
- **Tầng 1 (intent)**: `Pipeline(StandardScaler → LogisticRegression(C=0.5, solver="lbfgs", max_iter=1000))` bọc trong `CalibratedClassifierCV(..., cv=5, method="sigmoid")` (`query/domain_classifier.py:154-164`). Hồi quy logistic đa lớp thông thường (multinomial), không phải đa nhãn — cho ra một trong ba giá trị `{chitchat, rag, tool_search}` cho mỗi câu hỏi. `StandardScaler` là bắt buộc vì vector BGE-M3 thô có thể gây tràn số/chia cho 0 trong phép nhân ma trận nội bộ của `lbfgs` ở 1024 chiều (`query/domain_classifier.py:152-153`). `CalibratedClassifierCV` với 5-fold CV bọc quanh LR gốc để `predict_proba` cho ra một xác suất **thực sự đã hiệu chỉnh (calibrated)**, chứ không phải điểm sigmoid thô (thường quá tự tin) — chính con số confidence đã hiệu chỉnh này nuôi `_should_trigger_tier3` và `CONFIDENCE_THRESHOLD` ở các tầng downstream (§3.4, §3.5). Dùng CV thay vì tách riêng một tập validation để hiệu chỉnh giúp không lãng phí dữ liệu huấn luyện vốn đã không nhiều.
- **Tầng 2 (domain)**: `OneVsRestClassifier(Pipeline(StandardScaler → LogisticRegression(C=0.5, solver="lbfgs")))` (`query/domain_classifier.py:189-197`), chỉ huấn luyện **trên các mẫu mà nhãn Tầng 1 là `rag`**. Một classifier hồi quy logistic nhị phân độc lập cho mỗi domain (`ctdt`, `quydinh`, `kehoach`, `stsv`) — đây chính là điều làm cho đầu ra thực sự **đa nhãn (multi-label)**: một câu hỏi có thể kích hoạt đồng thời nhiều classifier nhị phân của nhiều domain (ví dụ `ctdt=0.951, quydinh=0.300`), khác với softmax vốn ép các xác suất phải cộng lại bằng 1 trong cùng một không gian nhãn duy nhất. Không có thêm bước hiệu chỉnh Platt/CV ở tầng này (`query/domain_classifier.py:13-14`) — đầu ra sigmoid của LR thường được đánh giá là đã đủ hiệu chỉnh hợp lý cho các bài toán nhị phân gần cân bằng này.
- **Vì sao tách hai tầng thay vì một classifier duy nhất cho 6 nhãn** (`query/domain_classifier.py:16-21`): phiên bản trước dùng một `OneVsRestClassifier` duy nhất cho cả 6 nhãn cùng lúc, và gặp vấn đề vì tỉ lệ nền thấp của `tool_search` (~12% dữ liệu) kéo xác suất đã hiệu chỉnh của nó xuống dưới ngưỡng cắt non-RAG của router gần như mọi lúc — F1 = 0% trong thực tế. Việc tách intent khỏi domain giúp mỗi classifier con có một bài toán tập trung, cân bằng lớp tốt hơn.
- **Lưu trữ (persistence)**: `DomainClassifier.save()`/`.load()` (`query/domain_classifier.py:336-379`) tuần tự hóa `{intent_clf, domain_clf, mlb, _format: "two_stage_v3"}` bằng `joblib` vào `query/models/domain_classifier.joblib` (`_DEFAULT_MODEL_PATH`, `query/domain_classifier.py:45-46`). `load()` raise `ValueError` với bất kỳ định dạng model cũ (single-model) nào thay vì âm thầm load sai, buộc phải retrain lại tường minh (`query/domain_classifier.py:355-377`).

Các ngưỡng quan trọng: `MULTI_LABEL_THRESHOLD = 0.35` (`query/domain_classifier.py:49`) — ngưỡng xác suất Tầng 2 để một domain được coi là "active"; nếu không domain nào vượt ngưỡng, domain có xác suất cao nhất (argmax) vẫn được ép đưa vào (`query/domain_classifier.py:316-317`) để `domains` không bao giờ rỗng với một câu hỏi có intent RAG. `LOW_CONFIDENCE_CEILING = 0.55` (`query/domain_classifier.py:53`) là ngưỡng chỉ mang tính ghi chú, tương ứng khái niệm với `_LLM_FALLBACK_THRESHOLD` trong `rag_helpers.py` (§3.4) — được giữ lại trong module classifier để dễ tra cứu, nhưng giá trị thực sự dùng lấy từ `pipeline/rag_helpers.py:15`.

#### 3.3.2 Gán nhãn (Labeling) — nhãn đến từ đâu và bằng cách nào

**Không có việc gán nhãn online/tự động** — classifier được huấn luyện offline trên một bộ dữ liệu tĩnh, được biên soạn thủ công trong `query/training_data.py`, và được retrain bằng cách chạy lại `python -m query.train_classifier` (`query/train_classifier.py`) mỗi khi bộ dữ liệu đó thay đổi. Không có vòng lặp active-learning nào tự động đưa câu hỏi production thực tế trở lại tập huấn luyện.

`query/training_data.py` định nghĩa ba khối dữ liệu viết tay, đều là các tuple `(nội_dung_câu_hỏi, nhãn_hoặc_danh_sách_nhãn)`, được gộp lại bởi `get_training_data()` (`query/training_data.py:1836-1848`):

| Khối | File:line | Kích thước (ước lượng) | Dạng nhãn | Mục đích |
|---|---|---|---|---|
| `TRAINING_DATA` | `query/training_data.py:42-519` | ~408 dòng | một nhãn (`str`) | Ví dụ đơn-domain cơ bản, viết tay cho từng nhãn, bao phủ các cách diễn đạt tiếng Việt tự nhiên (trang trọng lẫn kiểu gõ tắt/mobile) cho cả 6 nhãn. |
| `HARD_NEGATIVE_DATA` | `query/training_data.py:525-845` | ~158 dòng | một nhãn (`str`) | Các trường hợp biên (boundary case) được chọn riêng vì chúng *trông giống* domain này nhưng *thực chất* thuộc domain khác — ví dụ "Học bổng kỳ này nộp đơn ở đâu?" là `stsv` (thủ tục), không phải `quydinh` (quy định điều kiện), dù cả hai đều nhắc "học bổng". Comment tại `query/training_data.py:522-524` nêu rõ mục đích: mài sắc ranh giới quyết định đúng tại những chỗ va chạm từ khóa bề mặt vốn dễ bị phân loại sai. |
| `MULTI_LABEL_DATA` | `query/training_data.py:848-1833` | ~235 dòng | danh sách nhãn (`List[str]`), thứ tự chính→phụ | Các câu hỏi thực sự trải rộng ≥2 domain (ví dụ "Ngành CNTT cần bao nhiêu tín chỉ và điều kiện tốt nghiệp ra sao?" → `[ctdt, quydinh]`). Một khối con lớn (từ khoảng `query/training_data.py:1700` trở đi) là tập hợp dày đặc các câu hỏi thủ tục thi thực tế ("thi trắc nghiệm trực tuyến tại Bách khoa…") trải rộng `kehoach`+`quydinh`(+`stsv`), phản ánh một mảng mà classifier từng bao phủ thiếu. |

`get_training_data()` bọc mỗi tuple một-nhãn thành danh sách một phần tử để `DomainClassifier.train()` (`query/domain_classifier.py:96-258`) luôn nhận được cùng một dạng thống nhất `List[Tuple[str, List[str]]]`, sau đó nội bộ suy ra nhãn intent Tầng 1 cho từng mẫu là `"rag"` nếu bất kỳ nhãn nào của nó nằm trong `RAG_LABELS = {ctdt, quydinh, kehoach, stsv}` (`query/training_data.py:37`), ngược lại dùng chính nhãn phi-RAG duy nhất của mẫu đó (`query/domain_classifier.py:121-124`).

Bản thân các nhãn (`query/training_data.py:20-37`) là một tập cố định, đóng, được xác định theo các mảng nghiệp vụ của chatbot trường đại học — không có bước tự khám phá taxonomy; 6 nhãn được chọn sẵn từ đầu để khớp với 4 collection Qdrant/ES thật (`ctdt`/`quydinh`/`kehoach`/`stsv`) cộng với 2 intent phi-retrieval (`chitchat`/`tool_search`). Mọi ví dụ huấn luyện đều được viết/biên soạn thủ công bởi người duy trì `training_data.py` — không có crowd-sourcing, không có pipeline sinh dữ liệu tổng hợp bằng LLM, và không có cơ chế tự động chuyển log production thành ví dụ có nhãn xuất hiện trong file này.

Quy trình huấn luyện (`query/train_classifier.py:20-92`):
1. Nạp toàn bộ ~800 dòng dữ liệu gộp qua `get_training_data()`.
2. Embed mỗi câu hỏi bằng `BGEm3Embedder` (dùng một instance chung).
3. `DomainClassifier.train(data, test_size=0.2, val_size=0.15, random_state=42)` (`query/domain_classifier.py:96-258`) — tách train/test theo phân tầng (stratified) dựa trên nhãn intent suy ra (`train_test_split(..., stratify=intent_labels)`, `query/domain_classifier.py:130-136`) để các lớp nhỏ như `tool_search`/`chitchat` không bị thiếu hụt ngẫu nhiên ở bất kỳ tập nào; fit Tầng 1 trên toàn bộ tập train, sau đó fit Tầng 2 chỉ trên các dòng có nhãn `rag` của tập train.
4. In ra `classification_report` cho cả hai tầng (độ chính xác intent Tầng 1, precision/recall/F1 theo từng domain của Tầng 2, và `samples avg` F1 làm chỉ số đa nhãn chính) rồi lưu model qua `.save()`.
5. Chạy một danh sách câu hỏi mẫu cố định, chọn lọc thủ công (bao gồm đúng các trường hợp hard-negative) và in ra dự đoán thực tế để con người tự kiểm tra bằng mắt trước khi tin tưởng model mới (`query/train_classifier.py:54-88`) — **không có cổng pass/fail tự động** ở bước này, chỉ có kiểm tra thủ công bởi con người.

Kết quả chung: đây là một **bộ dữ liệu có nhãn tĩnh, được cập nhật thủ công theo phiên bản**, không phải một hệ thống học liên tục — muốn cải thiện độ chính xác của classifier trong production đồng nghĩa với việc ai đó phát hiện một câu hỏi bị route sai, viết thêm một ví dụ có nhãn thủ công mới (thường là hard negative nếu đó là va chạm ở ranh giới), rồi chạy lại script huấn luyện — đây cũng là cách các lỗi được ghi trong `ARCHITECTURE.md` của codebase này được sửa (đối chiếu với việc gỡ bỏ regex guard tại `retrieval/collection_selector.py:106-114`, §3.5 bên dưới — nguyên tắc chung xuyên suốt codebase này là "để classifier tự học từ dữ liệu" thay vì "hard-code luật thủ công").

### 3.4 Tier-3 — LLM fallback cho domain (`_should_trigger_tier3`, `pipeline/rag_helpers.py:25-55`; `RAGPipeline._llm_domain_classify`, `pipeline/rag_pipeline.py:891-972`)

Đây là **một escalation tách biệt khỏi các Tier 0-2 của complexity** — nó sửa vấn đề phân loại *domain* có confidence thấp, không liên quan đến việc phân tầng độ phức tạp. Được kích hoạt bên trong `_route_with_cache` (`pipeline/rag_pipeline.py:313-316`) và `_reroute_reflected` (`pipeline/rag_pipeline.py:372-373`), **trước khi** kết quả được cache, để một lần cache-hit sẽ tái sử dụng routing đã được làm giàu thay vì phải gọi lại lệnh LLM ~12s mỗi lần lặp lại.

Logic cổng `_should_trigger_tier3` (`pipeline/rag_helpers.py:25-55`):
```
nếu confidence không phải None và confidence >= 0.55 (_LLM_FALLBACK_THRESHOLD):
    bỏ qua                                    # đã được phân loại đủ tự tin
nếu khoảng cách xác suất top-1 và top-2 >= 0.25 (_TIER3_DOMINANT_DOMAIN_MARGIN):
    bỏ qua                                    # ví dụ kehoach=0.531, ctdt=0.180 → khoảng cách 0.351 → bỏ qua
ngược lại:
    kích hoạt lệnh gọi LLM Tier-3
```
Việc kiểm tra `confidence is not None` (thay vì `confidence or 1.0`) là cố ý (`pipeline/rag_helpers.py:34-40`) — chế độ LLM router hợp lệ trả về `confidence=None`, và nếu coi giá trị đó là 1.0 sẽ âm thầm vô hiệu hóa Tier-3 đúng vào lúc một phân loại LLM confidence thấp thực sự cần một ý kiến thứ hai nhất. Chỉ bỏ qua khi có điểm số cao thực sự bằng số.

`_llm_domain_classify` (`pipeline/rag_pipeline.py:891-972`) dùng prompt `DOMAIN_CLASSIFICATION_PROMPT` (`query/prompts.py:367-392`), truyền kèm 2 lượt hội thoại gần nhất làm ngữ cảnh. Ánh xạ confidence dạng chuỗi của LLM (`"high"/"medium"/"low"`) sang số `{0.85, 0.65, 0.45}` (`pipeline/rag_pipeline.py:939-941`). Khi có bất kỳ lỗi parse/LLM nào, hoặc nếu LLM trả về domain không hợp lệ, hàm này sẽ **giữ nguyên kết quả classifier gốc** (`pipeline/rag_pipeline.py:945-951, 966-972`) — không bao giờ chặn câu trả lời. Có một lỗi lịch sử được ghi chú ngay trong code (`pipeline/rag_pipeline.py:928-931`): phiên bản trước dùng `raw.strip("```json").strip("```")`, vốn strip *tập ký tự* chứ không phải chuỗi con — một lỗi kinh điển khi dùng sai `str.strip` trong Python, âm thầm làm hỏng JSON hợp lệ và vô hiệu hóa Tier-3; đã được thay bằng cách trích xuất qua regex `\{.*\}`.

### 3.5 Chọn collection (`retrieval/collection_selector.py`)

Sau khi biết `domains`, `CollectionSelector.select()` (`retrieval/collection_selector.py:235-361`) ánh xạ domain sang collection Qdrant/ES qua `DOMAIN_TO_COLLECTIONS` (`retrieval/collection_selector.py:19-24`):

```
ctdt    → [ctdt]
quydinh → [quydinh, stsv]     # quy định ↔ hỗ trợ sinh viên có giao thoa
kehoach → [kehoach]
stsv    → [stsv, quydinh]     # hỗ trợ sinh viên ↔ quy định có giao thoa
```

- **Confidence cao** (`confidence ≥ CONFIDENCE_THRESHOLD = 0.55`, `retrieval/collection_selector.py:31`): tìm trên hợp (union) các collection đã map của tất cả domain active.
- **Confidence thấp** (`< 0.55`): mở rộng thêm bằng `MULTI_DOMAIN_FALLBACK = [quydinh, stsv, ctdt]` (`retrieval/collection_selector.py:29`), nối vào sau các domain active (vẫn được giữ lại), cộng thêm khả năng chèn `kehoach` qua `_should_add_kehoach_low_confidence` (`retrieval/collection_selector.py:72-103`) — kích hoạt khi xác suất của kehoach cách domain top không quá `0.10` (`KEHOACH_CLOSE_PROBABILITY_MARGIN`, `retrieval/collection_selector.py:32`), hoặc khi có tín hiệu định tuyến về kehoach (freshness/schedule/deadline/announcement) và không có domain nào khác vừa trội rõ ràng vừa vượt xa kehoach.
- **Không giải quyết được domain nào**: tìm trên `ALL_COLLECTIONS` (`retrieval/collection_selector.py:26`).

**Bước mở rộng cuối cùng** — `augment_collections_for_query()` (`retrieval/collection_selector.py:142-206`) — luôn chạy sau các bước trên, mở rộng (không bao giờ thu hẹp) danh sách collection dựa trên `QuerySignals`, theo cách entity-agnostic:

| Tín hiệu | Hiệu ứng |
|---|---|
| `_is_foreign_language_policy_lookup` (`retrieval/collection_selector.py:117-139`: mã ngoại ngữ như `FL1032`, hoặc khóa K65-K70 đi kèm gợi ý ngoại ngữ/IELTS/TOEIC/VSTEP) | thêm `quydinh` vào đầu |
| `eligibility_check HOẶC table_lookup HOẶC exact_policy_lookup` | thêm `quydinh` vào đầu |
| `procedural_support` | thêm `stsv` vào cuối |
| `multi_domain VÀ eligibility_check` | thêm `ctdt` vào cuối |
| `curriculum_semester_intent` (và không có tín hiệu khi-nào/lịch/deadline/thông báo/freshness) | thêm `ctdt` vào đầu (vị trí học kỳ nằm trong chương trình học, không phải lịch đăng ký) |
| `_has_kehoach_routing_intent` (freshness/schedule/deadline/announcement) và không phải tra cứu học kỳ trong chương trình | thêm `kehoach` vào cuối |

Lưu ý về việc gỡ bỏ có chủ đích (`retrieval/collection_selector.py:106-114`, ghi ngày 2026-06-21): một guard regex cũ tên `_is_ctdt_course_lookup` từng *chặn* việc thêm `quydinh` cho các câu hỏi tín chỉ/môn học (kèm theo các ngoại lệ chỉnh tay cho học phí/ECTS) đã được đo lường là **có hại ròng (net-harmful)** và bị gỡ bỏ — classifier domain v2 đã tự phân biệt được ctdt vs quydinh, và việc gỡ guard này giúp recall của quydinh tăng từ 0.944→0.952 và recall tổng thể tăng từ 0.865→0.870 mà không gây hồi quy trên các trường hợp học-phí/ECTS đã được kiểm chọn. Điều này được ghi lại trong repo như một anti-pattern cần tránh tái lập: đừng liệt kê tay các ngoại lệ theo thực thể khi classifier đã tự tổng quát hóa được.

---

## 4. Thực thi đường complex (`ReActAgent`) — `complex_subtype` định hướng planner như thế nào

`RAGPipeline.query_agent()` truyền `complexity_subtype` xuống `ReActAgent.run()` (`agent/react_agent.py:182`). Nếu không được truyền vào, agent sẽ tự suy luận lại qua `ComplexityRouter.route()` tại `pipeline/rag_pipeline.py:601` (dùng cho trường hợp gọi trực tiếp `query_agent` mà bỏ qua `_decide_complexity`).

`_subtype_hint()` (`agent/react_agent.py:258-276`) biến subtype thành một chỉ dẫn ngắn bằng tiếng Việt, thêm vào prompt của planner (`agent/react_agent.py:294-309`):

- `"comparison"` → "tách thành các step riêng cho từng đối tượng (ngành/khóa), cùng collection, khác major_hint/cohort_hint."
- `"multi_source"` → "sinh step cho từng khía cạnh và collection liên quan."
- `"general"` / `None` → không thêm chỉ dẫn nào.

Cách này thay thế một bước LLM "decompose" (tách câu hỏi) riêng biệt trước đây, với chi phí LLM phát sinh bằng 0 — cùng một lệnh gọi planner duy nhất giờ vừa tách câu hỏi vừa route từng bước con vào đúng collection, được định hướng bởi gợi ý subtype (`agent/react_agent.py:87-89`, `agent/MODULE.md:68`).

---

## 5. Ví dụ trace đầy đủ — "Điều kiện tốt nghiệp của IT-E6 là gì?"

1. `POST /chat` (`api/routes/chat.py:97`), `mode=auto`.
2. `query_v3` (`pipeline/rag_pipeline.py:798`) → reflection giữ nguyên phần lớn câu hỏi (đã tự đủ nghĩa) → `reflected_question`.
3. `_decide_complexity` (`pipeline/rag_pipeline.py:1044`):
   - Tier 0 (`ComplexityRouter.route`): không pattern nào trong số chitchat/lịch thi/1-sự-thật/cá nhân-điều kiện/so sánh khớp (không có đại từ cá nhân, không so sánh tường minh) → rơi xuống `"unknown"`.
   - Tier 1: `QueryRouter.route` (chế độ classifier) trên câu đã reflect → ví dụ `domains={ctdt: 0.951, quydinh: 0.300}`. `_count_active_domains` chỉ đếm `ctdt` (quydinh dưới ngưỡng `MULTI_LABEL_THRESHOLD` 0.35) → `spans_two_collections=False`. Nhưng `analyze_query_signals` đặt `multi_domain=True` (graduation_rule: "tốt nghiệp"+"điều kiện" và ngữ cảnh chương trình) → điều kiện OR được thỏa → tiếp tục sang Tier 2 thay vì trả về `simple`.
   - Tier 2: `_classify_complexity_llm` với `COMPLEXITY_CLASSIFICATION_PROMPT` → khớp gần như nguyên văn với ví dụ mẫu có sẵn trong prompt → `{"complexity": "complex", "subtype": "multi_source"}`.
4. `_decide_complexity` trả về `("complex", "multi_source")`.
5. `query_agent()` (`pipeline/rag_pipeline.py:873`) được gọi với `complexity_subtype="multi_source"`.
6. `ReActAgent._planner_node` thêm gợi ý "nhiều nguồn" (`agent/react_agent.py:271-275`), planner sinh ra các step riêng cho `quydinh` (quy định ngoại ngữ/CPA/kỷ luật) và `ctdt` (tín chỉ/môn bắt buộc của IT-E6).

---

## 6. Bảng tra cứu ngưỡng (toàn bộ hằng số quan trọng, gom về một chỗ)

| Hằng số | Giá trị | File:line | Ý nghĩa |
|---|---|---|---|
| `MULTI_LABEL_THRESHOLD` | 0.35 | `query/domain_classifier.py:49` | Ngưỡng xác suất Tầng 2 để một domain được coi là "active" |
| `LOW_CONFIDENCE_CEILING` | 0.55 | `query/domain_classifier.py:53` | Ngưỡng chỉ mang tính ghi chú, phản chiếu `_LLM_FALLBACK_THRESHOLD` |
| `CONFIDENCE_THRESHOLD` | 0.55 | `retrieval/collection_selector.py:31` | Dưới ngưỡng này, `CollectionSelector` mở rộng bằng collection fallback |
| `KEHOACH_CLOSE_PROBABILITY_MARGIN` | 0.10 | `retrieval/collection_selector.py:32` | kehoach được coi là "gần sát top" trong khoảng này |
| `_LLM_FALLBACK_THRESHOLD` | 0.55 | `pipeline/rag_helpers.py:15` | Dưới ngưỡng này, Tier-3 LLM domain fallback có thể được kích hoạt |
| `_TIER3_DOMINANT_DOMAIN_MARGIN` | 0.25 | `pipeline/rag_helpers.py:22` | Khoảng cách top-2 vượt qua mức này thì bỏ qua Tier-3 dù confidence thấp |
| `_TWO_PASS_CONFIDENCE_THRESHOLD` | 0.65 | `query/router.py:58` | Dưới ngưỡng này (+ câu hỏi ngắn), Lượt 2 route lại có bổ sung lịch sử sẽ chạy |
| `_TWO_PASS_SHORT_QUERY_WORDS` | 8 | `query/router.py:59` | Câu hỏi phải ngắn hơn số từ này để Lượt 2 kích hoạt |
| `_CONTEXT_WINDOW` | 5 lượt | `query/router.py:52` | Số lượt lịch sử được ghép thêm làm ngữ cảnh cho classifier |
| `_ROUTE_CACHE_TTL_SEC` | 45s | `pipeline/rag_helpers.py:59` | TTL của `_route_with_cache` |
| `_ROUTE_CACHE_MAX_SIZE` | 256 | `pipeline/rag_helpers.py:60` | Giới hạn LRU của route cache |
| Heuristic độ phức tạp theo số từ | > 30 từ + liên từ đa chủ đề | `query/complexity_router.py:398-415` | Fallback cấu trúc của Tier-0 |

---

## 7. Bản đồ độ phủ test (để trace hành vi mong đợi)

| File test | Bao phủ |
|---|---|
| `tests/test_router.py` | Các trường hợp biên của `QueryRouter`/routing domain, kể cả câu hỏi tốt nghiệp/quy tắc chương trình phải chuyển giao cho các tầng ML |
| `tests/test_complexity_tiers.py` | Cách Tier-1/Tier-2 kết hợp trong `_decide_complexity`, kể cả việc subtype không hợp lệ mặc định thành `multi_source` |
| `tests/test_routing_fixes.py` | Bộ test hồi quy cho các lỗi routing lịch sử cụ thể |
| `tests/test_complexity_router_exam.py` | Cổng tính cụ thể của đường tắt lịch thi (câu hỏi thi route complex, câu hỏi lịch thường thì không) |
| `tests/test_routing_edge_cases.py` | Hồi quy cho trường hợp biên "khoảng trống khả năng cá nhân" và các trường hợp khác |

---

## 8. Các nguyên tắc thiết kế cốt lõi xuyên suốt codebase

- **Entity-agnostic theo thiết kế**: mọi quyết định routing đều dùng hoặc (a) phân bố xác suất của một classifier đã huấn luyện, hoặc (b) một tín hiệu ngôn ngữ tổng quát (đại từ cá nhân, cách diễn đạt điều kiện, regex ngữ cảnh chương trình) — không bao giờ liệt kê tay ngành/chương trình/khóa cụ thể. Hai lần gỡ bỏ được ghi lại trong code (`retrieval/collection_selector.py:106-114`, comment tại `pipeline/rag_pipeline.py:337-345`) chỉ đích danh các guard regex theo-thực-thể trước đây là anti-pattern, đã được đo lường là có hại ròng và bị xóa để thay bằng logic dựa trên classifier/tín hiệu.
- **Cascade rẻ nhất trước**: regex (Tier 0, ~0ms) → classifier embedding (Tier 1, ~10-50ms) → LLM phán xử (Tier 2/3, ~12s) — mỗi tầng chỉ chạy khi tầng trước đó không quyết định được, giới hạn chi phí LLM chỉ ở một phần nhỏ traffic.
- **Fail-open, không bao giờ fail-closed**: mọi tầng dựa vào LLM (Tier 2 phán xử độ phức tạp, Tier 3 fallback domain) đều bắt exception và mặc định về kết quả rẻ hơn/an toàn hơn (`simple`, hoặc "giữ nguyên kết quả classifier hiện có") thay vì raise lỗi — một lệnh gọi LLM hỏng chỉ làm giảm chất lượng, không bao giờ làm mất khả năng phục vụ (availability).
- **Route theo câu đã reflect để tránh rò rỉ ngữ cảnh**: cả Tier 1 của complexity lẫn `_reroute_reflected` đều cố tình bỏ qua `chat_history` khi route câu hỏi đã reflect (đã tự đủ nghĩa), để một cuộc hội thoại trước đó nặng về một chủ đề không thể làm lệch việc chọn domain cho một câu hỏi follow-up không liên quan.
