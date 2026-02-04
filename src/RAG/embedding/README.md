# Embedding Module

Module tạo embeddings và lưu trữ vector cho RAG system.

## 📁 Cấu trúc thư mục

```
embedding/
├── __init__.py           # Module exports
├── config.py             # Centralized configuration
├── embedding.py          # Core EmbeddingPipeline class
├── vector_store.py       # Abstract vector store interface
├── faiss_store.py        # FAISS implementation
├── search.py             # Search utilities
├── main.py               # CLI interface
├── run_embedding.py      # Python script examples
├── run_embedding_v2.py   # BaseProcessor version (with skip logic)
├── migrate_olmocr.py     # Migration script for olmOCR chunks
├── QUICKSTART.md         # Quick start guide
└── vector_store/         # Stored vector indices
```

## 🚀 Quick Start

### 1. Cài đặt dependencies

```bash
pip install langchain-huggingface faiss-cpu tqdm
```

### 2. Xử lý chunks và tạo embeddings

```python
from embedding import create_pipeline

# Tạo pipeline
pipeline = create_pipeline()

# Xử lý single file
documents = pipeline.process_single_file(
    chunks_file="../chunks_by_articles/QCDT_2025_chunks.json",
    source_file="QCDT_2025",
    add_to_store=True
)

# Save vector store
pipeline.save_vector_store()
print(f"✅ Processed {len(documents)} chunks")
```

### 3. Batch processing nhiều files

```python
from pathlib import Path
from embedding import create_pipeline

pipeline = create_pipeline()

# Tìm tất cả files chunks
chunks_dir = Path("../chunks_by_articles")
chunk_files = list(chunks_dir.glob("*_chunks.json"))

# Prepare for processing
files_to_process = [
    (str(f), f.stem.replace("_chunks", ""))
    for f in chunk_files
]

# Process all
all_docs = pipeline.process_multiple_files(files_to_process)
pipeline.save_vector_store()
```

### 4. Search trong vector store

```python
from embedding import create_pipeline

pipeline = create_pipeline()
pipeline.load_vector_store()

# Basic search
results = pipeline.search("điều kiện tốt nghiệp", top_k=5)

for result in results:
    print(f"Score: {result.score:.4f}")
    print(f"Source: {result.metadata.get('source_file')}")
    print(f"Content: {result.content[:200]}...")
    print()
```

## 📖 Command Line Interface

```bash
# Xử lý 1 file
python main.py --mode single \
    --file ../chunks_by_articles/chunks.json \
    --source QCDT_2025

# Xử lý batch
python main.py --mode batch \
    --dir ../chunks_by_articles

# Search
python main.py --mode search \
    --query "điều kiện tốt nghiệp" \
    --top-k 5

# Search với filter
python main.py --mode search \
    --query "quy định học phí" \
    --filter-source QCDT_2025
```

## ⚙️ Configuration

Configuration được quản lý tập trung trong `config.py`:

```python
from config import PipelineConfig

config = PipelineConfig()

# Embedding model
config.embedding.model_name = "intfloat/multilingual-e5-large"
config.embedding.device = "cuda"  # hoặc "cpu"
config.embedding.batch_size = 32

# Vector store
config.vector_store.store_type = "faiss"
config.vector_store.dimension = 1024
config.vector_store.faiss_index_type = "IndexFlatIP"

# Paths
config.chunks.input_chunks_dir = "../chunks_by_articles"
config.chunks.vector_store_dir = "./vector_store"
```

### Config từ file JSON

```python
config = PipelineConfig.from_dict({
    "embedding": {
        "model_name": "intfloat/multilingual-e5-large",
        "device": "cuda",
        "batch_size": 64
    },
    "vector_store": {
        "store_type": "faiss",
        "dimension": 1024
    }
})
```

## 🔍 Search với Metadata Filters

```python
# Filter by source file
results = pipeline.search(
    "điều kiện tốt nghiệp",
    filters={"source_file": "QCDT_2025"}
)

# Filter by chapter
results = pipeline.search(
    "quy định học phí",
    filters={"chapter": "II"}
)

# Filter by level (parent/child)
results = pipeline.search(
    "học bổng khuyến khích",
    filters={"level": "parent"}
)

# Multiple filters
results = pipeline.search(
    "quy định",
    filters={
        "source_file": "QCDT_2025",
        "level": "child"
    }
)
```

## 📊 Vector Store Statistics

```python
pipeline = create_pipeline()
pipeline.load_vector_store()

stats = pipeline.vector_store.get_statistics()
print(f"Total documents: {stats['total_documents']}")
print(f"Dimension: {stats['dimension']}")
print(f"Source files: {list(stats['source_files'].keys())}")

# Chi tiết từng source
for source, count in stats['source_files'].items():
    print(f"  - {source}: {count} chunks")
```

## 🔄 Update/Delete Documents

```python
pipeline = create_pipeline()
pipeline.load_vector_store()

# Xóa documents của một source
deleted = pipeline.vector_store.delete_by_metadata(
    {"source_file": "QCDT_2025"}
)
print(f"Deleted {deleted} documents")

# Thêm lại documents mới
pipeline.process_single_file(
    chunks_file="../chunks_by_articles/QCDT_2025_updated_chunks.json",
    source_file="QCDT_2025",
    add_to_store=True
)

pipeline.save_vector_store()
```

## 🏗️ Architecture

### EmbeddingPipeline

Core class xử lý toàn bộ workflow:
- Load chunks từ JSON files
- Build embedding input với context hierarchy
- Tạo embeddings với HuggingFace model
- Lưu vào vector store (FAISS)
- Search với metadata filters

### Document Structure

```python
@dataclass
class Document:
    chunk_id: str           # Unique ID
    content: str            # Original content
    embedding: np.ndarray   # Vector embedding
    metadata: Dict          # chapter, article, source_file, etc.
```

### Embedding Input Format (E5 Model)

```
passage: CHƯƠNG II: QUẢN LÝ VÀ TỔ CHỨC
Điều 15. Tiêu đề điều
Khoản 2

Nội dung chunk...
```

## 📦 Supported Vector Stores

### FAISS (Default)
- Local, fast, no setup required
- Good for development và small-medium scale

```python
config.vector_store.store_type = "faiss"
config.vector_store.faiss_index_type = "IndexFlatIP"  # Cosine similarity
```

### PostgreSQL (Coming soon)
- Production-ready, scalable
- Better for large-scale deployments

## 🛠️ Advanced Usage

### Custom Pipeline với skip logic

```python
from run_embedding_v2 import EmbeddingProcessor

processor = EmbeddingProcessor(
    pipeline=create_pipeline(),
    chunks_dir=Path("../chunks_by_articles"),
    force_reprocess=False  # Skip files already in store
)

results = processor.process_directory(Path("../chunks_by_articles"))
```

### Migration từ Docling sang olmOCR

```python
from migrate_olmocr import main as migrate_main

# Run migration
migrate_main()
```

### Interactive Search

```python
from search import interactive_search

# Chạy chế độ tìm kiếm tương tác
interactive_search()
```

## 📝 Best Practices

1. **Sử dụng GPU** nếu có: set `device = "cuda"` và cài `faiss-gpu`
2. **Batch size**: Điều chỉnh theo VRAM (16 cho 4GB, 64 cho 16GB)
3. **Incremental updates**: Load store → delete old → add new → save
4. **Backup vector store**: Copy thư mục `vector_store/` trước khi update lớn
5. **Sử dụng run_embedding_v2.py** cho production (có skip logic)

## 🐛 Troubleshooting

### Lỗi: Vector store not found
```bash
# Chạy embedding trước
python main.py --mode batch --dir ../chunks_by_articles
```

### Lỗi: Out of memory
```python
config.embedding.batch_size = 16  # Giảm từ 32
```

### Lỗi: Model download slow
```bash
# Set mirror nếu ở Việt Nam
export HF_ENDPOINT=https://hf-mirror.com
```

### Lỗi: FAISS import error
```bash
pip install faiss-cpu
# hoặc với GPU
pip install faiss-gpu
```
