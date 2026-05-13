"""Sliding-window rate limiter backed by Redis.

Uses a sorted-set-based sliding window algorithm for both per-minute and
per-day limits.  Each request timestamp is stored as a member so the
window slides continuously rather than resetting at fixed intervals.

Redis Schema::

    rate:min:{identifier}  → Sorted Set  (member=uuid, score=timestamp)  TTL 120s
    rate:day:{identifier}  → Sorted Set  (member=uuid, score=timestamp)  TTL 86 400s

The ``identifier`` is either a ``user_id`` (authenticated) or an IP address
(anonymous).
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from typing import Optional

import redis

logger = logging.getLogger(__name__)


@dataclass
class RateLimitResult:
    """Outcome of a rate-limit check.

    Attributes:
        allowed: Whether the request is permitted.
        remaining_rpm: Remaining requests in the current minute window.
        remaining_rpd: Remaining requests in the current day window.
        retry_after_seconds: Seconds until the next request is permitted
            (only meaningful when ``allowed`` is ``False``).
        limit_type: Which limit was hit (``"minute"`` or ``"day"``), or
            ``None`` when the request is allowed.
    """

    allowed: bool
    remaining_rpm: int
    remaining_rpd: int
    retry_after_seconds: float = 0.0
    limit_type: Optional[str] = None


class SlidingWindowRateLimiter:
    """Per-user sliding-window rate limiter.

    Parameters:
        redis_client: Shared ``redis.Redis`` instance.
        rpm: Maximum requests per minute.
        rpd: Maximum requests per day.
        alert_threshold: Fraction (0–1) at which a warning is logged.
    """

    _MINUTE_WINDOW = 60  # seconds
    _DAY_WINDOW = 86_400  # seconds

    def __init__(
        self,
        redis_client: redis.Redis,
        rpm: int = 20,
        rpd: int = 200,
        alert_threshold: float = 0.8,
    ) -> None:
        self._r = redis_client
        self._rpm = rpm
        self._rpd = rpd
        self._alert_threshold = alert_threshold

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check(self, identifier: str) -> RateLimitResult:
        """Check whether *identifier* is within rate limits.

        Does NOT record the request — call :meth:`record` after a
        successful LLM invocation.

        Args:
            identifier: ``user_id`` for authenticated users, IP for anonymous.

        Returns:
            A :class:`RateLimitResult` describing whether the request is
            allowed and how much capacity remains.
        """
        now = time.time()
        min_key = f"rate:min:{identifier}"
        day_key = f"rate:day:{identifier}"

        try:
            pipe = self._r.pipeline()

            # Clean expired entries
            pipe.zremrangebyscore(min_key, "-inf", now - self._MINUTE_WINDOW)
            pipe.zremrangebyscore(day_key, "-inf", now - self._DAY_WINDOW)

            # Count current entries
            pipe.zcard(min_key)
            pipe.zcard(day_key)

            # Get oldest entry for retry_after calculation
            pipe.zrange(min_key, 0, 0, withscores=True)
            pipe.zrange(day_key, 0, 0, withscores=True)

            results = pipe.execute()
            # results: [removed_min, removed_day, count_min, count_day, oldest_min, oldest_day]
            count_min = results[2]
            count_day = results[3]
            oldest_min = results[4]  # [(member, score)] or []
            oldest_day = results[5]

        except redis.RedisError:
            logger.warning("Redis rate limit check failed — allowing request", exc_info=True)
            return RateLimitResult(
                allowed=True,
                remaining_rpm=self._rpm,
                remaining_rpd=self._rpd,
            )

        remaining_rpm = max(0, self._rpm - count_min)
        remaining_rpd = max(0, self._rpd - count_day)

        # Alert at threshold
        if remaining_rpm <= int(self._rpm * (1 - self._alert_threshold)):
            logger.warning(
                "Rate limit alert: %s has %d/%d minute requests remaining",
                identifier[:20],
                remaining_rpm,
                self._rpm,
            )
        if remaining_rpd <= int(self._rpd * (1 - self._alert_threshold)):
            logger.warning(
                "Rate limit alert: %s has %d/%d daily requests remaining",
                identifier[:20],
                remaining_rpd,
                self._rpd,
            )

        # Check minute limit
        if count_min >= self._rpm:
            retry_after = 0.0
            if oldest_min:
                oldest_ts = oldest_min[0][1]
                retry_after = max(0.0, (oldest_ts + self._MINUTE_WINDOW) - now)
            return RateLimitResult(
                allowed=False,
                remaining_rpm=0,
                remaining_rpd=remaining_rpd,
                retry_after_seconds=round(retry_after, 1),
                limit_type="minute",
            )

        # Check daily limit
        if count_day >= self._rpd:
            retry_after = 0.0
            if oldest_day:
                oldest_ts = oldest_day[0][1]
                retry_after = max(0.0, (oldest_ts + self._DAY_WINDOW) - now)
            return RateLimitResult(
                allowed=False,
                remaining_rpm=remaining_rpm,
                remaining_rpd=0,
                retry_after_seconds=round(retry_after, 1),
                limit_type="day",
            )

        return RateLimitResult(
            allowed=True,
            remaining_rpm=remaining_rpm,
            remaining_rpd=remaining_rpd,
        )

    def record(self, identifier: str) -> None:
        """Record a successful request for *identifier*.

        Call this AFTER the LLM call completes (not before), so failed
        requests don't consume quota.
        """
        now = time.time()
        member = str(uuid.uuid4())
        min_key = f"rate:min:{identifier}"
        day_key = f"rate:day:{identifier}"

        try:
            pipe = self._r.pipeline()
            pipe.zadd(min_key, {member: now})
            pipe.expire(min_key, self._MINUTE_WINDOW + 10)  # small buffer
            pipe.zadd(day_key, {member: now})
            pipe.expire(day_key, self._DAY_WINDOW + 60)
            pipe.execute()
        except redis.RedisError:
            logger.warning("Redis rate limit record failed", exc_info=True)

    def get_usage(self, identifier: str) -> dict:
        """Return current usage stats for an identifier (debug/metrics)."""
        now = time.time()
        try:
            pipe = self._r.pipeline()
            pipe.zremrangebyscore(f"rate:min:{identifier}", "-inf", now - self._MINUTE_WINDOW)
            pipe.zremrangebyscore(f"rate:day:{identifier}", "-inf", now - self._DAY_WINDOW)
            pipe.zcard(f"rate:min:{identifier}")
            pipe.zcard(f"rate:day:{identifier}")
            results = pipe.execute()
            return {
                "minute_used": results[2],
                "minute_limit": self._rpm,
                "day_used": results[3],
                "day_limit": self._rpd,
            }
        except redis.RedisError:
            return {"error": "Redis unavailable"}
