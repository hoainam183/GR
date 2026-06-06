"""Evaluate JSON RAG datasets from evaluation/data against retrieval and live chat.

The datasets in ``evaluation/data`` use a top-level ``items`` array.  This
runner keeps that shape separate from the existing current-policy loaders so
historical/current eval behavior does not change.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import statistics
import sys
import time
import unicodedata
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_DATASET = PROJECT_ROOT / "evaluation" / "data" / "QD_ho_tro_SV_khuyet_tat_dataset.json"
DEFAULT_DATA_DIR = PROJECT_ROOT / "evaluation" / "data"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "evaluation" / "results" / "rag_dataset_eval"
DEFAULT_BACKEND_URL = "http://localhost:8000/chat/v3"
RETRIEVAL_VARIANTS = ("no_rerank", "rerank")


@dataclass
class RAGDatasetCase:
    case_uid: str
    dataset_file: str
    dataset_name: str
    source_file: str
    original_id: str
    item_index: int
    question_type: str
    question: str
    reference_answer: str
    expected_source_ids: List[str] = field(default_factory=list)
    ground_truth_context_texts: List[str] = field(default_factory=list)
    answerable: bool = True
    expected_behavior: str = "answer_with_citation"
    reasoning_required: str = ""
    difficulty: str = "medium"
    expected_collection: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_canonical_dict(self) -> Dict[str, Any]:
        return {
            "id": self.case_uid,
            "case_uid": self.case_uid,
            "category": "retrieval",
            "dataset_file": self.dataset_file,
            "dataset_name": self.dataset_name,
            "source_file": self.source_file,
            "original_id": self.original_id,
            "question": self.question,
            "query": self.question,
            "question_type": self.question_type,
            "ground_truth": self.reference_answer,
            "ground_truth_answer": self.reference_answer,
            "reference_answer": self.reference_answer,
            "expected_source_ids": list(self.expected_source_ids),
            "ground_truth_contexts": list(self.expected_source_ids),
            "ground_truth_context_texts": list(self.ground_truth_context_texts),
            "answerable": self.answerable,
            "expected_behavior": self.expected_behavior,
            "reasoning_required": self.reasoning_required,
            "difficulty": self.difficulty,
            "expected_collection": self.expected_collection,
            "expected_collections": [self.expected_collection] if self.expected_collection else [],
            "metadata": dict(self.metadata),
        }


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    return str(value)


def _elapsed_ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 2)


def _as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.replace(";", ",").split(",") if part.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _raw_id(value: Any) -> str:
    text = str(value or "").strip()
    return text.split("/", 1)[-1] if "/" in text else text


def _normalize_question_type(value: Any) -> str:
    text = str(value or "unknown").strip().lower().replace("-", "_")
    return text or "unknown"


def _expected_behavior(answerable: bool, question_type: str) -> str:
    if not answerable or question_type == "adversarial":
        return "refuse_insufficient_context"
    return "answer_with_citation"


def _stable_uid(dataset_stem: str, original_id: str, index: int) -> str:
    item_id = original_id or f"item_{index:04d}"
    return f"{dataset_stem}::{item_id}"


def _short_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def _strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text or "")
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def _norm_text(text: str) -> str:
    lowered = _strip_accents(text).lower()
    return " ".join(re.findall(r"[\w]+", lowered, flags=re.UNICODE))


def _tokens(text: str) -> List[str]:
    return re.findall(r"[\w]+", _norm_text(text), flags=re.UNICODE)


def _significant_tokens(text: str) -> List[str]:
    stopwords = {
        "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
        "in", "is", "it", "of", "on", "or", "the", "to", "with",
        "la", "va", "cua", "cho", "cac", "co", "duoc", "trong", "theo",
        "sinh", "vien", "hoc", "nguoi", "nay", "do", "ve", "tai",
    }
    return [token for token in _tokens(text) if len(token) >= 3 and token not in stopwords]


def load_dataset_file(
    dataset_path: Path,
    *,
    chunk_index: Optional[Dict[str, Dict[str, str]]] = None,
) -> List[RAGDatasetCase]:
    payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise ValueError(f"Dataset must be a JSON object with an items array: {dataset_path}")

    dataset_stem = dataset_path.stem
    dataset_name = str(payload.get("dataset_name") or dataset_stem)
    source_file = str(payload.get("source_file") or "")
    cases: List[RAGDatasetCase] = []
    for index, item in enumerate(payload["items"], start=1):
        if not isinstance(item, dict):
            continue
        original_id = str(item.get("id") or f"item_{index:04d}")
        question_type = _normalize_question_type(item.get("question_type"))
        answerable = item.get("is_answerable")
        if not isinstance(answerable, bool):
            answerable = question_type != "adversarial"
        expected_source_ids = [_raw_id(value) for value in _as_list(item.get("evidence_chunk_ids"))]
        expected_source_ids = [value for value in expected_source_ids if value]
        expected_collection = infer_collection(expected_source_ids, chunk_index or {})
        cases.append(
            RAGDatasetCase(
                case_uid=_stable_uid(dataset_stem, original_id, index),
                dataset_file=dataset_path.name,
                dataset_name=dataset_name,
                source_file=source_file,
                original_id=original_id,
                item_index=index,
                question_type=question_type,
                question=str(item.get("question") or "").strip(),
                reference_answer=str(item.get("gold_answer") or "").strip(),
                expected_source_ids=expected_source_ids,
                ground_truth_context_texts=_as_list(item.get("ground_truth_context")),
                answerable=answerable,
                expected_behavior=_expected_behavior(answerable, question_type),
                reasoning_required=str(item.get("reasoning_required") or "").strip(),
                difficulty=str(item.get("difficulty") or "medium").strip() or "medium",
                expected_collection=expected_collection,
                metadata={
                    "dataset_total_questions": payload.get("total_questions"),
                    "distribution": payload.get("distribution") or {},
                    "raw": item,
                },
            )
        )
    return cases


def load_cases(
    *,
    dataset: Optional[Path],
    input_dir: Optional[Path],
    max_cases: int = 0,
    chunk_index: Optional[Dict[str, Dict[str, str]]] = None,
) -> List[RAGDatasetCase]:
    paths: List[Path]
    if dataset is not None:
        paths = [dataset]
    else:
        root = input_dir or DEFAULT_DATA_DIR
        paths = sorted(root.glob("*.json"))

    cases: List[RAGDatasetCase] = []
    for path in paths:
        cases.extend(load_dataset_file(path, chunk_index=chunk_index))
        if max_cases and len(cases) >= max_cases:
            return cases[:max_cases]
    return cases


def _iter_chunk_rows(payload: Any) -> Iterable[Dict[str, Any]]:
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        rows = (
            payload.get("chunks")
            or payload.get("items")
            or payload.get("data")
            or payload.get("rows")
            or []
        )
    else:
        rows = []
    for row in rows:
        if isinstance(row, dict):
            yield row


def _collection_from_chunk_path(path: Path, data_root: Path) -> str:
    try:
        rel = path.relative_to(data_root)
        return rel.parts[0] if rel.parts else ""
    except ValueError:
        parts = path.parts
        if "data" in parts:
            index = parts.index("data")
            if index + 1 < len(parts):
                return parts[index + 1]
    return ""


def build_chunk_index(data_root: Path = PROJECT_ROOT / "data") -> Dict[str, Dict[str, str]]:
    index: Dict[str, Dict[str, str]] = {}
    if not data_root.exists():
        return index
    for path in data_root.rglob("*chunks*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        collection = _collection_from_chunk_path(path, data_root)
        for row in _iter_chunk_rows(payload):
            for key in ("id", "chunk_id", "readable_id"):
                value = str(row.get(key) or "").strip()
                if value:
                    index[_raw_id(value)] = {
                        "collection": collection,
                        "path": str(path),
                    }
    return index


def infer_collection(
    expected_source_ids: List[str],
    chunk_index: Dict[str, Dict[str, str]],
) -> str:
    collections = [
        chunk_index[doc_id]["collection"]
        for doc_id in expected_source_ids
        if doc_id in chunk_index and chunk_index[doc_id].get("collection")
    ]
    if not collections:
        return ""
    return Counter(collections).most_common(1)[0][0]


def validate_cases(
    cases: List[RAGDatasetCase],
    *,
    chunk_index: Optional[Dict[str, Dict[str, str]]] = None,
) -> Dict[str, Any]:
    chunk_index = chunk_index or {}
    duplicate_original_ids = sum(
        count - 1 for count in Counter(case.original_id for case in cases).values() if count > 1
    )
    schema_valid = 0
    missing_evidence = 0
    missing_context = 0
    missing_reference = 0
    missing_question = 0
    evidence_refs = 0
    missing_evidence_refs = 0
    case_errors: List[Dict[str, Any]] = []

    for case in cases:
        errors: List[str] = []
        if not case.question:
            errors.append("missing_question")
            missing_question += 1
        if not case.reference_answer:
            errors.append("missing_reference_answer")
            missing_reference += 1
        if case.answerable and not case.expected_source_ids:
            errors.append("missing_expected_source_ids")
            missing_evidence += 1
        if case.answerable and not case.ground_truth_context_texts:
            errors.append("missing_ground_truth_context")
            missing_context += 1
        for doc_id in case.expected_source_ids:
            evidence_refs += 1
            if chunk_index and doc_id not in chunk_index:
                missing_evidence_refs += 1
        if not errors:
            schema_valid += 1
        else:
            case_errors.append({"case_uid": case.case_uid, "errors": errors})

    return {
        "total_cases": len(cases),
        "schema_valid_cases": schema_valid,
        "schema_valid_rate": round(schema_valid / len(cases), 4) if cases else 0.0,
        "duplicate_original_id_count": duplicate_original_ids,
        "missing_question_count": missing_question,
        "missing_reference_count": missing_reference,
        "missing_evidence_count": missing_evidence,
        "missing_context_count": missing_context,
        "evidence_ref_count": evidence_refs,
        "evidence_ref_missing_in_chunks": missing_evidence_refs,
        "evidence_ref_coverage": (
            round(1.0 - (missing_evidence_refs / evidence_refs), 4)
            if evidence_refs and chunk_index
            else None
        ),
        "by_question_type": dict(Counter(case.question_type for case in cases)),
        "by_difficulty": dict(Counter(case.difficulty for case in cases)),
        "by_answerable": dict(Counter(str(case.answerable).lower() for case in cases)),
        "case_errors": case_errors[:100],
    }


def _ranking_metrics_for_k(retrieved: List[str], relevant: List[str], k: int) -> Dict[str, float]:
    retrieved_raw = [_raw_id(value) for value in retrieved if _raw_id(value)]
    relevant_set = {_raw_id(value) for value in relevant if _raw_id(value)}
    topk = retrieved_raw[:k]
    if not relevant_set:
        return {
            f"hit@{k}": 0.0,
            f"precision@{k}": 0.0,
            f"recall@{k}": 0.0,
            f"mrr@{k}": 0.0,
            f"ndcg@{k}": 0.0,
        }

    hits = [doc_id for doc_id in topk if doc_id in relevant_set]
    hit = 1.0 if hits else 0.0
    precision = len(set(hits)) / k if k else 0.0
    recall = len(set(hits)) / len(relevant_set)
    mrr = 0.0
    for rank, doc_id in enumerate(topk, start=1):
        if doc_id in relevant_set:
            mrr = 1.0 / rank
            break
    dcg = sum(
        1.0 / math.log2(rank + 1)
        for rank, doc_id in enumerate(topk, start=1)
        if doc_id in relevant_set
    )
    ideal_hits = min(len(relevant_set), k)
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
    return {
        f"hit@{k}": round(hit, 4),
        f"precision@{k}": round(precision, 4),
        f"recall@{k}": round(recall, 4),
        f"mrr@{k}": round(mrr, 4),
        f"ndcg@{k}": round(dcg / idcg, 4) if idcg else 0.0,
    }


def compute_ranking_metrics(
    retrieved_ids: List[str],
    expected_source_ids: List[str],
    *,
    cutoffs: Iterable[int] = (1, 3, 5),
) -> Dict[str, float]:
    metrics: Dict[str, float] = {}
    for k in cutoffs:
        metrics.update(_ranking_metrics_for_k(retrieved_ids, expected_source_ids, k))
    expected_set = {_raw_id(value) for value in expected_source_ids if _raw_id(value)}
    retrieved_set = {_raw_id(value) for value in retrieved_ids if _raw_id(value)}
    metrics["all_evidence_recalled"] = (
        1.0 if expected_set and expected_set <= retrieved_set else 0.0
    )
    return metrics


def _source_id(doc: Dict[str, Any]) -> str:
    """Return the stable evidence id used by dataset ``evidence_chunk_ids``."""
    metadata = doc.get("metadata") if isinstance(doc.get("metadata"), dict) else {}
    candidates = (
        doc.get("id"),
        doc.get("chunk_id"),
        doc.get("source_id"),
        metadata.get("chunk_id"),
        metadata.get("id"),
        metadata.get("doc_id"),
        metadata.get("document_id"),
    )
    for value in candidates:
        normalized = _raw_id(value)
        if normalized:
            return normalized
    return ""


def _doc_text(doc: Dict[str, Any]) -> str:
    return str(doc.get("text") or doc.get("content") or "")


def _clone_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    cloned = dict(doc)
    metadata = doc.get("metadata")
    if isinstance(metadata, dict):
        cloned["metadata"] = dict(metadata)
    return cloned


def _clone_docs(docs: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [_clone_doc(doc) for doc in docs if isinstance(doc, dict)]


def _retrieved_ids(docs: Iterable[Dict[str, Any]]) -> List[str]:
    return [doc_id for doc_id in (_source_id(doc) for doc in docs) if doc_id]


def _retrieved_collections(docs: Iterable[Dict[str, Any]]) -> List[str]:
    out: List[str] = []
    for doc in docs:
        metadata = doc.get("metadata") if isinstance(doc.get("metadata"), dict) else {}
        collection = str(doc.get("collection") or metadata.get("collection") or "").strip()
        if collection and collection not in out:
            out.append(collection)
    return out


def _compact_retrieval_sources(docs: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    sources: List[Dict[str, Any]] = []
    for rank, doc in enumerate(docs, start=1):
        metadata = doc.get("metadata") if isinstance(doc.get("metadata"), dict) else {}
        sources.append(
            {
                "rank": rank,
                "source_id": _source_id(doc),
                "id": _raw_id(doc.get("id")),
                "chunk_id": _raw_id(doc.get("chunk_id") or metadata.get("chunk_id")),
                "collection": doc.get("collection") or metadata.get("collection"),
                "score": doc.get("score"),
                "rerank_score": doc.get("rerank_score"),
                "vector_score": doc.get("vector_score"),
                "keyword_score": doc.get("keyword_score"),
                "text": _doc_text(doc)[:800],
                "metadata": {
                    key: metadata.get(key)
                    for key in (
                        "source",
                        "filename",
                        "source_file",
                        "document_id",
                        "doc_id",
                        "doc_title",
                        "title",
                        "major_code",
                        "applicable_cohort",
                        "date_str",
                        "section_h1",
                        "section_h2",
                        "section_h3",
                    )
                    if metadata.get(key) is not None
                },
            }
        )
    return sources


def _metric_cutoffs(top_k: int) -> List[int]:
    return sorted({1, 3, max(1, int(top_k or 5))})


def _collection_hit(retrieved_collections: List[str], expected_collection: str) -> Optional[float]:
    expected = str(expected_collection or "").strip()
    if not expected:
        return None
    return 1.0 if expected in set(retrieved_collections) else 0.0


def compute_retrieval_variant_metrics(
    *,
    retrieved_ids: List[str],
    retrieved_collections: List[str],
    case: RAGDatasetCase,
    top_k: int,
) -> Dict[str, Optional[float]]:
    metrics: Dict[str, Optional[float]] = compute_ranking_metrics(
        retrieved_ids,
        case.expected_source_ids,
        cutoffs=_metric_cutoffs(top_k),
    )
    metrics["collection_hit"] = _collection_hit(
        retrieved_collections,
        case.expected_collection,
    )
    metrics["multi_hop_all_evidence_recalled"] = (
        metrics["all_evidence_recalled"]
        if case.question_type == "multi_hop"
        else None
    )
    return metrics


def _text_overlap_score(expected_text: str, actual_text: str) -> float:
    expected = set(_significant_tokens(expected_text))
    actual = set(_significant_tokens(actual_text))
    if not expected or not actual:
        return 0.0
    return len(expected & actual) / len(expected)


def compute_context_text_metrics(
    source_texts: List[str],
    expected_contexts: List[str],
    *,
    cutoffs: Iterable[int] = (1, 3, 5),
) -> Dict[str, float]:
    metrics: Dict[str, float] = {}
    if not expected_contexts:
        for k in cutoffs:
            metrics[f"context_text_hit@{k}"] = 0.0
            metrics[f"context_text_recall@{k}"] = 0.0
        metrics["context_text_all_evidence_recalled"] = 0.0
        return metrics

    matched_at: Dict[int, set[int]] = {}
    for k in cutoffs:
        matched: set[int] = set()
        for expected_index, expected in enumerate(expected_contexts):
            for source_text in source_texts[:k]:
                if _text_overlap_score(expected, source_text) >= 0.45:
                    matched.add(expected_index)
                    break
        matched_at[k] = matched
        metrics[f"context_text_hit@{k}"] = 1.0 if matched else 0.0
        metrics[f"context_text_recall@{k}"] = round(len(matched) / len(expected_contexts), 4)

    largest_k = max(cutoffs)
    metrics["context_text_all_evidence_recalled"] = (
        1.0 if len(matched_at.get(largest_k, set())) == len(expected_contexts) else 0.0
    )
    return metrics


def _extract_facts(text: str) -> List[str]:
    normalized = " ".join((text or "").split())
    facts = re.findall(r"\b\d+(?:[.,]\d+)?(?:/\d+)?\b", normalized)
    facts.extend(re.findall(r"\b[A-Z]{2,}[A-Z0-9_-]*\b", normalized))
    out: List[str] = []
    for fact in facts:
        if fact not in out:
            out.append(fact)
    return out


def _coverage(expected: List[str], actual_text: str) -> float:
    if not expected:
        return 1.0
    actual = _norm_text(actual_text)
    hits = sum(1 for item in expected if _norm_text(item) in actual)
    return round(hits / len(expected), 4)


def _token_f1(reference: str, generated: str) -> float:
    ref = Counter(_tokens(reference))
    gen = Counter(_tokens(generated))
    if not ref or not gen:
        return 0.0
    overlap = sum((ref & gen).values())
    precision = overlap / sum(gen.values())
    recall = overlap / sum(ref.values())
    if precision + recall == 0:
        return 0.0
    return round(2 * precision * recall / (precision + recall), 4)


def _lcs_len(a: List[str], b: List[str]) -> int:
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    for token_a in a:
        cur = [0]
        for index_b, token_b in enumerate(b, start=1):
            if token_a == token_b:
                cur.append(prev[index_b - 1] + 1)
            else:
                cur.append(max(prev[index_b], cur[-1]))
        prev = cur
    return prev[-1]


def _rouge_l(reference: str, generated: str) -> float:
    ref = _tokens(reference)
    gen = _tokens(generated)
    if not ref or not gen:
        return 0.0
    lcs = _lcs_len(ref, gen)
    precision = lcs / len(gen)
    recall = lcs / len(ref)
    if precision + recall == 0:
        return 0.0
    return round(2 * precision * recall / (precision + recall), 4)


def _looks_like_refusal(answer: str) -> bool:
    normalized = _norm_text(answer)
    markers = (
        "khong co du thong tin",
        "khong du thong tin",
        "khong tim thay thong tin",
        "khong the tra loi",
        "khong xac dinh duoc",
        "can them thong tin",
        "insufficient information",
        "not enough information",
    )
    return any(marker in normalized for marker in markers)


def compute_answer_metrics(case: RAGDatasetCase, generated_answer: str) -> Dict[str, Any]:
    reference = case.reference_answer
    significant = sorted(set(_significant_tokens(reference)))
    expected_facts = _extract_facts(reference)
    exact = bool(_norm_text(reference) and _norm_text(reference) == _norm_text(generated_answer))
    refused = _looks_like_refusal(generated_answer)
    metrics: Dict[str, Any] = {
        "answer_nonempty": bool(generated_answer.strip()),
        "normalized_exact_match": exact,
        "token_f1": _token_f1(reference, generated_answer),
        "rouge_l": _rouge_l(reference, generated_answer),
        "keyword_coverage": _coverage(significant, generated_answer),
        "numeric_code_coverage": _coverage(expected_facts, generated_answer),
        "refused": refused,
    }
    if not case.answerable or case.expected_behavior == "refuse_insufficient_context":
        metrics["refusal_accuracy"] = 1.0 if refused else 0.0
        metrics["over_answer"] = 0.0 if refused else 1.0
    else:
        metrics["refusal_accuracy"] = None
        metrics["over_answer"] = None
    return metrics


def enrich_live_record(record: Dict[str, Any], case: RAGDatasetCase) -> Dict[str, Any]:
    source_ids = [str(value) for value in (record.get("source_ids") or []) if str(value)]
    source_texts = [
        str(value)
        for value in (record.get("source_texts_preview") or [])
        if str(value).strip()
    ]
    source_metrics = compute_ranking_metrics(source_ids, case.expected_source_ids, cutoffs=(1, 3, 5))
    context_text_metrics = compute_context_text_metrics(
        source_texts,
        case.ground_truth_context_texts,
        cutoffs=(1, 3, 5),
    )
    answer_metrics = compute_answer_metrics(case, str(record.get("generated_answer") or ""))
    existing_metrics = record.get("metrics") if isinstance(record.get("metrics"), dict) else {}
    merged_metrics = {
        **existing_metrics,
        **{f"source_{key}": value for key, value in source_metrics.items()},
        **context_text_metrics,
        **answer_metrics,
    }
    merged_metrics["citation_source_hit"] = max(
        float(merged_metrics.get("source_hit@5") or 0.0),
        float(merged_metrics.get("context_text_hit@5") or 0.0),
    )

    out = dict(record)
    out.update(
        {
            "case_uid": case.case_uid,
            "original_id": case.original_id,
            "dataset_file": case.dataset_file,
            "dataset_name": case.dataset_name,
            "source_file": case.source_file,
            "question_type": case.question_type,
            "difficulty": case.difficulty,
            "reasoning_required": case.reasoning_required,
            "answerable": case.answerable,
            "expected_behavior": case.expected_behavior,
            "expected_source_ids": case.expected_source_ids,
            "ground_truth_context_count": len(case.ground_truth_context_texts),
            "metrics": merged_metrics,
        }
    )
    return out


def _safe_evaluate_sample(sample: Any, config: Dict[str, Any]) -> Dict[str, Any]:
    from evaluation.evaluate_sft_backend import _record_failure, evaluate_sample

    started = time.perf_counter()
    try:
        return evaluate_sample(sample, config)
    except Exception as exc:
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        return _record_failure(sample, exc, latency_ms, config)


def run_live_eval(
    cases: List[RAGDatasetCase],
    *,
    backend_url: str,
    judge_backend: str,
    timeout_s: float,
    delay_s: float = 0.0,
) -> List[Dict[str, Any]]:
    from evaluation.evaluate_sft_backend import SFTSample

    config = {
        "backend_url": backend_url,
        "identity_mode": "anonymous",
        "mode": "auto",
        "top_k": 5,
        "history": [],
        "session_id": None,
        "user_context": None,
        "user_id": None,
        "send_null_optional_fields": False,
        "record_request_payload": True,
        "record_response_trace": True,
        "require_no_cache": True,
        "auth_token": "",
        "auth_token_env": "EVAL_AUTH_TOKEN",
        "judge_backend": judge_backend,
        "timeout_s": timeout_s,
        "lmstudio_base_url": "http://localhost:1234/v1",
        "lmstudio_model": "qwen/qwen3-8b:2",
        "gemini_model": "gemini-3.1-flash-lite",
    }
    records: List[Dict[str, Any]] = []
    for index, case in enumerate(cases, start=1):
        sample = SFTSample(
            index=index,
            sample_id=_short_hash(case.case_uid),
            instruction=case.question,
            input="\n\n".join(case.ground_truth_context_texts),
            reference_answer=case.reference_answer,
            doc_type=case.expected_collection or case.source_file or case.dataset_name,
            metadata={
                "document_title": case.source_file or case.dataset_name,
                "ground_truth_context_text": "\n\n".join(case.ground_truth_context_texts),
            },
        )
        record = _safe_evaluate_sample(sample, config)
        records.append(enrich_live_record(record, case))
        if delay_s > 0 and index < len(cases):
            time.sleep(delay_s)
    return records


def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, default=_json_default) + "\n")


def write_canonical_cases(run_dir: Path, cases: List[RAGDatasetCase]) -> Path:
    path = run_dir / "canonical_cases.jsonl"
    write_jsonl(path, (case.to_canonical_dict() for case in cases))
    return path


def _csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, default=_json_default)
    return value


def write_records_csv(path: Path, records: List[Dict[str, Any]]) -> None:
    if not records:
        path.write_text("", encoding="utf-8-sig")
        return
    fields: List[str] = []
    for record in records:
        for key in record:
            if key not in fields:
                fields.append(key)
    metric_keys = sorted(
        {
            key
            for record in records
            if isinstance(record.get("metrics"), dict)
            for key in record["metrics"]
        }
    )
    fields = [field for field in fields if field != "metrics"] + [f"metric.{key}" for key in metric_keys]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in records:
            row = {field: _csv_value(record.get(field, "")) for field in fields if not field.startswith("metric.")}
            metrics = record.get("metrics") if isinstance(record.get("metrics"), dict) else {}
            for key in metric_keys:
                row[f"metric.{key}"] = _csv_value(metrics.get(key, ""))
            writer.writerow(row)


def _percentile(values: List[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = int(math.ceil((pct / 100.0) * len(ordered))) - 1
    return ordered[max(0, min(index, len(ordered) - 1))]


def _mean_metric(records: List[Dict[str, Any]], key: str) -> Optional[float]:
    values = [
        float(record["metrics"][key])
        for record in records
        if isinstance(record.get("metrics"), dict)
        and isinstance(record["metrics"].get(key), (int, float, bool))
    ]
    return round(statistics.mean(values), 4) if values else None


def _group_counts(cases: List[RAGDatasetCase], attr: str) -> Dict[str, int]:
    return dict(Counter(str(getattr(case, attr)) for case in cases))


def build_eval_summary(
    cases: List[RAGDatasetCase],
    *,
    validation: Dict[str, Any],
    live_records: Optional[List[Dict[str, Any]]] = None,
    retrieval_payload: Optional[Dict[str, Any]] = None,
    retrieval_error: Optional[str] = None,
) -> Dict[str, Any]:
    live_records = live_records or []
    completed = [row for row in live_records if row.get("status") == "completed"]
    failed = [row for row in live_records if row.get("status") == "failed"]
    latencies = [
        float(row.get("latency_ms") or 0.0)
        for row in completed
        if row.get("latency_ms") is not None
    ]
    setup_invalid = [row for row in live_records if row.get("setup_invalid")]
    metric_keys = [
        "answer_nonempty",
        "normalized_exact_match",
        "token_f1",
        "rouge_l",
        "keyword_coverage",
        "numeric_code_coverage",
        "source_hit@1",
        "source_hit@3",
        "source_hit@5",
        "source_recall@5",
        "source_precision@5",
        "source_mrr@5",
        "source_ndcg@5",
        "source_all_evidence_recalled",
        "context_text_hit@1",
        "context_text_hit@3",
        "context_text_hit@5",
        "context_text_recall@5",
        "context_text_all_evidence_recalled",
        "citation_source_hit",
        "refusal_accuracy",
        "over_answer",
    ]
    return {
        "run_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "total_cases": len(cases),
        "dataset_quality": validation,
        "retrieval": {
            "summary": (retrieval_payload or {}).get("summary"),
            "error": retrieval_error,
        },
        "live": {
            "total_records": len(live_records),
            "completed": len(completed),
            "failed": len(failed),
            "error_rate": round(len(failed) / len(live_records), 4) if live_records else 0.0,
            "setup_valid": len(setup_invalid) == 0,
            "setup_invalid_count": len(setup_invalid),
            "latency_ms": {
                "mean": round(statistics.mean(latencies), 2) if latencies else 0.0,
                "p50": _percentile(latencies, 50),
                "p95": _percentile(latencies, 95),
                "max": max(latencies) if latencies else 0.0,
            },
            "metrics": {key: _mean_metric(completed, key) for key in metric_keys},
        },
        "breakdowns": {
            "by_dataset_file": _group_counts(cases, "dataset_file"),
            "by_question_type": _group_counts(cases, "question_type"),
            "by_difficulty": _group_counts(cases, "difficulty"),
            "by_reasoning_required": _group_counts(cases, "reasoning_required"),
            "by_answerable": _group_counts(cases, "answerable"),
            "by_expected_collection": _group_counts(cases, "expected_collection"),
        },
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }


def write_report(path: Path, summary: Dict[str, Any], records_path: Optional[Path]) -> None:
    quality = summary.get("dataset_quality") or {}
    live = summary.get("live") or {}
    retrieval = summary.get("retrieval") or {}
    lines = [
        "# RAG Dataset Evaluation Report",
        "",
        f"- Total cases: {summary.get('total_cases', 0)}",
        f"- Schema valid rate: {quality.get('schema_valid_rate', 0.0)}",
        f"- Evidence ref coverage: {quality.get('evidence_ref_coverage')}",
        f"- Duplicate original ids: {quality.get('duplicate_original_id_count', 0)}",
        f"- Live completed: {live.get('completed', 0)} / {live.get('total_records', 0)}",
        f"- Live error rate: {live.get('error_rate', 0.0)}",
        f"- Live setup valid: {live.get('setup_valid', True)}",
        f"- Latency p50/p95 ms: {live.get('latency_ms', {}).get('p50', 0.0)} / {live.get('latency_ms', {}).get('p95', 0.0)}",
    ]
    metrics = live.get("metrics") or {}
    if metrics:
        lines.extend(["", "## Live Metrics"])
        for key, value in metrics.items():
            lines.append(f"- {key}: {value}")
    if retrieval.get("summary"):
        lines.extend(["", "## Retrieval Summary"])
        for key, value in retrieval["summary"].items():
            if isinstance(value, (str, int, float, bool)) or value is None:
                lines.append(f"- {key}: {value}")
    if retrieval.get("error"):
        lines.extend(["", "## Retrieval Error", str(retrieval["error"])])
    if records_path is not None:
        lines.extend(["", f"Records: `{records_path}`"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_retrieval_eval(
    cases: List[RAGDatasetCase],
    *,
    top_k: int,
    validation: Dict[str, Any],
    run_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    from dotenv import load_dotenv

    from config.settings import Settings
    from query.router import QueryRouter
    from retrieval.collection_selector import CollectionSelector
    from retrieval.service import RetrievalService

    load_dotenv(PROJECT_ROOT / ".env")

    settings = Settings()
    service = RetrievalService.from_settings(settings)
    router = QueryRouter(mode=settings.router_mode, embedder=service.bge_embedder)
    selector = CollectionSelector()

    records: List[Dict[str, Any]] = []
    for case in cases:
        records.append(
            _evaluate_retrieval_case(
                case,
                top_k=top_k,
                service=service,
                router=router,
                selector=selector,
                settings=settings,
            )
        )

    payload = build_retrieval_results_payload(
        cases=cases,
        records=records,
        validation=validation,
        top_k=top_k,
        run_config={
            "mode": "offline_retrieval",
            "variants": list(RETRIEVAL_VARIANTS),
            "top_k": top_k,
            "settings": {
                "collections": list(getattr(settings, "collections", [])),
                "router_mode": getattr(settings, "router_mode", None),
                "vector_top_k": getattr(settings, "vector_top_k", None),
                "keyword_top_k": getattr(settings, "keyword_top_k", None),
                "vector_pool_k": getattr(settings, "vector_pool_k", None),
                "keyword_pool_k": getattr(settings, "keyword_pool_k", None),
                "reranker_top_k": getattr(settings, "reranker_top_k", None),
                "reranker_available": service.reranker is not None,
            },
            **(run_config or {}),
        },
    )
    return payload


def _route_retrieval_collections(
    *,
    router: Any,
    selector: Any,
    query: str,
) -> tuple[List[str], Dict[str, Any]]:
    try:
        routed = router.route(query)
        domain = routed.get("domain")
        domains = routed.get("domains") or ([domain] if domain else [])
        collections = selector.select(
            domain=domain,
            domains=domains,
            confidence=float(routed.get("confidence", 0.0) or 0.0),
            probabilities=routed.get("probabilities"),
            query=query,
        )
        return list(collections or []), routed
    except Exception as exc:
        return [], {"error": repr(exc)}


def _evaluate_retrieval_case(
    case: RAGDatasetCase,
    *,
    top_k: int,
    service: Any,
    router: Any,
    selector: Any,
    settings: Any,
) -> Dict[str, Any]:
    query = case.question.strip()
    collections, routed = _route_retrieval_collections(
        router=router,
        selector=selector,
        query=query,
    )
    active_collections = collections or list(getattr(settings, "collections", []) or [])
    timings: Dict[str, float] = {}
    trace_out: Dict[str, Any] = {}
    total_start = time.perf_counter()

    try:
        embed_start = time.perf_counter()
        bge_vec = service.bge_embedder.embed_query(query)
        timings["embed_bge_ms"] = _elapsed_ms(embed_start)

        embed_start = time.perf_counter()
        e5_vec = service.e5_embedder.embed_query(query)
        timings["embed_e5_ms"] = _elapsed_ms(embed_start)

        candidate_k = max(int(top_k or 5) * 4, 20)
        search_start = time.perf_counter()
        candidates = service.searcher.search(
            query=query,
            bge_m3_query=bge_vec,
            e5_query=e5_vec,
            top_k=candidate_k,
            vector_top_k=getattr(settings, "vector_top_k", 50),
            keyword_top_k=getattr(settings, "keyword_top_k", 50),
            vector_pool_k=getattr(settings, "vector_pool_k", 40),
            keyword_pool_k=getattr(settings, "keyword_pool_k", 40),
            active_collections=active_collections or None,
            trace_out=trace_out,
        )
        timings["search_ms"] = _elapsed_ms(search_start)
        no_rerank_total = _elapsed_ms(total_start)

        raw_docs = _clone_docs(candidates)
        no_rerank_docs = raw_docs[:top_k]
        no_rerank = _retrieval_variant_record(
            variant="no_rerank",
            docs=no_rerank_docs,
            case=case,
            top_k=top_k,
            timings={
                "embed_bge_ms": timings.get("embed_bge_ms", 0.0),
                "embed_e5_ms": timings.get("embed_e5_ms", 0.0),
                "search_ms": timings.get("search_ms", 0.0),
                "total_ms": no_rerank_total,
            },
            latency_ms=no_rerank_total,
        )

        rerank_timings = dict(timings)
        rerank_start = time.perf_counter()
        if getattr(service, "reranker", None) is not None:
            rerank_docs = service.reranker.rerank(
                query=query,
                documents=_clone_docs(candidates),
                top_k=top_k,
            )
            rerank_timings["rerank_ms"] = _elapsed_ms(rerank_start)
            rerank_available = True
        else:
            rerank_docs = _clone_docs(candidates)[:top_k]
            rerank_timings["rerank_ms"] = 0.0
            rerank_available = False
        rerank_total = _elapsed_ms(total_start)
        rerank_timings["total_ms"] = rerank_total
        rerank = _retrieval_variant_record(
            variant="rerank",
            docs=rerank_docs,
            case=case,
            top_k=top_k,
            timings=rerank_timings,
            latency_ms=rerank_total,
            extra={"reranker_available": rerank_available},
        )

        return {
            "case_uid": case.case_uid,
            "dataset_file": case.dataset_file,
            "dataset_name": case.dataset_name,
            "source_file": case.source_file,
            "original_id": case.original_id,
            "question": case.question,
            "question_type": case.question_type,
            "difficulty": case.difficulty,
            "reasoning_required": case.reasoning_required,
            "answerable": case.answerable,
            "expected_source_ids": list(case.expected_source_ids),
            "expected_collection": case.expected_collection,
            "target_collections": active_collections,
            "routing": routed,
            "trace": {
                "filters": trace_out.get("filters"),
                "collection_counts": trace_out.get("collection_counts"),
                "fusion_weights": trace_out.get("fusion_weights"),
            },
            "variants": {
                "no_rerank": no_rerank,
                "rerank": rerank,
            },
            "status": "completed",
            "error": None,
        }
    except Exception as exc:
        error = repr(exc)
        failed_variants = {
            variant: _failed_retrieval_variant(variant, case, top_k, error)
            for variant in RETRIEVAL_VARIANTS
        }
        return {
            "case_uid": case.case_uid,
            "dataset_file": case.dataset_file,
            "dataset_name": case.dataset_name,
            "source_file": case.source_file,
            "original_id": case.original_id,
            "question": case.question,
            "question_type": case.question_type,
            "difficulty": case.difficulty,
            "reasoning_required": case.reasoning_required,
            "answerable": case.answerable,
            "expected_source_ids": list(case.expected_source_ids),
            "expected_collection": case.expected_collection,
            "target_collections": active_collections,
            "routing": routed,
            "trace": {},
            "variants": failed_variants,
            "status": "failed",
            "error": error,
        }


def _retrieval_variant_record(
    *,
    variant: str,
    docs: List[Dict[str, Any]],
    case: RAGDatasetCase,
    top_k: int,
    timings: Dict[str, float],
    latency_ms: float,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    retrieved_ids = _retrieved_ids(docs)
    retrieved_collections = _retrieved_collections(docs)
    metrics = compute_retrieval_variant_metrics(
        retrieved_ids=retrieved_ids,
        retrieved_collections=retrieved_collections,
        case=case,
        top_k=top_k,
    )
    metrics["latency_ms"] = round(float(latency_ms), 2)
    metrics["error"] = 0.0
    out = {
        "variant": variant,
        "status": "completed",
        "error": None,
        "retrieved_ids": retrieved_ids,
        "retrieved_collections": retrieved_collections,
        "source_count": len(docs),
        "sources": _compact_retrieval_sources(docs),
        "metrics": metrics,
        "timings_ms": timings,
        "latency_ms": round(float(latency_ms), 2),
    }
    if extra:
        out.update(extra)
    return out


def _failed_retrieval_variant(
    variant: str,
    case: RAGDatasetCase,
    top_k: int,
    error: str,
) -> Dict[str, Any]:
    metrics = compute_retrieval_variant_metrics(
        retrieved_ids=[],
        retrieved_collections=[],
        case=case,
        top_k=top_k,
    )
    metrics["latency_ms"] = 0.0
    metrics["error"] = 1.0
    return {
        "variant": variant,
        "status": "failed",
        "error": error,
        "retrieved_ids": [],
        "retrieved_collections": [],
        "source_count": 0,
        "sources": [],
        "metrics": metrics,
        "timings_ms": {},
        "latency_ms": 0.0,
    }


def _mean_variant_metrics(records: List[Dict[str, Any]], variant: str) -> Dict[str, float]:
    metric_values: Dict[str, List[float]] = {}
    completed = 0
    for record in records:
        variant_payload = (record.get("variants") or {}).get(variant) or {}
        if variant_payload.get("status") == "completed":
            completed += 1
        metrics = variant_payload.get("metrics")
        if not isinstance(metrics, dict):
            continue
        for key, value in metrics.items():
            if isinstance(value, (int, float, bool)):
                metric_values.setdefault(key, []).append(float(value))
    summary = {
        key: round(statistics.mean(values), 4)
        for key, values in sorted(metric_values.items())
        if values
    }
    summary["completed"] = float(completed)
    summary["total"] = float(len(records))
    summary["error_rate"] = round(
        1.0 - (completed / len(records)),
        4,
    ) if records else 0.0
    return summary


def _delta_metrics(
    base: Dict[str, float],
    candidate: Dict[str, float],
) -> Dict[str, float]:
    keys = sorted(set(base) & set(candidate))
    return {
        key: round(float(candidate[key]) - float(base[key]), 4)
        for key in keys
        if key not in {"completed", "total"}
        and isinstance(base.get(key), (int, float))
        and isinstance(candidate.get(key), (int, float))
    }


def _group_retrieval_summary(
    records: List[Dict[str, Any]],
    group_key: str,
) -> Dict[str, Any]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for record in records:
        grouped.setdefault(str(record.get(group_key) or ""), []).append(record)
    return {
        key: _retrieval_summary_for_records(rows)
        for key, rows in sorted(grouped.items())
    }


def _retrieval_summary_for_records(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    no_rerank = _mean_variant_metrics(records, "no_rerank")
    rerank = _mean_variant_metrics(records, "rerank")
    return {
        "no_rerank": no_rerank,
        "rerank": rerank,
        "delta": _delta_metrics(no_rerank, rerank),
    }


def build_retrieval_results_payload(
    *,
    cases: List[RAGDatasetCase],
    records: List[Dict[str, Any]],
    validation: Dict[str, Any],
    top_k: int,
    run_config: Dict[str, Any],
) -> Dict[str, Any]:
    overall = _retrieval_summary_for_records(records)
    return {
        "run_config": {
            "top_k": top_k,
            **run_config,
        },
        "dataset_quality": validation,
        "summary": {
            "overall": {
                "no_rerank": overall["no_rerank"],
                "rerank": overall["rerank"],
            },
            "delta": overall["delta"],
            "by_dataset": _group_retrieval_summary(records, "dataset_file"),
            "by_question_type": _group_retrieval_summary(records, "question_type"),
            "case_count": len(cases),
        },
        "cases": records,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }


def write_retrieval_results_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )


def write_retrieval_results_csv(path: Path, records: List[Dict[str, Any]]) -> None:
    fields = [
        "case_uid",
        "dataset_file",
        "dataset_name",
        "source_file",
        "original_id",
        "question_type",
        "difficulty",
        "reasoning_required",
        "answerable",
        "question",
        "expected_collection",
        "expected_source_ids",
        "target_collections",
        "status",
        "error",
    ]
    metric_keys = sorted(
        {
            key
            for record in records
            for variant in RETRIEVAL_VARIANTS
            for key in (((record.get("variants") or {}).get(variant) or {}).get("metrics") or {})
        }
    )
    for variant in RETRIEVAL_VARIANTS:
        fields.extend(
            [
                f"{variant}_status",
                f"{variant}_error",
                f"{variant}_retrieved_ids",
                f"{variant}_retrieved_collections",
                f"{variant}_source_count",
                f"{variant}_latency_ms",
            ]
        )
        fields.extend(f"{variant}_{key}" for key in metric_keys)
    fields.extend(f"delta_{key}" for key in metric_keys)

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in records:
            row = {
                key: _csv_value(record.get(key, ""))
                for key in fields
                if not any(key.startswith(f"{variant}_") for variant in RETRIEVAL_VARIANTS)
                and not key.startswith("delta_")
            }
            variants = record.get("variants") or {}
            variant_metrics: Dict[str, Dict[str, Any]] = {}
            for variant in RETRIEVAL_VARIANTS:
                payload = variants.get(variant) or {}
                metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}
                variant_metrics[variant] = metrics
                row[f"{variant}_status"] = payload.get("status", "")
                row[f"{variant}_error"] = payload.get("error", "")
                row[f"{variant}_retrieved_ids"] = _csv_value(payload.get("retrieved_ids", []))
                row[f"{variant}_retrieved_collections"] = _csv_value(
                    payload.get("retrieved_collections", [])
                )
                row[f"{variant}_source_count"] = payload.get("source_count", 0)
                row[f"{variant}_latency_ms"] = payload.get("latency_ms", "")
                for key in metric_keys:
                    row[f"{variant}_{key}"] = metrics.get(key, "")
            for key in metric_keys:
                left = variant_metrics.get("no_rerank", {}).get(key)
                right = variant_metrics.get("rerank", {}).get(key)
                if isinstance(left, (int, float, bool)) and isinstance(right, (int, float, bool)):
                    row[f"delta_{key}"] = round(float(right) - float(left), 4)
                else:
                    row[f"delta_{key}"] = ""
            writer.writerow(row)


def write_retrieval_report(path: Path, payload: Dict[str, Any]) -> None:
    summary = payload.get("summary") or {}
    overall = summary.get("overall") or {}
    delta = summary.get("delta") or {}
    quality = payload.get("dataset_quality") or {}
    top_k = (payload.get("run_config") or {}).get("top_k", 5)
    lines = [
        "# Offline Retrieval Evaluation Report",
        "",
        f"- Total cases: {summary.get('case_count', 0)}",
        f"- Top K: {top_k}",
        f"- Schema valid rate: {quality.get('schema_valid_rate', 0.0)}",
        f"- Evidence ref coverage: {quality.get('evidence_ref_coverage')}",
        f"- Duplicate original ids: {quality.get('duplicate_original_id_count', 0)}",
    ]
    for variant in RETRIEVAL_VARIANTS:
        metrics = overall.get(variant) or {}
        lines.extend(
            [
                "",
                f"## {variant}",
                f"- hit@1: {metrics.get('hit@1')}",
                f"- hit@3: {metrics.get('hit@3')}",
                f"- recall@{top_k}: {metrics.get(f'recall@{top_k}')}",
                f"- precision@{top_k}: {metrics.get(f'precision@{top_k}')}",
                f"- mrr@{top_k}: {metrics.get(f'mrr@{top_k}')}",
                f"- ndcg@{top_k}: {metrics.get(f'ndcg@{top_k}')}",
                f"- all_evidence_recalled: {metrics.get('all_evidence_recalled')}",
                f"- error_rate: {metrics.get('error_rate')}",
            ]
        )
    if delta:
        lines.extend(["", "## Delta rerank - no_rerank"])
        for key, value in delta.items():
            if key in {"error", "error_rate"} or key.startswith(("hit@", "recall@", "precision@", "mrr@", "ndcg@")):
                lines.append(f"- {key}: {value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _resolve_path(path: Optional[Path]) -> Optional[Path]:
    if path is None:
        return None
    return path if path.is_absolute() else PROJECT_ROOT / path


def _prepare_run_dir(output_dir: Path) -> Path:
    run_dir = _resolve_path(output_dir) or DEFAULT_OUTPUT_DIR
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _load_and_validate(args: argparse.Namespace) -> tuple[List[RAGDatasetCase], Dict[str, Any], Path]:
    chunk_index = build_chunk_index(PROJECT_ROOT / "data")
    cases = load_cases(
        dataset=_resolve_path(args.dataset),
        input_dir=_resolve_path(args.input_dir),
        max_cases=int(args.max_cases or 0),
        chunk_index=chunk_index,
    )
    validation = validate_cases(cases, chunk_index=chunk_index)
    run_dir = _prepare_run_dir(args.output_dir)
    write_canonical_cases(run_dir, cases)
    return cases, validation, run_dir


def _args_top_k(args: argparse.Namespace) -> int:
    value = getattr(args, "top_k", None)
    if value is None:
        value = getattr(args, "k", None)
    return max(1, int(value or 5))


def _write_summary_artifacts(
    *,
    run_dir: Path,
    cases: List[RAGDatasetCase],
    validation: Dict[str, Any],
    live_records: Optional[List[Dict[str, Any]]] = None,
    retrieval_payload: Optional[Dict[str, Any]] = None,
    retrieval_error: Optional[str] = None,
) -> Dict[str, Any]:
    summary = build_eval_summary(
        cases,
        validation=validation,
        live_records=live_records,
        retrieval_payload=retrieval_payload,
        retrieval_error=retrieval_error,
    )
    (run_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )
    write_report(run_dir / "report.md", summary, run_dir / "records.jsonl" if live_records else None)
    return summary


def command_validate(args: argparse.Namespace) -> Dict[str, Any]:
    cases, validation, run_dir = _load_and_validate(args)
    return _write_summary_artifacts(run_dir=run_dir, cases=cases, validation=validation)


def command_retrieval(args: argparse.Namespace) -> Dict[str, Any]:
    cases, validation, run_dir = _load_and_validate(args)
    top_k = _args_top_k(args)
    retrieval_payload = run_retrieval_eval(
        cases,
        top_k=top_k,
        validation=validation,
        run_config={
            "dataset": str(_resolve_path(args.dataset)) if args.dataset else None,
            "input_dir": str(_resolve_path(args.input_dir)) if args.input_dir else None,
            "max_cases": int(args.max_cases or 0),
        },
    )
    write_retrieval_results_json(run_dir / "results.json", retrieval_payload)
    write_retrieval_results_csv(run_dir / "results.csv", retrieval_payload["cases"])
    write_retrieval_report(run_dir / "report.md", retrieval_payload)
    summary = {
        "run_config": retrieval_payload["run_config"],
        "dataset_quality": validation,
        "summary": retrieval_payload["summary"],
        "outputs": {
            "canonical_cases": str(run_dir / "canonical_cases.jsonl"),
            "results_json": str(run_dir / "results.json"),
            "results_csv": str(run_dir / "results.csv"),
            "report": str(run_dir / "report.md"),
        },
        "updated_at": retrieval_payload["updated_at"],
    }
    (run_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )
    return summary


def command_live(args: argparse.Namespace) -> Dict[str, Any]:
    cases, validation, run_dir = _load_and_validate(args)
    records = run_live_eval(
        cases,
        backend_url=str(args.backend_url or DEFAULT_BACKEND_URL),
        judge_backend=str(args.judge_backend or "none"),
        timeout_s=float(args.timeout_s or 240.0),
        delay_s=float(args.delay_s or 0.0),
    )
    write_jsonl(run_dir / "records.jsonl", records)
    write_records_csv(run_dir / "records.csv", records)
    return _write_summary_artifacts(
        run_dir=run_dir,
        cases=cases,
        validation=validation,
        live_records=records,
    )


def command_all(args: argparse.Namespace) -> Dict[str, Any]:
    cases, validation, run_dir = _load_and_validate(args)
    retrieval_payload: Optional[Dict[str, Any]] = None
    retrieval_error: Optional[str] = None
    try:
        retrieval_payload = run_retrieval_eval(
            cases,
            top_k=_args_top_k(args),
            validation=validation,
            run_config={
                "dataset": str(_resolve_path(args.dataset)) if args.dataset else None,
                "input_dir": str(_resolve_path(args.input_dir)) if args.input_dir else None,
                "max_cases": int(args.max_cases or 0),
            },
        )
        write_retrieval_results_json(run_dir / "results.json", retrieval_payload)
        write_retrieval_results_csv(run_dir / "results.csv", retrieval_payload["cases"])
    except Exception as exc:
        retrieval_error = repr(exc)
        (run_dir / "retrieval_error.txt").write_text(retrieval_error, encoding="utf-8")

    records = run_live_eval(
        cases,
        backend_url=str(args.backend_url or DEFAULT_BACKEND_URL),
        judge_backend=str(args.judge_backend or "none"),
        timeout_s=float(args.timeout_s or 240.0),
        delay_s=float(args.delay_s or 0.0),
    )
    write_jsonl(run_dir / "records.jsonl", records)
    write_records_csv(run_dir / "records.csv", records)
    return _write_summary_artifacts(
        run_dir=run_dir,
        cases=cases,
        validation=validation,
        live_records=records,
        retrieval_payload=retrieval_payload,
        retrieval_error=retrieval_error,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_common(sub: argparse.ArgumentParser) -> None:
        sub.add_argument("--dataset", type=Path, default=None)
        sub.add_argument("--input-dir", type=Path, default=None)
        sub.add_argument("--max-cases", type=int, default=0)
        sub.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)

    validate = subparsers.add_parser("validate")
    add_common(validate)
    validate.set_defaults(func=command_validate)

    retrieval = subparsers.add_parser("retrieval")
    add_common(retrieval)
    retrieval.add_argument("--top-k", "--k", dest="top_k", type=int, default=5)
    retrieval.set_defaults(func=command_retrieval)

    live = subparsers.add_parser("live")
    add_common(live)
    live.add_argument("--backend-url", default=DEFAULT_BACKEND_URL)
    live.add_argument("--judge-backend", choices=["none", "lmstudio", "gemini"], default="none")
    live.add_argument("--timeout-s", type=float, default=240.0)
    live.add_argument("--delay-s", type=float, default=0.0)
    live.set_defaults(func=command_live)

    all_cmd = subparsers.add_parser("all")
    add_common(all_cmd)
    all_cmd.add_argument("--top-k", "--k", dest="top_k", type=int, default=5)
    all_cmd.add_argument("--backend-url", default=DEFAULT_BACKEND_URL)
    all_cmd.add_argument("--judge-backend", choices=["none", "lmstudio", "gemini"], default="none")
    all_cmd.add_argument("--timeout-s", type=float, default=240.0)
    all_cmd.add_argument("--delay-s", type=float, default=0.0)
    all_cmd.set_defaults(func=command_all)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    summary = args.func(args)
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=_json_default))


if __name__ == "__main__":
    main()
