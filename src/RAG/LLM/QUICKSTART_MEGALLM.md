# 🚀 Quick Start - MegaLLM RAG

## Bước 1: Lấy API Key (chọn 1 trong các options)

### 🌟 Option 1: Groq (Miễn phí, Nhanh - KHUYẾN NGHỊ)
1. Truy cập: https://console.groq.com/
2. Đăng ký tài khoản miễn phí
3. Tạo API key
4. Copy key

### Option 2: OpenRouter (Nhiều models)
1. Truy cập: https://openrouter.ai/
2. Đăng ký
3. Tạo API key
4. Nạp credit ($5 là đủ dùng lâu)

### Option 3: OpenAI (Trả phí)
1. Truy cập: https://platform.openai.com/
2. Tạo API key
3. Nạp tiền

## Bước 2: Cấu hình .env

Mở file `d:\GR\.env` và sửa:

### Ví dụ với Groq:
```bash
MEGALLM_API_KEY = gsk_xxxxxxxxxxxxxxxxxxxxx
MEGALLM_API_URL = https://api.groq.com/openai/v1/chat/completions
MEGALLM_MODEL = llama-3.1-70b-versatile
```

### Ví dụ với OpenRouter:
```bash
MEGALLM_API_KEY = sk-or-v1-xxxxxxxxxxxxxxxxxxxxx
MEGALLM_API_URL = https://openrouter.ai/api/v1/chat/completions
MEGALLM_MODEL = google/gemini-flash-1.5
```

## Bước 3: Chạy

```bash
cd D:\GR\src\RAG\LLM
python main_megallm.py
```

## 🎯 Test nhanh

```bash
python llm_megallm.py
```

## 💡 Tips

### Groq - Models tốt nhất:
- `llama-3.1-70b-versatile` - Tốt nhất, balanced
- `mixtral-8x7b-32768` - Context dài
- `gemma2-9b-it` - Nhẹ, nhanh

### OpenRouter - Models giá rẻ:
- `google/gemini-flash-1.5` - $0.075/1M tokens
- `anthropic/claude-3-haiku` - $0.25/1M tokens
- `meta-llama/llama-3.1-8b-instruct` - Free

### Kiểm tra hoạt động:
```bash
# Test API connection
curl https://api.groq.com/openai/v1/models \
  -H "Authorization: Bearer $MEGALLM_API_KEY"
```

## ❓ Troubleshooting

**Lỗi: Unauthorized**
→ Kiểm tra API key trong .env

**Lỗi: Model not found**
→ Kiểm tra tên model, xem docs của provider

**Lỗi: Rate limit**
→ Đợi vài giây hoặc đổi provider

## 📞 Support

- Groq docs: https://console.groq.com/docs
- OpenRouter docs: https://openrouter.ai/docs
- Issues: Check README_MEGALLM.md
