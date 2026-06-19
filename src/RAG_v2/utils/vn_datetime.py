"""Vietnamese exam-schedule date & session normalisation helpers.

The HUST exam schedule stores dates in the "Ngày" column as non-zero-padded
``d/m/yyyy`` (e.g. ``9/5/2026``), occasionally as ``dd-mm-yyyy``, two-digit
years, ``datetime`` cells (openpyxl), or raw Excel serial numbers. Sessions live
in the "Kíp thi" column as ``Kíp 1`` … with no clock time; an optional map
supplies a display start time (the PDF banner also prints these — see
``services/exam_schedule_parser.parse_kip_time_map``).

All functions are pure and side-effect free.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

# Excel's day-zero is 1899-12-30 (the 1900 leap-year bug is baked into this base).
_EXCEL_EPOCH = datetime(1899, 12, 30)

_DEFAULT_DATE_FORMATS = ["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y"]
_TWO_DIGIT_YEAR_RE = re.compile(r"^\d{1,2}[/-]\d{1,2}[/-]\d{2}$")
_KIP_NUM_RE = re.compile(r"(\d+)")


def normalize_exam_date(
    raw: object,
    *,
    date_formats: list[str] | None = None,
    two_digit_year_pivot: int = 2000,
) -> tuple[datetime | None, str | None]:
    """Normalise a raw "Ngày" cell to ``(datetime|None, "DD/MM/YYYY"|None)``.

    Returns ``(None, None)`` when the value is empty or unparseable so the
    caller can flag the row as ``invalid_date``.
    """
    if raw is None:
        return None, None

    # openpyxl hands back native datetimes for date-typed cells.
    if isinstance(raw, datetime):
        return _result(raw)

    # Excel serial numbers (rare, but happens when a cell is number-typed).
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        try:
            return _result(_EXCEL_EPOCH + timedelta(days=float(raw)))
        except (OverflowError, ValueError):
            return None, None

    text = str(raw).strip().replace("\xa0", " ")
    if not text:
        return None, None

    formats = date_formats or _DEFAULT_DATE_FORMATS
    for fmt in formats:
        try:
            parsed = datetime.strptime(text, fmt)
        except ValueError:
            continue
        # strptime("%y") pivots at 1969/2068; apply the configured pivot instead
        # so two-digit years land in the intended century.
        if "%y" in fmt and _TWO_DIGIT_YEAR_RE.match(text):
            two_digit = parsed.year % 100
            parsed = parsed.replace(year=two_digit_year_pivot + two_digit)
        return _result(parsed)

    return None, None


def _result(dt: datetime) -> tuple[datetime, str]:
    """Drop the time component and produce the display string."""
    date_only = datetime(dt.year, dt.month, dt.day)
    return date_only, date_only.strftime("%d/%m/%Y")


def normalize_session(
    kip_raw: object,
    *,
    kip_time_map: dict[str, str] | None = None,
) -> tuple[str | None, str | None]:
    """Normalise a "Kíp thi" cell to ``(exam_session, start_time)``.

    ``exam_session`` is the cleaned label (e.g. ``"Kíp 1"``). ``start_time`` is
    looked up in ``kip_time_map`` by both the cleaned label and the bare number
    (so ``{"Kíp 1": "07:00"}`` and ``{"1": "07:00"}`` both work); ``None`` when
    no map entry matches.
    """
    if kip_raw is None:
        return None, None
    text = str(kip_raw).strip().replace("\xa0", " ")
    if not text:
        return None, None

    session = re.sub(r"\s+", " ", text)
    start_time: str | None = None
    if kip_time_map:
        if session in kip_time_map:
            start_time = kip_time_map[session]
        else:
            num_match = _KIP_NUM_RE.search(session)
            if num_match and num_match.group(1) in kip_time_map:
                start_time = kip_time_map[num_match.group(1)]
    return session, start_time
