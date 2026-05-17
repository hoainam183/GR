"""Reranking Layer — BGE-v2-M3 cross-encoder reranking."""

from __future__ import annotations

import importlib
from typing import Any, Optional, TYPE_CHECKING

from .base import BaseReranker, register_reranker, _REGISTRY

# Map provider name → dotted module path inside reranking/
_PROVIDER_MODULES: dict[str, str] = {
    "bge": "reranking.bge_reranker",
}


def create_reranker(settings: "Settings") -> Optional[BaseReranker]:  # type: ignore[name-defined]
    """Lazy-import and instantiate the configured reranker.

    Args:
        settings: Application settings instance.

    Returns:
        A concrete BaseReranker, or ``None`` when
        *settings.reranker_provider* is ``"none"``.

    Raises:
        ValueError: If the provider is not in ``_PROVIDER_MODULES``.
    """
    provider = settings.reranker_provider
    if provider == "none":
        return None
    if provider not in _REGISTRY:
        module_path = _PROVIDER_MODULES.get(provider)
        if module_path is None:
            raise ValueError(
                f"Unknown reranker provider '{provider}'. "
                f"Known providers: {list(_PROVIDER_MODULES)}"
            )
        importlib.import_module(module_path)  # triggers @register_reranker
    cls = _REGISTRY[provider]
    return cls(
        model_name=settings.reranker_model,
        top_k=settings.reranker_top_k,
        score_threshold=settings.reranker_score_threshold,
        table_score_threshold=settings.reranker_table_score_threshold,
    )


if TYPE_CHECKING:
    from .bge_reranker import BGEReranker


def __getattr__(name: str) -> Any:
    if name == "BGEReranker":
        from .bge_reranker import BGEReranker

        return BGEReranker
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "BaseReranker",
    "BGEReranker",
    "register_reranker",
    "create_reranker",
]
