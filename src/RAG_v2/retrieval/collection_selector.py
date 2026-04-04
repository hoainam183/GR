"""Collection Selector — choose target collections based on domain classification."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ─── Domain → Collection mapping ────────────────────────────────────────────────
DOMAIN_TO_COLLECTIONS: Dict[str, List[str]] = {
    "ctdt": ["ctdt"],
    "quydinh": ["quydinh"],
    "kehoach": ["kehoach"],
    "stsv": ["stsv"],
}

ALL_COLLECTIONS: List[str] = ["stsv", "quydinh", "kehoach", "ctdt"]
MULTI_DOMAIN_FALLBACK: List[str] = ["quydinh", "stsv"]

CONFIDENCE_THRESHOLD: float = 0.65


class CollectionSelector:
    """Selects target Qdrant/ES collections based on domain classification result.

    Parameters:
        confidence_threshold: Minimum confidence to trust the domain prediction.
        fallback_collections: Collections used when confidence is below threshold.
        all_collections: Full list of available collections.
    """

    def __init__(
        self,
        confidence_threshold: float = CONFIDENCE_THRESHOLD,
        fallback_collections: Optional[List[str]] = None,
        all_collections: Optional[List[str]] = None,
    ) -> None:
        self.confidence_threshold = confidence_threshold
        self.fallback_collections = (
            fallback_collections or MULTI_DOMAIN_FALLBACK
        )
        self.all_collections = all_collections or ALL_COLLECTIONS

    def select(
        self,
        domain: Optional[str],
        confidence: float = 0.0,
    ) -> List[str]:
        """Return the list of collections to search.

        Args:
            domain: Domain label from ``DomainClassifier`` (e.g. ``"quydinh"``).
                    *None* means no domain was determined.
            confidence: Classification confidence score (0–1).

        Returns:
            List of collection name strings.
        """
        if domain is None:
            logger.info(
                "CollectionSelector: domain=None → searching all %d collections",
                len(self.all_collections),
            )
            return list(self.all_collections)

        if confidence < self.confidence_threshold:
            logger.info(
                "CollectionSelector: domain=%s conf=%.3f < threshold=%.3f "
                "→ fallback collections: %s",
                domain,
                confidence,
                self.confidence_threshold,
                self.fallback_collections,
            )
            return list(self.fallback_collections)

        target = DOMAIN_TO_COLLECTIONS.get(domain)
        if target is None:
            logger.warning(
                "CollectionSelector: unknown domain=%s → searching all collections",
                domain,
            )
            return list(self.all_collections)

        logger.info(
            "CollectionSelector: domain=%s conf=%.3f → collections: %s",
            domain,
            confidence,
            target,
        )
        return list(target)
