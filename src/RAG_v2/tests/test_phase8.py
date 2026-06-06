"""Test Phase 8 — Collection-aware Query Routing.

Refactored from script-style to proper pytest module.
Tests:
  8.1 CollectionSelector logic
  8.2 MultiCollectionSearch active_collections filtering
  8.3 rag_flow integration with routing_result
  8.4 Settings fields for Phase 8
"""

from __future__ import annotations

from unittest.mock import MagicMock


# ─── Shared mock factory ──────────────────────────────────────────────────────

def _make_mock_hybrid(name: str) -> MagicMock:
    hybrid = MagicMock()
    hybrid.qdrant.search.return_value = [
        {"id": f"{name}-v1", "text": f"vec from {name}", "score": 0.8, "metadata": {}},
    ]
    hybrid.es.keyword_search.return_value = [
        {"id": f"{name}-k1", "text": f"kw from {name}", "score": 5.0, "metadata": {}},
    ]
    return hybrid


def _make_pipeline_mocks():
    mock_bge = MagicMock()
    mock_bge.embed_query.return_value = [0.1] * 1024
    mock_e5 = MagicMock()
    mock_e5.embed_query.return_value = [0.2] * 1024
    mock_searcher = MagicMock()
    mock_searcher.search.return_value = [
        {"text": "doc1", "metadata": {"title": "Test"}, "collection": "quydinh"},
    ]
    mock_reranker = MagicMock()
    mock_reranker.rerank.return_value = [
        {"text": "doc1", "metadata": {"title": "Test"}, "collection": "quydinh"},
    ]
    mock_chat = MagicMock()
    mock_chat.generate.return_value = "Test answer"
    mock_chat.model = "test-model"
    cfg = {
        "top_k": 5,
        "vector_top_k": 20,
        "keyword_top_k": 20,
        "vector_pool_k": 15,
        "keyword_pool_k": 15,
    }
    return mock_bge, mock_e5, mock_searcher, mock_reranker, mock_chat, cfg


class TestCollectionSelector:
    def test_none_domain_returns_all_collections(self) -> None:
        from retrieval.collection_selector import CollectionSelector, ALL_COLLECTIONS
        selector = CollectionSelector()
        result = selector.select(domain=None, confidence=0.0)
        assert set(result) == set(ALL_COLLECTIONS)

    def test_high_confidence_maps_to_single_domain(self) -> None:
        from retrieval.collection_selector import CollectionSelector
        selector = CollectionSelector()
        assert selector.select(domain="quydinh", confidence=0.90) == ["quydinh", "stsv"]
        assert selector.select(domain="stsv", confidence=0.80) == ["stsv", "quydinh"]
        assert selector.select(domain="ctdt", confidence=0.75) == ["ctdt"]
        assert selector.select(domain="kehoach", confidence=0.70) == ["kehoach"]

    def test_policy_support_query_expands_to_quydinh_and_stsv(self) -> None:
        from retrieval.collection_selector import CollectionSelector
        selector = CollectionSelector()
        result = selector.select(
            domain="stsv",
            confidence=0.90,
            query="tôi đã tham gia hiến máu nhưng chưa nhận được điểm rèn luyện",
        )
        assert result == ["quydinh", "stsv"]

    def test_ctdt_course_credit_lookup_stays_focused(self) -> None:
        from retrieval.collection_selector import CollectionSelector
        selector = CollectionSelector()
        result = selector.select(
            domain="ctdt",
            confidence=0.90,
            query="môn xử lý tín hiệu số có mấy tín chỉ",
        )
        assert result == ["ctdt"]

    def test_foreign_language_fl_code_lookup_adds_quydinh(self) -> None:
        from retrieval.collection_selector import CollectionSelector
        selector = CollectionSelector()
        result = selector.select(
            domain="ctdt",
            confidence=0.90,
            query="K65: Lớp FL1129 có thời lượng bao nhiêu?",
        )
        assert result == ["quydinh", "ctdt"]

    def test_foreign_language_cohort_lookup_adds_quydinh(self) -> None:
        from retrieval.collection_selector import CollectionSelector
        selector = CollectionSelector()
        result = selector.select(
            domain="kehoach",
            confidence=0.90,
            query="K70: Nếu tôi đạt Bậc 2.3 thì tôi thuộc nhóm mấy?",
        )
        assert result == ["quydinh", "kehoach"]

    def test_low_confidence_returns_fallback(self) -> None:
        from retrieval.collection_selector import CollectionSelector, MULTI_DOMAIN_FALLBACK
        selector = CollectionSelector()
        result = selector.select(domain="quydinh", confidence=0.40)
        assert set(result) == set(MULTI_DOMAIN_FALLBACK)

    def test_unknown_domain_returns_all_collections(self) -> None:
        from retrieval.collection_selector import CollectionSelector, ALL_COLLECTIONS
        selector = CollectionSelector()
        result = selector.select(domain="unknown_domain", confidence=0.99)
        assert set(result) == set(ALL_COLLECTIONS)

    def test_custom_threshold(self) -> None:
        from retrieval.collection_selector import CollectionSelector, MULTI_DOMAIN_FALLBACK
        custom = CollectionSelector(confidence_threshold=0.80)
        result = custom.select(domain="quydinh", confidence=0.75)
        assert set(result) == set(MULTI_DOMAIN_FALLBACK)

    def test_custom_fallback_collections(self) -> None:
        from retrieval.collection_selector import CollectionSelector
        custom = CollectionSelector(fallback_collections=["stsv", "ctdt"])
        result = custom.select(domain="quydinh", confidence=0.30)
        assert result == ["quydinh", "stsv", "ctdt"]

    def test_confidence_at_threshold_passes(self) -> None:
        from retrieval.collection_selector import CollectionSelector
        selector = CollectionSelector()
        result = selector.select(domain="quydinh", confidence=0.65)
        assert result == ["quydinh", "stsv"]

    def test_low_confidence_preserves_active_domain_before_fallback(self) -> None:
        from retrieval.collection_selector import CollectionSelector
        selector = CollectionSelector()
        result = selector.select(
            domain="kehoach",
            domains=["kehoach"],
            confidence=0.524,
        )
        assert result == ["kehoach", "quydinh", "stsv", "ctdt"]

    def test_low_confidence_schedule_signal_adds_kehoach(self) -> None:
        from retrieval.collection_selector import CollectionSelector
        selector = CollectionSelector()
        result = selector.select(
            domain="ctdt",
            confidence=0.40,
            query="lich dang ky hoc ky moi",
            probabilities={"ctdt": 0.40, "kehoach": 0.25, "quydinh": 0.20},
        )
        assert result == ["ctdt", "kehoach", "quydinh", "stsv"]

    def test_low_confidence_close_kehoach_probability_adds_kehoach(self) -> None:
        from retrieval.collection_selector import CollectionSelector
        selector = CollectionSelector()
        result = selector.select(
            domain="quydinh",
            confidence=0.44,
            query="dieu kien hoc bong",
            probabilities={"quydinh": 0.44, "kehoach": 0.39, "stsv": 0.20},
        )
        assert result == ["quydinh", "stsv", "kehoach", "ctdt"]

    def test_curriculum_study_plan_query_does_not_add_kehoach(self) -> None:
        from retrieval.collection_selector import CollectionSelector
        selector = CollectionSelector()
        result = selector.select(
            domain="ctdt",
            confidence=0.40,
            query="ke hoach hoc tap trong ctdt nganh cntt",
            probabilities={"ctdt": 0.54, "kehoach": 0.10, "quydinh": 0.22},
        )
        assert result == ["ctdt", "quydinh", "stsv"]


class TestKeHoachRouteLock:
    def test_clear_single_kehoach_schedule_locks(self) -> None:
        from pipeline.flows import _should_lock_kehoach_route

        assert _should_lock_kehoach_route(
            question="lich dang ky hoc ky moi nhat",
            search_query="lich dang ky hoc ky moi nhat",
            routing_result={
                "domain": "kehoach",
                "domains": ["kehoach"],
                "confidence": 0.52,
                "probabilities": {"kehoach": 0.52, "ctdt": 0.18},
            },
        ) is True

    def test_curriculum_study_plan_query_does_not_lock(self) -> None:
        from pipeline.flows import _should_lock_kehoach_route

        assert _should_lock_kehoach_route(
            question="ke hoach hoc tap trong ctdt nganh cntt",
            search_query="ke hoach hoc tap trong ctdt nganh cntt",
            routing_result={
                "domain": "kehoach",
                "domains": ["kehoach"],
                "confidence": 0.70,
                "probabilities": {"kehoach": 0.70, "ctdt": 0.20},
            },
        ) is False

    def test_non_kehoach_top_probability_does_not_lock(self) -> None:
        from pipeline.flows import _should_lock_kehoach_route

        assert _should_lock_kehoach_route(
            question="lich dang ky hoc chuong trinh thu hai",
            search_query="lich dang ky hoc chuong trinh thu hai",
            routing_result={
                "domain": "quydinh",
                "domains": ["quydinh", "kehoach"],
                "confidence": 0.60,
                "probabilities": {"quydinh": 0.60, "kehoach": 0.52},
            },
        ) is False

    def test_policy_timing_phrase_does_not_lock_when_only_kehoach_returned(self) -> None:
        from pipeline.flows import _should_lock_kehoach_route

        assert _should_lock_kehoach_route(
            question="khi nao sinh vien duoc dang ky hoc chuong trinh thu hai",
            search_query="khi nao sinh vien duoc dang ky hoc chuong trinh thu hai",
            routing_result={
                "domain": "kehoach",
                "domains": ["kehoach"],
                "confidence": 0.40,
                "probabilities": {"kehoach": 0.40, "quydinh": 0.38},
            },
        ) is False


class TestMultiCollectionSearchFiltering:
    def test_search_all_collections_when_no_filter(self) -> None:
        from retrieval.multi_collection_search import MultiCollectionSearch
        searchers = [
            ("stsv", _make_mock_hybrid("stsv")),
            ("quydinh", _make_mock_hybrid("quydinh")),
            ("kehoach", _make_mock_hybrid("kehoach")),
            ("ctdt", _make_mock_hybrid("ctdt")),
        ]
        mcs = MultiCollectionSearch(searchers=searchers)
        mcs.search(query="test", bge_m3_query=[0.1] * 10, e5_query=[0.2] * 10, top_k=10)
        for name, hybrid in searchers:
            assert hybrid.qdrant.search.called, f"{name} should have been searched"

    def test_filter_single_collection(self) -> None:
        from retrieval.multi_collection_search import MultiCollectionSearch
        stsv = _make_mock_hybrid("stsv")
        quydinh = _make_mock_hybrid("quydinh")
        kehoach = _make_mock_hybrid("kehoach")
        ctdt = _make_mock_hybrid("ctdt")
        searchers = [("stsv", stsv), ("quydinh", quydinh), ("kehoach", kehoach), ("ctdt", ctdt)]
        mcs = MultiCollectionSearch(searchers=searchers)
        mcs.search(
            query="test", bge_m3_query=[0.1] * 10, e5_query=[0.2] * 10, top_k=10,
            active_collections=["quydinh"],
        )
        assert quydinh.qdrant.search.called
        assert not stsv.qdrant.search.called
        assert not kehoach.qdrant.search.called
        assert not ctdt.qdrant.search.called

    def test_filter_multiple_collections(self) -> None:
        from retrieval.multi_collection_search import MultiCollectionSearch
        stsv = _make_mock_hybrid("stsv")
        quydinh = _make_mock_hybrid("quydinh")
        kehoach = _make_mock_hybrid("kehoach")
        ctdt = _make_mock_hybrid("ctdt")
        searchers = [("stsv", stsv), ("quydinh", quydinh), ("kehoach", kehoach), ("ctdt", ctdt)]
        mcs = MultiCollectionSearch(searchers=searchers)
        mcs.search(
            query="test", bge_m3_query=[0.1] * 10, e5_query=[0.2] * 10, top_k=10,
            active_collections=["stsv", "ctdt"],
        )
        assert stsv.qdrant.search.called
        assert ctdt.qdrant.search.called
        assert not quydinh.qdrant.search.called

    def test_freshness_query_filters_quydinh_vector_search_to_latest_ids(self) -> None:
        from retrieval.multi_collection_search import MultiCollectionSearch

        quydinh = _make_mock_hybrid("quydinh")
        quydinh.es.get_latest_chunk_ids_by_date.return_value = ["doc-latest"]
        quydinh.es.resolve_chunk_ids_for_qdrant.return_value = ["qdrant-latest"]

        mcs = MultiCollectionSearch(searchers=[("quydinh", quydinh)])
        results = mcs.search(
            query="quy dinh moi nhat",
            bge_m3_query=[0.1] * 10,
            e5_query=[0.2] * 10,
            top_k=10,
            active_collections=["quydinh"],
        )

        assert results
        quydinh.es.get_latest_chunk_ids_by_date.assert_called_once_with(max_n=200)
        qdrant_filter = quydinh.qdrant.search.call_args.kwargs["filters"]
        assert qdrant_filter is not None

    def test_freshness_query_without_date_str_support_uses_normal_retrieval(self) -> None:
        from retrieval.multi_collection_search import MultiCollectionSearch

        stsv = _make_mock_hybrid("stsv")

        mcs = MultiCollectionSearch(searchers=[("stsv", stsv)])
        mcs.search(
            query="thong tin moi nhat",
            bge_m3_query=[0.1] * 10,
            e5_query=[0.2] * 10,
            top_k=10,
            active_collections=["stsv"],
        )

        stsv.es.get_latest_chunk_ids_by_date.assert_not_called()
        qdrant_filter = stsv.qdrant.search.call_args.kwargs["filters"]
        assert qdrant_filter is not None
        assert not qdrant_filter.must

    def test_unknown_collection_falls_back_to_all(self) -> None:
        from retrieval.multi_collection_search import MultiCollectionSearch
        searchers = [
            ("stsv", _make_mock_hybrid("stsv")),
            ("quydinh", _make_mock_hybrid("quydinh")),
            ("kehoach", _make_mock_hybrid("kehoach")),
            ("ctdt", _make_mock_hybrid("ctdt")),
        ]
        mcs = MultiCollectionSearch(searchers=searchers)
        mcs.search(
            query="test", bge_m3_query=[0.1] * 10, e5_query=[0.2] * 10, top_k=10,
            active_collections=["nonexistent"],
        )
        for name, hybrid in searchers:
            assert hybrid.qdrant.search.called, f"{name} should fall back to all"

    def test_qdrant_stores_property(self) -> None:
        from retrieval.multi_collection_search import MultiCollectionSearch
        searchers = [
            ("stsv", _make_mock_hybrid("stsv")),
            ("quydinh", _make_mock_hybrid("quydinh")),
        ]
        mcs = MultiCollectionSearch(searchers=searchers)
        stores = mcs.qdrant_stores
        assert isinstance(stores, dict)
        assert len(stores) == 2

    def test_exact_policy_query_expands_keyword_candidate_pool(self) -> None:
        from retrieval.multi_collection_search import MultiCollectionSearch
        trace = {}
        quydinh = _make_mock_hybrid("quydinh")
        mcs = MultiCollectionSearch(searchers=[("quydinh", quydinh)])

        mcs.search(
            query="hiến máu được bao nhiêu điểm rèn luyện",
            bge_m3_query=[0.1] * 10,
            e5_query=[0.2] * 10,
            top_k=5,
            keyword_top_k=20,
            keyword_pool_k=15,
            active_collections=["quydinh"],
            trace_out=trace,
        )

        assert quydinh.es.keyword_search.call_args.kwargs["top_k"] == 120
        assert trace["candidate_pool_sizes"]["keyword_pool_k"] == 80
        assert trace["fusion_weights"]["reason"] == "exact_policy_keyword_bias"

    def test_table_hits_are_pinned_into_keyword_pool(self) -> None:
        from retrieval.multi_collection_search import MultiCollectionSearch

        high_noise = {"id": "quydinh/noise", "text": "noise", "score": 10.0, "metadata": {}}
        table_hit = {
            "id": "quydinh/df79f3f4",
            "text": "Tham gia hiến máu nhân đạo được 6 điểm",
            "score": 1.0,
            "metadata": {"_keyword_table_lookup_hit": True},
        }

        pool, pinned_count = MultiCollectionSearch._pin_keyword_hits(
            [high_noise, table_hit],
            [high_noise],
            k=2,
        )

        assert pinned_count == 1
        assert [item["id"] for item in pool] == ["quydinh/noise", "quydinh/df79f3f4"]

    def test_procedural_support_keeps_stsv_evidence_in_final_results(self) -> None:
        from retrieval.multi_collection_search import MultiCollectionSearch

        results = [
            {"id": f"quydinh/{idx}", "text": "regulation", "score": 1.0 - idx / 10}
            for idx in range(5)
        ]
        stsv_hit = {
            "id": "stsv/1177b82e-759b-42d6-aea8-c09ac514926f",
            "text": "minh chứng chưa được xác nhận",
            "score": 0.2,
            "metadata": {},
        }

        final = MultiCollectionSearch._ensure_collection_evidence(
            results,
            [stsv_hit],
            top_k=5,
            collection="stsv",
        )

        assert len(final) == 5
        assert final[-1]["id"] == "stsv/1177b82e-759b-42d6-aea8-c09ac514926f"


class TestRagFlowRoutingIntegration:
    def test_active_collections_passed_to_searcher(self) -> None:
        from pipeline.flows import rag_flow
        mock_bge, mock_e5, mock_searcher, mock_reranker, mock_chat, cfg = _make_pipeline_mocks()
        rag_flow(
            question="Điều kiện xét học bổng?", history=None, reflector=None,
            bge_embedder=mock_bge, e5_embedder=mock_e5,
            searcher=mock_searcher, reranker=mock_reranker, chat_model=mock_chat,
            self_evaluator=None, tavily_tool=None, cfg=cfg,
            routing_result={"intent": "rag", "domain": "quydinh", "confidence": 0.90},
        )
        # First search call must use the resolved active_collections
        first_call_kwargs = mock_searcher.search.call_args_list[0].kwargs
        assert "active_collections" in first_call_kwargs
        assert first_call_kwargs["active_collections"] == ["quydinh", "stsv"]

    def test_result_contains_target_collections(self) -> None:
        from pipeline.flows import rag_flow
        mock_bge, mock_e5, mock_searcher, mock_reranker, mock_chat, cfg = _make_pipeline_mocks()
        result = rag_flow(
            question="Điều kiện?", history=None, reflector=None,
            bge_embedder=mock_bge, e5_embedder=mock_e5,
            searcher=mock_searcher, reranker=mock_reranker, chat_model=mock_chat,
            self_evaluator=None, tavily_tool=None, cfg=cfg,
            routing_result={"intent": "rag", "domain": "quydinh", "confidence": 0.90},
        )
        # target_collections must appear in the response
        assert "target_collections" in result
        assert "quydinh" in result["target_collections"]

    def test_no_routing_result_passes_none(self) -> None:
        from pipeline.flows import rag_flow
        mock_bge, mock_e5, mock_searcher, mock_reranker, mock_chat, cfg = _make_pipeline_mocks()
        rag_flow(
            question="Xin chào", history=None, reflector=None,
            bge_embedder=mock_bge, e5_embedder=mock_e5,
            searcher=mock_searcher, reranker=mock_reranker, chat_model=mock_chat,
            self_evaluator=None, tavily_tool=None, cfg=cfg, routing_result=None,
        )
        first_call_kwargs = mock_searcher.search.call_args_list[0].kwargs
        # No routing → active_collections should be None (search all)
        assert first_call_kwargs.get("active_collections") is None

    def test_low_confidence_uses_fallback_collections(self) -> None:
        from pipeline.flows import rag_flow
        from retrieval.collection_selector import MULTI_DOMAIN_FALLBACK
        mock_bge, mock_e5, mock_searcher, mock_reranker, mock_chat, cfg = _make_pipeline_mocks()
        rag_flow(
            question="Test query", history=None, reflector=None,
            bge_embedder=mock_bge, e5_embedder=mock_e5,
            searcher=mock_searcher, reranker=mock_reranker, chat_model=mock_chat,
            self_evaluator=None, tavily_tool=None, cfg=cfg,
            routing_result={"intent": "rag", "domain": "ctdt", "confidence": 0.30},
        )
        first_call_kwargs = mock_searcher.search.call_args_list[0].kwargs
        active = first_call_kwargs.get("active_collections")
        assert set(active) == set(MULTI_DOMAIN_FALLBACK)

    def test_low_confidence_latest_kehoach_route_locks_to_kehoach(self) -> None:
        from pipeline.flows import rag_flow
        mock_bge, mock_e5, mock_searcher, mock_reranker, mock_chat, cfg = _make_pipeline_mocks()
        cfg["collections"] = ["stsv", "quydinh", "kehoach", "ctdt"]

        rag_flow(
            question="đăng kí học tập kì mới nhất", history=None, reflector=None,
            bge_embedder=mock_bge, e5_embedder=mock_e5,
            searcher=mock_searcher, reranker=mock_reranker, chat_model=mock_chat,
            self_evaluator=None, tavily_tool=None, cfg=cfg,
            routing_result={
                "intent": "rag",
                "domain": "kehoach",
                "domains": ["kehoach"],
                "confidence": 0.524,
                "probabilities": {
                    "kehoach": 0.524,
                    "quydinh": 0.169,
                    "stsv": 0.092,
                    "ctdt": 0.180,
                },
            },
        )

        first_call_kwargs = mock_searcher.search.call_args_list[0].kwargs
        assert first_call_kwargs["active_collections"] == ["kehoach"]

    def test_stream_passes_active_collections(self) -> None:
        from pipeline.flows import rag_flow_stream
        mock_bge, mock_e5, mock_searcher, mock_reranker, mock_chat, cfg = _make_pipeline_mocks()
        mock_chat.generate_stream.return_value = iter(["chunk1"])
        stream, _ = rag_flow_stream(
            question="Test stream", history=None, reflector=None,
            bge_embedder=mock_bge, e5_embedder=mock_e5,
            searcher=mock_searcher, reranker=mock_reranker, chat_model=mock_chat,
            cfg=cfg,
            routing_result={"intent": "rag", "domain": "stsv", "confidence": 0.85},
        )
        list(stream)
        first_call_kwargs = mock_searcher.search.call_args_list[0].kwargs
        assert first_call_kwargs.get("active_collections") == ["stsv", "quydinh"]

    def test_stream_low_confidence_latest_kehoach_route_locks_to_kehoach(self) -> None:
        from pipeline.flows import rag_flow_stream
        mock_bge, mock_e5, mock_searcher, mock_reranker, mock_chat, cfg = _make_pipeline_mocks()
        mock_chat.generate_stream.return_value = iter(["chunk1"])
        cfg["collections"] = ["stsv", "quydinh", "kehoach", "ctdt"]

        stream, _ = rag_flow_stream(
            question="đăng kí học tập kì mới nhất", history=None,
            reflector=None, bge_embedder=mock_bge, e5_embedder=mock_e5,
            searcher=mock_searcher, reranker=mock_reranker, chat_model=mock_chat,
            cfg=cfg,
            routing_result={
                "intent": "rag",
                "domain": "kehoach",
                "domains": ["kehoach"],
                "confidence": 0.524,
                "probabilities": {
                    "kehoach": 0.524,
                    "quydinh": 0.169,
                    "stsv": 0.092,
                    "ctdt": 0.180,
                },
            },
        )
        list(stream)

        first_call_kwargs = mock_searcher.search.call_args_list[0].kwargs
        assert first_call_kwargs["active_collections"] == ["kehoach"]


class TestSettingsPhase8:
    def test_domain_routing_enabled_field_exists_and_default(self) -> None:
        from config.settings import Settings
        s = Settings()
        assert hasattr(s, "domain_routing_enabled")
        assert s.domain_routing_enabled is True

    def test_domain_confidence_threshold_field(self) -> None:
        from config.settings import Settings
        s = Settings()
        assert hasattr(s, "domain_confidence_threshold")
        assert s.domain_confidence_threshold == 0.65
