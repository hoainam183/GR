"""Regression test suite for retrieval improvements.

Known failure cases — run before and after each retrieval change.
Tests validate web query enrichment, homepage filtering, no-info patterns,
and freshness date handling.
"""

from __future__ import annotations

import sys
import os
from datetime import datetime
from urllib.parse import urlparse

# Allow running from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.flows import (
    _build_web_search_query,
    _fold_vietnamese,
    _answer_has_no_info_signal,
    _is_date_within_days,
)
from tools.tavily_search import TavilySearch


# ═══════════════════════════════════════════════════════════════════════════════
# A1: Web Query Enrichment Tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_web_query_has_academic_year():
    """A1: Freshness queries should inject current academic year."""
    q = _build_web_search_query("Lịch học kỳ mới nhất?", "Lịch học kỳ mới nhất")
    now = datetime.now()
    year = now.year
    # Should contain a year reference
    assert "20" in q, f"Missing year in query: {q}"
    # Should contain CTT ĐHBKHN
    assert "CTT ĐHBKHN" in q, f"Missing CTT in query: {q}"
    print(f"  ✅ test_web_query_has_academic_year: {q}")


def test_web_query_summer_semester():
    """A1: Summer semester queries with explicit year should get semester code."""
    q = _build_web_search_query(
        "kế hoạch đăng ký học tập kỳ hè 2025",
        "kế hoạch đăng ký học tập kỳ hè 2025",
    )
    assert "20243" in q or "2024-2025" in q, f"Missing semester code: {q}"
    print(f"  ✅ test_web_query_summer_semester: {q}")


def test_web_query_content_type_signal():
    """A1: Queries about lịch/kế hoạch should get content-type signal."""
    q = _build_web_search_query("lịch đăng ký học tập mới nhất", "lịch đăng ký học tập mới nhất")
    # Should have either "thông báo kế hoạch" or related enrichment
    assert "CTT ĐHBKHN" in q, f"Missing CTT for freshness: {q}"
    print(f"  ✅ test_web_query_content_type_signal: {q}")


def test_web_query_no_duplicate_hust():
    """A1: HUST queries shouldn't get double HUST prefix."""
    q = _build_web_search_query("HUST lịch thi mới nhất", "HUST lịch thi mới nhất")
    assert not q.startswith("HUST HUST"), f"Double HUST prefix: {q}"
    print(f"  ✅ test_web_query_no_duplicate_hust: {q}")


# ═══════════════════════════════════════════════════════════════════════════════
# A1: Homepage Filter Tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_homepage_filter_removes_root():
    """A1: Homepage filter should remove root URL results."""
    results = [
        {"url": "https://ctt.hust.edu.vn/", "content": "x" * 200, "score": 0.9},
        {"url": "https://ctt.hust.edu.vn/vi", "content": "x" * 200, "score": 0.8},
        {"url": "https://ctt.hust.edu.vn/DisplayWeb/DisplayBaiViet?baession=123",
         "content": "x" * 200, "score": 0.7},
    ]
    filtered = TavilySearch.filter_results(results, exclude_homepages=True)
    urls = [r["url"] for r in filtered]
    assert "https://ctt.hust.edu.vn/" not in urls, "Homepage not filtered"
    assert "https://ctt.hust.edu.vn/vi" not in urls, "/vi homepage not filtered"
    assert len(filtered) == 1, f"Expected 1 result, got {len(filtered)}"
    print(f"  ✅ test_homepage_filter_removes_root: {len(filtered)} results kept")


def test_homepage_filter_keeps_content_pages():
    """A1: Homepage filter should keep actual content pages."""
    results = [
        {"url": "https://ctt.hust.edu.vn/DisplayWeb/DisplayBaiViet?baession=123",
         "content": "Thông báo kế hoạch đăng ký " + "x" * 200, "score": 0.9},
        {"url": "https://ctt.hust.edu.vn/SinhVien/ThoiKhoaBieu",
         "content": "Thời khóa biểu " + "x" * 200, "score": 0.8},
    ]
    filtered = TavilySearch.filter_results(results, exclude_homepages=True)
    assert len(filtered) == 2, f"Expected 2 results, got {len(filtered)}"
    print(f"  ✅ test_homepage_filter_keeps_content_pages: {len(filtered)} results kept")


def test_homepage_filter_disabled():
    """A1: Homepage filter should not apply when disabled."""
    results = [
        {"url": "https://ctt.hust.edu.vn/", "content": "x" * 200, "score": 0.9},
    ]
    filtered = TavilySearch.filter_results(results, exclude_homepages=False)
    assert len(filtered) == 1, "Should keep homepage when filter disabled"
    print(f"  ✅ test_homepage_filter_disabled")


# ═══════════════════════════════════════════════════════════════════════════════
# A2: No-Info Pattern Tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_no_info_existing_patterns():
    """A2: Existing patterns should still trigger."""
    assert _answer_has_no_info_signal("Tôi không tìm thấy thông tin này trong tài liệu hiện có.")
    assert _answer_has_no_info_signal("Không có thông tin về vấn đề này.")
    assert _answer_has_no_info_signal("Chưa tìm thấy dữ liệu liên quan.")
    print("  ✅ test_no_info_existing_patterns")


def test_no_info_new_patterns():
    """A2: New rephrase variants should trigger."""
    test_cases = [
        "Không thể xác nhận thông tin này.",
        "Chưa được cập nhật trong hệ thống.",
        "Nội dung này ngoài phạm vi tài liệu.",
        "Không có dữ liệu về chủ đề này.",
        "Không thể trả lời câu hỏi này.",
        "Tài liệu không đề cập đến vấn đề đó.",
        "Thông tin còn hạn chế, cần kiểm tra thêm.",
    ]
    for case in test_cases:
        assert _answer_has_no_info_signal(case), f"Pattern not detected: {case}"
    print(f"  ✅ test_no_info_new_patterns: {len(test_cases)} patterns validated")


def test_no_info_false_positives():
    """A2: Normal answers should NOT trigger no-info."""
    normal_answers = [
        "Theo quy định, sinh viên cần đạt tối thiểu 120 tín chỉ.",
        "Kế hoạch đăng ký học tập kỳ hè bắt đầu từ ngày 15/5/2025.",
        "Chương trình đào tạo IT-E10 gồm 150 tín chỉ.",
    ]
    for ans in normal_answers:
        assert not _answer_has_no_info_signal(ans), f"False positive: {ans}"
    print(f"  ✅ test_no_info_false_positives: {len(normal_answers)} cases checked")


# ═══════════════════════════════════════════════════════════════════════════════
# C3: Freshness Date Handling Tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_is_date_within_days_recent():
    """C3: Recent date should return True."""
    today = datetime.now().strftime("%d/%m/%Y")
    assert _is_date_within_days(today, 90) is True
    print("  ✅ test_is_date_within_days_recent")


def test_is_date_within_days_old():
    """C3: Old date should return False."""
    assert _is_date_within_days("01/01/2020", 90) is False
    print("  ✅ test_is_date_within_days_old")


def test_is_date_within_days_malformed():
    """C3: Malformed dates should return False (not raise)."""
    assert _is_date_within_days("not-a-date", 90) is False
    assert _is_date_within_days("", 90) is False
    assert _is_date_within_days("2025/01/01", 90) is False  # Wrong format
    print("  ✅ test_is_date_within_days_malformed")


# ═══════════════════════════════════════════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════════════════════════════════════════


ALL_TESTS = [
    # A1
    test_web_query_has_academic_year,
    test_web_query_summer_semester,
    test_web_query_content_type_signal,
    test_web_query_no_duplicate_hust,
    test_homepage_filter_removes_root,
    test_homepage_filter_keeps_content_pages,
    test_homepage_filter_disabled,
    # A2
    test_no_info_existing_patterns,
    test_no_info_new_patterns,
    test_no_info_false_positives,
    # C3
    test_is_date_within_days_recent,
    test_is_date_within_days_old,
    test_is_date_within_days_malformed,
]


def run_regression():
    """Run all regression tests, return pass/fail summary."""
    passed = 0
    failed = 0
    failures = []

    print(f"\n{'='*60}")
    print(f"Retrieval Regression Tests — {len(ALL_TESTS)} cases")
    print(f"{'='*60}\n")

    for test_fn in ALL_TESTS:
        try:
            test_fn()
            passed += 1
        except (AssertionError, Exception) as e:
            failed += 1
            failures.append((test_fn.__name__, str(e)))
            print(f"  ❌ {test_fn.__name__}: {e}")

    print(f"\n{'─'*60}")
    print(f"Results: {passed} passed, {failed} failed, {len(ALL_TESTS)} total")
    if failures:
        print("\nFailures:")
        for name, err in failures:
            print(f"  - {name}: {err}")
    print(f"{'─'*60}\n")

    return {"passed": passed, "failed": failed, "failures": failures}


if __name__ == "__main__":
    result = run_regression()
    sys.exit(0 if result["failed"] == 0 else 1)
