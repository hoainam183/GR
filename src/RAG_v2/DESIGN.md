# DESIGN.md — Chatbot Sinh viên HUST

Tài liệu thiết kế giao diện (UI/UX) cho chatbot hỗ trợ sinh viên Đại học Bách khoa Hà Nội, bám theo nhận diện của Cổng thông tin đào tạo (ctt.hust.edu.vn) và nhu cầu thực tế của sinh viên: tra cứu thông báo, kế hoạch học tập, học phí, quy chế, biểu mẫu, lịch thi, dịch vụ sinh viên.

---

## 1. Định hướng thiết kế

**Tên gợi ý:** BKA (Bách Khoa Assistant) / iBK / Trợ lý CTT

**Tính cách giao diện:** Tin cậy – Rõ ràng – Nhanh. Chatbot đại diện cho một cơ quan đào tạo, nên giao diện cần nghiêm túc và chính xác như một văn bản hành chính, nhưng trải nghiệm phải nhẹ nhàng, thân thiện như một app sinh viên dùng hằng ngày. Tránh hiệu ứng màu mè, gradient lòe loẹt, emoji dày đặc.

**Nguyên tắc cốt lõi:**
1. **Câu trả lời là trung tâm** — mọi thành phần khác (header, sidebar, gợi ý) phải nhường chỗ cho nội dung hội thoại.
2. **Luôn dẫn nguồn** — chatbot hoạt động theo kiến trúc RAG với kho tri thức chủ yếu là các file PDF (quy chế, thông báo, biểu mẫu). Mỗi câu trả lời phải kèm trích dẫn về tài liệu gốc: tên file PDF, số trang/mục được trích, và link tải hoặc xem tài liệu (kèm link bài viết trên ctt.hust.edu.vn nếu có) để sinh viên kiểm chứng.
3. **Mobile-first** — phần lớn sinh viên truy cập bằng điện thoại; thiết kế desktop là bản mở rộng của mobile, không phải ngược lại.
4. **Tiếng Việt chuẩn, có dấu** — toàn bộ UI copy dùng tiếng Việt; hỗ trợ hiển thị tốt các thuật ngữ mã hóa của trường (ĐTĐH, ĐTSĐH, VLVH, CTSV, GDQP, mã kỳ 20252...).

---

## 2. Hệ màu (Color Tokens)

Lấy cảm hứng từ màu đỏ nhận diện của ĐHBK Hà Nội (cần đối chiếu mã hex chính xác với bộ nhận diện thương hiệu chính thức của trường trước khi triển khai).

| Token | Hex | Vai trò |
|---|---|---|
| `--bk-red` | `#C02430` | Màu chủ đạo: header, nút gửi, avatar bot, link hover |
| `--bk-red-dark` | `#9A1B26` | Trạng thái hover/pressed của nút chính |
| `--bk-red-tint` | `#FBEAEC` | Nền nhãn tag, highlight nhẹ, bong bóng trích dẫn |
| `--ink` | `#1F2328` | Chữ chính |
| `--ink-soft` | `#5B6470` | Chữ phụ, timestamp, placeholder |
| `--surface` | `#FFFFFF` | Nền bong bóng bot, card |
| `--surface-alt` | `#F5F6F8` | Nền trang, nền vùng hội thoại |
| `--border` | `#E3E6EA` | Viền card, divider |
| `--success` | `#1E7F4E` | Trạng thái thành công (đã nộp học phí, còn hạn đăng ký) |
| `--warning` | `#B7791F` | Cảnh báo deadline sắp đến |
| `--error` | `#C0392B` | Lỗi hệ thống, quá hạn |

**Quy ước dùng màu đỏ:** đỏ là màu *nhấn*, không phải màu *nền diện rộng*. Chỉ dùng cho: thanh header mảnh, nút hành động chính, viền trái của card thông báo quan trọng. Nền hội thoại luôn sáng/trung tính để dễ đọc văn bản dài (trích quy chế thường rất dài).

**Dark mode (tùy chọn giai đoạn 2):** nền `#15171A`, surface `#1F2226`, đỏ chuyển sang `#E5535E` để đạt độ tương phản; chữ `#E8EAED`.

---

## 3. Typography

| Vai trò | Font | Cỡ / Weight |
|---|---|---|
| UI & nội dung chat | **Inter** (fallback: Roboto, system-ui) | 15–16px / 400, 600 |
| Tiêu đề khu vực, tên bot | **Be Vietnam Pro** | 18–22px / 600–700 |
| Dữ liệu dạng mã (mã lớp, mã HP, kỳ 20252) | **JetBrains Mono** hoặc `monospace` | 14px / 500 |

Lý do: Inter và Be Vietnam Pro hỗ trợ tiếng Việt đầy đủ, dấu không bị lệch dòng. Mã học phần/mã lớp dùng monospace giúp sinh viên đối chiếu chính xác (IT3080 vs IT3O80).

- Line-height nội dung chat: 1.6 (văn bản quy chế dài cần thoáng).
- Không dùng chữ in hoa toàn bộ cho đoạn dài; chỉ dùng cho nhãn tag ngắn (`ĐTĐH`, `CTSV`).

---

## 4. Layout

### 4.1 Mobile (mặc định, ≤ 768px)

```
┌──────────────────────────────┐
│ ☰  [logo] Trợ lý CTT      ⋮ │  ← header 56px, nền đỏ, chữ trắng
├──────────────────────────────┤
│                              │
│  [bot] Chào bạn! Mình có     │
│  thể giúp gì về học tập?     │
│                              │
│  ┌ Gợi ý nhanh ──────────┐   │
│  │ Lịch nộp học phí 20252 │   │
│  │ Đăng ký học GDQP hè    │   │
│  │ Thủ tục trở lại học    │   │
│  └────────────────────────┘   │
│                              │
│            Bạn hỏi gì đó ──┐ │
│            └───────────────┘ │
├──────────────────────────────┤
│ [+]  Nhập câu hỏi...    [➤] │  ← input bar cố định đáy
└──────────────────────────────┘
```

### 4.2 Desktop (≥ 1024px)

```
┌────────────┬─────────────────────────────────┐
│  SIDEBAR   │  HEADER (breadcrumb + tài khoản)│
│            ├─────────────────────────────────┤
│ + Chat mới │                                 │
│            │      VÙNG HỘI THOẠI             │
│ Hôm nay    │      (max-width 760px,          │
│  · Học phí │       căn giữa)                 │
│  · GDQP K70│                                 │
│ Tuần trước │                                 │
│  · ...     ├─────────────────────────────────┤
│            │  [ Ô nhập câu hỏi          ➤ ]  │
│ ⚙ Cài đặt  │  gợi ý chip: học phí · lịch thi │
└────────────┴─────────────────────────────────┘
```

- Sidebar 280px, có thể thu gọn; lưu lịch sử hội thoại nhóm theo ngày.
- Vùng hội thoại giới hạn `max-width: 760px` để dòng văn bản không quá dài.
- Có thể nhúng dạng **widget nổi** (bubble góc phải dưới) trên ctt.hust.edu.vn: bubble 56px màu đỏ, mở ra panel 380×600px.

---

## 5. Thành phần (Components)

### 5.1 Bong bóng tin nhắn
- **Bot:** nền trắng, viền `--border`, bo góc 12px (góc trên-trái 4px), avatar logo BK 32px bên trái. Hỗ trợ render Markdown: bảng, danh sách, đậm/nghiêng, link.
- **Người dùng:** nền `--bk-red`, chữ trắng, bo góc 12px (góc trên-phải 4px), căn phải, không avatar.
- Timestamp mờ (`--ink-soft`, 12px) hiện khi chạm/hover.
- Tin nhắn dài > 12 dòng: thu gọn kèm nút "Xem thêm".

### 5.2 Card trích nguồn (Citation card)
Bắt buộc với câu trả lời lấy từ kho tri thức RAG. Đặt cuối bong bóng bot:

```
┌─────────────────────────────────────────────┐
│ ▌📄 QD_quy-che-dao-tao-DH_2023.pdf          │
│ ▌   Điều 14, tr. 12–13 · [ĐTĐH]             │
├─────────────────────────────────────────────┤
│ ▌🔗 KẾ HOẠCH NỘP HỌC PHÍ KỲ 2 2025-2026     │
│ ▌   ctt.hust.edu.vn · [ĐTĐH] · 01/06        │
└─────────────────────────────────────────────┘
```
Viền trái 3px màu đỏ. Với nguồn PDF: hiển thị tên file, số trang/điều khoản được trích; click mở viewer PDF (nhảy đúng trang nếu kỹ thuật cho phép) hoặc tải file. Với nguồn web: click mở tab mới đến bài viết gốc. Tối đa 3 nguồn, nguồn thừa gom vào "+n nguồn khác".

Tùy chọn nâng cao: bấm vào card mở panel xem đoạn văn bản gốc được trích (highlight đoạn liên quan) ngay trong chat, không cần tải cả file PDF.

### 5.3 Chip gợi ý (Suggested prompts)
- Hiển thị khi mở chat và sau mỗi câu trả lời (gợi ý theo ngữ cảnh).
- Dạng pill: nền trắng, viền `--border`, hover viền đỏ; tối đa 4 chip, mỗi chip ≤ 6 từ.
- Nội dung lấy theo mùa vụ học tập: đầu kỳ → đăng ký lớp; giữa kỳ → lịch thi; tháng 6 → học phí, GDQP hè.

### 5.4 Card dữ liệu có cấu trúc
Khi trả lời về kế hoạch/deadline, render thành card thay vì văn xuôi:

```
┌──────────────────────────────┐
│ 01   NỘP HỌC PHÍ KỲ 20252    │
│ TH6  Đợt 2 · Hạn: 01/06/2026 │
│      [⚠ Còn 3 ngày]          │
└──────────────────────────────┘
```
Khối ngày bên trái giống lịch trên CTT (ô vuông, số to, tháng nhỏ). Badge trạng thái dùng `--warning`/`--error` theo độ gấp.

### 5.5 Ô nhập liệu
- Cố định đáy màn hình, nền trắng, shadow nhẹ phía trên.
- Textarea tự giãn tối đa 5 dòng; Enter gửi, Shift+Enter xuống dòng (desktop).
- Nút gửi: tròn 40px, nền đỏ, icon mũi tên trắng; disabled (xám) khi ô trống.
- Nút `+` (giai đoạn 2): đính kèm ảnh biểu mẫu, file PDF để hỏi.
- Placeholder xoay vòng: "Hỏi về học phí, lịch thi, quy chế…"

### 5.6 Trạng thái hệ thống
| Trạng thái | Thể hiện |
|---|---|
| Bot đang trả lời | 3 chấm nhấp nháy trong bong bóng bot + stream chữ dần |
| Lỗi mạng | Bong bóng xám: "Không gửi được. **Thử lại**" |
| Không tìm thấy thông tin | Bot nói rõ không có dữ liệu, kèm link Liên hệ phòng ban + chip "Hỏi cách khác" |
| Câu hỏi ngoài phạm vi | Lịch sự từ chối, gợi ý chủ đề bot hỗ trợ |
| Bảo trì | Banner vàng trên header |

### 5.7 Feedback
Dưới mỗi câu trả lời bot: 👍 👎 và nút "Sao chép". Bấm 👎 mở popover chọn lý do (Sai thông tin / Thiếu nguồn / Không liên quan).

---

## 6. Luồng hội thoại & UX writing

**Tin nhắn chào (lần đầu):**
> Chào bạn! Mình là Trợ lý CTT của Đại học Bách khoa Hà Nội. Mình giúp bạn tra cứu thông báo, kế hoạch học tập, học phí, quy chế và biểu mẫu. Bạn cần gì hôm nay?

**Giọng điệu:** xưng "mình", gọi "bạn"; câu ngắn, chủ động; không hứa hẹn thay phòng ban ("Theo thông báo ngày 01/06…", không phải "Chắc chắn bạn sẽ…"). Khi trích quy chế, ghi rõ số hiệu văn bản và ngày hiệu lực.

**Disclaimer cố định** (footer, chữ nhỏ): "Thông tin do AI tổng hợp từ tài liệu, quy chế và thông báo của Nhà trường, có thể chưa đầy đủ. Vui lòng đối chiếu văn bản gốc."

**Xử lý mơ hồ:** câu hỏi thiếu ngữ cảnh (vd: "học phí bao nhiêu?") → bot hỏi lại 1 lần kèm chip lựa chọn (Đại học / Sau đại học / VLVH) thay vì trả lời chung chung.

---

## 7. Accessibility & chất lượng

- Tương phản chữ/nền đạt WCAG AA (≥ 4.5:1); kiểm tra riêng chữ trắng trên nền đỏ.
- Focus ring rõ ràng (outline 2px đỏ) cho điều hướng bàn phím; thứ tự tab: input → gửi → chip → lịch sử.
- `aria-live="polite"` cho vùng tin nhắn để screen reader đọc câu trả lời mới.
- Tôn trọng `prefers-reduced-motion`: tắt animation typing, chỉ giữ fade.
- Vùng chạm tối thiểu 44×44px trên mobile.
- Hiệu năng: skeleton cho lịch sử chat; stream câu trả lời để cảm giác phản hồi < 1s.

---

## 8. Lộ trình giao diện

| Giai đoạn | Phạm vi |
|---|---|
| **MVP** | Chat 1 cột mobile-first, citation card, chip gợi ý, feedback 👍👎, disclaimer |
| **GĐ 2** | Sidebar lịch sử, dark mode, đính kèm file, card deadline có đếm ngược |
| **GĐ 3** | Widget nhúng trên ctt.hust.edu.vn, đăng nhập SSO (asso.hust.edu.vn) để cá nhân hóa theo mã số sinh viên, thông báo đẩy deadline |

---

## 9. Checklist trước khi build

- [ ] Xin file logo + mã màu chính thức từ bộ nhận diện thương hiệu ĐHBK Hà Nội
- [ ] Chốt tên bot và avatar
- [ ] Duyệt nội dung disclaimer với phòng CTSV/ĐTĐH
- [ ] Test font tiếng Việt trên Android/iOS cũ
- [ ] Kiểm thử contrast màu đỏ trên cả light/dark mode