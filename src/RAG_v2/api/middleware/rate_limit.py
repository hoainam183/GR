"""FastAPI middleware for per-user / per-IP rate limiting on LLM calls.

Only applies to chat endpoints that trigger LLM invocations:
    - POST /chat
    - POST /chat/v3
    - POST /api/chat/v3
    - POST /chat/stream

All other routes (health, sessions, metrics, auth) are exempt.

Rate-limit information is exposed via response headers:
    X-RateLimit-Limit-Minute
    X-RateLimit-Remaining-Minute
    X-RateLimit-Limit-Day
    X-RateLimit-Remaining-Day
    Retry-After  (only on 429 responses)

Registration note
-----------------
This middleware is registered unconditionally at app-build time. The actual
``SlidingWindowRateLimiter`` instance is created during ``lifespan`` (it needs
the Redis client), so the middleware resolves it lazily from ``app.state``
*per request*. When Redis / the limiter is unavailable the middleware is a
transparent pass-through. This avoids the broken pattern of calling
``app.add_middleware`` from a startup hook — Starlette forbids adding
middleware after the app has started, and ``on_event`` startup hooks do not
even run when a ``lifespan`` handler is provided.
"""

from __future__ import annotations

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

    The limiter is resolved from ``request.app.state.rate_limiter`` at dispatch
    time, so it works correctly with the ``lifespan``-based startup that builds
    the limiter after the middleware stack is assembled.

    Identity is derived from a trusted source only:
      1. The ``sub`` claim of a valid ``Authorization: Bearer`` JWT (signed —
         cannot be spoofed by the caller).
      2. The ``X-Forwarded-For`` header (reverse proxy), first hop.
      3. The direct client IP.

    The request body is intentionally NOT read for identity: reading it in a
    ``BaseHTTPMiddleware`` can dead-lock the downstream handler, and a
    body-supplied ``user_id`` is trivially spoofable, defeating the limit.

    Parameters:
        rpm: Requests per minute (for response headers / fallback).
        rpd: Requests per day (for response headers / fallback).
    """

    def __init__(
        self,
        app,
        rpm: int = 20,
        rpd: int = 200,
    ) -> None:
        super().__init__(app)
        self._rpm = rpm
        self._rpd = rpd

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Only rate-limit LLM-calling endpoints.
        if request.method != "POST" or request.url.path not in _RATE_LIMITED_PATHS:
            return await call_next(request)

        limiter = self._resolve_limiter(request)
        if limiter is None:
            # Redis / limiter unavailable — fail open (pass-through).
            return await call_next(request)

        identifier = self._resolve_identifier(request)
        result = limiter.check(identifier)

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

        # Process the request.
        response = await call_next(request)

        # Record the request AFTER successful processing.
        limiter.record(identifier)

        # Inject rate-limit headers into the response.
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

    @staticmethod
    def _resolve_limiter(request: Request) -> Optional[SlidingWindowRateLimiter]:
        """Fetch the live limiter from app state (built during lifespan)."""
        return getattr(request.app.state, "rate_limiter", None)

    @staticmethod
    def _resolve_identifier(request: Request) -> str:
        """Extract a trusted user identifier for rate limiting.

        Priority:
          1. ``sub`` claim from a valid Bearer JWT (authenticated user).
          2. ``X-Forwarded-For`` first hop (reverse proxy).
          3. Direct client IP.

        Falls back to ``"ip:unknown"`` when nothing is available.
        """
        auth = request.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()
            try:
                from auth.jwt_handler import verify_token

                payload = verify_token(token)
                sub = payload.get("sub")
                if sub:
                    return f"user:{sub}"
            except Exception:
                # Invalid/expired token → fall through to IP-based limiting.
                # The endpoint's own auth dependency (if any) still rejects it.
                pass

        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
            if ip:
                return f"ip:{ip}"

        client_ip = request.client.host if request.client else "unknown"
        return f"ip:{client_ip}"
