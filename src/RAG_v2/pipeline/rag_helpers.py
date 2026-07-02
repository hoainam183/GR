"""RAG pipeline helpers: Tier-3 routing gate, timings, and cache-key utils."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Generator, List, Optional

from query.training_data import RAG_LABELS

logger = logging.getLogger(__name__)


# Confidence below this threshold triggers the Tier-3 LLM domain fallback.
_LLM_FALLBACK_THRESHOLD: float = 0.55
_VALID_DOMAINS = set(RAG_LABELS)

# If the leading domain's probability margin over the 2nd domain exceeds this
# value, Tier-3 is skipped even when absolute confidence < _LLM_FALLBACK_THRESHOLD.
# Rationale: a dominant single domain (e.g. kehoach=0.531, ctdt=0.180, margin=0.351)
# doesn't need an expensive LLM call to disambiguate.
_TIER3_DOMINANT_DOMAIN_MARGIN: float = 0.25


def _should_trigger_tier3(routing: Dict[str, Any]) -> bool:
    """Return True when the Tier-3 LLM domain fallback should run.

    Skips when one domain is already clearly dominant (probability margin over
    the second-best domain exceeds ``_TIER3_DOMINANT_DOMAIN_MARGIN``), saving
    ~12 s per query that would previously trigger an unnecessary LLM call.

    Example: kehoach=0.531, ctdt=0.180 → margin=0.351 > 0.25 → skip Tier-3.
    """
    # NOTE: distinguish "no confidence reported" (None) from a genuine low score.
    # `routing.get("confidence") or 1.0` would turn both None and 0.0 into 1.0,
    # silently disabling Tier-3 exactly when it is most needed (e.g. the LLM
    # router returns confidence=None). Only skip on a real high-confidence score.
    confidence = routing.get("confidence")
    if confidence is not None and confidence >= _LLM_FALLBACK_THRESHOLD:
        return False

    probs: Dict[str, float] = routing.get("probabilities") or {}
    if len(probs) >= 2:
        sorted_vals = sorted(probs.values(), reverse=True)
        margin = sorted_vals[0] - sorted_vals[1]
        if margin >= _TIER3_DOMINANT_DOMAIN_MARGIN:
            logger.debug(
                "Skipping Tier-3: domain margin=%.3f ≥ threshold=%.3f "
                "(top domain is clearly dominant)",
                margin,
                _TIER3_DOMINANT_DOMAIN_MARGIN,
            )
            return False

    return True


# Route cache avoids repeat classifier calls.
_ROUTE_CACHE_TTL_SEC = 45.0
_ROUTE_CACHE_MAX_SIZE = 256


def _build_cache_key(
    question: str,
    history: "Optional[List[Dict[str, str]]]",
) -> str:
    """Compact cache key from question + last 2 history turns."""
    q = question.strip().lower()
    if not history:
        return q
    recent = history[-2:]
    parts = [
        f"{m.get('role','')}:{str(m.get('content',''))[:120]}" for m in recent
    ]
    return f"{q}||{'|'.join(parts)}"


def _elapsed_ms(start: float) -> float:
    """Return elapsed milliseconds rounded for compact logs/JSON."""
    return round((time.perf_counter() - start) * 1000, 2)


def _chunk_for_stream(text: str, size: int = 24) -> Generator[str, None, None]:
    """Split a finished answer into small pieces for animated delivery.

    Used for answers computed synchronously (e.g. the agent path) so the UI
    animates them in instead of dumping the whole block at once. Splits on
    spaces so markdown tokens are not torn mid-word; newlines inside tokens
    survive. Runs of multiple spaces collapse to a single space in the deltas.
    """
    if not text:
        return
    buf: List[str] = []
    length = 0
    for word in text.split(" "):
        buf.append(word)
        length += len(word) + 1
        if length >= size:
            yield " ".join(buf) + " "
            buf, length = [], 0
    if buf:
        yield " ".join(buf)


def _merge_timings(*timings: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge timing dictionaries while preserving insertion order."""
    merged: Dict[str, Any] = {}
    for timing in timings:
        if timing:
            merged.update(timing)
    return merged


def _log_timings(label: str, timings_ms: Dict[str, Any]) -> None:
    """Log timing breakdown sorted by slowest stage first."""
    if not timings_ms:
        return
    numeric_timings = {
        stage: duration
        for stage, duration in timings_ms.items()
        if isinstance(duration, (int, float))
    }
    if not numeric_timings:
        return
    ordered = sorted(
        numeric_timings.items(), key=lambda item: item[1], reverse=True
    )
    summary = ", ".join(
        f"{stage}={duration:.1f}" for stage, duration in ordered
    )
    logger.info("%s timings (ms): %s", label, summary)
