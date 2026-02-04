# Batch Evaluation - Đánh giá từng đợt để tránh giới hạn API

## Vấn đề
Gemini API có giới hạn số lượng request mỗi ngày. Khi đánh giá dataset lớn (ví dụ 150 câu hỏi), cần chia nhỏ thành nhiều batch để đánh giá dần theo từng ngày.

## Giải pháp
Script `evaluate_answer_quality.py` hỗ trợ:
- Đánh giá theo batch (từ câu X đến câu Y)
- Append kết quả vào file duy nhất
- Tracking question ID để không bị trùng lặp

## Cách sử dụng

### Ví dụ 1: Đánh giá 20 câu đầu tiên (ngày 1)
```bash
python evaluate_answer_quality.py --start 1 --end 20
```
Kết quả:
- File detailed: `answer_detailed_hybrid_rerank.csv` (20 dòng, câu 1-20)
- File summary: `answer_summary_hybrid_rerank_batch_1-20_20260129_140000.csv`

### Ví dụ 2: Đánh giá 20 câu tiếp theo (ngày 2)
```bash
python evaluate_answer_quality.py --start 21 --end 40 --append
```
Kết quả:
- File detailed: `answer_detailed_hybrid_rerank.csv` (40 dòng, câu 1-40) ✅ **APPEND**
- File summary: `answer_summary_hybrid_rerank_batch_21-40_20260130_140000.csv`

### Ví dụ 3: Đánh giá 20 câu tiếp nữa (ngày 3)
```bash
python evaluate_answer_quality.py --start 41 --end 60 --append
```
Kết quả:
- File detailed: `answer_detailed_hybrid_rerank.csv` (60 dòng, câu 1-60) ✅ **APPEND**
- File summary: `answer_summary_hybrid_rerank_batch_41-60_20260131_140000.csv`

### Ví dụ 4: Test với 5 câu đầu
```bash
python evaluate_answer_quality.py --start 1 --end 5
```

## Các tham số quan trọng

| Tham số | Mô tả | Ví dụ |
|---------|-------|-------|
| `--start` | Câu hỏi bắt đầu (1-based) | `--start 1`, `--start 21` |
| `--end` | Câu hỏi kết thúc (1-based) | `--end 20`, `--end 40` |
| `--append` | Append vào file existing | `--append` |
| `--limit` | Giới hạn số câu (alternative) | `--limit 10` |

## Workflow đầy đủ cho 150 câu

```bash
# Ngày 1: Câu 1-20
python evaluate_answer_quality.py --start 1 --end 20

# Ngày 2: Câu 21-40
python evaluate_answer_quality.py --start 21 --end 40 --append

# Ngày 3: Câu 41-60
python evaluate_answer_quality.py --start 41 --end 60 --append

# Ngày 4: Câu 61-80
python evaluate_answer_quality.py --start 61 --end 80 --append

# Ngày 5: Câu 81-100
python evaluate_answer_quality.py --start 81 --end 100 --append

# Ngày 6: Câu 101-120
python evaluate_answer_quality.py --start 101 --end 120 --append

# Ngày 7: Câu 121-140
python evaluate_answer_quality.py --start 121 --end 140 --append

# Ngày 8: Câu 141-150
python evaluate_answer_quality.py --start 141 --end 150 --append
```

## Kết quả cuối cùng

Sau khi chạy xong tất cả batch:

### File chính (tổng hợp)
- `answer_detailed_hybrid_rerank.csv`: Chứa TẤT CẢ 150 câu đã đánh giá
  - Cột `question_id`: Tracking số thứ tự câu hỏi
  - Có thể load vào Excel/Python để phân tích tổng thể

### File summary từng batch
- `answer_summary_hybrid_rerank_batch_1-20_*.csv`
- `answer_summary_hybrid_rerank_batch_21-40_*.csv`
- ... (các batch khác)

## Lưu ý quan trọng

### ✅ Nên làm
1. **Luôn dùng `--append`** từ batch thứ 2 trở đi
2. **Giữ nguyên config** (hybrid/rerank) cho tất cả batch
3. **Backup file detailed** trước mỗi batch mới

### ❌ Không nên
1. ❌ Không thay đổi `--no-hybrid` / `--no-rerank` giữa các batch
2. ❌ Không chạy trùng range câu hỏi (sẽ bị duplicate)
3. ❌ Không quên `--append` flag từ batch 2 trở đi

## Script mẫu (Windows)

Tạo file `run_batch_evaluation.bat`:
```batch
@echo off
echo Day 1: Questions 1-20
python evaluate_answer_quality.py --start 1 --end 20
echo.
echo Waiting 24 hours...
timeout /t 86400
echo.

echo Day 2: Questions 21-40
python evaluate_answer_quality.py --start 21 --end 40 --append
echo.
echo Waiting 24 hours...
timeout /t 86400
echo.

echo Day 3: Questions 41-60
python evaluate_answer_quality.py --start 41 --end 60 --append
echo Done!
```

## Phân tích kết quả tổng hợp

Sau khi có file `answer_detailed_hybrid_rerank.csv` đầy đủ:

```python
import pandas as pd

# Load kết quả
df = pd.read_csv('answer_quality_results/answer_detailed_hybrid_rerank.csv')

print(f"Total evaluated: {len(df)} questions")
print(f"Question ID range: {df['question_id'].min()} - {df['question_id'].max()}")

# Aggregate metrics
print(f"\nOverall metrics:")
print(f"  Hit Rate: {df['retrieval_hit'].mean():.2%}")
print(f"  Avg Semantic: {df['semantic_similarity'].mean():.4f}")
print(f"  Avg Token F1: {df['token_f1'].mean():.4f}")
print(f"  Avg BLEU: {df['bleu_avg'].mean():.4f}")

# By question type
print(f"\nBy question type:")
print(df.groupby('question_type')[['semantic_similarity', 'token_f1', 'bleu_avg']].mean())
```

## Troubleshooting

### Vấn đề: File bị ghi đè thay vì append
**Nguyên nhân**: Quên `--append` flag  
**Giải pháp**: Luôn dùng `--append` từ batch 2

### Vấn đề: Question ID bị trùng
**Nguyên nhân**: Chạy trùng range  
**Giải pháp**: Check file detailed trước khi chạy batch mới

### Vấn đề: API rate limit exceeded
**Nguyên nhân**: Chạy quá nhiều request trong ngày  
**Giải pháp**: Giảm batch size hoặc đợi 24h

## Contact
Nếu có vấn đề, check log hoặc liên hệ team.
