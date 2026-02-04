"""
Hybrid Search Module
Combines BM25 (sparse/keyword) with Semantic Search (dense/embedding)

BM25 excels at:
- Exact keyword matching
- Negation queries ("không được", "không xét")
- Specific terms

Semantic Search excels at:
- Understanding meaning/intent
- Synonym matching
- Paraphrasing

Hybrid combines both for better retrieval quality.

Special handling for Vietnamese negation queries.
"""

import math
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from rank_bm25 import BM25Okapi
import re
from pyvi import ViTokenizer

from .vector_store import SearchResult


@dataclass
class HybridSearchConfig:
    """Configuration for hybrid search"""

    # Weight for semantic search (1 - this = weight for BM25)
    semantic_weight: float = 0.5  # 50% semantic + 50% BM25

    # BM25 parameters
    bm25_k1: float = 1.5  # Term frequency saturation
    bm25_b: float = 0.75  # Document length normalization

    # Tokenization
    use_word_tokenization: bool = True  # If False, use character n-grams

    # Fusion method: "weighted_sum" or "rrf" (Reciprocal Rank Fusion)
    fusion_method: str = "rrf"
    rrf_k: int = 60  # RRF constant

    # Negation boosting
    enable_negation_boost: bool = True
    negation_boost_factor: float = (
        2.0  # Multiply BM25 score for negation matches
    )


class VietnameseTokenizer:
    """
    Vietnamese tokenizer for BM25 using pyvi.
    Uses proper Vietnamese word segmentation for better accuracy.
    """

    def __init__(self):
        # Common Vietnamese stopwords
        self.stopwords = {
            "và",
            "của",
            "là",
            "có",
            "trong",
            "được",
            "các",
            "cho",
            "với",
            "theo",
            "đến",
            "từ",
            "về",
            "những",
            "này",
            "đó",
            "như",
            "hoặc",
            "tại",
            "khi",
            "nếu",
            "thì",
            "mà",
            "để",
            "sẽ",
            "đã",
            "cũng",
            "một",
            "hai",
            "ba",
            "bốn",
            "năm",
            "sáu",
            "bảy",
            "tám",
            "chín",
            "mười",
        }

    def tokenize(self, text: str) -> List[str]:
        """
        Tokenize Vietnamese text using pyvi's ViTokenizer.
        - Uses proper Vietnamese word segmentation
        - Lowercase
        - Remove stopwords (optional)
        """
        # Lowercase
        text = text.lower()

        # Use pyvi for Vietnamese word segmentation
        # ViTokenizer.tokenize returns text with underscores for compound words
        # e.g., "sinh viên" -> "sinh_viên"
        tokenized_text = ViTokenizer.tokenize(text)

        # Split by whitespace (compound words are joined with underscore)
        tokens = tokenized_text.split()

        # Remove punctuation from tokens and filter
        cleaned_tokens = []
        for token in tokens:
            # Remove punctuation but keep underscores (compound word markers)
            cleaned = re.sub(
                r"[^\w_àáảãạăắằẳẵặâấầẩẫậđèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵ]",
                "",
                token,
            )
            if len(cleaned) > 1:
                cleaned_tokens.append(cleaned)

        return cleaned_tokens


class HybridSearcher:
    """
    Hybrid search combining BM25 and semantic search results.
    """

    def __init__(self, config: Optional[HybridSearchConfig] = None):
        self.config = config or HybridSearchConfig()
        self.tokenizer = VietnameseTokenizer()
        self.bm25 = None
        self.documents = []
        self.corpus = []
        self._initialized = False

    def build_index(self, results: List[SearchResult]) -> None:
        """
        Build BM25 index from search results.
        Should be called before hybrid_search().
        """
        self.documents = results

        # Tokenize documents
        self.corpus = [self.tokenizer.tokenize(r.content) for r in results]

        # Build BM25 index
        self.bm25 = BM25Okapi(
            self.corpus, k1=self.config.bm25_k1, b=self.config.bm25_b
        )

        self._initialized = True

    def get_bm25_scores(self, query: str) -> List[float]:
        """
        Get BM25 scores for all documents.
        """
        if not self._initialized:
            raise RuntimeError("Call build_index() first")

        query_tokens = self.tokenizer.tokenize(query)
        scores = self.bm25.get_scores(query_tokens)

        return scores.tolist()

    def _detect_negation_patterns(self, query: str) -> List[Tuple[str, float]]:
        """
        Detect negation patterns in Vietnamese query.
        Returns list of (negation_phrase, boost_weight) tuples.
        More specific patterns get higher boost.
        """
        query_lower = query.lower()
        patterns = []

        # Exact phrase patterns (highest priority) - order matters
        exact_phrases = [
            # Most specific first
            ("không được xét cấp", 3.0),
            ("không xét cấp", 3.0),  # "Không xét cấp học bổng" in doc
            ("không được xét", 2.5),
            ("không xét", 2.5),
            ("không được cấp", 2.0),
            ("không cấp", 2.0),
            ("không đủ điều kiện", 2.0),
            ("bị loại", 2.0),
            ("loại trừ", 2.0),
        ]

        # Check for exact phrase matches in query
        for phrase, boost in exact_phrases:
            if phrase in query_lower:
                patterns.append((phrase, boost))

        # Also add the document-side variations that answer the query
        # E.g., query "không được xét" should match document "không xét"
        doc_variations = {
            "không được xét cấp": [("không xét cấp", 3.0), ("không xét", 2.5)],
            "không được xét": [("không xét", 2.5)],
            "không được cấp": [("không cấp", 2.0)],
        }

        for query_phrase, doc_phrases in doc_variations.items():
            if query_phrase in query_lower:
                for doc_phrase, boost in doc_phrases:
                    if (doc_phrase, boost) not in patterns:
                        patterns.append((doc_phrase, boost))

        # If no exact match, fall back to word-level negation
        if not patterns:
            if "không" in query_lower:
                patterns.append(("không", 1.5))

        return patterns

    def _apply_negation_boost(
        self, query: str, results: List[SearchResult], bm25_scores: List[float]
    ) -> List[float]:
        """
        Boost BM25 scores for documents that contain negation phrases
        when query contains negation.
        """
        if not self.config.enable_negation_boost:
            return bm25_scores

        patterns = self._detect_negation_patterns(query)
        if not patterns:
            return bm25_scores

        pattern_strs = [p[0] for p in patterns]
        print(f"   ⚡ Negation patterns detected: {pattern_strs}")

        boosted_scores = []
        for result, score in zip(results, bm25_scores):
            content_lower = result.content.lower()

            # Calculate boost based on pattern matches
            max_boost = 1.0
            matched_patterns = []

            for pattern, boost in patterns:
                if pattern in content_lower:
                    max_boost = max(max_boost, boost)
                    matched_patterns.append(pattern)

            if matched_patterns:
                boosted_score = score * max_boost
                boosted_scores.append(boosted_score)
            else:
                boosted_scores.append(score)

        return boosted_scores

    def hybrid_search(
        self, query: str, semantic_results: List[SearchResult], top_k: int = 5
    ) -> List[SearchResult]:
        """
        Perform hybrid search combining BM25 and semantic scores.

        Args:
            query: Search query
            semantic_results: Results from semantic search (with scores)
            top_k: Number of results to return

        Returns:
            Re-ranked list of SearchResult with hybrid scores
        """
        if not semantic_results:
            return []

        # Build BM25 index
        self.build_index(semantic_results)

        # Get BM25 scores
        bm25_scores = self.get_bm25_scores(query)

        # Apply negation boosting if query contains negation patterns
        bm25_scores = self._apply_negation_boost(
            query, semantic_results, bm25_scores
        )

        # Get semantic scores (already in results)
        semantic_scores = [r.score for r in semantic_results]

        # Compute hybrid scores
        if self.config.fusion_method == "rrf":
            hybrid_scores = self._rrf_fusion(semantic_scores, bm25_scores)
        else:
            hybrid_scores = self._weighted_sum_fusion(
                semantic_scores, bm25_scores
            )

        # Create new results with hybrid scores
        hybrid_results = []
        for result, bm25_score, hybrid_score in zip(
            semantic_results, bm25_scores, hybrid_scores
        ):
            hybrid_result = SearchResult(
                chunk_id=result.chunk_id,
                content=result.content,
                metadata={
                    **result.metadata,
                    "semantic_score": result.score,
                    "bm25_score": bm25_score,
                    "hybrid_score": hybrid_score,
                },
                score=hybrid_score,
            )
            hybrid_results.append(hybrid_result)

        # Sort by hybrid score (descending)
        hybrid_results.sort(key=lambda x: x.score, reverse=True)

        return hybrid_results[:top_k]

    def _normalize_scores(self, scores: List[float]) -> List[float]:
        """Min-max normalize scores to [0, 1]"""
        if not scores:
            return []

        min_s, max_s = min(scores), max(scores)
        if max_s - min_s == 0:
            return [0.5] * len(scores)

        return [(s - min_s) / (max_s - min_s) for s in scores]

    def _weighted_sum_fusion(
        self, semantic_scores: List[float], bm25_scores: List[float]
    ) -> List[float]:
        """
        Combine scores using weighted sum.
        final = α * semantic + (1-α) * bm25
        """
        # Normalize both score lists
        norm_semantic = self._normalize_scores(semantic_scores)
        norm_bm25 = self._normalize_scores(bm25_scores)

        α = self.config.semantic_weight

        return [α * s + (1 - α) * b for s, b in zip(norm_semantic, norm_bm25)]

    def _rrf_fusion(
        self, semantic_scores: List[float], bm25_scores: List[float]
    ) -> List[float]:
        """
        Reciprocal Rank Fusion (RRF).
        More robust than weighted sum, doesn't require score normalization.

        Formula: RRF(d) = Σ 1/(k + rank_i(d))
        """
        k = self.config.rrf_k
        n = len(semantic_scores)

        # Get ranks (1-indexed, higher score = lower rank)
        semantic_ranks = self._scores_to_ranks(semantic_scores)
        bm25_ranks = self._scores_to_ranks(bm25_scores)

        # Compute RRF scores
        rrf_scores = []
        for i in range(n):
            rrf = 1.0 / (k + semantic_ranks[i]) + 1.0 / (k + bm25_ranks[i])
            rrf_scores.append(rrf)

        return rrf_scores

    def _scores_to_ranks(self, scores: List[float]) -> List[int]:
        """Convert scores to ranks (1-indexed, higher score = rank 1)"""
        indexed_scores = [(i, s) for i, s in enumerate(scores)]
        sorted_scores = sorted(indexed_scores, key=lambda x: x[1], reverse=True)

        ranks = [0] * len(scores)
        for rank, (idx, _) in enumerate(sorted_scores, 1):
            ranks[idx] = rank

        return ranks


def create_hybrid_searcher(
    semantic_weight: float = 0.5, fusion_method: str = "rrf"
) -> HybridSearcher:
    """
    Factory function to create hybrid searcher.

    Args:
        semantic_weight: Weight for semantic search (0-1)
        fusion_method: "rrf" or "weighted_sum"
    """
    config = HybridSearchConfig(
        semantic_weight=semantic_weight, fusion_method=fusion_method
    )
    return HybridSearcher(config)
