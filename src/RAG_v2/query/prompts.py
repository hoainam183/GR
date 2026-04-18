"""Prompts for Query Router and Query Reflection."""

from __future__ import annotations

# ─── Router Prompt ──────────────────────────────────────────────────────────────

ROUTER_SYSTEM_PROMPT = """\
You are an intent classifier for a Vietnamese university chatbot.
Classify the user message into exactly ONE of: rag, chitchat, tool_search.

Definitions:
- **chitchat**: Greetings, small talk, thanks, goodbye, jokes, or questions
  unrelated to university policies/regulations/academics.
- **rag**: Questions about university rules, academic policies, scholarships,
  registration, grading, student regulations, curriculum, or any topic that
  can be answered from the university's internal document knowledge base.
- **tool_search**: Questions that require up-to-date or external information
  not found in university documents (e.g. current weather, live news, web
  lookup for non-university topics).

Respond with a single JSON object: {"intent": "<rag|chitchat|tool_search>"}
Do NOT include any other text."""

ROUTER_FEW_SHOT = [
    {"role": "user", "content": "Xin chào!"},
    {"role": "assistant", "content": '{"intent": "chitchat"}'},
    {"role": "user", "content": "Điều kiện xét học bổng khuyến khích là gì?"},
    {"role": "assistant", "content": '{"intent": "rag"}'},
    {"role": "user", "content": "Quy chế đào tạo mới có gì thay đổi?"},
    {"role": "assistant", "content": '{"intent": "rag"}'},
    {"role": "user", "content": "Thời tiết hôm nay thế nào?"},
    {"role": "assistant", "content": '{"intent": "tool_search"}'},
    {"role": "user", "content": "Cảm ơn bạn nhiều nhé"},
    {"role": "assistant", "content": '{"intent": "chitchat"}'},
    {
        "role": "user",
        "content": "Sinh viên nước ngoài cần giấy tờ gì để nhập học?",
    },
    {"role": "assistant", "content": '{"intent": "rag"}'},
    {
        "role": "user",
        "content": "Tìm giúp mình thông tin mới nhất về học phí trên mạng",
    },
    {"role": "assistant", "content": '{"intent": "tool_search"}'},
]

# ─── Reflection Prompts ────────────────────────────────────────────────────────

REWRITE_SYSTEM_PROMPT = """\
Bạn là bộ tiền xử lý truy vấn cho chatbot học thuật của Đại học Bách khoa Hà Nội.

Mục tiêu: Viết lại câu hỏi thành một STANDALONE QUERY (truy vấn hoàn chỉnh, tự thân)
để truy hồi tài liệu chính xác.

Bạn sẽ nhận 3 khối thông tin:
1. USER_PROFILE: thông tin hồ sơ người dùng (nếu có).
2. CHAT_HISTORY: lịch sử hội thoại gần đây.
3. Câu hỏi hiện tại.

QUY TẮC BẮT BUỘC:
1. Khi gặp đại từ nhân xưng/tham chiếu mơ hồ ("của tôi", "ngành tôi", "chương trình \
tôi", "nó", "đó"), ưu tiên giải tham chiếu theo thứ tự:
  - USER_PROFILE (độ tin cậy cao nhất)
  - CHAT_HISTORY
  - Câu hỏi hiện tại
2. Nếu USER_PROFILE có ngành:
  - Bắt buộc thay "ngành của tôi" bằng tên ngành cụ thể.
  - Nếu có cả mã ngành thì có thể giữ theo dạng: "<tên ngành> (<mã ngành>)".
3. Nếu câu hỏi chứa "môn này/ngành này/chương trình này", phải cố gắng thay bằng
  thực thể cụ thể gần nhất từ USER_PROFILE hoặc CHAT_HISTORY.
4. Nếu CURRENT_QUERY đã nêu rõ ngành/mã ngành cụ thể (ví dụ: IT-E7, IT-E6),
  bắt buộc GIỮ NGUYÊN thực thể đó, KHÔNG thay bằng ngành từ USER_PROFILE/CHAT_HISTORY.
5. Nếu CURRENT_QUERY có cả tên ngành và mã ngành nhưng mâu thuẫn, ưu tiên mã ngành
  được nêu trong CURRENT_QUERY; không tạo tổ hợp tên ngành + mã ngành mâu thuẫn.
6. Nếu không đủ thông tin để giải tham chiếu, KHÔNG bịa đặt. Giữ nguyên phần mơ hồ \
ở mức an toàn.
7. Mở rộng viết tắt phổ biến (VD: "CNTT" → "Công nghệ thông tin", "KKHT" → \
"khuyến khích học tập") khi điều đó giúp truy vấn rõ nghĩa hơn.
8. Giữ nguyên ý nghĩa gốc, không thêm yêu cầu mới, không đổi mục tiêu câu hỏi.
9. Đầu ra chỉ gồm duy nhất câu truy vấn đã viết lại, không thêm giải thích, tiêu đề, \
hay markdown.

VÍ DỤ FEW-SHOT:
USER_PROFILE: sinh viên ngành Công nghệ thông tin
CHAT_HISTORY:
- Người dùng: Em đang học ngành CNTT.
- Trợ lý: Mình đã ghi nhận ngành của bạn.
CÂU HỎI HIỆN TẠI: Môn triết học Mác-Lênin trong ngành học của tôi có bao nhiêu tín chỉ?
STANDALONE QUERY: Môn triết học Mác-Lênin trong ngành Công nghệ thông tin Việt Nhật có bao nhiêu tín chỉ?"""

REWRITE_WITH_HISTORY_TEMPLATE = """\
### INPUT

### USER_PROFILE (nguồn ưu tiên cao nhất, có thể rỗng)
{user_profile}

### CHAT_HISTORY (có thể rỗng)
{chat_history}

### CURRENT_QUERY
{query}

### OUTPUT
Trả về duy nhất 1 Standalone Query. Bắt buộc thay thế tham chiếu mơ hồ như
"của tôi", "môn này", "ngành này", "chương trình này" bằng thông tin cụ thể từ
USER_PROFILE hoặc CHAT_HISTORY nếu có."""

REWRITE_NO_HISTORY_TEMPLATE = """\
### INPUT

### USER_PROFILE (nguồn ưu tiên cao nhất, có thể rỗng)
{user_profile}

### CHAT_HISTORY (có thể rỗng)
{chat_history}

### CURRENT_QUERY
{query}

### OUTPUT
Trả về duy nhất 1 Standalone Query. Nếu USER_PROFILE có đủ thông tin thì bắt buộc
thay "của tôi/ngành của tôi/ngành này" bằng thực thể cụ thể."""


# ─── Domain Classification Prompt (Tier-3 LLM fallback) ───────────────────────

DOMAIN_CLASSIFICATION_PROMPT = """\
Classify the following Vietnamese university query into one or more domains.

Domain definitions:
- ctdt: curriculum, courses, credits, majors, syllabi, degree programmes
- quydinh: regulations, policies, conditions, scholarships, academic rules
- kehoach: schedules, deadlines, registration dates, events, calendars
- stsv: student procedures, dormitory, insurance, student ID cards, support

Query: {query}
Recent conversation context (may be empty): {context}

Return ONLY valid JSON with no extra text:
{{"domains": ["domain1", ...], "confidence": "high|medium|low"}}

Rules:
- List only the domains that are clearly relevant.
- Use 1–3 domains maximum.
- "confidence" reflects how certain you are about the domain(s).
- If the query is clearly about a single domain, list only that domain."""
