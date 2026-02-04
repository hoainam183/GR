# BÁO CÁO TIẾN ĐỘ XÂY DỰNG HỆ THỐNG RAG CHATBOT
## Hệ thống Hỏi-Đáp Tài Liệu Quy Định Đào Tạo HUST

**Người thực hiện:** Sinh viên nghiên cứu  
**Thời gian:** Tháng 12/2024 - Tháng 01/2026  
**Ngày báo cáo:** 26/01/2026

---

## MỤC LỤC

1. [Tổng quan hệ thống](#1-tổng-quan-hệ-thống)
2. [Kiến trúc hệ thống](#2-kiến-trúc-hệ-thống)
3. [Module xử lý PDF](#3-module-xử-lý-pdf)
4. [Module Chunking](#4-module-chunking)
5. [Module Embedding và Vector Store](#5-module-embedding-và-vector-store)
6. [Module LLM và Generation](#6-module-llm-và-generation)
7. [Backend API](#7-backend-api)
8. [Frontend](#8-frontend)
9. [Evaluation Framework](#9-evaluation-framework)
10. [Kết quả và thống kê](#10-kết-quả-và-thống-kê)
11. [Hạn chế và hướng phát triển](#11-hạn-chế-và-hướng-phát-triển)

---

## 1. TỔNG QUAN HỆ THỐNG

### 1.1. Mục tiêu

Xây dựng hệ thống **RAG (Retrieval-Augmented Generation) Chatbot** hỗ trợ sinh viên hỏi-đáp tự động về các quy định, quy chế đào tạo của Đại học Bách khoa Hà Nội.

### 1.2. Tính năng chính

| Tính năng | Mô tả |
|-----------|-------|
| **Hỏi-đáp tự nhiên** | Sinh viên đặt câu hỏi bằng ngôn ngữ tự nhiên |
| **Trích dẫn nguồn** | Mỗi câu trả lời kèm theo Điều, Khoản cụ thể |
| **Đa nguồn tài liệu** | 16+ văn bản quy chế, quy định |
| **Xử lý tiếng Việt** | Accuracy 99.5%+ |

### 1.3. Công nghệ sử dụng

| Component | Technology |
|-----------|------------|
| **LLM** | Gemini 2.5 Flash |
| **Embedding** | intfloat/multilingual-e5-large (1024d) |
| **Vector Store** | FAISS (IndexFlatIP) |
| **PDF Processing** | Docling, PyMuPDF4LLM, olmOCR |
| **Backend** | FastAPI (Python 3.10+) |
| **Frontend** | React 18 + TypeScript + Vite |

### 1.4. Dữ liệu

**16 văn bản quy định đã xử lý:**

1. QCDT_2025_5445_QD-DHBK (Quy chế đào tạo 2025)
2. Quy chế CTSV ĐHBK Hà Nội 2025
3. QD_ngoai_ngu_tu_K68_CQ_final
4. QD NN DHCQ-2020-2021
5. 06_ Quy định ngoại ngữ từ K70
6. 1. QĐ Học bổng KKHT 2023
7. 4. QĐ thi Olympic và ĐMST 2023
8. 5. Quy định QLSV nước ngoài 2023
9. Khung-DGRL-2020-2021
10. QD ban hanh QD to chuc day hoc tren nen tang CN ket noi
11. QD ban hanh QD to chuc thi Truc tuyen
12. Quy định xét cấp HB tài trợ 2024
13. QĐ Ban hành hướng dân triển khai chính sách HT cho SV khuyết tật
14. QĐ đánh giá điểm rèn luyện sinh viên 2023
15. 01_1 2015 TT Lien tich_QD danh gia QP-AN
16. 01_3 HD hoc chuyen tiep ky su 180 TC

---

## 2. KIẾN TRÚC HỆ THỐNG

### 2.1. Sơ đồ kiến trúc tổng quan

```
┌─────────────────────────────────────────────────────────────────────┐
│                           FRONTEND                                   │
│                    React + TypeScript + Vite                        │
│                    (chat-companion/)                                 │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │ HTTP/REST
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                           BACKEND                                    │
│                    FastAPI (backend/main.py)                        │
│                                                                      │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐             │
│  │   /chat     │    │  /health    │    │  RAGLogger  │             │
│  │  Endpoint   │    │  Endpoint   │    │  (CSV Log)  │             │
│  └──────┬──────┘    └─────────────┘    └─────────────┘             │
└─────────┼───────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         RAG PIPELINE                                 │
│                     (src/RAG/)                                       │
│                                                                      │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                       GeminiRAG                                │  │
│  │                    (LLM/llm.py)                                │  │
│  │                                                                 │  │
│  │  answer(question) → retrieve() → build_prompt() → generate()  │  │
│  └───────────────────────────────┬───────────────────────────────┘  │
│                                  │                                   │
│  ┌───────────────────────────────▼───────────────────────────────┐  │
│  │                   EmbeddingPipeline                            │  │
│  │              (embedding/embedding.py)                          │  │
│  │                                                                 │  │
│  │  search(query) → embed() → vector_store.search()              │  │
│  └───────────────────────────────┬───────────────────────────────┘  │
│                                  │                                   │
│  ┌───────────────────────────────▼───────────────────────────────┐  │
│  │                   FaissVectorStore                             │  │
│  │              (embedding/faiss_store.py)                        │  │
│  │                                                                 │  │
│  │  IndexFlatIP (1024d) + Metadata Store                         │  │
│  │  1,247 chunks from 16 documents                               │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2. Cấu trúc thư mục dự án

```
GR/
├── backend/                    # FastAPI Backend
│   ├── main.py                 # API endpoints (179 lines)
│   ├── logger.py               # CSV logging (106 lines)
│   └── rag_logs.csv            # Interaction logs (200KB+)
│
├── frontend/                   # React Frontend
│   └── chat-companion/
│       └── src/
│           ├── App.tsx         # Main app with routing
│           ├── pages/          # Index, NotFound pages
│           ├── components/     # 54 UI components
│           └── services/       # API services
│
├── src/RAG/                    # Core RAG System
│   ├── LLM/                    # Language Model Integration
│   │   ├── llm.py              # GeminiRAG class (274 lines)
│   │   └── test_api.py         # API testing
│   │
│   ├── chunking/               # Text Chunking
│   │   └── chunker/
│   │       ├── base_chunker.py
│   │       ├── hierarchical_legal_chunker.py (24,639 bytes)
│   │       └── olmocr_legal_chunker.py (40,500 bytes, 1126 lines)
│   │
│   ├── embedding/              # Vector Embedding
│   │   ├── embedding.py        # EmbeddingPipeline (419 lines)
│   │   ├── faiss_store.py      # FaissVectorStore (366 lines)
│   │   ├── vector_store.py     # Abstract interface
│   │   └── migrate_olmocr.py   # Migration script
│   │
│   ├── evaluation/             # Evaluation Framework
│   │   ├── evaluate_rag.py     # Full RAG evaluation (613 lines)
│   │   └── evaluate_retrieval.py # Retrieval metrics (602 lines)
│   │
│   ├── document_loader/        # PDF Processing
│   │   └── pdf_to_markdown/
│   │
│   ├── olmocr_chunks/          # 16 processed chunk files
│   └── output_docling/         # Docling output
│
├── olmocr/                     # olmOCR Processing
│   ├── quydinh/                # 16 source markdown files
│   ├── converted/              # After HTML table conversion
│   ├── batch_convert.py
│   └── convert_html_to_markdown_tables.py (362 lines)
│
└── rag_evaluation_dataset.csv  # Evaluation test set
```

---

## 3. MODULE XỬ LÝ PDF

### 3.1. Multi-Converter Pipeline

Hệ thống hỗ trợ 3 PDF converters với fallback mechanism:

```
                    PDF Input
                        │
         ┌──────────────┼──────────────┐
         ▼              ▼              ▼
    ┌─────────┐    ┌─────────┐    ┌─────────┐
    │ Docling │    │PyMuPDF4 │    │ olmOCR  │
    │ (Text)  │    │  LLM    │    │ (Vision)│
    └────┬────┘    └────┬────┘    └────┬────┘
         │              │              │
         ▼              ▼              ▼
    Check Font     Check Font     Always OK
    Encoding       Encoding       (Vision-based)
         │              │              │
         └──────────────┴──────────────┘
                        │
                        ▼
                   Markdown Output
```

### 3.2. So sánh các Converter

| Tiêu chí | Docling | PyMuPDF4LLM | olmOCR |
|----------|---------|-------------|--------|
| **Speed** | 8s/34pages | 3s/34pages | ~60s/34pages |
| **Vietnamese accuracy** | 99.5% | 99.9% | 99.9% |
| **Font issues** | Có thể fail | Có thể fail | Không ảnh hưởng |
| **Table extraction** | Tốt | Trung bình | Xuất sắc |
| **Structure detection** | Xuất sắc | Tốt | Tốt |
| **GPU required** | Không | Không | Có |

### 3.3. olmOCR - Giải pháp cho PDF lỗi font

**Vấn đề với converter truyền thống:**

```
Văn bản gốc: "Điều 1. Phạm vi và đối tượng áp dụng"
Lỗi font:    "Äiá»u 1. Phạm vi và đá»i tượng áp dụng"
```

**Giải pháp olmOCR:**
- Vision-based OCR không phụ thuộc font embedding
- Output HTML tables → cần convert sang Markdown

**HTML Table Converter:**

```python
# File: olmocr/convert_html_to_markdown_tables.py (362 lines)

class HTMLTableParser(HTMLParser):
    """
    Xử lý HTML table với:
    - rowspan/colspan handling
    - Multi-row header merging
    - Empty cell filling
    """
```

**Kết quả batch processing:**

```
Total files processed: 16
Files with HTML tables: 12
Files without HTML tables: 4
Successfully converted: 16
```

---

## 4. MODULE CHUNKING

### 4.1. Chiến lược Chunking cho văn bản pháp lý

**Đặc điểm văn bản pháp lý Việt Nam:**
```
CHƯƠNG I - QUY ĐỊNH CHUNG
    Điều 1. Phạm vi điều chỉnh
        1. Khoản 1...
        2. Khoản 2...
            a) Điểm a...
            b) Điểm b...
    Điều 2. Đối tượng áp dụng
```

### 4.2. OlmOcrLegalChunker

**File:** `src/RAG/chunking/chunker/olmocr_legal_chunker.py`  
**Kích thước:** 1,126 dòng, 40,500 bytes  
**Classes:** 4 (ChunkLevel, DocumentMetadata, ChunkData, OlmOcrLegalChunker)  
**Methods:** 43+

**Cấu trúc ChunkLevel:**

```python
class ChunkLevel:
    HEADER = "header"      # Phần đầu văn bản (QĐ, căn cứ)
    PARENT = "parent"      # 1 Điều đầy đủ + context Chương
    CHILD = "child"        # Khoản trong Điều
    APPENDIX = "appendix"  # Phụ lục
    RECURSIVE = "recursive" # Fallback chunks
```

**Metadata được trích xuất:**

```python
@dataclass
class ChunkData:
    content: str
    level: ChunkLevel
    chapter: Optional[str]        # "I", "II", "III"
    chapter_title: Optional[str]  # "QUY ĐỊNH CHUNG"
    article: Optional[str]        # "1", "2", "18"
    article_title: Optional[str]  # "Điều kiện tốt nghiệp"
    clause: Optional[str]         # "1", "2", "3"
    has_table: bool
    is_appendix: bool
    chunk_id: int
    readable_id: str              # "c1_d5_k2" (Chương 1, Điều 5, Khoản 2)
    parent_id: Optional[str]
```

**Cấu hình mặc định:**

```python
OlmOcrLegalChunker(
    min_child_size=300,       # Minimum child chunk size
    max_child_size=1000,      # Maximum child chunk size
    parent_size_limit=4000,   # Merge điều nhỏ thành 1 parent
    chunk_overlap=100,        # Overlap giữa chunks
    fallback_chunk_size=1000, # Size cho RecursiveTextSplitter
    fallback_chunk_overlap=200
)
```

### 4.3. Hierarchical Legal Chunker (cho Docling/PyMuPDF)

**File:** `src/RAG/chunking/chunker/hierarchical_legal_chunker.py`  
**Kích thước:** 24,639 bytes

**Khác biệt với OlmOcrLegalChunker:**
- Xử lý markdown headings (#, ##)
- Không cần xử lý HTML tables
- Cùng output format (ChunkData)

---

## 5. MODULE EMBEDDING VÀ VECTOR STORE

### 5.1. EmbeddingPipeline

**File:** `src/RAG/embedding/embedding.py`  
**Kích thước:** 419 dòng, 14,597 bytes  
**Methods:** 16

**Chức năng chính:**

```python
class EmbeddingPipeline:
    def __init__(self, config: PipelineConfig):
        # Initialize E5 embedding model
        # Initialize FAISS vector store
    
    def build_embedding_input(self, chunk: Dict) -> str:
        """
        Tối ưu cho E5 model:
        - Natural language structure
        - Hierarchical context (Chương > Điều > Khoản)
        """
    
    def process_single_file(self, chunks_file, source_file, add_to_store=True):
        """Process 1 file chunks.json"""
    
    def process_multiple_files(self, chunks_files, overwrite_existing=None):
        """Batch processing nhiều files"""
    
    def search(self, query: str, top_k: int = 5, filters: Dict = None):
        """
        Semantic search với metadata filtering
        E.g., filters={"source_file": "QCDT_2025"}
        """
```

**Embedding Input Format (tối ưu cho E5):**

```python
def build_embedding_input_optimized(self, chunk):
    """
    Format:
    "Quy chế đào tạo HUST - Chương I: QUY ĐỊNH CHUNG
     Điều 5. Điều kiện tốt nghiệp
     
     [Nội dung chunk]"
    """
```

### 5.2. FaissVectorStore

**File:** `src/RAG/embedding/faiss_store.py`  
**Kích thước:** 366 dòng, 12,078 bytes

**Cấu hình:**

```python
@dataclass
class FaissConfig:
    index_type: str = "IndexFlatIP"  # Cosine similarity
    dimension: int = 1024            # E5-large dimension
    save_path: str = "./vector_store"
    use_gpu: bool = False
```

**Methods chính:**

```python
class FaissVectorStore:
    def add_documents(self, documents: List[Document], batch_size=100)
    def search(self, query_embedding, top_k=5, filters=None)
    def delete_by_metadata(self, filters: Dict) -> int
    def save(self, path: str)
    def load(self, path: str)
    def get_statistics(self) -> Dict
```

**Metadata Filtering:**

```python
# Có thể filter theo source file, chapter, article
results = vector_store.search(
    query_emb, 
    top_k=5, 
    filters={"source_file": "QCDT_2025.pdf", "chapter": "I"}
)
```

### 5.3. Migration Script (olmOCR → Vector Store)

**File:** `src/RAG/embedding/migrate_olmocr.py`  
**Kích thước:** 219 dòng

**Workflow:**

```
1. Load vector store hiện tại
2. Tìm files trùng lặp (docling vs olmOCR)
3. Xóa chunks cũ từ docling
4. Thêm tất cả 16 files olmOCR
5. Save và thống kê
```

**Kết quả migration:**

```
📊 THỐNG KÊ CUỐI CÙNG:
Total documents: 1,247 chunks
Unique chunks: 1,247
Source files: 16

Distribution by level:
- parent: 892
- child: 312
- header: 43
```

---

## 6. MODULE LLM VÀ GENERATION

### 6.1. GeminiRAG

**File:** `src/RAG/LLM/llm.py`  
**Kích thước:** 274 dòng, 7,860 bytes

**Class structure:**

```python
class GeminiRAG:
    def __init__(self, api_key, model_name="gemini-2.5-flash", pipeline=None):
        # Load embedding pipeline
        # Setup Gemini client
    
    def answer(self, question, top_k=5, filters=None, stream=False):
        """
        RAG Pipeline:
        1. Embed query
        2. Retrieve relevant chunks (top_k)
        3. Build prompt with context
        4. Generate answer with Gemini
        5. Return answer + sources
        """
    
    def _build_context(self, results: List) -> str:
        """Format retrieved chunks thành context"""
    
    def _build_prompt(self, question: str, context: str) -> str:
        """Prompt engineering cho legal QA"""
    
    def _get_gemini_response(self, prompt: str, stream: bool) -> str:
        """Call Gemini API"""
```

### 6.2. Prompt Template

```python
prompt = f"""Bạn là trợ lý AI chuyên về Quy chế đào tạo của Đại học Bách khoa Hà Nội.

Nhiệm vụ: Trả lời câu hỏi của sinh viên/học viên dựa trên ngữ cảnh từ quy chế.

Ngữ cảnh từ Quy chế:
{context}

Câu hỏi: {question}

Hướng dẫn:
1. Trả lời CHÍNH XÁC dựa trên ngữ cảnh
2. Trích dẫn điều khoản cụ thể nếu có
3. Nếu không tìm thấy thông tin, nói "Không tìm thấy thông tin trong quy chế"
4. Giải thích rõ ràng, dễ hiểu
5. Liệt kê đầy đủ nếu có điều kiện/yêu cầu

Trả lời bằng tiếng Việt:"""
```

### 6.3. Generation Config

```python
generation_config = {
    "temperature": 0.3,     # Low for factual accuracy
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 8192,
}
```

---

## 7. BACKEND API

### 7.1. FastAPI Application

**File:** `backend/main.py`  
**Kích thước:** 179 dòng, 4,626 bytes

**Endpoints:**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Health check |
| `/health` | GET | RAG system status |
| `/chat` | POST | Main chat endpoint |

### 7.2. Request/Response Models

```python
class QuestionRequest(BaseModel):
    question: str
    top_k: Optional[int] = 5

class RetrievedDocument(BaseModel):
    rank: int
    content: str
    score: float
    metadata: Dict

class AnswerResponse(BaseModel):
    question: str
    answer: str
    retrieved_documents: List[RetrievedDocument]
    num_documents: int
    model_name: str
```

### 7.3. Chat Flow

```python
@app.post("/chat", response_model=AnswerResponse)
async def chat(request: QuestionRequest):
    # 1. Get answer from RAG system
    result = rag_system.answer(
        question=request.question,
        top_k=request.top_k,
        stream=False,
        verbose=True,
    )
    
    # 2. Format retrieved documents
    retrieved_docs = [...]
    
    # 3. Log to CSV
    logger.log(
        question=result["question"],
        sources=sources_for_log,
        model_name=result["model_name"],
    )
    
    # 4. Return response
    return response
```

### 7.4. Logging System

**File:** `backend/logger.py`  
**Kích thước:** 106 dòng

**CSV Log Structure:**

| Column | Description |
|--------|-------------|
| `timestamp` | YYYY-MM-DD HH:MM:SS |
| `question` | User's question |
| `num_retrieved_docs` | Top-K documents |
| `retrieved_docs` | Full content with rank |
| `model_name` | LLM model used |

**Log file:** `backend/rag_logs.csv` (200KB+, hàng trăm interactions)

---

## 8. FRONTEND

### 8.1. Technology Stack

- **Framework:** React 18
- **Language:** TypeScript
- **Build Tool:** Vite
- **Styling:** CSS + Component Library
- **State Management:** React Query (@tanstack/react-query)
- **Routing:** React Router DOM

### 8.2. Project Structure

```
frontend/chat-companion/
├── src/
│   ├── App.tsx              # Main app với routing
│   ├── main.tsx             # Entry point
│   ├── pages/
│   │   ├── Index.tsx        # Chat interface
│   │   └── NotFound.tsx     # 404 page
│   ├── components/          # 54 UI components
│   │   ├── ui/              # Base UI components
│   │   └── ...
│   ├── services/            # API services
│   ├── hooks/               # Custom React hooks
│   └── types/               # TypeScript types
└── package.json
```

### 8.3. Tính năng chính

1. **Chat Interface:**
   - Nhập câu hỏi qua text input
   - Gửi bằng button hoặc phím Enter
   - Hiển thị câu trả lời với animation

2. **Display nguồn tham khảo:**
   - Mỗi câu trả lời kèm danh sách retrieved documents
   - Metadata: số điều, chương, relevance score

3. **UX Features:**
   - Loading indicator
   - Message history
   - Responsive design
   - Toast notifications

---

## 9. EVALUATION FRAMEWORK

### 9.1. Evaluation Scripts

**Files:**
- `src/RAG/evaluation/evaluate_rag.py` (613 dòng)
- `src/RAG/evaluation/evaluate_retrieval.py` (602 dòng)

### 9.2. Metrics

**Retrieval Metrics:**

| Metric | Description |
|--------|-------------|
| **Precision@K** | Relevant docs / K retrieved docs |
| **Recall@K** | Relevant docs found / Total relevant docs |
| **Hit Rate@K** | % queries có ít nhất 1 relevant doc |
| **MRR (Mean Reciprocal Rank)** | Average 1/rank của relevant doc đầu tiên |

**Generation Metrics:**

| Metric | Description |
|--------|-------------|
| **Answer Similarity** | Semantic similarity với ground truth |

### 9.3. Data Structures

```python
@dataclass
class EvaluationSample:
    question: str
    ground_truth_answer: str
    expected_source: str
    question_type: str      # "factual", "comparison", "multi-hop"
    difficulty: str         # "easy", "medium", "hard"
    relevant_context: str

@dataclass
class RetrievalEvalResult:
    question: str
    expected_source: str
    retrieved_sources: List[str]
    retrieved_scores: List[float]
    hit: bool
    rank: int
    precision: float
    recall: float
    reciprocal_rank: float
    question_type: str
    difficulty: str
```

### 9.4. Evaluation Workflow

```python
evaluator = RetrievalEvaluator(top_k=5)
evaluator.load_pipeline()

samples = evaluator.load_dataset("rag_evaluation_dataset.csv")
report = evaluator.evaluate(samples)

print_report(report)
save_results_csv(report, "evaluation_results.csv")
```

---

## 10. KẾT QUẢ VÀ THỐNG KÊ

### 10.1. Vector Store Statistics

```
📊 THỐNG KÊ VECTOR STORE:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total documents: 1,247 chunks
Embedding dimension: 1024
Index type: IndexFlatIP

Top source files by chunk count:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. QCDT_2025_5445_QD-DHBK: 384 chunks
2. Quy chế CTSV ĐHBK Hà Nội 2025: 223 chunks
3. QD_ngoai_ngu_tu_K68_CQ_final: 78 chunks
4. QD NN DHCQ-2020-2021: 76 chunks
5. 06_ Quy định ngoại ngữ từ K70: 72 chunks
```

### 10.2. Performance Metrics

| Metric | Value |
|--------|-------|
| **Response Time** | 2-4 seconds |
| **Query embedding** | ~200ms |
| **FAISS search** | ~50ms |
| **LLM generation** | 1.5-3s |
| **Vietnamese accuracy** | 99.5%+ |

### 10.4. Hybrid Search Evaluation Results (21/01/2026)

**Cấu hình:**
- **Hybrid Search (BM25):** Enabled
- **Reranking (Cross-encoder):** Disabled
- **Top K:** 5
- **Evaluation Dataset:** 154 samples

**Overall Metrics:**

| Metric | Value |
|--------|-------|
| **Hit Rate@5** | 99.35% |
| **MRR** | 92.31% |
| **Precision@5** | 19.87% |
| **Recall@5** | 99.35% |

**Metrics by Question Type:**

| Type | Count | Hit Rate | MRR | Precision | Recall |
|------|-------|----------|-----|-----------|--------|
| **calculation** | 4 | 100.0% | 100.0% | 20.0% | 100.0% |
| **comparative** | 11 | 100.0% | 95.45% | 20.0% | 100.0% |
| **factual** | 124 | 100.0% | 92.06% | 20.0% | 100.0% |
| **reasoning** | 15 | 93.33% | 90.0% | 18.67% | 93.33% |

**Metrics by Difficulty:**

| Difficulty | Count | Hit Rate | MRR | Precision | Recall |
|------------|-------|----------|-----|-----------|--------|
| **easy** | 36 | 100.0% | 85.65% | 20.0% | 100.0% |
| **medium** | 102 | 99.02% | 95.02% | 19.80% | 99.02% |
| **hard** | 16 | 100.0% | 90.0% | 20.0% | 100.0% |

**Nhận xét:**
- Hybrid search đạt **Hit Rate 99.35%** - gần như tất cả các câu hỏi đều tìm được document liên quan
- **MRR 92.31%** cho thấy document liên quan thường xuất hiện ở vị trí đầu tiên
- Câu hỏi dạng **reasoning** có kết quả thấp hơn một chút (93.33% hit rate) - cần cải thiện

### 10.3. PDF Processing Results

| Converter | Success Rate | Avg Speed |
|-----------|--------------|-----------|
| PyMuPDF4LLM | 99.9% | 12 pages/s |
| Docling | 99.5% | 4 pages/s |
| olmOCR | 100% | 0.5 pages/s |

---

## 11. HẠN CHẾ VÀ HƯỚNG PHÁT TRIỂN

### 11.1. Hạn chế hiện tại

**1. Performance:**
- Chưa có query caching
- Single-stage retrieval (chưa có re-ranking)
- FAISS Flat index (chưa scale được cho dataset lớn)

**2. Conversation:**
- Chưa tận dụng lịch sử hội thoại
- Mỗi query xử lý độc lập
- Không hỗ trợ follow-up questions

**3. Data:**
- Chưa có cơ chế update tài liệu tự động
- Table processing vẫn còn edge cases
- Chưa có web crawler cho documents mới

### 11.2. Roadmap

**Priority 1 - Critical (1-2 tháng):**
- [ ] Implement query caching (semantic + exact match)
- [ ] Add conversation history management
- [x] Build evaluation dataset (100+ test queries) ✅ **Hoàn thành: 155 câu hỏi**
- [ ] Implement basic metrics dashboard

**Priority 2 - Important (2-3 tháng):**
- [x] Hybrid search (BM25 + semantic) ✅ **Hoàn thành: Hit Rate 99.35%**
- [ ] Query rewriting với context
- [ ] Re-ranking với cross-encoder
- [ ] Table-aware chunking strategy

**Priority 3 - Nice to have (3-6 tháng):**
- [ ] Web crawler cho HUST documents
- [ ] Admin dashboard (monitor logs, metrics)
- [ ] User feedback mechanism
- [ ] Multi-document reasoning

---

## PHỤ LỤC

### A. Commands

**Start Backend:**
```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Start Frontend:**
```bash
cd frontend/chat-companion
npm run dev
```

**Run Evaluation:**
```bash
cd src/RAG/evaluation
python evaluate_retrieval.py --top_k 5
```

### B. Environment Variables

```
GEMINI_API_KEY=your_api_key_here
```

### C. Dependencies

**Backend:**
- FastAPI, Uvicorn
- LangChain, LangChain-HuggingFace
- FAISS-cpu
- Sentence Transformers
- Google Generative AI
- Python-dotenv

**Frontend:**
- React 18, TypeScript
- Vite
- React Router DOM
- TanStack React Query
- Tailwind CSS (optional)

---

**Ngày hoàn thành báo cáo:** 26/01/2026  
**Phiên bản:** 3.0
