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
VALID_DOMAINS = {"ctdt", "quydinh", "kehoach", "stsv"}
DEFAULT_INTENT = "rag"
DEFAULT_MODEL = "gpt-4o-mini"

# Number of recent chat turns to prepend as context for the classifier / LLM.
# Raised from 2 → 5: multi-turn registration queries often reference a course
# mentioned 3–4 turns back (e.g. "Kỳ này còn slot không?" after "Môn IT4062E").
_CONTEXT_WINDOW = 5


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
    
    # Avoid context bleeding: if the query is a complete sentence (>= 6 words), 
    # it likely contains its own context. Do not prepend history.
    if len(query.split()) >= 6:
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

        intent = result["intent"]
        domains = result.get("domains", [result["domain"]] if result["domain"] else [])
        confidence = result["confidence"]

        # Production monitoring: log confidence so histogram can be built
        # to detect distribution drift (alert if P(conf < 0.55) > 20%).
        log_level = logging.WARNING if confidence < 0.55 else logging.INFO
        logger.log(
            log_level,
            "Router(classifier): query=%r → intent=%s domains=%s conf=%.3f%s",
            query[:80],
            intent,
            domains,
            confidence,
            " [LOW_CONF]" if confidence < 0.55 else "",
        )
        return {
            "intent": intent,
            "domain": result["domain"],
            "domains": domains,
            "confidence": confidence,
            "label": result["label"],
            "probabilities": result.get("probabilities", {}),
        }

    # ------------------------------------------------------------------
    # LLM-based routing
    # ------------------------------------------------------------------

    def _route_llm(self, query: str) -> Dict[str, Any]:
        messages = self._build_messages(query)

        response = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=100,  # raised from 50 to accommodate domains list
        )

        raw = response.choices[0].message.content.strip()
        intent, domains = self._parse_response(raw)

        logger.info(
            "Router(llm): query=%r → intent=%s domains=%s (raw=%r)",
            query[:80],
            intent,
            domains,
            raw,
        )

        return {
            "intent": intent,
            "domain": domains[0] if domains else None,
            "domains": domains,
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

    def _parse_response(self, raw: str) -> tuple[str, List[str]]:
        """Extract intent and domains from the LLM's JSON response.

        Returns:
            (intent, domains) — falls back to (DEFAULT_INTENT, []) on failure.
        """
        try:
            data = json.loads(raw)
            intent = data.get("intent", DEFAULT_INTENT)
            if intent not in VALID_INTENTS:
                logger.warning(
                    "Unknown intent %r, falling back to %r", intent, DEFAULT_INTENT
                )
                intent = DEFAULT_INTENT

            raw_domains: List[str] = data.get("domains", [])
            domains = [d for d in raw_domains if d in VALID_DOMAINS]

            if intent != "rag":
                domains = []

            return intent, domains

        except (json.JSONDecodeError, AttributeError):
            logger.warning(
                "Failed to parse router response: %r, falling back to %r",
                raw,
                DEFAULT_INTENT,
            )
            return DEFAULT_INTENT, []