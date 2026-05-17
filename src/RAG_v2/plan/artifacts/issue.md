# Báo cáo Vấn đề (Issues Report) - Tích hợp Tavily Web Search

Tài liệu này tổng hợp các vấn đề phát sinh, phân tích nguyên nhân và giải pháp trong quá trình tích hợp và kích hoạt tính năng Tavily Web Search Fallback cho hệ thống RAG v2.

---

## Issue 1: Tavily Fallback không được kích hoạt dù mã nguồn đã hoàn thiện

**Mô tả:**
Hệ thống đã có sẵn toàn bộ logic code cho Tavily trong file `tavily_search.py` và đã tích hợp vào `flows.py`. Tuy nhiên, khi truy vấn các thông tin hệ thống không có, LLM vẫn trả lời trực tiếp thay vì gọi web search.

**Ví dụ:**
Hỏi về một sự kiện mới nhất không có trong database, LLM trả lời "Tôi không có thông tin" thay vì search web.

**Phân tích lỗi (Root Cause):**
Tính năng Tavily Fallback bị chặn hoàn toàn ở mức cấu hình môi trường. Trong file `pipeline/flows.py`, luồng gọi Tavily chỉ được kích hoạt nếu `self_evaluator is not None`. Tuy nhiên, biến này chỉ được khởi tạo khi `SELF_EVAL_ENABLED=true` trong file `.env`. Do file `.env` đang để `false` (mặc định để tối ưu tốc độ), hệ thống bỏ qua toàn bộ bước Self-eval và Fallback.

**Giải pháp:**
Sửa file `.env`, chuyển cấu hình thành:
```env
SELF_EVAL_ENABLED=true
TAVILY_FALLBACK_ENABLED=true
```

---

## Issue 2: Cấu hình lọc Domain chứa Subdomain và Routing SPA (Vue/React)

**Mô tả:**
Có nhu cầu giới hạn phạm vi tìm kiếm của Tavily vào các trang cụ thể của trường, bao gồm cả các trang ứng dụng (SPA) có URL dạng hash, ví dụ: `sv-ctt.hust.edu.vn/#/so-tay-sv`. Làm thế nào để truyền URL này cho Tavily?

**Phân tích lỗi (Root Cause):**
1. Tham số `include_domains` của Tavily API chỉ chấp nhận cấu trúc Tên miền (Domain/Subdomain), không chấp nhận đường dẫn (Path) hay các ký tự như `#/`. Truyền toàn bộ URL vào sẽ làm API báo lỗi.
2. `sv-ctt.hust.edu.vn` về mặt mạng lý thuyết là một subdomain hoàn toàn độc lập với `ctt.hust.edu.vn` (có dấu gạch ngang). Nếu chỉ truyền `ctt.hust.edu.vn`, Tavily sẽ không tìm trong `sv-ctt`.

**Giải pháp:**
Bổ sung minh bạch chuỗi `"sv-ctt.hust.edu.vn"` vào danh sách `HUST_DOMAINS`. Không cần truyền đoạn `#/so-tay-sv`, crawler của Tavily sẽ tự động tìm nội dung trang Sổ tay sinh viên thông qua các từ khóa trong câu hỏi.

---

## Issue 3: Lo ngại tốn kém chi phí (Credit API) khi gọi Tavily

**Mô tả:**
Mối lo ngại rằng việc truyền quá nhiều domain (HUST_DOMAINS) hoặc việc mọi câu hỏi đều đẩy lên Tavily sẽ làm cạn kiệt gói Free Tier (1,000 credits/tháng).

**Phân tích lỗi (Root Cause):**
Hiểu nhầm về cách tính phí của Tavily và kiến trúc RAG hiện tại:
1. **Lọc Domain:** Tavily tính 1 credit / 1 lần gọi hàm (cho mức basic search). Dù truyền 1 hay 50 domains vào `include_domains`, chi phí vẫn không đổi.
2. **Tần suất gọi:** Tavily đóng vai trò là chốt chặn cuối cùng (Fallback). Nó được bảo vệ bởi một màng lọc 2 lớp:
   - **Lớp 1:** Điểm truy xuất nội bộ (Reranker Score).
   - **Lớp 2:** Lớp tự đánh giá (Self-Evaluator LLM). 
   Chỉ khi nào DB nội bộ thất bại, Tavily mới bị trừ credit. (Tiết kiệm ~90-95% queries).

**Giải pháp:**
Yên tâm sử dụng. Với thiết kế hiện tại, ước tính chỉ tốn ~100-200 credits/tháng.

---

## Issue 4: Reranker Logits cao gây "Lủng lưới" lớp Self-Eval

**Mô tả:**
Sau khi đã bật `SELF_EVAL_ENABLED=true`, với câu hỏi: *"Kế hoạch học GDPQ kì hè K70"*, LLM trả lời là không tìm thấy thông tin GDPQ nhưng Tavily Fallback vẫn **không** được gọi.

**Ví dụ (Log Trace):**
```text
Rerank: 5.42s
#1 Đăng ký kế hoạch học tập kỳ hè... (rerank: 5.2517)
```
Hoàn toàn vắng bóng timing của bước `Self_eval` và `Tavily_search`.

**Phân tích lỗi (Root Cause):**
Hệ thống có cơ chế tối ưu (Shortcut): Nếu tài liệu nội bộ trả về có điểm chất lượng quá cao (`top_score >= 0.72`), nó sẽ tin tưởng tài liệu này và **bỏ qua hoàn toàn bước Self-eval**. 
- Hệ thống đang dùng **BGE Reranker** local, mô hình này trả về điểm số dạng *Raw Logits* (dao động từ -10.0 đến +10.0), chứ không phải xác suất đã chuẩn hóa [0, 1].
- Tài liệu nội bộ trùng khớp cực mạnh với cụm *"Kế hoạch học tập kì hè K70"* (chỉ thiếu đúng chữ GDPQ). BGE Reranker chấm điểm thô rất cao: **`5.2517`**.
- Vì `5.2517 >= 0.72` (Ngưỡng được set mặc định theo logic xác suất của Cohere), hệ thống lầm tưởng đã tìm ra "chân ái" nên bỏ qua luôn việc tự kiểm tra nội dung (Skip Self-Eval), dẫn đến không bao giờ đụng tới Tavily.

**Giải pháp:**
Khắc phục sự chênh lệch hệ quy chiếu bằng cách thay đổi giá trị ngưỡng chặn trong file `.env` lên một mức cực cao để vô hiệu hóa tính năng skip, ép hệ thống luôn luôn tự đọc và tự đánh giá lại mọi truy xuất:
```env
SELF_EVAL_MIN_TOP_SCORE=100.0
```
*(Nếu muốn dùng Shortcut, cần phải cài đặt một con số phù hợp với phổ điểm của BGE Logits, ví dụ 6.0 hoặc 7.0).*
