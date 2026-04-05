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

    # 1. Load training data (multi-label format)
    data = get_training_data()
    logger.info("Loaded %d training samples", len(data))
    multi_label_count = sum(1 for _, lbls in data if len(lbls) > 1)
    logger.info("  of which %d are multi-label", multi_label_count)

    # 2. Init embedder (shared instance)
    embedder = BGEm3Embedder()

    # 3. Train classifier (OvR + Platt scaling)
    clf = DomainClassifier(embedder=embedder)
    result = clf.train(data, test_size=0.2, val_size=0.15)

    # 4. Print report
    print("\n" + "=" * 60)
    print(f"  Samples F1: {result['accuracy']:.4f}")
    print("=" * 60)
    print(result["report"])

    # 5. Save model
    save_path = clf.save()
    print(f"\nModel saved to: {save_path}")

    # 6. Quick sanity check
    print("\n── Sanity Check ──")
    test_queries = [
        ("Xin chào!", None),
        ("Điều kiện xét học bổng khuyến khích là gì?", None),
        ("Lịch thi cuối kỳ khi nào?", None),
        ("Thời tiết hôm nay thế nào?", None),
        ("Thủ tục xin giấy xác nhận sinh viên", None),
        ("Chương trình đào tạo ngành CNTT có bao nhiêu tín chỉ?", None),
        # Multi-domain test
        (
            "Ngành CNTT cần bao nhiêu tín chỉ và điều kiện tốt nghiệp ra sao?",
            "→ expect ctdt + quydinh",
        ),
        (
            "Bao giờ đăng ký KTX và thủ tục đăng ký thế nào?",
            "→ expect kehoach + stsv",
        ),
        # Hard negative test
        ("Học bổng kỳ này nộp đơn ở đâu?", "→ expect stsv (not quydinh)"),
        ("Deadline nộp học bổng kỳ này?", "→ expect kehoach (not quydinh)"),
    ]
    for q, note in test_queries:
        pred = clf.predict(q)
        domains_str = ", ".join(pred.get("domains") or [pred["label"]])
        note_str = f"  {note}" if note else ""
        print(
            f"  [{pred['intent']:>11}] [{domains_str:<20}] "
            f"conf={pred['confidence']:.3f}  ← {q}{note_str}"
        )


if __name__ == "__main__":
    main()
