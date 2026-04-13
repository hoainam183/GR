"""Collection Selector — choose target collections based on domain classification."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

# ─── Domain → Collection mapping ────────────────────────────────────────────────
DOMAIN_TO_COLLECTIONS: Dict[str, List[str]] = {
    "ctdt": ["ctdt"],
    "quydinh": ["quydinh"],
    "kehoach": ["kehoach"],
    "stsv": ["stsv"],
}

ALL_COLLECTIONS: List[str] = ["stsv", "quydinh", "kehoach", "ctdt"]
# Include curriculum collection in low-confidence fallback so course queries
# still retrieve ctdt chunks when router confidence is borderline.
MULTI_DOMAIN_FALLBACK: List[str] = ["quydinh", "stsv", "ctdt"]

CONFIDENCE_THRESHOLD: float = 0.55  # Tier-1 calibration makes this meaningful


class CollectionSelector:
    """Selects target Qdrant/ES collections based on domain classification result.

    Supports both single-domain (``domain: str``) and multi-domain
    (``domains: List[str]``) inputs from the router.  When multiple domains
    are active, the returned collections are the union of all mapped collections.

    Parameters:
        confidence_threshold: Minimum confidence to trust the domain prediction.
        fallback_collections: Collections used when confidence is below threshold
                              AND the LLM fallback is not available.
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
        domain: Optional[Union[str, List[str]]] = None,
        confidence: float = 0.0,
        domains: Optional[List[str]] = None,
    ) -> List[str]:
        """Return the list of collections to search.

        Accepts either the legacy ``domain`` (single string) interface or the
        new ``domains`` (list of strings) interface.  When ``domains`` is
        provided it takes precedence over ``domain``.

        Args:
            domain: Primary domain label from ``DomainClassifier`` or a list
                    of domain labels (backward-compatible overload).
            confidence: Calibrated classification confidence (0–1).
            domains: Explicit list of active domains (Tier-2 multi-label).

        Returns:
            List of collection name strings (order preserved, duplicates removed).
        """
        # Normalise: prefer explicit `domains` list, otherwise fall back to
        # `domain` which may itself be a string or list.
        active_domains: List[str]
        if domains is not None:
            active_domains = [d for d in domains if d]
        elif isinstance(domain, list):
            active_domains = [d for d in domain if d]
        elif domain:
            active_domains = [domain]
        else:
            active_domains = []

        if not active_domains:
            logger.info(
                "CollectionSelector: no domain → searching all %d collections",
                len(self.all_collections),
            )
            return list(self.all_collections)

        if confidence < self.confidence_threshold:
            logger.info(
                "CollectionSelector: domains=%s conf=%.3f < threshold=%.3f "
                "→ fallback collections: %s",
                active_domains,
                confidence,
                self.confidence_threshold,
                self.fallback_collections,
            )
            return list(self.fallback_collections)

        # Resolve each domain to its collection(s) and take the union
        seen: set = set()
        target: List[str] = []
        for dom in active_domains:
            cols = DOMAIN_TO_COLLECTIONS.get(dom)
            if cols is None:
                logger.warning(
                    "CollectionSelector: unknown domain=%s → skipping", dom
                )
                continue
            for col in cols:
                if col not in seen:
                    seen.add(col)
                    target.append(col)

        if not target:
            logger.warning(
                "CollectionSelector: could not resolve domains=%s "
                "→ searching all collections",
                active_domains,
            )
            return list(self.all_collections)

        logger.info(
            "CollectionSelector: domains=%s conf=%.3f → collections: %s",
            active_domains,
            confidence,
            target,
        )
        return target
