"""LLM-based markdown structure reformatter (admin ingestion step).

Repairs markdown **structure** — heading levels, broken tables, split Vietnamese
diacritics — so the recursive chunker parses parent/child sections correctly,
WITHOUT changing the content. Long documents are split into H1/H2 sections (with
oversized sections further split by paragraph blocks so each LLM call stays under
a token budget), reformatted section-by-section, then merged.

The step is synchronous (like ``clean_markdown``); the pipeline offloads it via
``anyio.to_thread``. It reuses an already-configured :class:`BaseLLM` (built by
``create_llm`` with the reformat token/model overrides) — it never creates its own
client or reads secrets.

Because an LLM cannot be *forced* to preserve every character, a preservation
check compares the reformatted output against the input and returns human-readable
warnings (length drift, missing numbers / article markers). It does NOT discard
the output — the admin reviews the warnings and decides (keep, edit, or roll back).
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from llm.base import BaseLLM

logger = logging.getLogger(__name__)

# A line that opens a top-level section: H1 (``# ``) or H2 (``## ``) followed by
# real text. Used to split a document into reformattable sections.
_SECTION_HEADING_RE = re.compile(r"^#{1,2}\s+\S", re.MULTILINE)

# Digit runs (credits, article numbers, course codes) that must survive reformat.
_NUMBER_RE = re.compile(r"\d+")

# "Điều 12" markers — accent-tolerant so we still count them if OCR split "Đi ều".
_ARTICLE_RE = re.compile(r"[ĐD]i\s*[eề]\s*u\s+(\d+)", re.IGNORECASE)

# Leading/trailing markdown code-fence the model sometimes wraps output in.
_CODE_FENCE_RE = re.compile(r"^```[a-zA-Z]*\n(.*)\n```$", re.DOTALL)

try:  # tiktoken is a declared dependency; degrade gracefully if unavailable.
    import tiktoken

    _ENCODING = tiktoken.get_encoding("cl100k_base")
except Exception:  # pragma: no cover - defensive
    _ENCODING = None


def _count_tokens(text: str) -> int:
    """Approximate token count for section-budgeting (not billing-accurate)."""
    if _ENCODING is not None:
        try:
            return len(_ENCODING.encode(text))
        except Exception:  # pragma: no cover - defensive
            pass
    return max(1, len(text) // 4)


@dataclass
class ReformatResult:
    """Outcome of a reformat pass."""

    text: str
    warnings: List[str] = field(default_factory=list)
    section_count: int = 0


class LLMDocumentReformatter:
    """Normalise markdown structure via an injected LLM, preserving content."""

    def __init__(
        self,
        llm: BaseLLM,
        max_section_tokens: int = 2500,
        length_ratio_min: float = 0.85,
        length_ratio_max: float = 1.20,
    ) -> None:
        self._llm = llm
        self.max_section_tokens = max_section_tokens
        self.length_ratio_min = length_ratio_min
        self.length_ratio_max = length_ratio_max

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reformat(
        self, cleaned_md: str, doc_metadata: Optional[Dict] = None
    ) -> ReformatResult:
        """Reformat *cleaned_md*: split → per-section LLM → merge → validate."""
        if not cleaned_md or not cleaned_md.strip():
            return ReformatResult(text=cleaned_md or "", warnings=[], section_count=0)

        sections = self._split_into_sections(cleaned_md)
        context = self._build_context(doc_metadata)
        reformatted = [self._reformat_section(s, context) for s in sections]
        merged = self._merge_sections(reformatted)
        warnings = self._validate_preservation(cleaned_md, merged)
        logger.info(
            "Reformatted document into %d section(s); %d preservation warning(s).",
            len(sections),
            len(warnings),
        )
        return ReformatResult(
            text=merged, warnings=warnings, section_count=len(sections)
        )

    # ------------------------------------------------------------------
    # Splitting
    # ------------------------------------------------------------------

    def _split_into_sections(self, text: str) -> List[str]:
        """Split on H1/H2 headings, then break oversized sections by blocks."""
        starts = [m.start() for m in _SECTION_HEADING_RE.finditer(text)]
        if not starts:
            raw_segments = [text]
        else:
            raw_segments = []
            if starts[0] > 0:  # preamble before the first heading
                raw_segments.append(text[: starts[0]])
            for i, start in enumerate(starts):
                end = starts[i + 1] if i + 1 < len(starts) else len(text)
                raw_segments.append(text[start:end])

        sections: List[str] = []
        for seg in raw_segments:
            seg = seg.strip()
            if not seg:
                continue
            if _count_tokens(seg) <= self.max_section_tokens:
                sections.append(seg)
            else:
                sections.extend(self._split_oversized(seg))
        return sections

    def _split_oversized(self, section: str) -> List[str]:
        """Greedily group paragraph blocks so each chunk fits the token budget.

        Splitting on blank lines keeps markdown tables (which have no internal
        blank lines) intact within a single chunk.
        """
        blocks = re.split(r"\n{2,}", section)
        chunks: List[str] = []
        current: List[str] = []
        current_tokens = 0
        for block in blocks:
            block_tokens = _count_tokens(block)
            if current and current_tokens + block_tokens > self.max_section_tokens:
                chunks.append("\n\n".join(current))
                current, current_tokens = [], 0
            current.append(block)
            current_tokens += block_tokens
        if current:
            chunks.append("\n\n".join(current))
        return chunks

    # ------------------------------------------------------------------
    # Per-section reformat
    # ------------------------------------------------------------------

    def _reformat_section(self, section: str, context: Optional[str]) -> str:
        """Call the LLM to structurally normalise one section (blocking)."""
        raw = self._llm.generate(section, context=context, mode="reformat")
        return self._strip_code_fence(raw)

    @staticmethod
    def _strip_code_fence(text: str) -> str:
        """Remove an accidental wrapping ```markdown ... ``` fence."""
        text = text.strip()
        match = _CODE_FENCE_RE.match(text)
        return match.group(1).strip() if match else text

    @staticmethod
    def _build_context(doc_metadata: Optional[Dict]) -> Optional[str]:
        """Build a short position hint (document name) for heading-level choice."""
        if not doc_metadata:
            return None
        name = doc_metadata.get("filename") or doc_metadata.get("title")
        return f"Văn bản: {name}" if name else None

    @staticmethod
    def _merge_sections(sections: List[str]) -> str:
        """Rejoin reformatted sections, separating with a blank line."""
        merged = "\n\n".join(s.strip() for s in sections if s.strip())
        return merged.strip() + "\n" if merged else ""

    # ------------------------------------------------------------------
    # Preservation guardrail (warn-only)
    # ------------------------------------------------------------------

    def _validate_preservation(self, original: str, reformatted: str) -> List[str]:
        """Compare output vs input; return warnings (never raises, never drops)."""
        warnings: List[str] = []

        if not reformatted.strip():
            warnings.append(
                "Kết quả reformat rỗng — LLM có thể đã xoá toàn bộ nội dung."
            )
            return warnings

        warnings.extend(self._check_length_ratio(original, reformatted))
        warnings.extend(
            self._check_missing_tokens(
                original,
                reformatted,
                _NUMBER_RE,
                "con số",
            )
        )
        warnings.extend(
            self._check_missing_tokens(
                original,
                reformatted,
                _ARTICLE_RE,
                "mục 'Điều'",
            )
        )
        return warnings

    def _check_length_ratio(self, original: str, reformatted: str) -> List[str]:
        """Warn if non-whitespace length drifts outside the configured band."""
        orig_len = len(re.sub(r"\s+", "", original))
        new_len = len(re.sub(r"\s+", "", reformatted))
        if orig_len == 0:
            return []
        ratio = new_len / orig_len
        if ratio < self.length_ratio_min or ratio > self.length_ratio_max:
            return [
                f"Độ dài nội dung thay đổi bất thường: tỉ lệ {ratio:.2f} "
                f"(ngưỡng {self.length_ratio_min:.2f}–{self.length_ratio_max:.2f}). "
                "Cần kiểm tra xem LLM có thêm/bớt nội dung không."
            ]
        return []

    @staticmethod
    def _check_missing_tokens(
        original: str,
        reformatted: str,
        pattern: re.Pattern,
        label: str,
    ) -> List[str]:
        """Warn if any occurrences of *pattern* were lost (multiset compare)."""
        orig_counts = Counter(m.group(0) for m in pattern.finditer(original))
        new_counts = Counter(m.group(0) for m in pattern.finditer(reformatted))
        missing = orig_counts - new_counts
        if not missing:
            return []
        total = sum(missing.values())
        examples = ", ".join(list(missing.keys())[:5])
        return [
            f"Thiếu {total} {label} so với bản gốc (ví dụ: {examples}). "
            "Có thể LLM đã bỏ sót nội dung — cần rà soát."
        ]
