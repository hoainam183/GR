"""Tests for query complexity routing.

Run:
    pytest tests/test_router.py -v
"""

from __future__ import annotations

from query.complexity_router import ComplexityRouter

router = ComplexityRouter()


class TestChitchat:
    def test_greeting(self) -> None:
        assert router.route_tier("xin chào") == "chitchat"
        assert router.route_tier("Hello bạn") == "chitchat"

    def test_thanks(self) -> None:
        assert router.route_tier("cảm ơn bạn") == "chitchat"

    def test_ok(self) -> None:
        assert router.route_tier("ok") == "chitchat"


class TestSimple:
    def test_policy_question(self) -> None:
        assert router.route_tier("Điều kiện xét học bổng KKHT là gì?") == "simple"

    def test_course_question(self) -> None:
        assert router.route_tier("Môn Toán cao cấp 1 có bao nhiêu tín chỉ?") == "simple"

    def test_schedule_question(self) -> None:
        assert router.route_tier("Lịch thi học kỳ 1 khi nào?") == "simple"


    def test_general_graduation_conditions_stays_simple(self) -> None:
        result = router.route("điều kiện tốt nghiệp bao gồm những gì")
        assert result["tier"] == "simple"
        assert result["query_signals"]["eligibility_check"] is True

    def test_exact_policy_lookup_stays_simple_with_signals(self) -> None:
        result = router.route("hiến máu được bao nhiêu điểm rèn luyện")
        assert result["tier"] == "simple"
        assert result["query_signals"]["exact_policy_lookup"] is True
        assert result["query_signals"]["table_lookup"] is True


    def test_registration_count_lookup_stays_simple(self) -> None:
        result = router.route("Sinh vien co the dang ky dieu chinh bao nhieu lan?")
        assert result["tier"] == "simple"
        assert result["reason"] == "signals: single_fact_policy_lookup"


class TestComplex:
    def test_cohort_comparison(self) -> None:
        assert router.route_tier("So sánh học bổng giữa K65 và K70") == "complex"

    def test_two_cohorts_mentioned(self) -> None:
        assert (
            router.route_tier("K65 và K70 có quy định học bổng khác nhau không?")
            == "complex"
        )

    def test_graduation_condition(self) -> None:
        assert router.route_tier("Tôi đủ điều kiện tốt nghiệp chưa?") == "complex"

    def test_ambiguous_short(self) -> None:
        assert router.route_tier("học bổng") == "complex"

    def test_long_query(self) -> None:
        long_q = (
            "Sinh viên khóa K70 ngành Khoa học Máy tính học theo chương trình đào tạo "
            "mới có cần đáp ứng thêm yêu cầu nào so với khóa K67 không?"
        )
        assert router.route_tier(long_q) == "complex"

    def test_major_followup_compare_query(self) -> None:
        assert router.route_tier("so sánh với IT-E7") == "complex"


    def test_personal_graduation_check_suffix_pronoun_routes_multi_source(self) -> None:
        result = router.route("điều kiện tốt nghiệp của tôi")
        assert result["tier"] == "complex"
        assert result["complex_subtype"] == "multi_source"

    def test_graduation_program_rule_is_multi_source(self) -> None:
        result = router.route("điều kiện tốt nghiệp ngành IT-E6 theo chương trình đào tạo")
        assert result["tier"] == "complex"
        assert result["complex_subtype"] == "multi_source"


class TestRealUseCases:
    """Additional real-world university questions (Week 3 checklist)."""

    def test_simple_single_cohort_rule_question(self) -> None:
        q = "Quy định học bổng KKHT áp dụng cho K70 là gì?"
        assert router.route_tier(q) == "simple"

    def test_simple_course_credit_question(self) -> None:
        q = "Môn Xử lý tín hiệu số có mấy tín chỉ?"
        assert router.route_tier(q) == "simple"

    def test_complex_compare_graduation_between_two_cohorts(self) -> None:
        q = "So sánh yêu cầu tốt nghiệp giữa K67 và K70 ngành CNTT"
        assert router.route_tier(q) == "complex"

    def test_complex_two_cohorts_with_difference_keyword(self) -> None:
        q = "K66 và K70 khác nhau gì về điều kiện học bổng?"
        assert router.route_tier(q) == "complex"

    def test_complex_multi_step_query(self) -> None:
        q = "Cho tôi biết quy định học bổng và cho biết thêm cách xét điểm rèn luyện"
        assert router.route_tier(q) == "complex"


class TestRouteDict:
    """Test that route() returns structured dict with confidence."""

    def test_route_returns_dict(self) -> None:
        result = router.route("So sánh K65 và K70")
        assert isinstance(result, dict)
        assert result["tier"] == "complex"
        assert result["confidence"] in ("high", "medium")
        assert "reason" in result

    def test_simple_route_confidence(self) -> None:
        result = router.route("Lịch thi học kỳ 1 khi nào?")
        assert result["tier"] == "simple"
        assert result["confidence"] == "high"

