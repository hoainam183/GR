"""Unit tests for the exam ES index mapping + query builder (no live ES)."""

from __future__ import annotations

from retrieval.exam_schedule_store import (
    ExamScheduleESStore,
    build_exam_index_settings,
)


def test_mapping_field_types() -> None:
    props = build_exam_index_settings(use_vietnamese_plugin=True)["mappings"][
        "properties"
    ]
    assert props["exam_date"]["type"] == "date"
    assert props["subject_code"]["type"] == "keyword"
    assert props["subject_name"]["type"] == "text"
    assert props["subject_name"]["fields"]["keyword"]["type"] == "keyword"
    assert props["student_count"]["type"] == "integer"
    assert props["row_index"]["type"] == "integer"


def test_fallback_uses_standard_tokenizer() -> None:
    analyzer = "vietnamese_analyzer"
    plugin = build_exam_index_settings(use_vietnamese_plugin=True)
    fallback = build_exam_index_settings(use_vietnamese_plugin=False)
    assert (
        plugin["settings"]["analysis"]["analyzer"][analyzer]["tokenizer"]
        == "vi_tokenizer"
    )
    assert (
        fallback["settings"]["analysis"]["analyzer"][analyzer]["tokenizer"]
        == "standard"
    )


def test_build_query_subject_code_only() -> None:
    q = ExamScheduleESStore.build_query(subject_code="ch1012")
    assert q["bool"]["filter"] == [{"term": {"subject_code": "CH1012"}}]
    assert "must" not in q["bool"]


def test_build_query_name_only_uses_match() -> None:
    q = ExamScheduleESStore.build_query(subject_name="Hóa học 1")
    assert "filter" not in q["bool"]
    mm = q["bool"]["must"][0]["multi_match"]
    assert mm["query"] == "Hóa học 1"
    assert "subject_name^2" in mm["fields"]


def test_build_query_date_only_is_range() -> None:
    q = ExamScheduleESStore.build_query(exam_date="2026-05-09")
    assert q["bool"]["filter"] == [
        {"range": {"exam_date": {"gte": "2026-05-09", "lte": "2026-05-09"}}}
    ]


def test_build_query_combined() -> None:
    q = ExamScheduleESStore.build_query(
        subject_name="Hóa", exam_date="2026-05-09", exam_room="D3-201"
    )
    assert "must" in q["bool"]
    assert any("range" in c for c in q["bool"]["filter"])
    assert any("exam_room" in c.get("term", {}) for c in q["bool"]["filter"])


def test_build_query_empty_is_match_all() -> None:
    assert ExamScheduleESStore.build_query() == {"match_all": {}}
