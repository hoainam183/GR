# Module: `query` — Query Understanding Layer

## Tổng quan

Module `query` chịu trách nhiệm **hiểu và chuẩn bị câu hỏi** của người dùng trước khi đưa vào retrieval. Bao gồm 3 nhiệm vụ chính: (1) phân loại intent/domain bằng ML classifier, (2) rewrite query bằng LLM (reflection), và (3) trích xuất entity (major, cohort, course code…) từ query + context.

---

## Cấu trúc file

```
query/
├── router.py            # QueryRouter — phân loại intent + domain
├── domain_classifier.py # DomainClassifier — embedding-based ML classifier
├── reflection.py        # QueryReflector — LLM-based query rewrite
├── prompts.py           # System prompts cho reflection và domain classification
├── training_data.py     # Dữ liệu training cho DomainClassifier (38KB, ~500+ examples)
├── train_classifier.py  # Script huấn luyện và lưu model classifier
└── models/              # Thư mục lưu model classifier (.joblib)
```

---

## Nhiệm vụ chi tiết

### `router.py` — `QueryRouter`

**Nhiệm vụ:** Phân loại câu hỏi thành `intent` + `domain`.

**2 chế độ hoạt động:**

| Mode | Cơ chế | Latency | Chi phí |
|---|---|---|---|
| `"classifier"` | Embedding BGE-M3 + LogisticRegression | 10-50ms | $0 |
| `"llm"` | OpenAI GPT few-shot JSON | 200-800ms | $$ |

**Output format:**
```json
{
  "intent": "rag",
  "domain": "ctdt",
  "domains": ["ctdt", "quydinh"],
  "confidence": 0.87,
  "probabilities": {"ctdt": 0.72, "quydinh": 0.15, "kehoach": 0.08, "stsv": 0.05}
}
```

**Context-aware routing:** Với follow-up queries ngắn (< 6 words), router ghép thêm `[CTX: ...]` từ 5 turn lịch sử gần nhất trước khi classify.

---

### `domain_classifier.py` — `DomainClassifier`

**Nhiệm vụ:** Predict intent và domain bằng embedding similarity.

**Architecture:**
```
Query → BGE-M3 embedding (1024-dim) → LogisticRegression → {intent, domain, confidence}
```

**Labels:**
- `chitchat` — câu hỏi xã giao
- `ctdt` — chương trình đào tạo, môn học
- `quydinh` — quy định học vụ, học bổng, kỷ luật
- `kehoach` — kế hoạch học kỳ, lịch thi, deadline
- `stsv` — hỗ trợ sinh viên, biểu mẫu, giấy tờ

**Confidence calibration:**
- confidence < 0.55 → trigger Tier-3 LLM domain fallback
- confidence ≥ 0.55 → sử dụng trực tiếp

**Training:** File `training_data.py` chứa ~500+ câu hỏi mẫu đã gán nhãn. Chạy `train_classifier.py` để tạo lại model `.joblib`.

---

### `reflection.py` — `QueryReflector`

**Nhiệm vụ:** Rewrite và làm rõ câu hỏi của người dùng trước khi embedding.

**Tại sao cần reflection?**
- Người dùng hỏi mơ hồ: "môn đó điều kiện là gì?" → không rõ môn nào
- Câu hỏi với đại từ: "ngành của tôi" → cần resolve thành tên ngành cụ thể
- Follow-up: "còn quy định nào nữa không?" → cần biết context trước đó

**Cơ chế hoạt động:**
```
1. Build profile note từ user_context (authenticated) hoặc history (regex)
2. Gọi LLM với REWRITE_SYSTEM_PROMPT + REWRITE_WITH_HISTORY_TEMPLATE
3. Parse output → rewritten query
4. Guardrail: nếu vẫn còn "ngành của tôi" → replace deterministically
5. Extract entities: major_code, cohort, course_code, semester
```

**LLM Provider:** Gemini (default), LM Studio, Ollama, hoặc OpenAI
**Model default:** `gemini-2.0-flash`
**Max tokens:** 256 (chỉ cần output ngắn)

**Retry logic:** 3 lần với exponential backoff (2s, 4s) khi rate-limit.

---

### Entity Extraction (`_extract_entities()`)

**Không cần LLM** — dùng regex patterns để trích xuất:

| Entity | Pattern ví dụ | Ưu tiên |
|---|---|---|
| `major_code` | IT-E6, IT-E15, MI-E10 | Query > user_context > history |
| `major_name` | Công nghệ thông tin Việt-Nhật | Tra từ MAJOR_CODE_TO_NAME |
| `cohort` | K65, K70, Khóa 66 | Query > user_context > history |
| `year_of_study` | năm 3, năm thứ 2 | Query > history |
| `course_code` | IT4062E, MA1007 | Query > history |
| `semester` | 20241, HK1, học kỳ hè | Query > history |
| `academic_year` | 2024-2025, 20242 | Query > history |

---

### `prompts.py`

Chứa các system prompts:
- `REWRITE_SYSTEM_PROMPT` — hướng dẫn LLM cách rewrite query
- `REWRITE_WITH_HISTORY_TEMPLATE` — template với lịch sử hội thoại
- `REWRITE_NO_HISTORY_TEMPLATE` — template không có lịch sử
- `DOMAIN_CLASSIFICATION_PROMPT` — prompt cho Tier-3 LLM domain fallback
- `ROUTER_SYSTEM_PROMPT` + `ROUTER_FEW_SHOT` — cho LLM router mode

---

## Luồng xử lý tổng hợp

```
Raw query + history + user_context
        │
        ▼
QueryRouter.route()
        │  (embedding classifier, ~10-50ms)
        ▼
    intent = "rag" OR "chitchat"
    domain = "ctdt" | "quydinh" | "kehoach" | "stsv"
    confidence = 0.0 → 1.0
        │
        ├── confidence < 0.55 → Tier-3 LLM classify (~500ms)
        │
        ▼
QueryReflector.reflect()
        │  (LLM call, ~500-2000ms)
        ▼
    rewritten_query (self-contained, specific)
    entities: {major_code, cohort, course_code, ...}
```

---

## LLM involvement

| Function | LLM | Latency |
|---|---|---|
| `QueryRouter` (classifier mode) | ❌ Không dùng LLM | 10-50ms |
| `QueryRouter` (llm mode) | ✅ OpenAI GPT | 200-800ms |
| `_llm_domain_classify` (Tier-3) | ✅ Gemini chat | 300-800ms |
| `QueryReflector.reflect()` | ✅ Gemini flash | **500-2000ms** |
| `_extract_entities()` | ❌ Không dùng LLM | <1ms |

---

## Latency contribution

| Component | Thời gian |
|---|---|
| Domain classifier (embedding) | 10-50ms |
| Query reflection (LLM) | **500-2000ms** ⚠️ |
| Entity extraction (regex) | <1ms |
| **Tổng module query** | **~510-2050ms** |
