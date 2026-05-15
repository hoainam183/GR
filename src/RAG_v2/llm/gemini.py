"""GeminiLLM — Gemini provider via OpenAI-compatible endpoint."""

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
DEFAULT_MODEL = "gemini-3.1-flash-lite-preview"
DEFAULT_MAX_TOKENS = 1024
DEFAULT_TEMPERATURE = 0.3
_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
_MAX_RETRIES = 3
_BASE_RETRY_DELAY = 2.0  # seconds


# ═══════════════════════════════════════════════════════════════════════════════
@register_llm("gemini")
class GeminiLLM(BaseLLM):
    """Gemini LLM via OpenAI-compatible endpoint.

    Implements :class:`BaseLLM` so it can be swapped with any other provider.
    Accepts the same constructor arguments as the legacy ``ChatModel`` for
    backwards compatibility.

    Parameters:
        api_key: Google API key. If *None*, reads from ``GOOGLE_API_KEY`` env var.
        model: Gemini model identifier (e.g. ``gemini-3.1-flash-lite-preview``).
        temperature: Sampling temperature.
        max_tokens: Maximum tokens in the generated response.
    """

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
        resolved_key = api_key or os.environ.get("GOOGLE_API_KEY")
        self._client = OpenAI(api_key=resolved_key, base_url=_GEMINI_BASE_URL)

    # ------------------------------------------------------------------
    # BaseLLM interface
    # ------------------------------------------------------------------

    def generate(
        self,
        query: str,
        context: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        mode: str = "rag",
    ) -> str:
        """Generate a complete response (non-streaming).

        Args:
            query: The user question (or pre-formatted prompt for self_eval mode).
            context: Retrieved document context (required for RAG mode).
            history: Recent chat history as list of ``{"role", "content"}`` dicts.
            mode: ``"rag"``, ``"chitchat"``, or ``"self_eval"``.

        Returns:
            The generated response text.
        """
        messages = self._build_messages(query, context, history, mode)

        # Retry with exponential backoff for rate-limit errors
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
                        "GeminiLLM rate-limited [%s] (attempt %d/%d), retrying in %.1fs",
                        mode,
                        attempt + 1,
                        _MAX_RETRIES,
                        delay,
                    )
                    time.sleep(delay)
        else:
            raise last_exc  # type: ignore[misc]

        content = (response.choices[0].message.content or "").strip()
        logger.info(
            "GeminiLLM [%s]: query=%r → %d chars",
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
        """Generate a streaming response, yielding text chunks.

        Args:
            query: The user question.
            context: Retrieved document context (required for RAG mode).
            history: Recent chat history as list of ``{"role", "content"}`` dicts.
            mode: ``"rag"`` or ``"chitchat"``.

        Yields:
            Text chunks as they arrive from the API.
        """
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
            "GeminiLLM stream [%s]: query=%r → %d chars total",
            mode,
            query[:60],
            total_len,
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _build_messages(
        self,
        query: str,
        context: Optional[str],
        history: Optional[List[Dict[str, str]]],
        mode: str,
    ) -> List[Dict[str, str]]:
        """Assemble the message list for the given mode."""
        if mode == "chitchat":
            return build_chitchat_messages(query, history)
        if mode == "self_eval":
            return build_self_eval_messages(query)
        return build_rag_messages(query, context or "", history)
