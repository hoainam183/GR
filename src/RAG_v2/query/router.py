"""Query Router — classifies user intent into chitchat / rag / tool_search."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from openai import OpenAI

from .prompts import ROUTER_FEW_SHOT, ROUTER_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# ─── Constants ──────────────────────────────────────────────────────────────────
VALID_INTENTS = {"chitchat", "rag", "tool_search"}
DEFAULT_INTENT = "rag"
DEFAULT_MODEL = "gpt-4o-mini"


# ═══════════════════════════════════════════════════════════════════════════════
class QueryRouter:
    """Routes user queries to the appropriate processing pipeline.

    Uses an LLM with few-shot examples to classify intent as one of:
    ``chitchat``, ``rag``, or ``tool_search``.

    Parameters:
        api_key: OpenAI API key. If *None*, reads from ``OPENAI_API_KEY`` env var.
        model: Chat model used for classification.
        temperature: Sampling temperature (low for deterministic classification).
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        temperature: float = 0.0,
    ) -> None:
        self.model = model
        self.temperature = temperature
        self._client = OpenAI(api_key=api_key)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def route(self, query: str) -> Dict[str, Any]:
        """Classify *query* and return a routing decision.

        Args:
            query: The raw user message.

        Returns:
            Dict with at least ``{"intent": "rag"|"chitchat"|"tool_search"}``.
        """
        messages = self._build_messages(query)

        response = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=50,
        )

        raw = response.choices[0].message.content.strip()
        intent = self._parse_intent(raw)

        logger.info(
            "Router: query=%r → intent=%s (raw=%r)", query[:80], intent, raw
        )

        return {"intent": intent, "raw_response": raw}

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _build_messages(self, query: str) -> list:
        """Assemble the few-shot message list for the LLM."""
        messages = [{"role": "system", "content": ROUTER_SYSTEM_PROMPT}]
        messages.extend(ROUTER_FEW_SHOT)
        messages.append({"role": "user", "content": query})
        return messages

    def _parse_intent(self, raw: str) -> str:
        """Extract intent string from the LLM's JSON response.

        Falls back to ``DEFAULT_INTENT`` ("rag") when parsing fails.
        """
        try:
            data = json.loads(raw)
            intent = data.get("intent", DEFAULT_INTENT)
            if intent not in VALID_INTENTS:
                logger.warning(
                    "Unknown intent '%s', falling back to '%s'",
                    intent,
                    DEFAULT_INTENT,
                )
                return DEFAULT_INTENT
            return intent
        except (json.JSONDecodeError, AttributeError):
            logger.warning(
                "Failed to parse router response: %r, falling back to '%s'",
                raw,
                DEFAULT_INTENT,
            )
            return DEFAULT_INTENT
