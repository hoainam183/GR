"""LLM Base — provider-agnostic interface for all LLM backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Generator, List, Optional


class BaseLLM(ABC):
    """Provider-agnostic LLM interface.

    All LLM providers (Gemini, OpenAI, Azure, Ollama, …) must inherit this
    class and implement both abstract methods.  Concrete classes take only
    their own credentials and model params in ``__init__``; they must NOT
    read from ``Settings`` directly — that is the factory's responsibility.
    """

    @abstractmethod
    def generate(
        self,
        query: str,
        context: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        mode: str = "rag",
    ) -> str:
        """Generate a response (blocking).

        Args:
            query: The user question.
            context: Retrieved document context, if any.
            history: Conversation history as a list of ``{role, content}`` dicts.
            mode: ``"rag"`` for grounded answers, ``"chitchat"`` for open chat.

        Returns:
            The model's text response.
        """
        ...

    @abstractmethod
    def generate_stream(
        self,
        query: str,
        context: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        mode: str = "rag",
    ) -> Generator[str, None, None]:
        """Generate a response incrementally (streaming).

        Yields successive text chunks as they arrive from the provider.

        Args:
            query: The user question.
            context: Retrieved document context, if any.
            history: Conversation history as a list of ``{role, content}`` dicts.
            mode: ``"rag"`` for grounded answers, ``"chitchat"`` for open chat.

        Yields:
            Text chunks in order.
        """
        ...
