"""Hybrid search across multiple collections (stsv + quydinh).

Chỉnh sửa các biến cấu hình bên dưới rồi chạy:
    python retrieval/search_multi.py
"""

from __future__ import annotations

import sys
import os
import textwrap

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from embedding.bge_m3 import BGEm3Embedder
from embedding.e5_multilingual import E5MultilingualEmbedder
from retrieval.multi_collection_search import MultiCollectionSearch

# ============================================================
# CẤU HÌNH — chỉnh sửa tại đây
# ============================================================

# Danh sách collection cần tìm kiếm
COLLECTIONS = ["stsv", "quydinh"]

# Nếu tên ES index khác tên collection, khai báo ở đây.
# Để None thì tự dùng tên trùng với COLLECTIONS.
ES_INDEXES = None  # ví dụ: ["stsv_v2", "quydinh"]

# Kết nối
QDRANT_HOST = "localhost"
QDRANT_PORT = 6333
ES_HOST = "localhost"
ES_PORT = 9200

# Tham số search
TOP_K = 5  # số kết quả cuối cùng trả về
VECTOR_TOP_K = 20  # số ứng viên lấy từ Qdrant mỗi collection
KEYWORD_TOP_K = 20  # số ứng viên lấy từ ES mỗi collection
RRF_K = 60
VECTOR_WEIGHT = 1.0
KEYWORD_WEIGHT = 1.0
# Trọng số áp dụng lên per-collection hybrid score trong global fusion.
# 0 = RRF thuần theo vị trí (hành vi cũ); 1.0 = kết hợp cả score tập hợp.
COLLECTION_SCORE_WEIGHT = 1.0

# Câu hỏi cần tìm kiếm
QUERIES = [
    "Sinh viên cần bao nhiêu tín chỉ để tốt nghiệp?",
]

# ============================================================


def print_results(query: str, results: list[dict]) -> None:
    width = 84
    print("\n" + "=" * width)
    print(f"QUERY: {query}")
    print("=" * width)
    if not results:
        print("  (no results)")
        return
    for i, r in enumerate(results, 1):
        meta = r.get("metadata", {})
        title = meta.get("title", "—")
        type_doc = meta.get("type_doc", "—")
        collection = r.get("collection", "—")
        v_rank = r.get("vector_rank", 0)
        k_rank = r.get("keyword_rank", 0)
        score = r["score"]
        col_score = r.get("collection_score", 0.0)
        bge = r.get("bge_score", 0.0)
        e5 = r.get("e5_score", 0.0)
        text_preview = textwrap.fill(
            r["text"][:220], width=width - 6, subsequent_indent="       "
        )
        print(
            f"\n  [{i}] score={score:.5f}  col_score={col_score:.5f}"
            f"  bge={bge:.4f}  e5={e5:.4f}"
            f"  vec_rank={v_rank}  kw_rank={k_rank}"
        )
        print(f"      collection : {collection}")
        print(f"      title      : {title}")
        print(f"      type_doc   : {type_doc}")
        print(f"      text       : {text_preview[:180]}...")


if __name__ == "__main__":
    print("Loading BGE-M3 embedder ...")
    bge = BGEm3Embedder()

    print("Loading E5-multilingual embedder ...")
    e5 = E5MultilingualEmbedder()

    print(f"Initialising MultiCollectionSearch for: {COLLECTIONS} ...")
    searcher = MultiCollectionSearch.from_collection_names(
        collection_names=COLLECTIONS,
        es_index_names=ES_INDEXES,
        qdrant_host=QDRANT_HOST,
        qdrant_port=QDRANT_PORT,
        es_host=ES_HOST,
        es_port=ES_PORT,
        rrf_k=RRF_K,
        vector_weight=VECTOR_WEIGHT,
        keyword_weight=KEYWORD_WEIGHT,
        collection_score_weight=COLLECTION_SCORE_WEIGHT,
    )

    counts = searcher.collection_counts()
    for col, cnt in counts.items():
        print(f"  [{col}] Qdrant: {cnt['qdrant']} pts  |  ES: {cnt['es']} docs")

    print(f"\nRunning search for {len(QUERIES)} quer(ies) ...\n")

    for query in QUERIES:
        bge_vec = bge.embed_query(query)
        e5_vec = e5.embed_query(query)

        results = searcher.search(
            query=query,
            bge_m3_query=bge_vec,
            e5_query=e5_vec,
            top_k=TOP_K,
            vector_top_k=VECTOR_TOP_K,
            keyword_top_k=KEYWORD_TOP_K,
        )
        print_results(query, results)

    print("\n\nDone.")
