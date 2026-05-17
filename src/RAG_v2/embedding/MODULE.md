# Module: `embedding` — Vector Embedding Layer

## Tổng quan

Module `embedding` chịu trách nhiệm **chuyển đổi văn bản thành vector số** (dense embeddings) để phục vụ tìm kiếm ngữ nghĩa (semantic search). Hệ thống sử dụng **hai embedder song song** để tận dụng điểm mạnh của từng model.

---

## Cấu trúc file

```
embedding/
├── __init__.py        # Factory: BGEm3Embedder, E5MultilingualEmbedder, EnsembleEmbedder
├── base.py            # BaseEmbedder abstract class
├── bge_m3.py          # BGE-M3 embedder (FlagEmbedding)
├── e5_multilingual.py # E5-Multilingual-Large embedder (sentence-transformers)
└── ensemble.py        # EnsembleEmbedder (trung bình có trọng số)
```

---

## Nhiệm vụ chi tiết

### `bge_m3.py` — `BGEm3Embedder`

**Model:** `BAAI/bge-m3`
**Loại:** Multilingual dense retrieval model
**Chiều vector:** 1024-dim

**Khả năng đặc biệt:**
- Hỗ trợ **multi-lingual** (bao gồm Tiếng Việt rất tốt)
- Có thể tạo cả **dense**, **sparse**, và **ColBERT** vectors
- Hệ thống hiện tại chỉ dùng **dense vector**

**Vai trò trong retrieval:**
- Dùng cho **semantic search** trong Qdrant (vector similarity)
- Đồng thời dùng làm **feature extractor** cho `DomainClassifier`

```python
bge_vec = bge_embedder.embed_query("điều kiện xét học bổng là gì?")
# → List[float], dim=1024
```

---

### `e5_multilingual.py` — `E5MultilingualEmbedder`

**Model:** `intfloat/multilingual-e5-large`
**Loại:** Instruction-tuned multilingual embedder
**Chiều vector:** 1024-dim

**Khác biệt với BGE-M3:**
- Prefix-based: tự động thêm `"query: "` trước query
- Tốt hơn với **semantic similarity** ở level câu/đoạn
- Bổ sung góc nhìn retrieval khác với BGE-M3

**Vai trò trong retrieval:**
- Kết hợp với BGE-M3 tạo **ensemble vector search**
- Trong Qdrant: sử dụng **multi-vector** (BGE + E5) với fusion scoring

---

### `ensemble.py` — `EnsembleEmbedder`

**Nhiệm vụ:** Kết hợp vectors từ nhiều embedder bằng **weighted averaging**.

```python
ensemble_vec = alpha * bge_vec + (1-alpha) * e5_vec
```

*(Hiện tại ít được dùng trực tiếp — pipeline gọi riêng từng embedder để kiểm soát fusion tốt hơn)*

---

### `base.py` — `BaseEmbedder`

Abstract class định nghĩa interface chung:
```python
class BaseEmbedder:
    def embed_query(self, text: str) -> List[float]: ...
    def embed_documents(self, texts: List[str]) -> List[List[float]]: ...
```

---

## Điểm tích hợp với các module khác

| Nơi sử dụng | Cách dùng |
|---|---|
| `pipeline/flows.py` | `bge_embedder.embed_query()` + `e5_embedder.embed_query()` trước search |
| `retrieval/service.py` | `self.embed_query()` wraps cả hai |
| `agent/tool_adapters.py` | `runtime.bge_embedder.embed_query()` trong `_rag_search()` |
| `query/domain_classifier.py` | BGE-M3 làm feature cho LogisticRegression |

---

## LLM involvement

Module `embedding` **không sử dụng LLM** — chỉ dùng local neural models (BERT-family) chạy trên GPU/CPU.

---

## Latency contribution

| Bước | Thời gian điển hình |
|---|---|
| BGE-M3 embed (GPU) | 15-50ms |
| E5 embed (GPU) | 15-50ms |
| BGE-M3 embed (CPU only) | 100-400ms |
| E5 embed (CPU only) | 100-400ms |
| **Tổng (cả 2 embedders, GPU)** | **~30-100ms** |
| **Tổng (cả 2 embedders, CPU)** | **~200-800ms** ⚠️ |

> ⚠️ Nếu chạy trên CPU (không có GPU), embedding có thể chiếm **200-800ms** mỗi request.
> Cân nhắc dùng GPU inference hoặc cache embedding cho các query phổ biến.

---

## Update 2026-05-17: Lazy concrete exports

`embedding.__init__` keeps backwards-compatible exports for `BGEm3Embedder`,
`E5MultilingualEmbedder`, and `EnsembleEmbedder`, but resolves them lazily via
`__getattr__`. Importing `embedding.base` or `create_embedder` no longer imports
heavy optional ML dependencies such as `torch` unless a concrete embedder is
actually requested.
