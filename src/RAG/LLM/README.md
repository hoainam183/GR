# LLM Module

Hệ thống RAG (Retrieval-Augmented Generation) sử dụng Google Gemini để trả lời câu hỏi về Quy chế đào tạo.

## 📁 Cấu trúc thư mục

```
LLM/
├── llm.py              # Core GeminiRAG class
├── main.py             # Interactive mode script
├── requirements.txt    # Dependencies
└── README.md           # Documentation
```

## 🚀 Setup

### 1. Cài đặt dependencies

```bash
pip install -r requirements.txt
```

### 2. Tạo API Key

1. Truy cập: https://makersuite.google.com/app/apikey
2. Tạo API key mới
3. Copy key vào file `.env` ở thư mục gốc dự án:

```bash
# File: d:\GR\.env
GEMINI_API_KEY=your_api_key_here
```

### 3. Đảm bảo đã có Vector Store

Trước khi chạy RAG, cần có vector store đã được tạo từ bước embedding:

```bash
cd ../embedding
python run_embedding.py
```

## 💻 Sử dụng

### Mode 1: Interactive (Khuyến nghị)

Chạy chương trình tương tác:

```bash
python main.py
```

Sau đó bạn có thể:
- Đặt câu hỏi trực tiếp
- Filter theo file nguồn: `source:QCDT_2025`
- Xóa filter: `clear filter`
- Thoát: `quit` hoặc `exit`

### Mode 2: Test Script

Chạy test với câu hỏi mẫu:

```bash
python llm.py
```

### Mode 3: Import vào code của bạn

```python
from llm import GeminiRAG
import os
from dotenv import load_dotenv

# Load API key
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

# Initialize
rag = GeminiRAG(api_key=api_key)

# Ask question
result = rag.answer(
    question="khi nào sinh viên bị cảnh báo?",
    top_k=5,
    stream=True,
    verbose=True
)

# Access results
print(f"Answer: {result['answer']}")
print(f"Sources: {result['num_sources']}")
```

## 🔧 Configuration

### Các tham số của `answer()`:

- `question` (str): Câu hỏi của người dùng
- `top_k` (int): Số lượng chunks retrieve (default: 3)
- `filters` (dict): Lọc theo metadata (VD: `{"source_file": "QCDT_2025"}`)
- `stream` (bool): Stream output từ LLM (default: False)
- `verbose` (bool): Hiển thị log chi tiết (default: True)

### Model configuration:

Trong class `GeminiRAG.__init__()`:

```python
rag = GeminiRAG(
    api_key="your_key",
    model_name="models/gemini-2.0-flash-exp"  # Hoặc model khác
)
```

Available models:
- `models/gemini-2.0-flash-exp` (Mặc định - nhanh, free)
- `models/gemini-1.5-pro`
- `models/gemini-1.5-flash`

### Generation parameters:

Trong `_get_gemini_response()`, bạn có thể điều chỉnh:

```python
generation_config = {
    "temperature": 0.1,      # Tăng để creative hơn (0-1)
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 2048,  # Độ dài tối đa
}
```

## 📊 Output Format

Kết quả trả về là dictionary:

```python
{
    "question": "câu hỏi của bạn",
    "answer": "câu trả lời từ LLM",
    "sources": [SearchResult],  # List các chunks được retrieve
    "context": "context đầy đủ đã gửi cho LLM",
    "num_sources": 5,
    "llm_provider": "gemini",
    "model_name": "models/gemini-2.0-flash-exp"
}
```

## 🎯 Prompt Engineering

Prompt được định nghĩa trong `_build_prompt()`. Bạn có thể tùy chỉnh:

```python
def _build_prompt(self, question: str, context: str) -> str:
    prompt = f"""Bạn là trợ lý AI chuyên về Quy chế đào tạo...
    
    Ngữ cảnh: {context}
    
    Câu hỏi: {question}
    
    Hướng dẫn:
    1. Trả lời chính xác
    2. Giải thích rõ ràng
    ...
    """
    return prompt
```

## 🔍 Troubleshooting

### 1. Error: Vector store not found

```bash
cd ../embedding
python run_embedding.py
```

### 2. Error: GEMINI_API_KEY not found

Kiểm tra file `.env` ở thư mục gốc (d:\GR\.env)

### 3. Import errors

Đảm bảo cài đặt đủ dependencies:

```bash
pip install google-generativeai python-dotenv
```

### 4. Slow response

- Giảm `top_k` (số chunks retrieve)
- Sử dụng model flash thay vì pro
- Tắt verbose mode

## 📝 Examples

### Example 1: Câu hỏi đơn giản

```python
result = rag.answer("điều kiện tốt nghiệp là gì?", top_k=3)
```

### Example 2: Filter theo file

```python
result = rag.answer(
    question="quy định về học phí",
    filters={"source_file": "QCDT_2025"}
)
```

### Example 3: Stream mode

```python
result = rag.answer(
    question="các mức cảnh báo học tập",
    stream=True  # In ra từng token
)
```

## 🎓 Workflow

```
User Question
    ↓
Embedding (E5 model)
    ↓
Vector Search (FAISS)
    ↓
Top K chunks
    ↓
Build Context
    ↓
Build Prompt
    ↓
Gemini LLM
    ↓
Answer
```

## 📚 Documentation

- [Gemini API](https://ai.google.dev/)
- [RAG Overview](https://python.langchain.com/docs/use_cases/question_answering/)
- [FAISS](https://github.com/facebookresearch/faiss)
