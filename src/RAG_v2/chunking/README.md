# Chunking Module

Module phân chia văn bản pháp luật Việt Nam thành các chunks cho RAG system.

## 📁 Cấu trúc thư mục

```
chunking/
├── main.py                    # Pipeline chính cho single/batch processing
├── main_v2.py                 # Pipeline sử dụng BaseProcessor framework
├── standalone_pipeline.py     # Pipeline độc lập (PDF → Chunks)
├── batch_standalone.py        # Batch processing cho standalone
├── batch_process_pymupdf.py   # Batch processing cho PyMuPDF format
└── chunker/                   # Core chunker classes
    ├── base_chunker.py
    ├── chunking.py
    ├── hierarchical_legal_chunker.py        # Docling format
    ├── hierarchical_legal_chunker_pymupdf.py # PyMuPDF format
    └── olmocr_legal_chunker.py              # OLM OCR format
```

## 🚀 Quick Start

### 1. Chunking một file Markdown

```python
from main import main_pipeline

# Sử dụng hierarchical chunker cho Docling format
chunks, stats = main_pipeline(
    markdown_path="path/to/document.md",
    output_dir="../chunks_by_articles",
    chunker_type="hierarchical"  # hoặc "olmocr"
)

print(f"Total chunks: {stats['total_chunks']}")
```

### 2. Chunking nhiều files trong thư mục

```python
from main import process_folder

# Xử lý tất cả files .md trong thư mục
process_folder(
    input_dir="../output_docling_clean",
    output_dir="../chunks_by_articles",
    chunker_type="hierarchical",
    pattern="*.md"
)
```

### 3. Sử dụng ChunkingProcessor (với skip logic)

```python
from main_v2 import ChunkingProcessor
from pathlib import Path

# Tự động skip files đã được xử lý
processor = ChunkingProcessor(
    output_dir=Path("../chunks_by_articles"),
    min_child_size=500,
    max_child_size=1000,
    parent_size_limit=4000,
    chunk_overlap=150
)

# Xử lý directory
results = processor.process_directory(Path("../output_docling_clean"))
```

## 📦 Chunker Types

### 1. ArticleLevelLegalChunker (hierarchical)
- **Dùng cho**: Văn bản từ Docling OCR (có markdown headings `#`, `##`)
- **Cấu trúc**: Parent-Child architecture
  - **Header**: 1 chunk cho toàn bộ header document
  - **Parent**: 1 điều hoặc nhiều điều nhỏ merged
  - **Child**: Các khoản trong điều (~500-1000 chars)

```python
from chunker.hierarchical_legal_chunker import ArticleLevelLegalChunker

chunker = ArticleLevelLegalChunker(
    min_child_size=500,      # Min size cho child chunks
    max_child_size=1000,     # Max size cho child chunks
    parent_size_limit=4000,  # Max size cho parent chunks
    chunk_overlap=150        # Overlap giữa các chunks
)

chunks, stats = chunker.chunk_document(markdown_text)
chunker.save_chunks(chunks, "output.json")
```

### 2. OlmOcrLegalChunker (olmocr)
- **Dùng cho**: Văn bản từ OLM OCR (plain text, không có markdown headings)
- **Cấu trúc**: Tương tự hierarchical nhưng detect patterns khác

```python
from chunker.olmocr_legal_chunker import OlmOcrLegalChunker

chunker = OlmOcrLegalChunker(
    min_child_size=300,
    max_child_size=1000,
    parent_size_limit=4000,
    chunk_overlap=100
)

chunks, stats = chunker.chunk_document(markdown_text)
```

### 3. ArticleLegalChunkerPyMuPDF
- **Dùng cho**: Văn bản từ PyMuPDF4LLM (bold-based format `**text**`)

```python
from chunker.hierarchical_legal_chunker_pymupdf import ArticleLegalChunkerPyMuPDF

chunker = ArticleLegalChunkerPyMuPDF(
    min_child_size=500,
    max_child_size=1000,
    parent_size_limit=4000,
    split_threshold=1500,  # Chỉ split articles > 1500 chars
    chunk_overlap=0        # No overlap cho legal docs
)

chunks, stats = chunker.chunk_document(content)
```

## 📊 Output Format

Mỗi chunk trong output JSON có cấu trúc:

```json
{
    "id": "unique-uuid",
    "readable_id": "dieu_15_khoan_2",
    "content": "Nội dung chunk...",
    "parent_id": "parent-uuid",
    "metadata": {
        "level": "child",
        "chapter": "II",
        "chapter_full": "CHƯƠNG II: QUẢN LÝ VÀ TỔ CHỨC",
        "article": "15",
        "article_full": "Điều 15. Tiêu đề điều",
        "clause": "2",
        "chunk_size": 856,
        "has_table": false
    }
}
```

## 📈 Statistics

Sau khi chunking, bạn sẽ nhận được thống kê:

```python
stats = {
    "total_chunks": 150,
    "parent_chunks": 45,
    "child_chunks": 105,
    "by_level": {"header": 1, "parent": 45, "child": 104},
    "avg_chunk_size": 723,
    "min_chunk_size": 156,
    "max_chunk_size": 2341,
    "chunks_with_tables": 12,
    "appendix_chunks": 3
}
```

## 🔧 Command Line Usage

```bash
# Single file
python main.py

# Batch processing với PyMuPDF format
python batch_process_pymupdf.py

# Standalone pipeline (PDF → Chunks)
python standalone_pipeline.py "document.pdf"

# Batch standalone
python batch_standalone.py "d:/pdfs/" "./output"

python main.py --input <input_dir> --output <output_dir> --chunker parent_child --pattern "*_fix.md"
python main.py --input "d:\GR\src\RAG\data\ctdt\vatlieu\clean_data" --output "d:\GR\src\RAG\data\ctdt\vatlieu\chunks_recursive_parent_child" --chunker recursive --pattern "*_fix.md"
python main.py --input "D:\GR\src\RAG_v2\data\quydinh\olmocr\cleaned" --output "D:\GR\src\RAG_v2\data\quydinh\olmocr\chunks_recursive_parent_child_3" --chunker recursive --pattern "*.md"     
python main.py --chunker stsv --input path/to/stsv
python main.py --file ../data/kehoach/output_full.json --output ../data/kehoach/chunks --chunker kehoach
```

## 📝 Best Practices

1. **Chọn đúng chunker type** dựa trên nguồn OCR của document
2. **Điều chỉnh size parameters** phù hợp với use case:
   - Retrieval: chunks nhỏ hơn (500-800 chars)
   - Generation: chunks lớn hơn (800-1200 chars)
3. **Kiểm tra output** với một vài files trước khi batch processing
4. **Sử dụng main_v2.py** cho production (có skip logic, tránh re-process)
