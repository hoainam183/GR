# Đánh giá hệ thống RAG: Truy hồi và Sinh câu trả lời (End-to-End)

> **Phạm vi.** Tài liệu trình bày phương pháp và kết quả đánh giá thực nghiệm module
> `evaluation/`. Thực nghiệm so sánh hai chiến lược hợp nhất kết quả (fusion) — **Reciprocal
> Rank Fusion (RRF)** và **Linear (weighted-sum)** — trên đồng thời hai khía cạnh: chất
> lượng **truy hồi** (retrieval) và chất lượng **sinh câu trả lời đầu-cuối** (end-to-end).
> Đánh giá thực hiện ở **mức tổng thể** trên toàn bộ tập thực nghiệm: **16 bộ dữ liệu**,
> tổng **570 truy vấn** mỗi chế độ (khớp 1–1 theo truy vấn). Dữ liệu lấy từ
> `evaluation/results/` (Linear) và `evaluation/result_RRF/` (RRF).

---

## 1. Mục tiêu và thiết kế thực nghiệm

### 1.1. Mục tiêu

1. So sánh định lượng RRF và Linear trên các chỉ số truy hồi chuẩn (hit/precision/recall/MRR/nDCG @K).
2. Đánh giá tác động của fusion lên chất lượng câu trả lời cuối (groundedness, hallucination, completeness, độ đúng so với đáp án vàng).
3. Đưa ra khuyến nghị cấu hình fusion cho hệ thống vận hành thực tế.

### 1.2. Quy trình đánh giá

Harness `evaluate.py` chạy lại **chính xác pipeline vận hành** (`/chat/v3` →
`RAGPipeline.query_v3`) trên từng truy vấn, giữ nguyên cấu hình production: bật agent, bật
HyDE, bật ValidityFilter, `reranker_score_threshold = 0.0`, `reranker_min_top_k = 3`,
`top_k = 7`. Khác biệt duy nhất so với hệ thống live là **tắt cache LLM/Redis** để mỗi
truy vấn luôn sinh câu trả lời tươi. Nhờ đó số liệu phản ánh trung thực hành vi mà người
dùng cuối nhận được.

Với mỗi truy vấn, harness ghi lại: tập chunk truy hồi (so với `evidence_chunk_ids` để tính
metric truy hồi), câu trả lời sinh ra, và các nhãn đánh giá e2e do LLM-judge
(`llm.self_eval.SelfEvaluator`) và judge so-khớp đáp án vàng (`gold_answer`) gán.

### 1.3. Hai chiến lược fusion được so sánh

Cả hai hợp nhất một pool **vector** (độ tương đồng cosine) và một pool **keyword** (BM25)
với cùng trọng số `vector_weight = 0.8`, `keyword_weight = 0.2`
(`retrieval/multi_collection_search.py`). Khác biệt nằm ở **cơ chế kết hợp điểm**:

| | **Linear** (`_score_fusion`) | **RRF** (`_score_fusion_rrf`, `fusion_rrf_k = 10`) |
|---|---|---|
| Nguyên lý | Chuẩn hoá max-normalization mỗi pool về `[0,1]` rồi cộng có trọng số: `0.8·norm_v + 0.2·norm_k` | Hợp nhất theo **thứ hạng**: `0.8·1/(k+rank_v) + 0.2·1/(k+rank_k)` |
| Phụ thuộc | Độ lớn điểm tuyệt đối | Chỉ thứ hạng (bỏ qua độ lớn) |
| Điểm yếu | Nhạy khi thang điểm cosine vs BM25 lệch nhau | Nén khoảng cách giữa các hạng liền kề |

Cấu hình mặc định của hệ thống là `fusion_mode = "rrf"` (`config/settings.py:154`).

---

## 2. Định nghĩa các chỉ số

### 2.1. Chỉ số truy hồi (đối chiếu `source-id` truy hồi với `evidence_chunk_ids`, K ∈ {3, 5, 7})

| Chỉ số | Ý nghĩa | Vai trò |
|---|---|---|
| **hit@K** | Có ít nhất một chunk đúng trong top-K | Đo khả năng "tìm thấy" |
| **precision@K** | Tỷ lệ chunk đúng trong K vị trí | Đo độ "sạch" của ngữ cảnh |
| **recall@K** | Tỷ lệ bằng chứng được phủ trong top-K | **Chỉ số bao phủ then chốt cho RAG** |
| **MRR@K** | Nghịch đảo thứ hạng chunk đúng đầu tiên | Đo "đúng có nằm trên cao không" |
| **nDCG@K** | Vừa đúng vừa đúng thứ tự, có chiết khấu log | **Chỉ số xếp hạng tổng hợp tốt nhất** |

### 2.2. Chỉ số sinh câu trả lời (LLM-judge)

| Chỉ số | Ý nghĩa |
|---|---|
| **Faithfulness / Groundedness** | Câu trả lời có bám sát ngữ cảnh truy hồi không |
| **Hallucination rate** | Tỷ lệ câu trả lời bịa đặt — phần bù của faithfulness; **càng thấp càng tốt** |
| **Relevance** | Câu trả lời có đúng trọng tâm câu hỏi không |
| **Completeness** | Có trả lời đầy đủ các ý cần thiết không |
| **Correctness vs gold** | So với `gold_answer`: `correct` / `partial` / `incorrect`; **chỉ số "đúng/sai" sát người dùng nhất** |

---

## 3. Kết quả tổng thể (16 bộ dữ liệu, 570 truy vấn)

Số liệu tổng hợp theo hai cách: **macro** (trung bình đều trên 16 bộ dữ liệu) và **micro**
(trung bình có trọng số theo số truy vấn). Giá trị **in đậm** là chế độ tốt hơn.

**Bảng 3.1 — So sánh tổng thể Linear vs RRF**

| Nhóm | Chỉ số | Linear (macro) | RRF (macro) | Linear (micro) | RRF (micro) |
|---|---|---|---|---|---|
| Truy hồi | nDCG@3 | 0.671 | **0.706** | 0.623 | **0.670** |
| | nDCG@5 | 0.685 | **0.718** | 0.638 | **0.683** |
| | nDCG@7 | 0.693 | **0.724** | 0.645 | **0.688** |
| | Recall@5 | 0.730 | **0.759** | 0.684 | **0.727** |
| | MRR@5 | 0.684 | **0.721** | 0.635 | **0.682** |
| | hit@5 | 0.758 | **0.789** | 0.709 | **0.753** |
| | precision@5 | 0.166 | **0.173** | — | — |
| Sinh câu trả lời | Faithfulness | **0.937** | 0.934 | **0.944** | 0.942 |
| | Hallucination | **0.037** | 0.047 | **0.033** | 0.040 |
| | Completeness | 0.952 | **0.960** | 0.956 | **0.965** |
| | Relevance | 0.988 | **0.990** | 0.990 | **0.991** |
| | Correctness (đúng) | 0.770 | **0.804** | 0.730 | **0.777** |
| Hiệu năng | Độ trễ TB (ms) | 17 868 | 14 983 | 19 507 | 15 714 |

**Thống kê thắng/thua trên 16 bộ dữ liệu** (cho thấy ưu thế của RRF mang tính hệ thống chứ
không do một vài bộ cá biệt):

- **nDCG@5:** RRF thắng **8**, Linear thắng **5**, hoà **3**.
- **Correctness vs gold:** RRF cao hơn ở **9** bộ, Linear cao hơn ở **5**, hoà **2**.
- **Hallucination:** RRF thấp hơn ở **6** bộ, Linear thấp hơn ở **5**, bằng **5**.

---

## 4. Phân tích

### 4.1. Truy hồi: RRF vượt trội và ổn định

RRF cải thiện đồng đều mọi chỉ số xếp hạng: **+3,4 điểm nDCG@5 (macro)** và **+4,5 điểm
(micro)**, với xu hướng tương tự ở Recall@5, MRR@5, hit@5 và ở cả ba mức cắt K = 3, 5, 7.
Nguyên nhân nằm ở bản chất thuật toán: Linear cộng theo **độ lớn điểm**, nên khi thang điểm
cosine (vector) và BM25 (keyword) lệch nhau, một pool có thể lấn át pool kia và đẩy bằng
chứng đúng xuống thấp. RRF chỉ dựa trên **thứ hạng**, miễn nhiễm với chênh lệch thang điểm,
do đó cho xếp hạng ổn định và chính xác hơn trên đa số domain.

### 4.2. Sinh câu trả lời: độ đúng nghiêng về RRF, an toàn nghiêng nhẹ về Linear

- **Correctness so với đáp án vàng — RRF tốt hơn rõ rệt** (macro 80,4% vs 77,0%; micro
  77,7% vs 73,0%; thắng ở 9/16 bộ). Truy hồi tốt hơn dẫn thẳng tới câu trả lời đúng nhiều
  hơn. Đây là chỉ số sát người dùng nhất nên ưu thế của RRF có giá trị thực tiễn cao.
- **Faithfulness — gần như hoà** (93,4% vs 93,7% macro): khác biệt nằm trong khoảng dao
  động, fusion không phải yếu tố quyết định độ trung thực.
- **Hallucination — Linear an toàn hơn một chút** (3,7% vs 4,7% macro). RRF đôi khi kéo lên
  thêm chunk có thứ hạng cao nhưng nội dung lệch trên các bộ chunk nhiễu, khiến mô hình dễ
  suy diễn; bù lại trên các bộ "sạch" RRF thường đưa hallucination về 0%.
- **Completeness và Relevance — RRF nhỉnh nhẹ** (96,0% vs 95,2%; 99,0% vs 98,8%).

### 4.3. Về độ trễ

RRF có độ trễ trung bình thấp hơn (≈15 s vs ≈18–20 s), nhưng **không nên xem đây là tiêu
chí so sánh fusion**: hai chế độ dùng chung pipeline, chênh lệch chủ yếu đến từ nhiễu đo
trên máy phát triển (reranker chạy CPU, không có GPU) và vài truy vấn ngoại lai chậm. Trị
tuyệt đối 15–20 s là do reranker CPU và **nằm ngoài phạm vi tối ưu** — hệ thống vận hành
chạy trên MacBook M4 Pro (MPS) với reranker đặt trên GPU từ xa.

### 4.4. Nhận định chung về chất lượng RAG

- **Nút thắt nằm ở truy hồi/xếp hạng, không phải ở khâu sinh.** Faithfulness ~94% và
  relevance ~99% cho thấy khi đã có ngữ cảnh đúng thì mô hình trả lời tốt; trong khi
  nDCG@5/Recall@5 tổng thể chỉ ~0,68–0,76. Hướng cải thiện tiếp theo nên ưu tiên
  **chunking + truy hồi/định tuyến**, không phải tinh chỉnh prompt sinh.
- **Chất lượng chunk quyết định trần điểm truy hồi:** các nhóm domain đã được làm sạch
  chunk đạt nDCG@5 cao hơn hẳn, kéo điểm trung bình tổng thể lên.

---

## 5. Kết luận và khuyến nghị

**Bảng 5.1 — Tổng kết theo tiêu chí**

| Tiêu chí | Chế độ thắng |
|---|---|
| Truy hồi (nDCG / Recall / MRR / hit @3,5,7) | **RRF** — rõ rệt, ổn định (+3–5 điểm tổng hợp) |
| Độ đúng so với đáp án vàng | **RRF** (+3–5 điểm) |
| Completeness / Relevance | **RRF** (nhỉnh nhẹ) |
| Faithfulness / chống hallucination | **Linear** (an toàn hơn ~1 điểm) |
| Độ trễ | Không kết luận (nhiễu đo, ngoài phạm vi) |

**Khuyến nghị: giữ `fusion_mode = "rrf"` làm mặc định vận hành** (đúng như cấu hình hiện
tại). RRF cải thiện rõ rệt chất lượng truy hồi và độ đúng câu trả lời — những yếu tố sát
người dùng nhất — với cái giá là tăng nhẹ hallucination ở một số ít domain có chunk nhiễu.

**Hướng phát triển tiếp theo (theo thứ tự ưu tiên):**

1. **Giảm hallucination của RRF** bằng cách siết `ValidityFilter` / ngưỡng reranker hoặc
   cải thiện chất lượng chunk, thay vì đổi fusion.
2. **Nâng recall tổng thể** (cải thiện chunking và bộ phân loại định tuyến) — đây mới là
   trần điểm thực sự của hệ thống.
3. **Khảo sát siêu tham số `fusion_rrf_k`** (hiện 10) và cặp trọng số `vector/keyword`
   (0,8/0,2) để tối ưu thêm cho từng nhóm domain.

---

## Phụ lục — Các script trong module

| File | Vai trò |
|---|---|
| `evaluate.py` | Harness chính: chạy pipeline production, tính metric truy hồi + e2e, ghi `summary.json`, `report.md`, `query_results.csv`. |
| `evaluate_fusion.py` | So sánh nhiều cấu hình fusion (Linear vs RRF, pool 15/30) trong một lần chạy. |
| `evaluate_domain_routing.py` | Đánh giá riêng khâu định tuyến domain. |
| `retry_failed_eval.py` | Chạy lại các truy vấn lỗi; đặt `fusion_mode` động cho thư mục `results/` (linear) và `result_RRF/` (rrf). |
| `compare_results.py`, `compare_results_per_dataset.py` | In bảng so sánh nDCG@5 Linear vs RRF. |
| `generate_hallucination_csvs.py`, `aggregate_hallucinations.py` | Gom các trường hợp bị đánh dấu hallucinated. |

**Cách chạy lại** (trong `.venv` tại `RAG_v2`):

```bash
python -m evaluation.evaluate                                          # toàn bộ evaluation/data
python -m evaluation.evaluate --dataset evaluation/data/<tên>.json     # một bộ
python -m evaluation.evaluate --dataset ... --sample-n 3               # chạy thử nhanh
```
