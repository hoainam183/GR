# Fix: Câu trả lời bị ngắt & Agent không tìm được môn học theo kỳ

## Phân tích vấn đề

### Bug 1: Câu trả lời bị ngắt (RAG pipeline)
**Root cause:** `CHAT_MAX_TOKENS=1024` trong `.env` quá thấp.

Gemini 2.5 Flash với context dài (học bổng có nhiều điều kiện) cần nhiều token hơn để hoàn thành câu trả lời. Khi LLM hit limit, nó bị cắt ngang giữa chừng — **đây là lý do câu trả lời kết thúc đột ngột** ở giữa phần liệt kê điều kiện.

Bằng chứng: Log hiển thị `Generate: 5.51s` bình thường, không có lỗi — Gemini thực sự **sinh ra** đủ nhanh, nhưng bị cắt bởi `max_tokens`.

### Bug 2: Agent không tìm được "môn mạng máy tính học vào kỳ mấy"
**Root cause:** Câu hỏi này khớp với `COMPLEX_PATTERNS` pattern:
```
r"(môn|học phần).{0,30}\b(được|có)\s+(đăng ký|đăng kí|mở|học)\b"
```
Pattern này match `môn mạng máy tính được học vào kỳ mấy` → route → **agent**.

Nhưng khi agent chạy, tool `rag_search` được gọi với query `'"mạng máy tính" kỳ'` vào collection `chuong_trinh`. Dù prompt có hướng dẫn đúng, **Qwen 2.5 7B** (local LM Studio) không đủ mạnh để nhất quán tuân theo format `"quoted phrase"`. Có thể nó bỏ qua dấu ngoặc kép → ES không tìm thấy với exact phrase boost → fallback retrieval không có kết quả liên quan.

Thêm vào đó: kết quả `"Tôi không tìm thấy thông tin cụ thể"` có **Iterations: 2** — Qwen đã thử nhưng synthesis LLM (Gemini) vẫn nói "không tìm thấy", cho thấy **retrieval trả về không đúng chunks**, hoặc `_tool_result_limit=3000` cắt bớt bảng curriculum dài.

**Nguyên nhân cụ thể:**
1. Query `"mạng máy tính học vào kỳ mấy"` → `ComplexityRouter` route sang **agent** (do pattern `(môn|học phần).{0,30}học`) 
2. Qwen 7B không theo format quoted phrase → search thất bại
3. Ngay cả khi search thành công, bảng curriculum (phân bổ kỳ học) rất dài → `_tool_result_limit=3000` cắt bảng → Gemini synthesis không thấy thông tin kỳ

---

## Giải pháp đề xuất

### Fix 1 — Tăng `CHAT_MAX_TOKENS` (`.env`)
Tăng từ `1024` → `2048` để câu trả lời không bị cắt giữa chừng.

### Fix 2a — Loại bỏ false positive khỏi `COMPLEX_PATTERNS` (complexity_router.py)
Pattern `(môn|học phần).{0,30}\b(được|có)\s+(đăng ký|đăng kí|mở|học)\b` đang quá rộng.

Query "môn mạng máy tính **được học** vào kỳ mấy" là câu hỏi **đơn giản** (single-source lookup), không cần agent. Nên route sang **simple** để dùng RAG pipeline trực tiếp — RAG pipeline đã có semantic search đủ tốt cho loại câu này.

**Giải pháp:** Điều chỉnh pattern để chỉ route sang complex khi có cả (môn/học phần) + (được đăng ký/mở đăng ký) — thể hiện intent hỏi về lịch đăng ký, không phải phân bổ kỳ học.

### Fix 2b — Tăng `_tool_result_limit` cho agent (`.env` + react_agent.py)
Bảng phân bổ kỳ học trong `chuong_trinh` rất dài. `AGENT_TOOL_RESULT_LIMIT=3000` có thể cắt mất cột "kỳ" trong bảng.

Tăng từ `3000` → `5000` để giữ nguyên bảng curriculum.

### Fix 2c — Cải thiện keyword search cho query không có quoted phrase (elasticsearch_store.py)  
Khi agent gửi query không có dấu ngoặc kép (Qwen quên format), cần có fallback tốt hơn. Thêm boost cho `section_h2`/`section_h3` khi query chứa từ khóa tên môn học phổ biến.

---

## Proposed Changes

### Fix 1: CHAT_MAX_TOKENS

#### [MODIFY] `.env`
- `CHAT_MAX_TOKENS`: `1024` → `2048`

---

### Fix 2a: ComplexityRouter — loại bỏ false positive

#### [MODIFY] `complexity_router.py`
- Pattern `(môn|học phần).{0,30}\b(được|có)\s+(đăng ký|đăng kí|mở|học)\b` → điều chỉnh thành chỉ match khi có `đăng ký` / `đăng kí` / `mở`, loại bỏ chữ `học` khỏi pattern (vì "được học" là đặc điểm của câu hỏi về kỳ học, không phải đăng ký)

---

### Fix 2b: AGENT_TOOL_RESULT_LIMIT

#### [MODIFY] `.env`
- `AGENT_TOOL_RESULT_LIMIT`: `3000` → `5000`

---

## Verification Plan

### Test queries sau khi fix
1. **"điều kiện đạt học bổng"** → RAG pipeline, câu trả lời không bị cắt
2. **"môn mạng máy tính được học vào kỳ mấy"** → Route simple → RAG, tìm thấy kỳ học  
3. **"môn kỹ thuật phần mềm học vào kỳ nào"** → Route simple → RAG, tìm thấy kỳ học
4. **"so sánh chương trình IT-E6 và IT-E7"** → vẫn route complex → agent (không bị ảnh hưởng)

## Open Questions

> [!IMPORTANT]
> Câu hỏi: Bạn muốn "môn X được học vào kỳ mấy" đi qua **RAG pipeline** (nhanh hơn, ~20s) hay **agent** (chậm hơn, ~55s)?
> - RAG pipeline: dùng semantic search + reranker trực tiếp, không cần agent — nếu đã có boosting ES cho `"quoted phrase" kỳ` thì kết quả tốt
> - Agent: linh hoạt hơn nhưng phụ thuộc vào chất lượng Qwen 7B local

Theo kết quả log (`Iterations: 2`, thất bại), **nên route sang simple/RAG** vì agent không mang lại giá trị thêm cho loại query này.
