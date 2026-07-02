"""Shared low-level utilities and cfg readers used across flow submodules."""

from __future__ import annotations

from datetime import datetime
import logging
import time
import unicodedata

from typing import Any, Dict, Generator, List, Optional, Set

from query.signals import (
    fold_vietnamese_text,
)

logger = logging.getLogger(__name__)


# â”€â”€ Context-length error markers (shared across providers) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
_CTX_ERROR_MARKERS = (
    "context length",
    "maximum context length",
    "too many tokens",
    "tokens to keep",
    "prompt is too long",
    "context_length_exceeded",
)


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Helper
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•


def _elapsed_ms(start: float) -> float:
    """Return elapsed milliseconds rounded for compact logs/JSON."""
    return round((time.perf_counter() - start) * 1000, 2)


def _log_timings(flow_name: str, timings_ms: Dict[str, Any]) -> None:
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
    logger.info("%s timings (ms): %s", flow_name, summary)


def _safe_float(value: Any) -> float:
    """Return *value* as float, or 0.0 when conversion fails."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _cfg_bool(cfg: Dict[str, Any], key: str, default: bool) -> bool:
    """Read a boolean config value with string/env compatibility."""
    value = cfg.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _cfg_str_list(
    cfg: Dict[str, Any],
    key: str,
    default: tuple[str, ...],
) -> List[str]:
    """Read a list config value from a list/tuple/set or comma string."""
    value = cfg.get(key, default)
    if isinstance(value, str):
        items = value.split(",")
    elif isinstance(value, (list, tuple, set)):
        items = list(value)
    else:
        items = list(default)
    return [str(item).strip().lower() for item in items if str(item).strip()]


def _fold_vietnamese(text: str) -> str:
    """Lowercase and strip Vietnamese accents for robust text matching."""
    decomposed = unicodedata.normalize("NFD", text or "")
    without_marks = "".join(
        ch for ch in decomposed if unicodedata.category(ch) != "Mn"
    )
    return without_marks.replace("Ä‘", "d").replace("Ä", "D").casefold()


def _is_date_within_days(date_str: str, days: int) -> bool:
    """Check if date_str (dd/mm/yyyy) is within N days of now."""
    try:
        doc_date = datetime.strptime(date_str.strip(), "%d/%m/%Y")
        return (datetime.now() - doc_date).days <= days
    except (ValueError, TypeError, AttributeError):
        return False


def _dedup_text_values(values: List[str]) -> List[str]:
    out: List[str] = []
    seen: set[str] = set()
    for value in values:
        key = fold_vietnamese_text(value)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out




def _cfg_int(cfg: Dict[str, Any], key: str, default: int) -> int:
    """Read an integer config value with a safe fallback."""
    try:
        return int(cfg.get(key, default))
    except (TypeError, ValueError):
        return default


def _cfg_float(cfg: Dict[str, Any], key: str, default: float) -> float:
    """Read a float config value with a safe fallback."""
    try:
        return float(cfg.get(key, default))
    except (TypeError, ValueError):
        return default


def _is_context_length_error(exc: Exception) -> bool:
    """Detect provider errors caused by prompt/context length overflow."""
    message = str(exc).lower()
    return any(marker in message for marker in _CTX_ERROR_MARKERS)
