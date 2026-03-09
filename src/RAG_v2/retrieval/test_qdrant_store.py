"""Quick smoke test for QdrantStore (requires Qdrant running on localhost:6333)."""

import random
import uuid

from retrieval.qdrant_store import QdrantStore


def random_vector(dim: int = 1024) -> list[float]:
    return [random.gauss(0, 1) for _ in range(dim)]


def main() -> None:
    test_collection = f"test_{uuid.uuid4().hex[:8]}"
    store = QdrantStore(collection_name=test_collection)
    print(f"[OK] Connected to Qdrant, collection='{test_collection}'")

    # --- Index ---
    texts = [
        "Quy định về học bổng khuyến khích học tập",
        "Hướng dẫn đăng ký môn học trực tuyến",
        "Quy chế công tác sinh viên ĐHBK Hà Nội",
        "Điều kiện tốt nghiệp đại học chính quy",
        "Chính sách hỗ trợ sinh viên khuyết tật",
    ]
    bge_vecs = [random_vector() for _ in texts]
    e5_vecs = [random_vector() for _ in texts]
    metadatas = [{"source": f"doc_{i}.md"} for i in range(len(texts))]

    store.index_documents(texts, bge_vecs, e5_vecs, metadatas=metadatas)
    print(f"[OK] Indexed {len(texts)} documents")

    # --- Count ---
    count = store.count()
    assert count == len(texts), f"Expected {len(texts)}, got {count}"
    print(f"[OK] Count = {count}")

    # --- Search ---
    results = store.search(
        bge_m3_query=random_vector(),
        e5_query=random_vector(),
        top_k=3,
    )
    assert len(results) <= 3
    assert all("text" in r and "score" in r for r in results)
    print(f"[OK] Search returned {len(results)} results")
    for r in results:
        print(
            f"     score={r['score']:.4f}  bge={r['bge_score']:.4f}  e5={r['e5_score']:.4f}  text={r['text'][:50]}"
        )

    # --- Delete by metadata ---
    store.delete_by_metadata("source", "doc_0.md")
    import time

    time.sleep(0.5)  # Qdrant may need a moment
    new_count = store.count()
    assert new_count == count - 1, f"Expected {count - 1}, got {new_count}"
    print(f"[OK] Delete by metadata — count {count} → {new_count}")

    # --- Cleanup ---
    store.delete_collection()
    print(f"[OK] Cleaned up test collection '{test_collection}'")

    print("\n✅ All tests passed!")


if __name__ == "__main__":
    main()
