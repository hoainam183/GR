"""Question set for Week 2 prompt-tuning checks."""

from __future__ import annotations


TUNE_QUESTIONS: list[tuple[str, str, str | None]] = [
    (
        "Điều kiện xét học bổng KKHT học kỳ này là gì?",
        "rag_search",
        "quy_dinh",
    ),
    (
        "K70 ngành CNTT phải học bao nhiêu tín chỉ để tốt nghiệp?",
        "rag_search",
        "chuong_trinh",
    ),
    (
        "Lịch thi học kỳ 1 năm học 2024-2025 khi nào?",
        "rag_search",
        "ke_hoach",
    ),
    (
        "So sánh điều kiện nhận học bổng KKHT giữa K65 và K70",
        "compare_cohorts",
        None,
    ),
    (
        "Tôi đã học đủ tín chỉ và không có môn F, tôi đủ điều kiện tốt nghiệp chưa?",
        "multi_rag_search",
        None,
    ),
    (
        "Có thông báo gì mới từ nhà trường không?",
        "rag_search",
        "thong_bao",
    ),
    (
        "Học bổng",
        "clarify_question",
        None,
    ),
    (
        "Môn Toán cao cấp 1 có mã môn là gì và có bao nhiêu tín chỉ?",
        "rag_search",
        "chuong_trinh",
    ),
    (
        "Quy định về số lần thi lại tối đa là bao nhiêu?",
        "rag_search",
        "quy_dinh",
    ),
    (
        "Chương trình đào tạo K70 và K68 khác nhau những gì?",
        "compare_cohorts",
        None,
    ),
]
