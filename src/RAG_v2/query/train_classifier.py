"""Train the domain classifier and save the model.

Usage:
    cd d:\\GR\\src\\RAG_v2
    python -m query.train_classifier
"""

from __future__ import annotations

import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    from embedding.bge_m3 import BGEm3Embedder
    from query.domain_classifier import DomainClassifier
    from query.training_data import get_training_data

    # 1. Load training data
    data = get_training_data()
    logger.info("Loaded %d training samples", len(data))

    # 2. Init embedder (shared instance)
    embedder = BGEm3Embedder()

    # 3. Train classifier
    clf = DomainClassifier(embedder=embedder)
    result = clf.train(data, test_size=0.2)

    # 4. Print report
    print("\n" + "=" * 60)
    print(f"  Accuracy: {result['accuracy']:.4f}")
    print("=" * 60)
    print(result["report"])

    # 5. Save model
    save_path = clf.save()
    print(f"\nModel saved to: {save_path}")

    # 6. Quick sanity check
    print("\n── Sanity Check ──")
    test_queries = [
        "Xin chào!",
        "Điều kiện xét học bổng khuyến khích là gì?",
        "Lịch thi cuối kỳ khi nào?",
        "Thời tiết hôm nay thế nào?",
        "Thủ tục xin giấy xác nhận sinh viên",
        "Chương trình đào tạo ngành CNTT có bao nhiêu tín chỉ?",
    ]
    for q in test_queries:
        pred = clf.predict(q)
        print(
            f"  [{pred['intent']:>11}] [{pred['label']:>11}] "
            f"conf={pred['confidence']:.3f}  ← {q}"
        )


if __name__ == "__main__":
    main()
