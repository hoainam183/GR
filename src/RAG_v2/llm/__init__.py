"""Chat Model Layer — LLM wrapper, prompts, and self-evaluation."""

from .chat_model import ChatModel
from .self_eval import SelfEvaluator

__all__ = ["ChatModel", "SelfEvaluator"]
