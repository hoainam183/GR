# Đánh giá lỗi trong conversation của hệ thống RAG

## Conversation

**User:** ME-GU có học phí là bao nhiêu?  
**System:** Trả lời đúng mức học phí của ME-GU.

**User:** so với ngành của tôi  
**System:** So sánh **ngoại ngữ** giữa ME-GU và IT-E6.

**User:** so về học phí  
**System:** Nói rằng **không tìm thấy học phí IT-E6** để so sánh với ME-GU.

**User:** mức học phí cho ngành của tôi  
**System:** Lại **tìm thấy và trả lời được học phí IT-E6**.

---

## Các lỗi của hệ thống

### 1. Lỗi hiểu sai ngữ cảnh hội thoại

Ở câu:

> “so với ngành của tôi”

Ngữ cảnh gần nhất đang nói về **học phí ME-GU**, nên hệ thống cần hiểu là:

> So sánh **học phí** ME-GU với học phí ngành IT-E6.

Tuy nhiên, hệ thống lại chuyển sang so sánh **ngoại ngữ**, tức là bị kéo theo ngữ cảnh cũ không còn phù hợp.

---

### 2. Lỗi truy hồi không nhất quán

Ở câu:

> “so về học phí”

Hệ thống nói:

> Không tìm thấy thông tin học phí IT-E6.

Nhưng ngay sau đó, khi user hỏi:

> “mức học phí cho ngành của tôi”

hệ thống lại truy xuất được chính thông tin học phí IT-E6.

Điều này cho thấy retrieval bị **thiếu ổn định**: cùng một thông tin có trong tài liệu nhưng lúc tìm được, lúc không.

---

### 3. Lỗi xử lý câu hỏi so sánh

Với yêu cầu:

> “so về học phí”

Hệ thống đáng lẽ phải:

- Truy hồi học phí ME-GU
- Truy hồi học phí IT-E6
- Tổng hợp thành bảng hoặc kết luận so sánh

Nhưng thực tế hệ thống không hoàn thành được tác vụ so sánh, mà dừng lại ở việc báo thiếu dữ liệu.

---

### 4. Lỗi kết luận “không có thông tin” quá sớm

Hệ thống khẳng định:

> “Tài liệu hiện có không cung cấp thông tin chi tiết về học phí IT-E6.”

Trong khi tài liệu thực tế **có thông tin đó**.

Đây là lỗi nghiêm trọng vì làm giảm độ tin cậy của hệ thống. Khi retrieval chưa thấy, hệ thống nên:

- Thử truy vấn lại
- Hoặc nói “chưa truy xuất được” thay vì kết luận “không có”

---

## Tóm lại

Conversation này bộc lộ 3 vấn đề chính của hệ thống RAG:

1. **Sai ngữ cảnh hội thoại**: hiểu “so với ngành của tôi” thành so sánh ngoại ngữ thay vì học phí.  
2. **Retrieval thiếu nhất quán**: cùng một thông tin học phí IT-E6 nhưng lúc không tìm thấy, lúc lại tìm thấy.  
3. **Tổng hợp so sánh kém**: chưa xử lý tốt các câu hỏi yêu cầu đối chiếu thông tin giữa hai đối tượng.
