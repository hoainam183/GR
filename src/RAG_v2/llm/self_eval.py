"""Self Evaluation — checks response quality, faithfulness, and completeness."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

from llm.base import BaseLLM
from .prompts import SELF_EVAL_USER_TEMPLATE

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
class SelfEvaluator:
    """Evaluates the quality of a generated response using an LLM judge.

    Checks three criteria:
    - **Relevance**: does the answer address the question?
    - **Faithfulness**: is the answer grounded in the provided context?
    - **Completeness**: does the answer cover all relevant information?

    Returns a pass/fail decision with detailed reasoning.

    Parameters:
        llm: A :class:`~llm.base.BaseLLM` instance used as the evaluation judge.
    """

    def __init__(self, llm: BaseLLM) -> None:
        self._llm = llm

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
        user_content = SELF_EVAL_USER_TEMPLATE.format(
            query=query,
            context=context,
            response=response,
        )
        raw = self._llm.generate(query=user_content, mode="self_eval")
        result = self._parse_evaluation(raw)

        logger.info(
            "SelfEval: pass=%s, status=%s, web=%s, relevance=%s, "
            "faithfulness=%s, completeness=%s — %s",
            result.get("pass"),
            result.get("answer_status"),
            result.get("should_web_search"),
            result.get("relevance"),
            result.get("faithfulness"),
            result.get("completeness"),
            result.get("reason", "")[:80],
        )

        return result

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _strip_markdown_fences(text: str) -> str:
        """Remove markdown code fences (```json ... ```) wrapping JSON."""
        stripped = text.strip()
        if stripped.startswith("```"):
            # Remove opening fence (```json or ```)
            first_newline = stripped.find("\n")
            if first_newline != -1:
                stripped = stripped[first_newline + 1 :]
            # Remove closing fence
            if stripped.rstrip().endswith("```"):
                stripped = stripped.rstrip()[:-3].rstrip()
        return stripped

    def _parse_evaluation(self, raw: str) -> Dict[str, Any]:
        """Parse the LLM's JSON evaluation response.

        Falls back to a failing result when parsing fails.
        """
        try:
            cleaned = self._strip_markdown_fences(raw)
            data = json.loads(cleaned)
            passed = bool(data.get("pass", False))
            answer_status = str(
                data.get(
                    "answer_status",
                    "answered" if passed else "insufficient",
                )
                or ""
            ).strip()
            if answer_status not in {"answered", "insufficient", "stale_risk"}:
                answer_status = "answered" if passed else "insufficient"
            should_web_raw = data.get("should_web_search")
            should_web_search = (
                bool(should_web_raw)
                if should_web_raw is not None
                else not passed
            )
            # Ensure required keys exist
            return {
                "pass": passed,
                "relevance": data.get("relevance", "bad"),
                "faithfulness": data.get("faithfulness", "hallucinated"),
                "completeness": data.get("completeness", "incomplete"),
                "answer_status": answer_status,
                "should_web_search": should_web_search,
                "web_search_query": str(data.get("web_search_query", "") or ""),
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
                "answer_status": "insufficient",
                "should_web_search": True,
                "web_search_query": "",
                "reason": f"Failed to parse evaluation: {raw[:200]}",
                "raw_response": raw,
            }
