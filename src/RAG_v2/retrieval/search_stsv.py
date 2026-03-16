"""Real hybrid search demo against the 'stsv' Qdrant + Elasticsearch collection.

Usage (from RAG_v2/ directory):
    python retrieval/search_stsv.py
    python retrieval/search_stsv.py "câu hỏi của bạn"

What it does:
  1. Loads BGE-M3 + E5 embedders.
  2. Embeds each sample query.
  3. Runs hybrid search (Qdrant vector + ES BM25 via RRF).
  4. Prints the top-5 results with scores and metadata.
"""

from __future__ import annotations

import sys
import os
import textwrap

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from embedding.bge_m3 import BGEm3Embedder
from embedding.e5_multilingual import E5MultilingualEmbedder
from retrieval.qdrant_store import QdrantStore
from retrieval.elasticsearch_store import ElasticsearchStore
from retrieval.hybrid_search import HybridSearch

# ------------------------------------------------------------------
# Sample queries for the demo
# ------------------------------------------------------------------
SAMPLE_QUERIES = [
    "Điều kiện để được xét học bổng khuyến khích học tập là gì?",
    "Sinh viên cần bao nhiêu tín chỉ để tốt nghiệp?",
    "Quy định về điểm rèn luyện sinh viên ĐHBK",
    "Làm thế nào để đăng ký ở ký túc xá?",
    "Chính sách hỗ trợ sinh viên khuyết tật HUST",
]

TOP_K = 5
COLLECTION = "stsv"


def print_results(query: str, results: list[dict]) -> None:
    width = 80
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
        v_rank = r.get("vector_rank", 0)
        k_rank = r.get("keyword_rank", 0)
        score = r["score"]
        text_preview = textwrap.fill(
            r["text"][:200], width=width - 4, subsequent_indent="    "
        )
        print(
            f"\n  [{i}] score={score:.5f}  vec_rank={v_rank}  kw_rank={k_rank}"
        )
        print(f"      title    : {title}")
        print(f"      type_doc : {type_doc}")
        print(f"      text     : {text_preview[:160]}...")


def main() -> None:
    queries = sys.argv[1:] if len(sys.argv) > 1 else SAMPLE_QUERIES

    print("Loading BGE-M3 embedder ...")
    bge = BGEm3Embedder()

    print("Loading E5-multilingual embedder ...")
    e5 = E5MultilingualEmbedder()

    print(f"Connecting to Qdrant (collection='{COLLECTION}') ...")
    qdrant_store = QdrantStore(collection_name=COLLECTION)
    print(f"  Points in collection: {qdrant_store.count()}")

    print(f"Connecting to Elasticsearch (index='{COLLECTION}') ...")
    es_store = ElasticsearchStore(index_name=COLLECTION)
    print(f"  Docs in index: {es_store.count()}")

    hybrid = HybridSearch(
        qdrant_store=qdrant_store,
        es_store=es_store,
        rrf_k=60,
        vector_weight=1.0,
        keyword_weight=1.0,
    )

    print(f"\nRunning hybrid search for {len(queries)} quer(ies) ...\n")

    for query in queries:
        bge_vec = bge.embed_query(query)
        e5_vec = e5.embed_query(query)

        results = hybrid.search(
            query=query,
            bge_m3_query=bge_vec,
            e5_query=e5_vec,
            top_k=TOP_K,
            vector_top_k=20,
            keyword_top_k=20,
        )
        print_results(query, results)

    print("\n\nDone.")


if __name__ == "__main__":
    main()
