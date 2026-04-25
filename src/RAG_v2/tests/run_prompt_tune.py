"""Run prompt-tuning checks against a live LM Studio model.

Usage:
    python src/RAG_v2/tests/run_prompt_tune.py
"""

from __future__ import annotations

from agent.react_agent import ReActAgent

try:
    from tests.prompt_tune_questions import TUNE_QUESTIONS
except ModuleNotFoundError:
    from prompt_tune_questions import TUNE_QUESTIONS


class Settings:
    lm_studio_url = "http://localhost:1234/v1"
    agent_model = "qwen2.5-8b-instruct"
    agent_max_iterations = 4


def main() -> None:
    agent = ReActAgent(Settings())
    correct = 0

    for query, expected_tool, _expected_collection in TUNE_QUESTIONS:
        state = agent.run(query)
        first_tool = state.tool_call_history[0] if state.tool_call_history else "NONE"
        is_correct = first_tool == expected_tool
        correct += int(is_correct)
        status = "PASS" if is_correct else "FAIL"

        print(f"[{status}] {query[:60]}")
        print(f"  Expected: {expected_tool} | Got: {first_tool}")

    accuracy = correct / len(TUNE_QUESTIONS)
    print(f"\nAccuracy: {correct}/{len(TUNE_QUESTIONS)} = {accuracy:.0%}")


if __name__ == "__main__":
    main()
