"""Local model backend router — .gguf vs HuggingFace directory."""

from __future__ import annotations

import warnings
from enum import Enum
from pathlib import Path

from agentarmor.engines.local.llama_cpp_backend import LlamaCppBackend
from agentarmor.engines.local.transformers_backend import TransformersBackend


class LocalBackend(str, Enum):
    AUTO = "auto"
    LLAMA_CPP = "llama_cpp"
    TRANSFORMERS = "transformers"


def detect_backend(model_path: Path, backend: str = "auto") -> LocalBackend:
    if backend != "auto":
        return LocalBackend(backend)

    if model_path.suffix.lower() == ".gguf":
        return LocalBackend.LLAMA_CPP
    if model_path.is_dir() and (model_path / "config.json").exists():
        return LocalBackend.TRANSFORMERS
    if model_path.suffix.lower() in (".safetensors", ".bin"):
        return LocalBackend.TRANSFORMERS
    raise ValueError(
        f"Cannot detect backend for '{model_path}'. "
        "Use a .gguf file or a HuggingFace model directory."
    )


def check_memory_warning(model_path: Path, threshold_gb: float) -> None:
    if threshold_gb <= 0:
        return
    size_bytes = (
        model_path.stat().st_size
        if model_path.is_file()
        else sum(f.stat().st_size for f in model_path.rglob("*") if f.is_file())
    )
    size_gb = size_bytes / (1024**3)
    if size_gb > threshold_gb:
        warnings.warn(
            f"Model at '{model_path}' is ~{size_gb:.1f} GB "
            f"(threshold {threshold_gb:.1f} GB). Ensure sufficient RAM.",
            stacklevel=2,
        )


class LocalModelRouter:
    def __init__(
        self,
        model_path: Path,
        *,
        backend: str = "auto",
        gpu_layers: int = 0,
        memory_warn_gb: float = 8.0,
    ) -> None:
        self._path = model_path.resolve()
        if not self._path.exists():
            raise FileNotFoundError(f"Local model not found: {self._path}")
        check_memory_warning(self._path, memory_warn_gb)
        self._backend_type = detect_backend(self._path, backend)
        if self._backend_type == LocalBackend.LLAMA_CPP:
            self._backend: LlamaCppBackend | TransformersBackend = LlamaCppBackend(
                self._path, gpu_layers=gpu_layers
            )
        else:
            self._backend = TransformersBackend(self._path)

    @property
    def backend_type(self) -> LocalBackend:
        return self._backend_type

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 512,
    ) -> tuple[str, dict[str, object], float]:
        return self._backend.complete(
            messages, temperature=temperature, max_tokens=max_tokens
        )
