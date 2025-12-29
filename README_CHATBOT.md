# RAG Chatbot - Quy Chế Đào Tạo HUST

Hệ thống chatbot RAG (Retrieval-Augmented Generation) để trả lời câu hỏi về Quy chế đào tạo Đại học Bách khoa Hà Nội.

## Cấu trúc dự án

```
GR/
├── backend/              # FastAPI backend
│   ├── main.py          # API server
│   ├── logger.py        # CSV logging utility
│   ├── requirements.txt # Python dependencies
│   └── rag_logs.csv     # File log (tự động tạo)
├── frontend/            
│   └── my-app/          # React + TypeScript frontend
│       ├── src/
│       │   ├── App.tsx  # Main component
│       │   └── App.css  # Styles
│       └── package.json
└── src/RAG/             # RAG system
    ├── embedding/       # Vector store & embeddings
    └── LLM/            # LLM integration
        └── llm.py      # Gemini RAG class
```

## Tính năng

✅ **Chat Interface**: Giao diện chatbot thân thiện  
✅ **RAG System**: Truy xuất tài liệu liên quan và sinh câu trả lời  
✅ **Source Display**: Hiển thị nguồn tham khảo với metadata  
✅ **CSV Logging**: Tự động lưu câu hỏi, retrieved docs, và câu trả lời  
✅ **CORS Enabled**: Hỗ trợ kết nối frontend-backend

## Cài đặt

### 1. Backend Setup

```bash
# Di chuyển vào thư mục backend
cd backend

# Cài đặt dependencies
pip install -r requirements.txt
```

### 2. Frontend Setup

```bash
# Di chuyển vào thư mục frontend
cd frontend/my-app

# Cài đặt dependencies (nếu chưa có)
npm install
```

### 3. Environment Variables

Tạo file `.env` trong thư mục gốc `GR/` với nội dung:

```env
GEMINI_API_KEY=your_gemini_api_key_here
```

## Chạy ứng dụng

### Bước 1: Khởi động Backend

```bash
cd backend
python main.py
```

Backend sẽ chạy tại: `http://localhost:8000`

API Endpoints:
- `GET /` - Health check
- `GET /health` - Kiểm tra RAG system
- `POST /chat` - Chat endpoint

### Bước 2: Khởi động Frontend

Mở terminal mới:

```bash
cd frontend/my-app
npm run dev
```

Frontend sẽ chạy tại: `http://localhost:5173`

## Sử dụng

1. Mở trình duyệt tại `http://localhost:5173`
2. Nhập câu hỏi vào ô input
3. Nhấn "🚀 Gửi" hoặc Enter
4. Xem câu trả lời và nguồn tham khảo
5. Tất cả interactions được tự động lưu vào `backend/rag_logs.csv`

## CSV Log Format

File `rag_logs.csv` chứa:
- **timestamp**: Thời gian hỏi
- **question**: Câu hỏi của user
- **answer**: Câu trả lời của LLM
- **num_retrieved_docs**: Số lượng tài liệu truy xuất được
- **retrieved_docs**: Chi tiết các documents (JSON format) bao gồm:
  - rank: Thứ hạng
  - content: Nội dung
  - score: Độ liên quan
  - metadata: Thông tin file, điều khoản, chương
- **model_name**: Tên model LLM sử dụng

## API Usage Example

### Request

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "question": "khi nào sinh viên bị cảnh báo mức 2",
    "top_k": 3
  }'
```

### Response

```json
{
  "question": "khi nào sinh viên bị cảnh báo mức 2",
  "answer": "Sinh viên bị cảnh báo học vụ mức 2 khi...",
  "retrieved_documents": [
    {
      "rank": 1,
      "content": "Nội dung tài liệu...",
      "score": 0.95,
      "metadata": {
        "source_file": "quy_che.pdf",
        "article": "Điều 15"
      }
    }
  ],
  "num_documents": 3,
  "model_name": "models/gemini-2.5-flash"
}
```

## Troubleshooting

### Backend không khởi động được
- Kiểm tra đã cài đặt `pip install -r backend/requirements.txt`
- Kiểm tra file `.env` có `GEMINI_API_KEY` chưa
- Kiểm tra vector store đã được tạo trong `src/RAG/embedding/`

### Frontend không kết nối được backend
- Kiểm tra backend đang chạy tại `localhost:8000`
- Kiểm tra CORS settings trong `backend/main.py`
- Kiểm tra URL trong `frontend/my-app/src/App.tsx`

### Vector store not found
- Chạy embedding script trước:
  ```bash
  cd src/RAG/embedding
  python main.py
  ```

## Tech Stack

**Backend:**
- FastAPI
- Python 3.x
- Google Gemini API
- Custom RAG pipeline

**Frontend:**
- React 18
- TypeScript
- Vite
- CSS3

## Notes

- Mỗi lần hỏi đáp sẽ tự động lưu vào CSV
- Frontend hiển thị nguồn tham khảo để user kiểm chứng
- Backend có thể scale để xử lý nhiều requests
- Log file có thể dùng cho báo cáo, phân tích sau này
