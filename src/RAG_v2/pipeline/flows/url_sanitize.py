"""Answer/stream URL sanitization."""

from __future__ import annotations

import logging
import re
import time

logger = logging.getLogger(__name__)


# ── Answer post-processing: sanitize URLs ──────────────────────────────────────
# Three-step pipeline so users never see ugly raw URLs in answers:
#   1. Fix broken markdown links (URL-encode spaces in URLs)
#   2. Shorten long anchor text → "tại đây"
#   3. Wrap remaining raw URLs → [tại đây](url)

# Markdown link: [text](url)
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]*)\)")

# Standalone raw URL NOT inside markdown link parentheses.
_RAW_URL_RE = re.compile(r"(?<!\()(?<!\[)(https?://[^\s)\]>]+)")

# Short anchor phrases the LLM already uses well — no need to replace.
_NATURAL_ANCHORS = frozenset({
    "tại đây", "xem chi tiết", "xem thêm", "xem lịch thi",
    "xem tài liệu", "tải về", "chi tiết", "xem", "link",
    "xem biểu mẫu", "trang web", "đường dẫn",
})

# Maximum word count before anchor text is shortened to "tại đây".
_MAX_ANCHOR_WORDS = 4


def _fix_markdown_link_spaces(answer: str) -> str:
    """URL-encode spaces inside markdown link URLs so they render properly.

    ``[text](https://host/path with spaces/file.docx)``
    →  ``[text](https://host/path%20with%20spaces/file.docx)``
    """
    def _encode_url(m: re.Match) -> str:
        anchor, url = m.group(1), m.group(2)
        fixed_url = url.replace(" ", "%20")
        return f"[{anchor}]({fixed_url})"

    return _MD_LINK_RE.sub(_encode_url, answer)


def _shorten_long_anchors(answer: str) -> str:
    """Shorten verbose anchor text in markdown links to *tại đây*.

    Keeps naturally short anchors (≤ ``_MAX_ANCHOR_WORDS`` words) and anchors
    that match known ``_NATURAL_ANCHORS`` unchanged.
    """
    def _maybe_shorten(m: re.Match) -> str:
        anchor, url = m.group(1), m.group(2)
        normalized = anchor.strip().lower()
        if normalized in _NATURAL_ANCHORS:
            return m.group(0)
        if len(anchor.split()) <= _MAX_ANCHOR_WORDS:
            return m.group(0)
        return f"[tại đây]({url})"

    return _MD_LINK_RE.sub(_maybe_shorten, answer)


def _wrap_raw_urls(answer: str) -> str:
    """Wrap standalone raw URLs into ``[tại đây](url)`` markdown links.

    Protects existing markdown links first so their inner URLs are not
    double-wrapped.
    """
    placeholders: list[str] = []

    def _save(m: re.Match) -> str:
        placeholders.append(m.group(0))
        return f"\x00LINK{len(placeholders) - 1}\x00"

    protected = _MD_LINK_RE.sub(_save, answer)
    def repl(m: re.Match) -> str:
        url = m.group(1)
        trailing = ""
        while url and url[-1] in ".,)]\"'?!":
            trailing = url[-1] + trailing
            url = url[:-1]
        return f"[tại đây]({url.replace(' ', '%20')}){trailing}"

    wrapped = _RAW_URL_RE.sub(repl, protected)
    for i, ph in enumerate(placeholders):
        wrapped = wrapped.replace(f"\x00LINK{i}\x00", ph)
    return wrapped


def _sanitize_answer_urls(answer: str) -> str:
    """Post-process LLM answer: fix broken links, shorten anchors, wrap raw URLs.

    Pipeline:
      1. URL-encode spaces inside markdown link URLs
      2. Shorten long anchor text → "tại đây"
      3. Wrap remaining raw URLs → ``[tại đây](url)``
    """
    answer = _fix_markdown_link_spaces(answer)
    answer = _shorten_long_anchors(answer)
    answer = _wrap_raw_urls(answer)
    return answer


# Backward-compatible alias used by tests / callers outside this module.
_strip_raw_urls = _sanitize_answer_urls


# ── Streaming URL sanitizer ────────────────────────────────────────────────────

def _raw_url_hold_index(buf: str) -> int:
    """Index from which ``buf``'s tail should be held as a (partial) raw URL.

    Returns ``len(buf)`` when nothing URL-like is pending.

    A URL scheme (``http``) can arrive split across streaming chunks
    (``"h"``, ``"tt"``, ``"p"``). ``str.rfind("http")`` only sees the whole
    token once it is fully buffered, so the early characters would otherwise
    flush out as plain text and the URL would leak unsanitized. This also
    matches a *trailing prefix* of ``http`` (``h`` / ``ht`` / ``htt``) so the
    sanitizer keeps buffering until it can tell whether a URL is forming.
    """
    pos = buf.rfind("http")
    if pos != -1:
        return pos
    # No complete "http" yet — hold the longest suffix that is still a prefix
    # of "http" (covers the scheme arriving one char at a time).
    for n in range(min(len(buf), 3), 0, -1):
        if "http".startswith(buf[-n:]):
            return len(buf) - n
    return len(buf)


class _StreamUrlSanitizer:
    """Buffer streaming chunks to sanitize markdown links and raw URLs inline.

    When a ``[`` is encountered the sanitizer starts buffering until the
    markdown link pattern ``[text](url)`` is complete (or clearly not a link),
    then emits the sanitized version.  Raw ``https?://`` tokens are similarly
    buffered until the URL boundary is found, then wrapped as
    ``[tại đây](url)``.
    """

    def __init__(self) -> None:
        self._buffer: str = ""

    def feed(self, chunk: str) -> str:
        """Feed a new chunk and return text safe to yield."""
        self._buffer += chunk
        return self._try_flush()

    def finalize(self) -> str:
        """Flush remaining buffer at end of stream (applies full sanitization)."""
        result = _sanitize_answer_urls(self._buffer)
        self._buffer = ""
        return result

    # ── internal ──────────────────────────────────────────────────────────

    def _try_flush(self) -> str:
        buf = self._buffer

        # If buffer contains an open bracket that might be a markdown link
        # start, keep buffering until the link is complete or clearly broken.
        open_bracket = buf.rfind("[")
        if open_bracket != -1:
            after_bracket = buf[open_bracket:]
            # Complete link found → sanitize everything up to & including it
            if _MD_LINK_RE.search(after_bracket):
                # There may be more text after the link — find the end
                match = _MD_LINK_RE.search(after_bracket)
                if match:
                    end_pos = open_bracket + match.end()
                    safe = buf[:end_pos]
                    self._buffer = buf[end_pos:]
                    return _sanitize_answer_urls(safe)
            # Incomplete link — still buffering (but cap at 500 chars to avoid
            # unbounded memory if the bracket is just a bracket).
            if len(after_bracket) < 500:
                # Flush everything before the bracket safely
                safe = buf[:open_bracket]
                self._buffer = buf[open_bracket:]
                if safe:
                    return _sanitize_answer_urls(safe)
                return ""

        # Check for a raw URL (or the start of one) still streaming in. The
        # scheme may be split across chunks, so ``_raw_url_hold_index`` also
        # matches a trailing prefix of "http" — otherwise the URL leaks out
        # char-by-char before ``rfind("http")`` ever sees the whole token.
        http_pos = _raw_url_hold_index(buf)
        if http_pos < len(buf):
            after_http = buf[http_pos:]
            # If URL looks incomplete (no whitespace/newline terminator yet),
            # keep buffering the URL portion.
            if " " not in after_http and "\n" not in after_http and len(after_http) < 500:
                safe = buf[:http_pos]
                self._buffer = buf[http_pos:]
                if safe:
                    return _sanitize_answer_urls(safe)
                return ""

        # No pending link or URL — flush everything.
        self._buffer = ""
        return _sanitize_answer_urls(buf)
