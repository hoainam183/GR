# evaluate_retrieval.py

from retriever import FAISSRetriever
from typing import List, Dict


def evaluate_retrieval():
    """
    Đánh giá quality của retrieval system
    """
    print("=" * 70)
    print("📊 RETRIEVAL EVALUATION")
    print("=" * 70)
    print()

    retriever = FAISSRetriever()

    # Test cases với expected results
    test_cases = [
        {
            "query": "Điều kiện tốt nghiệp đại học",
            "expected_article": "Điều 14",
            "expected_applies_to": "sinh_vien",
        },
        {
            "query": "Điều kiện bảo vệ luận án tiến sĩ",
            "expected_article": "Điều 40",
            "expected_applies_to": "nghien_cuu_sinh",
        },
        {
            "query": "Quy định học phí",
            "expected_article": "Điều 9",
            "expected_applies_to": None,
        },
        {
            "query": "Đăng ký học tập chương trình đại học",
            "expected_article": "Điều 10",
            "expected_applies_to": "sinh_vien",
        },
    ]

    total_correct = 0

    for i, test in enumerate(test_cases, 1):
        print(f"Test {i}: {test['query']}")
        print(f"  Expected article: {test['expected_article']}")

        results = retriever.search(test["query"], top_k=3)

        # Check if expected article in top 3
        found = False
        for j, result in enumerate(results, 1):
            article = result["metadata"].get("article", "")
            if test["expected_article"] in article:
                print(
                    f"  ✅ Found at position {j} (score: {result['score']:.4f})"
                )
                found = True
                total_correct += 1
                break

        if not found:
            print(f"  ❌ Not found in top 3")
            print(
                f"  Top result: {results[0]['metadata'].get('article', 'N/A')}"
            )

        print()

    accuracy = total_correct / len(test_cases) * 100

    print("=" * 70)
    print(
        f"RESULTS: {total_correct}/{len(test_cases)} correct ({accuracy:.1f}%)"
    )
    print("=" * 70)


if __name__ == "__main__":
    evaluate_retrieval()
