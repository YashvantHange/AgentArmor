"""HuggingFace / safetensors local inference via transformers."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

_pipeline: Any = None
_pipeline_path: str | None = None


def _get_pipeline(model_path: Path) -> Any:
    global _pipeline, _pipeline_path
    path_str = str(model_path.resolve())
    if _pipeline is not None and _pipeline_path == path_str:
        return _pipeline
    try:
        import torch
        from transformers import pipeline
    except ImportError as exc:
        raise ImportError(
            "transformers and torch are required for HuggingFace models. "
            "Install with: pip install agentarmor[local]"
        ) from exc

    device = "cuda" if torch.cuda.is_available() else "cpu"
    _pipeline = pipeline(
        "text-generation",
        model=path_str,
        device_map=device if device == "cuda" else None,
        torch_dtype=torch.float32,
    )
    _pipeline_path = path_str
    return _pipeline


class TransformersBackend:
    def __init__(self, model_path: Path) -> None:
        self._model_path = model_path

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 512,
    ) -> tuple[str, dict[str, Any], float]:
        pipe = _get_pipeline(self._model_path)
        prompt = _messages_to_prompt(messages)
        start = time.perf_counter()
        outputs = pipe(
            prompt,
            max_new_tokens=max_tokens,
            do_sample=temperature > 0,
            temperature=max(temperature, 0.01),
            return_full_text=False,
        )
        latency_ms = (time.perf_counter() - start) * 1000
        content = ""
        if outputs:
            content = outputs[0].get("generated_text", "") or ""
        raw = {"generated_text": content, "prompt_chars": len(prompt)}
        return content.strip(), raw, latency_ms


def _messages_to_prompt(messages: list[dict[str, str]]) -> str:
    parts: list[str] = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        parts.append(f"{role}: {content}")
    parts.append("assistant:")
    return "\n".join(parts)
