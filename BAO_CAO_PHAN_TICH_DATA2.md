# Báo Cáo Phân Tích Dữ Liệu `data2.csv` — Email Tư Vấn Học Tập

> **Nguồn dữ liệu:** Crawl từ hệ thống email Tổ Tư vấn Học tập (TVHT), Viện CNTT&TT — Đại học Bách khoa Hà Nội  
> **Ngày phân tích:** 01/03/2026  
> **Mục đích:** Đánh giá chất lượng dữ liệu phục vụ xây dựng hệ thống RAG (Retrieval-Augmented Generation)

---

## 1. Tổng Quan Dữ Liệu

| Metric | Giá trị |
|---|---|
| Tổng số cặp Q&A | **4,011** |
| Số thread (cuộc hội thoại) | **2,644** |
| Số sinh viên duy nhất | **1,461** |
| Số email giáo viên/tư vấn viên | **37** |
| Khoảng thời gian | 12/2019 – 01/2025 |

### Phân bố theo năm

| Năm | Số dòng | Tỉ lệ |
|---|---|---|
| 2019 | 1 | 0.0% |
| 2020 | 615 | 15.3% |
| 2021 | 1,131 | **28.2%** |
| 2022 | 729 | 18.2% |
| 2023 | 656 | 16.4% |
| 2024 | 591 | 14.7% |
| 2025 | 32 | 0.8% |

> Dữ liệu tập trung nhiều nhất vào năm **2021** (đỉnh Covid-19, sinh viên hỏi online nhiều hơn).

---

## 2. Phân Tích Thread (Cuộc Hội Thoại)

| Metric | Giá trị |
|---|---|
| Trung bình lượt trao đổi/thread | **1.52** |
| Median | **1** |
| Min | 1 |
| Max | 256 (outlier) |

### Phân bố số lượt trao đổi

| Số lượt | Số threads | Tỉ lệ |
|---|---|---|
| 1 lượt (single-turn) | 1,903 | **72.0%** |
| 2 lượt | 538 | 20.3% |
| 3 lượt | 128 | 4.8% |
| 4 lượt | 36 | 1.4% |
| 5+ lượt | 39 | 1.5% |

**Nhận xét:**
- **72% thread chỉ có 1 lượt hỏi-đáp** → phần lớn dùng được trực tiếp cho single-turn RAG.
- **28% thread là multi-turn** (741 threads) → cần xử lý đặc biệt khi tạo training data.
- Có **1 thread outlier** với 256 lượt (có thể là lỗi crawl hoặc thread tổng hợp).

---

## 3. Phân Tích Token / Độ Dài Văn Bản

### 3.1 Câu hỏi (Questions)

| Metric | Words | Chars |
|---|---|---|
| Trung bình | 117.1 | 525 |
| Median | 99 | 445 |
| Min | 0 | — |
| Max | 1,593 | — |
| Stdev | — | 462 |
| P10 | — | 102 |
| P25 | — | 271 |
| P75 | — | 671 |
| P90 | — | 979 |
| P95 | — | 1,198 |

### 3.2 Câu trả lời (Answers)

| Metric | Words | Chars |
|---|---|---|
| Trung bình | 83.8 | 396 |
| Median | 58 | 272 |
| Min | 3 | — |
| Max | 1,152 | — |
| Stdev | — | 408 |
| P10 | — | 97 |
| P25 | — | 152 |
| P75 | — | 493 |
| P90 | — | 827 |
| P95 | — | 1,074 |

### 3.3 Q+A kết hợp

| Metric | Giá trị |
|---|---|
| Trung bình | **200.9 words** ≈ **301 tokens** (Vietnamese) |
| P90 | 351 words |
| P95 | 445 words |
| P99 | 767 words |
| Tổng tokens toàn dataset | **805,657 words** |

### 3.4 Token per Full Thread

| Metric | Giá trị |
|---|---|
| Trung bình | 305 words |
| Max | 30,498 words |
| P90 | 594 words |
| P95 | 806 words |

**Nhận xét:**
- Câu hỏi dài hơn câu trả lời trung bình (~117 vs ~84 words) do sinh viên thường kèm thông tin cá nhân, mô tả hoàn cảnh.
- Ước lượng **chunk size phù hợp: 500–800 tokens** để chứa được 90–95% cặp Q&A.

---

## 4. Phân Loại Chủ Đề (Keyword-Based)

> **Lưu ý:** Một câu hỏi có thể thuộc nhiều chủ đề (multi-label). 89.9% câu hỏi được phân loại vào ít nhất 1 chủ đề.

| Chủ đề | Số lượng | Tỉ lệ |
|---|---|---|
| Đăng ký học phần / Lịch học | 2,993 | **74.6%** |
| Chương trình đào tạo | 1,701 | 42.4% |
| Kỹ sư / Cử nhân | 1,482 | 36.9% |
| Đồ án / Project / ĐATN | 1,448 | 36.1% |
| Tín chỉ | 1,439 | 35.9% |
| Học phần tương đương / Thay thế | 1,292 | 32.2% |
| Giấy tờ / Thủ tục | 704 | 17.6% |
| Điểm số / GPA / CPA | 678 | 16.9% |
| Thực tập | 385 | 9.6% |
| Thạc sĩ / Sau đại học | 267 | 6.7% |
| Tiếng Anh / Ngoại ngữ | 264 | 6.6% |
| Học phí / Tài chính | 212 | 5.3% |
| Bảo lưu / Gia hạn | 136 | 3.4% |
| Lịch thi / Thi | 49 | 1.2% |
| Rèn luyện / Hoạt động | 37 | 0.9% |
| **Chưa phân loại** | **405** | **10.1%** |

### Phân bố số chủ đề per câu hỏi

| Số chủ đề | Số câu hỏi | Tỉ lệ |
|---|---|---|
| 0 (chưa phân loại) | 405 | 10.1% |
| 1 | 340 | 8.5% |
| 2 | 673 | 16.8% |
| 3 | 833 | **20.8%** |
| 4 | 744 | 18.5% |
| 5+ | 1,016 | 25.3% |

### Top 5 cặp chủ đề hay đi kèm

| Cặp chủ đề | Số lần |
|---|---|
| CTĐT + Đăng ký học phần | 1,449 |
| Kỹ sư/Cử nhân + Đăng ký học phần | 1,235 |
| Đồ án/ĐATN + Đăng ký học phần | 1,223 |
| HP tương đương + Đăng ký học phần | 1,206 |
| Tín chỉ + Đăng ký học phần | 1,195 |

**Nhận xét:**
- Chủ đề **đăng ký học phần** chiếm đa số (74.6%), phản ánh đây là nhu cầu tư vấn phổ biến nhất.
- Câu hỏi thường **đa chủ đề** (trung bình 3–4 topics) — sinh viên hỏi nhiều vấn đề trong cùng một email.
- **10.1% chưa phân loại** là các câu follow-up ngắn ("dạ vâng ạ", "em cảm ơn") hoặc câu hỏi đặc thù.

---

## 5. Chất Lượng Dữ Liệu

### 5.1 Vấn đề về dữ liệu

| Vấn đề | Số lượng | Tỉ lệ | Mức ảnh hưởng |
|---|---|---|---|
| Câu hỏi rỗng (empty) | 260 | 6.5% | 🔴 Cao |
| Câu hỏi quá ngắn (<5 words) | 267 | 6.7% | 🟡 Trung bình |
| Câu trả lời ngắn (<10 words) | 27 | 0.7% | 🟡 Trung bình |
| Câu hỏi trùng lặp (duplicate text) | ~881 | 22.0% | 🔴 Cao |
| Câu hỏi có nhiều đáp án (cùng thread) | 496 | 12.4% | 🟡 Trung bình |
| Câu trả lời là chuyển tiếp (forwarded) | 603 | 15.0% | 🔴 Cao |
| Câu trả lời từ email không phải TVHT | 610 | 15.2% | 🟡 Trung bình |
| Câu hỏi tham chiếu ảnh/file đính kèm | 553 | 13.8% | 🔴 Cao |
| Câu hỏi có vấn đề encoding | ~3,442* | — | 🟡 (cần kiểm tra) |

> (*) Con số encoding issues cao do bao gồm cả ký tự Unicode tiếng Việt hợp lệ — cần kiểm tra kỹ hơn các trường hợp thực sự bị lỗi.

### 5.2 Thông tin cá nhân (PII) trong câu hỏi

| Loại PII | Số lượng | Tỉ lệ |
|---|---|---|
| Đề cập tên cá nhân | 2,572 | 64.1% |
| Đề cập MSSV | 1,840 | 45.9% |
| Đề cập MSSV (pattern explicit) | 1,463 | 36.5% |

> ⚠️ **Cần anonymize/loại bỏ PII** trước khi dùng làm training data cho RAG.

### 5.3 Chất lượng câu trả lời

| Metric | Giá trị |
|---|---|
| Trả lời trực tiếp | 3,405 (84.9%) |
| Chuyển tiếp/nhờ người khác | 606 (15.1%) |
| Có chứa URL/link | 540 (13.5%) |
| Có tham chiếu quy định | 739 (18.4%) |
| Có bước hướng dẫn (list/steps) | 916 (22.8%) |
| Bắt đầu bằng "Chào em" | 3,083 (76.9%) |
| Có email signature | 1,967 (49.0%) |

### 5.4 Câu hỏi phụ thuộc ngữ cảnh

| Metric | Giá trị |
|---|---|
| Câu hỏi phụ thuộc context trước | 971 (24.2%) |
| Câu hỏi là follow-up ngắn (không phải câu hỏi thực sự) | 22 |
| Câu hỏi đa phần (multiple sub-questions) | 2,316 (57.7%) |
| Câu hỏi đề cập mã học phần cụ thể | 1,765 (44.0%) |
| Câu hỏi đề cập kỳ học cụ thể | 1,474 (36.7%) |

---

## 6. Phân Tích Thời Gian Phản Hồi

| Metric | Giá trị |
|---|---|
| Trung bình | 29.7 giờ |
| Median | 12.9 giờ |
| Min | <1 giờ |
| Max | 3,372.7 giờ (~140 ngày) |
| Phản hồi trong 24h | 2,511 (66.9%) |
| Phản hồi trong 48h | 3,110 (82.8%) |

> RAG system có thể giảm thời gian phản hồi xuống **gần real-time** cho các câu hỏi phổ biến.

---

## 7. Phân Bố Nguồn Trả Lời

| Email | Số lượng | Tỉ lệ |
|---|---|---|
| tuvanhoctap@soict.hust.edu.vn | 3,401 | **84.8%** |
| dungct@soict.hust.edu.vn | 128 | 3.2% |
| thuttv@soict.hust.edu.vn | 78 | 1.9% |
| binhht@soict.hust.edu.vn | 72 | 1.8% |
| Các email khác (33 người) | 332 | 8.3% |

> Phần lớn câu trả lời (84.8%) đến từ tài khoản TVHT chung — đảm bảo tính nhất quán.

---

## 8. Đánh Giá Metrics Cho Hệ Thống RAG

### 8.1 Số liệu tóm tắt

| RAG Metric | Giá trị | Đánh giá |
|---|---|---|
| Tổng cặp Q&A | 4,011 | Đủ để xây dựng hệ thống cơ bản |
| Cặp Q&A standalone sử dụng được | **3,186 (79.4%)** | Tốt |
| Unique questions | 3,130 | Đa dạng hợp lý |
| Tỉ lệ trùng lặp | 22.0% | Cần dedup |
| Context-dependent questions | 24.2% | Cần merge thread hoặc loại |
| Multi-turn threads | 28.0% | Cần xử lý riêng |
| Chưa phân loại | 10.1% | Chấp nhận được |

### 8.2 Khuyến nghị Chunk Size

| Percentile | Kích thước Q+A (words) | Tokens ước tính (Vietnamese ×1.5) |
|---|---|---|
| Trung bình | 201 | ~301 |
| P90 | 351 | ~527 |
| P95 | 445 | ~668 |
| P99 | 767 | ~1,151 |

> **Khuyến nghị chunk size: 512–1024 tokens** để bao phủ 95–99% cặp Q&A.

### 8.3 Các vấn đề cần xử lý trước khi dùng cho RAG

#### 🔴 Ưu tiên cao

1. **Loại bỏ thông tin cá nhân (PII):** 64% câu hỏi chứa tên, 46% chứa MSSV → cần anonymize.
2. **Loại bỏ câu hỏi rỗng:** 260 dòng không có nội dung câu hỏi.
3. **Xử lý duplicate:** 22% trùng lặp text → dedup hoặc merge answers.
4. **Lọc forwarded answers:** 15% câu trả lời chỉ là chuyển tiếp nội bộ, không chứa thông tin hữu ích cho sinh viên.
5. **Xử lý câu hỏi tham chiếu ảnh/đính kèm:** 13.8% câu hỏi dựa vào file đính kèm mà ta không có → cần flag hoặc loại.

#### 🟡 Ưu tiên trung bình

6. **Merge multi-turn threads:** 28% thread có nhiều lượt, cần ghép thành 1 context hoàn chỉnh.
7. **Loại bỏ email signature/greeting:** ~49% câu trả lời chứa signature, 77% chứa "Chào em" → cần clean.
8. **Xử lý câu hỏi có thời gian cụ thể:** 36.7% câu hỏi đề cập kỳ học cụ thể → cần generalize hoặc tag temporal.
9. **Tách câu hỏi đa phần:** 57.7% chứa nhiều sub-questions → cân nhắc tách thành từng cặp Q&A riêng.

#### 🟢 Cải thiện

10. **Phân loại chủ đề tốt hơn:** Keyword-based chỉ là baseline, nên dùng LLM/embedding-based classification.
11. **Quality scoring:** Gắn điểm chất lượng cho mỗi cặp Q&A dựa trên completeness, directness, specificity.
12. **Temporal tagging:** Tag các câu trả lời có thể bị outdated (quy định thay đổi qua các năm).

---

## 9. Ước Lượng Dữ Liệu Sạch Sau Xử Lý

| Bước xử lý | Loại bỏ (ước tính) | Còn lại |
|---|---|---|
| Dữ liệu gốc | — | 4,011 |
| Loại câu hỏi rỗng | -260 | 3,751 |
| Loại câu trả lời forwarded (không direct) | -603 | ~3,148 |
| Dedup (loại trùng lặp) | ~-400 | ~2,748 |
| Loại follow-up không có giá trị | ~-200 | ~2,548 |
| **Dữ liệu sạch ước tính** | | **~2,500–2,800 cặp Q&A** |

> Sau khi clean, còn khoảng **2,500–2,800 cặp Q&A chất lượng** — đủ tốt để làm evaluation set và fine-tune retriever cho domain tư vấn học tập.

---

## 10. Kết Luận

### Điểm mạnh
- ✅ Dữ liệu **thực tế** từ hệ thống email, phản ánh đúng nhu cầu sinh viên
- ✅ Phủ rộng **16+ chủ đề** liên quan đến tư vấn học tập
- ✅ Khoảng thời gian dài (**5 năm**), bao quát nhiều khóa sinh viên
- ✅ **84.9%** câu trả lời là trực tiếp, có giá trị thông tin cao
- ✅ Đủ lượng data (~2,500+ cặp sạch) cho RAG evaluation

### Điểm yếu / Thách thức
- ⚠️ Tỉ lệ PII cao → cần pipeline anonymization
- ⚠️ 22% duplicate → cần dedup cẩn thận
- ⚠️ 24.2% phụ thuộc ngữ cảnh → cần context merging
- ⚠️ 13.8% tham chiếu file đính kèm → missing context
- ⚠️ Câu trả lời có thể **outdated** (quy định thay đổi qua các năm)
- ⚠️ 57.7% câu hỏi đa phần → retrieval có thể bị phân tán

### Hướng sử dụng cho RAG
1. **Knowledge base:** Dùng làm corpus bổ sung cho RAG bên cạnh tài liệu chính thức (CTĐT, quy định)
2. **Evaluation set:** Tạo test set từ các câu hỏi thực tế để đánh giá hệ thống RAG
3. **Intent classification training:** Dùng để train bộ phân loại intent cho chatbot
4. **FAQ extraction:** Trích xuất top câu hỏi phổ biến nhất thành FAQ tĩnh
