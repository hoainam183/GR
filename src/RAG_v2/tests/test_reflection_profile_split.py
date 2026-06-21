"""Tests for the user-vs-target major split in query.reflection._extract_entities.

BUG-3·R1: the authenticated profile major must be immutable — a conversational
"em học Cơ điện tử" must NOT overwrite the user's real major. The query target
major (e.g. "ngành IT-E7") is tracked separately so target questions still work.

Run:
    pytest tests/test_reflection_profile_split.py -v
"""

from __future__ import annotations

from query.reflection import _extract_entities, _strip_pii_and_noise

AUTH = {"major_code": "IT-E6", "major": "Công nghệ thông tin Việt - Nhật", "cohort": "65"}


# ── PII strip must not destroy self-declared academic profile ────────────────
# Regression for: "tôi là sinh viên ngành IT1, học phí của tôi là bao nhiêu"
# was wrongly stripped to "1, học phí của" because _PERSONAL_INTRO_RE (compiled
# with re.IGNORECASE) treated the lowercase "sinh viên ngành IT" as a name.


def test_strip_preserves_self_declared_major():
    q = "tôi là sinh viên ngành IT1, học phí của tôi là bao nhiêu"
    cleaned = _strip_pii_and_noise(q)
    assert "IT1" in cleaned
    assert "ngành" in cleaned
    # The major survives the strip and is extracted as the query target.
    ents = _extract_entities(cleaned)
    assert ents["major_code"] == "IT1"


def test_strip_still_removes_genuine_name_intro():
    q = "Tôi là Phạm Nhật Anh, cho em hỏi học phí ngành IT1"
    cleaned = _strip_pii_and_noise(q)
    assert "Phạm Nhật Anh" not in cleaned
    assert "học phí" in cleaned
    assert "IT1" in cleaned


def test_strip_leaves_general_pronoun_query_untouched():
    q = "nếu tôi không nộp học phí thì sao"
    assert _strip_pii_and_noise(q) == q


def test_user_major_from_auth_only():
    ents = _extract_entities("điều kiện ngoại ngữ của tôi", user_context=AUTH)
    assert ents["user_major_code"] == "IT-E6"
    assert ents["target_major_code"] is None
    # back-compat resolved value falls through to the profile
    assert ents["major_code"] == "IT-E6"


def test_history_does_not_override_user_major():
    """A stray major stated in chat history must not replace the auth profile."""
    history = [{"role": "user", "content": "em học ngành ME1 Cơ điện tử"}]
    ents = _extract_entities(
        "điều kiện ngoại ngữ của tôi", user_context=AUTH, history=history
    )
    assert ents["user_major_code"] == "IT-E6"  # immutable, from auth


def test_explicit_query_major_is_target_not_user():
    """An explicit major in the current query is the target; the user's own major
    (from auth) is preserved separately."""
    ents = _extract_entities("ngành IT-E7 học môn gì", user_context=AUTH)
    assert ents["target_major_code"] == "IT-E7"
    assert ents["user_major_code"] == "IT-E6"
    # back-compat: query target still wins for the legacy major_code field
    assert ents["major_code"] == "IT-E7"


def test_anonymous_user_has_no_user_major():
    ents = _extract_entities("ngành IT-E7 học môn gì", user_context=None)
    assert ents["user_major_code"] is None
    assert ents["target_major_code"] == "IT-E7"
