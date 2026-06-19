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

    def test_exam_schedule_question_routes_to_agent(self) -> None:
        # "lịch thi" is now an exam-schedule signal: it routes to the
        # Planner-Executor (complex/general) so the planner can emit a
        # structured lich_thi step, rather than the generic ke_hoach RAG path.
        result = router.route("Lịch thi học kỳ 1 khi nào?")
        assert result["tier"] == "complex"
        assert result["reason"] == "signals: exam_schedule_lookup"


    def test_general_graduation_question_defers_to_ml_tiers(self) -> None:
        # Tier-0 no longer hard-codes a graduation gate (it had to enumerate
        # program tokens). It now returns "unknown" so the pipeline's ML
        # multi-label classifier + LLM judge decide. The eligibility signal is
        # still surfaced for downstream use.
        result = router.route("điều kiện tốt nghiệp bao gồm những gì")
        assert result["tier"] == "unknown"
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

    def test_graduation_program_rule_defers_to_ml_tiers(self) -> None:
        # Previously a regex gate forced complex/multi_source here, but it had to
        # enumerate program tokens — so a bare major code like "IT1" slipped
        # through. Tier-0 now defers ("unknown"); the multi_source decision is
        # made by RAGPipeline._decide_complexity (see test_complexity_tiers.py).
        result = router.route(
            "điều kiện tốt nghiệp ngành IT-E6 theo chương trình đào tạo"
        )
        assert result["tier"] == "unknown"


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


class TestMayMachineVsHowMany:
    """Regression: "máy" (machine) must not be read as "mấy" (how many).

    The major-name expansion adds "Khoa học Máy tính"; after accent folding
    "máy" → "may" used to trip the single-fact lookup gate and short-circuit a
    graduation query to ``simple`` before the ML/LLM tiers could see it.
    """

    def test_machine_name_does_not_trigger_single_fact(self) -> None:
        result = router.route(
            "điều kiện tốt nghiệp của IT1 (CNTT: Khoa học Máy tính)"
        )
        assert result["query_signals"]["exact_policy_lookup"] is False
        assert result["tier"] == "unknown"  # defers to ML/LLM tiers

    def test_how_many_with_diacritics_still_detected(self) -> None:
        result = router.route("Môn Xử lý tín hiệu số có mấy tín chỉ?")
        assert result["query_signals"]["exact_policy_lookup"] is True
        assert result["tier"] == "simple"

    def test_how_many_without_diacritics_still_detected(self) -> None:
        # Mobile input without diacritics: "may" == "mấy" (no "máy" present).
        result = router.route("tot nghiep can may tin chi")
        assert result["query_signals"]["exact_policy_lookup"] is True

    def test_machine_and_how_many_together_detected(self) -> None:
        result = router.route("máy tính có mấy loại")
        assert result["query_signals"]["exact_policy_lookup"] is True


class TestRouteDict:
    """Test that route() returns structured dict with confidence."""

    def test_route_returns_dict(self) -> None:
        result = router.route("So sánh K65 và K70")
        assert isinstance(result, dict)
        assert result["tier"] == "complex"
        assert result["confidence"] in ("high", "medium")
        assert "reason" in result

    def test_simple_route_confidence(self) -> None:
        # A decisive single-fact lookup is classified at Tier-0 (no ML/LLM need).
        result = router.route("Môn Xử lý tín hiệu số có mấy tín chỉ?")
        assert result["tier"] == "simple"
        assert result["confidence"] == "high"

    def test_undecided_query_returns_unknown_tier(self) -> None:
        # Queries with no decisive Tier-0 signal defer to the ML/LLM tiers.
        # (Avoids exam-schedule wording, which now has its own Tier-0 signal.)
        query = "Thông tin về ký túc xá như thế nào?"
        result = router.route(query)
        assert result["tier"] == "unknown"
        # route_tier() collapses "unknown" → "simple" for backward compatibility.
        assert router.route_tier(query) == "simple"

