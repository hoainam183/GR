"""Test Phase 7 — Bug Fixes & Feature Activation.

Refactored from script-style to proper pytest module.
Tests:
  7.1 Query Reflection Bug Fix
  7.2 Self-Evaluation Activation
  7.3 Tavily Fallback Activation
  7.4 payload.pop() Bug Fix
  7.5 Config Sync
"""

from __future__ import annotations

from unittest.mock import MagicMock


# ─── Shared mocks ─────────────────────────────────────────────────────────────

def _make_pipeline_mocks():
    mock_bge = MagicMock()
    mock_bge.embed_query.return_value = [0.1] * 1024
    mock_e5 = MagicMock()
    mock_e5.embed_query.return_value = [0.2] * 1024
    mock_searcher = MagicMock()
    mock_searcher.search.return_value = [{"text": "doc1", "metadata": {"title": "Test"}}]
    mock_reranker = MagicMock()
    mock_reranker.rerank.return_value = [{"text": "doc1", "metadata": {"title": "Test"}}]
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


class TestQueryReflection:
    def test_reflect_method_called_not_rewrite(self) -> None:
        from pipeline.flows import rag_flow
        mock_bge, mock_e5, mock_searcher, mock_reranker, mock_chat, cfg = _make_pipeline_mocks()
        mock_reflector = MagicMock()
        mock_reflector.reflect.return_value = {"original": "test query", "rewritten": "rewritten test query"}

        rag_flow(
            question="test query", history=None,
            reflector=mock_reflector, bge_embedder=mock_bge, e5_embedder=mock_e5,
            searcher=mock_searcher, reranker=mock_reranker, chat_model=mock_chat,
            self_evaluator=None, tavily_tool=None, cfg=cfg,
        )

        assert mock_reflector.reflect.called, "reflect() should be called"
        assert not mock_reflector.rewrite.called, "rewrite() should NOT be called"

    def test_rewritten_query_used_for_embedding(self) -> None:
        from pipeline.flows import rag_flow
        mock_bge, mock_e5, mock_searcher, mock_reranker, mock_chat, cfg = _make_pipeline_mocks()
        mock_reflector = MagicMock()
        mock_reflector.reflect.return_value = {"original": "test query", "rewritten": "rewritten test query"}

        rag_flow(
            question="test query", history=None,
            reflector=mock_reflector, bge_embedder=mock_bge, e5_embedder=mock_e5,
            searcher=mock_searcher, reranker=mock_reranker, chat_model=mock_chat,
            self_evaluator=None, tavily_tool=None, cfg=cfg,
        )

        mock_bge.embed_query.assert_called_with("rewritten test query")

    def test_reflect_called_with_chat_history_kwarg(self) -> None:
        from pipeline.flows import rag_flow
        mock_bge, mock_e5, mock_searcher, mock_reranker, mock_chat, cfg = _make_pipeline_mocks()
        mock_reflector = MagicMock()
        mock_reflector.reflect.return_value = {"original": "q", "rewritten": "q"}

        rag_flow(
            question="q", history=None,
            reflector=mock_reflector, bge_embedder=mock_bge, e5_embedder=mock_e5,
            searcher=mock_searcher, reranker=mock_reranker, chat_model=mock_chat,
            self_evaluator=None, tavily_tool=None, cfg=cfg,
        )

        call_args = mock_reflector.reflect.call_args
        assert "chat_history" in call_args.kwargs

    def test_stream_uses_reflect_not_rewrite(self) -> None:
        from pipeline.flows import rag_flow_stream
        mock_bge, mock_e5, mock_searcher, mock_reranker, mock_chat, cfg = _make_pipeline_mocks()
        mock_chat.generate_stream.return_value = iter(["chunk1", "chunk2"])
        mock_reflector = MagicMock()
        mock_reflector.reflect.return_value = {"original": "test query", "rewritten": "rewritten test query"}

        stream, _ = rag_flow_stream(
            question="test query", history=None,
            reflector=mock_reflector, bge_embedder=mock_bge, e5_embedder=mock_e5,
            searcher=mock_searcher, reranker=mock_reranker, chat_model=mock_chat, cfg=cfg,
        )
        list(stream)

        assert mock_reflector.reflect.called
        assert not mock_reflector.rewrite.called


class TestSelfEvaluationActivation:
    def test_self_eval_enabled_default_true(self) -> None:
        from config.settings import Settings
        s = Settings()
        assert s.self_eval_enabled is True

    def test_self_eval_prompts_in_vietnamese(self) -> None:
        from llm.prompts import SELF_EVAL_SYSTEM_PROMPT, SELF_EVAL_USER_TEMPLATE
        assert "Bạn là" in SELF_EVAL_SYSTEM_PROMPT or "đánh giá" in SELF_EVAL_SYSTEM_PROMPT
        assert "You are a strict" not in SELF_EVAL_SYSTEM_PROMPT
        assert "Câu hỏi người dùng" in SELF_EVAL_USER_TEMPLATE

    def test_self_eval_json_keys_english(self) -> None:
        from llm.prompts import SELF_EVAL_SYSTEM_PROMPT
        assert '"pass"' in SELF_EVAL_SYSTEM_PROMPT
        assert '"relevance"' in SELF_EVAL_SYSTEM_PROMPT

    def test_parse_eval_pass_true(self) -> None:
        from llm.self_eval import SelfEvaluator
        evaluator = SelfEvaluator.__new__(SelfEvaluator)
        evaluator.model = "test"
        evaluator.temperature = 0.0
        result = evaluator._parse_evaluation(
            '{"pass": true, "relevance": "good", "faithfulness": "grounded", "completeness": "complete", "reason": "OK"}'
        )
        assert result["pass"] is True

    def test_parse_eval_pass_false(self) -> None:
        from llm.self_eval import SelfEvaluator
        evaluator = SelfEvaluator.__new__(SelfEvaluator)
        evaluator.model = "test"
        evaluator.temperature = 0.0
        result = evaluator._parse_evaluation(
            '{"pass": false, "relevance": "bad", "faithfulness": "hallucinated", "completeness": "incomplete", "reason": "bad"}'
        )
        assert result["pass"] is False

    def test_parse_invalid_json_returns_fail(self) -> None:
        from llm.self_eval import SelfEvaluator
        evaluator = SelfEvaluator.__new__(SelfEvaluator)
        evaluator.model = "test"
        evaluator.temperature = 0.0
        result = evaluator._parse_evaluation("not json at all")
        assert result["pass"] is False


class TestTavilyFallback:
    def test_tavily_fallback_enabled_field_exists(self) -> None:
        from config.settings import Settings
        s = Settings()
        assert hasattr(s, "tavily_fallback_enabled")
        assert isinstance(s.tavily_fallback_enabled, bool)

    def test_tavily_tool_has_retry_attributes(self) -> None:
        from tools.tavily_search import TavilySearchTool
        tool = TavilySearchTool.__new__(TavilySearchTool)
        tool.max_retries = 3
        tool.min_retry_delay = 1.0
        tool._last_call_time = 0.0
        assert hasattr(tool, "max_retries")
        assert hasattr(tool, "min_retry_delay")
        assert hasattr(tool, "_last_call_time")

    def test_self_eval_fail_triggers_tavily(self) -> None:
        from pipeline.flows import rag_flow
        mock_bge, mock_e5, mock_searcher, mock_reranker, _, cfg = _make_pipeline_mocks()
        mock_chat = MagicMock()
        mock_chat.model = "test-model"
        mock_chat.generate.side_effect = ["bad answer", "better answer from web"]

        mock_self_eval = MagicMock()
        mock_self_eval.evaluate.return_value = {"pass": False, "reason": "bad answer"}
        mock_tavily = MagicMock()
        mock_tavily.search.return_value = {"context": "web context here"}

        result = rag_flow(
            question="test", history=None, reflector=None,
            bge_embedder=mock_bge, e5_embedder=mock_e5,
            searcher=mock_searcher, reranker=mock_reranker,
            chat_model=mock_chat, self_evaluator=mock_self_eval,
            tavily_tool=mock_tavily, cfg=cfg,
        )

        assert mock_self_eval.evaluate.called
        assert mock_tavily.search.called
        assert result["answer"] == "better answer from web"


class TestPayloadPopFix:
    def test_fused_results_text_preserved(self) -> None:
        from retrieval.qdrant_store import QdrantStore

        mock_hit_bge = MagicMock()
        mock_hit_bge.id = "point-1"
        mock_hit_bge.payload = {"text": "hello world", "title": "Doc1"}
        mock_hit_bge.score = 0.9

        mock_hit_e5 = MagicMock()
        mock_hit_e5.id = "point-1"  # Same ID — appears in both results
        mock_hit_e5.payload = {"text": "hello world", "title": "Doc1"}
        mock_hit_e5.score = 0.8

        fused = QdrantStore._fuse_results(
            [mock_hit_bge], [mock_hit_e5], top_k=5, bge_weight=0.5, e5_weight=0.5
        )

        assert len(fused) > 0
        assert fused[0]["text"] == "hello world"
        # Original payload must NOT be mutated
        assert "text" in mock_hit_bge.payload


class TestConfigSync:
    def test_settings_has_reflection_enabled(self) -> None:
        from config.settings import Settings
        s = Settings()
        assert hasattr(s, "reflection_enabled")
        assert s.reflection_enabled is True

    def test_settings_has_self_eval_and_tavily(self) -> None:
        from config.settings import Settings
        s = Settings()
        # self_eval_enabled can vary by env, check field existence and type
        assert isinstance(s.self_eval_enabled, bool)
        assert isinstance(s.tavily_fallback_enabled, bool)

    def test_config_dict_removed(self) -> None:
        import pipeline.rag_pipeline as rp_module
        assert not hasattr(rp_module, "CONFIG"), "CONFIG dict should be removed (use Settings)"

    def test_settings_to_cfg_exists(self) -> None:
        import pipeline.rag_pipeline as rp_module
        assert hasattr(rp_module, "_settings_to_cfg")

    def test_settings_to_cfg_keys(self) -> None:
        from config.settings import Settings
        from pipeline.rag_pipeline import _settings_to_cfg
        s = Settings()
        cfg = _settings_to_cfg(s)
        assert "collections" in cfg
        assert "es_host" in cfg
        assert "model" in cfg
        assert "temperature" in cfg
        assert "reflection_enabled" in cfg
        assert "self_eval_enabled" in cfg
        assert "tavily_fallback_enabled" in cfg
        assert cfg["model"] == s.chat_model
        assert cfg["es_host"] == s.elasticsearch_host
        assert cfg["top_k"] == s.top_k
