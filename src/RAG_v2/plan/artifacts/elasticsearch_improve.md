# Kế hoạch Cải thiện Elasticsearch cho Hệ thống RAG Tiếng Việt

> Tổng hợp từ phân tích chunk `quydinh` và cấu hình ES hiện tại  
> Mức độ ưu tiên: 🔴 Cao · 🟡 Trung bình · 🟢 Thấp

---

## 1. Chẩn đoán Hiện trạng

### 1.1 Vietnamese Analyzer — Tên hay, chất chưa đủ

```json
"vietnamese_analyzer": {
  "type": "custom",
  "tokenizer": "standard",   // ⚠️ Vẫn là standard tokenizer
  "filter": ["lowercase", "asciifolding"]
}
```

**Vấn đề:** `standard` tokenizer tách theo khoảng trắng và dấu câu, không hiểu từ ghép tiếng Việt.

| Input | standard tokenizer | Kỳ vọng |
|---|---|---|
| `"tín chỉ tích lũy"` | `[tín, chỉ, tích, lũy]` | `[tín chỉ, tích lũy]` |
| `"đồ án tốt nghiệp"` | `[đồ, án, tốt, nghiệp]` | `[đồ án, tốt nghiệp]` |
| `"học kỳ I năm 2024"` | `[học, kỳ, i, năm, 2024]` | `[học kỳ, năm 2024]` |

Với query này thì tình cờ vẫn match được vì các token rời vẫn có trong document. Nhưng **precision thấp** và **ranking sai** vì TF-IDF tính trên từng âm tiết thay vì từ có nghĩa.

### 1.2 `applicable_cohort` — Có trong mapping nhưng không trong text

```json
// Mapping: OK — có field applicable_cohort kiểu text + keyword
"applicable_cohort": { "type": "text", "fields": { "keyword": {...} } }

// Nhưng trong index_to_es.py:
text = payload.pop("text", "")  // chỉ lấy field "text"
metadatas.append(payload)        // applicable_cohort đi vào đây
```

**Vấn đề:** `applicable_cohort` được lưu trong ES document nhưng **query BM25 mặc định chỉ search trên field `text`**. Nếu hybrid search query không explicitly filter/search trên field này, token `K69` trong query của user sẽ không match được.

### 1.3 Markdown Table làm nhiễu TF-IDF

Chunk `quydinh` chứa nhiều bảng dạng:
```
| Số tín chỉ tích lũy | Trình độ tiếng Anh yêu cầu |
|---------------------|---------------------------|
| Đến 63 TC           | Đạt tất cả FL1131...      |
```

Các ký tự `|`, `---`, `<br>` được tokenize thành noise tokens, làm loãng IDF của các token có nghĩa. Document dài hơn bình thường → BM25 score thấp hơn so với document prose.

### 1.4 Không có `section_context` trong query

Field `section_h2`, `section_h3` có trong mapping và chứa thông tin context rất giá trị (`"PHỤ LỤC 3: Danh mục các học phần tiếng Anh..."`), nhưng nếu query builder không include các field này trong multi-match, context bị bỏ qua.

---

## 2. Kế hoạch Cải thiện

### 🔴 P1 — Nâng cấp Vietnamese Tokenizer

**Mục tiêu:** Tách từ đúng ngữ nghĩa tiếng Việt.

**Lựa chọn (theo thứ tự ưu tiên):**

#### Option A: `vi_analyzer` plugin (Tốt nhất)
Cài [Elasticsearch Vietnamese Analysis Plugin](https://github.com/duydo/elasticsearch-analysis-vietnamese):
```bash
bin/elasticsearch-plugin install \
  https://github.com/duydo/elasticsearch-analysis-vietnamese/releases/download/v8.x.x/elasticsearch-analysis-vietnamese-8.x.x.zip
```

```json
"vietnamese_analyzer": {
  "type": "custom",
  "tokenizer": "vi_tokenizer",
  "filter": ["lowercase", "asciifolding"]
}
```

#### Option B: ICU Tokenizer (Không cần plugin riêng, tốt hơn standard)
```bash
bin/elasticsearch-plugin install analysis-icu
```
```json
"vietnamese_analyzer": {
  "type": "custom",
  "tokenizer": "icu_tokenizer",
  "filter": ["lowercase", "icu_folding"]
}
```

#### Option C: Shingle filter (Không cần plugin, cải thiện tức thì)
Giữ `standard` tokenizer nhưng thêm bigram/trigram để capture từ ghép:
```json
"vietnamese_analyzer": {
  "type": "custom",
  "tokenizer": "standard",
  "filter": ["lowercase", "asciifolding", "vi_shingle"]
},
"filter": {
  "vi_shingle": {
    "type": "shingle",
    "min_shingle_size": 2,
    "max_shingle_size": 3,
    "output_unigrams": true
  }
}
```

> ⚠️ **Sau khi đổi analyzer phải reindex toàn bộ** — chạy lại `index_to_es.py` với `FORCE_REINDEX = True`.

---

### 🔴 P2 — Inject Cohort vào Text khi Index

**Mục tiêu:** Cho phép BM25 match token `K69`, `K68` từ query.

**Thay đổi trong `index_to_es.py`:**

```python
for pt in scroll_all_points(qdrant, collection):
    payload = dict(pt.payload or {})
    text = payload.pop("text", "")

    # --- Inject applicable_cohort vào text ---
    cohorts = payload.get("applicable_cohort")
    if cohorts:
        if isinstance(cohorts, list):
            cohort_str = " ".join(cohorts)
        else:
            cohort_str = str(cohorts)
        text = f"[Áp dụng cho: {cohort_str}]\n{text}"
    # -----------------------------------------

    texts.append(text)
    metadatas.append(payload)
    ids.append(str(pt.id))
```

**Kết quả:** Document sẽ có dạng:
```
[Áp dụng cho: K68 K69]
### Bảng 3.2: Yêu cầu chuẩn tiếng Anh...
```

---

### 🔴 P3 — Dùng `applicable_cohort.keyword` Filter trong Query

**Mục tiêu:** Khi có cohort trong query, filter chính xác thay vì chỉ rely vào BM25.

Trong query builder (hybrid search), thêm filter nếu detect được cohort:

```python
def build_es_query(query_text: str, cohort: str | None = None) -> dict:
    must_clauses = [
        {
            "multi_match": {
                "query": query_text,
                "fields": ["text^3", "title^2", "section_h2", "section_h3"],
                "type": "best_fields",
                "fuzziness": "AUTO"
            }
        }
    ]

    filter_clauses = []
    if cohort:
        filter_clauses.append({
            "term": {"applicable_cohort.keyword": cohort}
        })

    return {
        "query": {
            "bool": {
                "must": must_clauses,
                "filter": filter_clauses
            }
        }
    }
```

---

### 🟡 P4 — Clean Markdown trước khi Index

**Mục tiêu:** Giảm noise token từ cú pháp Markdown/table, cải thiện TF-IDF score.

```python
import re

def clean_markdown_for_indexing(text: str) -> str:
    """
    Giữ nội dung, bỏ cú pháp Markdown.
    Chỉ dùng khi index vào ES — Qdrant vẫn giữ text gốc.
    """
    lines = text.split("\n")
    cleaned = []

    for line in lines:
        # Convert table row thành prose
        if line.strip().startswith("|"):
            cells = [c.strip() for c in line.split("|")]
            cells = [c for c in cells if c and not re.match(r'^[-:]+$', c)]
            if cells:
                cleaned.append(" · ".join(cells))
            continue

        # Bỏ heading markers nhưng giữ text
        line = re.sub(r'^#{1,4}\s+', '', line)
        # Bỏ bold/italic markers
        line = re.sub(r'\*{1,3}(.*?)\*{1,3}', r'\1', line)
        # Bỏ <br> tags
        line = re.sub(r'<br\s*/?>', ' ', line)
        # Bỏ dòng toàn dấu ---
        if re.match(r'^[-=]{3,}$', line.strip()):
            continue

        if line.strip():
            cleaned.append(line)

    return "\n".join(cleaned)
```

**Tích hợp vào index loop:**
```python
# Chỉ clean text cho ES, không ảnh hưởng Qdrant
es_text = clean_markdown_for_indexing(text)
texts.append(es_text)
```

---

### 🟡 P5 — Multi-field Boosting trong Query

**Mục tiêu:** Tận dụng các metadata fields đã có trong mapping.

```python
"multi_match": {
    "query": query_text,
    "fields": [
        "text^3",          # Content chính — weight cao nhất
        "title^2",         # Title document
        "section_h2^1.5",  # Section heading
        "section_h3^1.5",
        "hierarchy_path^1" # Fallback
    ],
    "type": "best_fields"
}
```

---

### 🟢 P6 — Thêm `readable_id` / `chunk_id` vào Index

Hiện tại ID trong ES là UUID từ Qdrant (`pt.id`). Nên map thêm `readable_id` để debug và trace dễ hơn:

```python
payload["qdrant_id"] = str(pt.id)  # Giữ ID gốc để join lại
ids.append(payload.get("readable_id") or str(pt.id))
```

---

## 3. Tóm tắt Ưu tiên & Effort

| # | Cải tiến | Priority | Effort | Impact |
|---|---|---|---|---|
| P1 | Nâng cấp Vietnamese Tokenizer | 🔴 Cao | Trung bình (cần reindex) | Ranking tốt hơn toàn bộ |
| P2 | Inject cohort vào text | 🔴 Cao | Thấp (5 dòng code) | Fix miss hoàn toàn cho query K6x |
| P3 | Filter `applicable_cohort.keyword` trong query | 🔴 Cao | Thấp | Precision cao hơn |
| P4 | Clean Markdown trước index | 🟡 Trung bình | Trung bình | BM25 score sạch hơn |
| P5 | Multi-field boosting | 🟡 Trung bình | Thấp | Recall + ranking |
| P6 | Thêm readable_id | 🟢 Thấp | Thấp | Dev/debug experience |

---

## 4. Thứ tự Thực hiện Khuyến nghị

```
Tuần 1:
  ├── P2: Inject cohort vào text  (30 phút, không cần reindex nếu làm cùng P1)
  ├── P3: Update query builder    (1-2 giờ)
  └── P1: Chọn tokenizer, reindex (2-4 giờ tùy setup)

Tuần 2:
  ├── P4: Clean Markdown function (2 giờ + test)
  └── P5: Multi-field query       (1 giờ)

Sau đó:
  └── P6: readable_id             (30 phút)
```

> 💡 **P2 + P3 nên làm cùng P1** để chỉ reindex một lần duy nhất.