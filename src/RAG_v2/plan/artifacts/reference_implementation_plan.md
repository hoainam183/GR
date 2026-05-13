# Fix Reference Resolver — Same-Document Cross-Reference Resolution

## Phân Tích Chi Tiết

### Câu hỏi & Kết quả hiện tại

Query: **"Học bổng Trần Đại Nghĩa được bao nhiêu tiền"**

Chunk **#8** (Điều 7) được retrieval đúng, nội dung:
> "Đối tượng quy định tại **khoản 1 và khoản 2 Điều 5**: Học bổng có 2 mức..."
> "Đối tượng quy định tại **khoản 3 và khoản 4 Điều 5**: Học bổng có 2 mức..."

→ Người đọc cần biết **Điều 5 nói gì** mới hiểu "đối tượng" ở đây là ai.

### Điều 5 tồn tại trong cùng document

Trong file `6a034e61506cdfd33a4f9b0c_recursive_chunks.json`, có **2 chunks chứa Điều 5**:

| Chunk | ID | Nội dung | Section H3 |
|-------|-----|---------|------------|
| chunk_0005 | `a4b5fcf1-...` | Điều 5 — khoản 1 (SV mới trúng tuyển) | `Điều 5. Tiêu chuẩn được đăng ký xét HB TĐN` |
| chunk_0006 | `8b28d54d-...` | Điều 5 — khoản 2,3,4 (SV từ HK2, SV khó khăn) | `Điều 5. Tiêu chuẩn được đăng ký xét HB TĐN` |

Cả hai đều có:
- `source: "Quy định Học bổng Trần Đại Nghĩa 2025.pdf"`
- `document_id: "6a034e61506cdfd33a4f9b0c"`
- `collection: "quydinh"`

### Root Cause: Reference Resolver tìm sai document

File [reference_resolver.py](file:///Users/nam.nguyen/Documents/personal/GR/src/RAG_v2/retrieval/reference_resolver.py):

```python
# Line 178: Search TOÀN BỘ collection, không filter theo source/document_id
ref_results = self._service.search(
    query="Điều 5",                    # ← quá generic
    collections=[collection],           # ← chỉ filter collection, không filter document
    top_k=2,
    rerank=True,
)
```

**Kết quả thực tế**:
- Tìm "Điều 5" trong collection `quydinh` → Trả về "Điều 5. Trách nhiệm của sinh viên" từ **QUY CHẾ SINH VIÊN** (document hoàn toàn khác!)
- Chunks từ cùng document (chunk_0005, chunk_0006) bị rank thấp hơn hoặc bị loại

**Lý do chunks đúng bị miss**:
1. Query `"Điều 5"` quá ngắn → BGE/E5 embeddings không đủ discriminative
2. Reranker score `"Điều 5. Trách nhiệm SV"` (0.7082) > `"Điều 5. Tiêu chuẩn xét HB TĐN"` (?) vì text chunk QUY CHẾ dài hơn, match nhiều patterns hơn
3. **Không có filter nào buộc kết quả phải từ cùng `document_id`**

### Tác động đến chất lượng câu trả lời

Câu trả lời hiện tại **thiếu thông tin quan trọng**: người dùng biết "50%/100% học phí" và "5/10 triệu" nhưng **không biết ai thuộc nhóm nào** vì:
- Khoản 1 Điều 5 = SV mới trúng tuyển đạt giải quốc tế/điểm cao
- Khoản 2 Điều 5 = SV từ HK2 có GPA ≥ 2.0
- Khoản 3,4 Điều 5 = SV gặp tai nạn/rủi ro đột xuất

---

## Proposed Changes

### [MODIFY] [reference_resolver.py](file:///Users/nam.nguyen/Documents/personal/GR/src/RAG_v2/retrieval/reference_resolver.py)

Thay đổi chiến lược resolve hoàn toàn: **Ưu tiên metadata-based lookup trước, fallback sang search sau**.

#### Approach: 2-Phase Resolution

**Phase 1 — Metadata Lookup (nhanh, chính xác):**
Sử dụng `document_id` + `section_h3` pattern matching để tìm chunks cùng document chứa "Điều X" trực tiếp từ Qdrant payload scroll. Không cần embed/rerank.

```python
# Qdrant scroll filter:
# must: [
#   {key: "document_id", match: "6a034e61506cdfd33a4f9b0c"},  # cùng document
#   {key: "section_h3", match_text: "Điều 5"}                  # chứa Điều 5 trong heading
# ]
```

- Với chunk_0008 (Điều 7) → extract `document_id = "6a034e61506cdfd33a4f9b0c"`
- Search Qdrant: `document_id == "6a034e61506cdfd33a4f9b0c"` AND `section_h3 contains "Điều 5"`
- Kết quả: chunk_0005 + chunk_0006 → **đúng!**
- Thời gian: ~50ms vs ~3-4s hiện tại

**Phase 2 — Semantic Search Fallback (khi Phase 1 trả 0 kết quả):**
Chỉ khi metadata lookup không tìm thấy → search query enriched với document context:
```python
ref_query = f"Điều {article} {source_filename}"  # "Điều 5 Quy định Học bổng Trần Đại Nghĩa 2025"
```
Và **verify post-search**: bỏ qua kết quả từ `document_id` khác.

#### Implementation Detail

```python
class ReferenceResolver:
    def __init__(self, retrieval_service=None, *, max_refs_per_chunk=2, max_total_refs=3):
        self._service = retrieval_service
        self._max_refs_per_chunk = max_refs_per_chunk
        self._max_total_refs = max_total_refs

    def _lookup_by_metadata(
        self, collection: str, document_id: str, article: int, clause: int | None = None
    ) -> list[dict]:
        """Phase 1: Fast Qdrant payload-based lookup within same document."""
        if not collection or not document_id:
            return []
        
        qdrant_stores = getattr(self._service, 'searcher', None)
        if qdrant_stores is None:
            return []
        qdrant_stores = getattr(qdrant_stores, 'qdrant_stores', {})
        store = qdrant_stores.get(collection)
        if store is None:
            return []

        article_pattern = f"Điều {article}"
        
        from qdrant_client import models as qmodels
        scroll_filter = qmodels.Filter(must=[
            qmodels.FieldCondition(
                key="document_id",
                match=qmodels.MatchValue(value=document_id),
            ),
        ])
        
        # Scroll all points matching document_id, then filter by article in text/section_h3
        points, _ = store.client.scroll(
            collection_name=store.collection_name,
            scroll_filter=scroll_filter,
            limit=50,       # documents typically have <30 chunks
            with_payload=True,
            with_vectors=False,
        )
        
        results = []
        for point in points:
            payload = dict(point.payload or {})
            text = payload.get("text", "")
            section_h3 = payload.get("section_h3", "") or ""
            
            # Match: section_h3 contains "Điều {N}" OR text starts with "### Điều {N}"
            if article_pattern not in section_h3 and article_pattern not in text[:100]:
                continue
            
            # If clause specified, verify text contains "khoản {clause}" or the specific clause content  
            text_key = payload.pop("text", "")
            results.append({
                "id": str(point.id),
                "text": text_key,
                "metadata": payload,
                "collection": collection,
                "_cross_reference": True,
            })
        
        return results

    def resolve(self, results, query=""):
        """Scan results for cross-references and fetch referenced chunks."""
        if not results or self._service is None:
            return results

        all_refs = []
        existing_ids = set()  # use IDs for dedup instead of text prefix
        
        for item in results:
            if isinstance(item, dict):
                existing_ids.add(str(item.get("id", "")))

        for item in results:
            text = ""
            source = ""
            collection = ""
            document_id = ""

            if isinstance(item, dict):
                text = str(item.get("text") or item.get("content") or "")
                metadata = item.get("metadata", {}) or {}
                source = str(metadata.get("source") or "")
                collection = str(item.get("collection") or metadata.get("collection") or "")
                document_id = str(metadata.get("document_id") or "")

            refs = extract_references(text)
            if not refs:
                continue

            for ref in refs[:self._max_refs_per_chunk]:
                if len(all_refs) >= self._max_total_refs:
                    break

                # Phase 1: Metadata lookup (fast, precise)
                ref_items = self._lookup_by_metadata(
                    collection, document_id, ref["article"], ref.get("clause")
                )
                
                # Phase 2: Enriched search fallback
                if not ref_items and source:
                    ref_query = f"Điều {ref['article']} {source}"
                    try:
                        ref_items = self._service.search(
                            query=ref_query,
                            collections=[collection] if collection else None,
                            top_k=3,
                            rerank=True,
                        )
                        # Post-filter: only keep results from same document
                        if document_id:
                            ref_items = [
                                r for r in ref_items
                                if r.get("metadata", {}).get("document_id") == document_id
                            ]
                    except Exception:
                        continue

                for ref_item in ref_items:
                    ref_id = str(ref_item.get("id", ""))
                    if ref_id in existing_ids:
                        continue
                    
                    ref_item["_cross_reference"] = True
                    ref_item["_referenced_from"] = source[:60]
                    ref_item["_reference"] = ref["raw_match"]
                    
                    all_refs.append(ref_item)
                    existing_ids.add(ref_id)
                    break  # one match per reference

        if all_refs:
            return results + all_refs
        return results
```

#### Key Differences from Current Code

| Aspect | Current | Proposed |
|--------|---------|----------|
| **Lookup strategy** | Full semantic search (`embed → hybrid search → rerank`) per reference | Qdrant metadata scroll by `document_id` + `section_h3` |
| **Document scoping** | None — searches entire collection | Strict same-document filter via `document_id` |
| **Performance** | ~3-4s per reference (11s total) | ~50ms per reference (~0.3s total) |
| **Accuracy** | Returns any "Điều 5" from any document | Returns only "Điều 5" from same PDF |
| **Dedup** | Text prefix (200 chars) — fragile | Point ID — exact |
| **Fallback** | None | Enriched search with `source` in query + post-filter |

---

### Không thay đổi

> [!NOTE]
> **Collection Selector mapping** (`quydinh ↔ stsv`) — Sau khi phân tích lại, vấn đề chính không phải từ collection mapping mà từ Reference Resolver. Chunks #4 và #6 trong output gốc là kết quả từ cross-reference resolution sai, không phải từ retrieval chính. Giữ nguyên mapping hiện tại.

> [!NOTE]
> **Reranker threshold** — Không cần thay đổi ngay. Sau khi fix Reference Resolver, các chunks irrelevant (#4, #6) sẽ tự động không còn xuất hiện.

---

## Verification Plan

### Automated Tests

1. **Unit test `_lookup_by_metadata`**: Mock Qdrant scroll, verify chỉ trả chunks cùng `document_id` + đúng `section_h3`
2. **Integration test**: Chạy query "Học bổng Trần Đại Nghĩa được bao nhiêu tiền" → verify:
   - Reference resolver tìm đúng chunk_0005 và/hoặc chunk_0006 (Điều 5 cùng document)
   - Không có chunks từ QUY CHẾ SINH VIÊN hoặc documents khác
   - Reference resolver time < 1s (down from 11s)

### Manual Verification

1. Chạy pipeline và so sánh output trước/sau
2. Verify câu trả lời bao gồm thông tin về đối tượng thuộc Điều 5
3. Test thêm 3-5 queries khác có cross-reference trong quy định
