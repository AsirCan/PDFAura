from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.ai.model_manager import ModelManager


class LocalLLMUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class LocalLLMResponse:
    text: str
    model_path: str


class LocalLLM:
    """
    Runtime boundary for local GGUF language models.

    Phase 1 validates model configuration without forcing a heavy inference
    dependency into the base install. The actual llama.cpp binding can be added
    behind this class in the RAG phase.
    """

    def __init__(self, manager: ModelManager | None = None):
        self.manager = manager or ModelManager()

    def configured_model_path(self) -> str:
        status = self.manager.status("local_llm")
        return status.path if status.installed else ""

    def is_available(self) -> bool:
        path = self.configured_model_path()
        return bool(path and Path(path).exists())

    def generate(self, prompt: str, max_tokens: int = 512) -> LocalLLMResponse:
        path = self.configured_model_path()
        if not path:
            raise LocalLLMUnavailable("Yerel LLM modeli yapılandırılmadı.")
        raise LocalLLMUnavailable(
            "Yerel LLM runtime henüz bağlanmadı. Faz 3'te llama.cpp entegrasyonu eklenecek."
        )
