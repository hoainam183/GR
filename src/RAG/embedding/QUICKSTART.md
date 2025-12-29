# Quick Start Guide

## Bước 1: Cài đặt dependencies

```bash
cd src/RAG/embedding
pip install -r requirements.txt
```

## Bước 2: Xử lý chunks đầu tiên

### Option A: Sử dụng main.py (đơn giản)

```bash
# Xử lý 1 file
python main.py --mode single \
    --file ../chunks_by_articles/chunks.json \
    --source QCDT_2025

# Xử lý tất cả files trong thư mục
python main.py --mode batch \
    --dir ../chunks_by_articles

# Search
python main.py --mode search \
    --query "điều kiện tốt nghiệp" \
    --top-k 5

# Search với filter
python main.py --mode search \
    --query "quy định về học phí" \
    --filter-source QCDT_2025 \
    --top-k 3
```

### Option B: Sử dụng Python API (linh hoạt hơn)

```python
from embedding import create_pipeline

# 1. Create pipeline
pipeline = create_pipeline()

# 2. Process chunks
documents = pipeline.process_single_file(
    chunks_file="../chunks_by_articles/chunks.json",
    source_file="QCDT_2025",
    add_to_store=True
)

# 3. Save vector store
pipeline.save_vector_store()

# 4. Search
results = pipeline.search("điều kiện tốt nghiệp", top_k=5)
for result in results:
    print(f"Score: {result.score}")
    print(f"Content: {result.content[:200]}...")
```

## Bước 3: Thêm nhiều files khác

```python
from embedding import create_pipeline

pipeline = create_pipeline()

# Load vector store đã có
pipeline.load_vector_store()

# Thêm file mới
pipeline.process_single_file(
    chunks_file="../chunks_by_articles/QuyDinh_NN_chunks.json",
    source_file="QuyDinh_NgoaiNgu",
    add_to_store=True
)

# Save lại
pipeline.save_vector_store()
```

## Bước 4: Search với filters

```python
# Search trong tất cả documents
results = pipeline.search("điều kiện tốt nghiệp", top_k=5)

# Search chỉ trong 1 file
results = pipeline.search(
    "điều kiện tốt nghiệp",
    filters={"source_file": "QCDT_2025"}
)

# Search chỉ trong 1 chapter
results = pipeline.search(
    "quy định về học phí",
    filters={"chapter": "I"}
)

# Multi-filter
results = pipeline.search(
    "quy định về học phí",
    filters={
        "source_file": "QCDT_2025",
        "level": "parent"
    }
)
```

## Bước 5: Update khi có thay đổi

```python
pipeline = create_pipeline()
pipeline.load_vector_store()

# Xóa documents cũ của file cần update
pipeline.vector_store.delete_by_metadata({"source_file": "QCDT_2025"})

# Thêm documents mới
pipeline.process_single_file(
    chunks_file="../chunks_by_articles/QCDT_2025_updated_chunks.json",
    source_file="QCDT_2025",
    add_to_store=True
)

pipeline.save_vector_store()
```

## Các câu lệnh hữu ích

### Xem thống kê vector store

```python
from embedding import create_pipeline

pipeline = create_pipeline()
pipeline.load_vector_store()

stats = pipeline.vector_store.get_statistics()
print(f"Total documents: {stats['total_documents']}")
print(f"Source files: {stats['source_files']}")
```

### Batch processing tất cả files

```python
from pathlib import Path
from embedding import create_pipeline

pipeline = create_pipeline()

# Tìm tất cả files chunks
chunks_dir = Path("../chunks_by_articles")
chunk_files = list(chunks_dir.glob("*_chunks.json"))

# Prepare list
files_to_process = [
    (str(f), f.stem.replace("_chunks", "")) 
    for f in chunk_files
]

# Process all
pipeline.process_multiple_files(files_to_process)
pipeline.save_vector_store()
```

## Tips

1. **Lần đầu xử lý nhiều files**: Dùng `--mode batch` hoặc `process_multiple_files()`
2. **Thêm file mới**: Load vector store trước, rồi `process_single_file()`
3. **Update file**: Xóa bằng `delete_by_metadata()` trước khi thêm lại
4. **Search nhanh**: Dùng metadata filters để giảm search space
5. **GPU**: Đổi `config.embedding.device = "cuda"` và cài `faiss-gpu`

## Troubleshooting

### Lỗi: Vector store not found
```python
# Chạy embedding trước
python main.py --mode single --file chunks.json --source doc1
```

### Lỗi: Out of memory
```python
# Giảm batch size
from embedding import EmbeddingPipeline
from config import PipelineConfig

config = PipelineConfig()
config.embedding.batch_size = 16  # giảm từ 32
pipeline = EmbeddingPipeline(config)
```

### Lỗi: Model download slow
```python
# Set HF_ENDPOINT nếu ở Việt Nam
import os
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
```

## Next Steps

- Đọc [README.md](README.md) để hiểu chi tiết architecture
- Xem [examples.py](examples.py) để có thêm examples
- Customize config trong [config.py](config.py)
- Scale lên PostgreSQL khi cần (coming soon!)
