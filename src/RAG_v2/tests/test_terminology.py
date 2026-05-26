from __future__ import annotations


def test_expand_full_term_adds_abbreviation() -> None:
    from utils.terminology import expand_academic_abbreviations

    expanded = expand_academic_abbreviations(
        "Nghiên cứu sinh cần báo cáo tiến độ học tập."
    )

    assert "nghiên cứu sinh" in expanded.lower()
    assert "NCS" in expanded


def test_expand_abbreviation_adds_full_term() -> None:
    from utils.terminology import expand_academic_abbreviations

    expanded = expand_academic_abbreviations("NCS phải nộp báo cáo định kỳ.")

    assert "NCS" in expanded
    assert "nghiên cứu sinh" in expanded


def test_expansion_is_idempotent() -> None:
    from utils.terminology import expand_academic_abbreviations

    query = "nghiên cứu sinh (NCS) cần báo cáo tiến độ"

    assert expand_academic_abbreviations(expand_academic_abbreviations(query)) == query


def test_unrelated_text_is_unchanged() -> None:
    from utils.terminology import expand_academic_abbreviations

    query = "lịch đăng ký học phần mới nhất"

    assert expand_academic_abbreviations(query) == query


def test_rag_and_self_eval_prompts_include_glossary() -> None:
    from llm.prompts import RAG_SYSTEM_PROMPT, SELF_EVAL_SYSTEM_PROMPT

    assert "NCS = nghiên cứu sinh" in RAG_SYSTEM_PROMPT
    assert "NCS = nghiên cứu sinh" in SELF_EVAL_SYSTEM_PROMPT
    assert "tài liệu tham khảo" in RAG_SYSTEM_PROMPT
    assert "không coi đây là nguồn dữ kiện độc lập" in SELF_EVAL_SYSTEM_PROMPT
