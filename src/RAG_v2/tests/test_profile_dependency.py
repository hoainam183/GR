"""Truth-table tests for query.profile_dependency (DEPENDENCY vs SOURCE).

These encode the case table from the "điều kiện ngoại ngữ của tôi" bug report:
the decision to inject/filter by a profile attribute must follow the TOPIC
(does the answer depend on major/cohort?) and the SOURCE (target-in-query vs
authenticated profile) — NOT the presence of the pronoun "tôi"/"em".

Run:
    pytest tests/test_profile_dependency.py -v
"""

from __future__ import annotations

import pytest

from query.profile_dependency import (
    effective_major_for_retrieval,
    required_attributes,
    resolve_sources,
    should_inject_profile_note,
)


def _routing(domain: str):
    return {"domain": domain, "domains": [domain]}


# (label, query, domain, expected_required_set)
REQUIRED_CASES = [
    ("foreign-language → major", "điều kiện ngoại ngữ của tôi", "quydinh", {"major"}),
    # Case I from the report: foreign-language requirement → major (the language
    # rule matches before the graduation rule; report table lists this as major).
    ("TOEIC → major", "em cần TOEIC bao nhiêu để tốt nghiệp", "quydinh", {"major"}),
    ("tuition → major", "học phí của tôi là bao nhiêu", "quydinh", {"major"}),
    # Fee-waiver/scholarship procedure stays universal even though it contains
    # "học phí" — the scholarship rule is checked before the tuition rule.
    ("fee-waiver → none", "thủ tục miễn giảm học phí", "quydinh", set()),
    ("scholarship → none", "tôi muốn có học bổng thì phải làm thế nào", "quydinh", set()),
    ("training-reg → cohort", "quy chế đào tạo nào áp dụng cho tôi", "quydinh", {"cohort"}),
    ("graduation → major+cohort", "điều kiện tốt nghiệp của tôi", "quydinh", {"major", "cohort"}),
    ("curriculum domain → major", "ngành này học những môn gì", "ctdt", {"major"}),
    ("course registration → none", "thủ tục đăng ký học phần", "kehoach", set()),
    ("generic regulation → none", "quy trình bảo lưu kết quả học tập", "quydinh", set()),
]


@pytest.mark.parametrize("label,query,domain,expected", REQUIRED_CASES)
def test_required_attributes(label, query, domain, expected):
    assert required_attributes(query, query, _routing(domain)) == expected, label


def test_failing_case_injects_and_filters_by_user_major():
    """The original bug: 'điều kiện ngoại ngữ của tôi' for an IT-E6 student must
    inject the profile note AND scope retrieval to the user's major."""
    q = "điều kiện ngoại ngữ của tôi"
    r = _routing("quydinh")
    assert should_inject_profile_note(q, q, r, user_major="IT-E6") is True
    assert effective_major_for_retrieval(q, q, r, "IT-E6") == "IT-E6"


def test_scholarship_about_me_does_not_filter_by_major():
    """Case D: question is about the user but the answer is universal — must NOT
    inject the major nor filter retrieval by it."""
    q = "tôi muốn có học bổng thì phải làm thế nào"
    r = _routing("quydinh")
    assert should_inject_profile_note(q, q, r, user_major="IT-E6") is False
    assert effective_major_for_retrieval(q, q, r, "IT-E6") is None


def test_tuition_injects_and_filters_by_user_major():
    """Tuition differs by program (IT-E6 vs IT1), so 'học phí của tôi' must inject
    the profile note AND scope retrieval to the authenticated user's major."""
    q = "học phí của tôi là bao nhiêu"
    r = _routing("quydinh")
    assert required_attributes(q, q, r) == {"major"}
    assert should_inject_profile_note(q, q, r, user_major="IT1") is True
    assert effective_major_for_retrieval(q, q, r, "IT1") == "IT1"


def test_target_major_in_query_overrides_profile():
    """Case E/F: an explicit major named in the query is the target — use it, do
    NOT inject the asker's own profile major."""
    q = "ngành IT1 học những môn gì"
    r = _routing("ctdt")
    sources = resolve_sources({"major"}, user_major="IT-E6", target_major="IT1")
    assert sources["major"] == "target"
    assert should_inject_profile_note(q, q, r, user_major="IT-E6", target_major="IT1") is False
    # Retrieval scopes to the target, not the profile.
    assert effective_major_for_retrieval(q, q, r, "IT1") == "IT1"


def test_no_pronoun_still_requires_major():
    """Case G: keyword 'tôi' is absent but the foreign-language topic still
    depends on the major (the old keyword gate missed this)."""
    q = "điều kiện ngoại ngữ để tốt nghiệp"
    assert "major" in required_attributes(q, q, _routing("quydinh"))


def test_course_question_requires_major_without_routing_result():
    q = "môn hướng đối tượng được học vào kì mấy"
    assert required_attributes(q, q, None) == {"major"}
    assert effective_major_for_retrieval(q, q, None, "IT-E6") == "IT-E6"


def test_required_unknown_source_is_ask():
    """Required but neither target nor profile available → ask the user."""
    sources = resolve_sources({"major"}, user_major=None, target_major=None)
    assert sources["major"] == "ask"
    assert should_inject_profile_note("x", "x", _routing("ctdt"), user_major=None) is False
