"""Chat Model — Gemini wrapper with streaming and multi-prompt support."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Generator, List, Optional, cast

from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam

from .prompts import (
    CHITCHAT_SYSTEM_PROMPT,
    CHITCHAT_USER_TEMPLATE,
    CHITCHAT_USER_WITH_HISTORY_TEMPLATE,
    RAG_SYSTEM_PROMPT,
    RAG_USER_TEMPLATE,
    RAG_USER_WITH_HISTORY_TEMPLATE,
)

logger = logging.getLogger(__name__)

# ─── Constants ──────────────────────────────────────────────────────────────────
DEFAULT_MODEL = "gemini-2.5-flash"
DEFAULT_MAX_TOKENS = 1024
DEFAULT_TEMPERATURE = 0.3
_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


# ═══════════════════════════════════════════════════════════════════════════════
class ChatModel:
    """Wrapper around Gemini API (via OpenAI-compatible endpoint) with streaming and multi-prompt support.

    Supports two modes:
    - **RAG**: answer grounded in retrieved context documents.
    - **Chitchat**: friendly conversational response.

    Parameters:
        api_key: Google API key. If *None*, reads from ``GOOGLE_API_KEY`` env var.
        model: Gemini model identifier (e.g. ``gemini-2.5-flash``).
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
    # Public API
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
            query: The user question.
            context: Retrieved document context (required for RAG mode).
            history: Recent chat history as list of ``{"role", "content"}`` dicts.
            mode: ``"rag"`` or ``"chitchat"``.

        Returns:
            The generated response text.
        """
        messages = self._build_messages(query, context, history, mode)

        response = self._client.chat.completions.create(
            model=self.model,
            messages=cast(List[ChatCompletionMessageParam], messages),
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

        content = (response.choices[0].message.content or "").strip()
        logger.info(
            "ChatModel [%s]: query=%r → %d chars",
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
            "ChatModel stream [%s]: query=%r → %d chars total",
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
        """Assemble the message list for the Gemini API."""
        if mode == "chitchat":
            return self._build_chitchat_messages(query, history)
        return self._build_rag_messages(query, context, history)

    def _build_rag_messages(
        self,
        query: str,
        context: Optional[str],
        history: Optional[List[Dict[str, str]]],
    ) -> List[Dict[str, str]]:
        """Build messages for RAG mode."""
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": RAG_SYSTEM_PROMPT},
        ]

        if history:
            history_text = _format_history(history)
            user_content = RAG_USER_WITH_HISTORY_TEMPLATE.format(
                history=history_text,
                context=context or "",
                query=query,
            )
        else:
            user_content = RAG_USER_TEMPLATE.format(
                context=context or "",
                query=query,
            )

        messages.append({"role": "user", "content": user_content})
        return messages

    def _build_chitchat_messages(
        self,
        query: str,
        history: Optional[List[Dict[str, str]]],
    ) -> List[Dict[str, str]]:
        """Build messages for chitchat mode."""
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": CHITCHAT_SYSTEM_PROMPT},
        ]

        if history:
            history_text = _format_history(history)
            user_content = CHITCHAT_USER_WITH_HISTORY_TEMPLATE.format(
                history=history_text,
                query=query,
            )
        else:
            user_content = CHITCHAT_USER_TEMPLATE.format(query=query)

        messages.append({"role": "user", "content": user_content})
        return messages


# ─── Helpers ────────────────────────────────────────────────────────────────────


def _format_history(history: List[Dict[str, str]]) -> str:
    """Format chat history into a readable string."""
    return "\n".join(
        f"{msg['role'].capitalize()}: {msg['content']}" for msg in history
    )
