"""DeepSeek LLM provider via OpenAI-compatible endpoint."""

from __future__ import annotations

import logging
import os
import time
from typing import Dict, Generator, List, Optional, cast

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

DEFAULT_MODEL = "deepseek-v4-flash"
DEFAULT_MAX_TOKENS = 1500
DEFAULT_TEMPERATURE = 0.0
_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
_MAX_RETRIES = 3
_BASE_RETRY_DELAY = 2.0


@register_llm("deepseek")
class DeepSeekLLM(BaseLLM):
    """DeepSeek chat model through the OpenAI-compatible API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        resolved_key = (
            api_key
            or os.environ.get("DEEPSEEK_API_KEY")
            or os.environ.get("LLM_API_KEY")
        )
        self._client = OpenAI(api_key=resolved_key, base_url=_DEEPSEEK_BASE_URL)

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
                    delay = _BASE_RETRY_DELAY * (2**attempt)
                    logger.warning(
                        "DeepSeekLLM rate-limited [%s] (attempt %d/%d), retrying in %.1fs",
                        mode,
                        attempt + 1,
                        _MAX_RETRIES,
                        delay,
                    )
                    time.sleep(delay)
        else:
            if last_exc:
                raise last_exc
            raise RuntimeError("Failed to generate response")

        content = (response.choices[0].message.content or "").strip()
        logger.info(
            "DeepSeekLLM [%s]: query=%r -> %d chars",
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

        stream = self._client.chat.completions.create(
            model=self.model,
            messages=cast(List[ChatCompletionMessageParam], messages),
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            stream=True,
        )

        total_len = 0
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                total_len += len(delta)
                yield delta

        logger.info(
            "DeepSeekLLM stream [%s]: query=%r -> %d chars total",
            mode,
            query[:60],
            total_len,
        )

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
