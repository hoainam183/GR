"""Test script for routing logic fixes.

Tests each component in isolation:
1. ComplexityRouter — chitchat/simple/complex tier classification
2. QuerySignals — regex-based signal detection
3. fold_vietnamese consistency

Run: python test_routing_fixes.py
"""

from __future__ import annotations

import importlib
import importlib.util
import io
import sys
from pathlib import Path

# Force UTF-8 output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

# Direct file-based imports — completely bypass query/__init__.py
# which pulls in sklearn/joblib (heavy deps not needed for routing tests)
import importlib.util

def _load_module(name: str, filepath: str):
    spec = importlib.util.spec_from_file_location(name, filepath)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

_signals_mod = _load_module("query.signals", str(PROJECT_ROOT / "query" / "signals.py"))
analyze_query_signals = _signals_mod.analyze_query_signals
fold_vietnamese_text = _signals_mod.fold_vietnamese_text

_cr_mod = _load_module("query.complexity_router", str(PROJECT_ROOT / "query" / "complexity_router.py"))
ComplexityRouter = _cr_mod.ComplexityRouter




def _fmt(result: dict) -> str:
    """Format routing result for display."""
    tier = result.get("tier", "?")
    reason = result.get("reason", "")[:60]
    subtype = result.get("complex_subtype", "")
    conf = result.get("confidence", "")
    if subtype:
        return f"{tier}/{subtype} [{conf}] ({reason})"
    return f"{tier} [{conf}] ({reason})"


def _signals_fmt(signals) -> str:
    """Format signals for display."""
    active = [k for k, v in signals.to_dict().items() if v]
    return ", ".join(active) if active else "(none)"


# ═══════════════════════════════════════════════════════════════════════════════
# Test cases grouped by the bug they verify
# ═══════════════════════════════════════════════════════════════════════════════

# --- BUG 1: count("cho") >= 2 false positive ---
BUG1_TESTS = [
    # (query, expected_tier, description)
    ("Cho em hỏi điều kiện cho học bổng?", "simple", "Simple question with 2x 'cho' — should NOT be complex"),
    ("Cho tôi biết quy định cho sinh viên nước ngoài", "simple", "Single-topic with 2x 'cho'"),
    ("Chọn môn tiên quyết cho khóa luận", "simple", "'chọ' contains 'cho' substring"),
    ("Cho biết lịch thi cho kỳ hè", "simple", "Single-topic timing question"),
    ("Cho em hỏi điều kiện tốt nghiệp và cho biết lịch đăng ký", "complex", "TRUE compound request — should be complex"),
    ("Cho tôi biết quy định học bổng, VÀ cho tôi biết cả thủ tục nộp", "complex", "TRUE compound request"),
    ("Cho em hỏi thời gian cho đăng ký tín chỉ", "simple", "Simple with 2x 'cho'"),
]

# --- BUG 2: Dead code L302 (cho + và) ---
# These should work correctly after Bug 1 is fixed
BUG2_TESTS = [
    ("Cho em biết quy định và cho em biết lịch thi", "complex", "Compound with 'và'"),
]

# --- BUG 3: Tier-3 prompt (LLM) — tested separately, not via regex ---

# --- BUG 4: fold_vietnamese inconsistency ---
BUG4_TESTS = [
    # These test that fold functions give same results
    ("Đại học Bách Khoa", None, "fold: Đ handling"),
    ("ĐHBK Hà Nội", None, "fold: Đ uppercase handling"),
]

# --- BUG 5: Major code regex incomplete in complexity_router ---
BUG5_TESTS = [
    ("So sánh chương trình ME-GU và ME-LUH", "complex", "ME prefix — should match comparison"),
    ("So sánh CH-E11 và BF-E3", "complex", "CH/BF prefix — should match comparison"),
    ("Khác nhau giữa IT-E6 và IT-E7", "complex", "IT prefix — already works"),
    ("So sánh EE-EP và EV-E1", "complex", "EE/EV prefix — should match"),
    ("Chương trình TE-E1 và TX-E1 khác gì?", "complex", "TE/TX prefix — should match"),
    ("So sánh ITE6 và ITE7", "complex", "No dash format — should match comparison"),
]

# --- BUG 6: Cohort range hardcoded K65-K70 in collection_selector ---
BUG6_TESTS_SIGNALS = [
    # These are tested via signals since collection_selector needs more setup
    ("Quy định ngoại ngữ K71", None, "K71 — should detect program context"),
    ("Quy định K65 về ngoại ngữ", None, "K65 — current range, should work"),
]

# --- BUG 7: Personal pattern too broad ---
BUG7_TESTS_SIGNALS = [
    ("Môn toán em nên học kỳ nào?", False, "Casual 'em' — should NOT trigger personal"),
    ("Ngành của em là CNTT", True, "Possessive 'cua em' — should trigger personal"),
    ("CPA của tôi đủ chưa?", True, "Possessive 'cua toi' — should trigger"),
    ("Em muốn hỏi về lịch thi", False, "Greeting 'em' — should NOT trigger"),
]

# --- BUG 8: table_lookup ky\d+ overmatch ---
BUG8_TESTS_SIGNALS = [
    ("Kỳ 1 bắt đầu khi nào?", False, "Timeline question — should NOT be table_lookup"),
    ("Bảng quy đổi điểm kỳ 1", True, "Table lookup — should be table_lookup"),
    ("Khung chương trình kỳ 1 ngành CNTT", True, "Curriculum frame — table_lookup ok"),
]

# --- General regression tests ---
REGRESSION_TESTS = [
    ("Xin chào!", "chitchat", "Basic greeting"),
    ("Cảm ơn bạn", "chitchat", "Thanks"),
    ("Tạm biệt", "chitchat", "Goodbye"),
    ("Điều kiện xét học bổng là gì?", "simple", "Simple policy question"),
    ("Lịch thi cuối kỳ khi nào?", "simple", "Simple schedule question"),
    ("So sánh IT-E6 và IT-E7", "complex", "Comparison"),
    ("Điều kiện TC tích lũy để làm đồ án và deadline đăng ký đề tài?", "simple", "Multi-part question but no explicit pattern"),
    ("Thời tiết hôm nay thế nào?", "simple", "Tool search (handled by QueryRouter, not ComplexityRouter)"),
    ("Quy chế đào tạo mới có gì thay đổi?", "simple", "Regulation question"),
    ("Sinh viên nước ngoài cần giấy tờ gì?", "simple", "Student support question"),
    ("Khi nào mở đăng ký môn học kỳ 1?", "simple", "Schedule question"),
    ("Đồ án tốt nghiệp ngành CNTT bao nhiêu tín chỉ?", "simple", "Curriculum question"),
    ("Môn nào có thể thay thế cho Giải tích 1?", "simple", "Equivalent course question"),
    ("Dạ cảm ơn bạn nhé", "simple", "Greeting with prefix — tricky"),
    ("Bao giờ?", "simple", "Short follow-up"),
    ("Nộp ở đâu?", "simple", "Short follow-up"),
    ("Học bổng?", "complex", "Ambiguous short query intentionally complex"),
    ("Lập trình hướng đối tượng có mấy lớp học kỳ 2?", "simple", "kehoach query"),
    ("Điều kiện nhận học bổng và nộp hồ sơ ở đâu?", "simple", "Multi-domain but single query"),
]


def run_complexity_tests(label: str, tests: list, router: ComplexityRouter) -> tuple[int, int]:
    """Run test cases and return (pass_count, total_count)."""
    print(f"\n{'='*70}")
    print(f"  {label}")
    print(f"{'='*70}")
    passed = 0
    total = len(tests)
    for query, expected, desc in tests:
        result = router.route(query)
        actual = result["tier"]
        ok = actual == expected
        status = "PASS" if ok else "FAIL"
        passed += int(ok)
        print(f"  {status} [{actual:>8}] {query[:55]:<55}")
        if not ok:
            print(f"       Expected: {expected}, Got: {actual}")
            print(f"       Reason: {result.get('reason', '')[:70]}")
        # Show extra info
        if result.get("complex_subtype"):
            print(f"       Subtype: {result['complex_subtype']}")
    print(f"\n  Result: {passed}/{total} passed")
    return passed, total


def run_signal_tests_personal(label: str, tests: list) -> tuple[int, int]:
    """Test personal_reference signal detection."""
    print(f"\n{'='*70}")
    print(f"  {label}")
    print(f"{'='*70}")
    passed = 0
    total = len(tests)
    for query, expected, desc in tests:
        signals = analyze_query_signals(query)
        actual = signals.personal_reference
        ok = actual == expected
        status = "PASS" if ok else "FAIL"
        passed += int(ok)
        print(f"  {status} personal={actual!s:5} | {query[:50]:<50} | {desc}")
        if not ok:
            print(f"       Expected personal_reference={expected}")
            print(f"       All signals: {_signals_fmt(signals)}")
    print(f"\n  Result: {passed}/{total} passed")
    return passed, total


def run_signal_tests_table(label: str, tests: list) -> tuple[int, int]:
    """Test table_lookup signal detection."""
    print(f"\n{'='*70}")
    print(f"  {label}")
    print(f"{'='*70}")
    passed = 0
    total = len(tests)
    for query, expected, desc in tests:
        signals = analyze_query_signals(query)
        actual = signals.table_lookup
        ok = actual == expected
        status = "PASS" if ok else "FAIL"
        passed += int(ok)
        print(f"  {status} table={actual!s:5} | {query[:50]:<50} | {desc}")
        if not ok:
            print(f"       Expected table_lookup={expected}")
            print(f"       All signals: {_signals_fmt(signals)}")
    print(f"\n  Result: {passed}/{total} passed")
    return passed, total


def run_fold_consistency_test():
    """Test fold_vietnamese_text consistency between signals.py and flows.py."""
    import unicodedata
    from query.signals import fold_vietnamese_text as fold_signals

    # Inline the flows.py version for comparison (flows.py L252-258)
    def fold_flows(text: str) -> str:
        decomposed = unicodedata.normalize("NFD", text or "")
        without_marks = "".join(
            ch for ch in decomposed if unicodedata.category(ch) != "Mn"
        )
        return without_marks.replace("đ", "d").replace("Đ", "d").lower()


    print(f"\n{'='*70}")
    print(f"  BUG 4: fold_vietnamese consistency")
    print(f"{'='*70}")
    
    test_strings = [
        "Đại học Bách Khoa",
        "ĐHBK Hà Nội",
        "Đồ án tốt nghiệp",
        "Điều kiện đăng ký",
        "đồ án ĐẠI HỌC",
    ]
    passed = 0
    total = len(test_strings)
    for s in test_strings:
        r1 = fold_signals(s)
        r2 = fold_flows(s)
        ok = r1 == r2
        status = "PASS" if ok else "FAIL"
        passed += int(ok)
        print(f"  {status} '{s}'")
        if not ok:
            print(f"       signals: '{r1}'")
            print(f"       flows:   '{r2}'")
    print(f"\n  Result: {passed}/{total} passed")
    return passed, total


def main():
    router = ComplexityRouter()
    total_passed = 0
    total_tests = 0

    # Bug 1: count("cho")
    p, t = run_complexity_tests("BUG 1: count('cho') >= 2 false positive", BUG1_TESTS, router)
    total_passed += p; total_tests += t

    # Bug 2: Dead code
    p, t = run_complexity_tests("BUG 2: Dead code (cho + và)", BUG2_TESTS, router)
    total_passed += p; total_tests += t

    # Bug 4: fold consistency
    p, t = run_fold_consistency_test()
    total_passed += p; total_tests += t

    # Bug 5: Major code regex
    p, t = run_complexity_tests("BUG 5: Major code regex incomplete", BUG5_TESTS, router)
    total_passed += p; total_tests += t

    # Bug 7: Personal pattern
    p, t = run_signal_tests_personal("BUG 7: Personal pattern too broad", BUG7_TESTS_SIGNALS)
    total_passed += p; total_tests += t

    # Bug 8: Table lookup overmatch
    p, t = run_signal_tests_table("BUG 8: table_lookup ky\\d+ overmatch", BUG8_TESTS_SIGNALS)
    total_passed += p; total_tests += t

    # Regression
    p, t = run_complexity_tests("REGRESSION: General routing tests", REGRESSION_TESTS, router)
    total_passed += p; total_tests += t

    print(f"\n{'='*70}")
    print(f"  TOTAL: {total_passed}/{total_tests} passed")
    print(f"{'='*70}")
    return 0 if total_passed == total_tests else 1


if __name__ == "__main__":
    sys.exit(main())
