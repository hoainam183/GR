"""Structured Tracing — request-scoped performance tracking.

Provides a ``RequestTrace`` context object that travels through the pipeline,
collecting timing data for each stage. Also provides a ``@trace_stage``
decorator for automatic timing of individual functions.

Usage::

    from utils.tracing import RequestTrace, trace_stage

    trace = RequestTrace()

    with trace.stage("embedding"):
        vec = embedder.embed_query(query)

    # Or use as decorator:
    @trace_stage("reranking")
    def rerank(query, docs): ...

    # At the end:
    trace.summary()  # → {"embedding": 45.2, "reranking": 120.1, "total": 165.3}
"""

from __future__ import annotations

import functools
import logging
import time
import uuid
from contextlib import contextmanager
from typing import Any, Dict, Generator, Optional

logger = logging.getLogger(__name__)


class RequestTrace:
    """Collects timing and metadata for a single request lifecycle.

    Thread-safe for read, not designed for concurrent writes (each
    request gets its own trace instance).

    Parameters:
        correlation_id: Optional unique ID. Auto-generated if not provided.
        query: The original user query (for logging context).
    """

    def __init__(
        self,
        correlation_id: Optional[str] = None,
        query: Optional[str] = None,
    ) -> None:
        self.correlation_id: str = correlation_id or str(uuid.uuid4())[:12]
        self.query: Optional[str] = query
        self.created_at: float = time.time()
        self._start_time: float = time.perf_counter()
        self._stages: Dict[str, float] = {}
        self._metadata: Dict[str, Any] = {}
        self._errors: list[Dict[str, Any]] = []

    @contextmanager
    def stage(self, name: str) -> Generator[None, None, None]:
        """Context manager that times a named pipeline stage.

        Example::

            with trace.stage("retrieval"):
                results = searcher.search(...)
        """
        t0 = time.perf_counter()
        try:
            yield
        finally:
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
            # Accumulate if stage is called multiple times (e.g. multiple searches)
            self._stages[name] = round(
                self._stages.get(name, 0.0) + elapsed_ms, 2
            )

    def record_stage(self, name: str, elapsed_ms: float) -> None:
        """Manually record a stage duration (for cases where context manager doesn't fit)."""
        self._stages[name] = round(
            self._stages.get(name, 0.0) + elapsed_ms, 2
        )

    def set_metadata(self, key: str, value: Any) -> None:
        """Attach metadata to this trace (e.g., route, model_name, etc.)."""
        self._metadata[key] = value

    def record_error(self, stage: str, error: str) -> None:
        """Record an error that occurred during processing."""
        self._errors.append({
            "stage": stage,
            "error": error,
            "timestamp_ms": round((time.perf_counter() - self._start_time) * 1000, 2),
        })

    @property
    def total_ms(self) -> float:
        """Total elapsed time since trace creation."""
        return round((time.perf_counter() - self._start_time) * 1000, 2)

    @property
    def stages(self) -> Dict[str, float]:
        """Return a copy of the stage timings."""
        return dict(self._stages)

    def summary(self) -> Dict[str, Any]:
        """Return the complete trace summary for logging/MongoDB storage.

        Returns:
            Dict with ``correlation_id``, ``stages``, ``total_ms``,
            ``metadata``, and ``errors``.
        """
        return {
            "correlation_id": self.correlation_id,
            "query": (self.query or "")[:100],
            "stages": dict(self._stages),
            "total_ms": self.total_ms,
            "metadata": dict(self._metadata),
            "errors": list(self._errors) if self._errors else None,
            "created_at": self.created_at,
        }

    def log_summary(self, label: str = "Pipeline") -> None:
        """Log the timing summary at INFO level."""
        if not self._stages:
            return
        ordered = sorted(
            self._stages.items(), key=lambda item: item[1], reverse=True
        )
        summary = ", ".join(f"{s}={d:.1f}ms" for s, d in ordered)
        logger.info(
            "[%s] %s trace: total=%.1fms | %s",
            self.correlation_id,
            label,
            self.total_ms,
            summary,
        )

    def __repr__(self) -> str:
        return f"RequestTrace(id={self.correlation_id}, stages={len(self._stages)}, total={self.total_ms:.0f}ms)"


def trace_stage(stage_name: str):
    """Decorator that automatically times a function as a pipeline stage.

    Requires the decorated function to accept a ``trace`` keyword argument
    of type ``RequestTrace``. If ``trace`` is None or not provided, the
    decorator is a no-op.

    Example::

        @trace_stage("reranking")
        def rerank_documents(query, docs, *, trace=None):
            ...
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            trace = kwargs.get("trace")
            if trace is None:
                return func(*args, **kwargs)

            t0 = time.perf_counter()
            try:
                result = func(*args, **kwargs)
            except Exception as exc:
                elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
                trace.record_stage(stage_name, elapsed_ms)
                trace.record_error(stage_name, str(exc))
                raise
            else:
                elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
                trace.record_stage(stage_name, elapsed_ms)
                return result

        return wrapper

    return decorator
