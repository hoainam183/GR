"""Tests that exam-schedule phrases route to the agent, but calendar ones don't."""

from __future__ import annotations

import pytest

from query.complexity_router import ComplexityRouter


@pytest.fixture
def router() -> ComplexityRouter:
    return ComplexityRouter()


@pytest.mark.parametrize(
    "query",
    [
        "Phòng thi môn CH1012 ở đâu?",
        "Lịch thi học kỳ này thế nào",
        "Môn Hóa học 1 thi ngày nào",
        "kíp thi của IT3080",
        "ngày thi cuối kỳ",
    ],
)
def test_exam_phrases_route_complex(router, query) -> None:
    result = router.route(query)
    assert result["tier"] == "complex"
    assert result["complex_subtype"] == "general"
    assert result["reason"] == "signals: exam_schedule_lookup"


@pytest.mark.parametrize(
    "query",
    [
        "Lịch học của lớp tôi ra sao",
        "Lịch đăng ký học phần khi nào mở",
    ],
)
def test_calendar_phrases_are_not_exam(router, query) -> None:
    result = router.route(query)
    assert result["reason"] != "signals: exam_schedule_lookup"
