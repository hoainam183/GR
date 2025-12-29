# Hướng dẫn Setup - Sử dụng 1 Virtual Environment Chung

## Tạo Virtual Environment ở Root Level

```powershell
# Di chuyển vào thư mục gốc
cd D:\GR

# Tạo virtual environment
python -m venv venv

# Kích hoạt virtual environment
.\venv\Scripts\Activate.ps1
```

## Cài đặt Dependencies

```powershell
# Cài tất cả dependencies
pip install -r requirements.txt
```

**Lưu ý:** Nếu gặp lỗi với `tokenizers` (cần Rust compiler):
```powershell
# Cài pre-built wheels
pip install tokenizers sentencepiece --only-binary :all:
```

## Cấu trúc Thư mục & Import

Sau khi dùng venv chung, cấu trúc như sau:

```
D:\GR\
├── venv\              # Virtual environment chung
├── .env               # Environment variables
├── requirements.txt   # Dependencies chung
├── backend\
│   ├── main.py       # Backend import từ src/RAG
│   └── logger.py
├── src\
│   └── RAG\
│       ├── embedding\
│       └── LLM\
└── frontend\
    └── my-app\
```

## Chạy Backend

```powershell
# Từ D:\GR với venv activated
cd backend
python main.py
```

Backend sẽ tự động import từ `src/RAG/LLM` nhờ:
```python
sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "RAG" / "LLM"))
```

## Chạy Frontend

```powershell
# Terminal mới
cd D:\GR\frontend\my-app
npm run dev
```

## Kiểm tra Setup

```powershell
# Kiểm tra packages đã cài
pip list | Select-String -Pattern "langchain|faiss|fastapi|sentence"

# Test import
python -c "from langchain_huggingface import HuggingFaceEmbeddings; print('OK')"
python -c "import faiss; print('OK')"
python -c "import google.generativeai as genai; print('OK')"
```

## Chạy các Script khác

Với venv chung, bạn có thể chạy bất kỳ script nào:

```powershell
# Activate venv (nếu chưa)
.\venv\Scripts\Activate.ps1

# Chạy embedding
cd src\RAG\embedding
python main.py

# Chạy LLM test
cd ..\LLM
python llm.py

# Chạy backend
cd ..\..\..\backend
python main.py
```

## Troubleshooting

### 1. Import Error khi chạy backend
```powershell
# Đảm bảo đang ở D:\GR và venv activated
cd D:\GR
.\venv\Scripts\Activate.ps1
python backend\main.py
```

### 2. Module not found
```powershell
# Cài lại requirements
pip install -r requirements.txt
```

### 3. Vector store not found
```powershell
# Tạo vector store trước
cd src\RAG\embedding
python main.py
```

### 4. PaddleOCR/PaddlePaddle errors
Nếu không cần OCR, comment out trong requirements.txt:
```
# paddleocr>=3.3.2
# paddlepaddle==3.2.1
```

## So sánh với cách cũ

**Trước (2 venv):**
```
D:\GR\backend\venv\     # Venv riêng cho backend
D:\GR\src\venv\         # Venv riêng cho src
→ Conflict khi backend import từ src
```

**Sau (1 venv chung):**
```
D:\GR\venv\             # Venv chung cho cả project
→ Không còn conflict, dễ quản lý
```

## Alternative: Sử dụng pyproject.toml

Nếu muốn dùng `uv` hoặc modern Python tooling:

```powershell
# Install uv
pip install uv

# Sync dependencies từ pyproject.toml
uv sync

# Run với uv
uv run python backend/main.py
```

Nhưng với requirements.txt đơn giản hơn và hoạt động với pip thông thường.
