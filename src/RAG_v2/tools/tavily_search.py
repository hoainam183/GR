"""Tavily Web Search Tool — wrapper for the Tavily API."""

from __future__ import annotations

import logging
import os
import re
import time
import unicodedata
from collections import OrderedDict
from threading import RLock
from typing import Any, Dict, List, Literal, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# ─── Constants ──────────────────────────────────────────────────────────────────
DEFAULT_MAX_RESULTS = 5
DEFAULT_MAX_RETRIES = 3
DEFAULT_MIN_RETRY_DELAY = 1.0
DEFAULT_MIN_INTERVAL = 1.0  # seconds between API calls
DEFAULT_CACHE_MAXSIZE = 200
DEFAULT_CACHE_TTL_SECONDS = 3600

# ─── Default Domain Whitelists ────────────────────────────────────────────────
# Tier 1: nguồn chính thức HUST — dùng cho self-eval fallback (scope hẹp)
HUST_OFFICIAL_DOMAINS: list[str] = [
    "hust.edu.vn",
    "sis.hust.edu.vn",
    "ctt.hust.edu.vn",
    "ctsv.hust.edu.vn",
    "sv-ctt.hust.edu.vn",
    "soict.hust.edu.vn",
]

HUST_EXTENDED_DOMAINS: list[str] = [
    "seee.hust.edu.vn",
    "scls.hust.edu.vn",
    "fami.hust.edu.vn",
    "sme.hust.edu.vn",
    "smse.hust.edu.vn",
    "see.hust.edu.vn",
    "sem.hust.edu.vn",
    "fee.hust.edu.vn",
    "fme.hust.edu.vn",
]

# Tier 2: nguồn giáo dục VN mở rộng — dùng thêm cho agent web_search
EDU_AUTHORITATIVE_DOMAINS: list[str] = [
    "moet.gov.vn",
]

HUST_DOMAINS: list[str] = HUST_OFFICIAL_DOMAINS + HUST_EXTENDED_DOMAINS
EDU_DOMAINS: list[str] = EDU_AUTHORITATIVE_DOMAINS

_INVALID_TAVILY_KEY_EXACT = {
    "",
    "your-key-here",
    "change_me",
    "tvly-xxx",
    "your-tavily-api-key-here",
}
_INVALID_TAVILY_KEY_PREFIXES = ("your-", "change_me", "changeme")


# ═══════════════════════════════════════════════════════════════════════════════
def is_valid_tavily_api_key(key: Optional[str]) -> bool:
    """Return True when *key* is non-empty and not a known placeholder."""
    value = (key or "").strip()
    lowered = value.lower()
    if not value or lowered in _INVALID_TAVILY_KEY_EXACT:
        return False
    return not any(lowered.startswith(prefix) for prefix in _INVALID_TAVILY_KEY_PREFIXES)


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


class _SimpleTTLCache:
    """Small thread-external TTL cache backed by OrderedDict."""

    def __init__(self, maxsize: int, ttl_seconds: int) -> None:
        self.maxsize = max(1, int(maxsize))
        self.ttl_seconds = max(1, int(ttl_seconds))
        self._items: OrderedDict[Any, tuple[float, Dict[str, Any]]] = OrderedDict()

    def get(self, key: Any) -> Optional[Dict[str, Any]]:
        now = time.monotonic()
        item = self._items.get(key)
        if item is None:
            return None
        expires_at, value = item
        if expires_at <= now:
            self._items.pop(key, None)
            return None
        self._items.move_to_end(key)
        return value

    def __setitem__(self, key: Any, value: Dict[str, Any]) -> None:
        now = time.monotonic()
        self._items[key] = (now + self.ttl_seconds, value)
        self._items.move_to_end(key)
        while len(self._items) > self.maxsize:
            self._items.popitem(last=False)


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
        cache_maxsize: int = DEFAULT_CACHE_MAXSIZE,
        cache_ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
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
        self._cache_lock = RLock()
        self._cache = _SimpleTTLCache(
            maxsize=cache_maxsize,
            ttl_seconds=cache_ttl_seconds,
        )

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
        cache_key = (
            "search",
            query.strip(),
            effective_max,
            search_depth,
            include_answer,
            tuple(effective_include or ()),
            tuple(effective_exclude or ()),
        )
        with self._cache_lock:
            cached = self._cache.get(cache_key)
        if cached is not None:
            logger.debug("Tavily search cache hit: query=%r", query[:80])
            return dict(cached)

        logger.info(
            "Tavily search: query=%r (max=%d, domains=%s)",
            query[:80],
            effective_max,
            len(effective_include) if effective_include else "all",
        )

        # Retry with exponential backoff
        last_exc: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                self._wait_for_rate_limit()
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
                raw_count = len(results)
                results = self.filter_results(results, min_content_length=100)
                results.sort(
                    key=lambda item: self._rank_result_for_query(query, item),
                    reverse=True,
                )
                if raw_count != len(results):
                    logger.info(
                        "Tavily filter: %d → %d results",
                        raw_count, len(results),
                    )
                context = self._format_context(results)

                parsed_response = {
                    "query": query,
                    "answer": response.get("answer", ""),
                    "results": results,
                    "context": context,
                }
                with self._cache_lock:
                    self._cache[cache_key] = dict(parsed_response)
                return parsed_response
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

        last_exc: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                self._wait_for_rate_limit()
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

    def _wait_for_rate_limit(self) -> None:
        """Enforce a minimum interval between Tavily API calls for this instance."""
        with self._cache_lock:
            now = time.monotonic()
            elapsed = now - self._last_call_time
            if elapsed < DEFAULT_MIN_INTERVAL:
                time.sleep(DEFAULT_MIN_INTERVAL - elapsed)
            self._last_call_time = time.monotonic()

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
    def _parse_results(response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract structured results from the raw Tavily response."""
        parsed: List[Dict[str, Any]] = []
        for item in response.get("results", []):
            parsed.append(
                {
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "content": item.get("content", ""),
                    "score": float(item.get("score", 0.0) or 0.0),
                }
            )
        return parsed

    @staticmethod
    def filter_results(
        results: List[Dict[str, Any]],
        *,
        min_content_length: int = 100,
        min_score: float = 0.0,
        query_year: int | None = None,
    ) -> List[Dict[str, Any]]:
        """Filter low-quality or stale web results.

        Args:
            results: Parsed result list from ``_parse_results()``.
            min_content_length: Drop results with content shorter than this.
            min_score: Drop results with Tavily relevance score below this.
            query_year: If set, drop results mentioning only years older than
                query_year - 1 (freshness filter).

        Returns:
            Filtered list (may be empty — callers must handle).
        """
        import re as _re

        filtered: List[Dict[str, Any]] = []
        for r in results:
            content = r.get("content", "")

            if len(content) < min_content_length:
                continue

            if float(r.get("score", 1.0) or 1.0) < min_score:
                continue

            if query_year:
                years_in_content = _re.findall(r'\b(20\d{2})\b', content)
                if years_in_content:
                    max_year = max(int(y) for y in years_in_content)
                    if max_year < query_year - 1:
                        continue

            filtered.append(r)

        return filtered

    @staticmethod
    def _fold_text(text: str) -> str:
        decomposed = unicodedata.normalize("NFD", text or "")
        without_marks = "".join(
            char for char in decomposed if unicodedata.category(char) != "Mn"
        )
        return without_marks.casefold()

    @classmethod
    def _rank_result_for_query(cls, query: str, result: Dict[str, Any]) -> float:
        """Return a deterministic freshness/relevance score for result ordering."""
        folded_query = cls._fold_text(query)
        folded_blob = cls._fold_text(
            " ".join(
                str(result.get(key, "") or "")
                for key in ("title", "content", "url")
            )
        )

        score = float(result.get("score", 0.0) or 0.0)
        for semester_code in re.findall(r"\b20\d{2}[123]\b", folded_query):
            if semester_code in folded_blob:
                score += 5.0

        for school_year in re.findall(r"\b20\d{2}\s*[-/]\s*20\d{2}\b", folded_query):
            normalized = re.sub(r"\s+", "", school_year)
            if normalized in folded_blob.replace(" ", ""):
                score += 2.0

        if re.search(r"\b(?:ky|ki|hoc\s*ky)\s*he\b", folded_query):
            if re.search(r"\b20\d{2}3\b", folded_blob):
                score += 1.0
            if (
                "20243" in folded_blob
                and "20253" in folded_query
                and "20253" not in folded_blob
            ):
                score -= 2.0

        if any(
            token in folded_query
            for token in ("moi nhat", "latest", "recent", "hien tai")
        ):
            years = [int(year) for year in re.findall(r"\b(20\d{2})\b", folded_blob)]
            if years:
                score += min(max(years) - 2020, 10) / 10.0

        return score

    @staticmethod
    def _format_context(results: List[Dict[str, str]]) -> str:
        """Convert results into a numbered text block for LLM context."""
        parts: List[str] = []
        for i, r in enumerate(results, 1):
            parts.append(f"[{i}] {r['title']}\nURL: {r['url']}\n{r['content']}")
        return "\n\n---\n\n".join(parts)
