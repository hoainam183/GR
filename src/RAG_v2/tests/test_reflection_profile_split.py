"""Tests for the user-vs-target major split in query.reflection._extract_entities.

BUG-3·R1: the authenticated profile major must be immutable — a conversational
"em học Cơ điện tử" must NOT overwrite the user's real major. The query target
major (e.g. "ngành IT-E7") is tracked separately so target questions still work.

Run:
    pytest tests/test_reflection_profile_split.py -v
"""

from __future__ import annotations

from query.reflection import _extract_entities

AUTH = {"major_code": "IT-E6", "major": "Công nghệ thông tin Việt - Nhật", "cohort": "65"}


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
