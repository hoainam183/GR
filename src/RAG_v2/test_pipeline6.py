import re

_GENERIC_WORDS = {
    "tôi", "mình", "em", "bạn",
    "muốn", "cần", "hỏi", "biết", "tìm", "hiểu", "xem",
    "thông", "tin", "chung", "chi", "tiết", "tổng", "quan", "giới", "thiệu",
    "về", "của", "cho", "trong", "thuộc",
    "là", "gì", "như", "thế", "nào", "ra", "sao", "ở", "đâu",
    "có", "những", "cái", "các",
    "vui", "lòng", "hãy",
    "ngành", "chuyên", "học", "chương", "trình", "đào", "tạo"
}

def is_meaningful(text: str) -> bool:
    words = re.findall(r'\w+', text.lower())
    non_generic = [w for w in words if w not in _GENERIC_WORDS]
    return len(non_generic) >= 1

queries = [
    "tôi muốn tìm hiểu về",
    "môn mạng máy tính",
    "quy định ngoại ngữ",
    "thông tin chung về",
    "giới thiệu chi tiết",
    "học phí",
]

for q in queries:
    print(f"'{q}' -> meaningful: {is_meaningful(q)}")

