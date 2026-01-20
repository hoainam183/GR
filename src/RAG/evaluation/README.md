# Evaluation Module

Module đánh giá hiệu suất của RAG system với các metrics cho retrieval và generation.

## 📁 Cấu trúc thư mục

```
evaluation/
├── __init__.py              # Module exports
├── evaluate_rag.py          # Full RAG evaluation (retrieval + generation)
├── evaluate_retrieval.py    # Retrieval-only evaluation
├── run_evaluation.py        # Quick run script
└── retrieval_results/       # Saved evaluation results
```

## 🚀 Quick Start

### 1. Chuẩn bị evaluation dataset

Dataset là file CSV với các columns:
- `question`: Câu hỏi
- `answer`: Câu trả lời ground truth
- `document_source`: Source file mong đợi
- `question_type`: Loại câu hỏi (factual, inference, etc.)
- `difficulty`: Độ khó (easy, medium, hard)
- `relevant_context`: Context liên quan (optional)

Ví dụ:
```csv
question,answer,document_source,question_type,difficulty,relevant_context
Điều kiện tốt nghiệp là gì?,Sinh viên cần hoàn thành...,QCDT_2025,factual,easy,Điều 15...
```

### 2. Chạy evaluation retrieval

```python
from evaluate_retrieval import RetrievalEvaluator

# Initialize evaluator
evaluator = RetrievalEvaluator(top_k=5, verbose=True)

# Load pipeline
evaluator.load_pipeline()

# Load dataset
samples = evaluator.load_dataset("../../rag_evaluation_dataset.csv")

# Evaluate
report = evaluator.evaluate(samples)

# Print results
evaluator.print_report(report)
```

### 3. Chạy full RAG evaluation

```bash
# Start RAG API first (from backend folder)
uvicorn main:app --host 0.0.0.0 --port 8000

# Then run evaluation
python run_evaluation.py
```

Hoặc với Python:

```python
from evaluate_rag import RAGEvaluator, print_report, save_report

evaluator = RAGEvaluator(
    api_url="http://localhost:8000",
    top_k=5
)

samples = evaluator.load_dataset("../../rag_evaluation_dataset.csv")
report = evaluator.evaluate(samples, verbose=True)

print_report(report)
save_report(report, "./evaluation_results")
```

## 📊 Metrics

### Retrieval Metrics

| Metric | Mô tả |
|--------|-------|
| **Precision@K** | Số documents relevant / K documents retrieved |
| **Recall@K** | Số documents relevant retrieved / Tổng documents relevant |
| **Hit Rate@K** | % câu hỏi có ít nhất 1 relevant document trong top-K |
| **MRR** | Mean Reciprocal Rank - Trung bình 1/rank của relevant document đầu tiên |

### Generation Metrics

| Metric | Mô tả |
|--------|-------|
| **Semantic Similarity** | Similarity score giữa generated answer và ground truth (dùng sentence-transformers) |
| **Response Time** | Thời gian phản hồi trung bình |

## 🔧 Usage

### Command Line

```bash
# Quick evaluation với limited samples
python run_evaluation.py --limit 10

# Full evaluation
python run_evaluation.py

# Custom settings
python evaluate_rag.py \
    --api-url http://localhost:8000 \
    --dataset ../../rag_evaluation_dataset.csv \
    --top-k 5
```

### Python API

#### Retrieval Evaluation

```python
from evaluate_retrieval import RetrievalEvaluator

evaluator = RetrievalEvaluator(top_k=5)
evaluator.load_pipeline()

# Load samples
samples = evaluator.load_dataset("path/to/dataset.csv")

# Evaluate với limit
report = evaluator.evaluate(samples[:10])  # Test với 10 samples

# Full evaluation
report = evaluator.evaluate(samples)

# Access metrics
print(f"Hit Rate: {report.hit_rate_at_k:.2%}")
print(f"MRR: {report.mrr:.4f}")
print(f"Precision@5: {report.precision_at_k:.4f}")
```

#### Full RAG Evaluation

```python
from evaluate_rag import RAGEvaluator, print_report

evaluator = RAGEvaluator(
    api_url="http://localhost:8000",
    top_k=5
)

samples = evaluator.load_dataset("path/to/dataset.csv")
report = evaluator.evaluate(samples, verbose=True)

# Access detailed metrics
print(f"Hit Rate: {report.hit_rate:.2%}")
print(f"MRR: {report.mrr:.4f}")
print(f"Avg Answer Similarity: {report.avg_answer_similarity:.4f}")
print(f"Avg Response Time: {report.avg_response_time:.2f}s")

# Metrics by question type
for qtype, metrics in report.metrics_by_type.items():
    print(f"\n{qtype}:")
    print(f"  Hit Rate: {metrics['hit_rate']:.2%}")
    print(f"  Similarity: {metrics['avg_similarity']:.4f}")

# Metrics by difficulty
for diff, metrics in report.metrics_by_difficulty.items():
    print(f"\n{diff}:")
    print(f"  Hit Rate: {metrics['hit_rate']:.2%}")
```

## 📝 Evaluation Dataset Format

### Required columns

```csv
question,answer,document_source
"Điều kiện tốt nghiệp?","Hoàn thành tín chỉ...","QCDT_2025"
```

### Full format with metadata

```csv
question,answer,document_source,question_type,difficulty,relevant_context
"Điều kiện tốt nghiệp?","Hoàn thành...","QCDT_2025","factual","easy","Điều 15..."
```

### Question Types

- `factual`: Câu hỏi tìm kiếm thông tin trực tiếp
- `inference`: Câu hỏi cần suy luận
- `comparison`: So sánh giữa các điều khoản
- `procedural`: Hỏi về quy trình

### Difficulty Levels

- `easy`: Thông tin dễ tìm, rõ ràng
- `medium`: Cần tổng hợp từ nhiều phần
- `hard`: Thông tin ẩn, cần suy luận sâu

## 📈 Output Reports

### Console Output

```
================================================================================
📊 RETRIEVAL EVALUATION REPORT
================================================================================

📈 Overall Metrics:
   Total samples: 50
   Top-K: 5
   
   Hit Rate@5: 84.00%
   MRR: 0.6820
   Precision@5: 0.1680
   Recall@5: 0.8400

📊 By Question Type:
   factual: Hit Rate 92.0%, MRR 0.78
   inference: Hit Rate 75.0%, MRR 0.58
   ...
```

### Saved Reports

Reports được lưu vào `evaluation_results/`:
- `report_YYYYMMDD_HHMMSS.json`: Full JSON report
- `summary_YYYYMMDD_HHMMSS.txt`: Human-readable summary

## 🛠️ Advanced Configuration

### Custom Similarity Model

```python
from evaluate_rag import TextSimilarity

# Use custom model
similarity = TextSimilarity(use_sentence_transformers=True)
similarity.model = SentenceTransformer("your-custom-model")
```

### Custom API Endpoint

```python
evaluator = RAGEvaluator(
    api_url="http://your-api:8000",
    top_k=10
)
```

## 🐛 Troubleshooting

### Lỗi: Vector store not found
```bash
cd ../embedding
python main.py --mode batch --dir ../chunks_by_articles
```

### Lỗi: sentence-transformers not installed
```bash
pip install sentence-transformers
```

### Lỗi: API connection failed
```bash
# Ensure API is running
uvicorn main:app --host 0.0.0.0 --port 8000
```

## 📚 Best Practices

1. **Bắt đầu với sample nhỏ**: Test với `--limit 10` trước
2. **Cân bằng dataset**: Đảm bảo đủ samples cho mỗi question type và difficulty
3. **Review failed cases**: Xem các câu hỏi có hit=False để improve system
4. **Track metrics over time**: So sánh reports khi thay đổi system
5. **Diversify questions**: Thêm nhiều loại câu hỏi khác nhau
