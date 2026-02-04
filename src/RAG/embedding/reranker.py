"""
Reranker Module with Deduplication and Cross-Encoder
- Post-retrieval deduplication to remove duplicate parent-child content
- Cross-encoder reranking using BAAI/bge-reranker-v2-m3
"""

import torch
from typing import List, Optional, Tuple
from dataclasses import dataclass
from transformers import AutoModelForSequenceClassification, AutoTokenizer
from difflib import SequenceMatcher

from .vector_store import SearchResult


@dataclass
class RerankerConfig:
    """Configuration for reranker"""

    # Cross-encoder model
    model_name: str = "BAAI/bge-reranker-v2-m3"
    device: str = "cpu"  # "cpu" or "cuda"

    # Deduplication settings
    enable_deduplication: bool = True
    similarity_threshold: float = 0.85  # Threshold to consider as duplicate
    prefer_parent: bool = True  # When duplicate, prefer parent over child

    # Reranking settings
    enable_reranking: bool = True
    batch_size: int = 16
    max_length: int = 512

    # Search settings
    initial_top_k: int = 20  # Retrieve more for reranking
    final_top_k: int = 5  # Return after reranking

    # Score threshold - chỉ giữ documents có điểm cross-encoder >= threshold
    # Nếu None hoặc <= 0: giữ tất cả top_k documents
    # Giá trị thường dùng: 0.3-0.7 tùy theo model và dataset
    score_threshold: float = 0.7  # Chỉ giữ documents có CE score >= 0.5


class ContentDeduplicator:
    """
    Remove duplicate content from search results.
    Handles parent-child duplicates where child content is subset of parent.
    """

    def __init__(self, config: RerankerConfig):
        self.config = config

    def compute_similarity(self, text1: str, text2: str) -> float:
        """
        Compute text similarity using SequenceMatcher.
        Fast and works well for near-duplicate detection.
        """
        # Normalize texts
        text1 = text1.strip().lower()
        text2 = text2.strip().lower()

        # Quick length check - if very different lengths, likely not duplicates
        len_ratio = (
            min(len(text1), len(text2)) / max(len(text1), len(text2))
            if max(len(text1), len(text2)) > 0
            else 0
        )
        if len_ratio < 0.5:
            return len_ratio

        # Use SequenceMatcher for similarity
        return SequenceMatcher(None, text1, text2).ratio()

    def is_content_subset(self, content1: str, content2: str) -> bool:
        """
        Check if content1 is a subset (contained within) content2.
        Used to detect child content within parent.
        """
        content1_normalized = content1.strip().lower()
        content2_normalized = content2.strip().lower()

        # Check if one is substring of other
        return (
            content1_normalized in content2_normalized
            or content2_normalized in content1_normalized
        )

    def deduplicate(self, results: List[SearchResult]) -> List[SearchResult]:
        """
        Remove duplicate results based on content similarity.

        Strategy:
        1. Group results by similarity
        2. For each group, keep the best one based on:
           - Prefer parent if config.prefer_parent and similar score
           - Otherwise prefer higher score
        """
        if not self.config.enable_deduplication or len(results) <= 1:
            return results

        # Track which results to keep
        kept_results: List[SearchResult] = []
        seen_indices: set = set()

        for i, result in enumerate(results):
            if i in seen_indices:
                continue

            # Find duplicates of current result
            duplicate_group = [(i, result)]

            for j in range(i + 1, len(results)):
                if j in seen_indices:
                    continue

                other = results[j]

                # Check similarity
                similarity = self.compute_similarity(
                    result.content, other.content
                )
                is_subset = self.is_content_subset(
                    result.content, other.content
                )

                if similarity >= self.config.similarity_threshold or is_subset:
                    duplicate_group.append((j, other))
                    seen_indices.add(j)

            # Select best from duplicate group
            best_result = self._select_best_from_group(duplicate_group)
            kept_results.append(best_result)
            seen_indices.add(i)

        return kept_results

    def _select_best_from_group(
        self, group: List[Tuple[int, SearchResult]]
    ) -> SearchResult:
        """
        Select the best result from a group of duplicates.

        Priority:
        1. If prefer_parent and scores are similar: pick parent
        2. Otherwise: pick highest score
        3. If same score and level: pick longer content (more context)
        """
        if len(group) == 1:
            return group[0][1]

        # Separate parents and children
        parents = [
            (idx, r) for idx, r in group if r.metadata.get("level") == "parent"
        ]
        children = [
            (idx, r) for idx, r in group if r.metadata.get("level") == "child"
        ]

        # If prefer_parent and we have parents
        if self.config.prefer_parent and parents:
            # Get the parent with highest score
            best_parent = max(parents, key=lambda x: x[1].score)

            # Check if parent score is close to best child score
            if children:
                best_child = max(children, key=lambda x: x[1].score)
                score_diff = abs(best_parent[1].score - best_child[1].score)

                # If scores are similar (within 0.05), prefer parent
                if score_diff <= 0.05:
                    return best_parent[1]
                # If child has significantly higher score, use child
                elif best_child[1].score > best_parent[1].score:
                    return best_child[1]

            return best_parent[1]

        # Default: return highest score
        return max(group, key=lambda x: x[1].score)[1]


class CrossEncoderReranker:
    """
    Cross-encoder reranker using BAAI/bge-reranker-v2-m3.
    More accurate than bi-encoder but slower (needs pair-wise scoring).
    """

    def __init__(self, config: RerankerConfig):
        self.config = config
        self.model = None
        self.tokenizer = None
        self.cross_encoder = None  # sentence-transformers CrossEncoder
        self._initialized = False

    def _lazy_init(self):
        """Lazy initialization to avoid loading model if not needed"""
        if self._initialized:
            return

        try:
            print(f"🔄 Loading cross-encoder model: {self.config.model_name}")
            print(f"   This may take a few minutes on first load...")

            # Use sentence-transformers instead which is more stable
            from sentence_transformers import CrossEncoder

            print(f"   Using CrossEncoder from sentence-transformers...")
            self.cross_encoder = CrossEncoder(
                self.config.model_name,
                max_length=self.config.max_length,
                device=self.config.device,
            )

            self._initialized = True
            print(f"✅ Cross-encoder loaded on {self.config.device}")

        except Exception as e:
            print(f"❌ Error loading cross-encoder: {e}")
            print(f"   Trying fallback with transformers...")

            try:
                self.tokenizer = AutoTokenizer.from_pretrained(
                    self.config.model_name, trust_remote_code=True
                )

                print(f"   ✓ Tokenizer loaded")

                self.model = AutoModelForSequenceClassification.from_pretrained(
                    self.config.model_name, trust_remote_code=True
                )

                print(f"   ✓ Model loaded")

                # Move to device
                device = torch.device(self.config.device)
                self.model = self.model.to(device)
                self.model.eval()

                self._initialized = True
                self.cross_encoder = None  # Flag to use manual method
                print(f"✅ Cross-encoder loaded on {self.config.device}")

            except Exception as e2:
                print(f"❌ Error loading cross-encoder: {e2}")
                print(f"   Disabling reranking")
                self.config.enable_reranking = False
                self._initialized = False
                raise

    def compute_scores(self, query: str, documents: List[str]) -> List[float]:
        """
        Compute relevance scores for query-document pairs.

        Args:
            query: The search query
            documents: List of document contents

        Returns:
            List of relevance scores (higher = more relevant)
        """
        self._lazy_init()

        if not documents:
            return []

        # Use sentence-transformers CrossEncoder if available (faster)
        if hasattr(self, "cross_encoder") and self.cross_encoder is not None:
            pairs = [[query, doc] for doc in documents]
            scores = self.cross_encoder.predict(pairs, show_progress_bar=False)
            return (
                scores.tolist() if hasattr(scores, "tolist") else list(scores)
            )

        # Fallback to manual method
        device = torch.device(self.config.device)
        scores = []

        # Process in batches
        for i in range(0, len(documents), self.config.batch_size):
            batch_docs = documents[i : i + self.config.batch_size]

            # Create pairs
            pairs = [[query, doc] for doc in batch_docs]

            # Tokenize
            with torch.no_grad():
                inputs = self.tokenizer(
                    pairs,
                    padding=True,
                    truncation=True,
                    max_length=self.config.max_length,
                    return_tensors="pt",
                ).to(device)

                # Get scores
                outputs = self.model(**inputs)
                batch_scores = outputs.logits.squeeze(-1).cpu().tolist()

                # Handle single item case
                if isinstance(batch_scores, float):
                    batch_scores = [batch_scores]

                scores.extend(batch_scores)

        return scores

    def rerank(
        self, query: str, results: List[SearchResult]
    ) -> List[SearchResult]:
        """
        Rerank search results using cross-encoder.

        Args:
            query: The search query
            results: List of SearchResult from initial retrieval

        Returns:
            Reranked list of SearchResult with updated scores
        """
        if not self.config.enable_reranking or len(results) <= 1:
            return results

        # Extract documents
        documents = [r.content for r in results]

        # Compute cross-encoder scores
        ce_scores = self.compute_scores(query, documents)

        # Update results with new scores and sort
        reranked_results = []
        for result, ce_score in zip(results, ce_scores):
            # Create new result with cross-encoder score
            reranked_result = SearchResult(
                chunk_id=result.chunk_id,
                content=result.content,
                metadata={
                    **result.metadata,
                    "original_score": result.score,  # Keep original score
                    "ce_score": ce_score,  # Cross-encoder score
                },
                score=ce_score,  # Use CE score for ranking
            )
            reranked_results.append(reranked_result)

        # Sort by cross-encoder score (descending)
        reranked_results.sort(key=lambda x: x.score, reverse=True)

        return reranked_results


class RerankerPipeline:
    """
    Complete reranking pipeline:
    1. Deduplicate results
    2. Rerank with cross-encoder
    3. Return top-k
    """

    def __init__(self, config: Optional[RerankerConfig] = None):
        self.config = config or RerankerConfig()
        self.deduplicator = ContentDeduplicator(self.config)
        self.reranker = CrossEncoderReranker(self.config)

        print(f"✅ Initialized RerankerPipeline")
        print(f"   Deduplication: {self.config.enable_deduplication}")
        print(f"   Reranking: {self.config.enable_reranking}")
        if self.config.enable_reranking:
            print(f"   Model: {self.config.model_name}")

    def process(
        self,
        query: str,
        results: List[SearchResult],
        top_k: Optional[int] = None,
        score_threshold: Optional[float] = None,
    ) -> List[SearchResult]:
        """
        Process search results: deduplicate, rerank, and filter by score.

        Args:
            query: The search query
            results: Initial search results
            top_k: Maximum number of results to return (default from config)
            score_threshold: Minimum cross-encoder score to keep (default from config)
                           Set to None or 0 to keep all top_k results

        Returns:
            Processed list of SearchResult (có thể ít hơn top_k nếu filter theo score)
        """
        top_k = top_k or self.config.final_top_k
        threshold = (
            score_threshold
            if score_threshold is not None
            else self.config.score_threshold
        )

        # Step 1: Deduplicate
        if self.config.enable_deduplication:
            deduped_results = self.deduplicator.deduplicate(results)
            removed_count = len(results) - len(deduped_results)
            if removed_count > 0:
                print(
                    f"🔄 Deduplication: {len(results)} → {len(deduped_results)} (removed {removed_count} duplicates)"
                )
        else:
            deduped_results = results

        # Step 2: Rerank with cross-encoder
        if self.config.enable_reranking:
            print(
                f"🔄 Reranking {len(deduped_results)} results with cross-encoder..."
            )
            reranked_results = self.reranker.rerank(query, deduped_results)
        else:
            reranked_results = deduped_results

        # Step 3: Filter by score threshold (chỉ áp dụng nếu đã rerank với cross-encoder)
        if self.config.enable_reranking and threshold and threshold > 0:
            filtered_results = [
                r for r in reranked_results if r.score >= threshold
            ]
            filtered_count = len(reranked_results) - len(filtered_results)

            # Đảm bảo luôn có ít nhất 1 document (document có điểm cao nhất)
            # Điều này quan trọng để hệ thống luôn trả về kết quả cho user
            if len(filtered_results) == 0 and len(reranked_results) > 0:
                # Giữ document có điểm cao nhất (đã sort theo score descending)
                filtered_results = [reranked_results[0]]
                print(
                    f"🔄 Score filter (threshold={threshold}): All docs below threshold, keeping top 1 (score={reranked_results[0].score:.4f})"
                )
            elif filtered_count > 0:
                print(
                    f"🔄 Score filter (threshold={threshold}): {len(reranked_results)} → {len(filtered_results)} (removed {filtered_count} low-score docs)"
                )
            reranked_results = filtered_results

        # Step 4: Return top-k (có thể ít hơn nếu đã filter)
        return reranked_results[:top_k]


# Convenience function
def create_reranker(
    model_name: str = "BAAI/bge-reranker-v2-m3",
    device: str = "cpu",
    enable_deduplication: bool = True,
    enable_reranking: bool = True,
    score_threshold: float = 0.5,
) -> RerankerPipeline:
    """
    Factory function to create reranker pipeline.

    Args:
        model_name: Cross-encoder model name
        device: Device to use ("cpu" or "cuda")
        enable_deduplication: Whether to deduplicate results
        enable_reranking: Whether to rerank with cross-encoder
        score_threshold: Minimum cross-encoder score to keep documents
                        Set to 0 or None to keep all top_k results

    Returns:
        RerankerPipeline instance
    """
    config = RerankerConfig(
        model_name=model_name,
        device=device,
        enable_deduplication=enable_deduplication,
        enable_reranking=enable_reranking,
        score_threshold=score_threshold,
    )
    return RerankerPipeline(config)
