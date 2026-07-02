"""Chat-history trimming and budgets."""

from __future__ import annotations

import logging

from typing import Any, Dict, Generator, List, Optional, Set

logger = logging.getLogger(__name__)



# Personal-pronoun pattern removed â€” entity extraction is now handled by QueryReflector._extract_entities

# â”€â”€ History budget â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
_DEFAULT_HISTORY_LIMIT = 8
_HISTORY_MESSAGE_CHAR_LIMIT = 400  # chars per message before truncation
_HISTORY_TOTAL_CHAR_BUDGET = 2000  # total chars across all kept messages


def _trim_history(
    history: Optional[List[Dict[str, str]]],
    limit: int = _DEFAULT_HISTORY_LIMIT,
) -> List[Dict[str, str]]:
    """Keep recent history within message-count and character budgets.

    Truncates individual messages that are too long and stops adding
    older messages once the total character budget is exhausted. This
    prevents context-length errors that grow with conversation length.
    """
    if not history:
        return []

    recent = history[-limit:]
    normalised: List[Dict[str, str]] = []
    for msg in recent:
        role = str(msg.get("role", "")).strip()
        content = str(msg.get("content", "") or "").strip()
        if role not in {"user", "assistant"} or not content:
            continue
        if len(content) > _HISTORY_MESSAGE_CHAR_LIMIT:
            content = content[:_HISTORY_MESSAGE_CHAR_LIMIT] + "\u2026"
        normalised.append({"role": role, "content": content})

    if not normalised:
        return []

    # Apply total char budget from newest to oldest.
    kept_reversed: List[Dict[str, str]] = []
    used = 0
    for msg in reversed(normalised):
        msg_len = len(msg["content"])
        if used + msg_len > _HISTORY_TOTAL_CHAR_BUDGET and kept_reversed:
            break
        kept_reversed.append(msg)
        used += msg_len

    return list(reversed(kept_reversed))
