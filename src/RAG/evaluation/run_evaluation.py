"""
Quick Run Evaluation Script
Chạy nhanh để đánh giá RAG system
"""

import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from evaluate_rag import RAGEvaluator, print_report, save_report


def run_evaluation(
    api_url: str = "http://localhost:8000",
    dataset_path: str = None,
    top_k: int = 5,
    limit: int = None,
):
    """
    Run RAG evaluation

    Args:
        api_url: URL of RAG API
        dataset_path: Path to evaluation CSV
        top_k: Number of documents to retrieve
        limit: Limit number of samples (for testing)
    """

    # Default dataset path
    if dataset_path is None:
        dataset_path = (
            Path(__file__).parent.parent.parent.parent
            / "rag_evaluation_dataset.csv"
        )

    print("🚀 Starting RAG Evaluation...")
    print(f"   API: {api_url}")
    print(f"   Dataset: {dataset_path}")

    # Initialize evaluator
    evaluator = RAGEvaluator(api_url=api_url, top_k=top_k)

    # Load samples
    samples = evaluator.load_dataset(str(dataset_path))
    print(f"   Samples: {len(samples)}")

    if limit:
        samples = samples[:limit]
        print(f"   Limited to: {limit} samples")

    # Run evaluation
    report = evaluator.evaluate(samples, verbose=True)

    # Print results
    print_report(report)

    # Save results
    output_dir = Path(__file__).parent / "evaluation_results"
    save_report(report, str(output_dir))

    return report


if __name__ == "__main__":
    # Có thể thay đổi parameters ở đây

    # Test với số lượng nhỏ trước
    # run_evaluation(limit=5)

    # Chạy full evaluation
    run_evaluation()
