# Đánh giá hệ thống Router & Domain Classifier

> **Phạm vi:** `query/router.py`, `query/domain_classifier.py`, `query/reflection.py`, `query/training_data.py`
> **Dữ liệu tham chiếu:** Thống kê 4.014+ câu hỏi thực tế của sinh viên

---

## 1. Tóm tắt điểm mạnh

Kiến trúc hai tầng (two-stage) hiện tại đã giải quyết tốt vấn đề `tool_search = 0% F1` của v2. Các điểm đáng ghi nhận:

- **Stage 1/Stage 2 tách biệt** tránh xung đột prior giữa `chitchat`/`tool_search` và các nhãn RAG domain.
- **`CalibratedClassifierCV(cv=5)`** tận dụng toàn bộ tập train nhỏ thay vì phân tách thêm val split — phù hợp với quy mô dữ liệu hiện tại.
- **Multi-label inference** với `MULTI_LABEL_THRESHOLD = 0.35` + fallback argmax đảm bảo luôn có ít nhất một domain được trả về.
- **`build_routing_input()`** prepend 2 turns gần nhất giúp follow-up queries được ngữ cảnh hoá.
- **Reflection pipeline** với ưu tiên rõ ràng (USER_PROFILE > CHAT_HISTORY > query) và guardrail `_enforce_major_reference_rewrite()` xử lý tốt các tham chiếu mơ hồ.

---

## 2. Phân tích lệch pha: Nhãn hệ thống vs. Phân phối thực tế

Đây là vấn đề cốt lõi nhất. Taxonomy 4 nhãn hiện tại (`ctdt`, `quydinh`, `kehoach`, `stsv`) **không ánh xạ được các chủ đề chiếm thể tích lớn nhất**.

### 2.1. Bản đồ ánh xạ chủ đề thực tế → nhãn hiện tại

| Chủ đề thực tế | Tỉ lệ | Nhãn hiện tại | Vấn đề ánh xạ |
|---|---|---|---|
| Đăng ký học phần / Lịch học | **74.6%** | `kehoach` + `ctdt` | **Tách nhãn yếu** — WHEN đăng ký → `kehoach`, HOW/WHAT đăng ký → `ctdt`, điều kiện → `quydinh` |
| Chương trình đào tạo | 42.4% | `ctdt` | ✓ Khớp tốt |
| Kỹ sư / Cử nhân (loại bằng) | 36.9% | `ctdt` | ✓ Khớp — nhưng không phân biệt được bằng 4/4.5/5 năm |
| **Đồ án / Project / ĐATN** | **36.1%** | `ctdt` (mờ) | ⚠️ **Không có nhãn riêng** — ĐATN là chủ đề có đặc thù retrieval rất khác `ctdt` thông thường |
| Tín chỉ | 35.9% | `ctdt` + `quydinh` | Ranh giới mờ giữa "môn này mấy TC?" (`ctdt`) và "tối đa bao nhiêu TC/kỳ?" (`quydinh`) |
| **Học phần tương đương / Thay thế** | **32.2%** | `ctdt` (mờ) | ⚠️ **Không có nhãn riêng** — query dạng này cần tra bảng chéo, retrieval logic khác hẳn |
| Giấy tờ / Thủ tục | 17.6% | `stsv` | ✓ Khớp |
| Điểm số / GPA / CPA | 16.9% | `quydinh` | ✓ Khớp — nhưng thiếu mẫu trong training |
| Thực tập | 9.6% | `ctdt` + `stsv` + `kehoach` | Ba nhãn đều có liên quan, không nhãn nào chủ đạo |

### 2.2. Hai chủ đề cần nhãn riêng

**Đồ án / ĐATN (36.1%)** — Queries dạng này có pattern retrieval đặc thù:
```
"Điều kiện đăng ký đồ án tốt nghiệp" → quydinh + ctdt
"Lịch nộp đồ án kỳ này" → kehoach
"Thủ tục nộp đề cương đồ án" → stsv
"Đồ án 10 hay 12 tín chỉ?" → ctdt
```
Hiện tại router có thể phân loại đúng intent = `rag` nhưng domain sẽ không nhất quán, dẫn đến retrieval từ collection sai.

**Học phần tương đương / Thay thế (32.2%)** — Loại query này cần tra cứu bảng ánh xạ chuyên biệt, không phải tìm kiếm văn bản thông thường. Router hiện không thể phân biệt để kích hoạt tool phù hợp.

---

## 3. Vấn đề nghiêm trọng trong Training Data

### 3.1. Dữ liệu huấn luyện không phản ánh phân phối thực tế

Phân phối nhãn trong `training_data.py`:

| Nhãn | Số mẫu đơn | Tỉ lệ trong training | Tỉ lệ thực tế (proxy) |
|---|---|---|---|
| `chitchat` | ~50 | ~18% | thấp |
| `tool_search` | ~30 | ~11% | thấp |
| `ctdt` | ~60 | ~22% | **~42%** (Chương trình ĐT) |
| `quydinh` | ~57 | ~21% | trung bình |
| `kehoach` | ~50 | ~18% | **~74%** (Đăng ký / Lịch) |
| `stsv` | ~50 | ~18% | ~17% |

Nhãn `kehoach` — chiếm 74.6% câu hỏi thực tế — chỉ được đại diện bởi 18% training data. Đây là **distribution shift nghiêm trọng** dẫn đến:
- Classifier bị bias về `ctdt` khi nhận câu hỏi về đăng ký học phần (vì "đăng ký môn" giao thoa cả hai).
- Precision của `kehoach` thấp hơn thực tế cần thiết.

### 3.2. Thiếu mẫu cho các chủ đề thực tế quan trọng

Hiện tại trong `TRAINING_DATA` có rất ít (hoặc không có) mẫu cho:

| Chủ đề | Ước tính mẫu hiện có |
|---|---|
| Điểm số / GPA / CPA | ~5 mẫu (`quydinh`) |
| Học phần tương đương | 0 mẫu chuyên biệt |
| Đồ án / ĐATN | ~3–4 mẫu trong `ctdt` |
| Thực tập | ~4 mẫu rải rác |
| Thạc sĩ / Sau đại học | 2 mẫu |

### 3.3. Hard negatives chưa đủ cho ranh giới `kehoach` ↔ `ctdt`

```python
# Hiện có: 
("Đăng ký KTX ở đâu?", LABEL_STSV),         # kehoach-stsv ✓
("Lịch mở đăng ký KTX học kỳ tới", LABEL_KEHOACH)  # ✓

# Còn thiếu (ranh giới kehoach ↔ ctdt — chiếm 74% queries):
("Đăng ký IT4062E học kỳ này được không?", LABEL_KEHOACH),
("Môn IT4062E mở lớp kỳ nào?", LABEL_CTDT),
("Khi nào mở đăng ký môn Giải tích 1?", LABEL_KEHOACH),
("Giải tích 1 có bao nhiêu tín chỉ?", LABEL_CTDT),
```

---

## 4. Vấn đề kiến trúc Router

### 4.1. LLM Router mất thông tin domain

```python
# router.py — _route_llm()
return {
    "intent": intent,
    "domain": None,      # ← luôn None
    "domains": [],       # ← luôn rỗng
    "confidence": None,
}
```

Khi fallback sang LLM mode (hoặc khi dùng `mode="llm"` trực tiếp), pipeline downstream nhận được `domain=None`. Nếu `rag_pipeline` không handle trường hợp này thì sẽ query tất cả collections — vừa chậm, vừa tốn chi phí.

**Khuyến nghị:** LLM router cần trả về domain trong JSON response. Cập nhật `ROUTER_SYSTEM_PROMPT` và `ROUTER_FEW_SHOT` để bao gồm domain prediction:

```python
# Thay vì: {"intent": "rag"}
# Trả về:  {"intent": "rag", "domains": ["ctdt", "kehoach"]}
```

### 4.2. `_CONTEXT_WINDOW = 2` có thể quá nhỏ

```python
_CONTEXT_WINDOW = 2  # router.py dòng ~30
```

Với các câu hỏi multi-turn phổ biến về đăng ký học phần (74.6%), hội thoại thường có cấu trúc:
```
Turn 1: "Môn Giải tích 1 mã là gì?"         ← thiết lập context
Turn 2: "Tiên quyết của nó là gì?"           ← resolve "nó"
Turn 3: "Còn môn thay thế?"                  ← cần cả Turn 1 + 2
Turn 4: "Kỳ này còn chỗ đăng ký không?"     ← cần Turn 1 (môn cụ thể)
```
Ở Turn 4 với `_CONTEXT_WINDOW = 2`, context chỉ chứa Turn 2 + 3 — mất thông tin về môn học từ Turn 1.

**Khuyến nghị:** Tăng lên 4–6, hoặc implement sliding window có weighted recency.

### 4.3. Không có monitoring cho confidence distribution

```python
LOW_CONFIDENCE_CEILING: float = 0.55  # domain_classifier.py
```

Không có logging/metrics nào ghi lại tỉ lệ queries rơi vào "low confidence" zone (`confidence < 0.55`) trong production. Nếu con số này cao (>20%), đây là dấu hiệu classifier đang extrapolate ngoài training distribution.

**Khuyến nghị:** Log `confidence` cho mọi prediction để có histogram phân phối sau 1 tuần production.

### 4.4. Threshold cứng chưa được validate trên dữ liệu thực

```python
MULTI_LABEL_THRESHOLD: float = 0.35
```

Con số 0.35 được chọn theo kinh nghiệm nhưng chưa có evidence là optimal trên phân phối câu hỏi thực (74.6% `kehoach`). Với skewed distribution, threshold tối ưu cho từng domain thường khác nhau.

**Khuyến nghị:** Sau khi có production logs, tìm per-domain threshold tối ưu bằng F1-maximization trên validation set thực.

---

## 5. Vấn đề trong Reflection Pipeline

### 5.1. Few-shot trong `REWRITE_SYSTEM_PROMPT` chỉ có 1 ví dụ

```python
REWRITE_SYSTEM_PROMPT = """...
VÍ DỤ FEW-SHOT:
USER_PROFILE: sinh viên ngành Công nghệ thông tin
CHAT_HISTORY: ...
CÂU HỎI HIỆN TẠI: Môn triết học ...
STANDALONE QUERY: Môn triết học Mác-Lênin trong ngành Công nghệ thông tin Việt Nhật...
"""
```

Chỉ 1 ví dụ cho toàn bộ 32.2% queries về "học phần tương đương/thay thế" và 36.1% về ĐATN — là những query type yêu cầu rewrite phức tạp nhất.

**Khuyến nghị:** Thêm 3–5 ví dụ covering các pattern:
- Học phần tương đương ("môn nào thay thế được môn này?")
- Đồ án với profile enrichment ("điều kiện làm ĐATN ngành của tôi")
- Follow-up với mã môn ("còn điều kiện tiên quyết?")

### 5.2. `_extract_entities()` bỏ qua mã môn học trong CHAT_HISTORY

```python
# reflection.py — _extract_entities()
mo = _COURSE_CODE_RE.search(query)   # ← chỉ search trong query hiện tại
if mo:
    entities["course_code"] = mo.group(1).upper()
```

Nếu sinh viên nhắc mã môn ở Turn 1 rồi hỏi follow-up ở Turn 3, `course_code` sẽ là `None` — mất thông tin quan trọng cho retrieval với metadata filter.

**Khuyến nghị:**

```python
# Tìm course_code trong query trước, sau đó tìm trong history
sources = [query] + [m.get("content", "") for m in (history or []) if m.get("role") == "user"]
for text in sources:
    mo = _COURSE_CODE_RE.search(text)
    if mo:
        entities["course_code"] = mo.group(1).upper()
        break
```

### 5.3. Thiếu entity extraction cho mã học kỳ và năm học

Queries về đăng ký học phần (74.6% thực tế) thường chứa:
- Học kỳ: "20241", "HK1 2024-2025", "học kỳ 2"
- Năm học: "2024-2025", "năm học này"

Không có entity nào capture được thông tin này trong `_extract_entities()`. Điều này làm giảm khả năng filter metadata khi retrieval các thông báo/lịch theo kỳ.

---

## 6. Roadmap cải thiện (ưu tiên)

### 🔴 Ưu tiên cao (ảnh hưởng trực tiếp đến accuracy)

**P1: Bổ sung training data phản ánh phân phối thực tế**

Cần ít nhất **100 mẫu mới** tập trung vào:
- `kehoach`: 40 mẫu về đăng ký học phần với nhiều biến thể ("còn slot không?", "khi nào mở?", "đăng ký được chưa?")
- Ranh giới `kehoach` ↔ `ctdt`: 20 hard negatives với mã môn cụ thể
- `ctdt` về ĐATN: 20 mẫu ("điều kiện đăng ký ĐATN", "số TC đồ án", "chọn giảng viên hướng dẫn")
- `ctdt` về học phần tương đương: 20 mẫu

**P2: Cập nhật LLM Router trả về domain**

```python
# prompts.py — ROUTER_SYSTEM_PROMPT
"""...(thêm)
Nếu intent là 'rag', bổ sung 'domains': list các domain liên quan.
Respond: {"intent": "rag", "domains": ["ctdt", "kehoach"]}
"""

# prompts.py — ROUTER_FEW_SHOT (cập nhật)
{"role": "user", "content": "Khi nào đăng ký Giải tích 1?"},
{"role": "assistant", "content": '{"intent": "rag", "domains": ["kehoach", "ctdt"]}'},
```

### 🟡 Ưu tiên trung bình (cải thiện chất lượng)

**P3: Fix `course_code` extraction trong history**

Xem code đề xuất tại mục 5.2.

**P4: Thêm entity `semester` và `academic_year`**

```python
_SEMESTER_RE = re.compile(
    r"\b(20\d{2}[12])\b"                   # "20241", "20242"
    r"|h[oọ]c\s*k[yỳ]\s*(\d)"              # "học kỳ 1"
    r"|semester\s*(\d)",
    re.IGNORECASE,
)
```

**P5: Tăng `_CONTEXT_WINDOW` từ 2 lên 4–6**

**P6: Bổ sung few-shot vào `REWRITE_SYSTEM_PROMPT`**

Thêm ít nhất 3 ví dụ mới: học phần tương đương, ĐATN, follow-up với mã môn.

### 🟢 Ưu tiên thấp (cải thiện dài hạn)

**P7: Per-domain threshold tuning**

Sau khi có production logs (>1.000 predictions), tối ưu `MULTI_LABEL_THRESHOLD` riêng cho từng domain dựa trên Precision-Recall curve.

**P8: Cân nhắc thêm nhãn `datn` (Đồ án/ĐATN)**

Nếu sau P1 accuracy cho ĐATN queries vẫn dưới 80%, xem xét tách thành domain riêng:

```python
LABEL_DATN = "datn"  # training_data.py
RAG_LABELS = {LABEL_CTDT, LABEL_QUYDINH, LABEL_KEHOACH, LABEL_STSV, LABEL_DATN}
```

Lưu ý: cần ít nhất 60–80 mẫu mới và retrain toàn bộ Stage 2.

**P9: Production monitoring**

```python
# domain_classifier.py — predict()
logger.info(
    "PREDICT intent=%s domains=%s conf=%.3f query_len=%d",
    result["intent"], result.get("domains"), result["confidence"], len(query)
)
```

Export metrics này vào Prometheus/Grafana để theo dõi drift theo thời gian.

---

## 7. Tóm tắt

| Hạng mục | Đánh giá | Ghi chú |
|---|---|---|
| Kiến trúc hai tầng | ✅ Tốt | Tách intent/domain hợp lý |
| Calibration (cv=5) | ✅ Tốt | Phù hợp với dữ liệu nhỏ |
| Taxonomy nhãn | ⚠️ Cần cải thiện | Thiếu nhãn cho ĐATN, học phần TĐ |
| Phân phối training data | ❌ Lệch pha | `kehoach` 18% training vs 74% thực tế |
| LLM Router | ⚠️ Thiếu domain | `domain=None` khi dùng LLM mode |
| Context window routing | ⚠️ Hơi nhỏ | `_CONTEXT_WINDOW=2` → mất context |
| Reflection few-shot | ⚠️ Thiếu ví dụ | Chỉ 1 example, thiếu ĐATN / TĐ |
| Entity extraction | ⚠️ Thiếu semester | Không bắt được kỳ học, năm học |
| Production monitoring | ❌ Chưa có | Cần log confidence distribution |
