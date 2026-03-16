# 📊 RAG Evaluation Dataset Builder

> Công cụ hỗ trợ human xây dựng **ground truth dataset** để đánh giá hệ thống RAG.

## Cấu trúc thư mục

```
eval_dataset_builder/
├── app.py                     ← Entry point (Streamlit)
├── config/
│   └── retrieval_config.py    ← Kết nối Qdrant, config management
├── retrieval/
│   └── chunk_retriever.py     ← Embed query + search Qdrant (3 modes)
├── annotation/
│   └── annotator.py           ← Session management, CRUD, save/load
├── models/
│   └── schemas.py             ← Pydantic models (4 models, 3 enums)
├── export/
│   └── csv_exporter.py        ← Export CSV chuẩn 17 cột
├── data/                      ← Output: CSV files, session JSONs
├── development_guide.md
├── phase_tasks.md
└── README.md
```

## Yêu cầu hệ thống

### Prerequisites
- **Python 3.9+**
- **Qdrant** đang chạy (Docker hoặc local)
- **Embedding models** đã tải (BGE-M3 và/hoặc E5)

### Dependencies

```bash
# Core
pip install streamlit pydantic qdrant-client

# Embedding models (cần cho retrieve)
pip install FlagEmbedding sentence-transformers torch

# Đã có sẵn nếu setup RAG_v2
pip install transformers numpy
```

## Hướng dẫn chạy

### 1. Đảm bảo Qdrant đang chạy

```bash
# Nếu dùng Docker (từ RAG_v2/)
cd d:\GR\src\RAG_v2
docker-compose up -d qdrant

# Kiểm tra
curl http://localhost:6333/collections
```

### 2. Chạy Streamlit App

```bash
# QUAN TRỌNG: phải chạy từ thư mục RAG_v2/
cd d:\GR\src\RAG_v2

# Chạy app
streamlit run eval_dataset_builder/app.py
```

App sẽ mở tại `http://localhost:8501`

### 3. Sử dụng

#### Bước 1 — Sidebar: Cấu hình
1. Nhập Qdrant host/port → click **🔌 Kết nối Qdrant**
2. Chọn collection(s) từ dropdown
3. Chọn top_k và embedding model
4. Click **✅ Áp dụng Config**

#### Bước 2 — Tab Annotate: Query & Retrieve
1. Nhập câu hỏi vào text area
2. Click **🔍 Retrieve Chunks**
3. Xem từng chunk (text đầy đủ, score, metadata)
4. ✅ Tick chunks relevant
5. Chọn query_type, difficulty, viết expected_answer (optional)
6. Click **💾 Lưu Annotation**

#### Bước 3 — Tab Review: Xem lại & Sửa
- Xem danh sách tất cả annotations
- Sửa query_type, difficulty, expected_answer inline
- Xóa annotation nếu cần
- Lưu/Load session (JSON) để tiếp tục sau

#### Bước 4 — Tab Export: Xuất CSV
- Preview table trước khi export
- Click **📥 Download CSV** để tải file
- Hoặc lưu trực tiếp vào đĩa

## CSV Format

| # | Cột | Ghi chú |
|---|-----|---------|
| 1 | `id` | UUID v4, auto-generate |
| 2 | `query` | Câu hỏi |
| 3 | `query_type` | factoid / multi-hop / summarization / boolean |
| 4 | `difficulty` | easy / medium / hard |
| 5 | `expected_answer` | Optional |
| 6 | `relevant_doc_ids` | JSON array: `["id1","id2"]` |
| 7 | `top_k` | Config |
| 8 | `embedding_model` | e5 / bge_m3 / hybrid |
| 9-17 | Eval columns | **Để trống** (điền ở eval phase) |

## Embedding Models

| Model | Vector Name | Dimension | Ghi chú |
|-------|------------|-----------|---------|
| E5 Multilingual | `e5` | 1024 | Nhanh, query prefix `"query: "` |
| BGE-M3 | `bge_m3` | 1024 | Dense + sparse |
| Hybrid | cả 2 | 1024 | Weighted score fusion |

## Troubleshooting

| Lỗi | Nguyên nhân | Giải pháp |
|-----|------------|-----------|
| `Connection refused` | Qdrant không chạy | `docker-compose up -d qdrant` |
| `Collection not found` | Collection chưa tạo | Index documents vào Qdrant trước |
| `CUDA out of memory` | GPU không đủ RAM | Set `device="cpu"` trong embedder |
| `ModuleNotFoundError` | Chạy sai thư mục | `cd d:\GR\src\RAG_v2` rồi chạy lại |
