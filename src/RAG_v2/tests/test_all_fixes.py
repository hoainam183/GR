"""Unit tests for the 4 P0–P3 fixes.

Run:
    cd src/RAG_v2 && python -m pytest tests/test_all_fixes.py -v

Tests are designed to be fast and dependency-free (no Redis, no embedders,
no network), using mocks and pure-logic assertions.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest


# ═══════════════════════════════════════════════════════════════════════════════
# P3 — Relative confidence Tier-3 threshold
# ═══════════════════════════════════════════════════════════════════════════════


class TestShouldTriggerTier3:
    """_should_trigger_tier3 skips expensive LLM call when one domain dominates."""

    def setup_method(self):
        from pipeline.rag_pipeline import _should_trigger_tier3
        self.fn = _should_trigger_tier3

    def test_high_confidence_never_triggers(self):
        routing = {"confidence": 0.70, "probabilities": {"kehoach": 0.70, "ctdt": 0.10}}
        assert self.fn(routing) is False

    def test_low_conf_no_probs_triggers(self):
        """No probabilities available → fall back to absolute threshold."""
        routing = {"confidence": 0.40, "probabilities": {}}
        assert self.fn(routing) is True

    def test_low_conf_dominant_domain_skips(self):
        """kehoach=0.531, ctdt=0.180 → margin=0.351 ≥ 0.25 → skip."""
        routing = {
            "confidence": 0.531,
            "probabilities": {
                "kehoach": 0.531, "ctdt": 0.180, "quydinh": 0.169, "stsv": 0.092
            },
        }
        assert self.fn(routing) is False, (
            "Should skip Tier-3 when dominant domain has large margin"
        )

    def test_low_conf_ambiguous_domains_triggers(self):
        """kehoach=0.40, ctdt=0.35 → margin=0.05 < 0.25 → trigger."""
        routing = {
            "confidence": 0.40,
            "probabilities": {"kehoach": 0.40, "ctdt": 0.35, "quydinh": 0.15, "stsv": 0.10},
        }
        assert self.fn(routing) is True, (
            "Should run Tier-3 when two domains are close"
        )

    def test_exactly_at_confidence_threshold_does_not_trigger(self):
        routing = {"confidence": 0.55, "probabilities": {"kehoach": 0.55, "ctdt": 0.20}}
        assert self.fn(routing) is False  # >= threshold → no Tier-3

    def test_margin_exactly_at_boundary(self):
        """Margin == _TIER3_DOMINANT_DOMAIN_MARGIN → skip (≥, not >)."""
        routing = {
            "confidence": 0.40,
            "probabilities": {"kehoach": 0.50, "ctdt": 0.25},  # margin=0.25
        }
        assert self.fn(routing) is False

    def test_single_domain_no_second_triggers(self):
        """Only one domain in probs → len < 2 → no margin check → trigger."""
        routing = {"confidence": 0.40, "probabilities": {"kehoach": 0.40}}
        assert self.fn(routing) is True


# ═══════════════════════════════════════════════════════════════════════════════
# P2 — Normalize query before classification
# ═══════════════════════════════════════════════════════════════════════════════


class TestNormalizeQueryForClassification:
    def setup_method(self):
        from query.router import _normalize_query_for_classification
        self.fn = _normalize_query_for_classification

    def test_strips_whitespace(self):
        assert self.fn("  lịch thi  ") == "lịch thi"

    def test_nfc_normalization(self):
        # Decomposed form: 'i' + combining dot below (U+0323) + combining grave (U+0300)
        decomposed = "li\u0323\u0300ch thi"  # "lịch thi" in NFD
        result = self.fn(decomposed)
        import unicodedata
        assert unicodedata.is_normalized("NFC", result)

    def test_idempotent_on_normal_query(self):
        q = "lịch thi giữa kỳ 20252"
        assert self.fn(q) == q

    def test_typo_query_is_stripped(self):
        # Leading typo: missing 'l' → starts with 'ị'
        result = self.fn("  ịch thi giữa kì 20252  ")
        assert result == "ịch thi giữa kì 20252"

    def test_router_uses_normalization(self):
        """_route_classifier should call _normalize before predict."""
        from query.router import QueryRouter
        router = QueryRouter(mode="classifier")
        mock_clf = MagicMock()
        mock_clf.predict.return_value = {
            "intent": "rag", "domain": "kehoach", "domains": ["kehoach"],
            "confidence": 0.80, "label": "kehoach", "probabilities": {"kehoach": 0.80},
        }
        router._classifier = mock_clf

        router.route("  lịch thi  ", chat_history=None)

        # Classifier must be called with stripped input
        called_with = mock_clf.predict.call_args[0][0]
        assert called_with == "lịch thi", f"Expected stripped query, got: {called_with!r}"


# ═══════════════════════════════════════════════════════════════════════════════
# P1 — Reflection hallucination guardrail
# ═══════════════════════════════════════════════════════════════════════════════


class TestReflectionHallucinationGuard:
    """Reflection must NOT inject major/cohort when the query has no profile ref
    and no authenticated profile is provided."""

    def _make_reflector(self, llm_response: str):
        """Return a QueryReflector whose LLM is stubbed."""
        from query.reflection import QueryReflector

        mock_settings = MagicMock()
        mock_settings.reflection_model = "stub"
        mock_settings.reflection_temperature = 0.0
        mock_settings.reflection_max_tokens = 256
        mock_settings.reflection_provider = "gemini"
        mock_settings.google_api_key = "fake"
        mock_settings.lm_studio_base_url = ""
        mock_settings.ollama_base_url = ""
        mock_settings.openai_api_key = ""

        reflector = QueryReflector(settings=mock_settings)

        # Stub out the OpenAI client
        mock_response = MagicMock()
        mock_response.choices[0].message.content = llm_response
        reflector._client = MagicMock()
        reflector._client.chat.completions.create.return_value = mock_response
        return reflector

    def test_no_hallucination_when_profile_absent_and_no_personal_ref(self):
        """Generic query + no profile → LLM hallucination → guardrail reverts."""
        reflector = self._make_reflector(
            # LLM hallucinating IT-E6 and K67 (not in original query)
            "Lịch thi giữa kỳ của sinh viên ngành Công nghệ thông tin Việt - Nhật (IT-E6) khóa K67 là gì?"
        )
        result = reflector.reflect("lịch thi giữa kì", user_context=None)
        rewritten = result["rewritten"]
        assert "IT-E6" not in rewritten, f"Major should not be injected: {rewritten}"
        assert "K67" not in rewritten, f"Cohort should not be injected: {rewritten}"
        # Should revert to original
        assert rewritten == "lịch thi giữa kì"

    def test_profile_injection_allowed_when_personal_ref_present(self):
        """Query with 'ngành của tôi' + profile → injection IS expected."""
        reflector = self._make_reflector(
            "Lịch thi giữa kỳ ngành Công nghệ thông tin Việt - Nhật (IT-E6) là gì?"
        )
        profile = {"major": "Công nghệ thông tin Việt - Nhật", "major_code": "IT-E6"}
        result = reflector.reflect("lịch thi ngành của tôi", user_context=profile)
        # The guardrail should NOT revert because query has personal reference
        rewritten = result["rewritten"]
        assert "IT-E6" in rewritten, f"Major should be kept when personal ref present: {rewritten}"

    def test_profile_injection_allowed_when_profile_provided(self):
        """Even without personal reference, if profile exists, guardrail stays quiet."""
        reflector = self._make_reflector(
            "Lịch thi giữa kỳ ngành Công nghệ thông tin Việt - Nhật (IT-E6) là gì?"
        )
        # Profile IS provided
        profile = {"major": "Công nghệ thông tin Việt - Nhật", "major_code": "IT-E6"}
        result = reflector.reflect("lịch thi giữa kì", user_context=profile)
        # When a real profile is provided, we trust it
        rewritten = result["rewritten"]
        assert "IT-E6" in rewritten, (
            f"Major from real profile should be kept: {rewritten}"
        )

    def test_comparison_followup_preserves_recent_tuition_topic(self):
        """Short comparison follow-up must inherit the latest user topic."""
        reflector = self._make_reflector(
            "So sánh ngoại ngữ giữa ME-GU và IT-E6"
        )
        profile = {"major": "Công nghệ thông tin Việt - Nhật", "major_code": "IT-E6"}
        history = [
            {"role": "user", "content": "ME-GU có học phí là bao nhiêu?"},
            {"role": "assistant", "content": "Học phí ME-GU là ..."},
        ]

        result = reflector.reflect(
            "so với ngành của tôi",
            chat_history=history,
            user_context=profile,
        )

        assert result["rewritten"] == "So sánh học phí giữa ME-GU và IT-E6"

    def test_comparison_followup_current_topic_beats_bad_previous_answer(self):
        """Current topic clarifications should not reuse a wrong assistant topic."""
        reflector = self._make_reflector(
            "So sánh ngoại ngữ giữa ME-GU và IT-E6"
        )
        profile = {"major": "Công nghệ thông tin Việt - Nhật", "major_code": "IT-E6"}
        history = [
            {"role": "user", "content": "ME-GU có học phí là bao nhiêu?"},
            {"role": "assistant", "content": "Học phí ME-GU là ..."},
            {"role": "user", "content": "so với ngành của tôi"},
            {"role": "assistant", "content": "So sánh ngoại ngữ giữa ME-GU và IT-E6 ..."},
        ]

        result = reflector.reflect(
            "so về học phí",
            chat_history=history,
            user_context=profile,
        )

        assert result["rewritten"] == "So sánh học phí giữa ME-GU và IT-E6"

    def test_standalone_comparison_keeps_current_major_pair(self):
        """A complete current comparison should not inherit stale history majors."""
        reflector = self._make_reflector(
            "So sánh học phí giữa ME-GU và IT-E6"
        )
        history = [
            {"role": "user", "content": "So sánh học phí giữa IT1 và IT2"},
            {"role": "assistant", "content": "IT1 và IT2 khác nhau ..."},
        ]

        result = reflector.reflect(
            "So sánh học phí giữa ME-GU và IT-E6",
            chat_history=history,
            user_context={"major_code": "IT2"},
        )

        assert result["rewritten"] == "So sánh học phí giữa ME-GU và IT-E6"

    def test_no_revert_when_llm_improves_without_hallucination(self):
        """LLM expanding 'lịch thi HK 20252' → no major injected → keep it."""
        reflector = self._make_reflector(
            "Lịch thi giữa kỳ học kỳ 20252 là gì?"
        )
        result = reflector.reflect("lịch thi HK 20252", user_context=None)
        rewritten = result["rewritten"]
        # No major was injected, so the improved rewrite is kept
        assert rewritten == "Lịch thi giữa kỳ học kỳ 20252 là gì?"


# ═══════════════════════════════════════════════════════════════════════════════
# P0 — Pre-retrieval query cache
# ═══════════════════════════════════════════════════════════════════════════════


class TestQueryOnlyCache:
    """LLMResponseCache.get_by_query / put_by_query round-trip using fakeredis."""

    def _make_cache(self):
        pytest.importorskip("fakeredis", reason="fakeredis required for this test")
        import fakeredis
        from cache.llm_cache import LLMResponseCache
        r = fakeredis.FakeRedis(decode_responses=True)
        return LLMResponseCache(redis_client=r)

    def test_miss_before_put(self):
        cache = self._make_cache()
        result = cache.get_by_query("lịch thi giữa kì", "gemini-flash")
        assert result is None

    def test_hit_after_put(self):
        cache = self._make_cache()
        sources = [{"id": "doc1", "text": "Lịch thi", "score": 0.9}]
        cache.put_by_query("lịch thi giữa kì", "gemini-flash", "Câu trả lời mẫu", sources)

        result = cache.get_by_query("lịch thi giữa kì", "gemini-flash")
        assert result is not None
        assert result["answer"] == "Câu trả lời mẫu"
        assert len(result["sources"]) == 1

    def test_key_is_case_and_space_insensitive(self):
        """Normalized query should match regardless of leading/trailing spaces."""
        cache = self._make_cache()
        cache.put_by_query("lịch thi giữa kì", "gemini-flash", "Answer A", [])
        result = cache.get_by_query("  Lịch thi giữa kì  ", "gemini-flash")
        # Different case/spaces should still miss (normalization only strips+lower)
        # lower() is applied so this should HIT
        assert result is not None

    def test_different_model_is_separate_key(self):
        cache = self._make_cache()
        cache.put_by_query("lịch thi", "model-A", "Answer A", [])
        result = cache.get_by_query("lịch thi", "model-B")
        assert result is None

    def test_put_by_query_key_different_from_main_cache_key(self):
        """Query-only key must not collide with the doc-id-based key."""
        from cache.llm_cache import LLMResponseCache
        q = "lịch thi giữa kì"
        model = "gemini"
        doc_ids = ["doc1", "doc2"]
        key_full = LLMResponseCache._build_key(q, doc_ids, model)
        key_query = LLMResponseCache._build_query_only_key(q, model)
        assert key_full != key_query

    def test_rag_flow_returns_early_on_query_cache_hit(self):
        """rag_flow should skip reflection+retrieval when get_by_query hits."""
        from pipeline.flows import rag_flow

        mock_cache = MagicMock()
        mock_cache.get_by_query.return_value = {
            "answer": "Cached answer",
            "sources": [{"id": "doc1"}],
            "model_name": "stub",
            "cached_at": "2026-05-10T00:00:00Z",
        }

        mock_reflector = MagicMock()
        mock_bge = MagicMock()
        mock_e5 = MagicMock()
        mock_searcher = MagicMock()
        mock_reranker = MagicMock()
        mock_chat = MagicMock()
        mock_chat.model = "stub"

        result = rag_flow(
            question="lịch thi giữa kì",
            history=None,
            reflector=mock_reflector,
            bge_embedder=mock_bge,
            e5_embedder=mock_e5,
            searcher=mock_searcher,
            reranker=mock_reranker,
            chat_model=mock_chat,
            self_evaluator=None,
            tavily_tool=None,
            cfg={"top_k": 5},
            llm_cache=mock_cache,
        )

        assert result["answer"] == "Cached answer"
        assert result.get("query_cache_hit") is True
        # Reflector and embedders must NOT be called (early return)
        mock_reflector.reflect.assert_not_called()
        mock_bge.embed_query.assert_not_called()
        mock_searcher.search.assert_not_called()
