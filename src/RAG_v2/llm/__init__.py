"""Chat Model Layer — LLM wrapper, prompts, and self-evaluation."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

from .base import BaseLLM

# Map provider name → dotted module path inside llm/
_PROVIDER_MODULES: dict[str, str] = {
    "deepseek": "llm.deepseek",
    "gemini": "llm.gemini",
    "lm_studio": "llm.lm_studio",
}

# Provider registry — populated by @register_llm decorators at first call.
_REGISTRY: dict[str, type[BaseLLM]] = {}


def register_llm(name: str):
    """Decorator that registers an LLM provider class under *name*."""

    def decorator(cls: type[BaseLLM]) -> type[BaseLLM]:
        _REGISTRY[name] = cls
        return cls

    return decorator


def create_llm(settings: "Settings") -> BaseLLM:  # type: ignore[name-defined]
    """Lazy-import and instantiate the configured LLM provider.

    Args:
        settings: Application settings instance.

    Returns:
        A concrete BaseLLM implementation for the configured provider.

    Raises:
        ValueError: If *settings.llm_provider* is not in ``_PROVIDER_MODULES``.
    """
    provider = settings.llm_provider
    if provider not in _REGISTRY:
        module_path = _PROVIDER_MODULES.get(provider)
        if module_path is None:
            raise ValueError(
                f"Unknown LLM provider '{provider}'. "
                f"Known providers: {list(_PROVIDER_MODULES)}"
            )
        importlib.import_module(module_path)  # triggers @register_llm
    cls = _REGISTRY[provider]
    kwargs = {
        "api_key": settings.llm_api_key
        or (
            settings.deepseek_api_key
            if provider == "deepseek"
            else settings.google_api_key
        ),
        "model": settings.chat_model,
        "temperature": settings.chat_temperature,
        "max_tokens": settings.chat_max_tokens,
    }
    
    if provider == "lm_studio":
        kwargs["base_url"] = settings.lm_studio_base_url
        
    return cls(**kwargs)


# Keep existing exports for backwards compatibility.
from .chat_model import ChatModel
from .self_eval import SelfEvaluator

__all__ = [
    "BaseLLM",
    "ChatModel",
    "SelfEvaluator",
    "register_llm",
    "create_llm",
]
