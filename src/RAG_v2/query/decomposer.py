"""Query Decomposer — splits multi-domain questions into targeted sub-queries.

When a user question clearly spans multiple document collections
(e.g. "JP2111 tương đương với học phần nào?" + "điều kiện xét đồ án là gì?"),
this module decomposes it into per-collection sub-queries so the RAG pipeline
can retrieve from each collection with a focused query, improving recall and
preventing hallucination from the agent path.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, cast

from openai import InternalServerError, OpenAI, RateLimitError

logger = logging.getLogger(__name__)

# ─── Constants ──────────────────────────────────────────────────────────────────
_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
DEFAULT_MODEL = "gemini-3.1-flash-lite"
VALID_COLLECTIONS = {"ctdt", "quydinh", "kehoach", "stsv"}

_MAX_RETRIES = 2
_BASE_RETRY_DELAY = 1.0  # seconds

# ─── Prompts ────────────────────────────────────────────────────────────────────

_DECOMPOSE_SYSTEM_PROMPT = """\
Bạn là bộ phân tích câu hỏi học thuật cho chatbot Đại học Bách khoa Hà Nội.

Nhiệm vụ: Phân tích câu hỏi thành các câu hỏi con đơn giản, mỗi câu hỏi con
chỉ cần tra cứu trong MỘT nguồn tài liệu.

Nguồn tài liệu:
- ctdt: Chương trình đào tạo, học phần, tín chỉ, học phần tương đương, đồ án tốt nghiệp
- quydinh: Quy định, điều kiện, chính sách, học bổng, quy chế đào tạo
- kehoach: Lịch, thời hạn đăng ký, lịch thi, thông báo, sự kiện
- stsv: Thủ tục sinh viên, ký túc xá, bảo hiểm, thẻ sinh viên

QUY TẮC:
1. BỎ QUA hoàn toàn: tên người, mã sinh viên (MSSV), lời chào, lời cảm ơn.
2. Chỉ phân tách khi câu hỏi RÕ RÀNG có ≥2 phần cần tra cứu ở nguồn khác nhau.
   Nếu câu hỏi chỉ cần một nguồn → trả về list 1 phần tử với câu hỏi NGUYÊN VĂN.
3. Tối đa 3 câu hỏi con.
4. Mỗi câu hỏi con phải ngắn gọn, cụ thể, tự thân (standalone).
5. Giữ nguyên mã học phần (JP2111, IT4062E...) và mã ngành (IT-E6...) nếu có.
   KHÔNG thêm tên học phần hoặc tên ngành bên cạnh mã nếu không có trong câu hỏi gốc.
6. Câu hỏi con phải BÁM SÁT NGỮ NGHĨA GỐC — không thêm từ khóa, tên môn học,
   điều kiện hoặc ngữ cảnh không xuất hiện trong câu hỏi ban đầu.
7. Nếu câu hỏi chỉ cần một nguồn, field "query" phải là câu hỏi NGUYÊN VĂN gốc.

OUTPUT: JSON thuần, không markdown:
{"subqueries": [{"query": "<câu hỏi con>", "collection": "<ctdt|quydinh|kehoach|stsv>"}]}"""

_DECOMPOSE_FEW_SHOT: List[Dict[str, str]] = [
    {
        "role": "user",
        "content": (
            "Kỳ 2022.2 em trượt JP2111 thì kỳ 2024.1 có thể đăng ký học phần nào "
            "thay thế và điều kiện xét nhận đồ án tốt nghiệp kỳ sau là gì?"
        ),
    },
    {
        "role": "assistant",
        "content": json.dumps(
            {
                "subqueries": [
                    {
                        "query": "Học phần JP2111 có thể chuyển đổi tương đương với học phần nào?",
                        "collection": "ctdt",
                    },
                    {
                        "query": "Điều kiện để được xét nhận đồ án tốt nghiệp là gì?",
                        "collection": "quydinh",
                    },
                ]
            },
            ensure_ascii=False,
        ),
    },
    {
        "role": "user",
        "content": "Điều kiện xét học bổng khuyến khích học tập và nộp hồ sơ ở đâu?",
    },
    {
        "role": "assistant",
        "content": json.dumps(
            {
                "subqueries": [
                    {
                        "query": "Điều kiện xét học bổng khuyến khích học tập là gì?",
                        "collection": "quydinh",
                    },
                    {
                        "query": "Thủ tục và nơi nộp hồ sơ học bổng khuyến khích học tập?",
                        "collection": "stsv",
                    },
                ]
            },
            ensure_ascii=False,
        ),
    },
    {
        "role": "user",
        "content": "Môn IT4062E kỳ này còn slot không?",
    },
    {
        "role": "assistant",
        "content": json.dumps(
            {
                "subqueries": [
                    {
                        "query": "Lịch đăng ký và slot còn lại của môn IT4062E kỳ này?",
                        "collection": "kehoach",
                    }
                ]
            },
            ensure_ascii=False,
        ),
    },
    {
        "role": "user",
        "content": "Môn IT3080 trong chương trình IT-E6 có bao nhiêu tín chỉ?",
    },
    {
        "role": "assistant",
        "content": json.dumps(
            {
                "subqueries": [
                    {
                        "query": "Môn IT3080 trong chương trình IT-E6 có bao nhiêu tín chỉ?",
                        "collection": "ctdt",
                    }
                ]
            },
            ensure_ascii=False,
        ),
    },
]


class QueryDecomposer:
    """Splits multi-domain questions into domain-specific sub-queries.

    Makes a single fast LLM call (gemini-flash-lite) to detect whether a
    question needs multiple collections and produce per-collection sub-queries.

    Returns ``[{"query": str, "collection": str}, ...]``.
    When decomposition fails or the question is single-domain, falls back to a
    single-item list with the original query.
    """

    def __init__(
        self,
        settings: Optional[Any] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        if settings is None:
            from config.settings import Settings  # noqa: PLC0415

            settings = Settings()

        self.model = model or getattr(
            settings, "reflection_model", DEFAULT_MODEL
        )
        provider = getattr(settings, "reflection_provider", "gemini")

        if provider == "gemini":
            base_url = _GEMINI_BASE_URL
            resolved_key = (
                api_key
                or getattr(settings, "google_api_key", "")
                or os.getenv("GOOGLE_API_KEY", "")
            )
        elif provider == "lm_studio":
            base_url = getattr(
                settings, "lm_studio_base_url", "http://localhost:1234/v1"
            )
            resolved_key = api_key or "lm-studio"
        elif provider == "ollama":
            _base = getattr(
                settings, "ollama_base_url", "http://localhost:11434"
            )
            base_url = _base if _base.endswith("/v1") else f"{_base}/v1"
            resolved_key = api_key or "ollama"
        elif provider == "openai":
            base_url = "https://api.openai.com/v1"
            resolved_key = (
                api_key
                or getattr(settings, "openai_api_key", "")
                or os.getenv("OPENAI_API_KEY", "")
            )
        else:
            base_url = _GEMINI_BASE_URL
            resolved_key = (
                api_key
                or getattr(settings, "google_api_key", "")
                or os.getenv("GOOGLE_API_KEY", "")
            )

        self._client = OpenAI(api_key=resolved_key, base_url=base_url)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def decompose(self, query: str) -> List[Dict[str, str]]:
        """Decompose *query* into sub-queries with target collections.

        Returns:
            List of ``{"query": str, "collection": str}`` dicts.
            When the question is single-domain or decomposition fails, returns
            ``[{"query": query, "collection": ""}]`` so callers can treat it
            uniformly.
        """
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": _DECOMPOSE_SYSTEM_PROMPT},
            *_DECOMPOSE_FEW_SHOT,
            {"role": "user", "content": query},
        ]

        last_exc: Optional[Exception] = None
        for attempt in range(_MAX_RETRIES):
            try:
                response = self._client.chat.completions.create(
                    model=self.model,
                    messages=cast(Any, messages),
                    temperature=0.0,
                    max_tokens=512,
                )
                break
            except (RateLimitError, InternalServerError) as exc:
                if (
                    isinstance(exc, InternalServerError)
                    and exc.status_code != 503
                ):
                    raise
                last_exc = exc
                if attempt < _MAX_RETRIES - 1:
                    delay = _BASE_RETRY_DELAY * (2**attempt)
                    logger.warning(
                        "Decomposer transient error (attempt %d/%d), retrying in %.1fs: %s",
                        attempt + 1,
                        _MAX_RETRIES,
                        delay,
                        exc,
                    )
                    time.sleep(delay)
        else:
            logger.warning("Decomposer failed after retries: %s", last_exc)
            return [{"query": query, "collection": ""}]

        raw = (response.choices[0].message.content or "").strip()
        return self._parse_response(raw, fallback_query=query)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _parse_response(
        self, raw: str, *, fallback_query: str
    ) -> List[Dict[str, str]]:
        """Parse the LLM JSON response, validating collection names."""
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            logger.warning("Decomposer returned non-JSON: %r", raw[:200])
            return [{"query": fallback_query, "collection": ""}]

        subqueries = data.get("subqueries", [])
        if not isinstance(subqueries, list) or not subqueries:
            return [{"query": fallback_query, "collection": ""}]

        valid: List[Dict[str, str]] = []
        for item in subqueries:
            q = str(item.get("query", "")).strip()
            c = str(item.get("collection", "")).strip().lower()
            if q and c in VALID_COLLECTIONS:
                valid.append({"query": q, "collection": c})

        if not valid:
            logger.warning(
                "Decomposer produced no valid subqueries from: %r", raw[:200]
            )
            return [{"query": fallback_query, "collection": ""}]

        # Single-source: always return the original query to prevent semantic
        # drift from LLM paraphrasing.  The collection hint is preserved so
        # the caller can use it for targeted retrieval if desired.
        if len(valid) == 1:
            valid[0]["query"] = fallback_query

        logger.info(
            "Decomposed into %d sub-queries: %s",
            len(valid),
            [(item["collection"], item["query"][:50]) for item in valid],
        )
        return valid
