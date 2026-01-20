"""
RAG Evaluation Script
Đánh giá hiệu suất của RAG system dựa trên dataset có sẵn.

Metrics:
1. Retrieval Metrics: Precision, Recall, Hit Rate (document retrieval)
2. Answer Metrics: Semantic Similarity với ground truth

Usage:
    python evaluate_rag.py --api-url http://localhost:8000 --dataset ../../rag_evaluation_dataset.csv
"""

import argparse
import csv
import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests
from tqdm import tqdm

# For semantic similarity
try:
    from sentence_transformers import SentenceTransformer, util

    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    print("⚠️ sentence-transformers not installed. Using basic text similarity.")


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
class RetrievalResult:
    """Result from RAG retrieval"""

    retrieved_sources: List[str]  # List of source file names
    retrieved_contents: List[str]  # List of content
    scores: List[float]  # Similarity scores


@dataclass
class EvaluationResult:
    """Result for single evaluation"""

    question: str
    ground_truth: str
    predicted_answer: str
    expected_source: str
    retrieved_sources: List[str]

    # Retrieval metrics
    retrieval_hit: bool  # Expected source in retrieved sources
    retrieval_precision: float  # Relevant / Retrieved
    retrieval_recall: float  # Relevant / Expected (1 in this case)
    retrieval_mrr: float  # Mean Reciprocal Rank

    # Answer metrics
    answer_similarity: float  # Semantic similarity score

    # Metadata
    question_type: str
    difficulty: str
    response_time: float


@dataclass
class EvaluationReport:
    """Overall evaluation report"""

    total_samples: int

    # Retrieval metrics (aggregated)
    avg_retrieval_precision: float
    avg_retrieval_recall: float
    hit_rate: float  # % of questions where expected source was retrieved
    mrr: float  # Mean Reciprocal Rank

    # Answer metrics (aggregated)
    avg_answer_similarity: float

    # By question type
    metrics_by_type: Dict[str, Dict[str, float]]

    # By difficulty
    metrics_by_difficulty: Dict[str, Dict[str, float]]

    # Timing
    avg_response_time: float
    total_time: float

    # Individual results
    results: List[EvaluationResult] = field(default_factory=list)


class TextSimilarity:
    """Text similarity calculator"""

    def __init__(self, use_sentence_transformers: bool = True):
        self.use_st = (
            use_sentence_transformers and SENTENCE_TRANSFORMERS_AVAILABLE
        )

        if self.use_st:
            print("📦 Loading sentence-transformers model...")
            # Multilingual model that works well with Vietnamese
            self.model = SentenceTransformer(
                "paraphrase-multilingual-MiniLM-L12-v2"
            )
            print("✅ Model loaded!")
        else:
            self.model = None

    def similarity(self, text1: str, text2: str) -> float:
        """Calculate semantic similarity between two texts"""
        if self.use_st:
            embeddings = self.model.encode(
                [text1, text2], convert_to_tensor=True
            )
            sim = util.cos_sim(embeddings[0], embeddings[1]).item()
            return max(0, sim)  # Ensure non-negative
        else:
            # Fallback: Simple word overlap (Jaccard similarity)
            return self._jaccard_similarity(text1, text2)

    def _jaccard_similarity(self, text1: str, text2: str) -> float:
        """Simple Jaccard similarity as fallback"""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = words1 & words2
        union = words1 | words2

        return len(intersection) / len(union)


class RAGEvaluator:
    """RAG System Evaluator"""

    def __init__(self, api_url: str, top_k: int = 5):
        self.api_url = api_url.rstrip("/")
        self.top_k = top_k
        self.similarity_calculator = TextSimilarity()

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
                    question_type=row["question_type"],
                    difficulty=row["difficulty"],
                    relevant_context=row.get("relevant_context", ""),
                )
                samples.append(sample)

        return samples

    def query_rag(self, question: str) -> Tuple[str, RetrievalResult, float]:
        """
        Query RAG API and return answer + retrieval results

        Returns:
            answer: Generated answer
            retrieval_result: Retrieved documents info
            response_time: Time taken in seconds
        """
        start_time = time.time()

        try:
            response = requests.post(
                f"{self.api_url}/chat",
                json={"question": question, "top_k": self.top_k},
                timeout=60,
            )
            response.raise_for_status()

            data = response.json()
            response_time = time.time() - start_time

            # Extract retrieval info
            retrieved_sources = []
            retrieved_contents = []
            scores = []

            for doc in data.get("retrieved_documents", []):
                metadata = doc.get("metadata", {})
                source_file = metadata.get("source_file", "")
                retrieved_sources.append(source_file)
                retrieved_contents.append(doc.get("content", ""))
                scores.append(doc.get("score", 0))

            retrieval_result = RetrievalResult(
                retrieved_sources=retrieved_sources,
                retrieved_contents=retrieved_contents,
                scores=scores,
            )

            return data.get("answer", ""), retrieval_result, response_time

        except Exception as e:
            print(f"❌ Error querying RAG: {e}")
            return "", RetrievalResult([], [], []), time.time() - start_time

    def normalize_source_name(self, source: str) -> str:
        """Normalize source file name for comparison"""
        # Remove path, extension variations, and normalize
        source = source.lower()
        source = source.replace("\\", "/").split("/")[-1]  # Get filename
        source = source.replace("_converted", "").replace(".md", "")
        # Remove common prefixes/suffixes
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

            # Check if either contains the other (fuzzy match)
            if (
                expected_norm in retrieved_norm
                or retrieved_norm in expected_norm
            ):
                return True, i + 1

            # Check key parts match
            expected_parts = set(
                expected_norm.replace("_", " ").replace("-", " ").split()
            )
            retrieved_parts = set(
                retrieved_norm.replace("_", " ").replace("-", " ").split()
            )

            # If significant overlap in parts
            overlap = len(expected_parts & retrieved_parts)
            if overlap >= min(2, len(expected_parts)):
                return True, i + 1

        return False, 0

    def evaluate_single(self, sample: EvaluationSample) -> EvaluationResult:
        """Evaluate single sample"""
        # Query RAG
        answer, retrieval, response_time = self.query_rag(sample.question)

        # Retrieval evaluation
        hit, rank = self.check_source_match(
            sample.expected_source, retrieval.retrieved_sources
        )

        # Precision: If hit, 1/num_retrieved (simplified since we expect 1 relevant doc)
        # More accurate: relevant_retrieved / total_retrieved
        retrieval_precision = (
            1.0 / len(retrieval.retrieved_sources)
            if hit and retrieval.retrieved_sources
            else 0.0
        )

        # Recall: relevant_retrieved / total_relevant (we have 1 relevant doc per question)
        retrieval_recall = 1.0 if hit else 0.0

        # MRR: 1/rank if found, else 0
        mrr = 1.0 / rank if rank > 0 else 0.0

        # Answer similarity
        answer_similarity = (
            self.similarity_calculator.similarity(
                sample.ground_truth_answer, answer
            )
            if answer
            else 0.0
        )

        return EvaluationResult(
            question=sample.question,
            ground_truth=sample.ground_truth_answer,
            predicted_answer=answer,
            expected_source=sample.expected_source,
            retrieved_sources=retrieval.retrieved_sources,
            retrieval_hit=hit,
            retrieval_precision=retrieval_precision,
            retrieval_recall=retrieval_recall,
            retrieval_mrr=mrr,
            answer_similarity=answer_similarity,
            question_type=sample.question_type,
            difficulty=sample.difficulty,
            response_time=response_time,
        )

    def evaluate(
        self, samples: List[EvaluationSample], verbose: bool = True
    ) -> EvaluationReport:
        """Run full evaluation on all samples"""
        results = []
        total_start = time.time()

        iterator = tqdm(samples, desc="Evaluating") if verbose else samples

        for i, sample in enumerate(iterator):
            result = self.evaluate_single(sample)
            results.append(result)

            if verbose:
                status = "✅" if result.retrieval_hit else "❌"
                iterator.set_postfix(
                    {"hit": status, "sim": f"{result.answer_similarity:.2f}"}
                )

            # Sleep 60 seconds between queries to avoid rate limit (except for last sample)
            if i < len(samples) - 1:
                if verbose:
                    print(f"\n⏳ Waiting 60 seconds to avoid rate limit...")
                time.sleep(60)

        total_time = time.time() - total_start

        # Aggregate metrics
        n = len(results)

        avg_precision = sum(r.retrieval_precision for r in results) / n
        avg_recall = sum(r.retrieval_recall for r in results) / n
        hit_rate = sum(1 for r in results if r.retrieval_hit) / n
        mrr = sum(r.retrieval_mrr for r in results) / n
        avg_similarity = sum(r.answer_similarity for r in results) / n
        avg_response_time = sum(r.response_time for r in results) / n

        # Metrics by question type
        metrics_by_type = self._aggregate_by_field(results, "question_type")

        # Metrics by difficulty
        metrics_by_difficulty = self._aggregate_by_field(results, "difficulty")

        return EvaluationReport(
            total_samples=n,
            avg_retrieval_precision=avg_precision,
            avg_retrieval_recall=avg_recall,
            hit_rate=hit_rate,
            mrr=mrr,
            avg_answer_similarity=avg_similarity,
            metrics_by_type=metrics_by_type,
            metrics_by_difficulty=metrics_by_difficulty,
            avg_response_time=avg_response_time,
            total_time=total_time,
            results=results,
        )

    def _aggregate_by_field(
        self, results: List[EvaluationResult], field: str
    ) -> Dict[str, Dict[str, float]]:
        """Aggregate metrics by a specific field"""
        groups = {}

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
                "hit_rate": sum(1 for r in group if r.retrieval_hit) / n,
                "mrr": sum(r.retrieval_mrr for r in group) / n,
                "avg_similarity": sum(r.answer_similarity for r in group) / n,
                "avg_precision": sum(r.retrieval_precision for r in group) / n,
                "avg_recall": sum(r.retrieval_recall for r in group) / n,
            }

        return aggregated


def print_report(report: EvaluationReport):
    """Print formatted evaluation report"""
    print("\n" + "=" * 70)
    print("📊 RAG EVALUATION REPORT")
    print("=" * 70)

    print(f"\n📈 OVERALL METRICS (n={report.total_samples})")
    print("-" * 50)

    print("\n🔍 Retrieval Metrics:")
    print(f"   • Hit Rate:     {report.hit_rate:.2%}")
    print(f"   • MRR:          {report.mrr:.4f}")
    print(f"   • Precision:    {report.avg_retrieval_precision:.4f}")
    print(f"   • Recall:       {report.avg_retrieval_recall:.4f}")

    print("\n📝 Answer Quality Metrics:")
    print(f"   • Semantic Similarity: {report.avg_answer_similarity:.4f}")

    print("\n⏱️ Performance:")
    print(f"   • Avg Response Time: {report.avg_response_time:.2f}s")
    print(f"   • Total Time:        {report.total_time:.2f}s")

    # By question type
    print("\n📊 METRICS BY QUESTION TYPE")
    print("-" * 50)
    for qtype, metrics in report.metrics_by_type.items():
        print(f"\n   {qtype} (n={metrics['count']}):")
        print(
            f"      Hit Rate: {metrics['hit_rate']:.2%} | MRR: {metrics['mrr']:.4f} | Similarity: {metrics['avg_similarity']:.4f}"
        )

    # By difficulty
    print("\n📊 METRICS BY DIFFICULTY")
    print("-" * 50)
    for diff, metrics in report.metrics_by_difficulty.items():
        print(f"\n   {diff} (n={metrics['count']}):")
        print(
            f"      Hit Rate: {metrics['hit_rate']:.2%} | MRR: {metrics['mrr']:.4f} | Similarity: {metrics['avg_similarity']:.4f}"
        )

    # Failed retrievals
    failed = [r for r in report.results if not r.retrieval_hit]
    if failed:
        print(f"\n❌ FAILED RETRIEVALS ({len(failed)}/{report.total_samples})")
        print("-" * 50)
        for r in failed[:5]:  # Show first 5
            print(f"\n   Q: {r.question[:80]}...")
            print(f"   Expected: {r.expected_source}")
            print(f"   Retrieved: {r.retrieved_sources[:3]}")

    print("\n" + "=" * 70)


def save_report(report: EvaluationReport, output_dir: str):
    """Save detailed report to files"""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save summary JSON
    summary = {
        "timestamp": timestamp,
        "total_samples": report.total_samples,
        "retrieval_metrics": {
            "hit_rate": report.hit_rate,
            "mrr": report.mrr,
            "avg_precision": report.avg_retrieval_precision,
            "avg_recall": report.avg_retrieval_recall,
        },
        "answer_metrics": {
            "avg_semantic_similarity": report.avg_answer_similarity,
        },
        "performance": {
            "avg_response_time": report.avg_response_time,
            "total_time": report.total_time,
        },
        "by_question_type": report.metrics_by_type,
        "by_difficulty": report.metrics_by_difficulty,
    }

    summary_file = output_path / f"evaluation_summary_{timestamp}.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # Save detailed results CSV
    results_file = output_path / f"evaluation_results_{timestamp}.csv"
    with open(results_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "question",
                "ground_truth",
                "predicted_answer",
                "expected_source",
                "retrieved_sources",
                "retrieval_hit",
                "retrieval_precision",
                "retrieval_recall",
                "mrr",
                "answer_similarity",
                "question_type",
                "difficulty",
                "response_time",
            ]
        )

        for r in report.results:
            writer.writerow(
                [
                    r.question,
                    r.ground_truth,
                    r.predicted_answer,
                    r.expected_source,
                    "|".join(r.retrieved_sources),
                    r.retrieval_hit,
                    r.retrieval_precision,
                    r.retrieval_recall,
                    r.retrieval_mrr,
                    r.answer_similarity,
                    r.question_type,
                    r.difficulty,
                    r.response_time,
                ]
            )

    print(f"\n💾 Reports saved to:")
    print(f"   • Summary: {summary_file}")
    print(f"   • Details: {results_file}")


def main():
    parser = argparse.ArgumentParser(description="Evaluate RAG System")
    parser.add_argument(
        "--api-url",
        type=str,
        default="http://localhost:8000",
        help="RAG API URL",
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default=str(
            Path(__file__).parent.parent.parent.parent
            / "rag_evaluation_dataset.csv"
        ),
        help="Path to evaluation dataset CSV",
    )
    parser.add_argument(
        "--top-k", type=int, default=5, help="Number of documents to retrieve"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="evaluation_results",
        help="Directory to save results",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of samples to evaluate",
    )

    args = parser.parse_args()

    print("🚀 RAG Evaluation Script")
    print("=" * 50)
    print(f"   API URL:  {args.api_url}")
    print(f"   Dataset:  {args.dataset}")
    print(f"   Top K:    {args.top_k}")
    print("=" * 50)

    # Check API health
    try:
        response = requests.get(f"{args.api_url}/health", timeout=5)
        if response.status_code != 200:
            print(f"❌ API not healthy: {response.status_code}")
            return
        print("✅ API is healthy")
    except Exception as e:
        print(f"❌ Cannot connect to API: {e}")
        print("   Please start the backend first: uvicorn main:app --reload")
        return

    # Load dataset
    evaluator = RAGEvaluator(api_url=args.api_url, top_k=args.top_k)
    samples = evaluator.load_dataset(args.dataset)

    if args.limit:
        samples = samples[: args.limit]

    print(f"📚 Loaded {len(samples)} samples")

    # Run evaluation
    report = evaluator.evaluate(samples)

    # Print report
    print_report(report)

    # Save report
    save_report(report, args.output_dir)


if __name__ == "__main__":
    main()
