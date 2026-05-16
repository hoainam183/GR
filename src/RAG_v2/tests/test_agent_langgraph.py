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
    settings.agent_tool_result_limit = 3000  # prevent MagicMock int() → 1
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
        assert "Xin ch" not in state.final_answer
        assert len(state.tool_call_history) == 0
        assert mock_llm.invoke.call_count == 1
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

        # The [CLARIFY] prefix triggers early exit — agent stops and returns the
        # clarification message as the final answer.
        assert state.final_answer is not None
        assert "[CLARIFY]" in state.final_answer or "IT-E6 vs IT-E7" in state.final_answer
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

        # After clarify, the agent should stop — not proceed to compare_cohorts
        assert state.final_answer is not None
        assert "IT-E6" in state.final_answer or "[CLARIFY]" in state.final_answer
        assert mock_llm.invoke.call_count == 1
        assert state.tool_call_history == ["clarify_question"]


class TestComplexFlow:
    @patch("agent.react_agent.execute_retrieval_plan")
    @patch(PATCH_CHAT)
    def test_compare_cohorts_flow(
        self,
        mock_chat_cls: MagicMock,
        mock_execute_plan: MagicMock,
    ) -> None:
        mock_llm = MagicMock()
        mock_chat_cls.return_value = mock_llm
        mock_llm.bind_tools.return_value = mock_llm

        mock_llm.invoke.side_effect = [
            make_ai_answer(
                json.dumps(
                    {
                        "sub_questions": [
                            "hoc bong KKHT K65",
                            "hoc bong KKHT K70",
                        ],
                        "reasoning": "comparison",
                    }
                )
            ),
            make_ai_answer(
                json.dumps(
                    {
                        "steps": [
                            {
                                "query": "hoc bong KKHT",
                                "collection": "quy_dinh",
                                "major_hint": None,
                                "cohort_hint": "K65",
                                "label": "K65",
                            },
                            {
                                "query": "hoc bong KKHT",
                                "collection": "quy_dinh",
                                "major_hint": None,
                                "cohort_hint": "K70",
                                "label": "K70",
                            },
                        ],
                        "needs_web": False,
                        "reasoning": "comparison",
                    }
                )
            ),
            make_ai_answer("K65 yeu cau GPA >= 3.2, K70 yeu cau GPA >= 3.5."),
        ]
        mock_execute_plan.return_value = [
            ("K65", "GPA >= 3.2"),
            ("K70", "GPA >= 3.5"),
        ]

        agent = ReActAgent(make_settings())
        state = agent.run(
            "So sanh hoc bong KKHT giua K65 va K70",
            complexity_subtype="comparison",
        )

        mock_execute_plan.assert_called_once()
        assert state.tool_call_history == [
            "planned_rag_search:K65",
            "planned_rag_search:K70",
        ]
        assert len(state.tool_results) == 2
        assert state.final_answer is not None
        assert state.error is None

    @patch("agent.react_agent.execute_retrieval_plan")
    @patch(PATCH_CHAT)
    def test_multi_rag_search_flow(
        self,
        mock_chat_cls: MagicMock,
        mock_execute_plan: MagicMock,
    ) -> None:
        mock_llm = MagicMock()
        mock_chat_cls.return_value = mock_llm
        mock_llm.bind_tools.return_value = mock_llm

        mock_llm.invoke.side_effect = [
            make_ai_answer(
                json.dumps(
                    {
                        "sub_questions": [
                            "dieu kien tot nghiep",
                            "tin chi tich luy",
                        ],
                        "reasoning": "multi_source",
                    }
                )
            ),
            make_ai_answer(
                json.dumps(
                    {
                        "steps": [
                            {
                                "query": "dieu kien tot nghiep",
                                "collection": "quy_dinh",
                                "major_hint": None,
                                "cohort_hint": None,
                                "label": "quy_dinh",
                            },
                            {
                                "query": "tin chi tich luy",
                                "collection": "chuong_trinh",
                                "major_hint": None,
                                "cohort_hint": None,
                                "label": "chuong_trinh",
                            },
                        ],
                        "needs_web": False,
                        "reasoning": "multi_source",
                    }
                )
            ),
            make_ai_answer("Ban can du tin chi va dat dieu kien tot nghiep."),
        ]
        mock_execute_plan.return_value = [
            ("quy_dinh", "GPA >= 2.0, khong no mon."),
            ("chuong_trinh", "Can tich luy du tin chi theo CTDT."),
        ]

        agent = ReActAgent(make_settings())
        state = agent.run(
            "Toi du dieu kien tot nghiep chua?",
            complexity_subtype="multi_source",
        )

        mock_execute_plan.assert_called_once()
        assert state.tool_call_history == [
            "planned_rag_search:quy_dinh",
            "planned_rag_search:chuong_trinh",
        ]
        assert len(state.tool_results) == 2
        assert state.final_answer is not None

    @patch("agent.react_agent.execute_retrieval_plan")
    @patch("agent.lc_tools.execute_tool")
    @patch(PATCH_CHAT)
    def test_invalid_planner_plan_falls_back_to_agent_loop(
        self,
        mock_chat_cls: MagicMock,
        mock_execute_tool: MagicMock,
        mock_execute_plan: MagicMock,
    ) -> None:
        mock_llm = MagicMock()
        mock_chat_cls.return_value = mock_llm
        mock_llm.bind_tools.return_value = mock_llm

        mock_llm.invoke.side_effect = [
            make_ai_answer(
                json.dumps(
                    {
                        "sub_questions": ["dieu kien tot nghiep"],
                        "reasoning": "single aspect",
                    }
                )
            ),
            make_ai_answer(
                json.dumps(
                    {
                        "steps": [
                            {
                                "query": "dieu kien tot nghiep",
                                "collection": "khong_hop_le",
                                "major_hint": None,
                                "cohort_hint": None,
                                "label": "bad",
                            }
                        ],
                        "needs_web": False,
                        "reasoning": "invalid collection",
                    }
                )
            ),
            make_ai_with_tool(
                "rag_search",
                {"query": "dieu kien tot nghiep", "collection": "quy_dinh"},
            ),
            make_ai_answer("Dieu kien tot nghiep duoc tim thay trong quy dinh."),
        ]
        mock_execute_tool.return_value = "GPA >= 2.0, khong no mon."

        agent = ReActAgent(make_settings())
        state = agent.run(
            "Toi du dieu kien tot nghiep chua?",
            complexity_subtype="multi_source",
        )

        mock_execute_plan.assert_not_called()
        mock_execute_tool.assert_called_once()
        assert state.tool_call_history == ["rag_search"]
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
