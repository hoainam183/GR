"""A planner step targeting the lich_thi collection must pass plan validation."""

from __future__ import annotations

from agent.react_agent import ReActAgent


def _agent() -> ReActAgent:
    # Bypass heavy __init__ (LLM + graph build); validation only needs the
    # class-level _VALID_COLLECTIONS.
    return object.__new__(ReActAgent)


def test_lich_thi_in_valid_collections() -> None:
    assert "lich_thi" in ReActAgent._VALID_COLLECTIONS


def test_lich_thi_step_survives_validation() -> None:
    agent = _agent()
    plan = {
        "steps": [
            {
                "query": "lịch thi phòng thi môn CH1012",
                "collection": "lich_thi",
                "major_hint": None,
                "cohort_hint": None,
                "label": "lich_thi_CH1012",
            }
        ]
    }
    assert agent._validate_plan(plan) is True
    assert len(agent._valid_plan_steps(plan["steps"])) == 1


def test_unknown_collection_still_rejected() -> None:
    agent = _agent()
    plan = {"steps": [{"query": "x", "collection": "bogus"}]}
    assert agent._validate_plan(plan) is False
