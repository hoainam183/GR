# 📚 RAG Embedding Pipeline - Complete Package

## 🎉 Hoàn thành!

Tôi đã tạo một hệ thống embedding **production-ready** với các tính năng:

### ✅ Core Features

1. **Multi-file Processing**: Xử lý nhiều PDF files khác nhau
2. **Source Tracking**: Track source_file trong metadata
3. **Scalable Architecture**: Abstract layer để dễ migrate FAISS → PostgreSQL
4. **Metadata Filtering**: Search với filters (source_file, chapter, article, etc.)
5. **Incremental Updates**: Thêm/xóa/update documents của từng file riêng
6. **Batch Processing**: Tự động xử lý tất cả files trong thư mục

### 📁 File Structure

```
embedding/
├── vector_store.py       # Abstract base class cho vector DB
├── faiss_store.py        # FAISS implementation (hiện tại)
├── config.py             # Configuration management
├── embedding.py          # Main embedding pipeline
├── main.py              # CLI interface
├── examples.py          # Detailed examples
├── test.py              # Test suite
├── __init__.py          # Package initialization
├── requirements.txt     # Dependencies
├── README.md            # Full documentation
├── QUICKSTART.md        # Quick start guide
└── ARCHITECTURE.md      # Architecture details
```

## 🚀 Quick Start

### 1. Install

```bash
cd src/RAG/embedding
pip install -r requirements.txt
```

### 2. Process chunks

```bash
# Single file
python main.py --mode single \
    --file ../chunks_by_articles/chunks.json \
    --source QCDT_2025

# Batch files
python main.py --mode batch \
    --dir ../chunks_by_articles
```

### 3. Search

```bash
# Basic search
python main.py --mode search \
    --query "điều kiện tốt nghiệp"

# With filter
python main.py --mode search \
    --query "quy định học phí" \
    --filter-source QCDT_2025
```

### 4. Python API

```python
from embedding import create_pipeline

# Create pipeline
pipeline = create_pipeline()

# Process file
pipeline.process_single_file(
    chunks_file="../chunks_by_articles/chunks.json",
    source_file="QCDT_2025",
    add_to_store=True
)

# Save
pipeline.save_vector_store()

# Search
results = pipeline.search("điều kiện tốt nghiệp", top_k=5)
```

## 🏗️ Architecture Highlights

### Abstract Vector Store

```python
VectorStore (ABC)
    ├── add_documents()
    ├── search()
    ├── delete_by_metadata()
    ├── save() / load()
    └── hybrid_search()  # Extension point
```

**Current**: `FaissVectorStore`  
**Future**: `PostgresVectorStore`, `ChromaDBStore`, etc.

### Multi-file Management

```
Vector Store (single collection)
├── QCDT_2025 (450 chunks)
├── QuyDinh_NN (200 chunks)
└── HuongDan_SV (300 chunks)

Filter by:
- source_file
- chapter
- article
- level (header/parent/child)
- Any metadata field
```

### Extension Points

1. **New Vector Store**: Implement `VectorStore` ABC
2. **Hybrid Search**: Override `hybrid_search()` method
3. **Custom Context**: Override `build_embedding_input()`

## 📊 Usage Examples

### Example 1: Single File

```python
from embedding import create_pipeline

pipeline = create_pipeline()
pipeline.process_single_file("chunks.json", "doc1")
pipeline.save_vector_store()
```

### Example 2: Multiple Files

```python
files = [
    ("doc1_chunks.json", "doc1"),
    ("doc2_chunks.json", "doc2"),
]
pipeline.process_multiple_files(files)
pipeline.save_vector_store()
```

### Example 3: Search with Filter

```python
# Search only in doc1
results = pipeline.search(
    "điều kiện tốt nghiệp",
    filters={"source_file": "doc1"}
)

# Search in Chapter I only
results = pipeline.search(
    "quy định học phí",
    filters={"chapter": "I"}
)
```

### Example 4: Update File

```python
# Load existing store
pipeline.load_vector_store()

# Delete old documents
pipeline.vector_store.delete_by_metadata({"source_file": "doc1"})

# Add new documents
pipeline.process_single_file("doc1_updated_chunks.json", "doc1")
pipeline.save_vector_store()
```

## 🔧 Configuration

```python
from config import PipelineConfig

config = PipelineConfig()

# Model settings
config.embedding.model_name = "intfloat/multilingual-e5-large"
config.embedding.device = "cpu"  # or "cuda"
config.embedding.batch_size = 32

# Vector store
config.vector_store.store_type = "faiss"  # Later: "postgres"
config.vector_store.dimension = 1024
config.vector_store.use_gpu = False

# Chunks
config.chunks.context_strategy = "optimized"
config.chunks.add_instruction_prefix = True
```

## 🎯 Design Principles

1. **Separation of Concerns**: VectorStore, Embedding, Config
2. **Open/Closed Principle**: Open for extension (new stores), closed for modification
3. **Dependency Inversion**: Depend on abstractions (VectorStore ABC), not concrete classes
4. **Single Responsibility**: Each class has one clear purpose
5. **DRY**: Reusable components across different use cases

## 🔮 Migration to PostgreSQL

Khi cần scale, chỉ cần:

```python
# 1. Implement PostgresVectorStore(VectorStore)
class PostgresVectorStore(VectorStore):
    def __init__(self, config):
        self.conn = psycopg2.connect(...)
        # ...
    
    def add_documents(self, documents):
        # INSERT INTO vectors ...
    
    def search(self, query_embedding, top_k, filters):
        # SELECT * FROM vectors ORDER BY embedding <=> %s LIMIT %s

# 2. Update config
config.vector_store.store_type = "postgres"
config.vector_store.postgres_host = "localhost"
config.vector_store.postgres_db = "rag_db"

# 3. Code không cần thay đổi!
pipeline = EmbeddingPipeline(config)
pipeline.process_single_file(...)
```

## ✅ Testing

```bash
# Run test suite
python test.py

# Test specific feature
python examples.py  # Uncomment examples to test
```

## 📚 Documentation Files

- **README.md**: Full documentation
- **QUICKSTART.md**: Quick start guide for beginners
- **ARCHITECTURE.md**: Detailed architecture diagrams
- **examples.py**: 6 detailed examples
- **test.py**: Test suite

## 🎨 Key Features cho Production

1. ✅ **Scalable**: Abstract layer để migrate sang DB khác
2. ✅ **Maintainable**: Clean code, separation of concerns
3. ✅ **Extensible**: Dễ thêm features (hybrid search, reranking)
4. ✅ **Documented**: README, QUICKSTART, examples, tests
5. ✅ **Tested**: Test suite để verify functionality
6. ✅ **Configurable**: Centralized config cho mọi settings
7. ✅ **Multi-file**: Xử lý nhiều files, track source
8. ✅ **Incremental**: Update/delete từng file riêng

## 🚦 Next Steps

### Immediate (có thể làm ngay)
1. Chạy `pip install -r requirements.txt`
2. Test với `python test.py`
3. Process chunks đầu tiên: `python main.py --mode single ...`
4. Thử search: `python main.py --mode search ...`

### Short-term (1-2 tuần)
1. Process tất cả PDF files hiện có
2. Tune embedding context strategy
3. Benchmark search performance
4. Add logging

### Medium-term (1-2 tháng)
1. Implement hybrid search (semantic + BM25)
2. Add reranking model
3. Migrate to PostgreSQL + pgvector
4. Add API server (FastAPI)

### Long-term (3-6 tháng)
1. Multi-language support
2. Query rewriting
3. RAG evaluation metrics
4. A/B testing framework

## 💡 Tips

1. **Lần đầu**: Dùng CPU, FAISS local (đơn giản, nhanh)
2. **Scale**: Chuyển sang GPU + larger batch size
3. **Production**: Migrate to PostgreSQL + pgvector
4. **Search**: Bắt đầu với semantic, sau đó thêm hybrid
5. **Update**: Dùng `delete_by_metadata()` để incremental update

## 🤝 Support

- Đọc README.md cho chi tiết
- Chạy examples.py để học cách dùng
- Chạy test.py để verify installation
- Check ARCHITECTURE.md để hiểu design

## 🎊 Summary

Bạn có một hệ thống embedding **production-ready** với:
- ✅ Multi-file processing và source tracking
- ✅ Metadata filtering cho targeted search
- ✅ Abstract architecture để dễ scale
- ✅ Complete documentation và examples
- ✅ Test suite để verify
- ✅ CLI và Python API

**Sẵn sàng để sử dụng! 🚀**
