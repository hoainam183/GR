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
    def test_self_eval_fields_and_bge_logit_threshold(self) -> None:
        from config.settings import Settings
        s = Settings()
        assert isinstance(s.self_eval_enabled, bool)
        assert Settings.model_fields["self_eval_min_top_score"].default == 100.0

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
        assert result["answer_status"] == "answered"
        assert result["should_web_search"] is False

    def test_parse_eval_pass_false(self) -> None:
        from llm.self_eval import SelfEvaluator
        evaluator = SelfEvaluator.__new__(SelfEvaluator)
        evaluator.model = "test"
        evaluator.temperature = 0.0
        result = evaluator._parse_evaluation(
            '{"pass": false, "relevance": "bad", "faithfulness": "hallucinated", "completeness": "incomplete", "reason": "bad"}'
        )
        assert result["pass"] is False
        assert result["answer_status"] == "insufficient"
        assert result["should_web_search"] is True

    def test_parse_eval_structured_web_search_fields(self) -> None:
        from llm.self_eval import SelfEvaluator
        evaluator = SelfEvaluator.__new__(SelfEvaluator)
        evaluator.model = "test"
        evaluator.temperature = 0.0
        result = evaluator._parse_evaluation(
            '{"pass": true, "relevance": "good", "faithfulness": "grounded", '
            '"completeness": "partial", "answer_status": "stale_risk", '
            '"should_web_search": true, "web_search_query": "site:ctt.hust.edu.vn test", '
            '"reason": "dynamic"}'
        )
        assert result["pass"] is True
        assert result["answer_status"] == "stale_risk"
        assert result["should_web_search"] is True
        assert result["web_search_query"] == "site:ctt.hust.edu.vn test"

    def test_parse_invalid_json_returns_fail(self) -> None:
        from llm.self_eval import SelfEvaluator
        evaluator = SelfEvaluator.__new__(SelfEvaluator)
        evaluator.model = "test"
        evaluator.temperature = 0.0
        result = evaluator._parse_evaluation("not json at all")
        assert result["pass"] is False
        assert result["should_web_search"] is True


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

    def test_self_eval_web_request_triggers_tavily(self) -> None:
        from pipeline.flows import rag_flow
        mock_bge, mock_e5, mock_searcher, mock_reranker, _, cfg = _make_pipeline_mocks()
        cfg.update({
            "tavily_fallback_enabled": True,
            "tavily_max_results": 2,
            "tavily_search_depth": "advanced",
        })
        mock_chat = MagicMock()
        mock_chat.model = "test-model"
        mock_chat.generate.side_effect = ["bad answer", "better answer from web"]

        mock_self_eval = MagicMock()
        mock_self_eval.evaluate.return_value = {
            "pass": False,
            "answer_status": "insufficient",
            "should_web_search": True,
            "web_search_query": "HUST test",
            "reason": "bad answer",
        }
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
        assert mock_tavily.search.call_args.kwargs["max_results"] == 2
        assert mock_tavily.search.call_args.kwargs["search_depth"] == "advanced"
        assert result["answer"] == "better answer from web"
        assert result["tools_used"] == ["tavily_search"]
        assert result["tool_calls"][0]["args"]["query"] == "HUST test"

    def test_self_eval_web_request_respects_tavily_disabled(self) -> None:
        from pipeline.flows import rag_flow
        mock_bge, mock_e5, mock_searcher, mock_reranker, _, cfg = _make_pipeline_mocks()
        cfg["tavily_fallback_enabled"] = False
        mock_chat = MagicMock()
        mock_chat.model = "test-model"
        mock_chat.generate.return_value = "bad answer"

        mock_self_eval = MagicMock()
        mock_self_eval.evaluate.return_value = {
            "pass": False,
            "answer_status": "insufficient",
            "should_web_search": True,
            "reason": "bad answer",
        }
        mock_tavily = MagicMock()

        result = rag_flow(
            question="test", history=None, reflector=None,
            bge_embedder=mock_bge, e5_embedder=mock_e5,
            searcher=mock_searcher, reranker=mock_reranker,
            chat_model=mock_chat, self_evaluator=mock_self_eval,
            tavily_tool=mock_tavily, cfg=cfg,
        )

        assert mock_self_eval.evaluate.called
        assert not mock_tavily.search.called
        assert result["answer"] == "bad answer"
        assert result["timings_ms"]["tavily_skipped"] == 1.0

    def test_self_eval_fail_without_web_request_does_not_call_tavily(self) -> None:
        from pipeline.flows import rag_flow
        mock_bge, mock_e5, mock_searcher, mock_reranker, _, cfg = _make_pipeline_mocks()
        cfg["tavily_fallback_enabled"] = True
        mock_chat = MagicMock()
        mock_chat.model = "test-model"
        mock_chat.generate.return_value = "possibly incomplete answer"

        mock_self_eval = MagicMock()
        mock_self_eval.evaluate.return_value = {"pass": False, "reason": "bad answer"}
        mock_tavily = MagicMock()

        result = rag_flow(
            question="test", history=None, reflector=None,
            bge_embedder=mock_bge, e5_embedder=mock_e5,
            searcher=mock_searcher, reranker=mock_reranker,
            chat_model=mock_chat, self_evaluator=mock_self_eval,
            tavily_tool=mock_tavily, cfg=cfg,
        )

        assert mock_self_eval.evaluate.called
        assert not mock_tavily.search.called
        assert result["answer"] == "possibly incomplete answer"
        assert result["answer_quality_gate"]["informational_notes"] == [
            "self_eval_failed"
        ]

    def test_no_info_answer_triggers_tavily_without_hardcoded_query(self) -> None:
        from pipeline.flows import rag_flow
        mock_bge, mock_e5, mock_searcher, mock_reranker, _, cfg = _make_pipeline_mocks()
        cfg.update({
            "tavily_fallback_enabled": True,
            "tavily_max_results": 2,
            "tavily_search_depth": "basic",
        })
        mock_chat = MagicMock()
        mock_chat.model = "test-model"
        mock_chat.generate.side_effect = [
            "Tôi không tìm thấy thông tin này trong tài liệu hiện có.",
            "answer from official web",
        ]
        mock_tavily = MagicMock()
        mock_tavily.search.return_value = {
            "context": "official web context",
            "results": [
                {
                    "title": "Official notice",
                    "url": "https://ctt.hust.edu.vn/test",
                    "content": "official web context",
                }
            ],
        }

        result = rag_flow(
            question="câu hỏi thông tin mới", history=None, reflector=None,
            bge_embedder=mock_bge, e5_embedder=mock_e5,
            searcher=mock_searcher, reranker=mock_reranker,
            chat_model=mock_chat, self_evaluator=None,
            tavily_tool=mock_tavily, cfg=cfg,
        )

        assert mock_tavily.search.called
        assert result["answer"] == "answer from official web"
        assert result["timings_ms"]["web_fallback_used"] == 1.0
        assert result["answer_quality_gate"]["reasons"] == ["answer_no_info"]
        assert result["sources"][0]["collection"] == "web"
        assert result["sources"][0]["metadata"]["provider"] == "tavily"

    def test_answer_ok_does_not_call_tavily(self) -> None:
        from pipeline.flows import rag_flow
        mock_bge, mock_e5, mock_searcher, mock_reranker, mock_chat, cfg = _make_pipeline_mocks()
        cfg["tavily_fallback_enabled"] = True
        mock_chat.generate.return_value = "Đây là câu trả lời có căn cứ."
        mock_self_eval = MagicMock()
        mock_self_eval.evaluate.return_value = {
            "pass": True,
            "answer_status": "answered",
            "should_web_search": False,
            "reason": "ok",
        }
        mock_tavily = MagicMock()

        result = rag_flow(
            question="học phần X là gì", history=None, reflector=None,
            bge_embedder=mock_bge, e5_embedder=mock_e5,
            searcher=mock_searcher, reranker=mock_reranker,
            chat_model=mock_chat, self_evaluator=mock_self_eval,
            tavily_tool=mock_tavily, cfg=cfg,
        )

        assert result["answer"] == "Đây là câu trả lời có căn cứ."
        assert not mock_tavily.search.called
        assert result["tools_used"] == []

    def test_dynamic_collection_bypasses_query_cache(self) -> None:
        from pipeline.flows import rag_flow
        mock_bge, mock_e5, mock_searcher, mock_reranker, mock_chat, cfg = _make_pipeline_mocks()
        cfg.update({
            "tavily_fallback_enabled": False,
            "collections": ["stsv", "quydinh", "kehoach", "ctdt"],
        })
        mock_cache = MagicMock()
        mock_cache.get_by_query.return_value = {
            "answer": "cached stale answer",
            "sources": [],
        }
        routing_result = {
            "intent": "rag",
            "domain": "kehoach",
            "domains": ["kehoach"],
            "confidence": 0.9,
            "probabilities": {"kehoach": 0.9},
        }

        rag_flow(
            question="kế hoạch học kỳ hè", history=None, reflector=None,
            bge_embedder=mock_bge, e5_embedder=mock_e5,
            searcher=mock_searcher, reranker=mock_reranker,
            chat_model=mock_chat, self_evaluator=None,
            tavily_tool=None, cfg=cfg, routing_result=routing_result,
            llm_cache=mock_cache,
        )

        assert not mock_cache.get_by_query.called
        assert not mock_cache.get.called
        assert not mock_cache.put_by_query.called

    def test_dynamic_kehoach_query_calls_tavily_without_case_hardcode(self) -> None:
        from pipeline.flows import rag_flow
        mock_bge, mock_e5, mock_searcher, mock_reranker, _, cfg = _make_pipeline_mocks()
        cfg.update({
            "tavily_fallback_enabled": True,
            "collections": ["stsv", "quydinh", "kehoach", "ctdt"],
        })
        mock_chat = MagicMock()
        mock_chat.model = "test-model"
        mock_chat.generate.side_effect = [
            "Khóa K70 sẽ không mở đăng ký học kỳ hè 20253.",
            "answer from ctt",
        ]
        mock_tavily = MagicMock()
        mock_tavily.search.return_value = {
            "context": "ctt official context",
            "results": [
                {
                    "title": "Kế hoạch học GDPQ",
                    "url": "https://ctt.hust.edu.vn/post",
                    "content": "ctt official context",
                }
            ],
        }
        routing_result = {
            "intent": "rag",
            "domain": "kehoach",
            "domains": ["kehoach"],
            "confidence": 0.9,
            "probabilities": {"kehoach": 0.9},
        }

        result = rag_flow(
            question="kế hoạch học GDPQ kì hè K70", history=None, reflector=None,
            bge_embedder=mock_bge, e5_embedder=mock_e5,
            searcher=mock_searcher, reranker=mock_reranker,
            chat_model=mock_chat, self_evaluator=None,
            tavily_tool=mock_tavily, cfg=cfg, routing_result=routing_result,
        )

        assert mock_tavily.search.called
        assert mock_tavily.search.call_args.args[0] == "HUST kế hoạch học GDPQ kì hè K70"
        assert "dynamic_query" in result["answer_quality_gate"]["pre_generation_reasons"]
        assert result["answer"] == "Khóa K70 sẽ không mở đăng ký học kỳ hè 20253."

    def test_freshness_query_keeps_local_sources_before_tavily_sources(self) -> None:
        from pipeline.flows import rag_flow

        mock_bge, mock_e5, mock_searcher, mock_reranker, _, cfg = _make_pipeline_mocks()
        cfg.update({
            "tavily_fallback_enabled": True,
            "collections": ["stsv", "quydinh", "kehoach", "ctdt"],
        })
        local_doc = {
            "id": "kehoach-latest",
            "text": "Local latest semester schedule.",
            "score": 0.95,
            "collection": "kehoach",
            "metadata": {
                "title": "Local latest plan",
                "date_str": "20/4/2026",
                "source": "ctt-local",
            },
        }

        def _search_side_effect(**kwargs):
            trace = kwargs.get("trace_out")
            if isinstance(trace, dict):
                trace["filters"] = {
                    "kehoach": {
                        "applied": True,
                        "matched_ids": 1,
                        "filter_desc": "freshness_sort_date_str (1 latest IDs)",
                    }
                }
                trace["collection_counts"] = {"kehoach": {"vector": 1, "keyword": 1}}
            return [local_doc]

        mock_searcher.search.side_effect = _search_side_effect
        mock_reranker.rerank.return_value = [local_doc]
        mock_chat = MagicMock()
        mock_chat.model = "test-model"
        mock_chat.generate.return_value = "answer from local plus web context"
        mock_tavily = MagicMock()
        mock_tavily.search.return_value = {
            "context": "web live context",
            "results": [
                {
                    "title": "Web notice",
                    "url": "https://ctt.hust.edu.vn/web",
                    "content": "web live context",
                }
            ],
        }
        routing_result = {
            "intent": "rag",
            "domain": "kehoach",
            "domains": ["kehoach"],
            "confidence": 0.9,
            "probabilities": {"kehoach": 0.9},
        }

        result = rag_flow(
            question="Lich trinh hoc ky moi nhat?", history=None, reflector=None,
            bge_embedder=mock_bge, e5_embedder=mock_e5,
            searcher=mock_searcher, reranker=mock_reranker,
            chat_model=mock_chat, self_evaluator=None,
            tavily_tool=mock_tavily, cfg=cfg, routing_result=routing_result,
        )

        assert mock_searcher.search.call_args.kwargs["active_collections"] == ["kehoach"]
        assert mock_tavily.search.called
        assert result["sources"][0]["collection"] == "kehoach"
        assert result["sources"][1]["collection"] == "web"
        assert result["collection_results"] == {"kehoach": {"vector": 1, "keyword": 1}}
        gate = result["answer_quality_gate"]
        assert "freshness_query" in gate["pre_generation_reasons"]
        assert gate["pre_generation_freshness_query"] is True
        assert result["tools_used"] == ["tavily_search"]

        context = mock_chat.generate.call_args.kwargs["context"]
        assert context.index("Local latest semester schedule.") < context.index(
            "web live context"
        )
        assert "web_live_context" in context

    def test_freshness_stream_metadata_matches_non_stream_trace_shape(self) -> None:
        from pipeline.flows import rag_flow_stream

        mock_bge, mock_e5, mock_searcher, mock_reranker, _, cfg = _make_pipeline_mocks()
        cfg.update({
            "tavily_fallback_enabled": True,
            "collections": ["stsv", "quydinh", "kehoach", "ctdt"],
        })
        local_doc = {
            "id": "kehoach-latest",
            "text": "Local latest semester schedule.",
            "score": 0.95,
            "collection": "kehoach",
            "metadata": {"title": "Local latest plan", "date_str": "20/4/2026"},
        }

        def _search_side_effect(**kwargs):
            trace = kwargs.get("trace_out")
            if isinstance(trace, dict):
                trace["filters"] = {"kehoach": {"applied": True, "matched_ids": 1}}
                trace["collection_counts"] = {"kehoach": {"vector": 1, "keyword": 1}}
            return [local_doc]

        mock_searcher.search.side_effect = _search_side_effect
        mock_reranker.rerank.return_value = [local_doc]
        mock_chat = MagicMock()
        mock_chat.model = "test-model"
        mock_chat.generate_stream.return_value = iter(["streamed answer"])
        mock_tavily = MagicMock()
        mock_tavily.search.return_value = {
            "context": "web live context",
            "results": [
                {
                    "title": "Web notice",
                    "url": "https://ctt.hust.edu.vn/web",
                    "content": "web live context",
                }
            ],
        }
        metadata = {}
        routing_result = {
            "intent": "rag",
            "domain": "kehoach",
            "domains": ["kehoach"],
            "confidence": 0.9,
            "probabilities": {"kehoach": 0.9},
        }

        stream, sources = rag_flow_stream(
            question="Lich trinh hoc ky moi nhat?", history=None, reflector=None,
            bge_embedder=mock_bge, e5_embedder=mock_e5,
            searcher=mock_searcher, reranker=mock_reranker,
            chat_model=mock_chat, tavily_tool=mock_tavily,
            cfg=cfg, routing_result=routing_result, metadata_out=metadata,
        )

        assert list(stream) == ["streamed answer"]
        assert sources[0]["collection"] == "kehoach"
        assert sources[1]["collection"] == "web"
        gate = metadata["answer_quality_gate"]
        assert gate["freshness_query"] is True
        assert gate["pre_generation_freshness_query"] is True
        assert metadata["collection_results"] == {"kehoach": {"vector": 1, "keyword": 1}}
        assert metadata["tools_used"] == ["tavily_search"]

    def test_no_info_cached_answer_is_ignored(self) -> None:
        from pipeline.flows import rag_flow
        mock_bge, mock_e5, mock_searcher, mock_reranker, mock_chat, cfg = _make_pipeline_mocks()
        mock_chat.generate.return_value = "fresh grounded answer"
        mock_cache = MagicMock()
        mock_cache.get_by_query.return_value = {
            "answer": "Tôi không tìm thấy thông tin này trong tài liệu hiện có.",
            "sources": [],
        }
        mock_cache.get.return_value = None

        result = rag_flow(
            question="học phần X là gì", history=None, reflector=None,
            bge_embedder=mock_bge, e5_embedder=mock_e5,
            searcher=mock_searcher, reranker=mock_reranker,
            chat_model=mock_chat, self_evaluator=None,
            tavily_tool=None, cfg=cfg, llm_cache=mock_cache,
        )

        assert mock_cache.get_by_query.called
        assert mock_searcher.search.called
        assert result["answer"] == "fresh grounded answer"
        assert result["timings_ms"]["query_cache_ignored_no_info"] == 1.0

    def test_cache_stores_final_answer_after_tavily_fallback(self) -> None:
        from pipeline.flows import rag_flow
        mock_bge, mock_e5, mock_searcher, mock_reranker, _, cfg = _make_pipeline_mocks()
        cfg["tavily_fallback_enabled"] = True
        mock_chat = MagicMock()
        mock_chat.model = "test-model"
        mock_chat.generate.side_effect = [
            "Tôi không tìm thấy thông tin này trong tài liệu hiện có.",
            "final web answer",
        ]
        mock_tavily = MagicMock()
        mock_tavily.search.return_value = {
            "context": "web context",
            "results": [
                {
                    "title": "Official source",
                    "url": "https://ctt.hust.edu.vn/source",
                    "content": "web context",
                }
            ],
        }
        mock_cache = MagicMock()
        mock_cache.get_by_query.return_value = None
        mock_cache.get.return_value = None

        result = rag_flow(
            question="câu hỏi mới", history=None, reflector=None,
            bge_embedder=mock_bge, e5_embedder=mock_e5,
            searcher=mock_searcher, reranker=mock_reranker,
            chat_model=mock_chat, self_evaluator=None,
            tavily_tool=mock_tavily, cfg=cfg, llm_cache=mock_cache,
        )

        assert result["answer"] == "final web answer"
        assert mock_cache.put.called
        assert mock_cache.put.call_args.args[3] == "final web answer"
        assert not mock_cache.put_by_query.called

    def test_bge_raw_logit_does_not_skip_self_eval_by_default(self) -> None:
        from pipeline.flows import rag_flow
        mock_bge, mock_e5, mock_searcher, mock_reranker, _, cfg = _make_pipeline_mocks()
        mock_reranker.rerank.return_value = [
            {"text": "doc1", "score": 5.2517, "metadata": {"title": "Test"}}
        ]
        mock_chat = MagicMock()
        mock_chat.model = "test-model"
        mock_chat.generate.return_value = "answer"
        mock_self_eval = MagicMock()
        mock_self_eval.evaluate.return_value = {"pass": True, "reason": "ok"}

        rag_flow(
            question="test", history=None, reflector=None,
            bge_embedder=mock_bge, e5_embedder=mock_e5,
            searcher=mock_searcher, reranker=mock_reranker,
            chat_model=mock_chat, self_evaluator=mock_self_eval,
            tavily_tool=None, cfg=cfg,
        )

        assert mock_self_eval.evaluate.called

    def test_tavily_domain_url_is_normalized_to_domain(self) -> None:
        from tools.tavily_search import _normalize_domains

        assert _normalize_domains(
            ["https://sv-ctt.hust.edu.vn/#/so-tay-sv", "ctt.hust.edu.vn/path"]
        ) == ["sv-ctt.hust.edu.vn", "ctt.hust.edu.vn"]

    def test_tavily_domain_tiers_exclude_news_sites(self) -> None:
        from tools.tavily_search import (
            EDU_DOMAINS,
            HUST_DOMAINS,
            HUST_OFFICIAL_DOMAINS,
        )

        assert "ctt.hust.edu.vn" in HUST_OFFICIAL_DOMAINS
        assert "sv-ctt.hust.edu.vn" in HUST_DOMAINS
        assert EDU_DOMAINS == ["moet.gov.vn"]
        assert "vnexpress.net" not in EDU_DOMAINS

    def test_tavily_search_uses_cache_after_domain_normalization(self) -> None:
        from threading import RLock
        from tools.tavily_search import TavilySearchTool, _SimpleTTLCache

        class InvalidKeyError(Exception):
            pass

        tool = TavilySearchTool.__new__(TavilySearchTool)
        tool._client = MagicMock()
        tool._client.search.return_value = {
            "answer": "answer",
            "results": [
                {
                    "title": "Title",
                    "url": "https://ctt.hust.edu.vn/post",
                    "content": "content",
                }
            ],
        }
        tool._invalid_key_error = InvalidKeyError
        tool.max_results = 3
        tool.max_retries = 1
        tool.min_retry_delay = 0.0
        tool._last_call_time = 0.0
        tool.default_include_domains = None
        tool._cache_lock = RLock()
        tool._cache = _SimpleTTLCache(maxsize=10, ttl_seconds=60)

        first = tool.search(
            "test",
            include_domains=["https://ctt.hust.edu.vn/path"],
        )
        second = tool.search("test", include_domains=["ctt.hust.edu.vn"])

        assert first == second
        assert tool._client.search.call_count == 1


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
        assert "tavily_search_depth" in cfg
        assert "tavily_max_results" in cfg
        assert "web_fallback_on_dynamic" in cfg
        assert cfg["model"] == s.chat_model
        assert cfg["es_host"] == s.elasticsearch_host
        assert cfg["top_k"] == s.top_k

    def test_tavily_fallback_requests_self_evaluator(self) -> None:
        from pipeline.rag_pipeline import _should_enable_self_evaluator

        assert _should_enable_self_evaluator({
            "self_eval_enabled": False,
            "tavily_fallback_enabled": True,
        })
        assert not _should_enable_self_evaluator({
            "self_eval_enabled": False,
            "tavily_fallback_enabled": False,
        })
