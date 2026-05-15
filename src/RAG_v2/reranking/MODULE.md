# Module: `reranking` — Document Reranking Layer

## Tổng quan

Module `reranking` chịu trách nhiệm **sắp xếp lại thứ tự** các tài liệu đã được retrieve từ giai đoạn hybrid search. Reranker sử dụng **cross-encoder model** để đánh giá mức độ liên quan của mỗi tài liệu với câu hỏi một cách chính xác hơn bi-encoder.

---

## Cấu trúc file

```
reranking/
├── __init__.py     # Factory: create_reranker()
├── base.py         # BaseReranker abstract class
└── bge_reranker.py # BGEReranker — BGE cross-encoder reranker
```


---

## Tại sao cần reranking?

**Hai giai đoạn retrieval (Bi-encoder → Cross-encoder):**

| Giai đoạn | Model | Ưu điểm | Nhược điểm |
|---|---|---|---|
| Retrieval (bi-encoder) | BGE-M3, E5 | Nhanh, xử lý batch | Kém chính xác hơn |
| Reranking (cross-encoder) | BGE Reranker | Rất chính xác | Chậm hơn, không batch tốt |

Hệ thống dùng `top_k * 4 = 20` candidates từ retrieval → reranker chọn lại top 5.

---

## Nhiệm vụ chi tiết

### `bge_reranker.py` — `BGEReranker`

**Model:** `BAAI/bge-reranker-v2-m3` (hoặc config từ settings)
**Loại:** Cross-encoder (xem query + document cùng lúc)

**Hoạt động:**
```
Input: query + List[Document] (20 candidates)
  ↓
Cross-encoder scores mỗi (query, doc) pair
  ↓
Sort by score DESC
  ↓
Filter by per-doc threshold (table vs non-table)
  ↓
Return top_k from survivors (thường top 5)
```

**Score threshold:** Tài liệu có `rerank_score < threshold` bị bỏ (tránh hallucination từ tài liệu không liên quan).
Đặc biệt đối với dữ liệu bảng (`has_table: true`), hệ thống hỗ trợ một ngưỡng riêng `reranker_table_score_threshold` (mặc định `-5.0`) vì mô hình cross-encoder thường chấm điểm logit âm cho các văn bản dạng bảng.

**Quan trọng:** Threshold filtering xảy ra **TRƯỚC** top_k truncation. Nếu ngược lại (top_k trước, filter sau), các table docs với ngưỡng thấp hơn có thể bị loại bởi top_k cut khi các non-table docs chiếm hết slot mặc dù chúng cũng fail threshold.

Hệ thống cũng tăng số lượng ứng viên truy xuất ban đầu (`vector_top_k` / `keyword_top_k` = 50) để đảm bảo các từ khoá hiếm trong bảng không bị loại bỏ sớm do nhiễu từ truy vấn viết lại.


**Bypass reranker logic (trong `tool_adapters.py`):**
```python
# Bỏ qua reranker cho curriculum table chunks (tránh mất dữ liệu bảng dài)
if collection == "chuong_trinh" and any(w in query for w in ["kỳ", "kì", "chẵn", "lẻ"]):
    skip_rerank = True
```

---

### `base.py` — `BaseReranker`

Abstract class định nghĩa interface:
```python
class BaseReranker:
    def rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: int,
    ) -> List[Dict[str, Any]]: ...
```

---

### `__init__.py` — `create_reranker()`

Factory function tạo reranker từ settings:
```python
reranker = create_reranker(settings)
# settings.reranker_provider = "bge" → BGEReranker
# settings.reranker_provider = None  → NoOpReranker
```

---

## Kết nối với các module khác

| Module | Cách dùng |
|---|---|
| `pipeline/flows.py` | `reranker.rerank(query, documents, top_k)` |
| `retrieval/service.py` | `self.reranker.rerank(...)` trong `search()` |
| `agent/tool_adapters.py` | `runtime.reranker.rerank(...)` trong `_rag_search()` |

---

## LLM involvement

Module `reranking` **không sử dụng LLM** — sử dụng local cross-encoder model (BERT-based).

---

## Latency contribution

| Cấu hình | Thời gian điển hình |
|---|---|
| BGE Reranker (GPU, 20 candidates) | 50-200ms |
| BGE Reranker (CPU, 20 candidates) | **300-1500ms** ⚠️ |
| NoOp Reranker | <1ms |

> ⚠️ **Reranker trên CPU là điểm nghẽn đáng kể** — cân nhắc GPU inference hoặc giảm candidate pool size.

## Tuning suggestions

| Param | Default | Tác động |
|---|---|---|
| `reranker_top_k` | 5 | Giảm → nhanh hơn, kém coverage hơn |
| `reranker_score_threshold` | 0.3 | Tăng → loại nhiều doc hơn, giảm hallucination |
| `raw_candidate_k` | top_k * 4 | Giảm → reranker nhanh hơn, ít candidates hơn |
