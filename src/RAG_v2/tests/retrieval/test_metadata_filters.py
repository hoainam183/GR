"""Unit tests for major-name middleware used by metadata filters."""

from retrieval.metadata_filters import (
    MAJOR_CODE_TO_NAME,
    _extract_major_code,
    _resolve_major_code,
    build_collection_filters,
    build_major_comparison_subqueries_for_retrieval,
    build_cohort_comparison_subqueries_for_retrieval,
    canonicalize_major_name,
    enrich_major_references_for_query,
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


def _extract_query_fields(node: object) -> set[str]:
    """Collect term/exists field names from a nested ES query object."""
    out: set[str] = set()
    if isinstance(node, dict):
        term_clause = node.get("term")
        if isinstance(term_clause, dict):
            out.update(str(field) for field in term_clause)

        exists_clause = node.get("exists")
        if isinstance(exists_clause, dict) and exists_clause.get("field"):
            out.add(str(exists_clause["field"]))

        for value in node.values():
            out.update(_extract_query_fields(value))
    elif isinstance(node, list):
        for item in node:
            out.update(_extract_query_fields(item))
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


def test_enrich_major_references_expands_codes_to_names() -> None:
    """Retrieval query should include major names for explicit major codes."""
    query = "So sánh ngoại ngữ giữa IT1 và IT-E6"

    enriched = enrich_major_references_for_query(query)

    assert "IT1 (CNTT: Khoa học Máy tính)" in enriched
    assert "IT-E6 (Công nghệ thông tin (Việt-Nhật)" in enriched


def test_enrich_major_references_expands_names_to_codes() -> None:
    """Retrieval query should include codes for explicit major names."""
    query = "So sánh ngoại ngữ giữa Khoa học máy tính và Công nghệ thông tin Việt-Nhật"

    enriched = enrich_major_references_for_query(query)

    assert "Khoa học máy tính (IT1)" in enriched
    assert "Công nghệ thông tin Việt-Nhật (IT-E6)" in enriched


def test_extract_major_code_supports_all_indexed_ctdt_codes() -> None:
    """Every indexed CTDT major code should be recognised explicitly."""
    expected_codes = list(MAJOR_CODE_TO_NAME)
    query = ", ".join(expected_codes)

    assert extract_major_codes(query) == expected_codes
    for code in expected_codes:
        assert _resolve_major_code(code, None) == code


def test_resolve_major_code_preserves_direct_code_for_similar_names() -> None:
    """Direct codes should not be remapped through similar major names."""
    assert _resolve_major_code("generic", "EE2") == "EE2"
    assert _resolve_major_code("generic", "EE-E8") == "EE-E8"
    assert _resolve_major_code("generic", "BF2") == "BF2"
    assert _resolve_major_code("generic", "BF-E12") == "BF-E12"


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


def test_quydinh_filter_extractor_matches_applicable_cohort_array_values() -> None:
    """QuyDinh filter should use cohort Kxx term queries for applicable_cohort arrays."""
    extractor = QuyDinhFilterExtractor()
    cf = extractor.extract("quy định ngoại ngữ của K70")

    assert len(cf.metadata_es_queries) == 1
    query = cf.metadata_es_queries[0]
    assert query["bool"]["minimum_should_match"] == 1
    fields = _extract_query_fields(query)
    assert "applicable_cohort" in fields
    assert "applicable_cohort.keyword" in fields
    assert not any(field.startswith("applicable_major") for field in fields)
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


def test_quydinh_filter_uses_applicable_cohort_for_blood_donation_with_profile() -> None:
    """Generic discipline-score questions should not filter cohorts on applicable_major."""
    extractor = QuyDinhFilterExtractor()
    cf = extractor.extract(
        "hiến máu được mấy điểm rèn luyện",
        resolved_cohort="68",
        resolved_major="IT1",
    )

    strict = cf.metadata_es_queries[0]
    strict_values = _extract_term_values(strict)
    fields = _extract_query_fields(strict)

    assert "K68" in strict_values
    assert "applicable_cohort" in fields
    assert not any(field.startswith("applicable_major") for field in fields)


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


def test_kehoach_filter_freshness_intent_sets_sort_by_date_desc() -> None:
    """Freshness-intent phrases should produce sort_by_date_desc=True with no ES query."""
    from retrieval.metadata_filters import KeHoachFilterExtractor
    extractor = KeHoachFilterExtractor()

    for phrase in [
        "học kỳ mới nhất",
        "Lịch trình học kỳ mới nhất?",
        "thông báo gần đây",
        "kế hoạch hiện tại",
        "kỳ này có gì mới",
        "học kỳ mới bắt đầu khi nào",
        "học kỳ tới cần đăng ký gì",
        "thông báo mới từ phòng đào tạo",
    ]:
        cf = extractor.extract(phrase)
        assert cf.sort_by_date_desc is True, f"Expected sort_by_date_desc for: {phrase!r}"
        assert cf.is_empty is True, f"Expected no ES query for: {phrase!r}"


def test_kehoach_filter_academic_terms_do_not_become_calendar_year_filters() -> None:
    """Academic term tokens are not posting dates; freshness sorting should handle them."""
    from retrieval.metadata_filters import KeHoachFilterExtractor
    extractor = KeHoachFilterExtractor()

    for phrase in [
        "đăng kí học tập học kỳ 2025.2 mới nhất",
        "đăng kí học tập học kỳ 20252 mới nhất",
        "đăng kí học tập học kỳ 2025-2 mới nhất",
    ]:
        cf = extractor.extract(phrase)
        assert cf.sort_by_date_desc is True, f"Expected latest sorting for: {phrase!r}"
        assert cf.is_empty is True, f"Expected no wildcard date query for: {phrase!r}"


def test_kehoach_filter_academic_term_without_freshness_is_not_calendar_date() -> None:
    """Academic term tokens alone should not create a date_str wildcard."""
    from retrieval.metadata_filters import KeHoachFilterExtractor
    extractor = KeHoachFilterExtractor()

    for phrase in [
        "đăng kí học tập học kỳ 2025.2",
        "đăng kí học tập học kỳ 20252",
        "đăng kí học tập học kỳ 2025-2",
    ]:
        cf = extractor.extract(phrase)
        assert cf.is_empty is True, f"Expected no date filter for: {phrase!r}"
        assert cf.sort_by_date_desc is False


def test_build_collection_filters_applies_freshness_to_date_str_collections() -> None:
    """Generic freshness intent should use date_str sorting for supported collections."""
    from retrieval.metadata_filters import build_collection_filters

    filters = build_collection_filters(
        "lich trinh hoc ky moi nhat",
        ["kehoach", "quydinh", "ctdt", "stsv"],
    )

    assert filters["kehoach"].sort_by_date_desc is True
    assert filters["quydinh"].sort_by_date_desc is True
    assert filters["ctdt"].sort_by_date_desc is False
    assert filters["stsv"].sort_by_date_desc is False


def test_quydinh_cohort_filter_takes_priority_over_generic_freshness() -> None:
    """Existing quydinh cohort filters should not be replaced by latest-doc filtering."""
    from retrieval.metadata_filters import build_collection_filters

    filters = build_collection_filters(
        "quy dinh moi nhat cho K70",
        ["quydinh"],
    )

    assert filters["quydinh"].sort_by_date_desc is False
    assert filters["quydinh"].is_empty is False


def test_kehoach_filter_explicit_date_keeps_wildcard_priority() -> None:
    """Explicit month/year filter takes priority — no sort_by_date_desc flag."""
    from retrieval.metadata_filters import KeHoachFilterExtractor
    extractor = KeHoachFilterExtractor()

    cf1 = extractor.extract("kế hoạch tháng 3/2026")
    assert cf1.sort_by_date_desc is False
    assert cf1.is_empty is False
    assert "2026" in str(cf1.metadata_es_queries)

    cf2 = extractor.extract("kế hoạch năm 2025")
    assert cf2.sort_by_date_desc is False
    assert cf2.is_empty is False
    assert "2025" in str(cf2.metadata_es_queries)


def test_kehoach_filter_combined_freshness_and_explicit_date_explicit_wins() -> None:
    """When both freshness intent and explicit date are present, explicit date wins."""
    from retrieval.metadata_filters import KeHoachFilterExtractor
    extractor = KeHoachFilterExtractor()

    # "mới nhất" + explicit "tháng 4/2026" — explicit date should win
    cf = extractor.extract("thông báo mới nhất tháng 4/2026")
    assert cf.sort_by_date_desc is False
    assert cf.is_empty is False
    assert "4" in str(cf.metadata_es_queries)
    assert "2026" in str(cf.metadata_es_queries)


def test_kehoach_filter_school_year_does_not_trigger_freshness() -> None:
    """School-year ranges without freshness keywords must produce empty filter."""
    from retrieval.metadata_filters import KeHoachFilterExtractor
    extractor = KeHoachFilterExtractor()

    cf = extractor.extract("kế hoạch học tập năm học 2025-2026")
    assert cf.is_empty is True
    assert cf.sort_by_date_desc is False


# ─── Freshness mode — ES ids filter propagation ──────────────────────────────


def test_freshness_mode_es_ids_filter_applied() -> None:
    """In freshness mode, _resolve_filter_with_fallback must pass an ES ids filter.

    When sort_by_date_desc=True and get_latest_chunk_ids_by_date returns IDs,
    the function should return BOTH a Qdrant HasIdCondition AND an ES ids filter
    so that BM25 keyword search is constrained to the same latest docs.
    This prevents older dated documents (e.g. 20252) from outranking newer ones
    (e.g. 20253/20261) via keyword-score alone.
    """
    from unittest.mock import MagicMock
    from retrieval.multi_collection_search import MultiCollectionSearch
    from retrieval.metadata_filters import CollectionFilter

    latest_ids = ["chunk_new_1", "chunk_new_2", "chunk_new_3"]

    hybrid = MagicMock()
    hybrid.es.get_latest_chunk_ids_by_date.return_value = latest_ids
    hybrid.es.resolve_chunk_ids_for_qdrant.return_value = latest_ids

    cf = CollectionFilter(sort_by_date_desc=True)

    searcher = object.__new__(MultiCollectionSearch)
    qdrant_filter, es_filter, trace = searcher._resolve_filter_with_fallback(
        "kehoach", hybrid, cf
    )

    # Qdrant filter must be set
    assert qdrant_filter is not None, "Qdrant HasIdCondition must be applied in freshness mode"

    # ES ids filter must also be set (new behaviour — prevents unfiltered BM25)
    assert es_filter is not None, (
        "ES ids filter must be set in freshness mode to constrain BM25 to latest docs"
    )
    assert "ids" in es_filter, f"ES filter must use 'ids' query, got: {es_filter}"
    assert set(es_filter["ids"]["values"]) == set(latest_ids), (
        f"ES filter must cover exactly the latest chunk IDs, got: {es_filter['ids']['values']}"
    )

    # Trace must report the filter was applied
    assert trace["applied"] is True
    assert trace["matched_ids"] == len(latest_ids)


def test_freshness_mode_no_ids_returns_no_filter() -> None:
    """When get_latest_chunk_ids_by_date returns empty, no filter is applied."""
    from unittest.mock import MagicMock
    from retrieval.multi_collection_search import MultiCollectionSearch
    from retrieval.metadata_filters import CollectionFilter

    hybrid = MagicMock()
    hybrid.es.get_latest_chunk_ids_by_date.return_value = []

    cf = CollectionFilter(sort_by_date_desc=True)

    searcher = object.__new__(MultiCollectionSearch)
    qdrant_filter, es_filter, trace = searcher._resolve_filter_with_fallback(
        "kehoach", hybrid, cf
    )

    assert qdrant_filter is None
    assert es_filter is None
    assert trace["applied"] is False


def test_metadata_presearch_zero_ids_falls_back_to_no_filter() -> None:
    """Zero ES metadata matches must not produce an empty Qdrant HasIdCondition."""
    from unittest.mock import MagicMock
    from retrieval.multi_collection_search import MultiCollectionSearch
    from retrieval.metadata_filters import CollectionFilter

    hybrid = MagicMock()
    hybrid.es.metadata_filter_search.return_value = []
    hybrid.es.count.return_value = 10

    cf = CollectionFilter(
        metadata_es_queries=[
            {"term": {"applicable_cohort": "K68"}},
        ]
    )

    searcher = object.__new__(MultiCollectionSearch)
    qdrant_filter, es_filter, trace = searcher._resolve_filter_with_fallback(
        "quydinh", hybrid, cf
    )

    assert qdrant_filter is None
    assert es_filter is None
    assert trace["applied"] is False
    hybrid.es.resolve_chunk_ids_for_qdrant.assert_not_called()


def test_metadata_presearch_empty_es_index_uses_qdrant_payload_filter() -> None:
    """When ES is empty, exact metadata filters should still constrain Qdrant."""
    from unittest.mock import MagicMock
    from retrieval.multi_collection_search import MultiCollectionSearch
    from retrieval.metadata_filters import CollectionFilter

    hybrid = MagicMock()
    hybrid.es.metadata_filter_search.return_value = []
    hybrid.es.count.return_value = 0

    cf = CollectionFilter(
        metadata_es_queries=[
            {
                "bool": {
                    "should": [
                        {"term": {"major_code": "IT-E6"}},
                        {"term": {"major_code.keyword": "IT-E6"}},
                    ],
                    "minimum_should_match": 1,
                }
            }
        ]
    )

    searcher = object.__new__(MultiCollectionSearch)
    qdrant_filter, es_filter, trace = searcher._resolve_filter_with_fallback(
        "ctdt", hybrid, cf
    )

    assert qdrant_filter is not None
    assert es_filter is None
    assert trace["applied"] is True
    assert "qdrant_payload:major_code=IT-E6" in trace["filter_desc"]

    condition = qdrant_filter.must[0]
    assert condition.key == "major_code"
    assert condition.match.value == "IT-E6"
