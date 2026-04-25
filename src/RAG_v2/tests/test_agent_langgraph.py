"""Tests for LangGraph ReActAgent.

Run:
    pytest tests/test_agent_langgraph.py -v
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage
from openai import APIConnectionError

from agent.react_agent import ReActAgent

PATCH_CHAT = "agent.react_agent.ChatOpenAI"


def make_settings(max_iterations: int = 4) -> MagicMock:
    settings = MagicMock()
    settings.lm_studio_url = "http://localhost:1234/v1"
    settings.agent_model = "qwen2.5-8b-instruct"
    settings.agent_max_iterations = max_iterations
    return settings


def make_ai_with_tool(tool_name: str, args: dict, call_id: str = "tc_001") -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            {
                "id": call_id,
                "name": tool_name,
                "args": args,
                "type": "tool_call",
            }
        ],
    )


def make_ai_answer(content: str) -> AIMessage:
    return AIMessage(content=content, tool_calls=[])


def make_connection_error() -> APIConnectionError:
    request = MagicMock()
    try:
        return APIConnectionError(message="Connection failed", request=request)
    except TypeError:
        return APIConnectionError(request=request)


class TestSimpleFlow:
    @patch("agent.lc_tools.execute_tool")
    @patch(PATCH_CHAT)
    def test_one_tool_then_answer(self, mock_chat_cls: MagicMock, mock_execute: MagicMock) -> None:
        mock_llm = MagicMock()
        mock_chat_cls.return_value = mock_llm
        mock_llm.bind_tools.return_value = mock_llm

        mock_llm.invoke.side_effect = [
            make_ai_with_tool("rag_search", {"query": "học bổng KKHT", "collection": "quy_dinh"}),
            make_ai_answer("Học bổng KKHT yêu cầu GPA >= 3.2 và không có môn F."),
        ]
        mock_execute.return_value = "GPA >= 3.2, không có môn F, không bị kỷ luật."

        agent = ReActAgent(make_settings())
        state = agent.run("Điều kiện học bổng KKHT là gì?")

        assert state.final_answer is not None
        assert "rag_search" in state.tool_call_history
        assert state.error is None
        assert state.iteration == 2
        assert len(state.tool_results) == 1
        assert state.tool_results[0].tool_name == "rag_search"

    @patch("agent.lc_tools.execute_tool")
    @patch(PATCH_CHAT)
    def test_direct_answer_no_tool(self, mock_chat_cls: MagicMock, mock_execute: MagicMock) -> None:
        mock_llm = MagicMock()
        mock_chat_cls.return_value = mock_llm
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.invoke.return_value = make_ai_answer("Xin chào! Tôi có thể giúp gì cho bạn?")

        agent = ReActAgent(make_settings())
        state = agent.run("Xin chào")

        assert state.final_answer is not None
        assert len(state.tool_call_history) == 0
        mock_execute.assert_not_called()

    @patch("agent.lc_tools.execute_tool")
    @patch(PATCH_CHAT)
    def test_history_messages_are_forwarded_to_agent(
        self,
        mock_chat_cls: MagicMock,
        mock_execute: MagicMock,
    ) -> None:
        mock_llm = MagicMock()
        mock_chat_cls.return_value = mock_llm
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.invoke.return_value = make_ai_answer("Đã rõ, mình sẽ so sánh cho bạn.")

        agent = ReActAgent(make_settings())
        state = agent.run(
            "so sánh với IT-E7",
            history=[
                {
                    "role": "user",
                    "content": "so sánh môn lập trình mạng của ngành IT-E6 và",
                },
                {
                    "role": "assistant",
                    "content": "Bạn muốn so sánh với ngành nào?",
                },
            ],
        )

        assert state.final_answer is not None
        call_messages = mock_llm.invoke.call_args_list[0].args[0]
        human_contents = [
            msg.content
            for msg in call_messages
            if isinstance(msg, HumanMessage)
        ]
        assert any("IT-E6" in content for content in human_contents)
        assert human_contents[-1] == "so sánh với IT-E7"
        mock_execute.assert_not_called()

    @patch("agent.lc_tools.execute_tool")
    @patch(PATCH_CHAT)
    def test_clarify_question_preserves_numbered_options(
        self,
        mock_chat_cls: MagicMock,
        mock_execute: MagicMock,
    ) -> None:
        mock_llm = MagicMock()
        mock_chat_cls.return_value = mock_llm
        mock_llm.bind_tools.return_value = mock_llm

        mock_llm.invoke.side_effect = [
            make_ai_with_tool(
                "clarify_question",
                {
                    "message": "Bạn muốn so sánh theo hướng nào?",
                    "options": ["IT-E6 vs IT-E7", "K65 vs K70", "So sánh học phí"],
                },
            ),
            make_ai_answer("Vui lòng chọn lựa chọn so sánh bạn muốn (1, 2 hoặc 3) để tiếp tục."),
        ]
        mock_execute.return_value = (
            "[CLARIFY]\n"
            "Bạn muốn so sánh theo hướng nào?\n\n"
            "1. IT-E6 vs IT-E7\n"
            "2. K65 vs K70\n"
            "3. So sánh học phí"
        )

        agent = ReActAgent(make_settings())
        state = agent.run("so sánh môn lập trình mạng")

        assert state.final_answer is not None
        assert "1. IT-E6 vs IT-E7" in state.final_answer
        assert "2. K65 vs K70" in state.final_answer
        assert mock_llm.invoke.call_count == 1

    @patch("agent.lc_tools.execute_tool")
    @patch(PATCH_CHAT)
    def test_clarify_question_stops_before_followup_compare_call(
        self,
        mock_chat_cls: MagicMock,
        mock_execute: MagicMock,
    ) -> None:
        mock_llm = MagicMock()
        mock_chat_cls.return_value = mock_llm
        mock_llm.bind_tools.return_value = mock_llm

        mock_llm.invoke.side_effect = [
            make_ai_with_tool(
                "clarify_question",
                {
                    "message": "Bạn muốn so sánh ngành nào với IT-E6?",
                    "options": ["IT-E7", "K65", "Môn khác"],
                },
            ),
            make_ai_with_tool(
                "compare_cohorts",
                {
                    "topic": "môn lập trình mạng",
                    "cohort_a": "IT-E6",
                    "cohort_b": "IT-E7",
                    "collection": "chuong_trinh",
                },
            ),
        ]
        mock_execute.return_value = (
            "[CLARIFY]\n"
            "Bạn muốn so sánh ngành nào với IT-E6?\n\n"
            "1. IT-E7\n"
            "2. K65\n"
            "3. Môn khác"
        )

        agent = ReActAgent(make_settings())
        state = agent.run("so sánh môn lập trình mạng")

        assert state.final_answer is not None
        assert "Bạn muốn so sánh ngành nào" in state.final_answer
        assert "1. IT-E7" in state.final_answer
        assert mock_llm.invoke.call_count == 1
        assert state.tool_call_history == ["clarify_question"]


class TestComplexFlow:
    @patch("agent.lc_tools.execute_tool")
    @patch(PATCH_CHAT)
    def test_compare_cohorts_flow(self, mock_chat_cls: MagicMock, mock_execute: MagicMock) -> None:
        mock_llm = MagicMock()
        mock_chat_cls.return_value = mock_llm
        mock_llm.bind_tools.return_value = mock_llm

        mock_llm.invoke.side_effect = [
            make_ai_with_tool(
                "compare_cohorts",
                {
                    "topic": "học bổng KKHT",
                    "cohort_a": "K65",
                    "cohort_b": "K70",
                    "collection": "quy_dinh",
                },
                call_id="tc_002",
            ),
            make_ai_answer("K65 yêu cầu GPA >= 3.2, K70 yêu cầu GPA >= 3.5."),
        ]
        mock_execute.return_value = "### K65\nGPA >= 3.2\n---\n### K70\nGPA >= 3.5"

        agent = ReActAgent(make_settings())
        state = agent.run("So sánh học bổng KKHT giữa K65 và K70")

        assert "compare_cohorts" in state.tool_call_history
        assert state.final_answer is not None
        assert state.error is None

    @patch("agent.lc_tools.execute_tool")
    @patch(PATCH_CHAT)
    def test_multi_rag_search_flow(self, mock_chat_cls: MagicMock, mock_execute: MagicMock) -> None:
        mock_llm = MagicMock()
        mock_chat_cls.return_value = mock_llm
        mock_llm.bind_tools.return_value = mock_llm

        mock_llm.invoke.side_effect = [
            make_ai_with_tool(
                "multi_rag_search",
                {
                    "queries": [
                        {"query": "điều kiện tốt nghiệp", "collection": "quy_dinh"},
                        {"query": "tín chỉ tích lũy", "collection": "chuong_trinh"},
                    ]
                },
                call_id="tc_003",
            ),
            make_ai_answer("Bạn cần đủ 130 tín chỉ và không có môn F để tốt nghiệp."),
        ]
        mock_execute.return_value = "Điều kiện: >=130 tín chỉ, GPA >= 2.0, không nợ môn."

        agent = ReActAgent(make_settings())
        state = agent.run("Tôi đủ điều kiện tốt nghiệp chưa?")

        assert "multi_rag_search" in state.tool_call_history
        assert state.final_answer is not None


class TestSafetyMechanisms:
    @patch("agent.lc_tools.execute_tool")
    @patch(PATCH_CHAT)
    def test_loop_detection_triggers_synthesis(
        self,
        mock_chat_cls: MagicMock,
        mock_execute: MagicMock,
    ) -> None:
        mock_llm = MagicMock()
        mock_chat_cls.return_value = mock_llm
        mock_llm.bind_tools.return_value = mock_llm

        tool_call = make_ai_with_tool("rag_search", {"query": "test", "collection": "quy_dinh"})
        synthesis_answer = AIMessage(content="Tổng hợp: kết quả test.")

        mock_llm.invoke.side_effect = [
            tool_call,
            tool_call,
            synthesis_answer,
        ]
        mock_execute.return_value = "Kết quả test."

        agent = ReActAgent(make_settings(max_iterations=4))
        state = agent.run("Test query")

        assert state.final_answer is not None
        assert state.tool_call_history.count("rag_search") == 1

    @patch("agent.lc_tools.execute_tool")
    @patch(PATCH_CHAT)
    def test_max_iterations_triggers_synthesis(
        self,
        mock_chat_cls: MagicMock,
        mock_execute: MagicMock,
    ) -> None:
        mock_llm = MagicMock()
        mock_chat_cls.return_value = mock_llm
        mock_llm.bind_tools.return_value = mock_llm

        mock_llm.invoke.side_effect = [
            make_ai_with_tool("rag_search", {"query": "q1", "collection": "quy_dinh"}, "tc_1"),
            make_ai_with_tool("web_search", {"query": "q2"}, "tc_2"),
            AIMessage(content="Tổng hợp từ kết quả tìm kiếm."),
        ]
        mock_execute.return_value = "Kết quả mock."

        agent = ReActAgent(make_settings(max_iterations=2))
        state = agent.run("Câu hỏi phức tạp")

        assert state.final_answer is not None
        assert state.iteration <= 2

    @patch(PATCH_CHAT)
    def test_llm_connection_error_returns_graceful_state(self, mock_chat_cls: MagicMock) -> None:
        mock_llm = MagicMock()
        mock_chat_cls.return_value = mock_llm
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.invoke.side_effect = make_connection_error()

        agent = ReActAgent(make_settings())
        state = agent.run("Test khi LM Studio tắt")

        assert state.final_answer is not None or state.error is not None


class TestStateConversion:
    @patch("agent.lc_tools.execute_tool")
    @patch(PATCH_CHAT)
    def test_tool_results_logged_correctly(self, mock_chat_cls: MagicMock, mock_execute: MagicMock) -> None:
        mock_llm = MagicMock()
        mock_chat_cls.return_value = mock_llm
        mock_llm.bind_tools.return_value = mock_llm

        mock_llm.invoke.side_effect = [
            make_ai_with_tool("rag_search", {"query": "học bổng", "collection": "quy_dinh"}),
            make_ai_answer("GPA >= 3.2."),
        ]
        mock_execute.return_value = "Nội dung học bổng KKHT."

        agent = ReActAgent(make_settings())
        state = agent.run("Học bổng KKHT?")

        assert len(state.tool_results) == 1
        tr = state.tool_results[0]
        assert tr.tool_name == "rag_search"
        assert tr.args == {"query": "học bổng", "collection": "quy_dinh"}
        assert "Nội dung học bổng" in tr.result

    @patch("agent.lc_tools.execute_tool")
    @patch(PATCH_CHAT)
    def test_to_log_dict_serializable(self, mock_chat_cls: MagicMock, mock_execute: MagicMock) -> None:
        mock_llm = MagicMock()
        mock_chat_cls.return_value = mock_llm
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.invoke.return_value = make_ai_answer("Câu trả lời.")

        agent = ReActAgent(make_settings())
        state = agent.run("Test serialization")

        log_dict = state.to_log_dict()
        json_str = json.dumps(log_dict, ensure_ascii=False)
        assert len(json_str) > 0
