"""Unit tests for the exam_schedule_search agent tool."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from agent import tool_adapters
from agent.tool_adapters import (
    _AdapterRuntime,
    _extract_exam_filters,
    _format_exam_results,
    get_agent_docs,
    init_agent_docs,
    set_runtime,
)

_ROW = {
    "subject_code": "CH1012",
    "subject_name": "Hóa học 1",
    "weekday": "Thứ bảy",
    "exam_date_str": "09/05/2026",
    "exam_session": "Kíp 1",
    "start_time": "07:00",
    "exam_room": "D3-201",
    "group": "02,04-K70C",
    "exam_batch": "AB",
}


def _runtime(store) -> _AdapterRuntime:
    return _AdapterRuntime(
        settings=SimpleNamespace(exam_schedule_search_top_k=20),
        bge_embedder=None,
        e5_embedder=None,
        searcher=None,
        reranker=None,
        tavily_tool=None,
        exam_es_store=store,
    )


@pytest.fixture(autouse=True)
def _reset_runtime():
    init_agent_docs()
    yield
    set_runtime(None)


def test_extract_subject_code() -> None:
    filters = _extract_exam_filters("Phòng thi môn CH1012 ở đâu?")
    assert filters["subject_code"] == "CH1012"
    assert "subject_name" not in filters


def test_extract_date_to_iso() -> None:
    filters = _extract_exam_filters("Lịch thi ngày 9/5/2026 có môn nào?")
    assert "subject_code" not in filters
    assert filters["exam_date"] == "2026-05-09"
    assert filters["subject_name"]


def test_search_passes_extracted_code() -> None:
    store = MagicMock()
    store.search.return_value = [_ROW]
    set_runtime(_runtime(store))

    out = tool_adapters._exam_schedule_search(query="phòng thi CH1012")
    assert isinstance(out, str)
    assert "CH1012" in out and "D3-201" in out
    assert store.search.call_args.kwargs["subject_code"] == "CH1012"


def test_exam_schedule_rows_do_not_become_retrieved_sources() -> None:
    store = MagicMock()
    store.search.return_value = [_ROW]
    set_runtime(_runtime(store))

    out = tool_adapters._exam_schedule_search(query="phòng thi CH1012")
    assert "CH1012" in out
    assert "D3-201" in out
    assert "Kíp 1" in out
    assert get_agent_docs() == []


def test_explicit_date_filter_is_normalised() -> None:
    store = MagicMock()
    store.search.return_value = []
    set_runtime(_runtime(store))

    tool_adapters._exam_schedule_search(query="", exam_date="9/5/2026")
    assert store.search.call_args.kwargs["exam_date"] == "2026-05-09"


def test_empty_results_message() -> None:
    store = MagicMock()
    store.search.return_value = []
    set_runtime(_runtime(store))
    out = tool_adapters._exam_schedule_search(query="phòng thi CH9999")
    assert out == "[Khong tim thay lich thi phu hop]"


def test_store_unavailable_guard() -> None:
    set_runtime(_runtime(None))
    out = tool_adapters._exam_schedule_search(query="phòng thi CH1012")
    assert "chua san sang" in out


def test_no_identifiable_filters() -> None:
    store = MagicMock()
    set_runtime(_runtime(store))
    out = tool_adapters._exam_schedule_search(query="   ")
    assert out.startswith("[Loi")
    store.search.assert_not_called()


def test_format_exam_results_layout() -> None:
    line = _format_exam_results([_ROW])
    assert line.startswith("[1] CH1012 — Hóa học 1")
    assert "Phòng D3-201" in line
    assert "Kíp 1 (07:00)" in line
    assert "Đợt AB" in line


def test_format_exam_results_empty() -> None:
    assert _format_exam_results([]) == "[Khong tim thay lich thi phu hop]"
