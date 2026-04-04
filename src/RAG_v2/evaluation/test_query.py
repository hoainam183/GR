"""Kiểm tra output LLM cho một mảng query.

Chạy:
    python evaluation/test_query.py

Sửa CONFIG bên dưới để thay đổi danh sách query và các tuỳ chọn.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).resolve().parent.parent  # …/RAG_v2
sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv

load_dotenv(_ROOT / ".env")

from pipeline.rag_pipeline import RAGPipeline, _format_context  # noqa: E402
from llm.self_eval import SelfEvaluator  # noqa: E402

# ---------------------------------------------------------------------------
# Config — chỉnh tham số tại đây, không dùng CLI
# ---------------------------------------------------------------------------
CONFIG = {
    # Danh sách query cần kiểm tra
    "queries": [
        "GPA tối thiểu để được xét học bổng khuyến khích học tập loại A là bao nhiêu?",
        "Đầu ra ngoại ngữ của K70 là gì?",
        "Điều kiện tốt nghiệp ngành CNTT Việt Nhật",
    ],
    # True  → bật streaming token-by-token
    "stream": False,
    # True  → chạy self-evaluation sau mỗi câu trả lời
    "run_eval": False,
    # Số giây chờ giữa các query (tránh rate-limit)
    "delay_s": 1.0,
}

logging.basicConfig(
    level=logging.WARNING,  # tắt log INFO để output gọn hơn
    format="%(levelname)s  %(name)s — %(message)s",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SEP = "─" * 70


def _print_sources(sources: list) -> None:
    if not sources:
        print("  (Không có nguồn tài liệu nào được truy xuất)")
        return
    for i, doc in enumerate(sources, 1):
        meta = doc.get("metadata", {})
        title = (
            meta.get("title")
            or meta.get("source")
            or meta.get("file_name")
            or "Tài liệu"
        )
        score = doc.get("score") or doc.get("rerank_score") or ""
        score_str = f"  [score={score:.4f}]" if isinstance(score, float) else ""
        snippet = doc.get("text", "")[:200].replace("\n", " ")
        print(f"  [{i}] {title}{score_str}")
        print(f"       {snippet}…")


def _print_self_eval(result: dict) -> None:
    verdict = "✓ PASS" if result.get("pass") else "✗ FAIL"
    print(f"\n  Kết quả   : {verdict}")
    print(f"  Relevance     : {result.get('relevance', '-')}")
    print(f"  Faithfulness  : {result.get('faithfulness', '-')}")
    print(f"  Completeness  : {result.get('completeness', '-')}")
    print(f"  Lý do         : {result.get('reason', '-')}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def run(query: str, use_stream: bool, run_eval: bool) -> None:
    print(f"\n{_SEP}")
    print(f"  QUERY: {query}")
    print(_SEP)

    print("\n[1/3] Khởi tạo pipeline …")
    pipeline = RAGPipeline()

    # ── Generate
    print("[2/3] Đang xử lý …\n")
    t0 = time.perf_counter()

    if use_stream:
        print("── ANSWER (stream) ".ljust(70, "─"))
        sources = []
        chunks = []
        for chunk in pipeline.query_stream(query):
            print(chunk, end="", flush=True)
            chunks.append(chunk)
        print()
        latency_ms = round((time.perf_counter() - t0) * 1000)
        generated = "".join(chunks)
        sources = getattr(pipeline, "last_sources", [])
        intent = getattr(pipeline, "last_intent", "rag")
    else:
        result = pipeline.query(query)
        latency_ms = round((time.perf_counter() - t0) * 1000)
        generated = result["answer"]
        sources = result["sources"]
        intent = result["intent"]

        print(f"── ANSWER  [intent={intent}] ".ljust(70, "─"))
        print(generated)

    print(f"\n  ⏱  {latency_ms} ms  |  {len(sources)} nguồn tài liệu")

    # ── Sources
    print(f"\n── SOURCES ".ljust(70, "─"))
    _print_sources(sources)

    # ── Self-eval
    if run_eval:
        print(f"\n[3/3] Chạy self-evaluation …")
        evaluator = SelfEvaluator()
        context_str = _format_context(sources) if sources else "(no context)"
        eval_result = evaluator.evaluate(
            query=query,
            context=context_str,
            response=generated,
        )
        print(f"\n── SELF-EVALUATION ".ljust(70, "─"))
        _print_self_eval(eval_result)
    else:
        print("\n  (Bỏ qua self-evaluation. Dùng --eval để bật)")

    print(f"\n{_SEP}\n")


def main() -> None:
    queries = CONFIG["queries"]
    use_stream = CONFIG["stream"]
    run_eval = CONFIG["run_eval"]
    delay_s = CONFIG["delay_s"]

    if not queries:
        print("CONFIG['queries'] trống. Thêm câu hỏi vào mảng rồi chạy lại.")
        sys.exit(0)

    print(f"\nSẽ kiểm tra {len(queries)} query.")
    print(f"stream={use_stream}  |  self-eval={run_eval}  |  delay={delay_s}s")

    for i, query in enumerate(queries):
        run(query=query, use_stream=use_stream, run_eval=run_eval)
        if delay_s > 0 and i < len(queries) - 1:
            time.sleep(delay_s)


if __name__ == "__main__":
    main()
