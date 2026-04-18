"""Unit tests for major-name middleware used by metadata filters."""

from retrieval.metadata_filters import (
    _resolve_major_code,
    canonicalize_major_name,
    strip_major_from_query_for_retrieval,
)


def test_canonicalize_major_name_match_alias_case_insensitive() -> None:
    """Alias from profile should resolve to canonical major name."""
    assert (
        canonicalize_major_name("cntt việt nhật")
        == "Công nghệ thông tin Việt - Nhật"
    )


def test_canonicalize_major_name_no_match_returns_original_input() -> None:
    """Unknown majors should pass through unchanged."""
    user_major = "Kỹ thuật hàng không"
    assert canonicalize_major_name(user_major) == user_major


def test_strip_major_phrase_from_query_with_code() -> None:
    """Major mentions should be stripped when metadata filter is available."""
    query = "môn mạng máy tính trong ngành IT-E6"
    assert (
        strip_major_from_query_for_retrieval(query, resolved_major="IT-E6")
        == "môn mạng máy tính"
    )


def test_strip_major_phrase_from_query_with_name_and_code() -> None:
    """Both major name and code fragments should be removed from retrieval query."""
    query = (
        "môn mạng máy tính trong ngành Công nghệ thông tin Việt - Nhật (IT-E6)"
    )
    assert (
        strip_major_from_query_for_retrieval(query, resolved_major="IT-E6")
        == "môn mạng máy tính"
    )


def test_strip_major_keeps_original_when_query_too_short() -> None:
    """Safety fallback: do not return a nearly-empty query after stripping."""
    query = "ngành IT-E6"
    assert (
        strip_major_from_query_for_retrieval(query, resolved_major="IT-E6")
        == "ngành IT-E6"
    )


def test_resolve_major_code_accepts_unicode_dash_and_space_variants() -> None:
    """Major code extraction should handle common dash/spacing variants."""
    assert _resolve_major_code("môn lập trình mạng của ngành IT–E6", None) == "IT-E6"
    assert _resolve_major_code("môn lập trình mạng", "IT – E6") == "IT-E6"
    assert _resolve_major_code("môn lập trình mạng", "IT E6") == "IT-E6"


def test_strip_major_phrase_from_query_with_unicode_dash_code() -> None:
    """Unicode dash in major code should still be stripped from retrieval query."""
    query = "môn mạng máy tính trong ngành IT–E6"
    assert strip_major_from_query_for_retrieval(query) == "môn mạng máy tính"
