"""GGUF local inference via llama-cpp-python."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

_Llama: Any = None


def _get_llama_class() -> Any:
    global _Llama
    if _Llama is None:
        try:
            from llama_cpp import Llama

            _Llama = Llama
        except ImportError as exc:
            raise ImportError(
                "llama-cpp-python is required for .gguf models. "
                "Install with: pip install agentarmor[local]"
            ) from exc
    return _Llama


class LlamaCppBackend:
    def __init__(self, model_path: Path, gpu_layers: int = 0) -> None:
        self._model_path = model_path
        self._gpu_layers = gpu_layers
        self._model: Any = None

    def _ensure_loaded(self) -> None:
        if self._model is None:
            Llama = _get_llama_class()
            self._model = Llama(
                model_path=str(self._model_path),
                n_gpu_layers=self._gpu_layers,
                verbose=False,
            )

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 512,
    ) -> tuple[str, dict[str, Any], float]:
        self._ensure_loaded()
        prompt = _messages_to_prompt(messages)
        start = time.perf_counter()
        result = self._model.create_chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        latency_ms = (time.perf_counter() - start) * 1000
        content = ""
        choices = result.get("choices") or []
        if choices:
            content = (choices[0].get("message") or {}).get("content", "") or ""
        raw = {"choices": choices, "prompt_chars": len(prompt)}
        return content, raw, latency_ms


def _messages_to_prompt(messages: list[dict[str, str]]) -> str:
    parts: list[str] = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        parts.append(f"{role}: {content}")
    return "\n".join(parts)
