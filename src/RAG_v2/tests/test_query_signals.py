"""Tests for reusable query signal detection."""

from __future__ import annotations

from query.signals import analyze_query_signals, extract_key_phrases


def test_personal_graduation_check_is_detected_with_suffix_pronoun() -> None:
    signals = analyze_query_signals("điều kiện tốt nghiệp của tôi")

    assert signals.personal_reference is True
    assert signals.eligibility_check is True
    assert signals.exact_policy_lookup is False


def test_accent_insensitive_policy_table_lookup() -> None:
    signals = analyze_query_signals("hien mau duoc bao nhieu diem ren luyen")

    assert signals.exact_policy_lookup is True
    assert signals.table_lookup is True
    assert signals.personal_reference is False


def test_broad_scholarship_words_do_not_imply_eligibility() -> None:
    signals = analyze_query_signals("hoc bong co duoc bao nhieu tien")

    assert signals.eligibility_check is False
    assert signals.exact_policy_lookup is True


def test_procedural_support_can_combine_with_exact_policy_lookup() -> None:
    signals = analyze_query_signals(
        "toi da tham gia hien mau nhung chua nhan duoc diem ren luyen"
    )

    assert signals.procedural_support is True
    assert signals.exact_policy_lookup is True
    assert signals.multi_domain is True


def test_extract_key_phrases_splits_at_stopwords() -> None:
    phrases = extract_key_phrases("hiến máu được bao nhiêu điểm rèn luyện")

    assert "hiến máu" in phrases
    assert "điểm rèn luyện" in phrases
    assert all("bao nhiêu" not in phrase for phrase in phrases)
