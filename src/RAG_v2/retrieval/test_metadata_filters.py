"""Unit tests for major-name middleware used by metadata filters."""

from retrieval.metadata_filters import (
    MAJOR_CODE_TO_NAME,
    _extract_major_code,
    _resolve_major_code,
    build_collection_filters,
    build_major_comparison_subqueries_for_retrieval,
    build_cohort_comparison_subqueries_for_retrieval,
    canonicalize_major_name,
    extract_major_codes,
    extract_cohort_codes,
    strip_major_from_query_for_retrieval,
    strip_major_comparison_scaffold_for_retrieval,
    strip_cohort_comparison_scaffold_for_retrieval,
    QuyDinhFilterExtractor,
)


def _extract_term_values(node: object) -> set[str]:
    """Collect all term values from a nested ES query object."""
    out: set[str] = set()
    if isinstance(node, dict):
        term_clause = node.get("term")
        if isinstance(term_clause, dict):
            for value in term_clause.values():
                out.add(str(value))
        for value in node.values():
            out.update(_extract_term_values(value))
    elif isinstance(node, list):
        for item in node:
            out.update(_extract_term_values(item))
    return out


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


def test_extract_cohort_codes_dedups_and_normalises_mentions() -> None:
    """Cohort extractor should return unique Kxx codes in mention order."""
    query = "so sánh K70 với khóa 67 và k70"
    assert extract_cohort_codes(query) == ["K70", "K67"]


def test_extract_major_codes_dedups_and_preserves_order() -> None:
    """Major extractor should keep first mention order and remove duplicates."""
    query = "so sánh IT-E7 với IT E6 và IT-E7"
    assert extract_major_codes(query) == ["IT-E7", "IT-E6"]


def test_extract_major_code_supports_all_indexed_ctdt_codes() -> None:
    """Every indexed CTDT major code should be recognised explicitly."""
    expected_codes = list(MAJOR_CODE_TO_NAME)
    query = ", ".join(expected_codes)

    assert extract_major_codes(query) == expected_codes
    for code in expected_codes:
        assert _resolve_major_code(code, None) == code


def test_resolve_major_code_preserves_direct_code_for_duplicate_names() -> None:
    """Direct codes should not be remapped through duplicate canonical names."""
    assert _resolve_major_code("generic", "EE2") == "EE2"
    assert _resolve_major_code("generic", "EE-E8") == "EE-E8"
    assert _resolve_major_code("generic", "BF2") == "BF2"
    assert _resolve_major_code("generic", "BF-E12") == "BF-E12"

    duplicate_name = MAJOR_CODE_TO_NAME["EE2"]
    assert duplicate_name == MAJOR_CODE_TO_NAME["EE-E8"]
    assert _resolve_major_code("generic", duplicate_name) == "EE2"


def test_extract_major_code_supports_new_dash_and_space_variants() -> None:
    """New major families should support compact, spaced, and dash variants."""
    cases = {
        "ME-GU học ngoại ngữ chính là gì": "ME-GU",
        "chương trình ME GU": "ME-GU",
        "ME–LUH có bao nhiêu tín chỉ": "ME-LUH",
        "MENUT học ở đâu": "ME-NUT",
        "EEE18 là ngành gì": "EE-E18",
        "BF E12 chương trình tiên tiến": "BF-E12",
        "CHE11 học gì": "CH-E11",
        "MSE3 có bao nhiêu tín chỉ": "MS-E3",
        "TROY IT là chương trình nào": "TROY-IT",
        "TE EP cơ khí hàng không": "TE-EP",
        "HE1 kỹ thuật nhiệt": "HE1",
        "TX1 công nghệ dệt may": "TX1",
    }
    for query, expected_code in cases.items():
        assert _resolve_major_code(query, None) == expected_code


def test_extract_major_code_avoids_common_false_positives() -> None:
    """Short prefixes and Vietnamese words should not become major codes."""
    assert _extract_major_code("ai là người phụ trách học bổng") is None
    assert _extract_major_code("meeting về lịch đăng ký") is None
    assert _extract_major_code("message của phòng đào tạo") is None
    assert _extract_major_code("he asked about scholarship") is None


def test_quydinh_filter_extractor_matches_applicable_major_array_values() -> None:
    """QuyDinh filter should use cohort Kxx term queries for applicable_major arrays."""
    extractor = QuyDinhFilterExtractor()
    cf = extractor.extract("quy định ngoại ngữ của K70")

    assert len(cf.metadata_es_queries) == 1
    query = cf.metadata_es_queries[0]
    assert query["bool"]["minimum_should_match"] == 1
    strict_values = _extract_term_values(query)
    assert "K70" in strict_values
    assert any("must_not" in clause.get("bool", {}) for clause in query["bool"]["should"])


def test_quydinh_filter_extractor_supports_multi_cohort_query() -> None:
    """When query mentions many cohorts, strict filter should OR all cohorts."""
    extractor = QuyDinhFilterExtractor()
    cf = extractor.extract("so sánh quy định ngoại ngữ của K70 và K67")

    strict = cf.metadata_es_queries[0]
    strict_values = _extract_term_values(strict)
    assert {"K70", "K67"}.issubset(strict_values)


def test_quydinh_filter_explicit_cohort_overrides_profile_cohort_hint() -> None:
    """Explicit Kxx in query must take priority over resolved_cohort hint."""
    extractor = QuyDinhFilterExtractor()
    cf = extractor.extract(
        "quy định ngoại ngữ của K70",
        resolved_cohort="67",
    )

    query = cf.metadata_es_queries[0]
    values = _extract_term_values(query)
    assert "K70" in values
    assert "K67" not in values


def test_quydinh_filter_extractor_uses_resolved_cohort_for_generic_query() -> None:
    """Generic quydinh query should still get cohort filter from user/profile context."""
    extractor = QuyDinhFilterExtractor()
    cf = extractor.extract("quy định về ngoại ngữ", resolved_cohort="70")

    strict = cf.metadata_es_queries[0]
    strict_values = _extract_term_values(strict)
    assert "K70" in strict_values


def test_build_collection_filters_passes_resolved_cohort_to_quydinh() -> None:
    """End-to-end builder should apply cohort-derived quydinh pre-filters."""
    filters = build_collection_filters(
        query="quy định học bổng",
        collections=["quydinh"],
        resolved_cohort="K67",
    )
    assert filters["quydinh"].is_empty is False


def test_strip_cohort_comparison_scaffold_keeps_topic_only() -> None:
    """Comparison scaffolding should be removed to keep topic-focused retrieval."""
    query = "so sánh quy định về ngoại ngữ của K70 và K67"
    assert strip_cohort_comparison_scaffold_for_retrieval(query) == "quy định về ngoại ngữ"


def test_strip_major_comparison_scaffold_keeps_topic_only() -> None:
    """Major-comparison scaffolding should be removed for topic rerank query."""
    query = "môn lập trình mạng của ngành IT-E7 và IT-E6 có gì khác nhau"
    assert strip_major_comparison_scaffold_for_retrieval(query) == "môn lập trình mạng"


def test_build_cohort_comparison_subqueries_for_retrieval() -> None:
    """Comparison query should be decomposed into one retrieval query per cohort."""
    query = "so sánh quy định về ngoại ngữ của K70 và K67"
    assert build_cohort_comparison_subqueries_for_retrieval(query) == [
        "quy định về ngoại ngữ cho K70",
        "quy định về ngoại ngữ cho K67",
    ]


def test_build_major_comparison_subqueries_for_retrieval() -> None:
    """Major comparison query should be decomposed into one query per major."""
    query = "môn lập trình mạng của ngành IT-E7 và IT-E6 có gì khác nhau"
    assert build_major_comparison_subqueries_for_retrieval(query) == [
        ("môn lập trình mạng của ngành IT-E7", "IT-E7"),
        ("môn lập trình mạng của ngành IT-E6", "IT-E6"),
    ]


def test_build_major_comparison_subqueries_for_new_major_codes() -> None:
    """Comparison decomposition should work for newly supported major codes."""
    query = "so sánh ngoại ngữ của ME-GU và ME-LUH có gì khác nhau"
    assert build_major_comparison_subqueries_for_retrieval(query) == [
        ("ngoại ngữ của ngành ME-GU", "ME-GU"),
        ("ngoại ngữ của ngành ME-LUH", "ME-LUH"),
    ]


def test_kehoach_filter_extractor_bypasses_school_years() -> None:
    """KeHoach filter extractor should bypass school years like 2025-2026 or 2025/2026."""
    from retrieval.metadata_filters import KeHoachFilterExtractor
    extractor = KeHoachFilterExtractor()
    
    # Queries containing school-year ranges should not trigger year-specific pre-filters.
    cf1 = extractor.extract("kế hoạch học tập năm học 2025-2026")
    assert cf1.is_empty is True
    
    cf2 = extractor.extract("đăng ký học phần kỳ hè 2025/2026 tuyển sinh")
    assert cf2.is_empty is True

    # But standard single-year queries should still correctly filter.
    cf3 = extractor.extract("Kế hoạch đăng ký lớp năm 2025")
    assert cf3.is_empty is False
    assert "2025" in str(cf3.metadata_es_queries)
