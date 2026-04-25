"""Evaluate RAG v2 baseline vs LangGraph Agent on curated question sets.

Usage:
    python eval/evaluate.py
"""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config.settings import Settings
from pipeline.rag_pipeline import RAGPipeline

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

QUESTION_PATHS: dict[str, Path] = {
    "simple": ROOT_DIR / "eval" / "question_sets" / "simple_questions.json",
    "complex": ROOT_DIR / "eval" / "question_sets" / "complex_questions.json",
}
DEFAULT_OUTPUT_PATH = ROOT_DIR / "eval" / "results.json"


def load_questions(path: str | Path) -> list[dict[str, Any]]:
    """Load question list from a JSON file."""
    question_path = Path(path)
    with question_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise ValueError(f"Question set must be a list: {question_path}")
    return data


def evaluate_answer(answer: str, expected_keywords: list[str]) -> dict[str, Any]:
    """Score an answer by keyword presence and basic content checks."""
    if not answer:
        return {
            "keyword_score": 0.0,
            "has_content": False,
            "answer_length": 0,
        }

    answer_lower = answer.lower()
    found = sum(1 for keyword in expected_keywords if keyword.lower() in answer_lower)
    denominator = len(expected_keywords) if expected_keywords else 1
    return {
        "keyword_score": found / denominator,
        "has_content": len(answer.strip()) > 50,
        "answer_length": len(answer),
    }


def run_evaluation(
    pipeline: Optional[RAGPipeline] = None,
    question_paths: Optional[dict[str, Path]] = None,
    output_path: Optional[str | Path] = None,
) -> dict[str, list[dict[str, Any]]]:
    """Run the evaluation suite and save a JSON report."""
    if pipeline is None:
        pipeline = RAGPipeline(Settings())

    paths = question_paths or QUESTION_PATHS
    results: dict[str, list[dict[str, Any]]] = {"simple": [], "complex": []}

    for category in ("simple", "complex"):
        questions = load_questions(paths[category])
        print(f"\n{'=' * 50}")
        print(f"Evaluating {category.upper()} ({len(questions)} questions)")
        print("=" * 50)

        for question_data in questions:
            query = str(question_data.get("query", "")).strip()
            if not query:
                continue

            expected_keywords = list(question_data.get("expected_keywords", []))
            expected_tools = list(question_data.get("expected_tools", []))
            expected_route = question_data.get("expected_route")

            # Baseline: classic RAG v2.
            baseline_start = time.perf_counter()
            rag_error: str | None = None
            try:
                rag_result = pipeline.query(query)
            except Exception as exc:
                rag_error = str(exc)
                logger.warning("RAG baseline failed for %s: %s", question_data.get("id"), exc)
                rag_result = {
                    "answer": "",
                    "mode": "rag_v2_error",
                }
            rag_latency = time.perf_counter() - baseline_start
            rag_eval = evaluate_answer(rag_result.get("answer", ""), expected_keywords)

            # Candidate: smart route (agent for complex queries).
            agent_start = time.perf_counter()
            agent_error: str | None = None
            try:
                agent_result = pipeline.query_v3(query)
            except Exception as exc:
                agent_error = str(exc)
                logger.warning("Agent route failed for %s: %s", question_data.get("id"), exc)
                agent_result = {
                    "answer": "",
                    "mode": "agent_error",
                    "route": None,
                    "tools_used": [],
                    "iterations": 0,
                }
            agent_latency = time.perf_counter() - agent_start
            agent_eval = evaluate_answer(agent_result.get("answer", ""), expected_keywords)

            used_tools = list(agent_result.get("tools_used", []))
            tool_correct: bool | None = None
            if expected_tools:
                tool_correct = any(tool in used_tools for tool in expected_tools)

            row = {
                "id": question_data.get("id", ""),
                "query": query[:80],
                "expected_route": expected_route,
                "actual_route": agent_result.get("route"),
                "route_match": expected_route == agent_result.get("route"),
                "rag_keyword_score": rag_eval["keyword_score"],
                "agent_keyword_score": agent_eval["keyword_score"],
                "rag_latency": round(rag_latency, 2),
                "agent_latency": round(agent_latency, 2),
                "agent_iterations": int(agent_result.get("iterations", 0) or 0),
                "expected_tools": expected_tools,
                "tools_used": used_tools,
                "tool_correct": tool_correct,
                "agent_mode": agent_result.get("mode"),
                "rag_error": rag_error,
                "agent_error": agent_error,
            }
            results[category].append(row)

            if agent_eval["keyword_score"] > rag_eval["keyword_score"]:
                winner = "AGENT"
            elif agent_eval["keyword_score"] < rag_eval["keyword_score"]:
                winner = "RAG"
            else:
                winner = "TIE"

            print(
                f"[{row['id']}] {winner} | "
                f"RAG: {rag_eval['keyword_score']:.1f} ({rag_latency:.1f}s) | "
                f"Agent: {agent_eval['keyword_score']:.1f} ({agent_latency:.1f}s)"
            )

    print(f"\n{'=' * 50}\nSUMMARY\n{'=' * 50}")
    for category, rows in results.items():
        if not rows:
            continue

        avg_rag = sum(row["rag_keyword_score"] for row in rows) / len(rows)
        avg_agent = sum(row["agent_keyword_score"] for row in rows) / len(rows)
        avg_rag_latency = sum(row["rag_latency"] for row in rows) / len(rows)
        avg_agent_latency = sum(row["agent_latency"] for row in rows) / len(rows)
        route_accuracy = sum(1 for row in rows if row.get("route_match")) / len(rows)

        print(f"\n[{category.upper()}]")
        print(f"  Keyword score - RAG: {avg_rag:.2f} | Agent: {avg_agent:.2f}")
        print(f"  Latency avg   - RAG: {avg_rag_latency:.1f}s | Agent: {avg_agent_latency:.1f}s")
        print(f"  Route accuracy: {route_accuracy:.0%}")

        if category == "complex":
            tool_rows = [row for row in rows if row.get("tool_correct") is not None]
            if tool_rows:
                tool_accuracy = sum(1 for row in tool_rows if row["tool_correct"]) / len(tool_rows)
                print(f"  Tool selection accuracy: {tool_accuracy:.0%}")

    target_path = Path(output_path) if output_path else DEFAULT_OUTPUT_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with target_path.open("w", encoding="utf-8") as file:
        json.dump(results, file, ensure_ascii=False, indent=2)

    print(f"\nResults saved to {target_path}")
    return results


if __name__ == "__main__":
    run_evaluation()
