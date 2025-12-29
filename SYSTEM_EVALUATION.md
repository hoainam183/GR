# 📊 ĐÁNH GIÁ HỆ THỐNG RAG - Quy Chế Đào Tạo HUST

*Ngày đánh giá: 27/12/2025*

---

## 📋 TÓM TẮT TỔNG QUAN

### Điểm mạnh nổi bật ⭐⭐⭐⭐
- ✅ Kiến trúc module hóa tốt với separation of concerns
- ✅ Abstract layer cho vector store (dễ scale)
- ✅ Chunking strategy phù hợp với văn bản pháp lý
- ✅ Multi-file support với metadata tracking
- ✅ E5 multilingual model phù hợp với tiếng Việt
- ✅ Full-stack implementation (Backend + Frontend)

### Điểm cần cải thiện ⚠️
- 🔴 **PDF conversion** - vấn đề lớn nhất (không ổn định, đa công cụ)
- 🟡 **Single-document focus** - chưa có strategy rõ ràng cho multi-document
- 🟡 **Chunking strategy** - chỉ có 1 approach (section-based)
- 🟡 **No evaluation metrics** - thiếu cách đo lường chất lượng RAG
- 🟡 **No hybrid search** - chỉ có semantic search
- 🟡 **Database design** - chưa có schema rõ ràng cho production

---

## 1️⃣ ĐÁNH GIÁ CHI TIẾT TỪNG COMPONENT

### 1.1 PDF → Markdown Pipeline

#### Hiện trạng
Bạn đang sử dụng **3 công cụ khác nhau**:
1. **Docling** - [`src/extract_from_pdf/docling/`]
2. **Unstructured** - [`src/extract_from_pdf/unstructured.py`]
3. **PyMuPDF4LLM** - [`src/RAG/output_pymupdf4llm/`]

#### Vấn đề chính 🔴

**Vấn đề 1: Không có pipeline thống nhất**
```
❌ Current state:
   File A → Docling → MD format 1
   File B → PyMuPDF → MD format 2
   File C → Unstructured → MD format 3
```

**Vấn đề 2: Font encoding với tiếng Việt**
- Đây là vấn đề **cực kỳ phổ biến** với PDF tiếng Việt
- Nguyên nhân: PDF sử dụng font embedding không chuẩn
- PyMuPDF/Docling gặp khó khăn với các font custom

**Vấn đề 3: Thiếu preprocessing pipeline**
- Không có bước clean/normalize output
- Footnotes handling (đã có code nhưng không consistent)
- Table extraction không ổn định

#### Đánh giá: ⭐⭐ / 5
- Có nỗ lực xử lý nhiều tools
- Nhưng thiếu strategy thống nhất
- Chưa có error handling và fallback mechanism

---

### 1.2 Chunking Strategy

#### Hiện trạng
Bạn có **2 chunking implementations**:

**Implementation 1: Section-based** [`src/RAG/chunking/chunker/chunking.py`]
```python
# Parse theo cấu trúc:
# - Chương (Chapter)
# - Điều (Article)
# - Khoản (Clause)
```

**Implementation 2: Parent-Child** [`hierarchical_legal_chunker.py`]
```python
class ArticleLevelLegalChunker:
    # Parent: Toàn bộ điều
    # Children: Các khoản trong điều
    # + Overlap support
    # + Table protection
```

#### Điểm mạnh ✅
1. **Hierarchical metadata** - rất tốt!
   ```python
   metadata = {
       "chapter": "I",
       "chapter_full": "CHƯƠNG I - QUY ĐỊNH CHUNG",
       "article": "Điều 1",
       "article_full": "Điều 1. Phạm vi áp dụng",
       "clause": "1"
   }
   ```
2. **Context preservation** - mỗi chunk biết nó thuộc chương/điều nào
3. **Parent-child architecture** - đúng hướng cho legal documents

#### Điểm yếu ⚠️
1. **Chỉ có 1 strategy được sử dụng** - parent-child chưa integrate vào main pipeline
2. **Không có dynamic chunk sizing** - cố định theo section
3. **Thiếu semantic chunking** - không xem xét độ liên quan ngữ nghĩa
4. **Table handling** - có detect nhưng chưa có strategy rõ ràng

#### Đề xuất strategy mới 💡
Bạn muốn implement:
> "Chunk theo điều → chia nhỏ theo độ dài cố định → có overlap"

**Đánh giá đề xuất này:** ⭐⭐⭐⭐ / 5
- ✅ Rất hợp lý cho văn bản pháp lý
- ✅ Parent-child approach phù hợp
- ✅ Overlap giúp giữ context

**Nhưng cần lưu ý:**
- Độ dài cố định có thể cắt giữa câu → dùng sentence-aware splitting
- Overlap size cần tune (100-200 chars là hợp lý)
- Cần metadata tracking parent-child relationship

#### Đánh giá: ⭐⭐⭐⭐ / 5
- Strategy đúng hướng
- Implementation tốt
- Chỉ thiếu multi-strategy comparison

---

### 1.3 Embedding & Vector Store

#### Hiện trạng
```python
Model: intfloat/multilingual-e5-large
Dimensions: 1024
Vector Store: FAISS (local)
```

#### Điểm mạnh ✅
1. **Model choice xuất sắc** ⭐⭐⭐⭐⭐
   - E5 multilingual là một trong những model tốt nhất cho tiếng Việt
   - 1024 dims - đủ để capture semantic information
   - Open source, chạy local được

2. **Abstract Vector Store design** ⭐⭐⭐⭐⭐
   ```python
   class VectorStore(ABC):
       def search(query_embedding, filters) -> List[SearchResult]
   ```
   - Rất tốt! Dễ migrate sang PostgreSQL/ChromaDB sau này

3. **Context-aware embedding** ⭐⭐⭐⭐
   ```python
   def build_embedding_input_optimized(chunk):
       # "Chương I, Điều 1 quy định: [content]"
   ```
   - Thêm context vào embedding input - strategy đúng!

4. **Metadata filtering support**
   ```python
   filters = {"source_file": "QCDT_2025", "chapter": "I"}
   ```

#### Điểm yếu ⚠️
1. **Chỉ có semantic search** - không có:
   - BM25 (keyword-based)
   - Hybrid search (semantic + keyword)
   - Re-ranking

2. **Không có evaluation**
   - Không biết retrieval accuracy
   - Không có metrics: MRR, NDCG, Recall@K

3. **FAISS index type** - đang dùng type nào?
   - Flat (exact search) - tốt nhưng chậm với large dataset
   - IVF/HNSW - cần cho production

#### Đánh giá: ⭐⭐⭐⭐ / 5
- Implementation tốt
- Thiếu advanced features (hybrid search, re-ranking)

---

### 1.4 LLM Integration (Gemini)

#### Hiện trạng
```python
Model: gemini-2.5-flash
Temperature: 0.3
Max tokens: 8192
```

#### Điểm mạnh ✅
1. **Prompt engineering tốt**
   ```python
   "Bạn là trợ lý AI chuyên về Quy chế đào tạo..."
   "Trích dẫn điều khoản cụ thể nếu có"
   ```

2. **Source citation** - hiển thị retrieved documents với metadata

3. **Temperature = 0.3** - hợp lý cho QA (không quá creative)

#### Điểm yếu ⚠️
1. **Không có fallback** - chỉ support Gemini
2. **Không có answer evaluation** - không validate quality
3. **Không có citation verification** - không check hallucination

#### Đánh giá: ⭐⭐⭐ / 5
- Functional nhưng basic
- Cần thêm robustness

---

### 1.5 Multi-file Support & Database Design

#### Hiện trạng
```python
metadata["source_file"] = "QCDT_2025"
```

Bạn đã implement:
- ✅ Track source file trong metadata
- ✅ Load chunks từ multiple files
- ✅ Filter by source_file trong search

#### Vấn đề 🔴
**Bạn chưa có:**

1. **Document Registry** - không track documents trong system
   ```
   Không biết: 
   - File nào đã được ingest?
   - Version nào?
   - Khi nào?
   - Bao nhiêu chunks?
   ```

2. **Update/Delete mechanism**
   - Không có cách xóa/update document cũ
   - Re-ingest sẽ duplicate

3. **Metadata schema không consistent**
   - Các file khác nhau có metadata khác nhau
   - Không có validation

4. **Relationship tracking**
   - Không track parent-child relationships
   - Không có cross-references giữa các điều

#### Đánh giá: ⭐⭐ / 5
- Support basic multi-file
- Nhưng thiếu document management system

---

### 1.6 Backend API (FastAPI)

#### Điểm mạnh ✅
1. **RESTful design**
   ```python
   POST /chat - main endpoint
   GET /health - health check
   ```

2. **Logging to CSV** - good for debugging
   ```python
   logger.log(question, answer, sources)
   ```

3. **Structured response**
   ```python
   class AnswerResponse(BaseModel):
       question: str
       answer: str
       retrieved_documents: List[RetrievedDocument]
   ```

#### Điểm yếu ⚠️
1. **No authentication** - ai cũng có thể query
2. **No rate limiting** - có thể bị abuse
3. **No caching** - same query → re-compute
4. **CSV logging** - không scale, nên dùng database

#### Đánh giá: ⭐⭐⭐ / 5
- Functional cho development
- Cần nhiều improvements cho production

---

### 1.7 Frontend (React)

#### Đánh giá: ⭐⭐⭐ / 5
- Basic chat interface
- Hiển thị sources - good!
- Functional nhưng chưa có advanced features:
  - Chat history
  - Follow-up questions
  - Source highlighting
  - Feedback mechanism

---

## 2️⃣ GIẢI PHÁP CHO CÁC VẤN ĐỀ

### 🔴 Vấn đề 1: PDF Conversion Unstable

#### Root Cause Analysis
PDF tiếng Việt có 3 loại problems:
1. **Font embedding issues** - font không standard
2. **Character encoding** - Unicode vs ANSI
3. **Layout complexity** - tables, multi-column

#### Giải pháp A: Multi-stage Conversion Pipeline ⭐⭐⭐⭐⭐

```
Stage 1: Detection
├─> Check PDF properties (fonts, encoding)
├─> Classify PDF type (simple, complex, scanned)
└─> Choose converter based on type

Stage 2: Primary Conversion
├─> Simple text PDF → PyMuPDF
├─> Complex layout → Docling
└─> Scanned/Image PDF → OCR (Tesseract + Vietnamese)

Stage 3: Fallback
├─> If primary fails → try alternative
├─> Quality check (encoding, structure)
└─> Manual review flag if all fail

Stage 4: Post-processing
├─> Normalize encoding (ensure UTF-8)
├─> Fix common Vietnamese font issues
├─> Clean up artifacts
└─> Validate structure (chapters, articles)
```

**Implementation:**
```python
class PDFConversionPipeline:
    def __init__(self):
        self.converters = {
            'docling': DoclingConverter(),
            'pymupdf': PyMuPDFConverter(),
            'tesseract': TesseractOCR()
        }
        
    def detect_pdf_type(self, pdf_path) -> str:
        """Classify PDF"""
        # Check if scanned
        # Check fonts
        # Check complexity
        return 'simple' | 'complex' | 'scanned'
    
    def convert(self, pdf_path) -> tuple[str, dict]:
        pdf_type = self.detect_pdf_type(pdf_path)
        
        # Primary converter
        primary = self._get_primary_converter(pdf_type)
        result = primary.convert(pdf_path)
        
        # Quality check
        if not self._validate_output(result):
            # Try fallback
            fallback = self._get_fallback_converter(pdf_type)
            result = fallback.convert(pdf_path)
        
        # Post-process
        result = self._post_process(result)
        
        return result, {"converter": primary.name, "quality": score}
```

#### Giải pháp B: Vietnamese Font Fixing ⭐⭐⭐⭐

**Vấn đề:** Font encoding thường bị nhầm giữa:
- VNI, TCVN3, Unicode
- Composite characters vs precomposed

**Code fix:**
```python
import unicodedata

def fix_vietnamese_encoding(text: str) -> str:
    """Fix common Vietnamese encoding issues"""
    
    # 1. Normalize to NFC (precomposed)
    text = unicodedata.normalize('NFC', text)
    
    # 2. Fix common replacements
    replacements = {
        'Äá': 'Đ',  # Common Đ encoding issue
        'Äâ': 'Đ',
        'Ä'': 'Đ',
        # Add more based on your observations
    }
    
    for wrong, correct in replacements.items():
        text = text.replace(wrong, correct)
    
    # 3. Remove zero-width characters
    text = ''.join(c for c in text if unicodedata.category(c) != 'Cf')
    
    return text

def validate_vietnamese_text(text: str) -> bool:
    """Check if Vietnamese text is valid"""
    # Check for common Vietnamese characters
    vietnamese_chars = set('àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệ...')
    
    # Should have some Vietnamese chars
    has_vietnamese = any(c in vietnamese_chars for c in text)
    
    # Should not have weird encodings
    has_errors = any(ord(c) > 0xFFFF for c in text)
    
    return has_vietnamese and not has_errors
```

#### Giải pháp C: Manual Review Interface ⭐⭐⭐

Với các PDF khó, tạo interface để:
1. **Preview conversion** - xem output trước khi ingest
2. **Manual edit** - sửa lỗi encoding
3. **Mark problematic sections** - flag để xử lý sau
4. **Alternative upload** - cho phép upload Markdown manual

---

### 🟡 Vấn đề 2: Multi-Document Database Design

#### Giải pháp: Document Management System

**Schema Design:**

```python
# Document Registry Table
class Document(BaseModel):
    doc_id: str                    # unique identifier
    source_file: str               # "QCDT_2025.pdf"
    doc_type: str                  # "regulation", "guideline"
    title: str                     # "Quy chế đào tạo 2025"
    version: str                   # "v1.0"
    effective_date: Optional[date] # For legal docs
    
    # Processing metadata
    ingested_at: datetime
    num_chunks: int
    chunking_strategy: str         # "parent-child", "section-based"
    status: str                    # "active", "deprecated", "draft"
    
    # File tracking
    original_path: str
    markdown_path: str
    conversion_method: str         # "docling", "pymupdf"
    conversion_quality: float

# Chunk Registry
class Chunk(BaseModel):
    chunk_id: str                  # unique
    doc_id: str                    # foreign key to Document
    
    # Hierarchy
    level: str                     # "header", "parent", "child"
    parent_chunk_id: Optional[str] # for child chunks
    
    # Position
    sequence_number: int           # order in document
    
    # Content metadata
    chapter: Optional[str]
    article: Optional[str]
    clause: Optional[str]
    
    # Processing
    chunk_size: int
    has_table: bool
    created_at: datetime

# Cross References
class CrossReference(BaseModel):
    from_chunk_id: str
    to_chunk_id: str
    reference_text: str            # "theo quy định tại Điều 5"
    reference_type: str            # "explicit", "implicit"
```

**Implementation với PostgreSQL + pgvector:**

```sql
-- Documents table
CREATE TABLE documents (
    doc_id VARCHAR(50) PRIMARY KEY,
    source_file VARCHAR(255),
    title TEXT,
    version VARCHAR(20),
    effective_date DATE,
    ingested_at TIMESTAMP,
    num_chunks INTEGER,
    status VARCHAR(20),
    metadata JSONB
);

-- Chunks table
CREATE TABLE chunks (
    chunk_id VARCHAR(100) PRIMARY KEY,
    doc_id VARCHAR(50) REFERENCES documents(doc_id),
    level VARCHAR(20),
    parent_chunk_id VARCHAR(100),
    sequence_number INTEGER,
    content TEXT,
    embedding vector(1024),  -- pgvector extension
    metadata JSONB,
    created_at TIMESTAMP
);

-- Indexes
CREATE INDEX idx_chunks_doc ON chunks(doc_id);
CREATE INDEX idx_chunks_embedding ON chunks USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX idx_chunks_metadata ON chunks USING gin (metadata);
```

**Pipeline Integration:**

```python
class DocumentManager:
    def __init__(self, db_connection):
        self.db = db_connection
    
    def ingest_document(self, pdf_path: str, metadata: Dict):
        """Full document ingestion pipeline"""
        
        # 1. Register document
        doc_id = self._generate_doc_id(pdf_path)
        doc = Document(
            doc_id=doc_id,
            source_file=Path(pdf_path).name,
            **metadata
        )
        self.db.save_document(doc)
        
        # 2. Convert PDF
        markdown = self.conversion_pipeline.convert(pdf_path)
        
        # 3. Chunk
        chunks = self.chunker.chunk(markdown, doc_id=doc_id)
        
        # 4. Embed
        embeddings = self.embedder.embed_batch(chunks)
        
        # 5. Save to vector store
        self.vector_store.add_documents(chunks, embeddings)
        
        # 6. Update document stats
        doc.num_chunks = len(chunks)
        self.db.update_document(doc)
        
        return doc_id
    
    def update_document(self, doc_id: str, new_pdf: str):
        """Update existing document"""
        
        # 1. Mark old version as deprecated
        old_doc = self.db.get_document(doc_id)
        old_doc.status = "deprecated"
        self.db.update_document(old_doc)
        
        # 2. Delete old chunks from vector store
        self.vector_store.delete_by_filter({"doc_id": doc_id})
        
        # 3. Ingest new version
        new_doc_id = f"{doc_id}_v{get_next_version()}"
        self.ingest_document(new_pdf, metadata={
            "previous_version": doc_id
        })
    
    def list_documents(self, filters: Dict = None):
        """List all documents with stats"""
        return self.db.query_documents(filters)
```

---

### 🟡 Vấn đề 3: Chunking Strategy - Implement New Approach

Bạn muốn:
> "Chunk theo điều → chia nhỏ theo độ dài → có overlap"

**Implementation:**

```python
class HierarchicalOverlapChunker:
    """
    Strategy:
    1. Parse document theo điều (article level)
    2. Mỗi điều → chia thành sub-chunks với overlap
    3. Keep parent-child relationship
    """
    
    def __init__(
        self,
        chunk_size: int = 800,        # Target size for children
        chunk_overlap: int = 150,     # Overlap between chunks
        min_chunk_size: int = 400,    # Don't create too small chunks
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
        
        # Sentence splitter for Vietnamese
        self.sentence_splitter = self._init_vietnamese_splitter()
    
    def _init_vietnamese_splitter(self):
        """Split by Vietnamese sentence boundaries"""
        import re
        # Pattern: ends with . ! ? và theo sau là uppercase hoặc số
        pattern = r'(?<=[.!?])\s+(?=[A-ZĐÀÁẢÃẠÂẦẤẨẪẬĂẰẮẲẴẶÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴ\d])'
        return lambda text: re.split(pattern, text)
    
    def chunk_document(self, markdown: str) -> List[Dict]:
        """Main chunking logic"""
        
        # Phase 1: Parse articles
        articles = self._parse_articles(markdown)
        
        # Phase 2: Create parent + children for each article
        all_chunks = []
        for article in articles:
            chunks = self._process_article(article)
            all_chunks.extend(chunks)
        
        return all_chunks
    
    def _parse_articles(self, markdown: str) -> List[Dict]:
        """Parse document into articles"""
        articles = []
        current_chapter = None
        
        lines = markdown.split('\n')
        article_buffer = []
        current_article_metadata = {}
        
        for line in lines:
            # Detect chapter
            if re.match(r'^#\s+CHƯƠNG', line):
                current_chapter = line.strip('#').strip()
                continue
            
            # Detect article
            if re.match(r'^##\s+Điều\s+\d+', line):
                # Save previous article
                if article_buffer:
                    articles.append({
                        'content': '\n'.join(article_buffer),
                        'metadata': current_article_metadata
                    })
                
                # Start new article
                article_title = line.strip('#').strip()
                article_num = re.search(r'Điều\s+(\d+)', article_title).group(1)
                
                article_buffer = [article_title]
                current_article_metadata = {
                    'chapter': current_chapter,
                    'article': f'Điều {article_num}',
                    'article_full': article_title
                }
                continue
            
            # Regular content
            if article_buffer is not None:
                article_buffer.append(line)
        
        # Save last article
        if article_buffer:
            articles.append({
                'content': '\n'.join(article_buffer),
                'metadata': current_article_metadata
            })
        
        return articles
    
    def _process_article(self, article: Dict) -> List[Dict]:
        """Create parent + children chunks for one article"""
        
        content = article['content']
        metadata = article['metadata']
        
        # Parent chunk: full article
        parent_id = self._generate_chunk_id('parent', metadata)
        parent_chunk = {
            'chunk_id': parent_id,
            'level': 'parent',
            'content': content,
            'metadata': {
                **metadata,
                'chunk_size': len(content),
                'parent_id': None
            }
        }
        
        chunks = [parent_chunk]
        
        # Children: split with overlap
        if len(content) > self.chunk_size:
            child_chunks = self._split_with_overlap(
                content, 
                metadata,
                parent_id
            )
            chunks.extend(child_chunks)
        
        return chunks
    
    def _split_with_overlap(
        self, 
        text: str, 
        metadata: Dict,
        parent_id: str
    ) -> List[Dict]:
        """Split text into overlapping chunks"""
        
        # Split into sentences first
        sentences = self.sentence_splitter(text)
        
        chunks = []
        current_chunk = []
        current_size = 0
        chunk_idx = 0
        
        for i, sentence in enumerate(sentences):
            sentence_len = len(sentence)
            
            # Add sentence to current chunk
            current_chunk.append(sentence)
            current_size += sentence_len
            
            # Check if chunk is big enough
            if current_size >= self.chunk_size:
                # Save chunk
                chunk_content = ' '.join(current_chunk)
                chunks.append({
                    'chunk_id': f"{parent_id}_child_{chunk_idx}",
                    'level': 'child',
                    'content': chunk_content,
                    'metadata': {
                        **metadata,
                        'parent_id': parent_id,
                        'chunk_idx': chunk_idx,
                        'chunk_size': current_size,
                        'has_overlap': chunk_idx > 0
                    }
                })
                
                # Start new chunk with overlap
                # Keep last few sentences for overlap
                overlap_sentences = []
                overlap_size = 0
                for sent in reversed(current_chunk):
                    if overlap_size + len(sent) <= self.chunk_overlap:
                        overlap_sentences.insert(0, sent)
                        overlap_size += len(sent)
                    else:
                        break
                
                current_chunk = overlap_sentences
                current_size = overlap_size
                chunk_idx += 1
        
        # Save last chunk if it's big enough
        if current_size >= self.min_chunk_size:
            chunk_content = ' '.join(current_chunk)
            chunks.append({
                'chunk_id': f"{parent_id}_child_{chunk_idx}",
                'level': 'child',
                'content': chunk_content,
                'metadata': {
                    **metadata,
                    'parent_id': parent_id,
                    'chunk_idx': chunk_idx,
                    'chunk_size': current_size,
                    'has_overlap': chunk_idx > 0
                }
            })
        
        return chunks
    
    def _generate_chunk_id(self, level: str, metadata: Dict) -> str:
        """Generate unique chunk ID"""
        chapter = metadata.get('article', 'no_article')
        return f"{level}_{chapter}".replace(' ', '_').lower()
```

**Usage:**
```python
chunker = HierarchicalOverlapChunker(
    chunk_size=800,
    chunk_overlap=150,
    min_chunk_size=400
)

chunks = chunker.chunk_document(markdown_text)

# Example output:
# [
#   {
#     'chunk_id': 'parent_dieu_1',
#     'level': 'parent',
#     'content': 'Điều 1. ... (full article)',
#     'metadata': {'article': 'Điều 1', ...}
#   },
#   {
#     'chunk_id': 'parent_dieu_1_child_0',
#     'level': 'child',
#     'content': 'Điều 1. ... (first 800 chars)',
#     'metadata': {'parent_id': 'parent_dieu_1', ...}
#   },
#   ...
# ]
```

---

### 🟡 Vấn đề 4: No Evaluation Metrics

**Giải pháp: RAG Evaluation Framework**

```python
class RAGEvaluator:
    """Evaluate RAG system performance"""
    
    def __init__(self, rag_system, test_dataset):
        self.rag = rag_system
        self.test_data = test_dataset
    
    def evaluate_retrieval(self) -> Dict:
        """Evaluate retrieval quality"""
        
        metrics = {
            'recall@k': [],
            'mrr': [],
            'ndcg@k': []
        }
        
        for item in self.test_data:
            query = item['question']
            relevant_docs = item['relevant_chunk_ids']
            
            # Retrieve
            results = self.rag.pipeline.search(query, top_k=5)
            retrieved_ids = [r.chunk_id for r in results]
            
            # Calculate metrics
            metrics['recall@k'].append(
                self._recall_at_k(retrieved_ids, relevant_docs, k=5)
            )
            metrics['mrr'].append(
                self._mrr(retrieved_ids, relevant_docs)
            )
        
        # Average metrics
        return {
            k: sum(v) / len(v) 
            for k, v in metrics.items()
        }
    
    def _recall_at_k(self, retrieved, relevant, k):
        """Recall@K: % relevant docs in top-k"""
        top_k = retrieved[:k]
        hits = len(set(top_k) & set(relevant))
        return hits / len(relevant) if relevant else 0
    
    def _mrr(self, retrieved, relevant):
        """Mean Reciprocal Rank"""
        for i, doc_id in enumerate(retrieved, 1):
            if doc_id in relevant:
                return 1.0 / i
        return 0
    
    def evaluate_answer_quality(self) -> Dict:
        """Evaluate answer quality with LLM judge"""
        
        from openai import OpenAI
        judge = OpenAI()  # Use GPT-4 as judge
        
        scores = []
        for item in self.test_data:
            question = item['question']
            ground_truth = item['answer']
            
            # Generate answer
            result = self.rag.answer(question)
            generated = result['answer']
            
            # Judge quality
            judge_prompt = f"""
            Rate the quality of this answer on a scale of 1-5:
            
            Question: {question}
            Ground Truth: {ground_truth}
            Generated Answer: {generated}
            
            Criteria:
            - Accuracy
            - Completeness
            - Relevance
            - Clarity
            
            Output only a number 1-5.
            """
            
            score = judge.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": judge_prompt}]
            ).choices[0].message.content
            
            scores.append(float(score))
        
        return {
            'avg_quality_score': sum(scores) / len(scores),
            'scores': scores
        }
```

**Test Dataset Format:**
```json
{
    "test_cases": [
        {
            "question": "Sinh viên bị cảnh báo học vụ khi nào?",
            "answer": "Sinh viên bị cảnh báo khi CPA < 2.0...",
            "relevant_chunk_ids": ["parent_dieu_15", "parent_dieu_16"],
            "difficulty": "easy"
        },
        ...
    ]
}
```

---

### 🟡 Vấn đề 5: No Hybrid Search

**Giải pháp: Implement Hybrid Retrieval**

```python
from rank_bm25 import BM25Okapi

class HybridRetriever:
    """Combine semantic + keyword search"""
    
    def __init__(self, vector_store, documents):
        self.vector_store = vector_store
        
        # Build BM25 index
        self.doc_ids = [d.id for d in documents]
        self.doc_contents = [d.content for d in documents]
        tokenized = [self._tokenize(c) for c in self.doc_contents]
        self.bm25 = BM25Okapi(tokenized)
    
    def _tokenize(self, text: str) -> List[str]:
        """Vietnamese tokenization"""
        # Simple word split (better: use underthesea)
        import re
        return re.findall(r'\w+', text.lower())
    
    def search(
        self, 
        query: str, 
        top_k: int = 10,
        semantic_weight: float = 0.7,
        keyword_weight: float = 0.3
    ) -> List[SearchResult]:
        """Hybrid search with weighted combination"""
        
        # 1. Semantic search
        semantic_results = self.vector_store.search(
            query_embedding=self._embed(query),
            top_k=top_k * 2  # Get more candidates
        )
        
        # 2. BM25 keyword search
        query_tokens = self._tokenize(query)
        bm25_scores = self.bm25.get_scores(query_tokens)
        
        # 3. Normalize scores to [0, 1]
        semantic_scores = {
            r.chunk_id: r.score 
            for r in semantic_results
        }
        
        max_bm25 = max(bm25_scores) if max(bm25_scores) > 0 else 1
        bm25_scores_norm = {
            self.doc_ids[i]: score / max_bm25
            for i, score in enumerate(bm25_scores)
        }
        
        # 4. Combine scores
        all_doc_ids = set(semantic_scores.keys()) | set(bm25_scores_norm.keys())
        
        combined_scores = {}
        for doc_id in all_doc_ids:
            sem_score = semantic_scores.get(doc_id, 0)
            bm25_score = bm25_scores_norm.get(doc_id, 0)
            
            combined_scores[doc_id] = (
                semantic_weight * sem_score + 
                keyword_weight * bm25_score
            )
        
        # 5. Re-rank and return top-k
        sorted_ids = sorted(
            combined_scores.items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:top_k]
        
        results = []
        for doc_id, score in sorted_ids:
            # Get full document
            doc = self._get_document(doc_id)
            results.append(SearchResult(
                chunk_id=doc_id,
                content=doc.content,
                metadata=doc.metadata,
                score=score
            ))
        
        return results
```

**Khi nào dùng Hybrid?**
- ✅ Queries có keywords cụ thể: "điều 15", "GPA < 2.0"
- ✅ Acronyms: "CPA", "ĐHBK"
- ✅ Numbers và dates
- ❌ Conceptual questions: "Làm thế nào để..." (semantic tốt hơn)

---

## 3️⃣ ROADMAP MỞ RỘNG HỆ THỐNG

### Phase 1: Foundation (1-2 tuần) 🏗️

**Mục tiêu:** Stable PDF conversion + Multi-document support

1. **Implement Conversion Pipeline**
   - [ ] PDF type detection
   - [ ] Multi-tool with fallback
   - [ ] Vietnamese encoding fixes
   - [ ] Quality validation

2. **Database Schema**
   - [ ] Design document registry
   - [ ] Implement with PostgreSQL + pgvector
   - [ ] Migration script from FAISS
   - [ ] API for document management

3. **Chunking Strategy v2**
   - [ ] Implement overlapping chunker
   - [ ] Add parent-child support
   - [ ] Compare strategies
   - [ ] Choose best approach

**Deliverable:** Stable ingestion pipeline for multiple PDFs

---

### Phase 2: Enhanced Retrieval (1 tuần) 🔍

**Mục tiêu:** Better retrieval quality

1. **Hybrid Search**
   - [ ] Implement BM25
   - [ ] Combine with semantic search
   - [ ] Tune weights

2. **Re-ranking**
   - [ ] Add cross-encoder re-ranker
   - [ ] Context-aware scoring

3. **Evaluation**
   - [ ] Build test dataset (50-100 questions)
   - [ ] Implement metrics
   - [ ] Benchmark different strategies

**Deliverable:** Retrieval Recall@5 > 85%

---

### Phase 3: Advanced Features (2 tuần) 🚀

**Mục tiêu:** Production-ready system

1. **Multi-hop Reasoning**
   - [ ] Detect cross-references
   - [ ] Retrieve linked articles
   - [ ] Combine information

2. **Query Understanding**
   - [ ] Intent classification
   - [ ] Entity extraction
   - [ ] Query expansion

3. **Answer Quality**
   - [ ] Citation verification
   - [ ] Confidence scoring
   - [ ] Hallucination detection

4. **Frontend Enhancements**
   - [ ] Chat history
   - [ ] Source highlighting
   - [ ] Feedback collection
   - [ ] Analytics dashboard

**Deliverable:** Production-ready RAG chatbot

---

### Phase 4: Scale & Monitor (ongoing) 📊

1. **Monitoring**
   - [ ] Query analytics
   - [ ] Retrieval quality tracking
   - [ ] User feedback analysis

2. **Continuous Improvement**
   - [ ] A/B testing different strategies
   - [ ] Fine-tune based on user feedback
   - [ ] Update documents regularly

3. **Advanced Features**
   - [ ] Multi-language support
   - [ ] Voice input/output
   - [ ] Mobile app

---

## 4️⃣ TÓM TẮT KHUYẾN NGHỊ

### Ưu tiên cao (Làm ngay) 🔥

1. **Fix PDF conversion** - vấn đề nghiêm trọng nhất
   - Implement multi-stage pipeline
   - Add Vietnamese encoding fixes
   - Quality validation

2. **Document management** - cần cho multi-file
   - PostgreSQL + pgvector
   - Document registry
   - Update/delete mechanism

3. **Evaluation metrics** - để biết chất lượng
   - Build test dataset
   - Implement Recall@K, MRR
   - Benchmark current system

### Ưu tiên trung bình (1-2 tuần tới) ⚡

4. **Implement new chunking strategy** - đã plan tốt
   - Hierarchical với overlap
   - Parent-child architecture
   - Compare với current approach

5. **Hybrid search** - cải thiện retrieval
   - BM25 + semantic
   - Re-ranking

### Ưu tiên thấp (Sau này) 💡

6. **Advanced features**
   - Multi-hop reasoning
   - Query understanding
   - Frontend enhancements

---

## 5️⃣ ĐIỂM SỐ TỔNG QUAN

| Component | Score | Note |
|-----------|-------|------|
| **PDF Conversion** | ⭐⭐ / 5 | Vấn đề lớn nhất - cần ưu tiên fix |
| **Chunking** | ⭐⭐⭐⭐ / 5 | Strategy tốt, cần thêm options |
| **Embedding** | ⭐⭐⭐⭐ / 5 | Model choice xuất sắc |
| **Vector Store** | ⭐⭐⭐⭐ / 5 | Abstract design tốt |
| **LLM Integration** | ⭐⭐⭐ / 5 | Functional, cần robustness |
| **Multi-file Support** | ⭐⭐ / 5 | Basic, thiếu management |
| **API Backend** | ⭐⭐⭐ / 5 | Good for dev, cần improvements |
| **Frontend** | ⭐⭐⭐ / 5 | Basic but functional |
| **Evaluation** | ⭐ / 5 | Không có metrics |
| **Documentation** | ⭐⭐⭐⭐ / 5 | Rất tốt! |

### **Overall: ⭐⭐⭐ / 5**

**Tổng kết:** 
- ✅ Foundation tốt, architecture đúng hướng
- ⚠️ Cần fix PDF conversion urgently
- 💡 Nhiều tiềm năng để phát triển thành production system

---

## 📚 TÀI LIỆU THAM KHẢO

### Papers
1. **RAG Survey** - "Retrieval-Augmented Generation for Large Language Models: A Survey" (2024)
2. **Chunking Strategies** - "Lost in the Middle: How Language Models Use Long Contexts" (2023)
3. **Vietnamese NLP** - PhoBERT, ViT5 papers

### Tools & Libraries
- **Vector DBs:** pgvector, ChromaDB, Weaviate
- **Embeddings:** sentence-transformers, intfloat/e5
- **Retrieval:** LangChain, LlamaIndex
- **Evaluation:** RAGAS, TruLens

### Best Practices
- LangChain RAG documentation
- Pinecone RAG guide
- Anthropic RAG cookbook

---

*Đánh giá chi tiết này được tạo để giúp bạn có roadmap rõ ràng để phát triển hệ thống RAG. Nếu cần clarification về bất kỳ phần nào, hãy hỏi!* ✨
