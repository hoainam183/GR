# RAG Evaluation Module

Module đánh giá hệ thống RAG cho tài liệu ĐHBK Hà Nội (HEDSPI curriculum + Quy định ngoại ngữ K70).

## Cấu trúc thư mục

```
rag_eval/
├── main_eval.py              ← Điểm vào chính
├── requirements.txt
├── data/
│   ├── ITE6_fix_chunks.json
│   └── 06__Quy_dinh_ngoai_ngu_K70_chunks.json
├── src/
│   ├── config.py             ← Cấu hình backend và tham số
│   ├── chunk_loader.py       ← Đọc, lọc, lấy mẫu chunks
│   ├── llm_client.py         ← Wrapper LMStudio / Gemini
│   ├── qa_generator.py       ← Sinh câu hỏi + ground truth
│   └── evaluator.py          ← Chạy RAGAS metrics
└── outputs/                  ← Kết quả tự động lưu tại đây
```

## Cài đặt

```bash
pip install -r requirements.txt
```

Sao chép file chunk JSON vào thư mục `data/`.

## Sử dụng

### 1. Với LMStudio (Qwen3 8B — chạy local)

> Yêu cầu: LMStudio đang chạy với model **Qwen3 8B** được load.
> Đảm bảo Local Server đang bật tại `http://localhost:1234`.

```bash
# Chạy đầy đủ (sinh QA + đánh giá)
python main_eval.py --backend lmstudio

# Tùy chỉnh số lượng
python main_eval.py --backend lmstudio --max-chunks 20 --questions-per-chunk 3

# Chỉ sinh QA dataset (tiết kiệm thời gian nếu chưa muốn đánh giá)
python main_eval.py --backend lmstudio --generate-only
```

**Lưu ý Qwen3**: Module tự động thêm `/no_think` vào prompt để tắt thinking mode,
giúp tiết kiệm token và tăng tốc độ xử lý.

### 2. Với Google Gemini

```bash
# Cách 1: truyền API key trực tiếp
python main_eval.py --backend gemini --api-key YOUR_GOOGLE_API_KEY

# Cách 2: set environment variable
export GOOGLE_API_KEY=YOUR_GOOGLE_API_KEY
python main_eval.py --backend gemini
```

Model mặc định: `gemini-2.0-flash` (nhanh, rẻ). Đổi sang `gemini-1.5-pro` trong `config.py` nếu cần độ chính xác cao hơn.

### 3. Load QA dataset đã có sẵn

```bash
# Bỏ qua bước generation, chỉ chạy RAGAS evaluation
python main_eval.py --backend lmstudio --qa-file outputs/qa_dataset_lmstudio_20250101_120000.json
```

## Tùy chỉnh nâng cao

### Thay đổi tỷ lệ loại câu hỏi (`src/config.py`)

```python
cfg.question_type_ratios = {
    "factoid":     0.40,   # Câu hỏi sự kiện cụ thể
    "multi_hop":   0.30,   # Cần kết hợp nhiều thông tin
    "comparative": 0.10,   # So sánh
    "procedural":  0.20,   # Quy trình, điều kiện
}
```

### Thêm metrics RAGAS

```python
cfg.ragas_metrics = [
    "faithfulness",
    "answer_relevancy",
    "context_precision",
    "context_recall",
    # Thêm: "answer_correctness" nếu muốn so sánh với ground truth
]
```

### Đổi embedding model trong LMStudio

Trong `src/llm_client.py`, dòng `model="text-embedding-nomic-embed-text-v1.5"` —
đổi thành tên embedding model bạn đang load trong LMStudio.

## Output files

| File | Mô tả |
|------|-------|
| `outputs/qa_dataset_*.json` | QA Dataset (câu hỏi + ground truth + context) |
| `outputs/eval_result_*.json` | RAGAS scores (overall + per-sample) |

## RAGAS Metrics giải thích

| Metric | Ý nghĩa | Điểm tốt |
|--------|---------|-----------|
| **faithfulness** | Answer có trung thực với context không? Phát hiện hallucination. | > 0.8 |
| **answer_relevancy** | Answer có trả lời đúng question không? | > 0.8 |
| **context_precision** | Context retrieve được có chứa đúng thông tin cần thiết không? | > 0.7 |
| **context_recall** | Ground truth có được bao phủ bởi context không? | > 0.7 |

## Tips & Troubleshooting

**LMStudio không phản hồi:**
- Kiểm tra LMStudio Local Server đang chạy (cổng 1234)
- Model Qwen3 8B đã được load
- Tăng `timeout` trong `LMStudioConfig` nếu máy chậm

**Gemini quota error:**
- Dùng `gemini-2.0-flash` thay vì `gemini-1.5-pro`
- Giảm `max_chunks_to_sample` xuống 10-15

**RAGAS điểm thấp bất thường:**
- Kiểm tra context có đủ dài để trả lời câu hỏi không
- Thử tăng `min_chunk_size` để lọc chunk quá ngắn
- Với LMStudio, LLM nhỏ (8B) có thể không đủ mạnh làm "judge" — cân nhắc dùng Gemini cho bước evaluation
