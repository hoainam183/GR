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

    # 3. Train two-stage classifier
    clf = DomainClassifier(embedder=embedder)
    result = clf.train(data, test_size=0.2)

    # 4. Print report
    print("\n" + "=" * 60)
    print(f"  Stage 1 Intent Accuracy : {result['accuracy']:.4f}")
    print(
        f"  Stage 2 Domain  F1      : {result['domain_f1']:.4f}  (samples avg)"
    )
    print("=" * 60)
    print(result["report"])

    # 5. Save model
    save_path = clf.save()
    print(f"\nModel saved to: {save_path}")

    # 6. Sanity check — single-label and multi-label cases
    print("\n── Sanity Check ──")
    test_cases = [
        # (query, note)
        ("Xin chào!", None),
        ("Thời tiết hôm nay thế nào?", None),
        ("Điều kiện xét học bổng khuyến khích là gì?", None),
        ("Lịch thi cuối kỳ khi nào?", None),
        ("Thủ tục xin giấy xác nhận sinh viên", None),
        ("Chương trình đào tạo ngành CNTT có bao nhiêu tín chỉ?", None),
        # Multi-domain
        (
            "Ngành CNTT cần bao nhiêu tín chỉ và điều kiện tốt nghiệp ra sao?",
            "→ expect ctdt + quydinh",
        ),
        (
            "Bao giờ đăng ký KTX và thủ tục đăng ký thế nào?",
            "→ expect kehoach + stsv",
        ),
        # Hard negatives
        ("Học bổng kỳ này nộp đơn ở đâu?", "→ expect stsv (not quydinh)"),
        ("Deadline nộp học bổng kỳ này?", "→ expect kehoach (not quydinh)"),
        (
            "Mức đóng bảo hiểm y tế sinh viên năm nay",
            "→ expect quydinh (not stsv)",
        ),
    ]
    for q, note in test_cases:
        pred = clf.predict(q)
        domains_str = ", ".join(pred.get("domains") or [pred["label"]])
        note_str = f"  {note}" if note else ""
        print(
            f"  [{pred['intent']:>11}] [{domains_str:<22}]"
            f" conf={pred['confidence']:.3f}  ← {q}{note_str}"
        )


if __name__ == "__main__":
    main()
