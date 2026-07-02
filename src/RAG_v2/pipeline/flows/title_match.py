"""Kehoach source-link title-mention matching."""

from __future__ import annotations

import logging
import re
import unicodedata

from typing import Any, Dict, Generator, List, Optional, Set

logger = logging.getLogger(__name__)



# â”€â”€â”€ Kehoach source-link footer â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# kehoach (notification) docs always carry a real URL in metadata, but the LLM
# does not reliably embed it. When the answer actually references such a doc, we
# deterministically append a verifiable link footer so the user can open the
# original notice.

_KEHOACH_LINK_HEADER = "**Nguá»“n thÃ´ng bÃ¡o:**"
# A title counts as "mentioned" when the answer shares at least this fraction of
# the title's adjacent word-pairs (bigrams). Bigrams are far more discriminative
# than single words, which the kehoach titles share heavily ("há»c ká»³", "nÄƒm há»c").
_TITLE_MENTION_MIN_BIGRAM_OVERLAP = 0.5
# Vietnamese titles use space-separated syllables; need enough to form bigrams.
_TITLE_MENTION_MIN_TOKENS = 4
_MATCH_NORMALIZE_RE = re.compile(r"[^0-9a-zÃ -á»¹]+")


def _normalize_for_match(text: str) -> str:
    """Lowercase, drop punctuation, collapse whitespace for fuzzy matching."""
    lowered = unicodedata.normalize("NFC", text).lower()
    return _MATCH_NORMALIZE_RE.sub(" ", lowered).strip()


def _bigrams(tokens: List[str]) -> Set[str]:
    return {f"{a} {b}" for a, b in zip(tokens, tokens[1:])}


def _title_mentioned(
    answer_norm: str, answer_bigrams: Set[str], title: str
) -> bool:
    """True when ``title`` is referenced in the (normalized) answer text."""
    title_norm = _normalize_for_match(title)
    if not title_norm:
        return False
    if title_norm in answer_norm:
        return True
    title_tokens = title_norm.split()
    if len(title_tokens) < _TITLE_MENTION_MIN_TOKENS:
        return False  # too short to bigram-match; substring already failed
    title_bigrams = _bigrams(title_tokens)
    if not title_bigrams:
        return False
    overlap = len(title_bigrams & answer_bigrams) / len(title_bigrams)
    return overlap >= _TITLE_MENTION_MIN_BIGRAM_OVERLAP
