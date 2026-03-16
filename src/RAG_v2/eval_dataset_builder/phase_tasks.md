# 📋 RAG Evaluation Dataset Builder — Task List theo Phase

> **Công cụ xây dựng ground truth dataset** để đánh giá RAG system.
> Flow: Cấu hình → Retrieve → Annotate → Export CSV

---

## Phase 1: Cấu hình Retrieval

> **Mục tiêu**: Setup retrieval config trước khi bắt đầu annotate.

### Tasks

- [x] **1.1 Kết nối Qdrant & List Collections**
  - [x] Dùng `QdrantClient` kết nối Qdrant
  - [x] List tất cả collections, hiển thị để chọn
  - [x] Cho phép chọn 1 hoặc nhiều collection

- [x] **1.2 Cấu hình Retrieval Parameters**
  - [x] Input `top_k` (default: 10, validate > 0)
  - [x] Dropdown chọn `embedding_model`: e5 / bge_m3 / hybrid
  - [x] Validate: bắt buộc trước khi nhập query

- [x] **1.3 Pydantic Schema — `RetrievalConfig`**
  - [x] Implement `RetrievalConfig` model trong `models/schemas.py`
  - [x] Implement `RetrievalConfigManager` trong `config/retrieval_config.py`

### ✅ Kết quả sau Phase 1

| Deliverable | Mô tả |
|-------------|--------|
| **Config UI** | Chọn collection + nhập top_k + chọn embedding model |
| **Validation** | Config bắt buộc trước khi bắt đầu |

---

## Phase 2: Nhập Query & Retrieve Chunks

> **Mục tiêu**: Human nhập query, hệ thống gọi Qdrant retrieve chunks.

### Tasks

- [x] **2.1 Query Input**
  - [x] Text input cho human nhập query
  - [x] Validate query không rỗng

- [x] **2.2 Chunk Retriever**
  - [x] Implement `ChunkRetriever` trong `retrieval/chunk_retriever.py`
  - [x] Embed query bằng model đã chọn
  - [x] Gọi Qdrant search trên collection(s) đã chọn
  - [x] Trả về `List[RetrievedChunk]`

- [x] **2.3 Hiển thị Chunks**
  - [x] Hiển thị chunk_id, score, nội dung text đầy đủ
  - [x] Sort theo score cao → thấp
  - [x] Expandable cho chunks dài

### ✅ Kết quả sau Phase 2

| Deliverable | Mô tả |
|-------------|--------|
| **Retrieve** | Gọi Qdrant, trả chunks theo config |
| **Display** | Hiển thị đầy đủ text để human đọc |

---

## Phase 3: Human Annotation

> **Mục tiêu**: Human tick relevant chunks, điền metadata.

### Tasks

- [x] **3.1 Tick Relevant Chunks**
  - [x] Checkbox mỗi chunk
  - [x] Lưu `relevant_doc_ids` dạng JSON array
  - [x] Validate ≥ 1 chunk được tick mới cho lưu

- [x] **3.2 Điền Metadata**
  - [x] Dropdown `query_type`: factoid / multi-hop / summarization / boolean
  - [x] Radio `difficulty`: easy / medium / hard
  - [x] Text area `expected_answer` (optional)

- [x] **3.3 Session Management**
  - [x] Auto-generate UUID v4 cho `id` (không cho phép sửa)
  - [x] Lưu annotation vào session
  - [x] Hiển thị progress: số query đã annotate + tổng relevant chunks
  - [x] Cho phép xem lại và sửa annotation trước khi export
  - [x] Session persistence (save/load JSON)
  - [x] Validate session trước khi export

- [x] **3.4 Pydantic Schema — `AnnotatedQuery`**
  - [x] Implement `AnnotatedQuery` model trong `models/schemas.py`
  - [x] Implement `RetrievedChunk` model
  - [x] Implement `AnnotationSession` trong `annotation/annotator.py`

### ✅ Kết quả sau Phase 3

| Deliverable | Mô tả |
|-------------|--------|
| **Annotation** | Tick relevant chunks + metadata đầy đủ |
| **Validation** | ≥ 1 chunk, UUID auto-generate |
| **Session** | Nhiều queries, xem lại, sửa trước export |

---

## Phase 4: Export CSV

> **Mục tiêu**: Xuất file CSV chuẩn cho evaluation pipeline.

### Tasks

- [x] **4.1 CSV Exporter**
  - [x] Implement `CSVExporter` trong `export/csv_exporter.py`
  - [x] Serialize `relevant_doc_ids` dạng JSON array string
  - [x] Các cột eval để trống (không null, không 0)
  - [x] Export tất cả queries trong session → 1 file CSV
  - [x] Append mode (ghi thêm vào file CSV đã có)
  - [x] Auto-generate filename với timestamp

- [x] **4.2 Review trước Export**
  - [x] Hiển thị preview table trước khi export
  - [x] Cho phép sửa annotation cuối cùng
  - [x] Hiển thị tổng số records sẽ export
  - [x] UUID uniqueness validation

- [x] **4.3 Pydantic Schema — `ExportRecord`**
  - [x] Implement `ExportRecord` model
  - [x] Đảm bảo đúng thứ tự 17 cột theo spec

### ✅ Kết quả sau Phase 4

| Deliverable | Mô tả |
|-------------|--------|
| **CSV File** | File CSV chuẩn 17 cột |
| **Clean Data** | Cột eval trống, UUID unique |
| **Review** | Preview trước khi download |

---

## Phase 5: UI (Streamlit App)

> **Mục tiêu**: Giao diện Streamlit kết nối tất cả phases.

### Tasks

- [x] **5.1 Layout & Navigation**
  - [x] Sidebar: config retrieval
  - [x] Main: nhập query → hiển thị chunks → annotate
  - [x] Tabs: Annotate / Review & Edit / Export CSV

- [x] **5.2 Streamlit App**
  - [x] Implement `app.py` tích hợp tất cả modules
  - [x] Session state management
  - [x] Download button cho CSV export
  - [x] Session save/load JSON
  - [x] Inline edit/delete annotations

### ✅ Kết quả sau Phase 5

| Deliverable | Mô tả |
|-------------|--------|
| **Full App** | Streamlit UI end-to-end |
| **Export** | Download CSV trực tiếp từ browser |
