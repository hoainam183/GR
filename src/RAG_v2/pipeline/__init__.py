"""Pipeline orchestration module."""

from __future__ import annotations

from typing import Any

__all__ = ["RAGPipeline", "DocumentPipeline"]


def __getattr__(name: str) -> Any:
    if name == "RAGPipeline":
        from .rag_pipeline import RAGPipeline

        return RAGPipeline
    if name == "DocumentPipeline":
        from .document_pipeline import DocumentPipeline

        return DocumentPipeline
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
