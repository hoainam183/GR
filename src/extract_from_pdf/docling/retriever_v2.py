# faiss_retriever.py - Fixed version

from langchain_huggingface import HuggingFaceEmbeddings
import numpy as np
from typing import List, Dict, Optional
import hashlib
from faiss_vector_store import FAISSVectorStore


class FAISSRetriever:
    """
    Retriever sử dụng FAISS vector store
    Fixed: Consistent embedding, efficient lookup, error handling
    """

    def __init__(
        self,
        index_path: str = "./output/faiss_2.index",
        chunks_path: str = "./output/faiss_chunks_2.pkl",
        embedding_model: str = "intfloat/multilingual-e5-large",
        use_cache: bool = True,
    ):
        print("🔄 Initializing FAISS Retriever...")

        # Load vector store
        print(f"   Loading vector store...")
        self.vector_store = FAISSVectorStore()
        self.vector_store.load(index_path, chunks_path)

        # ✅ Use LangChain embeddings (consistent with embedding step)
        print(f"   Loading embedding model: {embedding_model}")
        self.embeddings = HuggingFaceEmbeddings(
            model_name=embedding_model,
            model_kwargs={"device": "cpu"},  # or 'cpu'
            encode_kwargs={"normalize_embeddings": True},
        )
        self.is_e5 = "e5" in embedding_model.lower()

        # ✅ Build chunk_id index for O(1) lookup
        # print("   Building chunk_id index...")
        # self.chunk_id_to_index = {
        #     chunk.get("chunk_id"): i
        #     for i, chunk in enumerate(self.vector_store.chunks)
        #     if chunk.get("chunk_id")
        # }
        # print(f"   Indexed {len(self.chunk_id_to_index)} chunks")

        # ✅ Cache for frequent queries
        self.use_cache = use_cache
        if use_cache:
            self.cache = {}
            self.cache_hits = 0
            self.cache_misses = 0

        print("✅ Retriever ready!\n")

    def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict] = None,
        include_footnotes: bool = True,
        rerank: bool = False,
    ) -> List[Dict]:
        """
        Search cho relevant chunks

        Args:
            query: User question
            top_k: Number of results
            filters: Metadata filters
            include_footnotes: Lấy footnotes liên quan không
            rerank: Re-rank results với additional signals

        Returns:
            List of search results với metadata
        """
        try:
            # Validate inputs
            if not query or not query.strip():
                print("   ⚠️  Empty query")
                return []

            if top_k <= 0:
                raise ValueError(f"top_k must be > 0, got {top_k}")

            # Check cache
            if self.use_cache:
                cache_key = self._make_cache_key(query, top_k, filters)
                if cache_key in self.cache:
                    self.cache_hits += 1
                    hit_rate = self.get_cache_hit_rate()
                    print(
                        f"💾 Cache hit for '{query}' (rate: {hit_rate:.1%})\n"
                    )
                    return self.cache[cache_key]
                self.cache_misses += 1

            print(f"🔍 Searching: '{query}'")

            # Preprocess query
            query = self._preprocess_query(query)

            # 1. Embed query using LangChain (auto adds "query:" for E5)
            query_vector = self.embeddings.embed_query(query)
            query_vector = np.array(query_vector, dtype="float32")

            # 2. Adaptive search with retry
            results = []
            search_k = top_k * 3 if filters else top_k
            max_attempts = 3

            for attempt in range(max_attempts):
                # Search in FAISS
                raw_results = self.vector_store.search(
                    query_vector, top_k=search_k
                )

                # Process results
                for idx, score in raw_results:
                    chunk = self.vector_store.get_chunk(idx)

                    # Apply filters
                    if filters and not self._match_filters(chunk, filters):
                        continue

                    # Format result
                    result = self._format_result(
                        chunk, idx, score, include_footnotes
                    )
                    results.append(result)

                    if len(results) >= top_k:
                        break

                # Check if we have enough
                if len(results) >= top_k:
                    break

                # Retry with more candidates
                if attempt < max_attempts - 1:
                    old_k = search_k
                    search_k = min(search_k * 2, len(self.vector_store.chunks))
                    print(f"   Retrying: {old_k} → {search_k} candidates")

            # Re-rank if requested
            if rerank and len(results) > top_k:
                results = self._rerank_results(query, results)

            # Trim to top_k
            results = results[:top_k]

            print(f"   Found {len(results)} results\n")

            # Cache results
            if self.use_cache and len(self.cache) < 1000:
                self.cache[cache_key] = results

            return results

        except Exception as e:
            print(f"   ❌ Search error: {e}")
            import traceback

            traceback.print_exc()
            return []

    def _preprocess_query(self, query: str) -> str:
        """Preprocess query for better results"""
        # Remove extra whitespace
        query = " ".join(query.split())

        # Expand common abbreviations
        abbreviations = {
            "sv": "sinh viên",
            "gv": "giảng viên",
            "đhbk": "đại học bách khoa",
            "tn": "tốt nghiệp",
        }

        words = query.split()
        expanded = [abbreviations.get(w.lower(), w) for w in words]
        query = " ".join(expanded)

        return query

    def _match_filters(self, chunk: Dict, filters: Dict) -> bool:
        """Check if chunk matches all filters"""
        metadata = chunk.get("metadata", {})
        return all(metadata.get(key) == value for key, value in filters.items())

    def _format_result(
        self, chunk: Dict, idx: int, score: float, include_footnotes: bool
    ) -> Dict:
        """Format result with metadata"""
        result = {
            "score": float(score),
            "index": idx,
            "chunk_id": chunk.get("chunk_id"),
            "chunk_type": chunk.get("chunk_type", "main_content"),
            "content": chunk.get("content"),
            "metadata": chunk.get("metadata", {}),
        }

        # Get footnotes if applicable
        if include_footnotes and chunk.get("chunk_type") == "main_content":
            footnote_refs = chunk.get("metadata", {}).get("footnote_refs", [])
            if footnote_refs:
                result["footnotes"] = self._get_footnotes(footnote_refs)

        return result

    # def _get_footnotes(self, footnote_refs: List[str]) -> List[Dict]:
    #     """
    #     Lấy footnote chunks từ references
    #     O(1) lookup using chunk_id index
    #     """
    #     footnotes = []

    #     for ref in footnote_refs:
    #         target_chunk_id = f"footnote_{ref}"

    #         # ✅ O(1) dict lookup
    #         idx = self.chunk_id_to_index.get(target_chunk_id)

    #         if idx is not None:
    #             chunk = self.vector_store.chunks[idx]
    #             footnotes.append({"id": ref, "content": chunk.get("content")})

    #     return footnotes

    def _rerank_results(self, query: str, results: List[Dict]) -> List[Dict]:
        """
        Re-rank results using additional signals
        """
        for result in results:
            # Initial score from FAISS
            semantic_score = result["score"]

            # Additional signals
            length_score = self._compute_length_score(result["content"])
            position_score = self._compute_position_score(result["metadata"])

            # Combined score
            result["rerank_score"] = (
                0.7 * semantic_score + 0.2 * length_score + 0.1 * position_score
            )

        # Sort by rerank_score
        results.sort(key=lambda x: x["rerank_score"], reverse=True)

        return results

    def _compute_length_score(self, content: str) -> float:
        """Prefer chunks with sufficient detail"""
        length = len(content)
        # Optimal length: 200-800 chars
        if 200 <= length <= 800:
            return 1.0
        elif length < 200:
            return length / 200
        else:
            return max(0.5, 1.0 - (length - 800) / 2000)

    def _compute_position_score(self, metadata: Dict) -> float:
        """Prefer earlier chapters/articles"""
        chapter = metadata.get("chapter", "")

        # Chapter I-III get higher scores
        chapter_scores = {"I": 1.0, "II": 0.9, "III": 0.8}

        return chapter_scores.get(chapter, 0.7)

    def _make_cache_key(
        self, query: str, top_k: int, filters: Optional[Dict]
    ) -> str:
        """Create hashable cache key"""
        key_str = f"{query}|{top_k}|{str(filters)}"
        return hashlib.md5(key_str.encode()).hexdigest()

    def get_cache_hit_rate(self) -> float:
        """Get cache hit rate"""
        if not self.use_cache:
            return 0.0
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total > 0 else 0.0

    def clear_cache(self):
        """Clear query cache"""
        if self.use_cache:
            self.cache = {}
            self.cache_hits = 0
            self.cache_misses = 0
            print("✅ Cache cleared")

    # def search_by_chunk_id(self, chunk_id: str) -> Optional[Dict]:
    #     """Tìm chunk theo chunk_id - O(1) lookup"""
    #     idx = self.chunk_id_to_index.get(chunk_id)
    #     if idx is not None:
    #         return {"index": idx, "chunk": self.vector_store.chunks[idx]}
    #     return None

    def search_by_metadata(
        self, metadata_key: str, metadata_value: str, top_k: int = 10
    ) -> List[Dict]:
        """
        Search chunks có metadata matching

        Example:
            search_by_metadata("applies_to", "sinh_vien")
        """
        results = []

        for i, chunk in enumerate(self.vector_store.chunks):
            if chunk.get("metadata", {}).get(metadata_key) == metadata_value:
                results.append(
                    {
                        "index": i,
                        "chunk_id": chunk.get("chunk_id"),
                        "content": chunk.get("content"),
                        "metadata": chunk.get("metadata", {}),
                    }
                )

                if len(results) >= top_k:
                    break

        return results

    def get_stats(self):
        """Print retriever statistics"""
        print("📊 Retriever Statistics")
        print("=" * 70)
        print(f"Total chunks: {len(self.vector_store.chunks)}")
        # print(f"Indexed chunks: {len(self.chunk_id_to_index)}")

        if self.use_cache:
            print(f"\nCache:")
            print(f"  Size: {len(self.cache)}")
            print(f"  Hits: {self.cache_hits}")
            print(f"  Misses: {self.cache_misses}")
            print(f"  Hit rate: {self.get_cache_hit_rate():.1%}")

        print("=" * 70)


# ============================================================================
# Test Retriever
# ============================================================================


def test_retriever():
    """Test FAISS retriever với các queries"""
    print("=" * 70)
    print("🧪 TESTING FAISS RETRIEVER")
    print("=" * 70)
    print()

    # Initialize retriever
    retriever = FAISSRetriever()

    # Test queries
    test_cases = [
        {
            "query": "nội dung khoản 1 điều 1 chương I",
            "top_k": 10,
            "filters": None,
        }
    ]

    for i, test in enumerate(test_cases, 1):
        print(f"\n{'='*70}")
        print(f"TEST CASE {i}")
        print(f"{'='*70}")
        print(f"Query: {test['query']}")
        if test["filters"]:
            print(f"Filters: {test['filters']}")
        print(f"{'-'*70}\n")

        # Search
        results = retriever.search(
            query=test["query"],
            top_k=test["top_k"],
            filters=test["filters"],
            rerank=False,
        )

        # Display results
        for j, result in enumerate(results, 1):
            print(f"Result {j}:")
            print(f"  Score: {result['score']:.4f}", end="")
            if "rerank_score" in result:
                print(f" (reranked: {result['rerank_score']:.4f})")
            else:
                print()

            print(f"  Chunk ID: {result['chunk_id']}")
            print(f"  Type: {result['chunk_type']}")

            metadata = result["metadata"]
            if metadata.get("chapter_full"):
                print(f"  Chapter: {metadata['chapter_full']}")
            if metadata.get("article_full"):
                print(f"  Article: {metadata['article_full']}")
            if metadata.get("applies_to"):
                print(f"  Applies to: {metadata['applies_to']}")

            print(f"  Content preview:")
            content = result["content"]
            preview = content[:200] if len(content) > 200 else content
            print(f"    {preview}...")

            # Show footnotes if any
            if result.get("footnotes"):
                print(f"  Footnotes: {len(result['footnotes'])}")
                for fn in result["footnotes"][:2]:  # Show first 2
                    fn_preview = (
                        fn["content"][:80]
                        if len(fn["content"]) > 80
                        else fn["content"]
                    )
                    print(f"    [{fn['id']}]: {fn_preview}...")

            print()

    # Test cache
    print(f"\n{'='*70}")
    print("TEST: Cache Performance")
    print(f"{'='*70}\n")

    print("Searching same query twice...")
    query = "nội dung chương I"

    # First search
    results1 = retriever.search(query, top_k=3)

    # Second search (should hit cache)
    results2 = retriever.search(query, top_k=3)

    # Print stats
    retriever.get_stats()

    print("\n" + "=" * 70)
    print("✅ TESTING COMPLETED")
    print("=" * 70)


def test_metadata_search():
    """Test search by metadata"""
    print("\n" + "=" * 70)
    print("🧪 TESTING METADATA SEARCH")
    print("=" * 70)
    print()

    retriever = FAISSRetriever()

    # Test: Find all chunks for sinh_vien
    print("Finding chunks for 'sinh_vien'...")
    results = retriever.search_by_metadata("applies_to", "sinh_vien", top_k=5)

    print(f"Found {len(results)} chunks\n")
    for i, result in enumerate(results[:3], 1):
        print(f"{i}. {result['chunk_id']}")
        content = result["content"]
        preview = content[:150] if len(content) > 150 else content
        print(f"   {preview}...\n")


# def test_chunk_id_lookup():
#     """Test O(1) chunk_id lookup"""
#     print("\n" + "=" * 70)
#     print("🧪 TESTING CHUNK ID LOOKUP")
#     print("=" * 70)
#     print()

#     retriever = FAISSRetriever()

#     # Test lookup
#     test_ids = ["main_1_1", "main_2_1", "nonexistent_id"]

#     for chunk_id in test_ids:
#         print(f"Looking up: {chunk_id}")
#         result = retriever.search_by_chunk_id(chunk_id)

#         if result:
#             chunk = result["chunk"]
#             content = chunk.get("content", "")
#             preview = content[:100] if len(content) > 100 else content
#             print(f"  ✅ Found at index {result['index']}")
#             print(f"  Preview: {preview}...\n")
#         else:
#             print(f"  ❌ Not found\n")


def benchmark_search():
    """Benchmark search performance"""
    print("\n" + "=" * 70)
    print("🔬 BENCHMARKING SEARCH PERFORMANCE")
    print("=" * 70)
    print()

    import time

    retriever = FAISSRetriever(
        use_cache=False
    )  # Disable cache for fair benchmark

    queries = [
        "nội dung chương I",
        "điều kiện tốt nghiệp",
        "thời gian đào tạo",
        "quy định về sinh viên",
        "chương trình đào tạo",
    ]

    print(f"Running {len(queries)} queries...\n")

    latencies = []
    for query in queries:
        start = time.time()
        results = retriever.search(query, top_k=5)
        elapsed = time.time() - start
        latencies.append(elapsed * 1000)  # Convert to ms

        print(
            f"'{query[:30]}...': {elapsed*1000:.2f}ms ({len(results)} results)"
        )

    print(f"\n📊 Statistics:")
    print(f"  Average: {np.mean(latencies):.2f}ms")
    print(f"  Median: {np.median(latencies):.2f}ms")
    print(f"  Min: {np.min(latencies):.2f}ms")
    print(f"  Max: {np.max(latencies):.2f}ms")


if __name__ == "__main__":
    # Run tests
    test_retriever()
    # test_metadata_search()
    # test_chunk_id_lookup()
    # benchmark_search()
