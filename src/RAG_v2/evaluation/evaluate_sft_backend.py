"""Evaluate local SFT questions through the running RAG backend.

This runner intentionally keeps runtime settings in the CONFIG dictionary below
instead of accepting CLI arguments. It is designed for long SFT runs where the
backend or LLM provider may disconnect: each completed/failed sample is appended
to one run-level JSONL file, progress is written atomically, and explicit
``resume_dir`` can continue an interrupted run.
"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import math
import os
import re
import statistics
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from dotenv import dotenv_values, load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
_SHELL_VITE_API_URL = os.environ.get("VITE_API_URL")
load_dotenv(PROJECT_ROOT / ".env")
_FRONTEND_ENV_PATH = PROJECT_ROOT / "frontend" / "chat-companion" / ".env"
load_dotenv(_FRONTEND_ENV_PATH)
if _SHELL_VITE_API_URL is None and _FRONTEND_ENV_PATH.exists():
    _frontend_vite_api_url = dotenv_values(_FRONTEND_ENV_PATH).get("VITE_API_URL")
    if _frontend_vite_api_url:
        os.environ["VITE_API_URL"] = str(_frontend_vite_api_url)

logger = logging.getLogger(__name__)


def _frontend_default_backend_url() -> str:
    """Match the web client default: VITE_API_URL or localhost, then /chat/v3."""
    api_base_url = (os.getenv("VITE_API_URL") or "http://localhost:8000").rstrip("/")
    return f"{api_base_url}/chat/v3"


CONFIG: Dict[str, Any] = {
    "dataset_path": "eval/data/sft_dataset (1).jsonl",
    "backend_url": _frontend_default_backend_url(),
    "output_dir": "evaluation/results/sft_backend_eval",
    "run_dir": None,  # None = use output_dir directly; set a path to isolate a run
    "timestamped_run_dir": True,  # fresh live-backend run: output_dir/YYYYMMDD_HHMMSS
    "merge_child_run_dirs": False,  # do not reuse stale child-run records by default
    "resume_dir": None,
    "batch_size": 1,  # number of questions grouped into one runner batch
    "batch_index": 0,  # 0 = all batches; 1..N = only that batch after start/limit selection
    "batch_concurrency": 1,  # independent /chat/v3 HTTP requests in flight per batch
    "limit": 0,
    "start_index": 0,
    "top_k": 5,
    "mode": "auto",
    "timeout_s": 240,  # frontend axios timeout is 240000 ms
    "delay_s": 0.5,  # pause between batches, not between samples
    # "anonymous" mirrors a new unauthenticated frontend session. "frontend_env"
    # keeps the previous evaluator behavior of reading auth/session/profile env.
    "identity_mode": "anonymous",
    # Frontend-compatible identity/request fields for identity_mode=frontend_env.
    # None means "omit from JSON", matching JSON.stringify({field: undefined}).
    "history": [],
    "session_id": None,
    "user_context": None,
    "user_id": None,
    "session_id_env": "EVAL_SESSION_ID",
    "user_context_env": "EVAL_USER_CONTEXT_JSON",
    "user_id_env": "EVAL_USER_ID",
    "send_null_optional_fields": False,
    "record_request_payload": True,
    "record_response_trace": True,
    "auth_token": "",
    "auth_token_env": "EVAL_AUTH_TOKEN",
    "judge_backend": "gemini",  # "none" | "lmstudio" | "gemini"
    "retry_failed": False,
    "lmstudio_base_url": "http://localhost:1234/v1",
    "lmstudio_model": "qwen/qwen3-8b:2",
    "gemini_model": "gemini-3.1-flash-lite-preview",
}


_REF_COMPARE_SYSTEM = """\
You are a strict evaluator comparing two Vietnamese-language answers to the same question.

Return a single JSON object with exactly:
{"match":"correct|partial|incorrect","reason":"one sentence"}

Definitions:
- correct: generated answer conveys all key facts from the reference and adds no incorrect information.
- partial: generated answer captures some but not all key facts, or adds minor inaccuracies.
- incorrect: generated answer is missing most key facts or contains significant inaccuracies.

Respond with JSON only."""

_REF_COMPARE_USER = """\
Question:
{question}

Reference answer:
{reference}

Generated answer:
{generated}

Compare the two answers."""


_STOPWORDS = {
    "anh", "bao", "bạn", "bằng", "các", "cần", "cho", "của", "được", "học",
    "hỏi", "không", "là", "mình", "một", "nào", "này", "như", "sinh",
    "theo", "thì", "thông", "tin", "trong", "và", "với",
}


@dataclass
class SFTSample:
    index: int
    sample_id: str
    instruction: str
    input: str
    reference_answer: str
    doc_type: str
    metadata: Dict[str, str] = field(default_factory=dict)


def _resolve_project_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _sample_id(index: int, instruction: str, output: str, doc_type: str) -> str:
    raw = f"{index}\n{instruction}\n{output}\n{doc_type}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    return str(value)


def _config_bool(config: Dict[str, Any], key: str, default: bool = False) -> bool:
    value = config.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _identity_mode(config: Dict[str, Any]) -> str:
    mode = str(config.get("identity_mode") or "anonymous").strip().lower()
    if mode not in {"anonymous", "frontend_env"}:
        raise ValueError(f"Unsupported identity_mode={mode!r}")
    return mode


def _clean_optional_text(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _sanitize_user_context(raw_context: Any) -> Optional[Dict[str, str]]:
    """Mirror frontend sanitizeUserContext before sending /chat/v3 payloads."""
    if not isinstance(raw_context, dict):
        return None

    cleaned: Dict[str, str] = {}
    for key in ("student_id", "cohort", "major", "major_code", "full_name"):
        value = _clean_optional_text(raw_context.get(key))
        if value:
            cleaned[key] = value
    return cleaned or None


def _json_from_env(env_name: str | None) -> Any:
    name = _clean_optional_text(env_name)
    if not name:
        return None
    raw = _clean_optional_text(os.getenv(name))
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Ignoring invalid JSON in %s", name)
        return None


def _text_from_config_or_env(
    config: Dict[str, Any],
    key: str,
    env_key: str,
) -> Optional[str]:
    configured = _clean_optional_text(config.get(key))
    if configured:
        return configured
    env_name = _clean_optional_text(config.get(env_key))
    return _clean_optional_text(os.getenv(env_name)) if env_name else None


def _user_context_from_config_or_env(
    config: Dict[str, Any],
) -> Optional[Dict[str, str]]:
    configured = _sanitize_user_context(config.get("user_context"))
    if configured:
        return configured
    return _sanitize_user_context(_json_from_env(config.get("user_context_env")))


def _normalise_history(raw_history: Any) -> List[Dict[str, str]]:
    if not isinstance(raw_history, list):
        return []

    history: List[Dict[str, str]] = []
    for item in raw_history:
        if not isinstance(item, dict):
            continue
        role = _clean_optional_text(item.get("role"))
        content = _clean_optional_text(item.get("content"))
        if role in {"user", "assistant"} and content:
            history.append({"role": role, "content": content})
    return history


def _frontend_chat_headers(config: Dict[str, Any]) -> Dict[str, str]:
    """Mirror frontend chatApi authHeaders() for evaluator HTTP requests."""
    headers = {"Content-Type": "application/json"}
    if _identity_mode(config) == "anonymous":
        return headers

    token = _clean_optional_text(config.get("auth_token"))
    if not token:
        token_env = _clean_optional_text(config.get("auth_token_env")) or "EVAL_AUTH_TOKEN"
        token = _clean_optional_text(os.getenv(token_env))
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _build_frontend_chat_payload(
    *,
    question: str,
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """Build the same JSON shape as frontend sendMessageV3()."""
    identity_mode = _identity_mode(config)
    payload: Dict[str, Any] = {
        "question": question,
        "mode": "auto" if identity_mode == "anonymous" else str(config.get("mode") or "auto"),
        "top_k": 5 if identity_mode == "anonymous" else int(config.get("top_k") or 5),
        "history": [] if identity_mode == "anonymous" else _normalise_history(config.get("history")),
    }

    if identity_mode == "anonymous":
        return payload

    optional_fields: Dict[str, Any] = {
        "session_id": _text_from_config_or_env(
            config,
            "session_id",
            "session_id_env",
        ),
        "user_context": _user_context_from_config_or_env(config),
        "user_id": _text_from_config_or_env(config, "user_id", "user_id_env"),
    }
    include_nulls = _config_bool(config, "send_null_optional_fields", False)
    for key, value in optional_fields.items():
        if value is not None:
            payload[key] = value
        elif include_nulls:
            payload[key] = None

    return payload


def _request_payload_hash(payload: Dict[str, Any]) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _optional_fields_sent(payload: Dict[str, Any]) -> List[str]:
    return [
        key
        for key in ("session_id", "user_context", "user_id")
        if key in payload
    ]


def _request_record_metadata(
    *,
    config: Dict[str, Any],
    backend_url: str,
    request_payload: Dict[str, Any],
    request_headers: Dict[str, str],
) -> Dict[str, Any]:
    return {
        "identity_mode": _identity_mode(config),
        "auth_header_sent": "Authorization" in request_headers,
        "optional_fields_sent": _optional_fields_sent(request_payload),
        "request_payload_hash": _request_payload_hash(request_payload),
        "backend_url": backend_url,
    }


def _atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )
    tmp.replace(path)


def _parse_legacy_input(input_text: str) -> Dict[str, str]:
    text = input_text or ""

    def field(label: str) -> str:
        match = re.search(rf"^{re.escape(label)}:\s*(.+)$", text, re.MULTILINE)
        return match.group(1).strip() if match else ""

    context_block = ""
    context_match = re.search(r"CONTEXT:\s*---\s*(.*?)\s*---\s*$", text, re.DOTALL)
    if context_match:
        context_block = context_match.group(1).strip()

    content = context_block
    content_match = re.search(r"Nội dung:\s*(.*)$", context_block, re.DOTALL)
    if content_match:
        content = content_match.group(1).strip()

    return {
        "document_title": field("Văn bản"),
        "chapter": field("Chương"),
        "article": field("Điều"),
        "clause": field("Khoản"),
        "effective_date": field("Ngày hiệu lực"),
        "ground_truth_context_text": content,
    }


def load_sft_dataset(dataset_path: str | Path) -> List[SFTSample]:
    path = _resolve_project_path(dataset_path)
    samples: List[SFTSample] = []
    with path.open(encoding="utf-8") as handle:
        for line_index, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            instruction = str(row.get("instruction") or "").strip()
            reference = str(row.get("output") or "").strip()
            doc_type = str(row.get("doc_type") or "").strip()
            legacy_input = str(row.get("input") or "")
            if not instruction:
                continue
            samples.append(
                SFTSample(
                    index=line_index,
                    sample_id=_sample_id(line_index, instruction, reference, doc_type),
                    instruction=instruction,
                    input=legacy_input,
                    reference_answer=reference,
                    doc_type=doc_type,
                    metadata=_parse_legacy_input(legacy_input),
                )
            )
    return samples


def _tokens(text: str) -> List[str]:
    raw = re.findall(r"[\wÀ-ỹ-]+", (text or "").lower(), flags=re.UNICODE)
    return [tok for tok in raw if len(tok) >= 4 and tok not in _STOPWORDS]


def _keyword_coverage(reference: str, generated: str) -> float:
    expected = sorted(set(_tokens(reference)))
    if not expected:
        return 0.0
    haystack = set(_tokens(generated))
    return round(len([tok for tok in expected if tok in haystack]) / len(expected), 4)


def _extract_atomic_facts(text: str) -> List[str]:
    normalized = " ".join((text or "").split())
    facts: List[str] = []
    facts.extend(re.findall(r"https?://\S+", normalized))
    facts.extend(
        re.findall(
            r"\b\d+(?:[.,]\d+)?\s*(?:năm|học kỳ|tín chỉ|TC|giờ|ngày|tháng|%)\b",
            normalized,
            flags=re.IGNORECASE,
        )
    )
    facts.extend(re.findall(r"\b[A-ZĐ]{2,}[A-ZĐ0-9-]*\b", normalized))

    out: List[str] = []
    for fact in facts:
        if fact and fact not in out:
            out.append(fact)
    return out[:8]


def _contains_text(haystack: str, needle: str) -> bool:
    if not needle:
        return False
    return " ".join(needle.lower().split()) in " ".join(haystack.lower().split())


def _atomic_fact_coverage(reference: str, generated: str) -> float:
    facts = _extract_atomic_facts(reference)
    if not facts:
        return 0.0
    hits = sum(1 for fact in facts if _contains_text(generated, fact))
    return round(hits / len(facts), 4)


def _as_source_list(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw_sources = (
        response.get("retrieved_documents")
        or response.get("sources")
        or response.get("documents")
        or []
    )
    return [item for item in raw_sources if isinstance(item, dict)]


def _source_text(source: Dict[str, Any]) -> str:
    metadata = source.get("metadata") if isinstance(source.get("metadata"), dict) else {}
    text = str(source.get("content") or source.get("text") or "")
    return "\n".join(
        [
            text,
            json.dumps(metadata, ensure_ascii=False, default=_json_default),
            str(source.get("collection") or ""),
        ]
    )


def _source_id(source: Dict[str, Any]) -> str:
    metadata = source.get("metadata") if isinstance(source.get("metadata"), dict) else {}
    return str(
        source.get("id")
        or metadata.get("chunk_id")
        or metadata.get("doc_id")
        or metadata.get("document_id")
        or ""
    )


def _source_title(source: Dict[str, Any]) -> str:
    metadata = source.get("metadata") if isinstance(source.get("metadata"), dict) else {}
    return str(
        metadata.get("document_title")
        or metadata.get("doc_title")
        or metadata.get("title")
        or metadata.get("source")
        or ""
    )


def calculate_metrics(
    sample: SFTSample,
    generated_answer: str,
    sources: List[Dict[str, Any]],
) -> Dict[str, Any]:
    source_haystack = "\n".join(_source_text(source) for source in sources)
    metadata = sample.metadata
    article = metadata.get("article", "")
    clause = metadata.get("clause", "")
    document_title = metadata.get("document_title") or sample.doc_type

    citation_parts = [part for part in (sample.doc_type, article, f"Khoản {clause}" if clause else "") if part]
    citation_text_hit = all(_contains_text(generated_answer, part) for part in citation_parts)

    return {
        "answer_nonempty": bool(generated_answer.strip()),
        "num_sources": len(sources),
        "reference_keyword_coverage": _keyword_coverage(
            sample.reference_answer,
            generated_answer,
        ),
        "atomic_fact_coverage": _atomic_fact_coverage(
            sample.reference_answer,
            generated_answer,
        ),
        "citation_text_hit": citation_text_hit if citation_parts else None,
        "expected_doc_hit": _contains_text(source_haystack, document_title),
        "expected_article_hit": _contains_text(source_haystack, article) if article else None,
        "expected_clause_hit": _contains_text(source_haystack, clause) if clause else None,
    }


def _post_backend(
    *,
    backend_url: str,
    question: str,
    config: Dict[str, Any],
    timeout_s: float,
) -> tuple[Dict[str, Any], Dict[str, Any], Dict[str, str]]:
    payload = _build_frontend_chat_payload(question=question, config=config)
    headers = _frontend_chat_headers(config)
    request = urllib.request.Request(
        backend_url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            body = response.read().decode("utf-8")
            return json.loads(body), payload, headers
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc


def _parse_json_response(raw: str, fallback_match: str = "incorrect") -> Dict[str, str]:
    cleaned = (raw or "").strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()
    try:
        payload = json.loads(cleaned)
        return {
            "match": str(payload.get("match") or fallback_match),
            "reason": str(payload.get("reason") or ""),
        }
    except Exception:
        return {"match": fallback_match, "reason": f"Parse error: {raw[:120]}"}


def _compare_with_reference(
    *,
    judge_backend: str,
    question: str,
    reference: str,
    generated: str,
    config: Dict[str, Any],
) -> Dict[str, str]:
    if judge_backend == "none":
        return {"match": "", "reason": ""}

    from openai import OpenAI

    if judge_backend == "lmstudio":
        client = OpenAI(
            api_key="lm-studio",
            base_url=str(config.get("lmstudio_base_url")),
        )
        model = str(config.get("lmstudio_model"))
    elif judge_backend == "gemini":
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GOOGLE_API_KEY or GEMINI_API_KEY is required")
        client = OpenAI(
            api_key=api_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        )
        model = str(config.get("gemini_model"))
    else:
        raise ValueError(f"Unsupported judge_backend={judge_backend!r}")

    user_msg = _REF_COMPARE_USER.format(
        question=question,
        reference=reference,
        generated=generated,
    )
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _REF_COMPARE_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.0,
        max_tokens=256,
    )
    raw = response.choices[0].message.content or ""
    return _parse_json_response(raw)


def _batch_files(run_dir: Path) -> List[Path]:
    # Backward compatibility for runs created before results.jsonl became the
    # live append file.
    return sorted((run_dir / "batches").glob("batch_*.jsonl"))


def _looks_like_legacy_run_dir(path: Path) -> bool:
    return (
        path.is_dir()
        and (
            (path / "results.jsonl").exists()
            or (path / "batches").is_dir()
            or (path / "progress.json").exists()
        )
    )


def _child_run_dirs(run_dir: Path) -> List[Path]:
    if not run_dir.exists():
        return []
    return sorted(
        child
        for child in run_dir.iterdir()
        if _looks_like_legacy_run_dir(child)
    )


def _read_record_file(path: Path, records: Dict[str, Dict[str, Any]]) -> None:
    if not path.exists():
        return
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                logger.warning("Skipping malformed JSONL row %s:%d: %s", path, line_no, exc)
                continue
            sample_id = str(record.get("sample_id") or "")
            if sample_id:
                records[sample_id] = record


def _load_records_from_single_run_dir(
    run_dir: Path,
    records: Dict[str, Dict[str, Any]],
) -> None:
    for batch_file in _batch_files(run_dir):
        _read_record_file(batch_file, records)
    _read_record_file(run_dir / "results.jsonl", records)


def load_existing_records(
    run_dir: Path,
    *,
    include_child_run_dirs: bool = False,
) -> Dict[str, Dict[str, Any]]:
    records: Dict[str, Dict[str, Any]] = {}
    if include_child_run_dirs:
        for child_run_dir in _child_run_dirs(run_dir):
            _load_records_from_single_run_dir(child_run_dir, records)
    _load_records_from_single_run_dir(run_dir, records)
    return records


def should_skip_sample(
    sample: SFTSample,
    existing_records: Dict[str, Dict[str, Any]],
    *,
    retry_failed: bool,
) -> bool:
    existing = existing_records.get(sample.sample_id)
    if not existing:
        return False
    if existing.get("status") == "completed":
        return True
    if existing.get("status") == "failed":
        return not retry_failed
    return False


def _select_samples(samples: List[SFTSample], config: Dict[str, Any]) -> List[SFTSample]:
    start_index = max(0, int(config.get("start_index") or 0))
    limit = int(config.get("limit") or 0)
    selected = samples[start_index:]
    return selected[:limit] if limit > 0 else selected


def _chunk_samples(samples: List[SFTSample], batch_size: int) -> List[List[SFTSample]]:
    if batch_size <= 0:
        raise ValueError("CONFIG['batch_size'] must be > 0")
    return [
        samples[start:start + batch_size]
        for start in range(0, len(samples), batch_size)
    ]


def _select_batches(
    samples: List[SFTSample],
    config: Dict[str, Any],
) -> List[tuple[int, List[SFTSample]]]:
    batches = _chunk_samples(samples, int(config.get("batch_size") or 1))
    batch_index = int(config.get("batch_index") or 0)
    if batch_index <= 0:
        return list(enumerate(batches, start=1))
    if batch_index > len(batches):
        return []
    return [(batch_index, batches[batch_index - 1])]


def _append_jsonl(path: Path, record: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, default=_json_default) + "\n")


def _percentile(values: List[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = int(math.ceil((pct / 100.0) * len(ordered))) - 1
    return ordered[max(0, min(index, len(ordered) - 1))]


def build_summary(records: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    rows = list(records)
    completed = [row for row in rows if row.get("status") == "completed"]
    failed = [row for row in rows if row.get("status") == "failed"]
    latencies = [
        float(row.get("latency_ms") or 0.0)
        for row in completed
        if row.get("latency_ms") is not None
    ]

    def mean_metric(key: str) -> Optional[float]:
        vals = [
            float(row["metrics"][key])
            for row in completed
            if isinstance(row.get("metrics"), dict)
            and isinstance(row["metrics"].get(key), (int, float))
        ]
        return round(statistics.mean(vals), 4) if vals else None

    by_doc_type: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        doc_type = str(row.get("doc_type") or "unknown")
        entry = by_doc_type.setdefault(doc_type, {"total": 0, "completed": 0, "failed": 0})
        entry["total"] += 1
        if row.get("status") == "completed":
            entry["completed"] += 1
        elif row.get("status") == "failed":
            entry["failed"] += 1

    by_mode: Dict[str, int] = {}
    for row in completed:
        key = str(row.get("backend_mode") or row.get("route") or "unknown")
        by_mode[key] = by_mode.get(key, 0) + 1

    judge_counts: Dict[str, int] = {}
    for row in completed:
        match = str(row.get("judge_match") or "")
        if match:
            judge_counts[match] = judge_counts.get(match, 0) + 1

    return {
        "total_records": len(rows),
        "completed": len(completed),
        "failed": len(failed),
        "error_rate": round(len(failed) / len(rows), 4) if rows else 0.0,
        "latency_ms": {
            "mean": round(statistics.mean(latencies), 2) if latencies else 0.0,
            "p50": _percentile(latencies, 50),
            "p95": _percentile(latencies, 95),
            "max": max(latencies) if latencies else 0.0,
        },
        "metrics": {
            "answer_nonempty_rate": mean_metric("answer_nonempty"),
            "reference_keyword_coverage": mean_metric("reference_keyword_coverage"),
            "atomic_fact_coverage": mean_metric("atomic_fact_coverage"),
            "expected_doc_hit_rate": mean_metric("expected_doc_hit"),
            "expected_article_hit_rate": mean_metric("expected_article_hit"),
            "expected_clause_hit_rate": mean_metric("expected_clause_hit"),
            "citation_text_hit_rate": mean_metric("citation_text_hit"),
        },
        "by_doc_type": by_doc_type,
        "by_mode": by_mode,
        "judge": judge_counts,
        "updated_at": _now_iso(),
    }


def _write_progress(
    *,
    run_dir: Path,
    run_id: str,
    samples_total: int,
    records: Dict[str, Dict[str, Any]],
    config: Dict[str, Any],
) -> None:
    status_counts: Dict[str, int] = {}
    sample_statuses: Dict[str, str] = {}
    for sample_id, record in records.items():
        status = str(record.get("status") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        sample_statuses[sample_id] = status
    _atomic_write_json(
        run_dir / "progress.json",
        {
            "run_id": run_id,
            "samples_total": samples_total,
            "records_total": len(records),
            "status_counts": status_counts,
            "sample_statuses": sample_statuses,
            "config": config,
            "updated_at": _now_iso(),
        },
    )


def _write_final_outputs(run_dir: Path, records: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    ordered = sorted(records.values(), key=lambda row: int(row.get("index") or 0))
    results_jsonl = run_dir / "results.jsonl"
    with results_jsonl.open("w", encoding="utf-8") as handle:
        for record in ordered:
            handle.write(json.dumps(record, ensure_ascii=False, default=_json_default) + "\n")

    results_csv = run_dir / "results.csv"
    fields = [
        "sample_id", "index", "batch_index", "status", "question", "reference_answer",
        "generated_answer", "doc_type", "document_title", "article", "clause",
        "identity_mode", "auth_header_sent", "optional_fields_sent", "request_payload_hash",
        "request_mode", "request_top_k", "request_history_len", "request_session_id",
        "response_session_id", "backend_url", "backend_mode", "route", "reflected_question",
        "num_sources", "latency_ms", "cache_hit", "query_cache_hit", "agent_error",
        "iterations", "error",
        "reference_keyword_coverage", "atomic_fact_coverage", "citation_text_hit",
        "expected_doc_hit", "expected_article_hit", "expected_clause_hit",
        "judge_match", "judge_reason",
    ]
    with results_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in ordered:
            metrics = record.get("metrics") if isinstance(record.get("metrics"), dict) else {}
            row = dict(record)
            for key in (
                "reference_keyword_coverage", "atomic_fact_coverage",
                "citation_text_hit", "expected_doc_hit", "expected_article_hit",
                "expected_clause_hit",
            ):
                row[key] = metrics.get(key)
            writer.writerow({field: row.get(field, "") for field in fields})

    summary = build_summary(ordered)
    _atomic_write_json(run_dir / "summary.json", summary)
    return summary


def _prepare_run_dir(config: Dict[str, Any]) -> tuple[str, Path]:
    if config.get("resume_dir"):
        run_dir = _resolve_project_path(str(config["resume_dir"]))
        run_dir.mkdir(parents=True, exist_ok=True)
        run_id = run_dir.name
        return run_id, run_dir

    output_dir = _resolve_project_path(str(config["output_dir"]))
    if config.get("run_dir"):
        run_dir = _resolve_project_path(str(config["run_dir"]))
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir.name, run_dir

    if not _config_bool(config, "timestamped_run_dir", False):
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir.name, output_dir

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = output_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_id, run_dir


def _record_failure(
    sample: SFTSample,
    exc: Exception,
    latency_ms: float,
    config: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    record = {
        "sample_id": sample.sample_id,
        "index": sample.index,
        "status": "failed",
        "question": sample.instruction,
        "reference_answer": sample.reference_answer,
        "generated_answer": "",
        "doc_type": sample.doc_type,
        "document_title": sample.metadata.get("document_title", ""),
        "article": sample.metadata.get("article", ""),
        "clause": sample.metadata.get("clause", ""),
        "latency_ms": latency_ms,
        "error": str(exc),
        "finished_at": _now_iso(),
    }

    if config is not None:
        try:
            request_payload = _build_frontend_chat_payload(
                question=sample.instruction,
                config=config,
            )
            request_headers = _frontend_chat_headers(config)
            record.update(
                _request_record_metadata(
                    config=config,
                    backend_url=str(config.get("backend_url") or ""),
                    request_payload=request_payload,
                    request_headers=request_headers,
                )
            )
            record["request_payload"] = (
                request_payload
                if _config_bool(config, "record_request_payload", True)
                else None
            )
        except Exception as metadata_exc:
            record["request_metadata_error"] = str(metadata_exc)

    return record


def evaluate_sample(sample: SFTSample, config: Dict[str, Any]) -> Dict[str, Any]:
    started = time.perf_counter()
    response, request_payload, request_headers = _post_backend(
        backend_url=str(config["backend_url"]),
        question=sample.instruction,
        config=config,
        timeout_s=float(config["timeout_s"]),
    )
    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    generated = str(response.get("answer") or "")
    sources = _as_source_list(response)
    metrics = calculate_metrics(sample, generated, sources)
    request_history = request_payload.get("history")
    response_trace_keys = (
        "reflected_question",
        "target_collections",
        "collection_scores",
        "routing_probabilities",
        "timings_ms",
        "applied_filters",
        "collection_results",
        "cache_hit",
        "query_cache_hit",
        "agent_error",
        "agent_trace",
        "rerank_trace",
        "answer_quality_gate",
        "context_trace",
        "fusion_weights",
        "tools_used",
        "tool_calls",
        "iterations",
    )
    always_trace_keys = {
        "rerank_trace",
        "answer_quality_gate",
        "context_trace",
        "fusion_weights",
        "tools_used",
        "tool_calls",
    }
    response_trace = {
        key: response.get(key)
        for key in response_trace_keys
        if response.get(key) is not None or key in always_trace_keys
    }

    judge = _compare_with_reference(
        judge_backend=str(config.get("judge_backend") or "none"),
        question=sample.instruction,
        reference=sample.reference_answer,
        generated=generated,
        config=config,
    )

    return {
        "sample_id": sample.sample_id,
        "index": sample.index,
        "status": "completed",
        "question": sample.instruction,
        "reference_answer": sample.reference_answer,
        "generated_answer": generated,
        "doc_type": sample.doc_type,
        "document_title": sample.metadata.get("document_title", ""),
        "chapter": sample.metadata.get("chapter", ""),
        "article": sample.metadata.get("article", ""),
        "clause": sample.metadata.get("clause", ""),
        "effective_date": sample.metadata.get("effective_date", ""),
        **_request_record_metadata(
            config=config,
            backend_url=str(config["backend_url"]),
            request_payload=request_payload,
            request_headers=request_headers,
        ),
        "request_mode": request_payload.get("mode"),
        "request_top_k": request_payload.get("top_k"),
        "request_history_len": (
            len(request_history) if isinstance(request_history, list) else 0
        ),
        "request_session_id": request_payload.get("session_id", ""),
        "request_user_id": request_payload.get("user_id", ""),
        "request_user_context": request_payload.get("user_context"),
        "request_payload": (
            request_payload
            if _config_bool(config, "record_request_payload", True)
            else None
        ),
        "backend_url": str(config["backend_url"]),
        "response_session_id": response.get("session_id", ""),
        "backend_mode": response.get("mode"),
        "route": response.get("route") or response.get("intent"),
        "reflected_question": response.get("reflected_question"),
        "target_collections": response.get("target_collections"),
        "routing_probabilities": response.get("routing_probabilities"),
        "timings_ms": response.get("timings_ms"),
        "cache_hit": response.get("cache_hit", False),
        "query_cache_hit": response.get("query_cache_hit", False),
        "agent_error": response.get("agent_error", ""),
        "iterations": response.get("iterations"),
        "response_trace": (
            response_trace
            if _config_bool(config, "record_response_trace", True)
            else None
        ),
        "num_sources": len(sources),
        "source_ids": [_source_id(source) for source in sources],
        "source_titles": [_source_title(source) for source in sources],
        "source_texts_preview": [
            str(source.get("content") or source.get("text") or "")[:800]
            for source in sources
        ],
        "metrics": metrics,
        "latency_ms": latency_ms,
        "error": "",
        "judge_match": judge.get("match", ""),
        "judge_reason": judge.get("reason", ""),
        "finished_at": _now_iso(),
    }


def _evaluate_sample_safe(sample: SFTSample, config: Dict[str, Any]) -> Dict[str, Any]:
    sample_t0 = time.perf_counter()
    try:
        return evaluate_sample(sample, config)
    except Exception as exc:
        latency_ms = round((time.perf_counter() - sample_t0) * 1000, 2)
        logger.error("Sample failed: %s", exc)
        return _record_failure(sample, exc, latency_ms, config)


def _evaluate_batch(
    *,
    batch_no: int,
    batch_samples: List[SFTSample],
    records: Dict[str, Dict[str, Any]],
    run_dir: Path,
    run_id: str,
    samples_total: int,
    config: Dict[str, Any],
) -> int:
    pending: List[SFTSample] = []
    retry_failed = bool(config.get("retry_failed"))
    for sample in batch_samples:
        if should_skip_sample(sample, records, retry_failed=retry_failed):
            logger.info(
                "Batch %04d skip sample=%s status=%s",
                batch_no,
                sample.sample_id,
                records[sample.sample_id].get("status"),
            )
            continue
        pending.append(sample)

    if not pending:
        logger.info("Batch %04d has no pending samples", batch_no)
        _write_progress(
            run_dir=run_dir,
            run_id=run_id,
            samples_total=samples_total,
            records=records,
            config=config,
        )
        return 0

    max_workers = max(1, int(config.get("batch_concurrency") or 1))
    max_workers = min(max_workers, len(pending))
    results_path = run_dir / "results.jsonl"

    logger.info(
        "Batch %04d sending %d independent requests with concurrency=%d",
        batch_no,
        len(pending),
        max_workers,
    )

    written = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_evaluate_sample_safe, sample, config): sample
            for sample in pending
        }
        for future in as_completed(futures):
            sample = futures[future]
            record = future.result()
            record["batch_index"] = batch_no
            _append_jsonl(results_path, record)
            records[sample.sample_id] = record
            written += 1

            logger.info(
                "Batch %04d wrote sample=%s status=%s (%d/%d)",
                batch_no,
                sample.sample_id,
                record.get("status"),
                written,
                len(pending),
            )
            _write_progress(
                run_dir=run_dir,
                run_id=run_id,
                samples_total=samples_total,
                records=records,
                config=config,
            )

    return written


def run(config: Dict[str, Any] = CONFIG) -> Dict[str, Any]:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%H:%M:%S",
    )
    run_id, run_dir = _prepare_run_dir(config)

    samples = _select_samples(load_sft_dataset(str(config["dataset_path"])), config)
    batches = _select_batches(samples, config)
    records = load_existing_records(
        run_dir,
        include_child_run_dirs=_config_bool(config, "merge_child_run_dirs", True),
    )

    logger.info("Run directory: %s", run_dir)
    logger.info("Loaded %d selected samples", len(samples))
    logger.info("Selected %d batch(es)", len(batches))
    logger.info("Existing records: %d", len(records))

    if not batches:
        logger.warning("No batches selected. Check CONFIG['batch_index'], start_index, and limit.")
        _write_progress(
            run_dir=run_dir,
            run_id=run_id,
            samples_total=len(samples),
            records=records,
            config=config,
        )

    for batch_no, batch_samples in batches:
        _evaluate_batch(
            batch_no=batch_no,
            batch_samples=batch_samples,
            records=records,
            run_dir=run_dir,
            run_id=run_id,
            samples_total=len(samples),
            config=config,
        )
        _atomic_write_json(run_dir / "summary_partial.json", build_summary(records.values()))

        delay = float(config.get("delay_s") or 0.0)
        if delay > 0:
            time.sleep(delay)

    summary = _write_final_outputs(run_dir, records)
    output_root = _resolve_project_path(str(config["output_dir"]))
    output_root.mkdir(parents=True, exist_ok=True)
    _atomic_write_json(
        output_root / "latest.json",
        {
            "run_id": run_id,
            "run_dir": str(run_dir),
            "summary": summary,
            "updated_at": _now_iso(),
        },
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


if __name__ == "__main__":
    run(CONFIG)
