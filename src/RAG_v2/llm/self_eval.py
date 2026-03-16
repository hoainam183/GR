"""Self Evaluation — checks response quality, faithfulness, and completeness."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from openai import OpenAI

from .prompts import SELF_EVAL_SYSTEM_PROMPT, SELF_EVAL_USER_TEMPLATE

logger = logging.getLogger(__name__)

# ─── Constants ──────────────────────────────────────────────────────────────────
DEFAULT_MODEL = "gpt-4o-mini"


# ═══════════════════════════════════════════════════════════════════════════════
class SelfEvaluator:
    """Evaluates the quality of a generated response using an LLM judge.

    Checks three criteria:
    - **Relevance**: does the answer address the question?
    - **Faithfulness**: is the answer grounded in the provided context?
    - **Completeness**: does the answer cover all relevant information?

    Returns a pass/fail decision with detailed reasoning.

    Parameters:
        api_key: OpenAI API key. If *None*, reads from ``OPENAI_API_KEY`` env var.
        model: Model used for evaluation (should be fast and cheap).
        temperature: Sampling temperature (low for consistent evaluation).
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

    def evaluate(
        self,
        query: str,
        context: str,
        response: str,
    ) -> Dict[str, Any]:
        """Evaluate a generated *response* against *query* and *context*.

        Args:
            query: The original user question.
            context: The retrieved document context used for generation.
            response: The assistant's generated answer.

        Returns:
            Dict with keys: ``pass`` (bool), ``relevance``, ``faithfulness``,
            ``completeness``, and ``reason`` (str).
        """
        messages = self._build_messages(query, context, response)

        llm_response = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=256,
        )

        raw = llm_response.choices[0].message.content.strip()
        result = self._parse_evaluation(raw)

        logger.info(
            "SelfEval: pass=%s, relevance=%s, faithfulness=%s, completeness=%s — %s",
            result.get("pass"),
            result.get("relevance"),
            result.get("faithfulness"),
            result.get("completeness"),
            result.get("reason", "")[:80],
        )

        return result

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _build_messages(
        self,
        query: str,
        context: str,
        response: str,
    ) -> list:
        """Assemble the evaluation prompt messages."""
        user_content = SELF_EVAL_USER_TEMPLATE.format(
            query=query,
            context=context,
            response=response,
        )
        return [
            {"role": "system", "content": SELF_EVAL_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

    def _parse_evaluation(self, raw: str) -> Dict[str, Any]:
        """Parse the LLM's JSON evaluation response.

        Falls back to a failing result when parsing fails.
        """
        try:
            data = json.loads(raw)
            # Ensure required keys exist
            return {
                "pass": bool(data.get("pass", False)),
                "relevance": data.get("relevance", "bad"),
                "faithfulness": data.get("faithfulness", "hallucinated"),
                "completeness": data.get("completeness", "incomplete"),
                "reason": data.get("reason", ""),
                "raw_response": raw,
            }
        except (json.JSONDecodeError, AttributeError):
            logger.warning(
                "Failed to parse self-eval response: %r — marking as fail",
                raw,
            )
            return {
                "pass": False,
                "relevance": "bad",
                "faithfulness": "hallucinated",
                "completeness": "incomplete",
                "reason": f"Failed to parse evaluation: {raw[:200]}",
                "raw_response": raw,
            }
