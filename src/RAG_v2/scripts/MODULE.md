# Module: `scripts` — Standalone CLI Tools & Data Pipelines

## Tổng quan

Module `scripts` chứa các **standalone CLI scripts** để quản lý data stores (indexing, crawling, migration). Các file này không tham gia vào runtime RAG query pipeline — chúng chỉ được chạy trực tiếp từ command line hoặc qua APScheduler.

---

## Cấu trúc file

```
scripts/
├── __init__.py          # Module init
├── auto_crawler.py      # AutoCrawlPipeline — crawl → chunk → index → retention
├── index_kehoach.py     # Indexing kế hoạch học kỳ → Qdrant
├── index_quydinh.py     # Indexing quy định → Qdrant
├── index_stsv.py        # Indexing hỗ trợ sinh viên → Qdrant
├── index_to_es.py       # Indexing documents → Elasticsearch
├── search_multi.py      # Utility search functions (standalone)
└── update_metadata.py   # Cập nhật metadata cho existing documents
```

---

## Nhiệm vụ chi tiết

### `auto_crawler.py` — `AutoCrawlPipeline`

**Nhiệm vụ:** Tự động crawl bài viết mới từ ctt.hust.edu.vn hàng ngày, làm sạch, chunk, embed và index vào Qdrant + Elasticsearch.

**Classes:**
- `KehoachCrawler` — incremental crawl (chỉ lấy bài mới, dựa trên baiviet_id)
- `ChunkProcessor` — wrapper quanh `KeHoachChunker`
- `DualIndexer` — embed BGE-M3 + E5, upsert Qdrant + ES
- `RetentionManager` — xoá bài >N tháng khỏi JSON, chunks, Qdrant, ES
- `AutoCrawlPipeline` — orchestrator: crawl → chunk → index → retention → notify

**Pipeline flow:**
```
Crawl (incremental) → Save JSON → Chunk → Index (Qdrant+ES) → Retention → Notify
```

**Scheduling:** APScheduler cron job trong FastAPI lifespan (mặc định 02:00 hàng ngày).

**CLI:** `python -m scripts.auto_crawler` (standalone) hoặc `--dry` (dry-run).

---

### `index_kehoach.py` / `index_quydinh.py` / `index_stsv.py`

**Nhiệm vụ:** Scripts indexing dữ liệu vào Qdrant cho từng collection riêng.

**Usage:**
```bash
python -m scripts.index_kehoach
python -m scripts.index_quydinh
python -m scripts.index_stsv
```

---

### `index_to_es.py`

**Nhiệm vụ:** Indexing documents vào Elasticsearch cho keyword (BM25) search.

---

### `update_metadata.py`

**Nhiệm vụ:** Cập nhật metadata cho existing documents trong Qdrant/ES (migration utility).

---

## Nguồn gốc

| File | Vị trí cũ | Lý do di chuyển |
|------|-----------|-----------------|
| `auto_crawler.py` | `pipeline/` | Data pipeline, không phải query pipeline |
| `index_kehoach.py` | `pipeline/` | Standalone CLI script |
| `index_quydinh.py` | `pipeline/` | Standalone CLI script |
| `index_stsv.py` | `pipeline/` | Standalone CLI script |
| `update_metadata.py` | `pipeline/` | Standalone CLI script |
| `index_to_es.py` | `retrieval/` | Standalone CLI script |
| `search_multi.py` | `retrieval/` | Standalone utility script |
