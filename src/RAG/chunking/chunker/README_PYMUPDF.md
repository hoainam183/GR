# PyMuPDF4LLM Legal Document Chunker

## 📌 Overview

Chunker chuyên dụng cho văn bản pháp luật Việt Nam được convert bởi **PyMuPDF4LLM**, xử lý format bold (`**text**`) thay vì markdown headers (`#`).

## 🔑 Key Differences from Docling Version

| Aspect | Docling | PyMuPDF4LLM |
|--------|---------|-------------|
| Chapter format | `# CHƯƠNG I` | `**CHƯƠNG I**` |
| Article format | `## Điều 1` | `**Điều 1.**` |
| Detection method | Direct regex on `#` | Strip `**` first, then regex |
| Metadata | `source_format: 'docling'` | `source_format: 'pymupdf4llm'` |

## 🏗️ Architecture

**Parent-Child chunking strategy:**

```
Document
├── Header (1 chunk)
└── Body
    ├── Parent: Điều 1 (full article)
    │   ├── Child 1: Khoản 1-2
    │   └── Child 2: Khoản 3-4
    ├── Parent: Điều 2 (full article)
    │   └── Child 1: Full article (if small)
    └── ...
```

### Features:
- ✅ **Chapter context** preserved in every chunk
- ✅ **Table protection** - tables never split
- ✅ **Parent-child IDs** for retrieval optimization
- ✅ **Nested structure** handling (khoản, điểm)
- ✅ **Size control**: 500-1000 chars per child chunk

## 📦 Installation

```bash
# No additional dependencies needed beyond base Python
pip install langchain-text-splitters  # Optional for fallback
```

## 🚀 Quick Start

### Basic Usage

```python
from chunker.hierarchical_legal_chunker_pymupdf import ArticleLegalChunkerPyMuPDF

# Initialize chunker
chunker = ArticleLegalChunkerPyMuPDF(
    min_child_size=500,      # Min child chunk size
    max_child_size=1000,     # Max child chunk size
    parent_size_limit=4000,  # Max parent size before warning
    chunk_overlap=150,       # Overlap between chunks
)

# Load document
with open("document.md", "r", encoding="utf-8") as f:
    text = f.read()

# Process document
chunks, stats = chunker.chunk_document(text)

# Access chunks
for chunk in chunks:
    print(f"ID: {chunk['readable_id']}")
    print(f"Level: {chunk['metadata']['level']}")
    print(f"Content: {chunk['content'][:100]}...")
    print(f"Parent: {chunk['parent_id']}")
    print()

# Save chunks
chunker.save_chunks(chunks, "output/chunks.json")
```

### Test Script

```bash
cd src/RAG/chunking
python test_pymupdf_chunker.py
```

## 📊 Output Format

### Chunk Structure

```json
{
  "content": "CHƯƠNG I\n\nĐiều 1. Title\n1. Khoản một...",
  "metadata": {
    "doc_type": "legal_document",
    "level": "parent",  // or "child" or "header"
    "chapter": "I",
    "chapter_full": "CHƯƠNG I: TÊN CHƯƠNG",
    "article": "Điều 1",
    "article_full": "Điều 1. Phạm vi điều chỉnh",
    "chunk_size": 742,
    "has_table": false,
    "source_format": "pymupdf4llm"
  },
  "chunk_id": 5,
  "readable_id": "parent_cI_a1",
  "parent_id": null
}
```

### Statistics

```json
{
  "total_chunks": 40,
  "total_chars": 21439,
  "avg_chunk_size": 536,
  "min_chunk_size": 21,
  "max_chunk_size": 1788,
  "by_level": {
    "header": 1,
    "parent": 19,
    "child": 20
  },
  "parent_chunks": 19,
  "child_chunks": 20,
  "chunks_with_tables": 2,
  "size_distribution": {
    "0-500": 18,
    "500-1000": 19,
    "1000-2000": 3,
    "2000-3000": 0,
    "3000+": 0
  }
}
```

## 🎯 Detection Patterns

### PyMuPDF4LLM Format Detection

```python
# Chapter heading
**CHƯƠNG I**
**Chương II: QUẢN LÝ**

# Article heading
**Điều 1.**
**Điều 1. Phạm vi điều chỉnh**

# Numbered points (khoản)
1. Khoản một của điều
2. Khoản hai của điều

# Lettered points (điểm)
a) Điểm a của khoản
b) Điểm b của khoản

# Nested structure
**Điều 5.**
1. Khoản 1
   a) Điểm a của khoản 1
   b) Điểm b của khoản 1
2. Khoản 2
```

## 🔧 Configuration Options

```python
chunker = ArticleLegalChunkerPyMuPDF(
    min_child_size=500,        # Minimum child chunk size (chars)
    max_child_size=1000,       # Maximum child chunk size (chars)
    parent_size_limit=4000,    # Warning threshold for parent size
    chunk_overlap=150,         # Overlap between sequential chunks
)
```

### Recommended Settings

| Document Type | min_child | max_child | overlap |
|---------------|-----------|-----------|---------|
| Short regulations | 300 | 800 | 100 |
| **Standard (default)** | **500** | **1000** | **150** |
| Long legal codes | 700 | 1500 | 200 |

## 📝 Usage Examples

### Example 1: Process Single Document

```python
from pathlib import Path
from chunker.hierarchical_legal_chunker_pymupdf import ArticleLegalChunkerPyMuPDF

# Setup
input_file = Path("output_pymupdf4llm/quy_dinh.md")
output_file = Path("chunks/quy_dinh_chunks.json")

# Read
with open(input_file, "r", encoding="utf-8") as f:
    text = f.read()

# Chunk
chunker = ArticleLegalChunkerPyMuPDF()
chunks, stats = chunker.chunk_document(text)

# Save
chunker.save_chunks(chunks, output_file)

print(f"✅ Created {stats['total_chunks']} chunks")
```

### Example 2: Batch Process Multiple Documents

```python
from pathlib import Path
from chunker.hierarchical_legal_chunker_pymupdf import ArticleLegalChunkerPyMuPDF

input_dir = Path("output_pymupdf4llm")
output_dir = Path("chunks_by_articles")

chunker = ArticleLegalChunkerPyMuPDF()

for md_file in input_dir.glob("*.md"):
    print(f"Processing: {md_file.name}")
    
    with open(md_file, "r", encoding="utf-8") as f:
        text = f.read()
    
    chunks, stats = chunker.chunk_document(text)
    
    output_file = output_dir / f"{md_file.stem}_chunks.json"
    chunker.save_chunks(chunks, output_file)
    
    print(f"  → {stats['total_chunks']} chunks")
```

### Example 3: Filter by Metadata

```python
# Get only parent chunks
parents = [c for c in chunks if c['metadata']['level'] == 'parent']

# Get chunks from specific chapter
chapter_1 = [c for c in chunks if c['metadata']['chapter'] == 'I']

# Get chunks with tables
table_chunks = [c for c in chunks if c['metadata']['has_table']]

# Get article by number
article_5 = [c for c in chunks if c['metadata']['article'] == 'Điều 5']
```

## 🆚 Comparison with Docling Chunker

Run the comparison script to see format differences:

```bash
python compare_formats.py
```

**When to use which:**

- **Docling chunker**: Documents converted by Docling (uses `#` headers)
- **PyMuPDF chunker**: Documents converted by PyMuPDF4LLM (uses `**bold**`)

Both share the **same chunking logic**, only differing in format detection.

## 🧪 Testing

```bash
# Run test suite
python test_pymupdf_chunker.py

# Compare formats
python compare_formats.py
```

## 📈 Performance Benchmarks

Typical performance on legal documents:

| Document Size | Chunks | Processing Time | Avg Chunk Size |
|---------------|--------|-----------------|----------------|
| Small (5-10 KB) | 20-40 | < 0.1s | 400-600 chars |
| Medium (20-50 KB) | 50-100 | < 0.5s | 500-800 chars |
| Large (100+ KB) | 150-300 | < 2s | 600-1000 chars |

## ⚠️ Known Limitations

1. **Bold detection**: Requires `**text**` format (PyMuPDF4LLM standard)
2. **Mixed formats**: Cannot handle mixed markdown headers and bold
3. **Irregular structure**: Assumes standard Vietnamese legal document structure
4. **Table detection**: Basic pipe-based detection (`|`)

## 🔜 Future Improvements

- [ ] Support for mixed format detection
- [ ] Enhanced table detection (complex tables)
- [ ] Footnote preservation
- [ ] Cross-reference linking
- [ ] Custom metadata injection

## 🤝 Related Files

- `hierarchical_legal_chunker.py` - Docling version
- `test_pymupdf_chunker.py` - Test script
- `compare_formats.py` - Format comparison
- `main.py` - Batch processing pipeline

## 📄 License

Same license as parent project.

## 🐛 Troubleshooting

### Issue: No chunks detected

**Cause**: Format mismatch (document uses `#` instead of `**`)

**Solution**: Use Docling chunker instead, or manually convert headers

### Issue: Chapter context missing

**Cause**: Chapter heading not detected properly

**Solution**: Ensure chapter follows format: `**CHƯƠNG [I,II,III]**`

### Issue: Tables split incorrectly

**Cause**: Table detection failed (no pipes `|`)

**Solution**: Check table format, ensure proper markdown table syntax

## 📞 Support

For issues or questions, check:
- Compare output with Docling version
- Verify input format matches PyMuPDF4LLM output
- Run `compare_formats.py` to debug detection
