"""Test script for Embedding Layer (Task 1.1).

Embeds 10 sample Vietnamese university-related questions and checks:
  - Output dimensions
  - Cosine similarity between semantically similar/dissimilar pairs
"""

import sys
import time
import numpy as np

# Ensure the parent directory is on the path so `embedding` can be imported
sys.path.insert(
    0, str(__import__("pathlib").Path(__file__).resolve().parents[1])
)

# ── Sample questions ──────────────────────────────────────────────
# In-domain: university regulation questions (indices 0-7)
SAMPLE_QUERIES = [
    "Điều kiện tốt nghiệp đại học Bách Khoa là gì?",  # 0
    "Sinh viên cần bao nhiêu tín chỉ để tốt nghiệp?",  # 1  ← similar to q0
    "Quy định về học bổng khuyến khích học tập?",  # 2
    "Tiêu chí xét cấp học bổng tài trợ năm 2024?",  # 3  ← similar to q2
    "Sinh viên bị cảnh báo học vụ khi nào?",  # 4
    "Cách tính điểm trung bình tích lũy?",  # 5
    "Thủ tục xin nghỉ học tạm thời?",  # 6
    "Chương trình kỹ sư tài năng có gì khác?",  # 7
    # Out-of-domain: clearly unrelated to university (indices 8-9)
    "Công thức nấu phở bò truyền thống miền Bắc?",  # 8  ← off-topic
    "Giá vàng hôm nay tăng hay giảm so với tuần trước?",  # 9  ← off-topic
]

# Pairs for similarity sanity checks:
#   SIMILAR:    q0 vs q1  — both ask about graduation requirements
#   SIMILAR:    q2 vs q3  — both ask about scholarships
#   DISSIMILAR: q0 vs q8  — university regulation vs cooking recipe
#   DISSIMILAR: q0 vs q9  — university regulation vs gold price news
SIMILAR_PAIRS = [
    (0, 1, "tốt nghiệp vs tín chỉ tốt nghiệp"),
    (2, 3, "học bổng vs học bổng tài trợ"),
]
DISSIMILAR_PAIRS = [
    (0, 8, "tốt nghiệp vs nấu phở"),
    (0, 9, "tốt nghiệp vs giá vàng"),
]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    a_np, b_np = np.array(a), np.array(b)
    return float(
        np.dot(a_np, b_np)
        / (np.linalg.norm(a_np) * np.linalg.norm(b_np) + 1e-10)
    )


def test_single_embedder(embedder, name: str) -> None:
    print(f"\n{'='*60}")
    print(f"Testing: {name}  (dim={embedder.dimension})")
    print(f"{'='*60}")

    # 1. embed_query (single)
    t0 = time.perf_counter()
    q_vec = embedder.embed_query(SAMPLE_QUERIES[0])
    t1 = time.perf_counter()
    assert (
        len(q_vec) == embedder.dimension
    ), f"Expected dim {embedder.dimension}, got {len(q_vec)}"
    print(f"  embed_query        dim={len(q_vec)}  ({t1-t0:.3f}s)")

    # 2. embed_documents (batch)
    t0 = time.perf_counter()
    doc_vecs = embedder.embed_documents(SAMPLE_QUERIES)
    t1 = time.perf_counter()
    assert len(doc_vecs) == len(SAMPLE_QUERIES)
    assert all(len(v) == embedder.dimension for v in doc_vecs)
    print(
        f"  embed_documents    count={len(doc_vecs)}  dim={len(doc_vecs[0])}  ({t1-t0:.3f}s)"
    )

    # 3. Cosine similarity using embed_query (realistic RAG: query vs query)
    #    All sentences embedded as queries so the comparison is apples-to-apples.
    print("  --- Cosine similarity (embed_query encoding) ---")
    query_vecs = [embedder.embed_query(q) for q in SAMPLE_QUERIES]

    for i, j, label in SIMILAR_PAIRS:
        sim = cosine_similarity(query_vecs[i], query_vecs[j])
        mark = "✅" if sim >= 0.70 else "⚠️ "
        print(
            f"  {mark} SIMILAR    q{i} vs q{j} ({label}): {sim:.4f}  (expect ≥ 0.70)"
        )

    for i, j, label in DISSIMILAR_PAIRS:
        sim = cosine_similarity(query_vecs[i], query_vecs[j])
        mark = "✅" if sim < 0.70 else "⚠️ "
        print(
            f"  {mark} DISSIMILAR q{i} vs q{j} ({label}): {sim:.4f}  (expect < 0.70)"
        )

    # 4. RAG-style: query vs document encoding (E5 prefix difference matters here)
    print("  --- Cosine similarity (query vs document encoding, RAG-style) ---")
    q0_as_query = embedder.embed_query(SAMPLE_QUERIES[0])
    docs_as_docs = embedder.embed_documents(SAMPLE_QUERIES[:4])
    for idx, dvec in enumerate(docs_as_docs):
        sim = cosine_similarity(q0_as_query, dvec)
        print(f"    q0 → doc{idx}: {sim:.4f}  ({SAMPLE_QUERIES[idx][:40]}…)")

    print(f"  ✅ {name} passed all checks.")


def main() -> None:
    print("Loading models — this may take a while on first run…\n")

    # ── BGE-M3 ────────────────────────────────────────────────────
    from embedding.bge_m3 import BGEm3Embedder

    bge = BGEm3Embedder()
    test_single_embedder(bge, "BGE-M3")

    # Test sparse encoding (BGE-M3 specific)
    sparse = bge.encode_sparse([SAMPLE_QUERIES[0]])
    print(f"  sparse tokens for q0: {len(sparse[0])} non-zero weights")

    # ── E5-Multilingual ───────────────────────────────────────────
    from embedding.e5_multilingual import E5MultilingualEmbedder

    e5 = E5MultilingualEmbedder()
    test_single_embedder(e5, "E5-Multilingual-Large")

    # ── Ensemble ──────────────────────────────────────────────────
    from embedding.ensemble import EnsembleEmbedder

    ensemble = EnsembleEmbedder(embedders=[bge, e5], weights=[0.6, 0.4])
    test_single_embedder(ensemble, "Ensemble(BGE=0.6, E5=0.4)")

    print("\n🎉 All embedding tests passed!")


if __name__ == "__main__":
    main()
