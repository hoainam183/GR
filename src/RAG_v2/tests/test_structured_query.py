from __future__ import annotations

from query.structured_query import (
    build_es_must_not_clauses,
    parse_structured_query,
    text_contains_excluded_term,
)


def test_parse_structured_query_extracts_core_slots() -> None:
    sq = parse_structured_query("So sánh IT E6 và IT-E7 cho K70 về môn JP2111")

    assert sq.major_codes == ["IT-E6", "IT-E7"]
    assert sq.cohorts == ["K70"]
    assert sq.course_codes == ["JP2111"]


def test_parse_structured_query_extracts_no_diacritic_negation() -> None:
    sq = parse_structured_query("hoc phi NCS khong bao gom hoc phan bo sung")

    assert sq.exclude_terms == ["hoc phan bo sung"]


def test_parse_structured_query_extracts_vietnamese_negation() -> None:
    sq = parse_structured_query("môn tự chọn IT-E6 không bao gồm đồ án tốt nghiệp")

    assert sq.exclude_terms == ["do an tot nghiep"]


def test_text_contains_excluded_term_is_accent_insensitive() -> None:
    assert text_contains_excluded_term(
        "Học phần bổ sung dành cho nghiên cứu sinh",
        ["hoc phan bo sung"],
    )


def test_build_es_must_not_clauses_uses_phrase_matching() -> None:
    clauses = build_es_must_not_clauses(["do an tot nghiep"])

    assert clauses
    assert clauses[0]["multi_match"]["type"] == "phrase"
    assert clauses[0]["multi_match"]["query"] == "do an tot nghiep"
