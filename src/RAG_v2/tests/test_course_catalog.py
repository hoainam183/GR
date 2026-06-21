from __future__ import annotations

from query import course_catalog
from query.course_catalog import lookup_course_code


def test_lookup_course_code_matches_huong_doi_tuong_alias_by_major() -> None:
    cases = {
        "IT-E6": ("IT3103", "5"),
        "IT1": ("IT3100", "3"),
        "IT-E15": ("IT3100E", "3"),
    }

    for major, (expected_code, expected_semester) in cases.items():
        match = lookup_course_code("môn hướng đối tượng được học vào kì mấy", major)

        assert match is not None
        assert match["code"] == expected_code
        assert match["semester"] == expected_semester
        assert match["name"] == "Lập trình hướng đối tượng"


def test_lookup_course_code_rejects_ambiguous_alias(monkeypatch) -> None:
    monkeypatch.setattr(
        course_catalog,
        "_CATALOG",
        {
            "TEST": [
                {
                    "code": "IT0001",
                    "name": "Lập trình hướng đối tượng",
                    "name_folded": "lap trinh huong doi tuong",
                    "semester": "1",
                    "credits": "3",
                },
                {
                    "code": "IT0002",
                    "name": "Lập trình hướng đối tượng",
                    "name_folded": "lap trinh huong doi tuong",
                    "semester": "2",
                    "credits": "3",
                },
            ]
        },
    )

    assert lookup_course_code("môn hướng đối tượng", "TEST") is None


def test_lookup_course_code_matches_student_language_alias() -> None:
    match = lookup_course_code("nhật 5 học vào kì mấy", "IT-E6")

    assert match is not None
    assert match["code"] == "JP2126"
    assert match["semester"] == "5"
    assert match["name"] == "Tiếng Nhật 5"
    assert match["matched_alias_folded"] == "nhat 5"


def test_lookup_course_code_matches_roman_number_variant() -> None:
    match = lookup_course_code("giải tích 2 học kỳ mấy", "ME2")

    assert match is not None
    assert match["code"] == "MI1121"
    assert match["name"] == "Giải tích II"
    assert match["matched_alias_folded"] == "giai tich 2"


def test_lookup_course_code_matches_student_abbreviations() -> None:
    cases = {
        "csdl học kỳ mấy": ("IT3292", "Cơ sở dữ liệu", "4"),
        "hđh học kỳ mấy": ("IT3070", "Nguyên lý hệ điều hành", "5"),
        "mmt học kỳ mấy": ("IT3080", "Mạng máy tính", "5"),
        "xstk học kỳ mấy": ("MI2021", "Xác suất thống kê", "4"),
        "triết học kỳ mấy": ("SSH1111", "Triết học Mác-Lênin", "3"),
        "tư tưởng hcm học kỳ mấy": ("SSH1151", "Tư tưởng Hồ Chí Minh", "7"),
        "pháp luật học kỳ mấy": ("EM1170", "Pháp luật đại cương", "6"),
    }

    for query, (expected_code, expected_name, expected_semester) in cases.items():
        match = lookup_course_code(query, "IT-E6")

        assert match is not None
        assert match["code"] == expected_code
        assert match["name"] == expected_name
        assert match["semester"] == expected_semester


def test_lookup_course_code_matches_toeic_alias() -> None:
    match = lookup_course_code("toeic 2 học kỳ mấy", "IT-E6")

    assert match is not None
    assert match["code"] == "FL1102"
    assert match["name"] == "Tiếng Anh TOEIC II"
    assert match["semester"] == "2"
    assert match["matched_alias_folded"] == "toeic 2"
