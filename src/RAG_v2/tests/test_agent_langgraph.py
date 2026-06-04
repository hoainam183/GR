"""Tests for the Planner-Executor ReActAgent compatibility class."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage
from openai import APIConnectionError

from agent.prompts import DECOMPOSE_SYSTEM_PROMPT, PLANNER_SYSTEM_PROMPT
from agent.react_agent import ReActAgent

PATCH_CHAT = "agent.react_agent.ChatOpenAI"


def make_settings() -> MagicMock:
    settings = MagicMock()
    settings.lm_studio_url = "http://localhost:1234/v1"
    settings.agent_model = "qwen2.5-8b-instruct"
    settings.agent_max_iterations = 4
    settings.agent_tool_result_limit = 3000
    settings.agent_synthesis_provider = ""
    settings.agent_synthesis_model = ""
    settings.agent_synthesis_temperature = 0.0
    settings.agent_synthesis_max_tokens = 1200
    settings.lm_studio_api_key = "lm-studio"
    return settings


def make_ai_answer(content: str) -> AIMessage:
    return AIMessage(content=content)


def plan_payload(collection: str = "quy_dinh") -> str:
    return json.dumps(
        {
            "steps": [
                {
                    "query": "dieu kien tot nghiep",
                    "collection": collection,
                    "major_hint": None,
                    "cohort_hint": None,
                    "label": "quy_dinh",
                }
            ],
            "needs_web": False,
            "reasoning": "single step",
        }
    )


def decompose_payload() -> str:
    return json.dumps(
        {
            "sub_questions": ["dieu kien tot nghiep", "tin chi tich luy"],
            "reasoning": "multi source",
        }
    )


def make_connection_error() -> APIConnectionError:
    request = MagicMock()
    try:
        return APIConnectionError(message="Connection failed", request=request)
    except TypeError:
        return APIConnectionError(request=request)


class TestPlannerExecutorFlow:
    @patch("agent.react_agent.execute_retrieval_plan")
    @patch(PATCH_CHAT)
    def test_general_query_skips_decompose(
        self,
        mock_chat_cls: MagicMock,
        mock_execute_plan: MagicMock,
    ) -> None:
        mock_llm = MagicMock()
        mock_chat_cls.return_value = mock_llm
        mock_llm.invoke.side_effect = [
            make_ai_answer(plan_payload()),
            make_ai_answer("Dieu kien tot nghiep duoc quy dinh trong quy che."),
        ]
        mock_execute_plan.return_value = [("quy_dinh", "GPA >= 2.0")]

        agent = ReActAgent(make_settings())
        state = agent.run("Dieu kien tot nghiep la gi?", complexity_subtype="general")

        assert state.error is None
        assert state.final_answer
        assert mock_execute_plan.call_count == 1
        first_system = mock_llm.invoke.call_args_list[0].args[0][0]
        assert first_system.content == PLANNER_SYSTEM_PROMPT

    @patch("agent.react_agent.execute_retrieval_plan")
    @patch(PATCH_CHAT)
    def test_planner_preserves_reflected_major_and_cohort_scope(
        self,
        mock_chat_cls: MagicMock,
        mock_execute_plan: MagicMock,
    ) -> None:
        mock_llm = MagicMock()
        mock_chat_cls.return_value = mock_llm
        mock_llm.invoke.side_effect = [
            make_ai_answer(plan_payload()),
            make_ai_answer("Sinh viên IT-E6 K67 cần đạt chuẩn ngoại ngữ phù hợp."),
        ]
        mock_execute_plan.return_value = [("quy_dinh", "IT-E6 K67: tieng Nhat N3")]

        agent = ReActAgent(make_settings())
        state = agent.run(
            "Điều kiện ngoại ngữ để sinh viên chương trình Công nghệ thông tin "
            "Việt - Nhật (IT-E6) khóa K67 tốt nghiệp là gì?",
            complexity_subtype="general",
            top_k=7,
        )

        assert state.error is None
        executed_steps = mock_execute_plan.call_args.args[0]
        step = executed_steps[0]
        assert step["major_hint"] == "IT-E6"
        assert step["cohort_hint"] == "K67"
        assert "IT-E6" in step["query"]
        assert "K67" in step["query"]
        assert mock_execute_plan.call_args.kwargs["top_k"] == 7

    @patch("agent.react_agent.execute_retrieval_plan")
    @patch(PATCH_CHAT)
    def test_comparison_uses_decompose_then_planner(
        self,
        mock_chat_cls: MagicMock,
        mock_execute_plan: MagicMock,
    ) -> None:
        mock_llm = MagicMock()
        mock_chat_cls.return_value = mock_llm
        mock_llm.invoke.side_effect = [
            make_ai_answer(decompose_payload()),
            make_ai_answer(plan_payload()),
            make_ai_answer("Tong hop so sanh."),
        ]
        mock_execute_plan.return_value = [("quy_dinh", "ket qua")]

        agent = ReActAgent(make_settings())
        state = agent.run("So sanh K65 va K70", complexity_subtype="comparison")

        assert state.error is None
        assert mock_execute_plan.call_count == 1
        assert mock_llm.invoke.call_args_list[0].args[0][0].content == DECOMPOSE_SYSTEM_PROMPT
        assert mock_llm.invoke.call_args_list[1].args[0][0].content == PLANNER_SYSTEM_PROMPT

    @patch("agent.react_agent.execute_retrieval_plan")
    @patch(PATCH_CHAT)
    def test_multi_source_uses_decompose_then_planner(
        self,
        mock_chat_cls: MagicMock,
        mock_execute_plan: MagicMock,
    ) -> None:
        mock_llm = MagicMock()
        mock_chat_cls.return_value = mock_llm
        mock_llm.invoke.side_effect = [
            make_ai_answer(decompose_payload()),
            make_ai_answer(plan_payload("chuong_trinh")),
            make_ai_answer("Tong hop multi-source."),
        ]
        mock_execute_plan.return_value = [("chuong_trinh", "ket qua")]

        agent = ReActAgent(make_settings())
        state = agent.run("Toi du dieu kien tot nghiep chua?", complexity_subtype="multi_source")

        assert state.error is None
        assert mock_execute_plan.call_count == 1
        assert mock_llm.invoke.call_args_list[0].args[0][0].content == DECOMPOSE_SYSTEM_PROMPT

    @patch("agent.react_agent.execute_retrieval_plan")
    @patch(PATCH_CHAT)
    def test_json_fences_are_parsed_for_decomposer_and_planner(
        self,
        mock_chat_cls: MagicMock,
        mock_execute_plan: MagicMock,
    ) -> None:
        mock_llm = MagicMock()
        mock_chat_cls.return_value = mock_llm
        mock_llm.invoke.side_effect = [
            make_ai_answer(f"```json\n{decompose_payload()}\n```"),
            make_ai_answer(f"```json\n{plan_payload()}\n```"),
            make_ai_answer("Tong hop."),
        ]
        mock_execute_plan.return_value = [("quy_dinh", "ket qua")]

        agent = ReActAgent(make_settings())
        state = agent.run("So sanh K65 va K70", complexity_subtype="comparison")

        assert state.error is None
        assert mock_execute_plan.call_count == 1

    @patch("agent.react_agent.execute_retrieval_plan")
    @patch(PATCH_CHAT)
    def test_planner_invalid_json_sets_error(
        self,
        mock_chat_cls: MagicMock,
        mock_execute_plan: MagicMock,
    ) -> None:
        mock_llm = MagicMock()
        mock_chat_cls.return_value = mock_llm
        mock_llm.invoke.return_value = make_ai_answer("not json")

        agent = ReActAgent(make_settings())
        state = agent.run("Dieu kien tot nghiep")

        assert state.error and state.error.startswith("planner_invalid_json")
        mock_execute_plan.assert_not_called()

    @patch("agent.react_agent.execute_retrieval_plan")
    @patch(PATCH_CHAT)
    def test_planner_empty_steps_sets_error(
        self,
        mock_chat_cls: MagicMock,
        mock_execute_plan: MagicMock,
    ) -> None:
        mock_llm = MagicMock()
        mock_chat_cls.return_value = mock_llm
        mock_llm.invoke.return_value = make_ai_answer('{"steps": [], "needs_web": false}')

        agent = ReActAgent(make_settings())
        state = agent.run("Dieu kien tot nghiep")

        assert state.error == "planner_empty_steps"
        mock_execute_plan.assert_not_called()

    @patch("agent.react_agent.execute_retrieval_plan")
    @patch(PATCH_CHAT)
    def test_planner_invalid_collection_sets_error(
        self,
        mock_chat_cls: MagicMock,
        mock_execute_plan: MagicMock,
    ) -> None:
        mock_llm = MagicMock()
        mock_chat_cls.return_value = mock_llm
        mock_llm.invoke.return_value = make_ai_answer(plan_payload("bad_collection"))

        agent = ReActAgent(make_settings())
        state = agent.run("Dieu kien tot nghiep")

        assert state.error == "planner_invalid_plan"
        mock_execute_plan.assert_not_called()

    @patch("agent.react_agent.execute_retrieval_plan")
    @patch(PATCH_CHAT)
    def test_all_empty_executor_returns_no_info_without_error(
        self,
        mock_chat_cls: MagicMock,
        mock_execute_plan: MagicMock,
    ) -> None:
        mock_llm = MagicMock()
        mock_chat_cls.return_value = mock_llm
        mock_llm.invoke.return_value = make_ai_answer(plan_payload())
        mock_execute_plan.return_value = [
            ("quy_dinh", "[Khong tim thay thong tin trong co so du lieu]")
        ]

        agent = ReActAgent(make_settings())
        state = agent.run("Dieu kien tot nghiep")

        assert state.error is None
        assert "khong tim thay thong tin phu hop" in (state.final_answer or "")
        assert len(state.tool_results) == 0
        assert mock_llm.invoke.call_count == 1

    @patch("agent.react_agent.execute_retrieval_plan")
    @patch(PATCH_CHAT)
    def test_partial_empty_executor_filters_empty_text_before_synthesis(
        self,
        mock_chat_cls: MagicMock,
        mock_execute_plan: MagicMock,
    ) -> None:
        plan = json.dumps(
            {
                "steps": [
                    {
                        "query": "q1",
                        "collection": "quy_dinh",
                        "major_hint": None,
                        "cohort_hint": None,
                        "label": "empty",
                    },
                    {
                        "query": "q2",
                        "collection": "chuong_trinh",
                        "major_hint": None,
                        "cohort_hint": None,
                        "label": "nonempty",
                    },
                ],
                "needs_web": False,
            }
        )
        mock_llm = MagicMock()
        mock_chat_cls.return_value = mock_llm
        mock_llm.invoke.side_effect = [
            make_ai_answer(plan),
            make_ai_answer("Tong hop tu ket qua co thong tin."),
        ]
        mock_execute_plan.return_value = [
            ("empty", "[Khong tim thay thong tin trong co so du lieu]"),
            ("nonempty", "Co thong tin chuong trinh"),
        ]

        agent = ReActAgent(make_settings())
        state = agent.run("Dieu kien tot nghiep")

        assert state.error is None
        assert len(state.tool_results) == 1
        assert "Co thong tin" in state.tool_results[0].result
        synthesis_human = mock_llm.invoke.call_args_list[-1].args[0][1]
        assert "Khong tim thay" not in synthesis_human.content
        assert "Co thong tin chuong trinh" in synthesis_human.content

    @patch("agent.react_agent.execute_retrieval_plan")
    @patch(PATCH_CHAT)
    def test_top_k_reaches_execute_retrieval_plan(
        self,
        mock_chat_cls: MagicMock,
        mock_execute_plan: MagicMock,
    ) -> None:
        mock_llm = MagicMock()
        mock_chat_cls.return_value = mock_llm
        mock_llm.invoke.side_effect = [
            make_ai_answer(plan_payload()),
            make_ai_answer("Tong hop."),
        ]
        mock_execute_plan.return_value = [("quy_dinh", "ket qua")]

        agent = ReActAgent(make_settings())
        state = agent.run("Dieu kien tot nghiep", top_k=7)

        assert state.error is None
        assert mock_execute_plan.call_args.kwargs["top_k"] == 7
        assert state.tool_results[0].args["top_k"] == 7

    @patch(PATCH_CHAT)
    def test_llm_connection_error_returns_graceful_state(self, mock_chat_cls: MagicMock) -> None:
        mock_llm = MagicMock()
        mock_chat_cls.return_value = mock_llm
        mock_llm.invoke.side_effect = make_connection_error()

        agent = ReActAgent(make_settings())
        state = agent.run("Test khi LM Studio tat")

        assert state.final_answer is not None or state.error is not None

    @patch("agent.react_agent.execute_retrieval_plan")
    @patch(PATCH_CHAT)
    def test_to_log_dict_serializable(
        self,
        mock_chat_cls: MagicMock,
        mock_execute_plan: MagicMock,
    ) -> None:
        mock_llm = MagicMock()
        mock_chat_cls.return_value = mock_llm
        mock_llm.invoke.side_effect = [
            make_ai_answer(plan_payload()),
            make_ai_answer("Tong hop."),
        ]
        mock_execute_plan.return_value = [("quy_dinh", "ket qua")]

        agent = ReActAgent(make_settings())
        state = agent.run("Dieu kien tot nghiep")

        json_str = json.dumps(state.to_log_dict(), ensure_ascii=False)
        assert len(json_str) > 0
