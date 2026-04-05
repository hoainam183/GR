"""Domain Classifier — two-stage embedding-based intent + domain classifier.

Architecture (v3 — fixes tool_search = 0% F1):

- **Stage 1 (Intent)**: ``CalibratedClassifierCV(LogisticRegression, cv=5)``
  trained on *all* data → predicts one of {chitchat, rag, tool_search}.
  Using cv=5 instead of a separate val split avoids wasting data on small
  datasets and keeps probability calibration reliable.

- **Stage 2 (Domain, only when Stage 1 → rag)**:
  ``OneVsRestClassifier(LogisticRegression)`` trained exclusively on
  RAG-labeled samples → predicts any subset of {ctdt, quydinh, kehoach, stsv}.
  LogisticRegression's built-in sigmoid output is already reasonably calibrated
  for balanced binary sub-problems; no extra Platt step is needed.

Root cause of the v2 failure:
  The previous single-model OvR placed chitchat/tool_search alongside RAG
  domains in one binarised space. The tool_search binary classifier's probability
  rarely exceeded the hard-coded 0.6 non-RAG cutoff because its 12% base-rate
  depressed the calibrated output. Separating intent from domain gives each
  sub-classifier a focused task with balanced class priors.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.multiclass import OneVsRestClassifier
from sklearn.preprocessing import MultiLabelBinarizer

from .training_data import RAG_LABELS

logger = logging.getLogger(__name__)

# ─── Constants ──────────────────────────────────────────────────────────────────
_DEFAULT_MODEL_DIR = Path(__file__).parent / "models"
_DEFAULT_MODEL_PATH = _DEFAULT_MODEL_DIR / "domain_classifier.joblib"

# Stage-2 OvR: a domain is "active" when its binary probability exceeds this.
MULTI_LABEL_THRESHOLD: float = 0.35

# When Stage-2 primary domain probability is below this, the Tier-3 LLM
# fallback in rag_pipeline is triggered.
LOW_CONFIDENCE_CEILING: float = 0.55


class DomainClassifier:
    """Two-stage multi-label domain + intent classifier.

    Stage 1: ``CalibratedClassifierCV(LogisticRegression, cv=5)``
             → {chitchat, rag, tool_search}

    Stage 2 (runs only when Stage 1 → "rag"):
             ``OneVsRestClassifier(LogisticRegression)``
             → any subset of {ctdt, quydinh, kehoach, stsv}

    Parameters:
        embedder: An embedder with ``embed(texts)`` and ``embed_query(text)``.
                  Lazy-loads ``BGEm3Embedder`` when *None*.
    """

    def __init__(self, embedder: Optional[Any] = None) -> None:
        self._embedder = embedder
        self._intent_clf: Optional[Any] = (
            None  # Stage 1 — 3-class calibrated LR
        )
        self._domain_clf: Optional[Any] = None  # Stage 2 — OvR LR on RAG subset
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
        random_state: int = 42,
    ) -> Dict[str, Any]:
        """Embed, fit both stages, and return evaluation report.

        Args:
            data: List of ``(query, [label, ...])`` tuples.  Single-label
                  samples have a one-element list.
            test_size: Fraction held out for evaluation.
            random_state: Reproducibility seed.

        Returns:
            Dict with ``accuracy`` (Stage-1 intent accuracy), ``domain_f1``
            (Stage-2 samples F1 on RAG subset), ``report``, ``report_dict``.
        """
        texts = [q for q, _ in data]
        labels_list = [ls for _, ls in data]

        # ── Derive intent labels (single-label per sample) ───────────────────
        # Any sample with at least one RAG label → intent "rag"; otherwise the
        # single non-RAG label (chitchat or tool_search) is used directly.
        intent_labels: List[str] = [
            "rag" if any(lbl in RAG_LABELS for lbl in lbls) else lbls[0]
            for lbls in labels_list
        ]

        logger.info("Embedding %d samples …", len(texts))
        embeddings = np.array(self.embedder.embed(texts))

        # ── Stratified train/test split (by intent) ──────────────────────────
        indices = np.arange(len(data))
        train_idx, test_idx = train_test_split(
            indices,
            test_size=test_size,
            random_state=random_state,
            stratify=intent_labels,
        )
        X_train = embeddings[train_idx]
        X_test = embeddings[test_idx]
        intent_train = [intent_labels[i] for i in train_idx]
        intent_test = [intent_labels[i] for i in test_idx]

        n_rag_train = sum(1 for l in intent_train if l == "rag")
        logger.info(
            "Split — train=%d (RAG=%d)  test=%d",
            len(train_idx),
            n_rag_train,
            len(test_idx),
        )

        # ── Stage 1: Intent classifier (3-class, cv=5 calibrated) ────────────
        logger.info("Stage 1: training intent classifier (cv=5 calibration) …")
        intent_base = LogisticRegression(
            max_iter=1000, C=1.0, solver="lbfgs", random_state=random_state
        )
        # cv=5 avoids a separate validation split and provides stable calibration.
        self._intent_clf = CalibratedClassifierCV(
            intent_base, cv=5, method="sigmoid"
        )
        self._intent_clf.fit(X_train, intent_train)

        intent_pred = self._intent_clf.predict(X_test)
        intent_accuracy = float(accuracy_score(intent_test, intent_pred))
        intent_report = classification_report(
            intent_test, intent_pred, zero_division=0
        )
        logger.info("Stage 1 intent accuracy=%.4f", intent_accuracy)

        # ── Stage 2: Domain OvR (RAG samples only) ───────────────────────────
        rag_train_mask = np.array([l == "rag" for l in intent_train])
        X_rag_train = X_train[rag_train_mask]
        y_rag_train_raw: List[List[str]] = [
            [lbl for lbl in labels_list[int(train_idx[j])] if lbl in RAG_LABELS]
            for j, is_rag in enumerate(rag_train_mask)
            if is_rag
        ]

        self._mlb = MultiLabelBinarizer(classes=sorted(RAG_LABELS))
        y_rag_train = self._mlb.fit_transform(y_rag_train_raw)

        logger.info(
            "Stage 2: training domain OvR on %d RAG samples …",
            len(X_rag_train),
        )
        self._domain_clf = OneVsRestClassifier(
            LogisticRegression(
                max_iter=1000, C=1.0, solver="lbfgs", random_state=random_state
            )
        )
        self._domain_clf.fit(X_rag_train, y_rag_train)

        # ── Evaluate Stage 2 on RAG test samples ─────────────────────────────
        rag_test_mask = np.array([l == "rag" for l in intent_test])
        domain_report = "(no RAG samples in test split)"
        domain_f1 = 0.0
        domain_report_dict: Dict[str, Any] = {}

        if rag_test_mask.any():
            X_rag_test = X_test[rag_test_mask]
            y_rag_test_raw: List[List[str]] = [
                [
                    lbl
                    for lbl in labels_list[int(test_idx[j])]
                    if lbl in RAG_LABELS
                ]
                for j, is_rag in enumerate(rag_test_mask)
                if is_rag
            ]
            y_rag_test = self._mlb.transform(y_rag_test_raw)

            rag_proba = self._domain_clf.predict_proba(X_rag_test)
            y_rag_pred = (rag_proba >= MULTI_LABEL_THRESHOLD).astype(int)
            # Guarantee at least one active label per sample
            for row_i in range(len(y_rag_pred)):
                if y_rag_pred[row_i].sum() == 0:
                    y_rag_pred[row_i, int(np.argmax(rag_proba[row_i]))] = 1

            domain_report = classification_report(
                y_rag_test,
                y_rag_pred,
                target_names=list(self._mlb.classes_),
                zero_division=0,
            )
            domain_report_dict = classification_report(
                y_rag_test,
                y_rag_pred,
                target_names=list(self._mlb.classes_),
                output_dict=True,
                zero_division=0,
            )
            domain_f1 = float(
                domain_report_dict.get("samples avg", {}).get("f1-score", 0.0)
            )
            logger.info("Stage 2 domain samples-F1=%.4f", domain_f1)

        full_report = (
            "=== Stage 1: Intent (chitchat / rag / tool_search) ===\n"
            + intent_report
            + "\n=== Stage 2: Domain routing (RAG subset) ===\n"
            + domain_report
        )
        return {
            "accuracy": intent_accuracy,
            "domain_f1": domain_f1,
            "report": full_report,
            "report_dict": domain_report_dict,
        }

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------

    def predict(self, query: str) -> Dict[str, Any]:
        """Classify a single query using both stages.

        Returns:
            Dict with keys:

            - ``label``: primary predicted label (string)
            - ``intent``: ``"rag"`` | ``"chitchat"`` | ``"tool_search"``
            - ``domain``: primary RAG domain or *None*
            - ``domains``: list of all active RAG domains (may be >1)
            - ``confidence``: Stage-2 primary domain prob (rag) or Stage-1
                             max prob (non-rag)
            - ``probabilities``: raw probability dict for the active stage
        """
        if self._intent_clf is None or self._domain_clf is None:
            raise RuntimeError(
                "Classifier not trained or loaded. "
                "Call train() or load() first."
            )

        vec = np.array(self.embedder.embed_query(query)).reshape(1, -1)

        # ── Stage 1: intent ──────────────────────────────────────────────────
        intent_proba = self._intent_clf.predict_proba(vec)[0]
        intent_classes: List[str] = list(self._intent_clf.classes_)
        intent_label = intent_classes[int(np.argmax(intent_proba))]
        intent_confidence = float(np.max(intent_proba))

        if intent_label != "rag":
            return {
                "label": intent_label,
                "intent": intent_label,
                "domain": None,
                "domains": [],
                "confidence": intent_confidence,
                "probabilities": {
                    c: float(p) for c, p in zip(intent_classes, intent_proba)
                },
            }

        # ── Stage 2: domain (multi-label) ────────────────────────────────────
        domain_classes: List[str] = list(self._mlb.classes_)
        domain_proba = self._domain_clf.predict_proba(vec)[0]
        prob_map = {
            cls: float(p) for cls, p in zip(domain_classes, domain_proba)
        }

        active_domains = [
            cls for cls, p in prob_map.items() if p >= MULTI_LABEL_THRESHOLD
        ]
        # Always return at least the argmax domain
        if not active_domains:
            active_domains = [max(prob_map, key=lambda c: prob_map[c])]

        # Primary domain = highest Stage-2 probability
        active_domains.sort(key=lambda c: prob_map[c], reverse=True)
        primary = active_domains[0]

        return {
            "label": primary,
            "intent": "rag",
            "domain": primary,
            "domains": active_domains,
            "confidence": prob_map[primary],
            "probabilities": prob_map,
        }

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: Optional[str] = None) -> Path:
        """Save both stage classifiers + MLB to a single joblib file."""
        if self._intent_clf is None or self._domain_clf is None:
            raise RuntimeError("No trained classifier to save.")

        save_path = Path(path) if path else _DEFAULT_MODEL_PATH
        save_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "intent_clf": self._intent_clf,
                "domain_clf": self._domain_clf,
                "mlb": self._mlb,
                "_format": "two_stage_v3",
            },
            save_path,
        )
        logger.info("Classifier saved to %s", save_path)
        return save_path

    def load(self, path: Optional[str] = None) -> None:
        """Load classifiers from disk.

        Raises ``ValueError`` for outdated formats — caller should retrain.
        """
        load_path = Path(path) if path else _DEFAULT_MODEL_PATH
        if not load_path.exists():
            raise FileNotFoundError(f"No model file at {load_path}")

        payload = joblib.load(load_path)

        if isinstance(payload, dict) and "intent_clf" in payload:
            # Current two-stage format (v3)
            self._intent_clf = payload["intent_clf"]
            self._domain_clf = payload["domain_clf"]
            self._mlb = payload.get("mlb")
        else:
            # Legacy formats (single-model OvR or bare LogisticRegression)
            raise ValueError(
                "Model file is an older format that is incompatible with the "
                "two-stage classifier. Please retrain:\n"
                "  python -m query.train_classifier"
            )

        logger.info("Classifier loaded from %s", load_path)
