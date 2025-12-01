# hybrid_retriever.py - Hybrid Search Implementation

from langchain_huggingface import HuggingFaceEmbeddings
import numpy as np
from typing import List, Dict, Optional, Tuple
import re
from rank_bm25 import BM25Okapi
from faiss_vector_store import FAISSVectorStore


class HybridRetriever:
    """
    Hybrid Retriever: Semantic (E5) + Keyword (BM25)
    """

    def __init__(
        self,
        index_path: str = "./output/faiss_2.index",
        chunks_path: str = "./output/faiss_chunks_2.pkl",
        embedding_model: str = "intfloat/multilingual-e5-large",
    ):
        print("🔄 Initializing Hybrid Retriever...")

        # Load vector store
        print(f"   Loading FAISS vector store...")
        self.vector_store = FAISSVectorStore()
        self.vector_store.load(index_path, chunks_path)

        # Load embedding model
        print(f"   Loading embedding model: {embedding_model}")
        self.embeddings = HuggingFaceEmbeddings(
            model_name=embedding_model,
            model_kwargs={"device": "cpu"},  # or 'cpu'
            encode_kwargs={"normalize_embeddings": True},
        )

        # Build chunk_id index
        print("   Building chunk_id index...")
        self.chunk_id_to_index = {
            chunk.get("chunk_id"): i
            for i, chunk in enumerate(self.vector_store.chunks)
            if chunk.get("chunk_id")
        }

        # Build BM25 index
        print("   Building BM25 index for keyword search...")
        self._build_bm25_index()

        print("✅ Hybrid Retriever ready!\n")

    def _build_bm25_index(self):
        """
        Build BM25 index với structure-aware text
        """
        corpus = []

        for chunk in self.vector_store.chunks:
            # Build text including structural info
            text = self._build_bm25_text(chunk)
            corpus.append(text)

        # Tokenize corpus
        tokenized_corpus = [self._tokenize(text) for text in corpus]

        # Build BM25 index
        self.bm25 = BM25Okapi(tokenized_corpus)

        print(f"   ✅ BM25 index built with {len(corpus)} documents")

    def _build_bm25_text(self, chunk: Dict) -> str:
        """
        Build text for BM25 indexing
        Include: structure info + title + content
        """
        meta = chunk.get("metadata", {})
        parts = []

        # Structural info (important for keyword matching)
        if meta.get("chapter"):
            parts.append(f"chương {meta['chapter']}")

        if meta.get("article"):
            parts.append(f"điều {meta['article']}")

        # Titles
        if meta.get("chapter_title"):
            parts.append(meta["chapter_title"])

        if meta.get("article_title"):
            parts.append(meta["article_title"])

        # Content
        content = chunk.get("content", "")
        parts.append(content)

        # Footnotes refs (for better matching)
        footnote_refs = meta.get("footnote_refs", [])
        if footnote_refs:
            parts.append(" ".join([f"footnote_{ref}" for ref in footnote_refs]))

        return " ".join(parts)

    def _tokenize(self, text: str) -> List[str]:
        """
        Tokenize text for BM25
        Simple word-based tokenization
        """
        # Lowercase
        text = text.lower()

        # Remove punctuation except useful ones
        text = re.sub(r"[^\w\s\-]", " ", text)

        # Split and filter
        tokens = text.split()

        # Remove very short tokens
        tokens = [t for t in tokens if len(t) > 1]

        return tokens

    def search(
        self,
        query: str,
        top_k: int = 5,
        search_mode: str = "auto",  # "auto", "hybrid", "semantic", "keyword"
        alpha: float = 0.5,  # Weight: 0=pure BM25, 1=pure semantic
        filters: Optional[Dict] = None,
        include_footnotes: bool = True,
    ) -> List[Dict]:
        """
        Hybrid search with automatic mode selection

        Args:
            query: Search query
            top_k: Number of results
            search_mode: Search strategy
                - "auto": Automatically select based on query
                - "hybrid": Combine semantic + keyword
                - "semantic": Pure semantic search (E5)
                - "keyword": Pure keyword search (BM25)
            alpha: Weight for fusion (0-1)
                - 0.0: Pure keyword (BM25)
                - 0.5: Balanced
                - 1.0: Pure semantic (E5)
            filters: Metadata filters
            include_footnotes: Include footnotes in results

        Returns:
            List of search results
        """
        try:
            # Validate
            if not query or not query.strip():
                print("   ⚠️  Empty query")
                return []

            print(f"🔍 Searching: '{query}'")

            # Preprocess query
            query = self._preprocess_query(query)

            # Determine search mode
            if search_mode == "auto":
                search_mode = self._determine_search_mode(query)
                print(f"   🎯 Auto-selected mode: {search_mode}")

            # Execute search based on mode
            if search_mode == "hybrid":
                results = self._hybrid_search(
                    query, top_k, alpha, filters, include_footnotes
                )
            elif search_mode == "semantic":
                results = self._semantic_search(
                    query, top_k, filters, include_footnotes
                )
            elif search_mode == "keyword":
                results = self._keyword_search(
                    query, top_k, filters, include_footnotes
                )
            else:
                raise ValueError(f"Unknown search_mode: {search_mode}")

            print(f"   Found {len(results)} results\n")
            return results

        except Exception as e:
            print(f"   ❌ Search error: {e}")
            import traceback

            traceback.print_exc()
            return []

    def _determine_search_mode(self, query: str) -> str:
        """
        Automatically determine search mode based on query
        """
        has_structural = self._has_structural_references(query)
        has_semantic = self._has_semantic_keywords(query)

        if has_structural and not has_semantic:
            # Pure structural: "nội dung Điều 4 chương I"
            return "hybrid"  # Hybrid works best for structural
        elif has_structural and has_semantic:
            # Mixed: "Điều 4 Tín chỉ và học phần"
            return "hybrid"
        else:
            # Pure semantic: "quy định về tín chỉ"
            return "semantic"

    def _has_structural_references(self, query: str) -> bool:
        """Check if query contains structural references"""
        patterns = [
            r"\bđiều\s+\d+\b",
            r"\bchương\s+[IVX]+\b",
            r"\bkhoản\s+\d+\b",
        ]
        return any(re.search(p, query.lower()) for p in patterns)

    def _has_semantic_keywords(self, query: str) -> bool:
        """Check if query contains meaningful semantic keywords"""
        # Remove structural references
        cleaned = re.sub(
            r"\b(điều|chương|khoản)\s+[\dIVX]+\b", "", query.lower()
        )

        # Remove common filler words
        stop_words = {"nội", "dung", "của", "về", "theo", "trong", "các"}

        meaningful_words = [
            w for w in cleaned.split() if len(w) > 2 and w not in stop_words
        ]

        return len(meaningful_words) >= 1

    def _preprocess_query(self, query: str) -> str:
        """Preprocess query"""
        # Remove extra whitespace
        query = " ".join(query.split())

        # Expand abbreviations
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

    def _hybrid_search(
        self,
        query: str,
        top_k: int,
        alpha: float,
        filters: Optional[Dict],
        include_footnotes: bool,
    ) -> List[Dict]:
        """
        Hybrid search: Reciprocal Rank Fusion (RRF)
        Combines semantic and keyword search
        """
        print(f"   Mode: Hybrid (α={alpha:.2f})")

        # Get candidates from both methods
        candidate_k = top_k * 10

        # 1. Semantic search
        semantic_results = self._get_semantic_results(query, candidate_k)

        # 2. Keyword search
        keyword_results = self._get_keyword_results(query, candidate_k)

        # 3. Reciprocal Rank Fusion
        fused_scores = self._reciprocal_rank_fusion(
            semantic_results, keyword_results, alpha
        )

        # 4. Sort by fused score
        sorted_indices = sorted(
            fused_scores.items(), key=lambda x: x[1], reverse=True
        )

        # 5. Format results with filtering
        results = []
        for idx, score in sorted_indices:
            chunk = self.vector_store.get_chunk(idx)

            # Apply filters
            if filters and not self._match_filters(chunk, filters):
                continue

            # Format result
            result = self._format_result(chunk, idx, score, include_footnotes)

            # Add score breakdown
            result["search_mode"] = "hybrid"
            result["semantic_score"] = semantic_results.get(idx, 0.0)
            result["keyword_score"] = keyword_results.get(idx, 0.0)
            result["fused_score"] = score

            results.append(result)

            if len(results) >= top_k:
                break

        return results

    def _reciprocal_rank_fusion(
        self,
        semantic_results: Dict[int, float],
        keyword_results: Dict[int, float],
        alpha: float,
        k: int = 60,  # RRF constant
    ) -> Dict[int, float]:
        """
        Reciprocal Rank Fusion
        RRF score = alpha * (1/(k + rank_semantic)) + (1-alpha) * (1/(k + rank_keyword))
        """
        # Get ranks for semantic results
        semantic_sorted = sorted(
            semantic_results.items(), key=lambda x: x[1], reverse=True
        )
        semantic_ranks = {
            idx: rank for rank, (idx, _) in enumerate(semantic_sorted)
        }

        # Get ranks for keyword results
        keyword_sorted = sorted(
            keyword_results.items(), key=lambda x: x[1], reverse=True
        )
        keyword_ranks = {
            idx: rank for rank, (idx, _) in enumerate(keyword_sorted)
        }

        # Compute RRF scores
        all_indices = set(semantic_ranks.keys()) | set(keyword_ranks.keys())

        fused_scores = {}
        for idx in all_indices:
            semantic_rrf = 1.0 / (k + semantic_ranks.get(idx, 1e9))
            keyword_rrf = 1.0 / (k + keyword_ranks.get(idx, 1e9))

            fused_scores[idx] = alpha * semantic_rrf + (1 - alpha) * keyword_rrf

        return fused_scores

    def _get_semantic_results(self, query: str, top_k: int) -> Dict[int, float]:
        """Get results from semantic search (E5)"""
        # Embed query
        query_vector = self.embeddings.embed_query(query)
        query_vector = np.array(query_vector, dtype="float32")

        # Search in FAISS
        results = self.vector_store.search(query_vector, top_k=top_k)

        # Return as dict {index: score}
        return {idx: score for idx, score in results}

    def _get_keyword_results(self, query: str, top_k: int) -> Dict[int, float]:
        """Get results from keyword search (BM25)"""
        # Tokenize query
        tokenized_query = self._tokenize(query)

        # Get BM25 scores
        scores = self.bm25.get_scores(tokenized_query)

        # Get top-k indices
        top_indices = np.argsort(scores)[::-1][:top_k]

        # Return as dict {index: score}
        return {int(idx): float(scores[idx]) for idx in top_indices}

    def _semantic_search(
        self,
        query: str,
        top_k: int,
        filters: Optional[Dict],
        include_footnotes: bool,
    ) -> List[Dict]:
        """Pure semantic search"""
        print(f"   Mode: Semantic only")

        semantic_results = self._get_semantic_results(query, top_k * 5)

        results = []
        for idx, score in sorted(
            semantic_results.items(), key=lambda x: x[1], reverse=True
        ):
            chunk = self.vector_store.get_chunk(idx)

            if filters and not self._match_filters(chunk, filters):
                continue

            result = self._format_result(chunk, idx, score, include_footnotes)
            result["search_mode"] = "semantic"
            results.append(result)

            if len(results) >= top_k:
                break

        return results

    def _keyword_search(
        self,
        query: str,
        top_k: int,
        filters: Optional[Dict],
        include_footnotes: bool,
    ) -> List[Dict]:
        """Pure keyword search"""
        print(f"   Mode: Keyword only")

        keyword_results = self._get_keyword_results(query, top_k * 5)

        results = []
        for idx, score in sorted(
            keyword_results.items(), key=lambda x: x[1], reverse=True
        ):
            chunk = self.vector_store.get_chunk(idx)

            if filters and not self._match_filters(chunk, filters):
                continue

            result = self._format_result(chunk, idx, score, include_footnotes)
            result["search_mode"] = "keyword"
            results.append(result)

            if len(results) >= top_k:
                break

        return results

    def _match_filters(self, chunk: Dict, filters: Dict) -> bool:
        """Check if chunk matches filters"""
        metadata = chunk.get("metadata", {})
        return all(metadata.get(key) == value for key, value in filters.items())

    def _format_result(
        self,
        chunk: Dict,
        idx: int,
        score: float,
        include_footnotes: bool,
    ) -> Dict:
        """Format result"""
        result = {
            "score": float(score),
            "index": idx,
            "chunk_id": chunk.get("chunk_id"),
            "chunk_type": chunk.get("chunk_type", "main_content"),
            "content": chunk.get("content"),
            "metadata": chunk.get("metadata", {}),
        }

        # Get footnotes
        if include_footnotes and chunk.get("chunk_type") == "main_content":
            footnote_refs = chunk.get("metadata", {}).get("footnote_refs", [])
            if footnote_refs:
                result["footnotes"] = self._get_footnotes(footnote_refs)

        return result

    def _get_footnotes(self, footnote_refs: List[str]) -> List[Dict]:
        """Get footnote chunks - O(1) lookup"""
        footnotes = []

        for ref in footnote_refs:
            target_chunk_id = f"footnote_{ref}"
            idx = self.chunk_id_to_index.get(target_chunk_id)

            if idx is not None:
                chunk = self.vector_store.chunks[idx]
                footnotes.append({"id": ref, "content": chunk.get("content")})

        return footnotes


# ============================================================================
# Testing
# ============================================================================


def test_hybrid_retriever():
    """Test hybrid retriever with different query types"""
    print("=" * 70)
    print("🧪 TESTING HYBRID RETRIEVER")
    print("=" * 70)
    print()

    retriever = HybridRetriever()

    test_cases = [
        {
            "query": "nội dung Điều 4 chương I",
            "top_k": 5,
            "search_mode": "auto",
            "comment": "Structural query",
        },
        {
            "query": "Điều 4 Tín chỉ và học phần",
            "top_k": 5,
            "search_mode": "auto",
            "comment": "Mixed structural + semantic",
        },
        {
            "query": "quy định về tín chỉ",
            "top_k": 5,
            "search_mode": "auto",
            "comment": "Pure semantic query",
        },
        {
            "query": "điều kiện tốt nghiệp",
            "top_k": 5,
            "search_mode": "auto",
            "comment": "Semantic query",
        },
    ]

    for i, test in enumerate(test_cases, 1):
        print(f"\n{'='*70}")
        print(f"TEST CASE {i}: {test['comment']}")
        print(f"{'='*70}")
        print(f"Query: '{test['query']}'")
        print(f"{'-'*70}\n")

        # Search
        results = retriever.search(
            query=test["query"],
            top_k=test["top_k"],
            search_mode=test["search_mode"],
        )

        # Display results
        for j, result in enumerate(results, 1):
            print(f"Result {j}:")
            print(f"  Score: {result['score']:.4f} ({result['search_mode']})")

            if "semantic_score" in result:
                print(f"    ├─ Semantic: {result['semantic_score']:.4f}")
            if "keyword_score" in result:
                print(f"    └─ Keyword: {result['keyword_score']:.4f}")

            meta = result["metadata"]
            if meta.get("chapter_full"):
                print(f"  Location: {meta['chapter_full']}")
            if meta.get("article_full"):
                print(f"            {meta['article_full']}")

            content = result["content"]
            preview = content[:150] if len(content) > 150 else content
            print(f"  Preview: {preview}...")
            print()

    print("=" * 70)
    print("✅ TESTING COMPLETED")
    print("=" * 70)


def compare_search_modes():
    """Compare different search modes"""
    print("\n" + "=" * 70)
    print("🔬 COMPARING SEARCH MODES")
    print("=" * 70)
    print()

    retriever = HybridRetriever()

    query = "nội dung Điều 4 chương I"
    modes = ["semantic", "keyword", "hybrid"]

    print(f"Query: '{query}'\n")

    for mode in modes:
        print(f"\n{'─'*70}")
        print(f"Mode: {mode.upper()}")
        print(f"{'─'*70}")

        results = retriever.search(
            query=query,
            top_k=3,
            search_mode=mode,
        )

        for i, r in enumerate(results, 1):
            print(f"{i}. Score: {r['score']:.4f}")
            print(f"   {r['metadata'].get('article_full', 'N/A')}")
            print(f"   {r['content'][:80]}...\n")


if __name__ == "__main__":
    test_hybrid_retriever()
    # compare_search_modes()
