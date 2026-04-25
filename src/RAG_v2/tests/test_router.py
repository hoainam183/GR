"""Tests for query complexity routing.

Run:
    pytest tests/test_router.py -v
"""

from __future__ import annotations

from agent.complexity_router import ComplexityRouter

router = ComplexityRouter()


class TestChitchat:
    def test_greeting(self) -> None:
        assert router.route("xin chào") == "chitchat"
        assert router.route("Hello bạn") == "chitchat"

    def test_thanks(self) -> None:
        assert router.route("cảm ơn bạn") == "chitchat"

    def test_ok(self) -> None:
        assert router.route("ok") == "chitchat"


class TestSimple:
    def test_policy_question(self) -> None:
        assert router.route("Điều kiện xét học bổng KKHT là gì?") == "simple"

    def test_course_question(self) -> None:
        assert router.route("Môn Toán cao cấp 1 có bao nhiêu tín chỉ?") == "simple"

    def test_schedule_question(self) -> None:
        assert router.route("Lịch thi học kỳ 1 khi nào?") == "simple"


class TestComplex:
    def test_cohort_comparison(self) -> None:
        assert router.route("So sánh học bổng giữa K65 và K70") == "complex"

    def test_two_cohorts_mentioned(self) -> None:
        assert (
            router.route("K65 và K70 có quy định học bổng khác nhau không?")
            == "complex"
        )

    def test_graduation_condition(self) -> None:
        assert router.route("Tôi đủ điều kiện tốt nghiệp chưa?") == "complex"

    def test_ambiguous_short(self) -> None:
        assert router.route("học bổng") == "complex"

    def test_long_query(self) -> None:
        long_q = (
            "Sinh viên khóa K70 ngành Khoa học Máy tính học theo chương trình đào tạo "
            "mới có cần đáp ứng thêm yêu cầu nào so với khóa K67 không?"
        )
        assert router.route(long_q) == "complex"

    def test_major_followup_compare_query(self) -> None:
        assert router.route("so sánh với IT-E7") == "complex"


class TestRealUseCases:
    """Additional real-world university questions (Week 3 checklist)."""

    def test_simple_single_cohort_rule_question(self) -> None:
        q = "Quy định học bổng KKHT áp dụng cho K70 là gì?"
        assert router.route(q) == "simple"

    def test_simple_course_credit_question(self) -> None:
        q = "Môn Xử lý tín hiệu số có mấy tín chỉ?"
        assert router.route(q) == "simple"

    def test_complex_compare_graduation_between_two_cohorts(self) -> None:
        q = "So sánh yêu cầu tốt nghiệp giữa K67 và K70 ngành CNTT"
        assert router.route(q) == "complex"

    def test_complex_two_cohorts_with_difference_keyword(self) -> None:
        q = "K66 và K70 khác nhau gì về điều kiện học bổng?"
        assert router.route(q) == "complex"

    def test_complex_multi_step_query(self) -> None:
        q = "Cho tôi biết quy định học bổng và cho biết thêm cách xét điểm rèn luyện"
        assert router.route(q) == "complex"
