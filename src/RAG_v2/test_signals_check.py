"""Quick test to check signal detection for specific queries."""
import re, unicodedata

def fold(text):
    value = unicodedata.normalize("NFD", text or "")
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    return value.replace("\u0111", "d").replace("\u0110", "D").casefold()

def matches_any(text, patterns):
    return any(re.search(p, text) for p in patterns)

_PERSONAL = (
    r"\b(toi|minh|em|cua toi|nganh cua toi|chuong trinh cua toi|sinh vien nhu toi)\b",
    r"\b(hoc phan cua toi|diem cua toi|cpa cua toi|gpa cua toi)\b",
)
_ELIGIBILITY = (
    r"\b(dieu kien|du dieu kien|dat dieu kien|co du dieu kien)\b",
    r"\b(tot nghiep|xet tot nghiep|dang ky tot nghiep|cong nhan tot nghiep)\b",
    r"\b(chuan dau ra|ngoai ngu dau ra|gdtc|gdqp|giao duc the chat|quoc phong)\b",
    r"\b(hoc bong|mien giam|duoc xet|co duoc|duoc khong|ky luat|dinh chi)\b",
)

# Also check _has_personal_eligibility_inputs logic
def has_personal_inputs(question):
    folded = fold(question)
    return bool(
        "cpa" in folded
        or "gpa" in folded
        or "ielts" in folded
        or "toeic" in folded
        or "gdtc" in folded
        or "gdqp" in folded
        or "ngoai ngu" in folded
        or "ky luat" in folded
        or "dang ky tot nghiep" in folded
        or "tin chi" in folded and any(ch.isdigit() for ch in folded)
    )

# Also check complexity_router regex patterns
_COMPLEX_PERSONAL_CHECK = re.compile(
    r"\b(tôi|mình|em)\b.{0,80}\b(có\s+thể|đủ\s+điều\s+kiện|đạt\s+điều\s+kiện|đạt\s+chuẩn|được\s+không|có\s+được)\b",
    re.IGNORECASE,
)

queries = [
    "K70: Nếu tôi học CNTT Việt-Pháp thì chuẩn đầu ra là gì?",
    "K70: Nếu tôi đạt Bậc 2.3 thì tôi thuộc nhóm mấy?",
    "K69: Tôi cần đạt Bậc mấy để được nhận đồ án tốt nghiệp?",
    "K70: Nếu tôi có chứng chỉ IELTS 5.5 thì tôi có phải học tiếng Anh cơ sở không?",
]

for q in queries:
    f = fold(q)
    pr = matches_any(f, _PERSONAL)
    ec = matches_any(f, _ELIGIBILITY)
    has_inputs = has_personal_inputs(q)
    
    # Signal-based route in complexity_router (line 174)
    signal_personal_check = pr and ec
    
    # Regex pattern route in complexity_router
    regex_match = _COMPLEX_PERSONAL_CHECK.search(q)
    
    # _should_clarify check
    would_clarify = signal_personal_check and not has_inputs
    
    print(f"Q: {q}")
    print(f"  Folded: {f}")
    print(f"  personal_reference={pr}, eligibility_check={ec}")
    print(f"  signal_personal_check={signal_personal_check}")
    print(f"  regex_personal_check={bool(regex_match)} (pattern match: {regex_match})")
    print(f"  has_personal_inputs={has_inputs}")
    print(f"  >>> WOULD CLARIFY (skip RAG) = {would_clarify}")
    print()
