"""Optional local GGUF runtime for PDF Aura.

Only ``llama-cpp-python`` is needed for generation, and it is imported lazily:
a machine without it simply has no local LLM. The model file is discovered
through :class:`src.ai.model_manager.ModelManager` (its configured paths and
``<model root>/llm``) or passed explicitly.

``generate()`` returns ``None`` whenever the runtime or the model is missing,
so callers can fall back to an extractive answer instead of showing an error.
Cancellation is checked between streamed tokens and raises
:class:`src.core.task_manager.CancelledError`.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

from src.ai.model_manager import ModelManager
from src.core.task_manager import CancelledError


logger = logging.getLogger(__name__)

ProgressCallback = Callable[..., None]
CancelCheck = Callable[[], bool] | None

DEFAULT_CONTEXT = 2048
DEFAULT_MAX_TOKENS = 512

# Keys a user/UI may use in the ai_model_paths config for the chat model.
_MODEL_PATH_KEYS = ("llm", "local_llm", "rag_llm", "chat_model", "llm_model")


class LocalLLMUnavailable(RuntimeError):
    """The GGUF model or llama-cpp-python is not installed."""


def _import_llama_cpp():
    """Return llama_cpp.Llama, or None when the optional package is absent."""
    try:
        from llama_cpp import Llama
        return Llama
    except Exception as exc:  # ImportError, DLL load failures, ...
        logger.debug("llama-cpp-python unavailable: %s", exc)
        return None


def _as_gguf(path) -> Path | None:
    try:
        candidate = Path(path).expanduser()
    except (TypeError, ValueError):
        return None
    if candidate.is_file() and candidate.suffix.lower() == ".gguf":
        return candidate
    if candidate.is_dir():
        matches = sorted(candidate.rglob("*.gguf"))
        if matches:
            return matches[0]
    return None


def find_local_model_path(model_path: str | None = None,
                          manager: ModelManager | None = None) -> str:
    """Find the local GGUF model, preferring an explicitly chosen path."""
    if model_path:
        found = _as_gguf(model_path)
        return str(found) if found else str(Path(model_path).expanduser())

    try:
        model_manager = manager or ModelManager()
    except Exception as exc:
        logger.debug("ModelManager unavailable: %s", exc)
        return ""

    configured = model_manager.configured_paths()
    for key in _MODEL_PATH_KEYS:
        found = _as_gguf(configured.get(key, ""))
        if found:
            return str(found)
    for value in configured.values():
        found = _as_gguf(value)
        if found:
            return str(found)

    roots = [
        Path(model_manager.model_root) / "llm",
        Path(model_manager.model_root) / "rag",
        Path(model_manager.model_root),
        model_manager.app_root() / "models" / "llm",
        model_manager.app_root() / "models",
    ]
    seen = set()
    for root in roots:
        key = str(root)
        if key in seen:
            continue
        seen.add(key)
        found = _as_gguf(root)
        if found:
            return str(found)
    return ""


def check_cancelled(cancel: CancelCheck) -> None:
    if cancel is None:
        return
    checker = getattr(cancel, "check_cancelled", None)
    if callable(checker):
        checker()
        return
    if callable(cancel):
        if cancel():
            raise CancelledError("İşlem kullanıcı tarafından iptal edildi.")
        return
    if getattr(cancel, "is_cancelled", False):
        raise CancelledError("İşlem kullanıcı tarafından iptal edildi.")


def _report_progress(progress: ProgressCallback | None, current: int, total: int,
                     message: str = "") -> None:
    if progress is None:
        return
    try:
        progress(current, total, message)
    except TypeError:
        progress(current, total)


def _completion_text(item) -> str:
    if isinstance(item, str):
        return item
    if not isinstance(item, dict):
        return ""
    choices = item.get("choices") or []
    if not choices:
        return ""
    choice = choices[0] or {}
    text = choice.get("text")
    if text:
        return str(text)
    delta = choice.get("delta") or {}
    return str(delta.get("content") or "")


class LocalLLM:
    """A lazily loaded llama.cpp model, if one is available."""

    def __init__(self, model_path: str | None = None, *,
                 model_factory: Callable[..., object] | None = None,
                 n_ctx: int = DEFAULT_CONTEXT, n_threads: int | None = None,
                 verbose: bool = False, manager: ModelManager | None = None):
        self.model_path = find_local_model_path(model_path, manager)
        self._model_factory = model_factory
        self.n_ctx = int(n_ctx)
        self.n_threads = n_threads
        self.verbose = bool(verbose)
        self._model = None
        self.last_error = ""

    @property
    def available(self) -> bool:
        """Whether a GGUF model file was found (runtime may still be absent)."""
        if not self.model_path:
            return False
        path = Path(self.model_path)
        return path.is_file() and path.suffix.lower() == ".gguf"

    @property
    def runtime_available(self) -> bool:
        return _import_llama_cpp() is not None

    def _load_model(self):
        if self._model is not None:
            return self._model
        if not self.available:
            raise LocalLLMUnavailable("Yerel LLM modeli bulunamadı.")

        factory = self._model_factory
        if factory is None:
            llama_class = _import_llama_cpp()
            if llama_class is None:
                raise LocalLLMUnavailable(
                    "llama-cpp-python kurulu değil; yerel LLM devre dışı.")
            factory = llama_class

        self._model = factory(
            model_path=self.model_path,
            n_ctx=self.n_ctx,
            n_threads=self.n_threads,
            verbose=self.verbose,
        )
        return self._model

    def unload(self) -> None:
        self._model = None

    def generate(self, prompt: str, *, max_tokens: int = DEFAULT_MAX_TOKENS,
                 temperature: float = 0.1, stop: list[str] | None = None,
                 progress: ProgressCallback | None = None,
                 cancel: CancelCheck = None) -> str | None:
        """Generate an answer, or None when no local model can run."""
        if not self.available:
            return None
        check_cancelled(cancel)

        try:
            model = self._load_model()
        except Exception as exc:
            self.last_error = str(exc)
            logger.warning("Yerel LLM yüklenemedi: %s", exc)
            return None

        max_tokens = max(1, int(max_tokens))
        options = {
            "max_tokens": max_tokens,
            "temperature": float(temperature),
            "stop": list(stop or []),
        }

        try:
            try:
                stream = model(str(prompt), stream=True, **options)
            except TypeError:
                # A model wrapper without streaming support still works.
                stream = model(str(prompt), **options)

            if isinstance(stream, (str, dict)):
                pieces = [_completion_text(stream)]
            else:
                pieces = []
                produced = 0
                for item in stream:
                    check_cancelled(cancel)
                    piece = _completion_text(item)
                    if piece:
                        pieces.append(piece)
                        produced += 1
                    if produced % 8 == 0:
                        _report_progress(progress, produced, max_tokens,
                                         "Cevap üretiliyor")
                    choices = item.get("choices") if isinstance(item, dict) else None
                    if choices and choices[0] and choices[0].get("finish_reason"):
                        break

            text = "".join(pieces).strip()
            _report_progress(progress, max_tokens, max_tokens, "Cevap hazir")
            return text or None
        except CancelledError:
            raise
        except Exception as exc:
            self.last_error = str(exc)
            logger.warning("Yerel LLM cevap üretemedi: %s", exc)
            return None


def create_local_llm(model_path: str | None = None, **kwargs) -> LocalLLM | None:
    """A ready LocalLLM, or None when no model file is available."""
    llm = LocalLLM(model_path, **kwargs)
    return llm if llm.available else None


def generate(prompt: str, *, model_path: str | None = None,
             **kwargs) -> str | None:
    """One-shot helper; returns None when the local LLM is unavailable."""
    llm = create_local_llm(model_path)
    if llm is None:
        return None
    return llm.generate(prompt, **kwargs)


def is_llm_available(model_path: str | None = None) -> bool:
    return bool(find_local_model_path(model_path))
