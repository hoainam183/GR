# Module: `reranking`

Lớp rerank dùng cross-encoder BGE-v2-M3 để chấm lại và sắp xếp tài liệu theo độ liên quan với truy vấn, sau một interface chung có registry provider.

## Files

### `__init__.py`
Cung cấp factory `create_reranker(settings)` lazy-import provider theo `reranker_provider` (trả `None` nếu `"none"`) và xử lý lỗi thiếu bộ nhớ khi nạp model.

### `base.py`
Định nghĩa interface reranker và registry provider.
- `BaseReranker.rerank()` — method trừu tượng chấm và sắp xếp tài liệu theo query.
- `register_reranker()` — decorator đăng ký lớp provider vào registry.

### `bge_reranker.py`
Cross-encoder `BAAI/bge-reranker-v2-m3` chấm từng cặp (query, doc), lọc theo ngưỡng điểm (riêng cho doc dạng bảng) rồi cắt top-K; có khóa để thread-safe.
- `BGEReranker.rerank()` — entry point thread-safe (khóa) gọi vào `_rerank_impl`.
- `BGEReranker._rerank_impl()` — chấm điểm, lọc ngưỡng, cắt top-K, hỗ trợ `min_top_k` fallback.
- `BGEReranker._enrich_text_for_reranking()` — thêm hierarchy/ngành/tiêu đề vào text trước khi chấm.
- `_resolve_torch_device()` — chọn device CUDA → MPS → CPU.
