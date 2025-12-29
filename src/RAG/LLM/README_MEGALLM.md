# RAG với MegaLLM

Hệ thống RAG sử dụng MegaLLM API để trả lời câu hỏi về Quy chế đào tạo.

## 🚀 Setup

### 1. Cài đặt dependencies

```bash
pip install requests python-dotenv
```

### 2. Cấu hình API Key

Thêm vào file `.env` ở thư mục gốc (d:\GR\.env):

```bash
# MegaLLM Configuration
MEGALLM_API_KEY=your_megallm_api_key_here

# Optional: Custom endpoint
MEGALLM_API_URL=https://api.mega-llm.com/v1/chat/completions

# Optional: Custom model
MEGALLM_MODEL=mega-chat
```

### 3. Các API endpoints phổ biến

MegaLLM có thể tương thích với nhiều providers:

#### OpenAI-compatible APIs:
```bash
MEGALLM_API_URL=https://api.openai.com/v1/chat/completions
MEGALLM_MODEL=gpt-3.5-turbo
```

#### Groq:
```bash
MEGALLM_API_URL=https://api.groq.com/openai/v1/chat/completions
MEGALLM_MODEL=llama-3.1-70b-versatile
```

#### Together AI:
```bash
MEGALLM_API_URL=https://api.together.xyz/v1/chat/completions
MEGALLM_MODEL=mistralai/Mixtral-8x7B-Instruct-v0.1
```

#### Hugging Face:
```bash
MEGALLM_API_URL=https://api-inference.huggingface.co/models/YOUR_MODEL/v1/chat/completions
MEGALLM_MODEL=mistralai/Mistral-7B-Instruct-v0.2
```

## 💻 Sử dụng

### Mode 1: Interactive (Khuyến nghị)

```bash
cd D:\GR\src\RAG\LLM
python main_megallm.py
```

### Mode 2: Test Script

```bash
python llm_megallm.py
```

### Mode 3: Import vào code

```python
from llm_megallm import MegaLLMRAG
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("MEGALLM_API_KEY")

# Initialize
rag = MegaLLMRAG(api_key=api_key)

# Ask question
result = rag.answer(
    question="khi nào sinh viên bị cảnh báo?",
    top_k=5,
    stream=True
)

print(result['answer'])
```

## 🔧 Configuration

### Các tham số khởi tạo:

```python
rag = MegaLLMRAG(
    api_key="your_key",
    api_url="https://api.mega-llm.com/v1/chat/completions",
    model_name="mega-chat",
    pipeline=None  # Optional: pre-loaded pipeline
)
```

### Các tham số answer():

```python
result = rag.answer(
    question="câu hỏi",
    top_k=5,              # Số chunks retrieve
    filters={"source_file": "QCDT_2025"},  # Filter theo file
    stream=True,          # Stream output
    verbose=True          # Show logs
)
```

## 📊 API Format

Script này sử dụng **OpenAI-compatible API format**:

### Request:
```json
{
  "model": "mega-chat",
  "messages": [
    {
      "role": "user",
      "content": "prompt here"
    }
  ],
  "temperature": 0.1,
  "max_tokens": 2048,
  "stream": true
}
```

### Response (non-streaming):
```json
{
  "choices": [
    {
      "message": {
        "content": "answer here"
      }
    }
  ]
}
```

### Response (streaming):
```
data: {"choices": [{"delta": {"content": "token"}}]}
data: {"choices": [{"delta": {"content": " here"}}]}
data: [DONE]
```

## 🔍 Troubleshooting

### 1. API Connection Error

Kiểm tra:
- API URL đúng format
- API key hợp lệ
- Internet connection

### 2. Model không tồn tại

Kiểm tra tên model trong docs của provider:
```bash
MEGALLM_MODEL=correct-model-name
```

### 3. Rate limit error

Giảm số request hoặc đợi reset:
```python
result = rag.answer(question, top_k=3)  # Giảm top_k
```

### 4. Timeout

Tăng timeout trong code:
```python
# Sửa trong llm_megallm.py
response = requests.post(..., timeout=120)  # Tăng từ 60 lên 120s
```

## 🎯 Ưu điểm so với Gemini

✅ Không bị quota limit nghiêm ngặt  
✅ Tương thích nhiều providers  
✅ Có thể self-host  
✅ Control được cost  

## 📝 Examples

### Example 1: Sử dụng Groq (miễn phí, nhanh)

```bash
# .env
MEGALLM_API_KEY=your_groq_api_key
MEGALLM_API_URL=https://api.groq.com/openai/v1/chat/completions
MEGALLM_MODEL=llama-3.1-70b-versatile
```

```bash
python main_megallm.py
```

### Example 2: Sử dụng OpenAI

```bash
# .env
MEGALLM_API_KEY=sk-...
MEGALLM_API_URL=https://api.openai.com/v1/chat/completions
MEGALLM_MODEL=gpt-4o-mini
```

### Example 3: Self-hosted với Ollama

```bash
# .env
MEGALLM_API_KEY=dummy  # Ollama không cần key
MEGALLM_API_URL=http://localhost:11434/v1/chat/completions
MEGALLM_MODEL=llama3
```

## 🔄 So sánh với Gemini

| Feature | Gemini | MegaLLM |
|---------|--------|---------|
| Setup | Dễ | Trung bình |
| Quota | Thấp (free tier) | Tùy provider |
| Speed | Nhanh | Tùy provider |
| Cost | Free → Paid | Đa dạng |
| Flexibility | Thấp | Cao |

## 📚 Providers phổ biến

1. **Groq** - Miễn phí, rất nhanh
2. **OpenRouter** - Nhiều models, pay-as-you-go
3. **Together AI** - Open source models
4. **Perplexity** - Specialized for RAG
5. **Fireworks AI** - Fast inference

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
MegaLLM API (HTTP)
    ↓
Answer (Stream/Non-stream)
```
