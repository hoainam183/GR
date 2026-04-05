"""Query Router — classifies user intent into chitchat / rag / tool_search.

Supports two modes:
- ``"llm"``: uses OpenAI LLM with few-shot classification (original behaviour).
- ``"classifier"``: uses a lightweight embedding-based ``DomainClassifier``
  (zero API cost, ~10-50 ms latency).

Improvements (Tier 1 + 2):
- ``build_routing_input`` prepends recent conversation context so that
  follow-up queries like "Còn điều kiện tiên quyết là gì?" are routed
  correctly.
- ``route()`` accepts an optional ``chat_history`` argument.
- ``domains`` (list) is returned alongside ``domain`` (single primary).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Literal, Optional

from .prompts import ROUTER_FEW_SHOT, ROUTER_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# ─── Constants ──────────────────────────────────────────────────────────────────
VALID_INTENTS = {"chitchat", "rag", "tool_search"}
DEFAULT_INTENT = "rag"
DEFAULT_MODEL = "gpt-4o-mini"

# Number of recent chat turns to prepend as context
_CONTEXT_WINDOW = 2


def build_routing_input(
    query: str,
    chat_history: Optional[List[Dict[str, str]]] = None,
) -> str:
    """Build the input string sent to the classifier / LLM.

    Prepends the last ``_CONTEXT_WINDOW`` message contents so that
    short follow-up queries are routed with the right domain in mind.
    BGE-M3 handles long inputs well, so the extra tokens are cheap.

    Args:
        query: The raw user message.
        chat_history: List of ``{"role": ..., "content": ...}`` dicts.

    Returns:
        Contextualised query string.
    """
    if not chat_history:
        return query
    recent = chat_history[-_CONTEXT_WINDOW:]
    ctx = " | ".join(m["content"] for m in recent if m.get("content"))
    if not ctx:
        return query
    return f"[CTX: {ctx}] {query}"


# ═══════════════════════════════════════════════════════════════════════════════
class QueryRouter:
    """Routes user queries to the appropriate processing pipeline.

    Parameters:
        mode: ``"classifier"`` (default, zero-cost) or ``"llm"`` (OpenAI).
        api_key: OpenAI API key (only needed when *mode="llm"*).
        model: Chat model used for LLM classification.
        temperature: Sampling temperature for LLM mode.
        embedder: Shared embedder instance for classifier mode.
                  If *None*, ``DomainClassifier`` will lazy-load BGE-M3.
        classifier_model_path: Path to a saved classifier ``.joblib`` file.
                               If *None*, uses the default path.
    """

    def __init__(
        self,
        mode: Literal["classifier", "llm"] = "classifier",
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        temperature: float = 0.0,
        embedder: Optional[Any] = None,
        classifier_model_path: Optional[str] = None,
    ) -> None:
        self.mode = mode
        self.model = model
        self.temperature = temperature

        if mode == "llm":
            from openai import OpenAI

            self._client = OpenAI(api_key=api_key)
            self._classifier = None
        else:
            from .domain_classifier import DomainClassifier

            self._client = None
            self._classifier = DomainClassifier(embedder=embedder)
            self._classifier.load(classifier_model_path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def route(
        self,
        query: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """Classify *query* and return a routing decision.

        Args:
            query: The raw user message.
            chat_history: Recent conversation turns used for context-aware
                          routing.  Passed to ``build_routing_input``.

        Returns:
            Dict with keys:

            - ``intent``: ``"rag"`` | ``"chitchat"`` | ``"tool_search"``
            - ``domain``: primary sub-domain string or *None*
            - ``domains``: list of all active RAG domains (may be >1)
            - ``confidence``: calibrated prediction confidence
        """
        if self.mode == "classifier":
            return self._route_classifier(query, chat_history)
        return self._route_llm(query)

    # ------------------------------------------------------------------
    # Classifier-based routing
    # ------------------------------------------------------------------

    def _route_classifier(
        self,
        query: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        routing_input = build_routing_input(query, chat_history)
        result = self._classifier.predict(routing_input)

        logger.info(
            "Router(classifier): query=%r → intent=%s, domains=%s, conf=%.3f",
            query[:80],
            result["intent"],
            result.get("domains"),
            result["confidence"],
        )
        return {
            "intent": result["intent"],
            "domain": result["domain"],
            "domains": result.get(
                "domains", [result["domain"]] if result["domain"] else []
            ),
            "confidence": result["confidence"],
            "label": result["label"],
            "probabilities": result.get("probabilities", {}),
        }

    # ------------------------------------------------------------------
    # LLM-based routing (original)
    # ------------------------------------------------------------------

    def _route_llm(self, query: str) -> Dict[str, Any]:
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
            "Router(llm): query=%r → intent=%s (raw=%r)",
            query[:80],
            intent,
            raw,
        )

        return {
            "intent": intent,
            "domain": None,
            "domains": [],
            "confidence": None,
            "raw_response": raw,
        }

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
