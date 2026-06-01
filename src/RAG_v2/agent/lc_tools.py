from __future__ import annotations

import logging
from typing import Any

from .tool_adapters import execute_tool

logger = logging.getLogger(__name__)


def _rag_search(query: str, collection: str) -> str:
    logger.debug("[lc_tools] legacy rag_search collection=%s query='%s'", collection, query[:60])
    return execute_tool("rag_search", {"query": query, "collection": collection})


def _multi_rag_search(queries: list[Any]) -> str:
    """Accept both Pydantic-style query items and plain dicts."""
    query_dicts: list[dict[str, str]] = []
    for item in queries:
        if hasattr(item, "model_dump"):
            item = item.model_dump()
        elif hasattr(item, "dict"):
            item = item.dict()

        if isinstance(item, dict):
            query_dicts.append(
                {
                    "query": str(item.get("query", "")),
                    "collection": str(item.get("collection", "")),
                }
            )
        else:
            logger.warning("[lc_tools] Unexpected query item type: %s", type(item))

    return execute_tool("multi_rag_search", {"queries": query_dicts})


def _compare_cohorts(
    topic: str,
    cohort_a: str,
    cohort_b: str,
    collection: str,
) -> str:
    return execute_tool(
        "compare_cohorts",
        {
            "topic": topic,
            "cohort_a": cohort_a,
            "cohort_b": cohort_b,
            "collection": collection,
        },
    )


def _compare_programs(
    topic: str,
    major_a: str,
    major_b: str,
    collection: str,
    course_keyword: str | None = None,
) -> str:
    return execute_tool(
        "compare_programs",
        {
            "topic": topic,
            "major_a": major_a,
            "major_b": major_b,
            "collection": collection,
            "course_keyword": course_keyword,
        },
    )


def _web_search(query: str) -> str:
    logger.debug("[lc_tools] legacy web_search query='%s'", query[:60])
    return execute_tool("web_search", {"query": query})
