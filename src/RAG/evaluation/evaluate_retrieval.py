"""
Retrieval Evaluation Script
Đánh giá hiệu suất retrieval của RAG system bằng cách so sánh với ground truth dataset.

Metrics:
- Precision@K: Số documents relevant / K documents retrieved
- Recall@K: Số documents relevant retrieved / Tổng documents relevant
- Hit Rate@K: % câu hỏi có ít nhất 1 relevant document trong top-K
- MRR (Mean Reciprocal Rank): Trung bình 1/rank của relevant document đầu tiên

Usage:
    python evaluate_retrieval.py
    python evaluate_retrieval.py --top-k 10
    python evaluate_retrieval.py --limit 10  # Test với 10 samples
"""

import csv
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Optional tqdm for progress bar
try:
    from tqdm import tqdm

    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

    def tqdm(iterable, **kwargs):
        """Fallback when tqdm is not installed"""
        desc = kwargs.get("desc", "")
        if desc:
            print(f"  {desc}...")
        return iterable


# Add parent paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from embedding.embedding import create_pipeline


@dataclass
class EvaluationSample:
    """Single evaluation sample from dataset"""

    question: str
    ground_truth_answer: str
    expected_source: str
    question_type: str
    difficulty: str
    relevant_context: str


@dataclass
class RetrievalEvalResult:
    """Result for single retrieval evaluation"""

    question: str
    expected_source: str
    retrieved_sources: List[str]
    retrieved_scores: List[float]

    # Metrics
    hit: bool  # Expected source in top-K
    rank: int  # Position of expected source (0 if not found)
    precision: float  # 1/K if hit, else 0 (single relevant doc assumption)
    recall: float  # 1 if hit, else 0 (single relevant doc assumption)
    reciprocal_rank: float  # 1/rank if found, else 0

    # Metadata
    question_type: str
    difficulty: str


@dataclass
class RetrievalEvalReport:
    """Overall retrieval evaluation report"""

    total_samples: int
    top_k: int

    # Aggregated metrics
    precision_at_k: float
    recall_at_k: float
    hit_rate_at_k: float
    mrr: float  # Mean Reciprocal Rank

    # By question type
    metrics_by_type: Dict[str, Dict[str, float]] = field(default_factory=dict)

    # By difficulty
    metrics_by_difficulty: Dict[str, Dict[str, float]] = field(
        default_factory=dict
    )

    # Individual results
    results: List[RetrievalEvalResult] = field(default_factory=list)


class RetrievalEvaluator:
    """Retrieval System Evaluator using local pipeline"""

    def __init__(self, top_k: int = 5, verbose: bool = True):
        self.top_k = top_k
        self.verbose = verbose
        self.pipeline = None

    def load_pipeline(self):
        """Load embedding pipeline and vector store"""
        if self.verbose:
            print("📦 Loading embedding pipeline...")

        self.pipeline = create_pipeline()

        try:
            self.pipeline.load_vector_store()
            stats = self.pipeline.vector_store.get_statistics()

            if self.verbose:
                print(f"✅ Loaded vector store")
                print(f"   Total documents: {stats['total_documents']}")
                print(f"   Source files: {list(stats['source_files'].keys())}")

        except FileNotFoundError:
            raise RuntimeError(
                "❌ Vector store not found! Please run embedding first:\n"
                "   python run_embedding.py"
            )

    def load_dataset(self, csv_path: str) -> List[EvaluationSample]:
        """Load evaluation dataset from CSV"""
        samples = []

        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                sample = EvaluationSample(
                    question=row["question"],
                    ground_truth_answer=row["answer"],
                    expected_source=row["document_source"],
                    question_type=row.get("question_type", "unknown"),
                    difficulty=row.get("difficulty", "unknown"),
                    relevant_context=row.get("relevant_context", ""),
                )
                samples.append(sample)

        return samples

    def normalize_source_name(self, source: str) -> str:
        """Normalize source file name for comparison"""
        source = source.lower()
        source = source.replace("\\", "/").split("/")[-1]  # Get filename
        source = source.replace("_converted", "").replace(".md", "")
        source = source.strip()
        return source

    def check_source_match(
        self, expected: str, retrieved_list: List[str]
    ) -> Tuple[bool, int]:
        """
        Check if expected source is in retrieved list

        Returns:
            hit: Whether expected source was found
            rank: Position in list (1-indexed), 0 if not found
        """
        expected_norm = self.normalize_source_name(expected)

        for i, retrieved in enumerate(retrieved_list):
            retrieved_norm = self.normalize_source_name(retrieved)

            # Exact match
            if expected_norm == retrieved_norm:
                return True, i + 1

            # Partial match (expected is substring or vice versa)
            if (
                expected_norm in retrieved_norm
                or retrieved_norm in expected_norm
            ):
                return True, i + 1

            # Handle variations (e.g., "QĐ" vs "QD", "Học bổng" variations)
            expected_simple = (
                expected_norm.replace("đ", "d")
                .replace("ă", "a")
                .replace("â", "a")
            )
            retrieved_simple = (
                retrieved_norm.replace("đ", "d")
                .replace("ă", "a")
                .replace("â", "a")
            )

            if (
                expected_simple in retrieved_simple
                or retrieved_simple in expected_simple
            ):
                return True, i + 1

        return False, 0

    def retrieve(self, query: str) -> Tuple[List[str], List[float]]:
        """
        Retrieve documents for a query

        Returns:
            sources: List of source file names
            scores: List of similarity scores
        """
        if self.pipeline is None:
            raise RuntimeError(
                "Pipeline not loaded. Call load_pipeline() first."
            )

        results = self.pipeline.search(query, top_k=self.top_k)

        sources = []
        scores = []

        for result in results:
            source = result.metadata.get("source_file", "unknown")
            sources.append(source)
            scores.append(result.score)

        return sources, scores

    def evaluate_single(self, sample: EvaluationSample) -> RetrievalEvalResult:
        """Evaluate single sample"""
        # Retrieve documents
        sources, scores = self.retrieve(sample.question)

        # Check if expected source is in retrieved
        hit, rank = self.check_source_match(sample.expected_source, sources)

        # Calculate metrics
        # Precision@K: relevant_retrieved / K (với 1 relevant doc, = 1/K nếu hit)
        precision = 1.0 / self.top_k if hit else 0.0

        # Recall@K: relevant_retrieved / total_relevant (với 1 relevant doc, = 1 nếu hit)
        recall = 1.0 if hit else 0.0

        # Reciprocal Rank: 1/rank nếu found
        rr = 1.0 / rank if rank > 0 else 0.0

        return RetrievalEvalResult(
            question=sample.question,
            expected_source=sample.expected_source,
            retrieved_sources=sources,
            retrieved_scores=scores,
            hit=hit,
            rank=rank,
            precision=precision,
            recall=recall,
            reciprocal_rank=rr,
            question_type=sample.question_type,
            difficulty=sample.difficulty,
        )

    def evaluate(self, samples: List[EvaluationSample]) -> RetrievalEvalReport:
        """Run full evaluation on all samples"""
        results = []

        iterator = tqdm(samples, desc="Evaluating") if self.verbose else samples

        for sample in iterator:
            result = self.evaluate_single(sample)
            results.append(result)

        # Aggregate metrics
        n = len(results)

        avg_precision = sum(r.precision for r in results) / n
        avg_recall = sum(r.recall for r in results) / n
        hit_rate = sum(1 for r in results if r.hit) / n
        mrr = sum(r.reciprocal_rank for r in results) / n

        # Metrics by question type
        metrics_by_type = self._aggregate_by_field(results, "question_type")

        # Metrics by difficulty
        metrics_by_difficulty = self._aggregate_by_field(results, "difficulty")

        return RetrievalEvalReport(
            total_samples=n,
            top_k=self.top_k,
            precision_at_k=avg_precision,
            recall_at_k=avg_recall,
            hit_rate_at_k=hit_rate,
            mrr=mrr,
            metrics_by_type=metrics_by_type,
            metrics_by_difficulty=metrics_by_difficulty,
            results=results,
        )

    def _aggregate_by_field(
        self, results: List[RetrievalEvalResult], field: str
    ) -> Dict[str, Dict[str, float]]:
        """Aggregate metrics by a specific field"""
        groups: Dict[str, List[RetrievalEvalResult]] = {}

        for r in results:
            key = getattr(r, field)
            if key not in groups:
                groups[key] = []
            groups[key].append(r)

        aggregated = {}
        for key, group in groups.items():
            n = len(group)
            aggregated[key] = {
                "count": n,
                "precision": sum(r.precision for r in group) / n,
                "recall": sum(r.recall for r in group) / n,
                "hit_rate": sum(1 for r in group if r.hit) / n,
                "mrr": sum(r.reciprocal_rank for r in group) / n,
            }

        return aggregated


def print_report(report: RetrievalEvalReport):
    """Print formatted evaluation report"""
    print("\n" + "=" * 70)
    print("📊 RETRIEVAL EVALUATION REPORT")
    print("=" * 70)

    print(
        f"\n📈 OVERALL METRICS (n={report.total_samples}, top_k={report.top_k})"
    )
    print("-" * 50)

    print(f"\n   • Hit Rate@{report.top_k}:    {report.hit_rate_at_k:.2%}")
    print(f"   • MRR:             {report.mrr:.4f}")
    print(f"   • Precision@{report.top_k}:   {report.precision_at_k:.4f}")
    print(f"   • Recall@{report.top_k}:      {report.recall_at_k:.4f}")

    # By question type
    print(f"\n📊 METRICS BY QUESTION TYPE")
    print("-" * 50)
    for qtype, metrics in sorted(report.metrics_by_type.items()):
        print(f"\n   {qtype} (n={metrics['count']}):")
        print(
            f"      Hit Rate: {metrics['hit_rate']:.2%} | MRR: {metrics['mrr']:.4f} | "
            f"P@{report.top_k}: {metrics['precision']:.4f} | R@{report.top_k}: {metrics['recall']:.4f}"
        )

    # By difficulty
    print(f"\n📊 METRICS BY DIFFICULTY")
    print("-" * 50)

    # Sort by difficulty level
    difficulty_order = {"easy": 0, "medium": 1, "hard": 2}
    sorted_difficulties = sorted(
        report.metrics_by_difficulty.items(),
        key=lambda x: difficulty_order.get(x[0], 99),
    )

    for diff, metrics in sorted_difficulties:
        print(f"\n   {diff} (n={metrics['count']}):")
        print(
            f"      Hit Rate: {metrics['hit_rate']:.2%} | MRR: {metrics['mrr']:.4f} | "
            f"P@{report.top_k}: {metrics['precision']:.4f} | R@{report.top_k}: {metrics['recall']:.4f}"
        )

    # Failed retrievals summary
    failed = [r for r in report.results if not r.hit]
    if failed:
        print(f"\n❌ FAILED RETRIEVALS ({len(failed)}/{report.total_samples})")
        print("-" * 50)
        for r in failed[:5]:  # Show first 5
            print(f"\n   Q: {r.question[:60]}...")
            print(f"   Expected: {r.expected_source}")
            print(f"   Retrieved: {r.retrieved_sources[:3]}")

        if len(failed) > 5:
            print(f"\n   ... and {len(failed) - 5} more failed cases")

    print("\n" + "=" * 70)


def save_results_csv(report: RetrievalEvalReport, output_path: str):
    """Save detailed results to CSV"""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)

        # Header
        writer.writerow(
            [
                "question",
                "expected_source",
                "retrieved_sources",
                "retrieved_scores",
                "hit",
                "rank",
                "precision",
                "recall",
                "reciprocal_rank",
                "question_type",
                "difficulty",
            ]
        )

        # Data rows
        for r in report.results:
            writer.writerow(
                [
                    r.question,
                    r.expected_source,
                    "|".join(r.retrieved_sources),
                    "|".join(f"{s:.4f}" for s in r.retrieved_scores),
                    r.hit,
                    r.rank,
                    f"{r.precision:.4f}",
                    f"{r.recall:.4f}",
                    f"{r.reciprocal_rank:.4f}",
                    r.question_type,
                    r.difficulty,
                ]
            )

    print(f"\n💾 Detailed results saved to: {path}")


def save_summary_csv(report: RetrievalEvalReport, output_path: str):
    """Save summary metrics to CSV"""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)

        # Overall metrics
        writer.writerow(["OVERALL METRICS"])
        writer.writerow(["Metric", "Value"])
        writer.writerow(["Total Samples", report.total_samples])
        writer.writerow(["Top K", report.top_k])
        writer.writerow(
            [f"Hit Rate@{report.top_k}", f"{report.hit_rate_at_k:.4f}"]
        )
        writer.writerow(["MRR", f"{report.mrr:.4f}"])
        writer.writerow(
            [f"Precision@{report.top_k}", f"{report.precision_at_k:.4f}"]
        )
        writer.writerow([f"Recall@{report.top_k}", f"{report.recall_at_k:.4f}"])

        writer.writerow([])

        # By question type
        writer.writerow(["METRICS BY QUESTION TYPE"])
        writer.writerow(
            ["Type", "Count", "Hit Rate", "MRR", "Precision", "Recall"]
        )
        for qtype, metrics in sorted(report.metrics_by_type.items()):
            writer.writerow(
                [
                    qtype,
                    metrics["count"],
                    f"{metrics['hit_rate']:.4f}",
                    f"{metrics['mrr']:.4f}",
                    f"{metrics['precision']:.4f}",
                    f"{metrics['recall']:.4f}",
                ]
            )

        writer.writerow([])

        # By difficulty
        writer.writerow(["METRICS BY DIFFICULTY"])
        writer.writerow(
            ["Difficulty", "Count", "Hit Rate", "MRR", "Precision", "Recall"]
        )
        for diff, metrics in sorted(report.metrics_by_difficulty.items()):
            writer.writerow(
                [
                    diff,
                    metrics["count"],
                    f"{metrics['hit_rate']:.4f}",
                    f"{metrics['mrr']:.4f}",
                    f"{metrics['precision']:.4f}",
                    f"{metrics['recall']:.4f}",
                ]
            )

    print(f"💾 Summary saved to: {path}")


def run_evaluation(
    dataset_path: str = None,
    top_k: int = 5,
    limit: int = None,
    output_dir: str = None,
):
    """
    Run retrieval evaluation

    Args:
        dataset_path: Path to evaluation CSV
        top_k: Number of documents to retrieve
        limit: Limit number of samples (for testing)
        output_dir: Directory to save results
    """
    # Default paths
    if dataset_path is None:
        dataset_path = (
            Path(__file__).parent.parent.parent.parent
            / "rag_evaluation_dataset.csv"
        )

    if output_dir is None:
        output_dir = Path(__file__).parent / "retrieval_results"

    print("🚀 Retrieval Evaluation Script")
    print("=" * 50)
    print(f"   Dataset:  {dataset_path}")
    print(f"   Top K:    {top_k}")
    print("=" * 50)

    # Initialize evaluator
    evaluator = RetrievalEvaluator(top_k=top_k, verbose=True)

    # Load pipeline
    evaluator.load_pipeline()

    # Load samples
    samples = evaluator.load_dataset(str(dataset_path))
    print(f"\n📚 Loaded {len(samples)} samples")

    if limit:
        samples = samples[:limit]
        print(f"   Limited to: {limit} samples")

    # Run evaluation
    print("\n🔍 Running evaluation...")
    report = evaluator.evaluate(samples)

    # Print results
    print_report(report)

    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(output_dir)

    save_results_csv(
        report, str(output_dir / f"retrieval_detailed_{timestamp}.csv")
    )
    save_summary_csv(
        report, str(output_dir / f"retrieval_summary_{timestamp}.csv")
    )

    return report


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Evaluate Retrieval System")
    parser.add_argument(
        "--dataset",
        type=str,
        default=None,
        help="Path to evaluation dataset CSV",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of documents to retrieve (default: 5)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of samples to evaluate (for testing)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Directory to save results",
    )

    args = parser.parse_args()

    run_evaluation(
        dataset_path=args.dataset,
        top_k=args.top_k,
        limit=args.limit,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()
