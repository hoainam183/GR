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
