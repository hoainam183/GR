"""Query Router — classifies user intent into chitchat / rag / tool_search.

Supports two modes:
- ``"llm"``: uses OpenAI LLM with few-shot classification (original behaviour).
- ``"classifier"``: uses a lightweight embedding-based ``DomainClassifier``
  (zero API cost, ~10-50 ms latency).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Literal, Optional

from .prompts import ROUTER_FEW_SHOT, ROUTER_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# ─── Constants ──────────────────────────────────────────────────────────────────
VALID_INTENTS = {"chitchat", "rag", "tool_search"}
DEFAULT_INTENT = "rag"
DEFAULT_MODEL = "gpt-4o-mini"


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

    def route(self, query: str) -> Dict[str, Any]:
        """Classify *query* and return a routing decision.

        Args:
            query: The raw user message.

        Returns:
            Dict with keys:
            - ``intent``: ``"rag"`` | ``"chitchat"`` | ``"tool_search"``
            - ``domain``: sub-domain string or *None* (classifier mode only)
            - ``confidence``: prediction confidence (classifier mode only)
        """
        if self.mode == "classifier":
            return self._route_classifier(query)
        return self._route_llm(query)

    # ------------------------------------------------------------------
    # Classifier-based routing
    # ------------------------------------------------------------------

    def _route_classifier(self, query: str) -> Dict[str, Any]:
        result = self._classifier.predict(query)
        logger.info(
            "Router(classifier): query=%r → intent=%s, domain=%s, conf=%.3f",
            query[:80],
            result["intent"],
            result["domain"],
            result["confidence"],
        )
        return {
            "intent": result["intent"],
            "domain": result["domain"],
            "confidence": result["confidence"],
            "label": result["label"],
            "probabilities": result["probabilities"],
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
