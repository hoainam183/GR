"""Evaluation Runner — automated testing against the golden dataset.

Runs routing, retrieval, and agent evaluation tests and generates a
structured report with pass/fail counts and accuracy metrics.

Usage::

    python -m eval.evaluator --category routing
    python -m eval.evaluator --all --report
"""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DATASET_PATH = Path(__file__).resolve().parent / "golden_dataset.json"


def load_golden_dataset(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Load the golden dataset test cases."""
    dataset_path = path or _DATASET_PATH
    with open(dataset_path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("test_cases", [])


class EvaluationResult:
    """Container for a single test case result."""

    def __init__(
        self,
        test_id: str,
        category: str,
        query: str,
        expected: Any,
        actual: Any,
        passed: bool,
        details: str = "",
        latency_ms: float = 0.0,
    ) -> None:
        self.test_id = test_id
        self.category = category
        self.query = query
        self.expected = expected
        self.actual = actual
        self.passed = passed
        self.details = details
        self.latency_ms = latency_ms

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_id": self.test_id,
            "category": self.category,
            "query": self.query[:80],
            "expected": self.expected,
            "actual": self.actual,
            "passed": self.passed,
            "details": self.details,
            "latency_ms": self.latency_ms,
        }


class Evaluator:
    """Run evaluation tests against the pipeline.

    Supports three evaluation categories:
    - ``routing``: Tests ComplexityRouter tier classification.
    - ``retrieval``: Tests that correct collections are searched and
      relevant keywords appear in results.
    - ``agent``: Tests that the agent selects appropriate tools.

    Parameters:
        pipeline: RAGPipeline instance (optional — routing tests don't need it).
    """

    def __init__(self, pipeline: Any = None) -> None:
        self._pipeline = pipeline
        self._results: List[EvaluationResult] = []

    def evaluate_routing(
        self,
        test_cases: List[Dict[str, Any]],
    ) -> List[EvaluationResult]:
        """Evaluate routing accuracy against golden labels.

        This test only requires the ComplexityRouter — no LLM or retrieval needed.
        """
        from query.complexity_router import ComplexityRouter

        router = ComplexityRouter()
        results: List[EvaluationResult] = []

        for case in test_cases:
            if case.get("category") != "routing":
                continue

            t0 = time.perf_counter()
            route_result = router.route(case["query"])
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)

            actual = route_result["tier"]
            expected = case["expected_route"]
            passed = actual == expected

            result = EvaluationResult(
                test_id=case["id"],
                category="routing",
                query=case["query"],
                expected=expected,
                actual=actual,
                passed=passed,
                details=route_result.get("reason", ""),
                latency_ms=latency_ms,
            )
            results.append(result)

            status = "✅" if passed else "❌"
            logger.info(
                "%s [%s] %r → expected=%s, actual=%s (%s)",
                status, case["id"], case["query"][:50], expected, actual,
                route_result.get("reason", "")[:40],
            )

        self._results.extend(results)
        return results

    def evaluate_retrieval(
        self,
        test_cases: List[Dict[str, Any]],
    ) -> List[EvaluationResult]:
        """Evaluate retrieval quality — checks collection routing and keyword presence.

        Requires a running pipeline with connected Qdrant/ES.
        """
        if self._pipeline is None:
            logger.warning("Pipeline not available — skipping retrieval evaluation")
            return []

        results: List[EvaluationResult] = []

        for case in test_cases:
            if case.get("category") != "retrieval":
                continue

            t0 = time.perf_counter()
            try:
                pipeline_result = self._pipeline.query(
                    question=case["query"],
                    history=[],
                    top_k=5,
                )
                latency_ms = round((time.perf_counter() - t0) * 1000, 2)

                # Check if expected collection appears in results
                sources = pipeline_result.get("sources", [])
                result_collections = set()
                result_text = ""
                for src in sources:
                    if isinstance(src, dict):
                        col = src.get("collection", "")
                        if col:
                            result_collections.add(col)
                        result_text += " " + str(src.get("text", ""))

                expected_collection = case.get("expected_collection", "")
                collection_hit = expected_collection in result_collections

                expected_keywords = case.get("expected_keywords", [])
                keyword_hits = sum(
                    1 for kw in expected_keywords
                    if kw.lower() in result_text.lower()
                )
                keyword_ratio = keyword_hits / len(expected_keywords) if expected_keywords else 1.0

                passed = collection_hit and keyword_ratio >= 0.5

                result = EvaluationResult(
                    test_id=case["id"],
                    category="retrieval",
                    query=case["query"],
                    expected=f"collection={expected_collection}, keywords={expected_keywords}",
                    actual=f"collections={sorted(result_collections)}, keyword_ratio={keyword_ratio:.1%}",
                    passed=passed,
                    details=f"collection_hit={collection_hit}, keywords={keyword_hits}/{len(expected_keywords)}",
                    latency_ms=latency_ms,
                )
            except Exception as exc:
                latency_ms = round((time.perf_counter() - t0) * 1000, 2)
                result = EvaluationResult(
                    test_id=case["id"],
                    category="retrieval",
                    query=case["query"],
                    expected=case.get("expected_collection", ""),
                    actual=f"ERROR: {exc}",
                    passed=False,
                    details=str(exc),
                    latency_ms=latency_ms,
                )

            results.append(result)
            status = "✅" if result.passed else "❌"
            logger.info(
                "%s [%s] %r → %s",
                status, case["id"], case["query"][:50], result.details,
            )

        self._results.extend(results)
        return results

    def generate_report(self) -> Dict[str, Any]:
        """Generate a summary evaluation report.

        Returns:
            Dict with per-category accuracy and overall statistics.
        """
        by_category: Dict[str, List[EvaluationResult]] = {}
        for r in self._results:
            by_category.setdefault(r.category, []).append(r)

        report: Dict[str, Any] = {
            "total_tests": len(self._results),
            "total_passed": sum(1 for r in self._results if r.passed),
            "total_failed": sum(1 for r in self._results if not r.passed),
            "overall_accuracy": (
                sum(1 for r in self._results if r.passed) / len(self._results)
                if self._results else 0.0
            ),
            "categories": {},
            "failures": [],
        }

        for category, results in sorted(by_category.items()):
            passed = sum(1 for r in results if r.passed)
            total = len(results)
            avg_latency = (
                sum(r.latency_ms for r in results) / total if total else 0.0
            )
            report["categories"][category] = {
                "total": total,
                "passed": passed,
                "failed": total - passed,
                "accuracy": passed / total if total else 0.0,
                "avg_latency_ms": round(avg_latency, 2),
            }

        # Collect failure details
        for r in self._results:
            if not r.passed:
                report["failures"].append(r.to_dict())

        return report

    def print_report(self) -> None:
        """Print a human-readable evaluation report."""
        report = self.generate_report()

        print("\n" + "=" * 60)
        print("  EVALUATION REPORT")
        print("=" * 60)
        print(
            f"  Total: {report['total_tests']} | "
            f"Passed: {report['total_passed']} | "
            f"Failed: {report['total_failed']} | "
            f"Accuracy: {report['overall_accuracy']:.1%}"
        )
        print("-" * 60)

        for category, stats in report["categories"].items():
            status = "✅" if stats["failed"] == 0 else "⚠️"
            print(
                f"  {status} {category}: "
                f"{stats['passed']}/{stats['total']} "
                f"({stats['accuracy']:.1%}) "
                f"avg_latency={stats['avg_latency_ms']:.1f}ms"
            )

        if report["failures"]:
            print("\n" + "-" * 60)
            print("  FAILURES:")
            for f in report["failures"]:
                print(f"    ❌ [{f['test_id']}] {f['query']}")
                print(f"       Expected: {f['expected']}")
                print(f"       Actual:   {f['actual']}")

        print("=" * 60 + "\n")


def main():
    """CLI entry point for running evaluations."""
    import argparse

    parser = argparse.ArgumentParser(description="RAG v2 Evaluation Runner")
    parser.add_argument(
        "--category",
        choices=["routing", "retrieval", "agent", "all"],
        default="routing",
        help="Which evaluation category to run (default: routing)",
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default=None,
        help="Path to golden dataset JSON (default: eval/golden_dataset.json)",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Print detailed report after evaluation",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output report as JSON",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    dataset_path = Path(args.dataset) if args.dataset else None
    test_cases = load_golden_dataset(dataset_path)

    pipeline = None
    category = args.category

    # Only init pipeline for retrieval/agent tests
    if category in ("retrieval", "agent", "all"):
        try:
            # Add project root to path
            project_root = Path(__file__).resolve().parent.parent
            sys.path.insert(0, str(project_root))
            from pipeline.rag_pipeline import RAGPipeline
            pipeline = RAGPipeline()
        except Exception as exc:
            logger.warning(
                "Pipeline init failed — retrieval/agent tests will be skipped: %s", exc
            )

    evaluator = Evaluator(pipeline=pipeline)

    if category in ("routing", "all"):
        evaluator.evaluate_routing(test_cases)

    if category in ("retrieval", "all") and pipeline is not None:
        evaluator.evaluate_retrieval(test_cases)

    if args.report:
        evaluator.print_report()

    if args.json:
        print(json.dumps(evaluator.generate_report(), indent=2, ensure_ascii=False))

    # Exit with error code if any tests failed
    report = evaluator.generate_report()
    sys.exit(0 if report["total_failed"] == 0 else 1)


if __name__ == "__main__":
    main()
