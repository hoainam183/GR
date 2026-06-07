"""Tests for query decomposer prompt examples and parsing."""

from __future__ import annotations

import json

from query.decomposer import _DECOMPOSE_FEW_SHOT


def test_graduation_few_shot_splits_foreign_language_and_general_rules() -> None:
    user_index = next(
        index
        for index, message in enumerate(_DECOMPOSE_FEW_SHOT)
        if message["role"] == "user"
        and message["content"] == "Điều kiện để tôi tốt nghiệp"
    )
    assistant_message = _DECOMPOSE_FEW_SHOT[user_index + 1]

    assert assistant_message["role"] == "assistant"
    payload = json.loads(assistant_message["content"])

    assert payload["subqueries"] == [
        {
            "query": "Điều kiện ngoại ngữ để tốt nghiệp là gì?",
            "collection": "quydinh",
        },
        {
            "query": "Điều kiện tốt nghiệp chung là gì?",
            "collection": "quydinh",
        },
        {
            "query": "Điều kiện hoàn thành chương trình đào tạo để tốt nghiệp là gì?",
            "collection": "ctdt",
        },
    ]
