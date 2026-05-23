"""Shared schemas and helpers for two-layer RAG evaluation.

The evaluation system intentionally separates historical advisor-email
behaviour checks from current-production policy checks.  Historical cases are
conversation-quality regressions; current-policy cases are factual production
golden tests against the indexed RAG corpus.
"""

from __future__ import annotations

import json
import re
import statistics
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Literal, Optional

EvalSuite = Literal["historical_email", "current_policy"]

HISTORICAL_RUBRIC = [
    "conversation_understanding",
    "followup_resolution",
    "clarification_quality",
    "personalization",
    "advisory_logic",
    "tone",
]

CURRENT_POLICY_RUBRIC = [
    "faithfulness",
    "answer_correctness",
    "answer_relevancy",
    "citation_accuracy",
]


@dataclass
class EvalCase:
    eval_suite: EvalSuite
    case_id: str
    question: str
    context: str = ""
    ground_truth_answer: str = ""
    timestamp: Optional[str] = None
    expected_source_ids: List[str] = field(default_factory=list)
    expected_collections: List[str] = field(default_factory=list)
    valid_as_of: Optional[str] = None
    query_class: str = "general"
    difficulty: str = "medium"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EvalCaseResult:
    eval_suite: EvalSuite
    case_id: str
    question: str
    actual_answer: str = ""
    retrieved_source_ids: List[str] = field(default_factory=list)
    sources: List[Dict[str, Any]] = field(default_factory=list)
    timings_ms: Dict[str, float] = field(default_factory=dict)
    judge_scores: Dict[str, float] = field(default_factory=dict)
    metrics: Dict[str, float] = field(default_factory=dict)
    fail_reasons: List[str] = field(default_factory=list)
    passed: bool = True
    error: Optional[str] = None
    case: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EvalRun:
    run_id: str
    eval_suite: EvalSuite
    status: str
    started_at: str
    finished_at: str
    trigger: str = "manual"
    summary: Dict[str, Any] = field(default_factory=dict)
    artifacts: Dict[str, str] = field(default_factory=dict)
    config: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def raw_id(value: Any) -> str:
    text = str(value or "").strip()
    return text.split("/", 1)[-1] if "/" in text else text


def load_relevance_labels(path: Optional[Path]) -> Dict[str, Dict[str, int]]:
    """Load graded retrieval labels as {case_id: {raw_doc_id: relevance}}.

    The labels JSONL is append-friendly: if the same (case_id, doc_id) appears
    multiple times, the later row wins. This allows manual audit rows to
    override earlier LLM-judge rows without rewriting the whole file.
    """
    if path is None or not path.exists():
        return {}
    labels: Dict[str, Dict[str, int]] = {}
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            case_id = str(row.get("case_id") or "").strip()
            doc_id = raw_id(row.get("doc_id"))
            if not case_id or not doc_id:
                continue
            try:
                relevance = int(row.get("relevance", 0))
            except (TypeError, ValueError):
                relevance = 0
            labels.setdefault(case_id, {})[doc_id] = max(0, min(2, relevance))
    return labels


def load_json_or_jsonl(path: Path) -> List[Dict[str, Any]]:
    if path.suffix == ".jsonl":
        with open(path, encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    if isinstance(payload, dict):
        for key in ("cases", "test_cases", "rows", "data"):
            if isinstance(payload.get(key), list):
                return payload[key]
    return payload if isinstance(payload, list) else []


def load_historical_email_cases(path: Path, limit: int = 0) -> List[EvalCase]:
    rows = load_json_or_jsonl(path)
    cases: List[EvalCase] = []
    for index, item in enumerate(rows):
        if not isinstance(item, dict):
            continue
        question = str(item.get("question") or "").strip()
        if not question:
            continue
        metadata = dict(item.get("metadata") or {})
        cases.append(
            EvalCase(
                eval_suite="historical_email",
                case_id=str(item.get("id") or f"email_{index + 1}"),
                question=question,
                context=str(item.get("context") or ""),
                ground_truth_answer=str(item.get("ground_truth_answer") or ""),
                timestamp=metadata.get("timestamp"),
                query_class="email_followup" if item.get("context") else "email_initial",
                difficulty="hard" if item.get("context") else "medium",
                metadata={
                    "thread_id": item.get("thread_id"),
                    **metadata,
                },
            )
        )
        if limit and len(cases) >= limit:
            break
    return cases


def _listify(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.replace(";", ",").split(",") if part.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


CURRENT_POLICY_CATEGORIES = {"retrieval", "current_policy", "rag", "generation"}


def _bool_or_default(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "y"}:
            return True
        if lowered in {"false", "0", "no", "n"}:
            return False
    return default


def _collection_prefixed_id(value: Any, collection: Any = None) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if "/" in text or not collection:
        return text
    return f"{collection}/{text}"


def normalize_current_policy_item(
    item: Dict[str, Any],
    index: int = 0,
) -> Optional[Dict[str, Any]]:
    """Normalize legacy and schema-v1 rows into current-policy eval shape.

    Schema v1 is JSONL-first and uses ``question``, ``ground_truth`` and
    ``ground_truth_contexts``. Existing runners still consume ``query``,
    ``ground_truth_answer`` and ``expected_source_ids``. This helper bridges the
    two forms while preserving the original row fields for traceability.
    """
    if not isinstance(item, dict):
        return None

    category = str(item.get("category") or item.get("eval_suite") or "").strip()
    if category and category not in CURRENT_POLICY_CATEGORIES:
        return None

    question = str(
        item.get("query")
        or item.get("question")
        or item.get("instruction")
        or ""
    ).strip()
    if not question:
        return None

    expected_collection = (
        item.get("expected_collection")
        or item.get("source")
        or item.get("collection")
    )
    expected_collections = _listify(item.get("expected_collections"))
    if expected_collection and str(expected_collection) not in expected_collections:
        expected_collections.append(str(expected_collection))

    raw_context_ids = (
        item.get("expected_source_ids")
        or item.get("relevant_doc_ids")
        or item.get("ground_truth_contexts")
        or item.get("context_ids")
    )
    expected_source_ids = [
        _collection_prefixed_id(value, expected_collection)
        for value in _listify(raw_context_ids)
    ]
    expected_source_ids = [value for value in expected_source_ids if value]

    ground_truth_answer = str(
        item.get("ground_truth_answer")
        or item.get("expected_answer")
        or item.get("answer")
        or item.get("ground_truth")
        or item.get("reference_answer")
        or item.get("output")
        or ""
    )
    qtype = str(item.get("question_type") or "").strip()
    expected_behavior = str(item.get("expected_behavior") or "").strip()
    if not expected_behavior:
        expected_behavior = (
            "refuse_insufficient_context"
            if qtype == "adversarial"
            else "answer_with_citation"
        )
    answerable = _bool_or_default(
        item.get("answerable"),
        default=expected_behavior != "refuse_insufficient_context" and qtype != "adversarial",
    )

    normalized = dict(item)
    normalized["id"] = str(item.get("id") or f"current_{index + 1}")
    normalized["category"] = category or "retrieval"
    normalized["query"] = question
    normalized["question"] = question
    normalized["ground_truth"] = str(item.get("ground_truth") or ground_truth_answer)
    normalized["ground_truth_answer"] = ground_truth_answer
    normalized["reference_answer"] = str(item.get("reference_answer") or ground_truth_answer)
    normalized["expected_source_ids"] = expected_source_ids
    normalized["ground_truth_contexts"] = expected_source_ids
    normalized["expected_collection"] = str(expected_collection or "")
    normalized["expected_collections"] = expected_collections
    normalized["source"] = str(item.get("source") or expected_collection or "")
    normalized["answerable"] = answerable
    normalized["expected_behavior"] = expected_behavior
    normalized["difficulty"] = str(item.get("difficulty") or "medium")
    normalized["query_class"] = str(item.get("query_class") or qtype or normalized["category"])
    normalized["valid_as_of"] = item.get("valid_as_of") or item.get("effective_date")
    if item.get("input") and not item.get("legacy_input"):
        normalized["legacy_input"] = item.get("input")
    return normalized


def load_current_policy_cases(path: Path, limit: int = 0) -> List[EvalCase]:
    rows = load_json_or_jsonl(path)
    cases: List[EvalCase] = []
    for index, item in enumerate(rows):
        normalized = normalize_current_policy_item(item, index=index)
        if not normalized:
            continue
        cases.append(
            EvalCase(
                eval_suite="current_policy",
                case_id=str(normalized["id"]),
                question=str(normalized["question"]),
                ground_truth_answer=str(normalized.get("ground_truth_answer") or ""),
                expected_source_ids=[
                    raw_id(x) for x in _listify(normalized.get("expected_source_ids"))
                ],
                expected_collections=_listify(normalized.get("expected_collections")),
                valid_as_of=normalized.get("valid_as_of"),
                query_class=str(normalized.get("query_class") or "retrieval"),
                difficulty=str(normalized.get("difficulty") or "medium"),
                metadata=normalized,
            )
        )
        if limit and len(cases) >= limit:
            break
    return cases


def strip_json_fence(raw: str) -> str:
    text = (raw or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
        if text.startswith("json"):
            text = text[4:].strip()
    return text


def parse_judge_scores(
    raw: str,
    rubric_keys: Iterable[str],
    *,
    default_score: float = 0.0,
) -> tuple[Dict[str, float], List[str]]:
    """Parse LLM judge JSON while tolerating fences and malformed output."""
    keys = list(rubric_keys)
    scores = {key: default_score for key in keys}
    fail_reasons: List[str] = []
    try:
        payload = json.loads(strip_json_fence(raw))
    except Exception:
        fail_reasons.append("judge_parse_error")
        return scores, fail_reasons

    raw_scores = payload.get("scores", payload)
    if isinstance(raw_scores, dict):
        for key in keys:
            try:
                value = float(raw_scores.get(key, default_score))
            except (TypeError, ValueError):
                value = default_score
            scores[key] = max(0.0, min(1.0, value))

    reasons = payload.get("fail_reasons") or payload.get("reasons") or payload.get("reason")
    if isinstance(reasons, list):
        fail_reasons.extend(str(item) for item in reasons if str(item).strip())
    elif isinstance(reasons, str) and reasons.strip():
        fail_reasons.append(reasons.strip())
    return scores, fail_reasons


def load_superseded_sources(lineage_path: Path) -> tuple[set[str], List[str]]:
    if not lineage_path.exists():
        return set(), []
    try:
        payload = json.loads(lineage_path.read_text(encoding="utf-8"))
    except Exception:
        return set(), []
    docs = payload.get("documents", []) if isinstance(payload, dict) else []
    ids: set[str] = set()
    patterns: List[str] = []
    for doc in docs:
        if not isinstance(doc, dict) or doc.get("status") != "superseded":
            continue
        for key in ("doc_id", "document_id", "id"):
            if doc.get(key):
                ids.add(str(doc[key]).lower())
        source = str(doc.get("source_file") or doc.get("source") or "").strip()
        if source:
            patterns.append(Path(source).stem.lower())
    return ids, patterns


def source_is_superseded(source: Dict[str, Any], ids: set[str], patterns: List[str]) -> bool:
    metadata = source.get("metadata") if isinstance(source.get("metadata"), dict) else {}
    haystack_values = [
        source.get("id"),
        source.get("collection"),
        source.get("content"),
        source.get("text"),
        metadata.get("document_id"),
        metadata.get("doc_id"),
        metadata.get("source"),
        metadata.get("filename"),
        metadata.get("source_file"),
        metadata.get("doc_title"),
    ]
    haystack = " ".join(str(v or "") for v in haystack_values).lower()
    if any(sid and sid in haystack for sid in ids):
        return True
    return any(pattern and pattern in haystack for pattern in patterns)


def freshness_pass_for_sources(sources: List[Dict[str, Any]], lineage_path: Path) -> bool:
    ids, patterns = load_superseded_sources(lineage_path)
    if not ids and not patterns:
        return True
    return not any(source_is_superseded(source, ids, patterns) for source in sources)


def percentile(values: Iterable[float], pct: float) -> float:
    clean = sorted(float(v) for v in values if v is not None)
    if not clean:
        return 0.0
    index = int(round((pct / 100.0) * (len(clean) - 1)))
    return clean[max(0, min(index, len(clean) - 1))]


def mean_score(values: Iterable[float]) -> float:
    clean = [float(v) for v in values if v is not None]
    return round(statistics.mean(clean), 4) if clean else 0.0


def status_from_metrics(summary: Dict[str, Any], failures: List[str] | None = None) -> str:
    if failures:
        return "failed"
    hard_failed = int(summary.get("failed_cases", 0) or 0)
    total = int(summary.get("total_cases", 0) or 0)
    if total == 0:
        return "failed"
    fail_rate = hard_failed / total if total else 1.0
    if fail_rate > 0.2:
        return "warning"
    for key in ("citation_accuracy", "freshness_pass_rate"):
        if key in summary and float(summary[key] or 0) < 0.8:
            return "warning"
    return "passed"
