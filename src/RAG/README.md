# RAG System

Hệ thống Retrieval-Augmented Generation (RAG) cho văn bản pháp luật Việt Nam.

## 📁 Cấu trúc tổng quan

```
src/RAG/
├── chunking/           # Module phân chia văn bản thành chunks
├── embedding/          # Module tạo embeddings và vector store
├── LLM/                # Module LLM (Gemini) cho generation
├── evaluation/         # Module đánh giá hiệu suất RAG
├── document_loader/    # Module load và xử lý documents
├── common/             # Shared utilities (BaseProcessor, etc.)
├── clean/              # Scripts làm sạch data
├── examples/           # Example scripts
│
├── chunks_by_articles/ # Output: Chunks JSON files
├── olmocr_chunks/      # Output: OLM OCR chunks
├── output_docling/     # Output: Docling processed files
├── output_pymupdf4llm/ # Output: PyMuPDF4LLM processed files
└── quydinh/            # Input: PDF files quy định
```

## 🔄 Pipeline Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   PDF/Document  │ -> │    Chunking     │ -> │    Embedding    │
│   quydinh/*.pdf │    │ chunks_by_*/*.json   │ vector_store/  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                      │
                                                      v
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│     Answer      │ <- │      LLM        │ <- │    Retrieval    │
│                 │    │   (Gemini)      │    │    (FAISS)      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🚀 Quick Start

### Bước 1: Cài đặt dependencies

```bash
pip install -r requirements.txt
```

### Bước 2: Chunking documents

```bash
cd chunking
python main.py
```

Xem chi tiết: [chunking/README.md](chunking/README.md)

### Bước 3: Tạo embeddings và vector store

```bash
cd embedding
python main.py --mode batch --dir ../chunks_by_articles
```

Xem chi tiết: [embedding/README.md](embedding/README.md)

### Bước 4: Chạy RAG với LLM

```bash
cd LLM
python main.py
```

Xem chi tiết: [LLM/README.md](LLM/README.md)

### Bước 5: Evaluate system (Optional)

```bash
cd evaluation
python run_evaluation.py
```

Xem chi tiết: [evaluation/README.md](evaluation/README.md)

## 📦 Module Documentation

| Module | Mô tả | Documentation |
|--------|-------|---------------|
| **chunking** | Phân chia văn bản thành chunks với cấu trúc hierarchical | [README](chunking/README.md) |
| **embedding** | Tạo embeddings và lưu vào FAISS vector store | [README](embedding/README.md) |
| **LLM** | RAG với Google Gemini | [README](LLM/README.md) |
| **evaluation** | Đánh giá hiệu suất retrieval và generation | [README](evaluation/README.md) |

## ⚙️ Configuration

### Environment Variables

Tạo file `.env` ở thư mục gốc:

```bash
# Google Gemini API
GEMINI_API_KEY=your_gemini_api_key

# Optional: MegaLLM API (alternative)
MEGALLM_API_KEY=your_megallm_key
MEGALLM_API_URL=https://ai.megallm.io/v1
MEGALLM_MODEL=gpt-4o-mini
```

### Embedding Configuration

Xem `embedding/config.py` để customize:
- Model name (default: `intfloat/multilingual-e5-large`)
- Device (cpu/cuda)
- Batch size
- Vector store settings

## 🛠️ Development

### Project Structure Conventions

- `main.py`: Entry point cho mỗi module
- `main_v2.py`: Version sử dụng BaseProcessor framework
- `README.md`: Documentation cho mỗi module
- `__init__.py`: Module exports

### Adding New Chunkers

1. Tạo class mới kế thừa từ `base_chunker.py`
2. Implement các methods: `chunk_document()`, `save_chunks()`
3. Register trong `main.py`

### Adding New Vector Stores

1. Tạo class mới implement interface từ `vector_store.py`
2. Add configuration trong `config.py`
3. Update `embedding.py` để support

## 📊 Performance Tips

1. **GPU Acceleration**:
   ```python
   config.embedding.device = "cuda"
   ```

2. **Batch Size Tuning**:
   - 4GB VRAM: batch_size = 16
   - 8GB VRAM: batch_size = 32
   - 16GB VRAM: batch_size = 64

3. **Skip Processed Files**: Sử dụng `main_v2.py` versions

## 🐛 Troubleshooting

### Common Issues

1. **Vector store not found**:
   ```bash
   cd embedding
   python main.py --mode batch --dir ../chunks_by_articles
   ```

2. **Out of memory**:
   - Giảm batch size trong config
   - Sử dụng CPU thay vì GPU

3. **Slow embedding**:
   - Set `HF_ENDPOINT=https://hf-mirror.com` nếu ở Việt Nam
   - Sử dụng GPU nếu có

4. **API key errors**:
   - Kiểm tra file `.env`
   - Ensure key format đúng

## 📚 Resources

- [LangChain Documentation](https://python.langchain.com/)
- [FAISS Documentation](https://github.com/facebookresearch/faiss)
- [Google Gemini API](https://ai.google.dev/)
- [HuggingFace E5 Models](https://huggingface.co/intfloat/multilingual-e5-large)

## 📝 License

This project is for educational purposes.
