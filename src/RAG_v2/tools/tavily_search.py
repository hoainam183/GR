"""Tavily Web Search Tool — wrapper for the Tavily API."""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Literal, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# ─── Constants ──────────────────────────────────────────────────────────────────
DEFAULT_MAX_RESULTS = 5
DEFAULT_MAX_RETRIES = 3
DEFAULT_MIN_RETRY_DELAY = 1.0
DEFAULT_MIN_INTERVAL = 1.0  # seconds between API calls

# ─── Default Domain Whitelists ────────────────────────────────────────────────
# Tier 1: nguồn chính thức HUST — dùng cho self-eval fallback (scope hẹp)
HUST_DOMAINS: list[str] = [
    "hust.edu.vn",
    "sis.hust.edu.vn",
    "ctt.hust.edu.vn",
    "ctsv.hust.edu.vn",
    "soict.hust.edu.vn",
    "seee.hust.edu.vn",
    "scls.hust.edu.vn",
    "fami.hust.edu.vn",
    "sme.hust.edu.vn",
    "smse.hust.edu.vn",
    "sv-ctt.hust.edu.vn",
]

# Tier 2: nguồn giáo dục VN mở rộng — dùng thêm cho agent web_search
EDU_DOMAINS: list[str] = [
    "moet.gov.vn",
    "vnexpress.net",
    "tuoitre.vn",
    "thanhnien.vn",
    "dantri.com.vn",
]


# ═══════════════════════════════════════════════════════════════════════════════
def _load_tavily_client() -> tuple[Any, type[BaseException]]:
    try:
        from tavily import TavilyClient
        from tavily.errors import InvalidAPIKeyError
    except ModuleNotFoundError as exc:
        if exc.name == "tavily":
            raise RuntimeError(
                "tavily-python is required to use TavilySearchTool"
            ) from exc
        raise
    return TavilyClient, InvalidAPIKeyError


def _normalize_domain(domain: str) -> str:
    value = domain.strip().lower()
    if not value:
        return ""
    parsed = urlparse(value if "://" in value else f"//{value}")
    host = (
        parsed.hostname
        or value.split("/", 1)[0].split("#", 1)[0].split("?", 1)[0]
    )
    return host.rstrip(".")


def _normalize_domains(domains: Optional[List[str]]) -> Optional[List[str]]:
    if domains is None:
        return None
    normalized: List[str] = []
    seen: set[str] = set()
    for domain in domains:
        clean = _normalize_domain(domain)
        if clean and clean not in seen:
            normalized.append(clean)
            seen.add(clean)
    return normalized


class TavilySearchTool:
    """Performs web searches via the Tavily API and formats results for LLM context.

    Parameters:
        api_key: Tavily API key.  Falls back to ``TAVILY_API_KEY`` env var.
        max_results: Default number of results per search.
        max_retries: Number of retry attempts on transient failures.
        min_retry_delay: Base delay (seconds) for exponential backoff.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        max_results: int = DEFAULT_MAX_RESULTS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        min_retry_delay: float = DEFAULT_MIN_RETRY_DELAY,
        default_include_domains: Optional[List[str]] = None,
    ) -> None:
        resolved_key = api_key or os.environ.get("TAVILY_API_KEY", "")
        client_cls, invalid_key_error = _load_tavily_client()
        self._client = client_cls(api_key=resolved_key)
        self._invalid_key_error = invalid_key_error
        self.max_results = max_results
        self.max_retries = max_retries
        self.min_retry_delay = min_retry_delay
        self._last_call_time: float = 0.0
        self.default_include_domains = _normalize_domains(default_include_domains)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        max_results: Optional[int] = None,
        search_depth: Literal["advanced", "basic", "fast", "ultra-fast"] = "basic",
        include_answer: bool = True,
        include_domains: Optional[List[str]] = None,
        exclude_domains: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Execute a web search and return structured results.

        Args:
            query: Search query string.
            max_results: Override the default result count.
            search_depth: ``"basic"`` (fast) or ``"advanced"`` (deeper).
            include_answer: Ask Tavily to generate a short answer.
            include_domains: Restrict results to these domains.
                Falls back to ``default_include_domains`` when *None*.
            exclude_domains: Exclude results from these domains.

        Returns:
            Dict with keys:
            - ``query`` — the original query
            - ``answer`` — Tavily-generated short answer (if requested)
            - ``results`` — list of result dicts (``title``, ``url``, ``content``)
            - ``context`` — pre-formatted string suitable for LLM prompts
        """
        effective_max = max_results or self.max_results
        effective_include = _normalize_domains(
            include_domains
            if include_domains is not None
            else self.default_include_domains
        )
        effective_exclude = _normalize_domains(exclude_domains)
        logger.info(
            "Tavily search: query=%r (max=%d, domains=%s)",
            query[:80],
            effective_max,
            len(effective_include) if effective_include else "all",
        )

        # Rate limiting — enforce minimum interval between calls
        now = time.monotonic()
        elapsed = now - self._last_call_time
        if elapsed < DEFAULT_MIN_INTERVAL:
            time.sleep(DEFAULT_MIN_INTERVAL - elapsed)

        # Retry with exponential backoff
        last_exc: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                self._last_call_time = time.monotonic()
                search_kwargs: Dict[str, Any] = {
                    "query": query,
                    "max_results": effective_max,
                    "search_depth": search_depth,
                    "include_answer": include_answer,
                }
                if effective_include:
                    search_kwargs["include_domains"] = effective_include
                if effective_exclude:
                    search_kwargs["exclude_domains"] = effective_exclude
                response = self._client.search(**search_kwargs)

                results = self._parse_results(response)
                context = self._format_context(results)

                return {
                    "query": query,
                    "answer": response.get("answer", ""),
                    "results": results,
                    "context": context,
                }
            except self._invalid_key_error:
                # Auth errors won't be fixed by retrying — fail immediately
                logger.error("Tavily API key is invalid or missing, aborting")
                raise
            except Exception as exc:
                last_exc = exc
                if attempt < self.max_retries - 1:
                    delay = self.min_retry_delay * (2**attempt)
                    logger.warning(
                        "Tavily search attempt %d/%d failed: %s. Retrying in %.1fs",
                        attempt + 1,
                        self.max_retries,
                        exc,
                        delay,
                    )
                    time.sleep(delay)

        logger.error("Tavily search failed after %d attempts", self.max_retries)
        raise last_exc  # type: ignore[misc]

    def extract(
        self,
        urls: List[str],
        extract_depth: Literal["basic", "advanced"] = "basic",
        query: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fetch and extract content directly from specific URLs (bypass index).

        Use this for dynamic pages (e.g. ``?kehoach=29237``) that web crawlers
        may not have indexed.

        Args:
            urls: List of URLs to extract content from.
            extract_depth: ``"basic"`` (fast) or ``"advanced"`` (deeper extraction).
            query: Optional query hint to guide content extraction.

        Returns:
            Dict with keys:
            - ``results`` — list of dicts (``url``, ``title``, ``content``)
            - ``failed_results`` — list of dicts (``url``, ``error``)
            - ``context`` — pre-formatted string suitable for LLM prompts
        """
        if not urls:
            return {"results": [], "failed_results": [], "context": ""}

        logger.info("Tavily extract: %d URL(s), depth=%s", len(urls), extract_depth)

        # Rate limiting
        now = time.monotonic()
        elapsed = now - self._last_call_time
        if elapsed < DEFAULT_MIN_INTERVAL:
            time.sleep(DEFAULT_MIN_INTERVAL - elapsed)

        last_exc: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                self._last_call_time = time.monotonic()
                extract_kwargs: Dict[str, Any] = {
                    "urls": urls,
                    "extract_depth": extract_depth,
                }
                if query:
                    extract_kwargs["query"] = query
                response = self._client.extract(**extract_kwargs)

                results = self._parse_extract_results(response)
                failed = [
                    {"url": r.get("url", ""), "error": r.get("error", "")}
                    for r in response.get("failed_results", [])
                ]
                context = self._format_context(results)
                return {
                    "results": results,
                    "failed_results": failed,
                    "context": context,
                }
            except self._invalid_key_error:
                logger.error("Tavily API key is invalid or missing, aborting")
                raise
            except Exception as exc:
                last_exc = exc
                if attempt < self.max_retries - 1:
                    delay = self.min_retry_delay * (2**attempt)
                    logger.warning(
                        "Tavily extract attempt %d/%d failed: %s. Retrying in %.1fs",
                        attempt + 1,
                        self.max_retries,
                        exc,
                        delay,
                    )
                    time.sleep(delay)

        logger.error("Tavily extract failed after %d attempts", self.max_retries)
        raise last_exc  # type: ignore[misc]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_extract_results(response: Dict[str, Any]) -> List[Dict[str, str]]:
        """Extract structured results from the raw Tavily extract response."""
        parsed: List[Dict[str, str]] = []
        for item in response.get("results", []):
            content = item.get("raw_content") or item.get("content", "")
            parsed.append(
                {
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "content": content,
                }
            )
        return parsed

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
