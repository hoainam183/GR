"""Domain Classifier — lightweight embedding-based intent + domain classifier.

Architecture (Tier 1 + 2):
- **Multi-label**: ``OneVsRestClassifier(LogisticRegression)`` via sklearn.
  Each domain has an independent binary classifier, so a query can activate
  multiple collections simultaneously.
- **Platt scaling**: ``CalibratedClassifierCV(ovr_clf, cv='prefit',
  method='sigmoid')`` fitted on a held-out validation split makes predicted
  probabilities meaningful (0.7 really means ~70% confidence).
- **Persistence**: model file stores ``{"classifier": ..., "mlb": ...}`` so
  the ``MultiLabelBinarizer`` (class ordering) travels with the weights.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.multiclass import OneVsRestClassifier
from sklearn.preprocessing import MultiLabelBinarizer

from .training_data import RAG_LABELS

logger = logging.getLogger(__name__)

# ─── Constants ──────────────────────────────────────────────────────────────────
_DEFAULT_MODEL_DIR = Path(__file__).parent / "models"
_DEFAULT_MODEL_PATH = _DEFAULT_MODEL_DIR / "domain_classifier.joblib"

# A RAG-domain probability must exceed this threshold to be included in the
# active-domains list.  Lower than 0.5 because the binary classifiers in OvR
# are independent and the "true" threshold is dataset-dependent.
MULTI_LABEL_THRESHOLD: float = 0.35

# If the maximum RAG-domain probability stays below this value the router
# marks the result as low-confidence (triggers Tier-3 LLM fallback).
LOW_CONFIDENCE_CEILING: float = 0.55


class DomainClassifier:
    """Multi-label embedding-based domain + intent classifier.

    Labels: ``chitchat``, ``tool_search``, ``ctdt``, ``quydinh``,
    ``kehoach``, ``stsv``.

    A query can return **multiple** RAG domains when it genuinely spans more
    than one (e.g. "ngành CNTT học gì và học phí thế nào?" → ctdt + quydinh).

    Parameters:
        embedder: An embedder instance with ``embed(texts)`` and
                  ``embed_query(text)`` methods.  Lazy-loads BGEm3Embedder
                  when *None*.
    """

    def __init__(self, embedder: Optional[Any] = None) -> None:
        self._embedder = embedder
        self._classifier: Optional[Any] = None  # CalibratedClassifierCV(OvR)
        self._mlb: Optional[MultiLabelBinarizer] = None

    # ------------------------------------------------------------------
    # Embedder (lazy-load)
    # ------------------------------------------------------------------

    @property
    def embedder(self) -> Any:
        if self._embedder is None:
            from embedding.bge_m3 import BGEm3Embedder

            logger.info("DomainClassifier: lazy-loading BGEm3Embedder …")
            self._embedder = BGEm3Embedder()
        return self._embedder

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def train(
        self,
        data: List[Tuple[str, List[str]]],
        test_size: float = 0.2,
        val_size: float = 0.15,
        random_state: int = 42,
    ) -> Dict[str, Any]:
        """Embed training queries, fit OvR + calibrate, return eval report.

        Args:
            data: List of ``(query, [label, ...])`` tuples.  Single-label
                  samples have a one-element list.
            test_size: Fraction held out for final evaluation.
            val_size: Fraction (of remaining data) used for Platt scaling.
            random_state: Seed for reproducibility.

        Returns:
            Dict with ``accuracy``, ``report``, ``report_dict``.
        """
        texts, labels = zip(*data)
        texts = list(texts)
        labels = list(labels)

        logger.info("Embedding %d training samples …", len(texts))
        embeddings = np.array(self.embedder.embed(texts))

        # ── Binarize labels ──────────────────────────────────────────────
        self._mlb = MultiLabelBinarizer()
        y_all = self._mlb.fit_transform(labels)
        logger.info("Classes: %s", list(self._mlb.classes_))

        # ── Train / val / test split ─────────────────────────────────────
        # Split off test set first, then split remaining into train/val.
        X_trainval, X_test, y_trainval, y_test = train_test_split(
            embeddings,
            y_all,
            test_size=test_size,
            random_state=random_state,
        )
        X_train, X_val, y_train, y_val = train_test_split(
            X_trainval,
            y_trainval,
            test_size=val_size,
            random_state=random_state,
        )

        logger.info(
            "Split — train=%d  val=%d  test=%d",
            len(X_train),
            len(X_val),
            len(X_test),
        )

        # ── Fit base OvR classifier ──────────────────────────────────────
        ovr_clf = OneVsRestClassifier(
            LogisticRegression(
                max_iter=1000,
                C=1.0,
                solver="lbfgs",
                random_state=random_state,
            )
        )
        ovr_clf.fit(X_train, y_train)

        # ── Platt scaling (Tier 1) ───────────────────────────────────────
        # CalibratedClassifierCV with cv='prefit' calibrates on X_val / y_val.
        # Each binary OvR sub-classifier's probability is re-scaled via a
        # sigmoid so that predicted_proba reflects true empirical frequencies.
        try:
            calibrated = CalibratedClassifierCV(
                ovr_clf, cv="prefit", method="sigmoid"
            )
            calibrated.fit(X_val, y_val)
            self._classifier = calibrated
            logger.info("Platt scaling applied successfully.")
        except Exception as exc:  # pragma: no cover
            logger.warning(
                "Platt scaling failed (%s) — using uncalibrated OvR.", exc
            )
            self._classifier = ovr_clf

        # ── Evaluation ──────────────────────────────────────────────────
        y_pred = self._classifier.predict(X_test)
        report_str = classification_report(
            y_test,
            y_pred,
            target_names=list(self._mlb.classes_),
            zero_division=0,
        )
        report_dict = classification_report(
            y_test,
            y_pred,
            target_names=list(self._mlb.classes_),
            output_dict=True,
            zero_division=0,
        )
        accuracy = float(
            report_dict.get("samples avg", {}).get("f1-score", 0.0)
        )

        logger.info("Training complete — samples F1=%.4f", accuracy)
        return {
            "accuracy": accuracy,
            "report": report_str,
            "report_dict": report_dict,
        }

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------

    def predict(self, query: str) -> Dict[str, Any]:
        """Classify a single query (multi-label aware).

        Returns:
            Dict with keys:

            - ``label``: primary predicted label (string)
            - ``intent``: ``"rag"`` | ``"chitchat"`` | ``"tool_search"``
            - ``domain``: primary RAG domain or *None*
            - ``domains``: list of all active RAG domains (may be >1)
            - ``confidence``: calibrated probability of the primary label
            - ``probabilities``: dict mapping every class to its probability
        """
        if self._classifier is None or self._mlb is None:
            raise RuntimeError(
                "Classifier not trained or loaded. "
                "Call train() or load() first."
            )

        vec = np.array(self.embedder.embed_query(query)).reshape(1, -1)

        # predict_proba → shape (1, n_classes); each value is independent P(class)
        proba_matrix = self._classifier.predict_proba(vec)
        proba_row = proba_matrix[0]
        classes: List[str] = list(self._mlb.classes_)

        probabilities = {cls: float(p) for cls, p in zip(classes, proba_row)}

        # ── Check non-RAG labels ────────────────────────────────────────
        chitchat_prob = probabilities.get("chitchat", 0.0)
        tool_search_prob = probabilities.get("tool_search", 0.0)
        best_non_rag = max(chitchat_prob, tool_search_prob)

        # Non-RAG wins when it dominates the highest RAG probability.
        rag_probs = {
            cls: p for cls, p in probabilities.items() if cls in RAG_LABELS
        }
        best_rag_prob = max(rag_probs.values()) if rag_probs else 0.0

        if best_non_rag > 0.6 and best_non_rag >= best_rag_prob:
            label = (
                "chitchat"
                if chitchat_prob >= tool_search_prob
                else "tool_search"
            )
            return {
                "label": label,
                "intent": label,
                "domain": None,
                "domains": [],
                "confidence": best_non_rag,
                "probabilities": probabilities,
            }

        # ── Collect active RAG domains ──────────────────────────────────
        active_domains = [
            cls for cls, p in rag_probs.items() if p >= MULTI_LABEL_THRESHOLD
        ]

        # If nothing clears the threshold, fall back to the single best RAG
        if not active_domains and rag_probs:
            best_rag = max(rag_probs, key=rag_probs.get)  # type: ignore[arg-type]
            active_domains = [best_rag]

        # Sort by probability (primary domain = highest probability)
        active_domains.sort(key=lambda c: rag_probs.get(c, 0.0), reverse=True)
        primary_domain = active_domains[0] if active_domains else None
        confidence = (
            rag_probs.get(primary_domain, 0.0) if primary_domain else 0.0
        )

        return {
            "label": primary_domain or "chitchat",
            "intent": "rag" if active_domains else "chitchat",
            "domain": primary_domain,
            "domains": active_domains,
            "confidence": confidence,
            "probabilities": probabilities,
        }

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: Optional[str] = None) -> Path:
        """Save classifier + MLB to disk as a single joblib file."""
        if self._classifier is None or self._mlb is None:
            raise RuntimeError("No trained classifier to save.")

        save_path = Path(path) if path else _DEFAULT_MODEL_PATH
        save_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {"classifier": self._classifier, "mlb": self._mlb}, save_path
        )
        logger.info("Classifier saved to %s", save_path)
        return save_path

    def load(self, path: Optional[str] = None) -> None:
        """Load a previously trained classifier from disk.

        Supports both the new dict format ``{"classifier": ..., "mlb": ...}``
        and the legacy format (bare sklearn model) for backward compatibility.
        """
        load_path = Path(path) if path else _DEFAULT_MODEL_PATH
        if not load_path.exists():
            raise FileNotFoundError(f"No model file at {load_path}")

        data = joblib.load(load_path)
        if isinstance(data, dict):
            self._classifier = data["classifier"]
            self._mlb = data.get("mlb")
        else:
            # Legacy: bare LogisticRegression — rebuild a minimal MLB from classes_
            logger.warning(
                "Loading legacy single-label model from %s. "
                "Re-train to get multi-label support.",
                load_path,
            )
            self._classifier = data
            # Reconstruct MLB from the classifier's known classes
            from .training_data import ALL_LABELS

            self._mlb = MultiLabelBinarizer(classes=ALL_LABELS)
            self._mlb.fit([[lbl] for lbl in ALL_LABELS])

        logger.info("Classifier loaded from %s", load_path)
