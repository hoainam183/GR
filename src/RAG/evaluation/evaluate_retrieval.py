"""
Retrieval Evaluation Script
Đánh giá hiệu suất retrieval của RAG system bằng cách so sánh với ground truth dataset.

Hỗ trợ đánh giá:
- Semantic search only
- Hybrid search (BM25 + Semantic)
- With/without reranking (Cross-encoder)

Metrics:
- Precision@K: Số documents relevant / K documents retrieved
- Recall@K: Số documents relevant retrieved / Tổng documents relevant
- Hit Rate@K: % câu hỏi có ít nhất 1 relevant document trong top-K
- MRR (Mean Reciprocal Rank): Trung bình 1/rank của relevant document đầu tiên

Usage:
    python evaluate_retrieval.py
    python evaluate_retrieval.py --top-k 10
    python evaluate_retrieval.py --limit 10  # Test với 10 samples
    python evaluate_retrieval.py --no-hybrid  # Disable hybrid search
    python evaluate_retrieval.py --no-rerank  # Disable reranking
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
from embedding.hybrid_search import create_hybrid_searcher
from embedding.reranker import create_reranker


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

    # Configuration
    use_hybrid: bool = False
    use_reranker: bool = False

    # Aggregated metrics
    precision_at_k: float = 0.0
    recall_at_k: float = 0.0
    hit_rate_at_k: float = 0.0
    mrr: float = 0.0  # Mean Reciprocal Rank

    # By question type
    metrics_by_type: Dict[str, Dict[str, float]] = field(default_factory=dict)

    # By difficulty
    metrics_by_difficulty: Dict[str, Dict[str, float]] = field(
        default_factory=dict
    )

    # Individual results
    results: List[RetrievalEvalResult] = field(default_factory=list)


class RetrievalEvaluator:
    """Retrieval System Evaluator using local pipeline with BM25 + Reranking"""

    def __init__(
        self,
        top_k: int = 5,
        verbose: bool = True,
        use_hybrid: bool = True,
        use_reranker: bool = True,
        score_threshold: float = 0.5,
    ):
        self.top_k = top_k
        self.verbose = verbose
        self.use_hybrid = use_hybrid
        self.use_reranker = use_reranker
        self.score_threshold = score_threshold
        self.pipeline = None
        self.hybrid_searcher = None
        self.reranker = None

    def load_pipeline(self):
        """Load embedding pipeline, vector store, hybrid searcher, and reranker"""
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

        # Setup hybrid searcher (BM25 + Semantic)
        if self.use_hybrid:
            if self.verbose:
                print("🔗 Setting up hybrid searcher (BM25 + Semantic)...")
            self.hybrid_searcher = create_hybrid_searcher(
                semantic_weight=0.5, fusion_method="rrf"
            )
            if self.verbose:
                print("   ✅ Hybrid search enabled")

        # Setup reranker (Cross-encoder)
        if self.use_reranker:
            try:
                if self.verbose:
                    print("🎯 Loading reranker model...")
                    print(
                        "   Note: This may take 5-10 minutes on first load (downloading ~1.3GB model)"
                    )
                    print("   If it hangs, use --no-rerank to skip reranking")

                self.reranker = create_reranker(
                    model_name="BAAI/bge-reranker-v2-m3",
                    device="cpu",
                    enable_deduplication=True,
                    enable_reranking=True,
                    score_threshold=self.score_threshold,
                )

                if self.verbose:
                    print("   ✅ Reranker loaded")
                    print(f"   Score threshold: {self.score_threshold}")

            except Exception as e:
                print(f"❌ Failed to load reranker: {e}")
                print("   Continuing without reranking...")
                self.use_reranker = False
                self.reranker = None

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
        Retrieve documents for a query with optional hybrid search and reranking

        Returns:
            sources: List of source file names
            scores: List of similarity scores
        """
        if self.pipeline is None:
            raise RuntimeError(
                "Pipeline not loaded. Call load_pipeline() first."
            )

        # Calculate initial top_k (retrieve more if using hybrid/reranking)
        initial_top_k = (
            self.top_k * 4
            if (self.use_hybrid or self.use_reranker)
            else self.top_k * 2  # Lấy nhiều hơn để có thể filter theo threshold
        )

        # Step 1: Semantic search
        results = self.pipeline.search(query, top_k=initial_top_k)

        # Step 2: Apply Hybrid Search (BM25 + Semantic)
        if self.use_hybrid and self.hybrid_searcher and results:
            hybrid_top_k = self.top_k * 2 if self.use_reranker else self.top_k
            results = self.hybrid_searcher.hybrid_search(
                query, results, top_k=hybrid_top_k
            )

        # Step 3: Apply Reranking (Cross-encoder + Deduplication)
        if self.use_reranker and self.reranker and results:
            results = self.reranker.process(query, results, top_k=self.top_k)
        else:
            # Nếu không dùng reranker, áp dụng threshold cho semantic/hybrid scores
            if self.score_threshold and self.score_threshold > 0 and results:
                filtered_results = [
                    r for r in results if r.score >= self.score_threshold
                ]
                # Đảm bảo luôn có ít nhất 1 document
                if len(filtered_results) == 0:
                    filtered_results = [
                        results[0]
                    ]  # Giữ document có score cao nhất
                results = filtered_results[: self.top_k]
            else:
                results = results[: self.top_k]

        # Extract sources and scores
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
        # Precision: relevant_retrieved / actual_retrieved_docs
        # Với score threshold, số documents trả về có thể < top_k
        num_retrieved = len(sources)
        precision = 1.0 / num_retrieved if (hit and num_retrieved > 0) else 0.0

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
            use_hybrid=self.use_hybrid,
            use_reranker=self.use_reranker,
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

    # Configuration info
    print(f"\n⚙️  CONFIGURATION")
    print("-" * 50)
    print(
        f"   • Hybrid Search (BM25): {'✅ Enabled' if report.use_hybrid else '❌ Disabled'}"
    )
    print(
        f"   • Reranking (Cross-encoder): {'✅ Enabled' if report.use_reranker else '❌ Disabled'}"
    )

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

        # Configuration
        writer.writerow(["CONFIGURATION"])
        writer.writerow(["Setting", "Value"])
        writer.writerow(
            [
                "Hybrid Search (BM25)",
                "Enabled" if report.use_hybrid else "Disabled",
            ]
        )
        writer.writerow(
            [
                "Reranking (Cross-encoder)",
                "Enabled" if report.use_reranker else "Disabled",
            ]
        )
        writer.writerow([])

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
    use_hybrid: bool = True,
    use_reranker: bool = True,
    score_threshold: float = 0.5,
):
    """
    Run retrieval evaluation

    Args:
        dataset_path: Path to evaluation CSV
        top_k: Number of documents to retrieve
        limit: Limit number of samples (for testing)
        output_dir: Directory to save results
        use_hybrid: Enable hybrid search (BM25 + Semantic)
        use_reranker: Enable reranking (Cross-encoder)
        score_threshold: Minimum cross-encoder score to keep documents (0 = keep all)
    """
    # Default paths
    if dataset_path is None:
        dataset_path = (
            Path(__file__).parent.parent.parent.parent
            / "rag_evaluation_dataset_expanded.csv"
        )

    if output_dir is None:
        output_dir = Path(__file__).parent / "retrieval_results"

    print("🚀 Retrieval Evaluation Script")
    print("=" * 50)
    print(f"   Dataset:      {dataset_path}")
    print(f"   Top K:        {top_k}")
    print(f"   Hybrid (BM25): {'✅ Enabled' if use_hybrid else '❌ Disabled'}")
    print(f"   Reranking:    {'✅ Enabled' if use_reranker else '❌ Disabled'}")
    print(f"   Score Threshold: {score_threshold}")
    print("=" * 50)

    # Initialize evaluator
    evaluator = RetrievalEvaluator(
        top_k=top_k,
        verbose=True,
        use_hybrid=use_hybrid,
        use_reranker=use_reranker,
        score_threshold=score_threshold,
    )

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

    # Add config suffix to filename
    config_suffix = ""
    if use_hybrid:
        config_suffix += "_hybrid"
    if use_reranker:
        config_suffix += "_rerank"
    if not config_suffix:
        config_suffix = "_semantic_only"

    output_dir = Path(output_dir)

    save_results_csv(
        report,
        str(output_dir / f"retrieval_detailed{config_suffix}_{timestamp}.csv"),
    )
    save_summary_csv(
        report,
        str(output_dir / f"retrieval_summary{config_suffix}_{timestamp}.csv"),
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
    parser.add_argument(
        "--no-hybrid",
        action="store_true",
        help="Disable hybrid search (BM25 + Semantic)",
    )
    parser.add_argument(
        "--no-rerank",
        action="store_true",
        help="Disable reranking (Cross-encoder)",
    )
    parser.add_argument(
        "--score-threshold",
        type=float,
        default=0.5,
        help="Minimum cross-encoder score to keep documents (default: 0.5, use 0 to keep all)",
    )

    args = parser.parse_args()

    run_evaluation(
        dataset_path=args.dataset,
        top_k=args.top_k,
        limit=args.limit,
        output_dir=args.output_dir,
        use_hybrid=not args.no_hybrid,
        use_reranker=not args.no_rerank,
        score_threshold=args.score_threshold,
    )


if __name__ == "__main__":
    main()
