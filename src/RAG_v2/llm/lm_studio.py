"""LM Studio LLM — Local provider via OpenAI-compatible endpoint."""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, Generator, List, Optional, cast

from openai import OpenAI, RateLimitError
from openai.types.chat import ChatCompletionMessageParam

from llm import register_llm
from llm.base import BaseLLM
from llm.prompts import (
    build_chitchat_messages,
    build_rag_messages,
    build_self_eval_messages,
)

logger = logging.getLogger(__name__)

# ─── Constants ──────────────────────────────────────────────────────────────────
DEFAULT_MODEL = "qwen/qwen3-8b:2"
DEFAULT_MAX_TOKENS = 1024
DEFAULT_TEMPERATURE = 0.0
_MAX_RETRIES = 1
_BASE_RETRY_DELAY = 1.0


@register_llm("lm_studio")
class LMStudioLLM(BaseLLM):
    """LM Studio LLM via OpenAI-compatible endpoint."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        base_url: str = "http://localhost:1234/v1",
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        resolved_key = api_key or os.environ.get("OPENAI_API_KEY")
        self._client = OpenAI(api_key=resolved_key, base_url=base_url)

    def generate(
        self,
        query: str,
        context: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        mode: str = "rag",
    ) -> str:
        messages = self._build_messages(query, context, history, mode)

        last_exc: Optional[Exception] = None
        for attempt in range(_MAX_RETRIES):
            try:
                response = self._client.chat.completions.create(
                    model=self.model,
                    messages=cast(List[ChatCompletionMessageParam], messages),
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                )
                break
            except RateLimitError as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES - 1:
                    time.sleep(_BASE_RETRY_DELAY)
        else:
            if last_exc:
                raise last_exc
            raise RuntimeError("Failed to generate response")

        content = (response.choices[0].message.content or "").strip()
        logger.info(
            "LMStudioLLM [%s]: query=%r → %d chars",
            mode,
            query[:60],
            len(content),
        )
        return content

    def generate_stream(
        self,
        query: str,
        context: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        mode: str = "rag",
    ) -> Generator[str, None, None]:
        messages = self._build_messages(query, context, history, mode)

        # Retry only the stream-open + first content chunk: once a token has been
        # yielded to the client a partial stream cannot be safely replayed.
        last_exc: Optional[Exception] = None
        iterator = None
        first_delta: Optional[str] = None
        for attempt in range(_MAX_RETRIES):
            try:
                stream = self._client.chat.completions.create(
                    model=self.model,
                    messages=cast(List[ChatCompletionMessageParam], messages),
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    stream=True,
                )
                iterator = iter(stream)
                for first_chunk in iterator:
                    delta = first_chunk.choices[0].delta.content
                    if delta:
                        first_delta = delta
                        break
                break
            except RateLimitError as exc:
                last_exc = exc
                iterator = None
                if attempt < _MAX_RETRIES - 1:
                    logger.warning(
                        "LMStudioLLM stream rate-limited [%s] (attempt %d/%d), retrying",
                        mode,
                        attempt + 1,
                        _MAX_RETRIES,
                    )
                    time.sleep(_BASE_RETRY_DELAY)
        else:
            raise last_exc  # type: ignore[misc]

        total_len = 0
        if first_delta:
            total_len += len(first_delta)
            yield first_delta
        for chunk in iterator or []:
            delta = chunk.choices[0].delta.content
            if delta:
                total_len += len(delta)
                yield delta

    def _build_messages(
        self,
        query: str,
        context: Optional[str],
        history: Optional[List[Dict[str, str]]],
        mode: str,
    ) -> List[Dict[str, str]]:
        if mode == "chitchat":
            return build_chitchat_messages(query, history)
        if mode == "self_eval":
            return build_self_eval_messages(query)
        return build_rag_messages(query, context or "", history)
