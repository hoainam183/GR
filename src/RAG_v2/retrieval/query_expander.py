"""Multi-Query Expansion — generate query variants for improved recall.

Given a (possibly reflected) query and extracted entities, produces 2-3
search-optimized query variants.  Results from all variants are merged
before reranking, increasing the chance of capturing relevant chunks that
a single query formulation would miss.

Usage::

    from retrieval.query_expander import MultiQueryExpander

    expander = MultiQueryExpander()
    variants = expander.expand(
        query="điều kiện tốt nghiệp ngành IT-E6",
        entities={"major_code": "IT-E6"},
    )
    # → ["điều kiện tốt nghiệp ngành IT-E6",
    #    "IT-E6 tốt nghiệp yêu cầu",
    #    "điều kiện tốt nghiệp"]
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Words that rarely add retrieval value when standing alone
_FILLER_WORDS = {
    "cho", "của", "với", "về", "trong", "là", "gì", "như", "thế", "nào",
    "có", "những", "các", "được", "và", "hoặc", "hay", "bao", "nhiêu",
    "tôi", "mình", "em", "bạn", "ơi", "vui", "lòng", "xin", "hãy",
    "muốn", "cần", "hỏi", "biết", "tìm", "hiểu", "xem",
}

_ENTITY_KEYS = ("major_code", "cohort", "course_code", "academic_year", "semester")


class MultiQueryExpander:
    """Produces multiple query variants to improve retrieval recall.

    Strategies:
      1. **Original** — the reflected query as-is (best precision).
      2. **Entity-focused** — key entities concatenated (captures exact-match BM25).
      3. **Topic-only** — original minus entity mentions (broader semantic coverage).

    Parameters:
        max_variants: Maximum number of query variants to return (2-4).
    """

    def __init__(self, max_variants: int = 3) -> None:
        self.max_variants = max(2, min(max_variants, 4))

    def expand(
        self,
        query: str,
        entities: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """Generate query variants.

        Args:
            query: The reflected/rewritten query string.
            entities: Extracted entities dict from the query analysis step.
                Keys: major_code, cohort, course_code, academic_year, semester.

        Returns:
            List of 1-3 unique query strings (original is always first).
        """
        if not query or not query.strip():
            return [query] if query else []

        query = query.strip()
        variants: List[str] = [query]
        entities = entities or {}

        # Strategy 2: Entity-focused query
        entity_query = self._build_entity_query(query, entities)
        if entity_query and entity_query != query:
            variants.append(entity_query)

        # Strategy 3: Topic-only query (strip entities for broader semantic match)
        topic_query = self._build_topic_query(query, entities)
        if topic_query and topic_query != query and topic_query not in variants:
            variants.append(topic_query)

        return variants[: self.max_variants]

    def _build_entity_query(
        self,
        query: str,
        entities: Dict[str, Any],
    ) -> Optional[str]:
        """Build a short entity-centric query for BM25 matching."""
        parts: List[str] = []

        for key in _ENTITY_KEYS:
            val = entities.get(key)
            if val and isinstance(val, str) and val.strip():
                parts.append(val.strip())

        if not parts:
            return None

        # Extract core topic words (non-filler, non-entity) from original query
        topic_words = self._extract_topic_words(query, entities)
        if topic_words:
            parts.extend(topic_words[:4])

        return " ".join(parts)

    def _build_topic_query(
        self,
        query: str,
        entities: Dict[str, Any],
    ) -> Optional[str]:
        """Build a topic-only query by stripping entity values."""
        cleaned = query
        for key in _ENTITY_KEYS:
            val = entities.get(key)
            if val and isinstance(val, str) and val.strip():
                # Remove the entity value from the query
                cleaned = re.sub(
                    rf"\b{re.escape(val.strip())}\b",
                    " ",
                    cleaned,
                    flags=re.IGNORECASE,
                )

        # Also strip common structural phrases around entities
        cleaned = re.sub(
            r"\b(?:ngành|chuyên\s+ngành|chương\s+trình|khóa|khoá)\b",
            " ",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" ,.;:-()[]")

        if len(cleaned.split()) < 2:
            return None

        return cleaned

    @staticmethod
    def _extract_topic_words(query: str, entities: Dict[str, Any]) -> List[str]:
        """Extract meaningful topic words (not fillers, not entity values)."""
        entity_values = set()
        for key in _ENTITY_KEYS:
            val = entities.get(key)
            if val and isinstance(val, str):
                entity_values.update(val.lower().split())

        words = re.findall(r"\w+", query.lower())
        topic = [
            w for w in words
            if w not in _FILLER_WORDS and w not in entity_values and len(w) > 1
        ]
        return topic
