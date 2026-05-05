"""test_retrieval_docs.py — Kiểm tra docs trả về từ retrieval pipeline.

Chạy:
    python test_retrieval_docs.py
    python test_retrieval_docs.py --query "your query" --collection ctdt --major IT1 --top_k 10
    python test_retrieval_docs.py --case all        # chạy toàn bộ test cases
    python test_retrieval_docs.py --case 0          # chạy test case theo index
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import textwrap
from pathlib import Path
from typing import Any, Dict, List, Optional

# Đảm bảo import từ đúng workspace
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import Settings
from retrieval.service import RetrievalService

# ──────────────────────────────────────────────────────────────────────────────
# Test cases mặc định — thêm / sửa tuỳ ý
# ──────────────────────────────────────────────────────────────────────────────
DEFAULT_TEST_CASES: List[Dict[str, Any]] = [
    {
        "name": "CTDT — IT1 chương trình đào tạo",
        "query": "mạng máy tính",
        "collections": ["ctdt"],
        "resolved_major": "IT1",
        "resolved_cohort": None,
        "top_k": 5,
        "rerank": True,
    },
]

# ──────────────────────────────────────────────────────────────────────────────
# Helpers hiển thị
# ──────────────────────────────────────────────────────────────────────────────
_SEP = "─" * 80
_SEP2 = "═" * 80
_TEXT_WIDTH = 120  # ký tự tối đa cho text preview


def _fmt_text(text: str, width: int = _TEXT_WIDTH) -> str:
    """Truncate & indent text for display."""
    snippet = text.strip().replace("\n", " ")
    if len(snippet) > width:
        snippet = snippet[:width] + " …"
    return snippet


def _fmt_meta(meta: Dict[str, Any]) -> str:
    """Format metadata dict as compact key=value pairs."""
    if not meta:
        return "(none)"
    important_keys = [
        "course_code", "course_name", "major_code", "major_name",
        "source", "file_name", "chunk_index", "semester", "year",
        "applicable_major", "document_type",
    ]
    parts = []
    for k in important_keys:
        if k in meta:
            parts.append(f"{k}={meta[k]!r}")
    for k, v in meta.items():
        if k not in important_keys:
            parts.append(f"{k}={v!r}")
    return "  ".join(parts)


def _print_doc(rank: int, doc: Dict[str, Any], show_full_meta: bool = False) -> None:
    collection = doc.get("collection", "?")
    doc_id = doc.get("id", "?")
    score = doc.get("score", 0.0)
    vec_score = doc.get("vector_score")
    kw_score = doc.get("keyword_score")
    rerank_score = doc.get("rerank_score")
    text = doc.get("text", "")
    meta = doc.get("metadata", {})

    score_parts = [f"fusion={score:.4f}"]
    if vec_score is not None:
        score_parts.append(f"vec={vec_score:.4f}")
    if kw_score is not None:
        score_parts.append(f"kw={kw_score:.4f}")
    if rerank_score is not None:
        score_parts.append(f"rerank={rerank_score:.4f}")

    print(f"  [{rank:02d}] [{collection}] {doc_id}")
    print(f"       Score : {' | '.join(score_parts)}")
    print(f"       Text  : {_fmt_text(text)}")
    print(f"       Meta  : {_fmt_meta(meta)}")


def _print_trace(trace: Dict[str, Any]) -> None:
    """Print filter trace from search."""
    filters = trace.get("filters", {})
    fusion = trace.get("fusion_weights", {})
    counts = trace.get("collection_counts", {})

    if fusion:
        print(f"  Fusion weights : vector={fusion.get('vector')} | keyword={fusion.get('keyword')} | reason={fusion.get('reason')}")

    for col, col_counts in counts.items():
        vec_n = col_counts.get("vector", "?")
        kw_n = col_counts.get("keyword", "?")
        f_info = filters.get(col, {})
        applied = f_info.get("applied", False)
        matched = f_info.get("matched_ids", 0)
        fdesc = f_info.get("filter_desc") or "no filter"
        print(f"  [{col}] fetched: vec={vec_n} kw={kw_n} | filter: {'✓' if applied else '✗'} {fdesc} ({matched} IDs)")


# ──────────────────────────────────────────────────────────────────────────────
# Core runner
# ──────────────────────────────────────────────────────────────────────────────

def run_test_case(
    service: RetrievalService,
    *,
    name: str,
    query: str,
    collections: List[str],
    resolved_major: Optional[str] = None,
    resolved_cohort: Optional[str] = None,
    top_k: int = 5,
    rerank: bool = True,
) -> None:
    """Chạy một test case và in kết quả chi tiết."""
    print()
    print(_SEP2)
    print(f"  TEST: {name}")
    print(_SEP2)
    print(f"  Query      : {query!r}")
    print(f"  Collections: {collections}")
    print(f"  Major      : {resolved_major!r}  |  Cohort: {resolved_cohort!r}")
    print(f"  top_k      : {top_k}  |  rerank: {rerank}")
    print(_SEP)

    settings = service.settings
    bge_vec, e5_vec = service.embed_query(query)

    # Raw search (no reranking) with trace
    raw_top_k = max(top_k * 4, 20)
    trace_out: Dict[str, Any] = {}
    raw_results = service.searcher.search(
        query=query,
        bge_m3_query=bge_vec,
        e5_query=e5_vec,
        top_k=raw_top_k,
        vector_top_k=getattr(settings, "vector_top_k", 20),
        keyword_top_k=getattr(settings, "keyword_top_k", 20),
        vector_pool_k=getattr(settings, "vector_pool_k", 15),
        keyword_pool_k=getattr(settings, "keyword_pool_k", 15),
        active_collections=collections,
        resolved_major=resolved_major,
        resolved_cohort=resolved_cohort,
        trace_out=trace_out,
    )

    print("  [TRACE]")
    _print_trace(trace_out)
    print()

    print(f"  [RAW RESULTS — top {min(top_k, len(raw_results))}/{len(raw_results)} docs trước reranking]")
    for i, doc in enumerate(raw_results[:top_k]):
        _print_doc(i + 1, doc)

    # Reranking
    if rerank and service.reranker is not None:
        print()
        print(f"  [RERANKED — top {top_k} docs]")
        try:
            reranked = service.reranker.rerank(
                query=query, documents=raw_results, top_k=top_k
            )
            for i, doc in enumerate(reranked):
                _print_doc(i + 1, doc)
        except Exception as exc:
            print(f"  ⚠ Reranking failed: {exc}")
    elif rerank and service.reranker is None:
        print("  ⚠ Reranker not available — showing raw results only")

    print(_SEP)


# ──────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ──────────────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Test retrieval docs trả về từ query",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Ví dụ:
              python test_retrieval_docs.py
              python test_retrieval_docs.py --case all
              python test_retrieval_docs.py --case 0
              python test_retrieval_docs.py --case 1 3
              python test_retrieval_docs.py --query "môn IT1 học gì" --collection ctdt --major IT1
        """),
    )
    p.add_argument("--query", type=str, default=None, help="Query tuỳ chỉnh (bỏ qua test cases)")
    p.add_argument(
        "--collection", "-c", nargs="+", default=None,
        help="Collection(s) để search (mặc định: ctdt)",
    )
    p.add_argument("--major", type=str, default=None, help="resolved_major (vd: IT1, IT-E7)")
    p.add_argument("--cohort", type=str, default=None, help="resolved_cohort (vd: K67)")
    p.add_argument("--top_k", type=int, default=5, help="Số docs hiển thị (mặc định: 5)")
    p.add_argument("--no-rerank", action="store_true", help="Tắt reranking")
    p.add_argument(
        "--case", nargs="+", default=None,
        help="Index của test case(s) cần chạy, hoặc 'all' để chạy tất cả (mặc định: all)",
    )
    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    print(_SEP2)
    print("  Initialising RetrievalService …")
    print(_SEP2)
    settings = Settings()
    service = RetrievalService.from_settings(settings)
    print("  RetrievalService ready ✓")

    # ── Custom query mode ──────────────────────────────────────────────────
    if args.query:
        collections = args.collection or ["ctdt"]
        run_test_case(
            service,
            name=f"Custom: {args.query[:60]}",
            query=args.query,
            collections=collections,
            resolved_major=args.major,
            resolved_cohort=args.cohort,
            top_k=args.top_k,
            rerank=not args.no_rerank,
        )
        return

    # ── Test cases mode ────────────────────────────────────────────────────
    case_arg = args.case
    if case_arg is None or (len(case_arg) == 1 and case_arg[0].lower() == "all"):
        selected = list(range(len(DEFAULT_TEST_CASES)))
    else:
        selected = []
        for c in case_arg:
            if c.lower() == "all":
                selected = list(range(len(DEFAULT_TEST_CASES)))
                break
            try:
                idx = int(c)
                if 0 <= idx < len(DEFAULT_TEST_CASES):
                    selected.append(idx)
                else:
                    print(f"  ⚠ Case index {idx} out of range (0–{len(DEFAULT_TEST_CASES)-1})")
            except ValueError:
                print(f"  ⚠ Invalid case: {c!r}")

    if not selected:
        print("Không có test case nào được chọn. Dùng --case all hoặc --case <index>.")
        return

    print(f"\n  Sẽ chạy {len(selected)} test case(s): {selected}")

    for idx in selected:
        tc = DEFAULT_TEST_CASES[idx]
        run_test_case(
            service,
            name=f"[{idx}] {tc['name']}",
            query=tc["query"],
            collections=tc.get("collections", ["ctdt"]),
            resolved_major=tc.get("resolved_major"),
            resolved_cohort=tc.get("resolved_cohort"),
            top_k=tc.get("top_k", args.top_k),
            rerank=tc.get("rerank", not args.no_rerank),
        )

    print()
    print(_SEP2)
    print("  Hoàn thành tất cả test cases.")
    print(_SEP2)


if __name__ == "__main__":
    main()
