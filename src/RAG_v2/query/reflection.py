"""Query Reflection — rewrite, clarify, format, and add context from history."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from openai import OpenAI

from .prompts import (
    REWRITE_NO_HISTORY_TEMPLATE,
    REWRITE_SYSTEM_PROMPT,
    REWRITE_WITH_HISTORY_TEMPLATE,
)

logger = logging.getLogger(__name__)

# ─── Constants ──────────────────────────────────────────────────────────────────
_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
DEFAULT_MODEL = "gemini-2.0-flash"
DEFAULT_HISTORY_LIMIT = 5


# ═══════════════════════════════════════════════════════════════════════════════
class QueryReflector:
    """Rewrites and enriches a user query before it enters the retrieval pipeline.

    Responsibilities:
        1. **Rewrite** — make the query clear and self-contained.
        2. **Clarify** — resolve vague references using chat history.
        3. **Format** — normalise the query for embedding search.
        4. **Add context** — incorporate relevant chat history.

    All four steps are collapsed into a single LLM call that receives
    the raw query (and optionally recent chat history) and returns an
    improved version.

    Parameters:
        api_key: Google API key for Gemini. If *None*, reads from
            ``GOOGLE_API_KEY`` env var.
        model: Gemini model identifier used for query rewriting.
        temperature: Sampling temperature.
        history_limit: Maximum number of recent history messages to include.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        temperature: float = 0.3,
        history_limit: int = DEFAULT_HISTORY_LIMIT,
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.history_limit = history_limit
        resolved_key = api_key or os.getenv("GOOGLE_API_KEY", "")
        self._client = OpenAI(api_key=resolved_key, base_url=_GEMINI_BASE_URL)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reflect(
        self,
        query: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """Rewrite *query* into a retrieval-optimised form.

        Args:
            query: The raw user message.
            chat_history: Recent conversation messages, each a dict with
                ``"role"`` (``"user"``/``"assistant"``) and ``"content"`` keys.

        Returns:
            Dict with ``{"original": str, "rewritten": str}``.
        """
        user_prompt = self._build_user_prompt(query, chat_history)

        messages = [
            {"role": "system", "content": REWRITE_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        response = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=256,
        )

        rewritten = response.choices[0].message.content.strip()

        # If the LLM returns empty or just whitespace, keep the original
        if not rewritten:
            rewritten = query

        logger.info(
            "Reflection: %r → %r (history_len=%d)",
            query[:60],
            rewritten[:60],
            len(chat_history) if chat_history else 0,
        )

        return {"original": query, "rewritten": rewritten}

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _build_user_prompt(
        self,
        query: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """Format the user prompt, optionally including chat history."""
        if chat_history:
            recent = chat_history[-self.history_limit :]
            history_text = "\n".join(
                f"{msg['role'].capitalize()}: {msg['content']}"
                for msg in recent
            )
            return REWRITE_WITH_HISTORY_TEMPLATE.format(
                history=history_text, query=query
            )
        return REWRITE_NO_HISTORY_TEMPLATE.format(query=query)
