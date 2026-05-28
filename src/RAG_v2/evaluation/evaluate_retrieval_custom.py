"""Custom RAG Retrieval Evaluation Script

Evaluates RAG retrieval metrics on the user's custom JSON dataset.
Supports:
- Local Classifier routing with dynamic Tier-3 LLM (Gemini) fallback.
- Baseline (no routing - querying all collections).
- Metrics: Hit@K, Recall@K, Precision@K, MRR@K, NDCG@K for K in [3, 5, 7].
- Breakdown analysis by question type and difficulty.
- Saving results as CSV, JSON, and MD report.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import math
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Set up logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("evaluate_retrieval_custom")

# Make project imports work when executed from any cwd
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import Settings
from llm import create_llm
from query.router import QueryRouter
from retrieval.collection_selector import CollectionSelector
from retrieval.service import RetrievalService


# ─── Helper Functions for Matching & Metrics ───────────────────────────────────

def _raw_id(value: Any) -> str:
    text = str(value or "").strip()
    return text.split("/", 1)[-1] if "/" in text else text


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


def _as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.replace(";", ",").split(",") if part.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _should_trigger_tier3(routing: Dict[str, Any]) -> bool:
    """Confidence below this threshold triggers the Tier-3 LLM domain fallback."""
    confidence = routing.get("confidence") or 1.0
    if confidence >= 0.55:
        return False

    probs: Dict[str, float] = routing.get("probabilities") or {}
    if len(probs) >= 2:
        sorted_vals = sorted(probs.values(), reverse=True)
        margin = sorted_vals[0] - sorted_vals[1]
        if margin >= 0.25:
            return False

    return True


def _llm_domain_classify(
    chat: Any,
    question: str,
    current_routing: Dict[str, Any],
) -> Dict[str, Any]:
    """Call Gemini to classify domain when classifier confidence is low."""
    try:
        from query.prompts import DOMAIN_CLASSIFICATION_PROMPT
        prompt = DOMAIN_CLASSIFICATION_PROMPT.format(
            query=question,
            context="(none)",  # single-query eval has no history
        )
        raw = chat.generate(query=prompt, mode="chitchat")
        
        # Strip markdown fences if present
        clean = raw.strip().strip("```json").strip("```").strip()
        parsed = json.loads(clean)

        raw_domains = parsed.get("domains") or []
        llm_confidence_str = parsed.get("confidence", "medium")
        llm_confidence = {"high": 0.85, "medium": 0.65, "low": 0.45}.get(
            llm_confidence_str, 0.65
        )

        valid_domains = [d for d in raw_domains if d in {"ctdt", "quydinh", "kehoach", "stsv"}]
        if not valid_domains:
            return current_routing

        updated = dict(current_routing)
        updated["domains"] = valid_domains
        updated["domain"] = valid_domains[0]
        updated["confidence"] = llm_confidence
        updated["tier3_override"] = True
        return updated
    except Exception as exc:
        logger.warning("Tier-3 LLM domain classification failed: %s", exc)
        return current_routing


def compute_metrics_for_k(retrieved_ids: List[str], relevant_ids: List[str], k: int) -> Dict[str, float]:
    """Calculate evaluation metrics for a specific K cutoff."""
    retrieved_raw = [_raw_id(rid) for rid in retrieved_ids if rid]
    relevant_set = {_raw_id(rid) for rid in relevant_ids if rid}
    
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
    precision = len(set(hits)) / k if k > 0 else 0.0
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
    ndcg = dcg / idcg if idcg else 0.0
    
    return {
        f"hit@{k}": round(hit, 4),
        f"precision@{k}": round(precision, 4),
        f"recall@{k}": round(recall, 4),
        f"mrr@{k}": round(mrr, 4),
        f"ndcg@{k}": round(ndcg, 4),
    }


def compute_all_metrics(retrieved_ids: List[str], relevant_ids: List[str], cutoffs: List[int]) -> Dict[str, float]:
    metrics = {}
    for k in cutoffs:
        metrics.update(compute_metrics_for_k(retrieved_ids, relevant_ids, k))
    return metrics


# ─── Dataset Loading ────────────────────────────────────────────────────────────

def load_dataset(dataset_path: Path) -> List[Dict[str, Any]]:
    if not dataset_path.exists():
        logger.error("Dataset file not found at %s", dataset_path)
        sys.exit(1)
        
    try:
        payload = json.loads(dataset_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or "items" not in payload:
            logger.error("Invalid dataset format. Must contain an 'items' array.")
            sys.exit(1)
        return payload["items"]
    except Exception as exc:
        logger.exception("Failed to read dataset JSON from %s", dataset_path)
        sys.exit(1)


def resolve_dataset_paths(dataset_path: Path) -> List[Path]:
    """Return one or more dataset JSON files from a file or directory path."""
    if dataset_path.is_dir():
        paths = sorted(dataset_path.glob("*.json"))
        if not paths:
            logger.error("No JSON dataset files found in %s", dataset_path)
            sys.exit(1)
        return paths
    return [dataset_path]


def _safe_output_name(path: Path) -> str:
    """Create a filesystem-safe output folder name from a dataset filename."""
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", path.stem).strip("._-")
    return name or "dataset"


def _normalize_router_mode(router_mode: str) -> str:
    if router_mode == "llm":
        logger.warning(
            "--router-mode llm is deprecated for this retrieval eval; "
            "using classifier routing with Tier-3 Gemini fallback instead."
        )
        return "classifier"
    return router_mode


def build_evaluation_runtime(
    router_mode: str,
    top_k: int,
) -> Tuple[Settings, RetrievalService, CollectionSelector, Optional[QueryRouter]]:
    """Initialise shared retrieval/router objects once for a whole eval run."""
    settings = Settings()
    settings.top_k = top_k
    # Retrieval eval mirrors the main flow: local classifier routing with Gemini
    # used only as the Tier-3 fallback. Never instantiate QueryRouter in
    # mode="llm" here because that path expects OPENAI_API_KEY.
    settings.router_mode = "classifier"

    logger.info("Initializing RetrievalService (embedders, stores, reranker) ...")
    service = RetrievalService.from_settings(settings)
    selector = CollectionSelector()
    router = (
        QueryRouter(mode="classifier", embedder=service.bge_embedder)
        if router_mode == "classifier"
        else None
    )
    return settings, service, selector, router


# ─── Main Evaluation Loop ───────────────────────────────────────────────────────

def run_evaluation(
    dataset_items: List[Dict[str, Any]],
    router_mode: str,
    top_k: int,
    output_dir: Path,
    dataset_name: Optional[str] = None,
    settings: Optional[Settings] = None,
    service: Optional[RetrievalService] = None,
    selector: Optional[CollectionSelector] = None,
    router: Optional[QueryRouter] = None,
) -> Dict[str, Any]:
    router_mode = _normalize_router_mode(router_mode)
    if settings is None or service is None or selector is None:
        settings, service, selector, router = build_evaluation_runtime(router_mode, top_k)
    chat_llm: Optional[Any] = None
    
    # K Cutoffs
    cutoffs = [3, 5, 7]
    
    records: List[Dict[str, Any]] = []
    
    total_fallback_triggers = 0
    total_queries = len(dataset_items)
    
    logger.info("=== Running retrieval evaluation on %d queries ===", total_queries)
    
    for idx, item in enumerate(dataset_items, start=1):
        question = item["question"]
        relevant_ids = _as_list(item.get("evidence_chunk_ids", []))
        question_type = item.get("question_type", "simple")
        difficulty = item.get("difficulty", "medium")
        item_id = item.get("id", f"case_{idx:03d}")
        
        logger.info("[%d/%d] ID: %s | Question: '%s'", idx, total_queries, item_id, question[:50])
        
        routing_time_ms = 0.0
        retrieval_time_ms = 0.0
        fallback_triggered = False
        
        # Routing Stage
        t_start = time.perf_counter()
        if router_mode == "none":
            # Baseline: bypass routing, query all collections
            collections = ["stsv", "quydinh", "kehoach", "ctdt"]
            routing_decision = {
                "intent": "rag",
                "domains": collections,
                "domain": "quydinh",
                "confidence": 1.0
            }
        else:
            if router is None:
                raise RuntimeError(f"Unsupported router_mode={router_mode!r}")

            # Run local classifier first.
            routing_decision = router.route(question)
            
            # Tier-3 Gemini Fallback check
            if _should_trigger_tier3(routing_decision):
                logger.info("  ↳ Low confidence margin. Triggering Gemini LLM fallback...")
                if chat_llm is None:
                    logger.info("Initializing Gemini Chat LLM client for routing fallback ...")
                    chat_llm = create_llm(settings)
                routing_decision = _llm_domain_classify(chat_llm, question, routing_decision)
                fallback_triggered = True
                total_fallback_triggers += 1
                
            # Filter targeted collections using CollectionSelector
            domain = routing_decision.get("domain")
            domains = routing_decision.get("domains") or ([domain] if domain else [])
            confidence = float(routing_decision.get("confidence") or 0.0)
            collections = selector.select(domain=domain, domains=domains, confidence=confidence)
            
        routing_time_ms = round((time.perf_counter() - t_start) * 1000, 2)
        
        # Retrieval Stage (Hybrid search + BGE reranking)
        t_start = time.perf_counter()
        # Use ValidityFilter & ReferenceResolver implicitly as defined in pipeline if needed
        # We query the service directly
        retrieved_docs = service.search(
            query=question,
            collections=collections,
            top_k=top_k,
            rerank=True,
        )
        retrieval_time_ms = round((time.perf_counter() - t_start) * 1000, 2)
        
        # Map retrieve document IDs
        retrieved_ids = [_source_id(doc) for doc in retrieved_docs if doc]
        
        # Calculate metrics for the query
        metrics = compute_all_metrics(retrieved_ids, relevant_ids, cutoffs)
        
        # Add latency and routing details
        total_time_ms = round(routing_time_ms + retrieval_time_ms, 2)
        
        record = {
            "id": item_id,
            "question": question,
            "question_type": question_type,
            "difficulty": difficulty,
            "target_collections": ",".join(collections),
            "relevant_chunk_ids": ",".join(relevant_ids),
            "retrieved_chunk_ids": ",".join(retrieved_ids),
            "routing_time_ms": routing_time_ms,
            "retrieval_time_ms": retrieval_time_ms,
            "total_time_ms": total_time_ms,
            "fallback_triggered": fallback_triggered,
            "intent": routing_decision.get("intent", "rag"),
            **metrics
        }
        
        records.append(record)
        
        # Quick log of metrics
        logger.info(
            "  ↳ Hit@3: %.2f | Hit@5: %.2f | Hit@7: %.2f | Latency: %.1fms (Routing: %.1fms, Retrieval: %.1fms)%s",
            metrics["hit@3"], metrics["hit@5"], metrics["hit@7"],
            total_time_ms, routing_time_ms, retrieval_time_ms,
            " [LLM-FALLBACK]" if fallback_triggered else ""
        )

    # 3. Aggregate results and breakdowns
    summary = build_summary_report(records, total_fallback_triggers, top_k, router_mode)
    if dataset_name:
        summary["dataset"] = dataset_name
    
    # 4. Save results to disk
    save_outputs(records, summary, output_dir, router_mode)
    
    return summary


# ─── Aggregators & Reports ──────────────────────────────────────────────────────

def _average_metrics(recs: List[Dict[str, Any]]) -> Dict[str, float]:
    if not recs:
        return {}
    keys = [k for k in recs[0].keys() if "@" in k]
    return {
        key: round(float(sum(r[key] for r in recs) / len(recs)), 4)
        for key in keys
    }


def build_summary_report(
    records: List[Dict[str, Any]],
    fallback_count: int,
    top_k: int,
    router_mode: str,
) -> Dict[str, Any]:
    
    # Global metrics
    overall_metrics = _average_metrics(records)
    avg_latency = round(sum(r["total_time_ms"] for r in records) / len(records), 1)
    avg_routing_latency = round(sum(r["routing_time_ms"] for r in records) / len(records), 1)
    avg_retrieval_latency = round(sum(r["retrieval_time_ms"] for r in records) / len(records), 1)
    
    # Breakdowns by question_type
    type_breakdown = {}
    qtypes = sorted(list(set(r["question_type"] for r in records)))
    for qt in qtypes:
        sub_recs = [r for r in records if r["question_type"] == qt]
        type_breakdown[qt] = {
            "count": len(sub_recs),
            "metrics": _average_metrics(sub_recs),
            "avg_latency_ms": round(sum(r["total_time_ms"] for r in sub_recs) / len(sub_recs), 1)
        }
        
    # Breakdowns by difficulty
    diff_breakdown = {}
    difficulties = sorted(list(set(r["difficulty"] for r in records)))
    for diff in difficulties:
        sub_recs = [r for r in records if r["difficulty"] == diff]
        diff_breakdown[diff] = {
            "count": len(sub_recs),
            "metrics": _average_metrics(sub_recs),
            "avg_latency_ms": round(sum(r["total_time_ms"] for r in sub_recs) / len(sub_recs), 1)
        }
        
    fallback_rate = round(fallback_count / len(records), 4) if len(records) > 0 else 0.0
    
    return {
        "router_mode": router_mode,
        "top_k": top_k,
        "total_queries": len(records),
        "fallback_count": fallback_count,
        "fallback_rate": fallback_rate,
        "overall_avg_latency_ms": avg_latency,
        "overall_avg_routing_ms": avg_routing_latency,
        "overall_avg_retrieval_ms": avg_retrieval_latency,
        "overall_metrics": overall_metrics,
        "by_question_type": type_breakdown,
        "by_difficulty": diff_breakdown,
    }


def save_outputs(
    records: List[Dict[str, Any]],
    summary: Dict[str, Any],
    output_dir: Path,
    router_mode: str,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Save detailed query results CSV
    csv_path = output_dir / f"query_results_{router_mode}.csv"
    if records:
        keys = list(records[0].keys())
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(records)
    logger.info("Wrote detailed results CSV → %s", csv_path)
            
    # 2. Save summary JSON
    json_path = output_dir / f"summary_{router_mode}.json"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Wrote summary JSON → %s", json_path)
    
    # 3. Save Markdown report
    md_path = output_dir / f"report_{router_mode}.md"
    
    lines = [
        f"# RAG Retrieval Quality Evaluation Report ({router_mode.upper()})",
        "",
        f"- **Date**: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- **Router Mode**: `{router_mode}`",
        f"- **Metric Cutoff (Top K)**: `{summary['top_k']}`",
        f"- **Total Queries Evaluated**: `{summary['total_queries']}`",
        "",
        "## Overall Performance",
        "",
        "| Metric | Score (Average) |",
        "| :--- | :--- |",
    ]
    
    for metric, score in summary["overall_metrics"].items():
        lines.append(f"| **{metric}** | `{score * 100:.2f}%` |")
        
    lines.extend([
        f"| **Avg Total Latency** | `{summary['overall_avg_latency_ms']} ms` |",
        f"| **Avg Routing Latency** | `{summary['overall_avg_routing_ms']} ms` |",
        f"| **Avg Retrieval Latency** | `{summary['overall_avg_retrieval_ms']} ms` |",
    ])
    
    if router_mode == "classifier":
        lines.append(f"| **Gemini Fallback Rate** | `{summary['fallback_rate'] * 100:.2f}%` (`{summary['fallback_count']}` queries) |")
        
    lines.extend([
        "",
        "## Breakdown by Question Type",
        "",
        "| Type | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |"
    ])
    
    for qt, info in summary["by_question_type"].items():
        m = info["metrics"]
        lines.append(
            f"| **{qt}** | {info['count']} | `{m['hit@3']*100:.1f}%` | `{m['hit@5']*100:.1f}%` | `{m['hit@7']*100:.1f}%` | "
            f"`{m['recall@5']*100:.1f}%` | `{m['ndcg@5']*100:.1f}%` | `{m['mrr@5']*100:.1f}%` | `{info['avg_latency_ms']} ms` |"
        )
        
    lines.extend([
        "",
        "## Breakdown by Difficulty",
        "",
        "| Difficulty | Count | Hit@3 | Hit@5 | Hit@7 | Recall@5 | NDCG@5 | MRR@5 | Avg Latency |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |"
    ])
    
    for diff, info in summary["by_difficulty"].items():
        m = info["metrics"]
        lines.append(
            f"| **{diff}** | {info['count']} | `{m['hit@3']*100:.1f}%` | `{m['hit@5']*100:.1f}%` | `{m['hit@7']*100:.1f}%` | "
            f"`{m['recall@5']*100:.1f}%` | `{m['ndcg@5']*100:.1f}%` | `{m['mrr@5']*100:.1f}%` | `{info['avg_latency_ms']} ms` |"
        )
        
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info("Wrote beautifully formatted report.md → %s", md_path)
    
    # 4. Print beautiful console report
    print("\n" + "="*60)
    print(f" EVALUATION SUMMARY ({router_mode.upper()} MODE)")
    print("="*60)
    print(f"Total Queries:         {summary['total_queries']}")
    print(f"Avg Latency (Total):   {summary['overall_avg_latency_ms']} ms")
    if router_mode == "classifier":
        print(f"Gemini Fallback Rate:  {summary['fallback_rate'] * 100:.2f}% ({summary['fallback_count']} queries)")
    print("-"*60)
    for metric, score in summary["overall_metrics"].items():
        print(f"{metric:<15} : {score * 100:.2f}%")
    print("="*60 + "\n")


def save_batch_summary(
    summaries: List[Dict[str, Any]],
    output_dir: Path,
    router_mode: str,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    total_queries = sum(int(s.get("total_queries", 0)) for s in summaries)
    total_fallbacks = sum(int(s.get("fallback_count", 0)) for s in summaries)

    metric_names = sorted(
        {
            metric
            for summary in summaries
            for metric in (summary.get("overall_metrics") or {}).keys()
        }
    )
    overall_metrics = {}
    if total_queries:
        overall_metrics = {
            metric: round(
                sum(
                    float((summary.get("overall_metrics") or {}).get(metric, 0.0))
                    * int(summary.get("total_queries", 0))
                    for summary in summaries
                )
                / total_queries,
                4,
            )
            for metric in metric_names
        }

    def _weighted_average(key: str) -> float:
        if not total_queries:
            return 0.0
        return round(
            sum(
                float(summary.get(key, 0.0)) * int(summary.get("total_queries", 0))
                for summary in summaries
            )
            / total_queries,
            1,
        )

    payload = {
        "router_mode": router_mode,
        "dataset_count": len(summaries),
        "total_queries": total_queries,
        "fallback_count": total_fallbacks,
        "fallback_rate": round(total_fallbacks / total_queries, 4)
        if total_queries
        else 0.0,
        "overall_avg_latency_ms": _weighted_average("overall_avg_latency_ms"),
        "overall_avg_routing_ms": _weighted_average("overall_avg_routing_ms"),
        "overall_avg_retrieval_ms": _weighted_average("overall_avg_retrieval_ms"),
        "overall_metrics": overall_metrics,
        "datasets": summaries,
    }

    path = output_dir / f"batch_summary_{router_mode}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Wrote batch summary JSON → %s", path)


# ─── Entry Point ────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate RAG custom retrieval metrics.")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=PROJECT_ROOT / "evaluation" / "data",
        help="Path to an evaluation JSON dataset file or a directory of JSON datasets."
    )
    parser.add_argument(
        "--router-mode",
        choices=["classifier", "llm", "none"],
        default="classifier",
        help=(
            "Query router strategy: classifier (default, with Gemini fallback) "
            "or none. llm is kept as a deprecated alias for classifier fallback."
        )
    )
    parser.add_argument(
        "--top-k", "--k",
        type=int,
        default=7,
        help="Final number of retrieved documents (cutoffs will be computed up to K=7)."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "evaluation" / "results" / "custom_eval",
        help="Directory to save evaluation reports."
    )
    
    args = parser.parse_args()

    router_mode = _normalize_router_mode(args.router_mode)
    dataset_paths = resolve_dataset_paths(args.dataset)
    multi_dataset = len(dataset_paths) > 1 or args.dataset.is_dir()

    settings, service, selector, router = build_evaluation_runtime(
        router_mode=router_mode,
        top_k=args.top_k,
    )

    summaries: List[Dict[str, Any]] = []
    logger.info("Found %d dataset file(s).", len(dataset_paths))
    for dataset_path in dataset_paths:
        logger.info("Loading dataset from %s ...", dataset_path)
        dataset_items = load_dataset(dataset_path)
        dataset_output_dir = (
            args.output_dir / _safe_output_name(dataset_path)
            if multi_dataset
            else args.output_dir
        )

        summary = run_evaluation(
            dataset_items=dataset_items,
            router_mode=router_mode,
            top_k=args.top_k,
            output_dir=dataset_output_dir,
            dataset_name=dataset_path.name,
            settings=settings,
            service=service,
            selector=selector,
            router=router,
        )
        summaries.append(summary)

    if multi_dataset:
        save_batch_summary(summaries, args.output_dir, router_mode)


if __name__ == "__main__":
    main()
