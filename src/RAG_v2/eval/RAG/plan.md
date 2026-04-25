# Eval Module — Hướng dẫn sử dụng

Pipeline đánh giá chất lượng retrieval hệ thống RAG hỗ trợ sinh viên ĐHBK Hà Nội.

## Cấu trúc

```
eval/
├── llm_judge.py          # LLM judge: Gemini / LM Studio / Auto
├── dataset_generator.py  # Tạo synthetic Q&A dataset từ Qdrant
├── run_eval.py           # Chạy RAGAS evaluation
├── tune_retrieval.py     # Grid search optimal hyperparameters
├── data/
│   └── golden_dataset.jsonl
└── results/
    ├── summary_latest.json
    └── results_latest.csv
```

## Cài đặt

```bash
pip install ragas datasets langchain-google-genai langchain-openai \
            google-generativeai openai langchain-community sentence-transformers
```

## Setup LLM Judge

### Option A — Google Gemini (có rate limit ~15 RPM free tier)
```bash
export GEMINI_API_KEY="your_gemini_api_key"
export GEMINI_MODEL="gemini-1.5-flash"   # mặc định
```

### Option B — LM Studio + Qwen3 8B (local, không rate limit) ← Khuyến nghị
1. Mở LM Studio → Load model `Qwen3-8B` hoặc `Qwen3-8B-Instruct`
2. Tab **Local Server** → Start Server (port 1234 mặc định)
3. (Tuỳ chọn) Load thêm 1 embedding model như `nomic-embed-text` để RAGAS dùng local embeddings

```bash
export LMSTUDIO_BASE_URL="http://localhost:1234/v1"   # mặc định
export LMSTUDIO_MODEL="qwen3-8b"                      # tên model trong LM Studio
```

> **Qwen3 thinking mode:** Script tự động strip `<think>...</think>` và thêm `/no_think`
> vào cuối prompt để tắt thinking, giảm latency đáng kể.

### Option C — Auto (Gemini → fallback LM Studio khi rate limited)
Set cả `GEMINI_API_KEY` và chạy LM Studio. Script tự chọn.

### Test backend trước khi dùng
```bash
python eval/llm_judge.py --backend lmstudio
python eval/llm_judge.py --backend gemini
python eval/llm_judge.py --backend auto
```

---

## Workflow

### Bước 1 — Tạo Dataset

```bash
# LM Studio (không rate limit, chạy offline)
python eval/dataset_generator.py --llm lmstudio

# Chỉ 1 collection, 50 chunks, 3 Q/chunk
python eval/dataset_generator.py --llm lmstudio --collection ctdt --samples 50 --questions-per-chunk 3

# Custom model name
python eval/dataset_generator.py --llm lmstudio --lmstudio-model "qwen3-8b-instruct"

# Gemini (nhanh hơn nhưng có rate limit)
python eval/dataset_generator.py --llm gemini
```

### Bước 2 — Eval nhanh (không cần LLM, chạy trong vài phút)

```bash
python eval/run_eval.py --retrieval-only
python eval/run_eval.py --retrieval-only --collection ctdt
python eval/run_eval.py --retrieval-only --top-k 10
```

### Bước 3 — Eval đầy đủ (RAGAS metrics)

```bash
# LM Studio (khuyến nghị)
python eval/run_eval.py --llm lmstudio

# Gemini
python eval/run_eval.py --llm gemini

# Tuỳ chỉnh
python eval/run_eval.py --llm lmstudio --collection ctdt --top-k 10 \
    --vector-weight 0.6 --keyword-weight 0.4
```

### Bước 4 — Tune Hyperparameters

```bash
python eval/tune_retrieval.py --dataset eval/data/golden_dataset.jsonl
python eval/tune_retrieval.py --collection ctdt --metric mrr
```

---

## Metrics

| Metric | Ý nghĩa | Target |
|---|---|---|
| `hit_rate@5` | % câu hỏi có correct doc trong top-5 | > 0.75 |
| `mrr@5` | Mean Reciprocal Rank (1.0 = luôn ở rank 1) | > 0.60 |
| `context_precision` | % retrieved chunks thực sự relevant | > 0.70 |
| `context_recall` | % thông tin cần đã được retrieve | > 0.65 |
| `faithfulness` | Answer bám sát context không | > 0.85 |
| `answer_relevancy` | Answer trả lời đúng câu hỏi không | > 0.80 |

---

## Tips

- **Chạy retrieval-only trước** để nhanh chóng biết baseline, sau mới dùng RAGAS full.
- **LM Studio vs Gemini cho scoring:** Qwen3 8B có thể khắt khe hơn với tiếng Việt. Nên chạy cả hai trên cùng dataset nhỏ để calibrate.
- **Dataset size:** 30 chunks × 4 collections × 2 Q/chunk = ~240 Q&A là đủ để có kết quả tin cậy.
- **LMSTUDIO_MODEL phải khớp** với tên hiển thị trong LM Studio. Test bằng `llm_judge.py` trước.