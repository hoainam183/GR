# Script thuyết trình phản biện — Hệ thống RAG (bản đã đối chiếu source code)

> Bản này đã sửa theo source code thực tế trong `src/RAG_v2`. Mỗi phần có kèm dẫn chứng `file:line` để trả lời khi thầy hỏi sâu.

---

## PHẦN 1 — Dữ liệu & Ingestion

Hệ thống có **4 vector collection** và **1 kho lịch thi có cấu trúc riêng**:

| Collection | Nội dung | Nguồn | Cách xử lý |
|-----------|----------|-------|-----------|
| `quydinh` | Quy chế, quy định | PDF luật được **OCR/convert** + file **admin upload** (KHÔNG crawl) | recursive chunk theo cấu trúc markdown (Điều/Chương) + có parent chunk |
| `ctdt` | Chương trình đào tạo | Web các khoa (soict, cokhi, dien-dientu, hoa, toan, vatlieu) | recursive chunk theo heading markdown + có parent chunk |
| `stsv` | Sổ tay sinh viên | Dữ liệu web JSON từ cổng CTT, đã làm sạch HTML | chunk phẳng theo số La Mã (I., II.) và mục 1., 2. |
| `kehoach` | Kế hoạch, thông báo | **Crawl từ `ctt.hust.edu.vn`** | chunk phẳng theo mục 1., 2. |
| `lichthi` *(không phải vector)* | Lịch thi | PDF lịch thi | Mongo + Elasticsearch có cấu trúc, query bằng filter (không vector search) |

**Luồng xử lý:**
1. **Raw → Markdown có cấu trúc:** dùng các converter (`pymupdf4llm`, `docling`, `pdfplumber` — có fallback OCR).
   - Dẫn chứng: `document_loader/pdf_to_markdown/converters/`
2. **Chunking theo cấu trúc markdown:** tách theo heading `#`, `##`, `###`.
   - Dẫn chứng: `chunking/chunker/recursive_chunker.py:38-50` (`MARKDOWN_SEPARATORS`); legal chunker `olmocr_legal_chunker.py`
   - Với **kehoach/stsv** (nguồn web): làm sạch thẻ HTML bằng BeautifulSoup rồi chunk lại theo đầu mục.
     - Dẫn chứng: `data/kehoach/reprocess_content_text.py:67-114`, `data/stsv/clean_data/clean_data.py:36-59`; regex `kehoach_chunker.py:72`, `stsv_chunker.py:72,77` (số La Mã + mục số). Cả hai chunker đều **table-aware**.
     - Metadata khác hẳn nhóm legal: kehoach có `baiviet_id, category, date_str`; stsv có `type_doc, section_context`; còn ctdt/quydinh có `chapter, article, hierarchy_path`.
3. **Embed bằng CẢ 2 model** rồi lưu:
   - `BAAI/bge-m3` (1024 chiều) + `intfloat/multilingual-e5-large` (1024 chiều)
   - Dẫn chứng: `scripts/index_parent_child.py:226-227`; model id ở `embedding/bge_m3.py:77`, `embedding/e5_multilingual.py:76`
4. **Lưu vào Qdrant + Elasticsearch:**
   - Qdrant: lưu **2 named vector** (`bge_m3`, `e5`) trong 1 collection — `retrieval/qdrant_store.py:15-18`
   - **Parent chunk chỉ lưu cho `ctdt` + `quydinh`** để mở rộng context (stsv/kehoach là chunk phẳng) — `index_parent_child.py:50` (`PARENT_CHILD_SOURCES`), expander `retrieval/parent_context.py:64`
   - Elasticsearch: index theo tên collection (ES loại parent chunk, chỉ giữ child) — `index_parent_child.py:273-284`

**Vì sao dùng 2 model (câu hỏi phản biện chắc chắn có):**
- 2 model bổ trợ điểm yếu của nhau; fusion dùng **max-normalization** để không model nào áp đảo do khác thang điểm (`qdrant_store.py:231-252`), trọng số `bge 0.5 / e5 0.5` (`settings.py:156-157`).
- **Tradeoff về thời gian là không đáng kể** vì 2 vector search được gộp thành **1 round-trip** (`client.query_batch_points`, `qdrant_store.py:158-181`, giảm ~30% latency). Chi phí thêm chỉ là 1 lần embed query, không phải 2 lần gọi DB.
- Lưu ý kỹ thuật: đây là **2 named vector + score fusion**, KHÔNG phải `EnsembleEmbedder` (vector trung bình). Bật/tắt qua `embedding_provider="ensemble"` (`settings.py:68`).

---

## PHẦN 2 — Phân loại Intent & Định tuyến (Routing)

> **Điểm mấu chốt:** đây KHÔNG phải 2 classifier tuần tự, mà là **1 hàm 3 tầng** chạy **sau bước reflection**.
> Dẫn chứng: `pipeline/rag_pipeline.py:1044-1101` (`_decide_complexity`), gọi tại `:829-831`.

**Tầng 0 — Regex (`ComplexityRouter`)** — chạy đầu tiên:
- Bắt nhanh các mẫu rõ ràng: chào hỏi/cảm ơn (→ chitchat), so sánh (`so sánh`, 2 mã khoá `K\d{2,3}`), điều kiện cá nhân (`đủ điều kiện`), fast-path lịch thi, câu hỏi single-fact (`bao nhiêu`, `bao lâu` → simple).
- Không khớp mẫu nào → trả `"unknown"` để chuyển xuống tầng ML.
- Dẫn chứng: `query/complexity_router.py:216`, gọi tại `rag_pipeline.py:1062`
- **Lưu ý:** gate "điều kiện tốt nghiệp / nhiều ngành học" **đã bị xoá có chủ đích** (`complexity_router.py:337-345` — anti-pattern enumeration). Cụm này giờ nằm trong **prompt LLM ở Tầng 2**, không phải regex.

**Tầng 1 — ML classifier (LogisticRegression, multi-label)** — chạy khi Tầng 0 trả `unknown`:
- Model: `CalibratedClassifierCV(LogisticRegression, cv=5)` — `query/domain_classifier.py:56-64`
- **Stage 1 — Intent:** 3 nhãn `chitchat`, `rag`, `tool_search` (`query/router.py:29`). Trong đó `rag` là nhãn **phái sinh** (gộp từ 4 domain RAG — `domain_classifier.py:121-124`).
- **Stage 2 — Domain multi-label:** 4 domain `ctdt, quydinh, kehoach, stsv`. Một domain được coi là "active" khi xác suất ≥ **0.35** (`MULTI_LABEL_THRESHOLD`, `domain_classifier.py:49`).
- Nếu intent ≠ rag → `simple`. Nếu intent = rag: **< 2 domain active → `simple`** (đi thẳng vào RAG search); **≥ 2 domain active → escalate lên Tầng 2**.

**Tầng 2 — LLM judge** (phần trước bị bỏ sót, cần bổ sung):
- Với query "biên giới" (≥2 domain hoặc có tín hiệu `multi_domain`), **LLM đưa ra phán quyết cuối** simple/complex.
- Dẫn chứng: `_classify_complexity_llm`, `rag_pipeline.py:991-1042`, quyết định tại `:1095-1101`. LLM vẫn có thể trả về `simple`; mặc định `simple` nếu lỗi.

**Query complex → Planner-Executor:**
- Đồ thị LangGraph: `START → planner → executor → synthesize → END` (`agent/react_agent.py:658-672`).
- **planner**: phân rã query + định tuyến trong **1 lần gọi LLM** (không còn bước decompose riêng — `react_agent.py:87-92`).
- **executor**: chạy từng bước RAG search **song song** (`agent/tool_adapters.py:855-868`).
- **synthesize**: tổng hợp thành câu trả lời cuối.

---

## PHẦN 3 — Reflection → Retrieval → Rerank → Fallback

> Live path: `pipeline/flows/coordinators.py` (`rag_flow` / `rag_flow_stream`).

### 3.1 — Reflection query
- Lấy **5 message gần nhất** (trộn user + assistant, ~2–3 lượt — KHÔNG phải 5 cặp Q-A).
  - Dẫn chứng: `reflection.py:31` (`DEFAULT_HISTORY_LIMIT = 5`), `reflection.py:1534`
- **Expand thực thể** (deterministic, không LLM):
  - Mã ngành ↔ tên ngành 2 chiều: `IT1 → IT1 (CNTT: Khoa học Máy tính)` (`reflection.py:450`)
  - Mã môn: tên môn → `Mạng máy tính (IT3080)` (`reflection.py:1040`)
  - Viết tắt học thuật 2 chiều: NCS, ĐRL, NCKH, TKB, HVCH, CTĐT (`utils/terminology.py:19-26`)
  - "ngành của tôi / ngành này" → tên+mã ngành từ profile (`reflection.py:209`)
  - Trích để làm filter: cohort, học kỳ, năm học
- **Strip thông tin nhạy cảm** (`reflection.py:165-191`):
  - MSSV (`mssv|msv|mã sinh viên` + 6–12 số)
  - Tên tự giới thiệu ("Em/Tôi/Mình là <Tên>")
  - Lời cảm ơn, xưng hô thừa ("kính gửi thầy/cô/ban cố vấn")
  - Rò rỉ tên trường (ĐHBKHN/HUST nếu user không tự gõ)
  - **KHÔNG strip email/SĐT** (không có regex — đừng nói là có).

### 3.2 — Hybrid search
- Query đã reflect được embed bằng **cả BGE + E5**, search song song trên từng collection:
  - Qdrant (vector) + Elasticsearch (keyword) — `coordinators.py:530-565`, `multi_collection_search.py:421-439`
- **Số lượng ứng viên (giá trị LIVE, không phải 20/20):**
  - Lấy **50 vector + 50 keyword** mỗi collection (`settings.py:144-145`)
  - Gộp cross-collection về pool **40 + 40** (`settings.py:146-147`)
  - **RRF chọn top 28** đưa vào rerank — 28 = `raw_candidate_multiplier (4.0) × top_k (7)` (`settings.py:148`, `retrieval_helpers.py:85-108`)
- **Boost trong keyword search** (`elasticsearch_store.py`):
  - BM25 tuỳ chỉnh: k1=1.5, b=0.5
  - Theo field: `search_text^3.0, title^2.0, course_name^1.8, doc_title^1.8, text^1.6, hierarchy_path^1.5, section_h1/h2^1.4, section_h3^1.3, major_name^1.2, semester^1.2`
  - **Mã môn (course_code): boost 8.0** (`elasticsearch_store.py:877-881`)
  - match_phrase key-phrase: boost 10.0 (3 cụm đầu), 5.0 sau đó
  - Table-lookup hit: ×1.2
  - *Lưu ý: `exam_type`, cohort, date-range là FILTER trước search, không phải boost.*

### 3.3 — Fusion (nói chính xác: **weighted RRF + recency**)
- `fusion_mode = "rrf"`, `rrf_k = 10` (`settings.py:154-155`)
- Trọng số hardcode: **vector 0.8 / keyword 0.2** (`multi_collection_search.py:515-524`)
- Cộng thêm **recency bonus cho kehoach** (max +0.05, decay 365 ngày — `metadata_filters.py:1349-1373`)
- Linear max-norm chỉ dùng cho **eval**, không phải live.
- *Freshness KHÔNG boost trong ES:* recency cộng ở bước fusion; query "mới nhất" dùng pre-filter (`elasticsearch_store.py:567`).

### 3.4 — Rerank
- Reranker `BAAI/bge-reranker-v2-m3`, giữ **tối đa 7 doc**, chỉ giữ **score ≥ 0** (`settings.py:143,167,173`; lọc `bge_reranker.py:184`)
- Caveat:
  - Query dạng "liệt kê/danh sách" → nâng lên tối đa **12** (`retrieval_helpers.py:26-48`)
  - Chunk bảng dùng ngưỡng nới lỏng **−1.0** (`reranker_table_score_threshold`)
  - `reranker_min_top_k = 3`: nếu <3 doc qua ngưỡng thì vẫn giữ 3 doc tốt nhất (nên "chỉ ≥0" không tuyệt đối)

### 3.5 — Fallback: HyDE → Web search
- **HyDE** (chạy trước, sau rerank) — `pipeline/flows/hyde.py:28-73`:
  - Kích hoạt khi (a) không doc nào qua rerank, HOẶC (b) best score < 0, HOẶC (c) số doc qua strict < 3 (`hyde_min_results = 3`)
  - *Trước HyDE còn có bước rerank-retry bằng query gốc.*
- **Web search (Tavily)** — `pipeline/flows/web_fallback.py:328-489`:
  - Trigger bởi: `no_sources` / `low_retrieval_confidence` / `freshness_query` / `dynamic_query` / `answer_no_info` (câu trả lời báo "không có thông tin")
  - Chỉ search trên **domain chính thức của trường** (`HUST_OFFICIAL_DOMAINS`)
  - Nói đúng: *"nếu kết quả cuối vẫn không có/thiếu nguồn hoặc câu trả lời báo không có thông tin → web search"* — KHÔNG phải "HyDE tìm không ra".

---

## Phụ lục — 6 điểm dễ bị bắt lỗi nhất

1. **quydinh KHÔNG crawl** → OCR/convert PDF + admin upload; kehoach mới là crawl từ ctt.hust.edu.vn.
2. **Parent chunk chỉ có ở ctdt + quydinh**, không phải cả 4 collection.
3. **Routing là 3 tầng** (regex Tier 0 → ML Tier 1 → **LLM Tier 2**), không phải 2 classifier.
4. **≥2 domain → escalate LLM judge**, không đi thẳng sang complex; ngưỡng domain = 0.35.
5. **Số ứng viên live: 50/50 fetch → pool 40/40 → RRF top 28**, không phải 20/20.
6. **Fusion = weighted RRF (k=10, 0.8/0.2) + recency**; KHÔNG strip email; recency ở fusion chứ không phải boost ES.
