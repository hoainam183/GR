"""Tavily search/extract execution and web fallback result assembly."""

from __future__ import annotations

import logging
import re
import time

from typing import Any, Dict, Generator, List, Optional, Set

from llm.base import BaseLLM

from .common import (
    _elapsed_ms,
    _fold_vietnamese,
)
from .context import _merge_local_and_web_context
from .url_sanitize import _strip_raw_urls

logger = logging.getLogger(__name__)



# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Tavily Fallback
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•


def _tavily_results_to_docs(
    search_result: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Convert Tavily results into source docs compatible with response mapping."""
    docs: List[Dict[str, Any]] = []
    for idx, item in enumerate(search_result.get("results", []) or [], 1):
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "")
        title = str(item.get("title") or url or "Tavily result")
        content = str(item.get("content") or "")
        if not title and not content:
            continue
        docs.append(
            {
                "id": f"tavily:{url or idx}",
                "text": content,
                "score": round(1.0 / idx, 6),
                "rerank_score": None,
                "collection": "web",
                "metadata": {
                    "title": title,
                    "source": url,
                    "url": url,
                    "provider": "tavily",
                    "collection": "web",
                },
            }
        )
    return docs


def _extract_query_year(text: str) -> Optional[int]:
    """Return the most recent academic year (20XX) mentioned in the query.

    Used to drive Tavily's freshness filter so stale official pages from older
    years are dropped. Returns None when the query mentions no year.
    """
    years = re.findall(r"\b(20\d{2})\b", _fold_vietnamese(text or ""))
    return max(int(y) for y in years) if years else None


def _tavily_search_context(
    *,
    query: str,
    tavily_tool: Any | None,
    max_results: int = 3,
    search_depth: str = "basic",
    extract_urls: Optional[List[str]] = None,
    result_count: Optional[int] = None,
    content_char_limit: Optional[int] = None,
    query_year: Optional[int] = None,
) -> Dict[str, Any]:
    """Search official HUST domains and return context, sources, timings.

    If ``extract_urls`` is provided those URLs are fetched directly via the
    Tavily Extract API (useful for dynamic pages like
    ``ctt.hust.edu.vn/DisplayWeb/DisplayKehoach?kehoach=...`` that may not
    appear in Tavily's search index).

    When no explicit ``extract_urls`` are given the function runs a normal
    search first.  If search returns empty context it then attempts to extract
    content directly from the top URL(s) returned by the search results.
    """
    fallback_t0 = time.perf_counter()
    timings_ms: Dict[str, float] = {}

    if tavily_tool is None:
        logger.info("No Tavily tool configured, skipping web search")
        timings_ms["tavily_total"] = _elapsed_ms(fallback_t0)
        return {
            "context": "",
            "timings": timings_ms,
            "sources": [],
            "used": False,
        }
    try:
        from tools.tavily_search import HUST_OFFICIAL_DOMAINS

        tavily_query = query.strip()
        web_context = ""
        tavily_sources: List[Dict[str, Any]] = []

        # â”€â”€ Path A: caller supplied specific URLs â†’ extract directly â”€â”€â”€â”€â”€â”€
        if extract_urls:
            extract_t0 = time.perf_counter()
            extract_result = tavily_tool.extract(
                urls=extract_urls,
                extract_depth="advanced",
                query=tavily_query or None,
            )
            timings_ms["tavily_extract"] = _elapsed_ms(extract_t0)
            web_context = str(extract_result.get("context") or "")
            tavily_sources = _tavily_results_to_docs(extract_result)
            logger.info(
                "Tavily extract: %d URL(s) â†’ context_len=%d",
                len(extract_urls),
                len(web_context),
            )

        # â”€â”€ Path B: normal keyword search â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        else:
            search_t0 = time.perf_counter()
            search_result = tavily_tool.search(
                tavily_query,
                max_results=max_results,
                search_depth=search_depth,
                include_domains=HUST_OFFICIAL_DOMAINS,
                result_count=result_count,
                content_char_limit=content_char_limit,
                query_year=(
                    query_year
                    if query_year
                    else _extract_query_year(tavily_query)
                ),
            )
            timings_ms["tavily_search"] = _elapsed_ms(search_t0)

            raw_results = search_result.get("results") or []
            timings_ms["web_results_raw_count"] = float(len(raw_results))
            content_lengths = [
                len(str(r.get("content", "")))
                for r in raw_results
                if isinstance(r, dict)
            ]
            if content_lengths:
                timings_ms["web_avg_content_length"] = round(
                    sum(content_lengths) / len(content_lengths), 1
                )

            web_context = str(search_result.get("context") or "")
            tavily_sources = _tavily_results_to_docs(search_result)

            # â”€â”€ Path B2: search found URLs but empty content â†’ extract top URL
            if not web_context and search_result.get("results"):
                top_url = str(search_result["results"][0].get("url", ""))
                if top_url:
                    logger.info(
                        "Tavily search returned empty context, extracting top URL: %s",
                        top_url,
                    )
                    extract_t0 = time.perf_counter()
                    extract_result = tavily_tool.extract(
                        urls=[top_url],
                        extract_depth="advanced",
                        query=tavily_query or None,
                    )
                    timings_ms["tavily_extract"] = _elapsed_ms(extract_t0)
                    web_context = str(extract_result.get("context") or "")
                    if extract_result.get("results"):
                        tavily_sources = _tavily_results_to_docs(extract_result)

        timings_ms["tavily_total"] = _elapsed_ms(fallback_t0)
        return {
            "context": web_context,
            "timings": timings_ms,
            "sources": tavily_sources,
            "used": bool(web_context),
        }
    except Exception:
        logger.warning("Tavily search/extract failed", exc_info=True)
        timings_ms["tavily_total"] = _elapsed_ms(fallback_t0)
        return {
            "context": "",
            "timings": timings_ms,
            "sources": [],
            "used": False,
        }


def _tavily_fallback_result(
    *,
    question: str,
    answer: str,
    tavily_tool: Any | None,
    chat_model: BaseLLM,
    history: List[Dict[str, str]],
    max_results: int = 3,
    search_depth: str = "basic",
    search_query: Optional[str] = None,
    local_context: Optional[str] = None,
    result_count: Optional[int] = None,
    content_char_limit: Optional[int] = None,
) -> Dict[str, Any]:
    """Use Tavily web search and return answer, timings, source docs, status."""
    fallback_t0 = time.perf_counter()
    search_info = _tavily_search_context(
        query=(search_query or question).strip() or question,
        tavily_tool=tavily_tool,
        max_results=max_results,
        search_depth=search_depth,
        result_count=result_count,
        content_char_limit=content_char_limit,
    )
    timings_ms: Dict[str, float] = dict(search_info["timings"])
    web_context = str(search_info.get("context") or "")
    tavily_sources = list(search_info.get("sources") or [])
    # Early-exit only when web context is empty. Short official snippets are
    # still useful for notices/deadlines and should be allowed to regenerate.
    if not web_context:
        return {
            "answer": _strip_raw_urls(answer),
            "timings": timings_ms,
            "sources": tavily_sources,
            "used": False,
        }
    generation_context = _merge_local_and_web_context(
        str(local_context or "").strip(),
        web_context,
    )
    try:
        regenerate_t0 = time.perf_counter()
        new_answer = chat_model.generate(
            query=question,
            context=generation_context,
            history=history,
            mode="rag",
        )
        timings_ms["tavily_generate"] = _elapsed_ms(regenerate_t0)
        timings_ms["tavily_total"] = _elapsed_ms(fallback_t0)
        logger.info("Tavily fallback generated %d chars", len(new_answer))
        return {
            "answer": _strip_raw_urls(new_answer),
            "timings": timings_ms,
            "sources": tavily_sources,
            "used": True,
        }
    except Exception:
        logger.warning(
            "Tavily answer regeneration failed, returning original answer",
            exc_info=True,
        )
        timings_ms["tavily_total"] = _elapsed_ms(fallback_t0)
        return {
            "answer": _strip_raw_urls(answer),
            "timings": timings_ms,
            "sources": tavily_sources,
            "used": False,
        }
