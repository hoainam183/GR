from __future__ import annotations

from unittest.mock import MagicMock

from query.reflection import QueryReflector


AUTH = {
    "major_code": "IT-E6",
    "major": "Công nghệ thông tin Việt - Nhật",
    "cohort": "65",
}


class _Settings:
    reflection_model = "stub"
    reflection_temperature = 0.0
    reflection_max_tokens = 256
    reflection_provider = "gemini"
    google_api_key = "fake"
    lm_studio_base_url = ""
    ollama_base_url = ""
    openai_api_key = ""


def _reflector(llm_response: str | None = None) -> QueryReflector:
    reflector = QueryReflector(settings=_Settings())
    reflector._client = MagicMock()
    if llm_response is not None:
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = llm_response
        reflector._client.chat.completions.create.return_value = response
    return reflector


def test_standalone_course_query_with_profile_skips_llm() -> None:
    reflector = _reflector()

    result = reflector.reflect(
        "môn hướng đối tượng được học vào kì mấy",
        user_context=AUTH,
    )

    reflector._client.chat.completions.create.assert_not_called()
    assert result["prompt"] == ""
    assert result["entities"]["course_code"] == "IT3103"
    assert "Lập trình hướng đối tượng (IT3103)" in result["rewritten"]


def test_reflection_corrects_llm_invented_adjacent_course_code() -> None:
    reflector = _reflector(
        "Lập trình hướng đối tượng (IT3100) được học vào kỳ mấy?"
    )

    result = reflector.reflect(
        "còn môn hướng đối tượng được học vào kì mấy",
        chat_history=[{"role": "user", "content": "môn này là môn nào?"}],
        user_context=AUTH,
    )

    reflector._client.chat.completions.create.assert_called_once()
    assert "Lập trình hướng đối tượng (IT3103)" in result["rewritten"]
    assert "IT3100" not in result["rewritten"]


def test_user_explicit_course_code_is_preserved() -> None:
    reflector = _reflector(
        "Lập trình hướng đối tượng (IT3103) được học vào kỳ mấy?"
    )

    result = reflector.reflect(
        "còn môn Lập trình hướng đối tượng IT3100 được học vào kì mấy",
        chat_history=[{"role": "user", "content": "môn này là môn nào?"}],
        user_context=AUTH,
    )

    assert "IT3100" in result["rewritten"]
    assert "IT3103" not in result["rewritten"]
