"""Domain Classifier — lightweight embedding-based intent + domain classifier."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

from .training_data import RAG_LABELS

logger = logging.getLogger(__name__)

# ─── Default model path ────────────────────────────────────────────────────────
_DEFAULT_MODEL_DIR = Path(__file__).parent / "models"
_DEFAULT_MODEL_PATH = _DEFAULT_MODEL_DIR / "domain_classifier.joblib"


class DomainClassifier:
    """Classifies queries into 6 labels using embeddings + Logistic Regression.

    Labels: ``chitchat``, ``tool_search``, ``ctdt``, ``quydinh``, ``kehoach``, ``stsv``.

    If the predicted label is a RAG domain (ctdt/quydinh/kehoach/stsv),
    ``intent`` is set to ``"rag"``; otherwise it matches the label directly.

    Parameters:
        embedder: An embedder instance with ``embed(texts) -> List[List[float]]``
                  and ``embed_query(text) -> List[float]`` methods.
                  If *None*, a ``BGEm3Embedder`` will be lazily loaded.
    """

    def __init__(self, embedder: Optional[Any] = None) -> None:
        self._embedder = embedder
        self._classifier: Optional[LogisticRegression] = None

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
        data: List[Tuple[str, str]],
        test_size: float = 0.2,
        random_state: int = 42,
    ) -> Dict[str, Any]:
        """Embed training queries, fit classifier, and return evaluation report.

        Args:
            data: List of ``(query, label)`` tuples.
            test_size: Fraction held out for evaluation.
            random_state: Seed for reproducibility.

        Returns:
            Dict with ``accuracy``, ``report`` (classification report string),
            and ``report_dict`` (per-class metrics dict).
        """
        texts, labels = zip(*data)
        texts: List[str] = list(texts)
        labels: List[str] = list(labels)

        logger.info("Embedding %d training samples …", len(texts))
        embeddings = np.array(self.embedder.embed(texts))

        X_train, X_test, y_train, y_test = train_test_split(
            embeddings,
            labels,
            test_size=test_size,
            random_state=random_state,
            stratify=labels,
        )

        logger.info(
            "Training LogisticRegression (train=%d, test=%d) …",
            len(X_train),
            len(X_test),
        )
        self._classifier = LogisticRegression(
            max_iter=1000,
            C=1.0,
            solver="lbfgs",
            random_state=random_state,
        )
        self._classifier.fit(X_train, y_train)

        accuracy = self._classifier.score(X_test, y_test)
        report_str = classification_report(
            y_test, self._classifier.predict(X_test)
        )
        report_dict = classification_report(
            y_test,
            self._classifier.predict(X_test),
            output_dict=True,
        )

        logger.info("Training complete — accuracy=%.4f", accuracy)
        return {
            "accuracy": accuracy,
            "report": report_str,
            "report_dict": report_dict,
        }

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------

    def predict(self, query: str) -> Dict[str, Any]:
        """Classify a single query.

        Returns:
            Dict with keys:
            - ``label``: one of the 6 class labels
            - ``intent``: ``"rag"`` | ``"chitchat"`` | ``"tool_search"``
            - ``domain``: label string if intent is rag, else *None*
            - ``confidence``: max probability
            - ``probabilities``: dict mapping each label to its probability
        """
        if self._classifier is None:
            raise RuntimeError(
                "Classifier not trained or loaded. "
                "Call train() or load() first."
            )

        vec = np.array(self.embedder.embed_query(query)).reshape(1, -1)
        proba = self._classifier.predict_proba(vec)[0]
        classes = self._classifier.classes_

        label = classes[np.argmax(proba)]
        confidence = float(np.max(proba))
        probabilities = {cls: float(p) for cls, p in zip(classes, proba)}

        if label in RAG_LABELS:
            intent = "rag"
            domain = label
        else:
            intent = label  # "chitchat" or "tool_search"
            domain = None

        return {
            "label": label,
            "intent": intent,
            "domain": domain,
            "confidence": confidence,
            "probabilities": probabilities,
        }

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: Optional[str] = None) -> Path:
        """Save the trained classifier to disk (only the sklearn model).

        The embedder is NOT saved — it must be provided or lazy-loaded at
        inference time.
        """
        if self._classifier is None:
            raise RuntimeError("No trained classifier to save.")

        save_path = Path(path) if path else _DEFAULT_MODEL_PATH
        save_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self._classifier, save_path)
        logger.info("Classifier saved to %s", save_path)
        return save_path

    def load(self, path: Optional[str] = None) -> None:
        """Load a previously trained classifier from disk."""
        load_path = Path(path) if path else _DEFAULT_MODEL_PATH
        if not load_path.exists():
            raise FileNotFoundError(f"No model file at {load_path}")
        self._classifier = joblib.load(load_path)
        logger.info("Classifier loaded from %s", load_path)
