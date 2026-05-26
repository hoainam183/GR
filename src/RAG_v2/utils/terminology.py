"""Shared academic terminology helpers."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class TerminologyAlias:
    """A canonical full term and its common abbreviation."""

    full: str
    abbr: str


HUST_TERMINOLOGY_ALIASES: tuple[TerminologyAlias, ...] = (
    TerminologyAlias("nghiên cứu sinh", "NCS"),
    TerminologyAlias("điểm rèn luyện", "ĐRL"),
    TerminologyAlias("nghiên cứu khoa học", "NCKH"),
    TerminologyAlias("thời khóa biểu", "TKB"),
    TerminologyAlias("học viên cao học", "HVCH"),
    TerminologyAlias("chương trình đào tạo", "CTĐT"),
)

HUST_TERMINOLOGY_GLOSSARY_TEXT = (
    "NCS = nghiên cứu sinh; ĐRL = điểm rèn luyện; "
    "NCKH = nghiên cứu khoa học; TKB = thời khóa biểu; "
    "HVCH = học viên cao học; CTĐT = chương trình đào tạo."
)


def _fold_text(text: str) -> str:
    value = unicodedata.normalize("NFD", text or "")
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    return value.replace("đ", "d").replace("Đ", "D").casefold()


def _contains_term(text: str, term: str) -> bool:
    folded_text = _fold_text(text)
    folded_term = _fold_text(term)
    return bool(re.search(rf"(?<!\w){re.escape(folded_term)}(?!\w)", folded_text))


def _replace_term_once(text: str, term: str, replacement: str) -> str:
    variants = [re.escape(term)]
    folded = _fold_text(term)
    if folded != term:
        variants.append(re.escape(folded))
    pattern = re.compile(rf"(?<!\w)({'|'.join(variants)})(?!\w)", re.IGNORECASE)
    return pattern.sub(lambda match: replacement.format(match=match.group(1)), text)


def expand_academic_abbreviations(
    text: str,
    aliases: Iterable[TerminologyAlias] = HUST_TERMINOLOGY_ALIASES,
) -> str:
    """Add full-term/abbreviation aliases to a query without changing intent.

    The expansion is intentionally idempotent: if either side already appears
    alongside the other in the same query, no duplicate parenthetical alias is
    appended.
    """
    expanded = text or ""
    for alias in aliases:
        has_full = _contains_term(expanded, alias.full)
        has_abbr = _contains_term(expanded, alias.abbr)
        if has_full and not has_abbr:
            expanded = _replace_term_once(
                expanded,
                alias.full,
                "{match} (" + alias.abbr + ")",
            )
        elif has_abbr and not has_full:
            expanded = _replace_term_once(
                expanded,
                alias.abbr,
                "{match} (" + alias.full + ")",
            )
    return expanded
