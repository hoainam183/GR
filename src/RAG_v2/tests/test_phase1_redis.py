"""Tests for Redis session store and rate limiter (Phase 1).

These tests use ``fakeredis`` as an in-memory Redis substitute so they can
run without a real Redis server.

Run:
    pytest tests/test_phase1_redis.py -v
"""

from __future__ import annotations

import time
import uuid
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Attempt to import fakeredis — skip all tests if unavailable.
# ---------------------------------------------------------------------------
try:
    import fakeredis
except ImportError:
    fakeredis = None

pytestmark = pytest.mark.skipif(
    fakeredis is None,
    reason="fakeredis not installed (pip install fakeredis)",
)


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture()
def redis_client():
    """Return a fakeredis client that behaves like ``redis.Redis``."""
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture()
def session_store(redis_client):
    """Return a ``RedisSessionStore`` backed by fakeredis (no MongoDB)."""
    from cache.session_store import RedisSessionStore

    return RedisSessionStore(redis_client=redis_client, mongo_logger=None)


@pytest.fixture()
def rate_limiter(redis_client):
    """Return a ``SlidingWindowRateLimiter`` with tight limits for testing."""
    from cache.rate_limiter import SlidingWindowRateLimiter

    return SlidingWindowRateLimiter(
        redis_client=redis_client,
        rpm=3,   # low limit for easy testing
        rpd=10,
        alert_threshold=0.5,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# RedisSessionStore tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestRedisSessionStore:
    """Tests for ``cache.session_store.RedisSessionStore``."""

    def test_new_session_returns_uuid(self, session_store):
        sid = session_store.new_session(user_id="u1")
        assert sid is not None
        # Should be a valid UUID
        uuid.UUID(sid)

    def test_get_session_roundtrip(self, session_store):
        sid = session_store.new_session(user_id="u1")
        session = session_store.get_session(sid)
        assert session is not None
        assert session["session_id"] == sid
        assert session["user_id"] == "u1"
        assert session["turn_count"] == 0

    def test_get_session_not_found(self, session_store):
        assert session_store.get_session("nonexistent") is None

    def test_list_sessions_newest_first(self, session_store):
        s1 = session_store.new_session(user_id="u1")
        s2 = session_store.new_session(user_id="u1")
        s3 = session_store.new_session(user_id="u1")

        sessions = session_store.list_sessions(user_id="u1")
        ids = [s["session_id"] for s in sessions]
        # Newest first
        assert ids[0] == s3
        assert ids[-1] == s1

    def test_list_sessions_different_users_isolated(self, session_store):
        session_store.new_session(user_id="u1")
        session_store.new_session(user_id="u2")

        u1_sessions = session_store.list_sessions(user_id="u1")
        u2_sessions = session_store.list_sessions(user_id="u2")
        assert len(u1_sessions) == 1
        assert len(u2_sessions) == 1

    def test_list_sessions_respects_limit(self, session_store):
        for _ in range(5):
            session_store.new_session(user_id="u1")

        sessions = session_store.list_sessions(user_id="u1", limit=3)
        assert len(sessions) == 3

    def test_update_session_on_turn(self, session_store):
        sid = session_store.new_session(user_id="u1")
        session_store.update_session_on_turn(sid, "Hello world?", turn_id=1)

        session = session_store.get_session(sid)
        assert session["turn_count"] == 1
        assert session["title"] == "Hello world?"

    def test_update_session_title_only_on_first_turn(self, session_store):
        sid = session_store.new_session(user_id="u1")
        session_store.update_session_on_turn(sid, "First question", turn_id=1)
        session_store.update_session_on_turn(sid, "Second question", turn_id=2)

        session = session_store.get_session(sid)
        assert session["turn_count"] == 2
        assert session["title"] == "First question"  # unchanged by 2nd turn

    def test_dual_write_with_mongo_logger(self, redis_client):
        from cache.session_store import RedisSessionStore

        mock_mongo = MagicMock()
        mock_mongo._sessions = MagicMock()
        # Simulate MongoDB insert
        mock_mongo._sessions.insert_one = MagicMock()

        store = RedisSessionStore(
            redis_client=redis_client,
            mongo_logger=mock_mongo,
        )
        sid = store.new_session(user_id="u1")
        assert sid is not None
        # Redis should have the session
        session = store.get_session(sid)
        assert session is not None
        mock_mongo._sessions.insert_one.assert_called_once()
        assert mock_mongo._sessions.insert_one.call_args.args[0]["session_id"] == sid

    def test_fallback_on_redis_miss_without_mongo(self, session_store):
        """When Redis misses and no MongoDB, return None."""
        result = session_store.get_session("missing-id")
        assert result is None

    def test_list_sessions_empty_user(self, session_store):
        sessions = session_store.list_sessions(user_id="nobody")
        assert sessions == []

    def test_sync_from_mongo_warms_updated_metadata(self, redis_client):
        from cache.session_store import RedisSessionStore

        mock_mongo = MagicMock()
        mock_mongo.get_session.return_value = {
            "session_id": "s1",
            "user_id": "u1",
            "title": "First question",
            "created_at": "2026-05-15T00:00:00+00:00",
            "updated_at": "2026-05-15T00:01:00+00:00",
            "turn_count": 1,
        }
        store = RedisSessionStore(redis_client=redis_client, mongo_logger=mock_mongo)
        store.sync_from_mongo("s1")

        session = store.get_session("s1")
        assert session["title"] == "First question"
        assert session["turn_count"] == 1

    def test_delete_session_removes_metadata_and_history(self, session_store, redis_client):
        sid = session_store.new_session(user_id="u1")
        redis_client.lpush(f"history:{sid}", '{"role":"user","content":"hello"}')

        assert session_store.delete_session(sid, user_id="u1") is True
        assert redis_client.hgetall(f"session:{sid}") == {}
        assert redis_client.exists(f"history:{sid}") == 0
        assert redis_client.zscore("user_sessions:u1", sid) is None

    def test_update_session_title_roundtrip(self, session_store):
        sid = session_store.new_session(user_id="u1")

        assert session_store.update_session_title(sid, "Renamed") is True
        assert session_store.get_session(sid)["title"] == "Renamed"

    def test_update_session_title_does_not_create_missing_hash(self, session_store, redis_client):
        assert session_store.update_session_title("missing", "Renamed") is False
        assert redis_client.hgetall("session:missing") == {}


# ═══════════════════════════════════════════════════════════════════════════════
# SlidingWindowRateLimiter tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestSlidingWindowRateLimiter:
    """Tests for ``cache.rate_limiter.SlidingWindowRateLimiter``."""

    def test_allows_within_limit(self, rate_limiter):
        result = rate_limiter.check("user:test1")
        assert result.allowed is True
        assert result.remaining_rpm == 3  # limit - 0 used

    def test_blocks_after_minute_limit(self, rate_limiter):
        # Record 3 requests (rpm=3)
        for _ in range(3):
            rate_limiter.record("user:test2")

        result = rate_limiter.check("user:test2")
        assert result.allowed is False
        assert result.limit_type == "minute"
        assert result.retry_after_seconds > 0

    def test_blocks_after_daily_limit(self, rate_limiter):
        # Record 10 requests (rpd=10)
        for _ in range(10):
            rate_limiter.record("user:test3")

        result = rate_limiter.check("user:test3")
        assert result.allowed is False
        assert result.limit_type in ("minute", "day")

    def test_different_users_independent(self, rate_limiter):
        for _ in range(3):
            rate_limiter.record("user:alice")

        # Alice should be blocked
        alice_result = rate_limiter.check("user:alice")
        assert alice_result.allowed is False

        # Bob should be fine
        bob_result = rate_limiter.check("user:bob")
        assert bob_result.allowed is True

    def test_remaining_decreases(self, rate_limiter):
        rate_limiter.record("user:test4")
        result = rate_limiter.check("user:test4")
        assert result.allowed is True
        assert result.remaining_rpm == 2  # 3 - 1

    def test_retry_after_is_reasonable(self, rate_limiter):
        for _ in range(3):
            rate_limiter.record("user:test5")

        result = rate_limiter.check("user:test5")
        assert result.allowed is False
        # retry_after should be between 0 and 60 seconds
        assert 0 < result.retry_after_seconds <= 60

    def test_get_usage_returns_counts(self, rate_limiter):
        rate_limiter.record("user:test6")
        rate_limiter.record("user:test6")
        usage = rate_limiter.get_usage("user:test6")
        assert usage["minute_used"] == 2
        assert usage["minute_limit"] == 3
        assert usage["day_used"] == 2
        assert usage["day_limit"] == 10

    def test_check_without_record_does_not_consume(self, rate_limiter):
        """Calling check() should not consume quota."""
        rate_limiter.check("user:test7")
        rate_limiter.check("user:test7")
        rate_limiter.check("user:test7")
        # Should still be allowed because check doesn't record
        result = rate_limiter.check("user:test7")
        assert result.allowed is True
        assert result.remaining_rpm == 3


# ═══════════════════════════════════════════════════════════════════════════════
# RedisManager tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestRedisManager:
    """Tests for ``cache.redis_client.RedisManager``."""

    def test_redact_url_with_password(self):
        from cache.redis_client import RedisManager

        assert "***" in RedisManager._redact_url("redis://:secret@host:6379/0")

    def test_redact_url_without_password(self):
        from cache.redis_client import RedisManager

        url = "redis://localhost:6379/0"
        assert RedisManager._redact_url(url) == url


# ═══════════════════════════════════════════════════════════════════════════════
# Dependencies tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestResolveSession:
    """Tests for ``api.dependencies.resolve_session``."""

    def test_redis_path_creates_new_session(self, redis_client):
        from api.dependencies import resolve_session
        from cache.session_store import RedisSessionStore

        store = RedisSessionStore(redis_client=redis_client)
        sid = resolve_session(
            session_id=None,
            user_id="u1",
            mongo_logger=None,
            redis_session=store,
        )
        assert sid is not None
        uuid.UUID(sid)  # valid UUID

    def test_redis_path_reuses_existing_session(self, redis_client):
        from api.dependencies import resolve_session
        from cache.session_store import RedisSessionStore

        store = RedisSessionStore(redis_client=redis_client)
        original = store.new_session(user_id="u1")
        sid = resolve_session(
            session_id=original,
            user_id="u1",
            mongo_logger=None,
            redis_session=store,
        )
        assert sid == original

    def test_mongo_path_when_redis_not_provided(self):
        from api.dependencies import resolve_session

        mock_mongo = MagicMock()
        mock_mongo.get_session.return_value = None
        mock_mongo.new_session.return_value = "mongo-session-id"

        sid = resolve_session(
            session_id=None,
            user_id="u1",
            mongo_logger=mock_mongo,
            redis_session=None,
        )
        assert sid == "mongo-session-id"

    def test_no_store_returns_none(self):
        from api.dependencies import resolve_session

        sid = resolve_session(
            session_id=None,
            user_id="u1",
            mongo_logger=None,
            redis_session=None,
        )
        assert sid is None
