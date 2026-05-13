"""FastAPI middleware for per-user / per-IP rate limiting on LLM calls.

Only applies to chat endpoints that trigger LLM invocations:
    - POST /chat
    - POST /chat/v3
    - POST /chat/stream

All other routes (health, sessions, metrics, auth) are exempt.

Rate-limit information is exposed via response headers:
    X-RateLimit-Limit-Minute
    X-RateLimit-Remaining-Minute
    X-RateLimit-Limit-Day
    X-RateLimit-Remaining-Day
    Retry-After  (only on 429 responses)
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse

from cache.rate_limiter import SlidingWindowRateLimiter

logger = logging.getLogger(__name__)

# Paths that consume LLM quota.
_RATE_LIMITED_PATHS = frozenset({
    "/chat",
    "/chat/v3",
    "/api/chat/v3",
    "/chat/stream",
})


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Check rate limits before processing LLM-calling requests.

    Extracts the user identifier from:
      1. ``body.user_id`` (parsed from JSON body for POST requests)
      2. ``X-Forwarded-For`` header (anonymous / fallback to IP)

    When the limit is exceeded, returns HTTP 429 with a ``Retry-After``
    header and JSON body explaining the limit type and reset time.

    Parameters:
        rate_limiter: A :class:`SlidingWindowRateLimiter` instance.
        rpm: Requests per minute (for response headers).
        rpd: Requests per day (for response headers).
    """

    def __init__(
        self,
        app,
        rate_limiter: SlidingWindowRateLimiter,
        rpm: int = 20,
        rpd: int = 200,
    ) -> None:
        super().__init__(app)
        self._limiter = rate_limiter
        self._rpm = rpm
        self._rpd = rpd

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Only rate-limit LLM-calling endpoints
        if request.method != "POST" or request.url.path not in _RATE_LIMITED_PATHS:
            return await call_next(request)

        identifier = await self._resolve_identifier(request)
        result = self._limiter.check(identifier)

        if not result.allowed:
            logger.warning(
                "Rate limit exceeded for %s (%s limit): retry_after=%.1fs",
                identifier[:20],
                result.limit_type,
                result.retry_after_seconds,
            )
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded",
                    "limit_type": result.limit_type,
                    "retry_after_seconds": result.retry_after_seconds,
                },
                headers={
                    "Retry-After": str(int(result.retry_after_seconds) + 1),
                    "X-RateLimit-Limit-Minute": str(self._rpm),
                    "X-RateLimit-Remaining-Minute": str(result.remaining_rpm),
                    "X-RateLimit-Limit-Day": str(self._rpd),
                    "X-RateLimit-Remaining-Day": str(result.remaining_rpd),
                },
            )

        # Process the request
        response = await call_next(request)

        # Record the request AFTER successful processing
        self._limiter.record(identifier)

        # Inject rate-limit headers into response
        response.headers["X-RateLimit-Limit-Minute"] = str(self._rpm)
        response.headers["X-RateLimit-Remaining-Minute"] = str(
            max(0, result.remaining_rpm - 1)  # -1 because we just recorded
        )
        response.headers["X-RateLimit-Limit-Day"] = str(self._rpd)
        response.headers["X-RateLimit-Remaining-Day"] = str(
            max(0, result.remaining_rpd - 1)
        )

        return response

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _resolve_identifier(self, request: Request) -> str:
        """Extract user identifier for rate limiting.

        Priority:
          1. ``user_id`` from JSON body (authenticated user).
          2. ``X-Forwarded-For`` header (reverse proxy).
          3. Client IP from the connection (direct access).

        Falls back to ``"anon"`` when nothing is available (should not happen).
        """
        # Try to get user_id from cached body
        try:
            body_bytes = await request.body()
            if body_bytes:
                body = json.loads(body_bytes)
                user_id = body.get("user_id")
                if user_id:
                    return f"user:{user_id}"
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass

        # Fall back to IP
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
            return f"ip:{ip}"

        client_ip = request.client.host if request.client else "unknown"
        return f"ip:{client_ip}"
