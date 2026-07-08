# RAG Evaluation

Folder này chứa bộ dữ liệu và script chính để đánh giá pipeline RAG ở cả hai phần:

- Retrieval: so sánh các chunk truy hồi với `evidence_chunk_ids`, tính `hit@K`, `precision@K`, `recall@K`, `mrr@K`, `ndcg@K` với `K = 3, 5, 7`.
- End-to-end answer quality: chạy lại pipeline `/chat/v3`, sinh câu trả lời, rồi dùng LLM judge để đánh giá relevance, faithfulness/groundedness, completeness và correctness so với `gold_answer`.

## Dataset

Các dataset nằm trong `evaluation/data/*.json`. Mỗi file là một bộ câu hỏi theo một miền tài liệu, có cùng cấu trúc:

- `dataset_name`: tên dataset.
- `source_file`: file chunk nguồn tương ứng.
- `total_questions`: số lượng câu hỏi.
- `distribution`: phân phối câu hỏi `simple` và `multi_hop`.
- `items`: danh sách câu hỏi, mỗi item thường có `id`, `question_type`, `question`, `gold_answer`, `evidence_chunk_ids`, `ground_truth_context`, `is_answerable`, `reasoning_required`, `difficulty`.

Tổng hiện tại: 16 dataset, 570 câu hỏi, gồm 421 câu `simple` và 149 câu `multi_hop`.

| Dataset | Nội dung chính | Số câu | Simple | Multi-hop |
|---|---|---:|---:|---:|
| `06_Quy_dinh_ngoai_ngu_chunks.json` | Quy định ngoại ngữ, miễn học phần ngoại ngữ, chuẩn ngoại ngữ | 30 | 22 | 8 |
| `Khung-DGRL-2020-2021_rag_eval_dataset.json` | Khung đánh giá kết quả rèn luyện sinh viên năm học 2020-2021 | 30 | 22 | 8 |
| `blending_rag_dataset.json` | Quy định tổ chức dạy-học trực tuyến và B-Learning | 30 | 22 | 8 |
| `hbkkht_rag_dataset.json` | Quy định xét cấp học bổng khuyến khích học tập | 30 | 22 | 8 |
| `kehoach_rag_dataset.json` | Các kế hoạch/thông báo học vụ, mốc thời gian và hồ sơ | 50 | 38 | 12 |
| `kscs_rag_dataset.json` | Hướng dẫn học chương trình kỹ sư chuyên sâu đặc thù 180 tín chỉ | 30 | 22 | 8 |
| `olympic_rag_dataset.json` | Quy định tổ chức đội tuyển thi Olympic và đổi mới sáng tạo | 30 | 22 | 8 |
| `qpan_rag_dataset.json` | Quy định/đánh giá giáo dục quốc phòng-an ninh | 30 | 22 | 8 |
| `rag_evaluation_dataset.json` | Bài viết, tin tức, thông báo tuyển dụng/sự kiện tổng hợp | 100 | 75 | 25 |
| `rag_evaluation_dataset_ELITECH.json` | Quy định chương trình ELITECH khóa K62-K64 | 30 | 22 | 8 |
| `rag_evaluation_dataset_ITE6_fix_chunks.json` | Chương trình đào tạo CNTT Việt-Nhật IT-E6 | 30 | 22 | 8 |
| `rag_evaluation_dataset_ITE7_fix_chunks.json` | Chương trình đào tạo CNTT Global ICT IT-E7 | 30 | 22 | 8 |
| `rag_evaluation_dataset_k63_k64.json` | Chuẩn tiếng Anh cho sinh viên khóa K63-K64 | 30 | 22 | 8 |
| `renluyen_rag_dataset.json` | Quy định đánh giá điểm rèn luyện sinh viên | 30 | 22 | 8 |
| `svnn_rag_dataset.json` | Quy định quản lý sinh viên nước ngoài | 30 | 22 | 8 |
| `thitructuyen_rag_dataset.json` | Quy định tổ chức thi trực tuyến | 30 | 22 | 8 |

## Cách Chạy Evaluate

Chạy từ thư mục `src/RAG_v2` để import module đúng:

```bash
python -m evaluation.evaluate
```

Mặc định lệnh trên chạy toàn bộ `evaluation/data` với production-like config, tắt Redis/LLM cache để câu trả lời luôn được sinh mới. Kết quả được ghi theo từng dataset, mỗi dataset có:

- `query_results.csv`: kết quả từng câu hỏi, gồm câu trả lời, chunk truy hồi, metric retrieval và nhãn judge.
- `summary.json`: số liệu tổng hợp dạng JSON.
- `report.md`: báo cáo Markdown cho dataset đó.

Chạy một dataset:

```bash
python -m evaluation.evaluate --dataset evaluation/data/hbkkht_rag_dataset.json
```

Chạy thử nhanh vài câu đầu:

```bash
python -m evaluation.evaluate --dataset evaluation/data/hbkkht_rag_dataset.json --sample-n 3
```

Nếu provider/judge bị giới hạn RPM, thêm sleep giữa các câu:

```bash
python -m evaluation.evaluate --inter-question-sleep-s 15
```

## Config Evaluate

Các config benchmark đều truyền trực tiếp qua `evaluate.py`.

### Fusion mode

Mặc định dùng RRF:

```bash
python -m evaluation.evaluate --fusion-mode rrf
```

Chạy Linear fusion:

```bash
python -m evaluation.evaluate --fusion-mode linear
```

Output folder được đặt tự động theo config:

- RRF mặc định: `evaluation/result_dual_RRF/`
- Linear: `evaluation/result_dual_linear/`

### Vector model

Mặc định `dual`, tức kết hợp BGE và E5 với trọng số `0.8 / 0.2`.

```bash
python -m evaluation.evaluate --vector-model dual
python -m evaluation.evaluate --vector-model bge
python -m evaluation.evaluate --vector-model e5
```

Output folder có dạng `evaluation/result_<vector_model>_<fusion>/`, ví dụ `result_dual_RRF`, `result_bge_RRF`, `result_e5_linear`.

### Retrieval mode

Mặc định là hybrid, dùng cả vector và keyword:

```bash
python -m evaluation.evaluate --retrieval-mode hybrid
```

Vector only:

```bash
python -m evaluation.evaluate --retrieval-mode vector_only
```

Keyword only:

```bash
python -m evaluation.evaluate --retrieval-mode keyword_only
```

Khi chạy `vector_only`, script set `vector_weight = 1.0`, `keyword_weight = 0.0`, `keyword_top_k = 0`, `keyword_pool_k = 0`. Khi chạy `keyword_only`, script set ngược lại cho keyword và tắt vector pool.

### No rerank

Tắt reranker:

```bash
python -m evaluation.evaluate --disable-rerank
```

Có thể kết hợp với các config khác:

```bash
python -m evaluation.evaluate --fusion-mode rrf --vector-model dual --disable-rerank
python -m evaluation.evaluate --fusion-mode linear --retrieval-mode vector_only --disable-rerank
```

Output folder sẽ có hậu tố `_no_rerank`, ví dụ `evaluation/result_dual_RRF_no_rerank/`.

### Vector/keyword weight

Default trong settings là `vector_weight = 0.8`, `keyword_weight = 0.2`. Có thể override khi chạy hybrid:

```bash
python -m evaluation.evaluate --fusion-mode rrf --vector-weight 0.8 --keyword-weight 0.2
python -m evaluation.evaluate --fusion-mode rrf --vector-weight 0.6 --keyword-weight 0.4
```

Các tham số này cũng có tác dụng với `linear`, vì cùng được ghi vào settings trước khi build pipeline:

```bash
python -m evaluation.evaluate --fusion-mode linear --vector-weight 0.8 --keyword-weight 0.2
```

Lưu ý: nếu dùng `--retrieval-mode vector_only` hoặc `--retrieval-mode keyword_only`, mode đó sẽ override lại weight tương ứng thành `1.0 / 0.0` hoặc `0.0 / 1.0`.

### Top K

Mặc định `top_k = 7`, khớp production config:

```bash
python -m evaluation.evaluate --top-k 7
python -m evaluation.evaluate --top-k 5
```

Metric retrieval vẫn được aggregate ở các cutoff cố định `K = 3, 5, 7`; vì vậy nên giữ `top_k >= 7` nếu muốn so sánh đầy đủ các metric mặc định.

### Provider, model và judge

Override LLM sinh câu trả lời:

```bash
python -m evaluation.evaluate --provider gemini --model gemini-3.1-flash-lite
python -m evaluation.evaluate --provider deepseek --model deepseek-v4-flash
```

Override LLM judge:

```bash
python -m evaluation.evaluate --judge-provider gemini --judge-model gemini-3.1-pro
```

Nếu không truyền `--judge-provider` hoặc `--judge-model`, judge dùng cùng chat model/provider với pipeline.

## Ví Dụ Benchmark Thường Dùng

Chạy RRF dual hybrid có rerank:

```bash
python -m evaluation.evaluate --fusion-mode rrf --vector-model dual --retrieval-mode hybrid
```

Chạy RRF dual nhưng không rerank:

```bash
python -m evaluation.evaluate --fusion-mode rrf --vector-model dual --retrieval-mode hybrid --disable-rerank
```

Chạy vector only:

```bash
python -m evaluation.evaluate --fusion-mode rrf --vector-model dual --retrieval-mode vector_only
```

Chạy keyword only:

```bash
python -m evaluation.evaluate --fusion-mode rrf --vector-model dual --retrieval-mode keyword_only
```

Chạy Linear để so sánh với RRF:

```bash
python -m evaluation.evaluate --fusion-mode linear --vector-model dual --retrieval-mode hybrid
```

Chạy RRF với trọng số vector cao hơn:

```bash
python -m evaluation.evaluate --fusion-mode rrf --vector-weight 0.9 --keyword-weight 0.1
```
