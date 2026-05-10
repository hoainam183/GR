"""FastAPI reusable dependencies for chat endpoints.

Eliminates copy-paste of session resolution and history parsing
that previously appeared verbatim in /chat, /chat/v3, and /chat/stream.
"""

from __future__ import annotations

from typing import Any, Optional


def resolve_session(
    *,
    session_id: str | None,
    user_id: str | None,
    mongo_logger: Any,
    redis_session: Optional[Any] = None,
) -> str | None:
    """Return a valid session ID, creating a new one when necessary.

    When ``redis_session`` is provided (i.e. ``USE_REDIS_SESSION=true``),
    session operations are served from Redis with MongoDB dual-write.
    Otherwise the original MongoDB-only path is used.

    Args:
        session_id: Session ID supplied by the client (may be ``None``).
        user_id:    Authenticated user identifier forwarded to ``new_session``.
        mongo_logger: ``MongoLogger`` instance, or ``None`` when logging is
                      disabled.
        redis_session: Optional ``RedisSessionStore`` instance.

    Returns:
        A valid session ID string, or ``None`` when neither store is available
        and the client provided no session ID.
    """
    # ── Redis path ────────────────────────────────────────────────────────────
    if redis_session is not None:
        if session_id is None or redis_session.get_session(session_id) is None:
            return redis_session.new_session(user_id=user_id)
        return session_id

    # ── Original MongoDB path ─────────────────────────────────────────────────
    if mongo_logger is None:
        return session_id

    if session_id is None or mongo_logger.get_session(session_id) is None:
        return mongo_logger.new_session(user_id=user_id)

    return session_id


def parse_history(
    history: list[Any] | None,
) -> list[dict[str, str]]:
    """Convert a list of ``HistoryMessage`` Pydantic objects to plain dicts.

    Args:
        history: List of ``HistoryMessage`` instances, or ``None``.

    Returns:
        A list of ``{"role": ..., "content": ...}`` dicts, empty when
        ``history`` is ``None`` or empty.
    """
    if not history:
        return []
    return [{"role": m.role, "content": m.content} for m in history]
