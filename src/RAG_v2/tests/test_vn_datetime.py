"""Unit tests for Vietnamese exam date/session normalisation."""

from __future__ import annotations

from datetime import datetime

from utils.vn_datetime import normalize_exam_date, normalize_session


def test_non_padded_dmy() -> None:
    dt, disp = normalize_exam_date("9/5/2026")
    assert dt == datetime(2026, 5, 9)
    assert disp == "09/05/2026"


def test_dash_format() -> None:
    dt, disp = normalize_exam_date("09-05-2026")
    assert dt == datetime(2026, 5, 9)
    assert disp == "09/05/2026"


def test_iso_format() -> None:
    dt, _ = normalize_exam_date("2026-05-09")
    assert dt == datetime(2026, 5, 9)


def test_two_digit_year_uses_pivot() -> None:
    dt, _ = normalize_exam_date("9/5/26", two_digit_year_pivot=2000)
    assert dt == datetime(2026, 5, 9)


def test_native_datetime_passthrough() -> None:
    dt, disp = normalize_exam_date(datetime(2026, 5, 9, 14, 30))
    assert dt == datetime(2026, 5, 9)  # time dropped
    assert disp == "09/05/2026"


def test_excel_serial_number() -> None:
    dt, _ = normalize_exam_date(46151)  # serial 46151 == 2026-05-09
    assert dt == datetime(2026, 5, 9)


def test_empty_and_garbage_return_none() -> None:
    assert normalize_exam_date(None) == (None, None)
    assert normalize_exam_date("") == (None, None)
    assert normalize_exam_date("không rõ") == (None, None)


def test_session_label_and_time_lookup() -> None:
    session, start = normalize_session("Kíp 1", kip_time_map={"Kíp 1": "07:00"})
    assert session == "Kíp 1"
    assert start == "07:00"


def test_session_time_lookup_by_number() -> None:
    session, start = normalize_session("Kíp 2", kip_time_map={"2": "09:30"})
    assert session == "Kíp 2"
    assert start == "09:30"


def test_session_without_map_has_no_time() -> None:
    session, start = normalize_session("Kíp 3")
    assert session == "Kíp 3"
    assert start is None


def test_session_empty() -> None:
    assert normalize_session("") == (None, None)
    assert normalize_session(None) == (None, None)
