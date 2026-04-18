import re

CHITCHAT_PATTERNS = [
    r"^(xin chào|hello|hi|chào|hey)",
    r"^(bạn là ai|you are|who are you)",
    r"^(cảm ơn|thank|thanks)",
    r"^(tạm biệt|bye|goodbye)",
]

COMPLEX_PATTERNS = [
    # So sánh khóa
    r"so sánh.*(K\d{2}|khóa)",
    r"(K\d{2}).*(K\d{2})",                # K65 ... K70
    r"khác nhau|giống nhau|khác biệt",
    # Tổng hợp đa nguồn
    r"đủ điều kiện",
    r"có thể.*(tốt nghiệp|đăng ký|xét)",
    r"tất cả.*điều kiện",
    # Câu hỏi mơ hồ
    r"^cho tôi biết về\s+\w+$",           # quá ngắn/chung
    r"^(học bổng|môn học|lịch)\s*\??$",  # 1-2 từ không có context
    # Multi-step
    r"và.*(cho biết|liệt kê|so sánh)",
]

class ComplexityRouter:
    def route(self, query: str) -> str:
        """Returns: 'chitchat' | 'simple' | 'complex'"""
        q = query.strip().lower()

        # 1. Chitchat check
        for pattern in CHITCHAT_PATTERNS:
            if re.search(pattern, q):
                return "chitchat"

        # 2. Complex check
        for pattern in COMPLEX_PATTERNS:
            if re.search(pattern, q, re.IGNORECASE):
                return "complex"

        # 3. Multi-domain heuristic: câu hỏi dài + nhiều dấu hỏi/và
        if len(q.split()) > 25:
            return "complex"
        if q.count("?") > 1 or q.count(" và ") > 2:
            return "complex"

        return "simple"