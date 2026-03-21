"""Tavily Web Search Tool — wrapper for the Tavily API."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from tavily import TavilyClient

logger = logging.getLogger(__name__)

# ─── Constants ──────────────────────────────────────────────────────────────────
DEFAULT_MAX_RESULTS = 5


# ═══════════════════════════════════════════════════════════════════════════════
class TavilySearchTool:
    """Performs web searches via the Tavily API and formats results for LLM context.

    Parameters:
        api_key: Tavily API key.  Falls back to ``TAVILY_API_KEY`` env var.
        max_results: Default number of results per search.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        max_results: int = DEFAULT_MAX_RESULTS,
    ) -> None:
        resolved_key = api_key or os.environ.get("TAVILY_API_KEY", "")
        self._client = TavilyClient(api_key=resolved_key)
        self.max_results = max_results

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        max_results: Optional[int] = None,
        search_depth: str = "basic",
        include_answer: bool = True,
    ) -> Dict[str, Any]:
        """Execute a web search and return structured results.

        Args:
            query: Search query string.
            max_results: Override the default result count.
            search_depth: ``"basic"`` (fast) or ``"advanced"`` (deeper).
            include_answer: Ask Tavily to generate a short answer.

        Returns:
            Dict with keys:
            - ``query`` — the original query
            - ``answer`` — Tavily-generated short answer (if requested)
            - ``results`` — list of result dicts (``title``, ``url``, ``content``)
            - ``context`` — pre-formatted string suitable for LLM prompts
        """
        effective_max = max_results or self.max_results
        logger.info(
            "Tavily search: query=%r (max=%d)", query[:80], effective_max
        )

        response = self._client.search(
            query=query,
            max_results=effective_max,
            search_depth=search_depth,
            include_answer=include_answer,
        )

        results = self._parse_results(response)
        context = self._format_context(results)

        return {
            "query": query,
            "answer": response.get("answer", ""),
            "results": results,
            "context": context,
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_results(response: Dict[str, Any]) -> List[Dict[str, str]]:
        """Extract structured results from the raw Tavily response."""
        parsed: List[Dict[str, str]] = []
        for item in response.get("results", []):
            parsed.append(
                {
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "content": item.get("content", ""),
                }
            )
        return parsed

    @staticmethod
    def _format_context(results: List[Dict[str, str]]) -> str:
        """Convert results into a numbered text block for LLM context."""
        parts: List[str] = []
        for i, r in enumerate(results, 1):
            parts.append(f"[{i}] {r['title']}\nURL: {r['url']}\n{r['content']}")
        return "\n\n---\n\n".join(parts)
