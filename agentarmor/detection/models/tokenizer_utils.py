"""Tokenizer bundle loading for ONNX L2/L3 models."""

from __future__ import annotations

import logging
import warnings
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

_warned_no_tokenizer: set[str] = set()


def tokenizer_dir(model_dir: Path, model_key: str) -> Path:
    mapping = {
        "deberta_onnx": "deberta-tokenizer",
        "bge_onnx": "bge-tokenizer",
    }
    return model_dir / mapping.get(model_key, model_key)


def has_tokenizer_bundle(model_dir: Path, model_key: str) -> bool:
    td = tokenizer_dir(model_dir, model_key)
    return (td / "tokenizer.json").exists()


def warn_missing_tokenizer(model_key: str) -> None:
    if model_key in _warned_no_tokenizer:
        return
    _warned_no_tokenizer.add(model_key)
    warnings.warn(
        f"ONNX model '{model_key}' is present but tokenizer bundle is missing; "
        "using heuristic fallback. Run `agentarmor models download` to fetch tokenizers.",
        stacklevel=3,
    )


def encode_text(
    text: str,
    model_dir: Path,
    model_key: str,
    *,
    max_length: int = 256,
) -> dict[str, np.ndarray] | None:
    """Return input_ids and optional attention_mask for ONNX, or None if no bundle."""
    td = tokenizer_dir(model_dir, model_key)
    tok_path = td / "tokenizer.json"
    if not tok_path.exists():
        return None
    try:
        from tokenizers import Tokenizer

        tokenizer = Tokenizer.from_file(str(tok_path))
        encoded = tokenizer.encode(text)
        ids = encoded.ids[:max_length]
        if not ids:
            ids = [0]
        input_ids = np.array([ids], dtype=np.int64)
        attention_mask = np.ones_like(input_ids, dtype=np.int64)
        return {"input_ids": input_ids, "attention_mask": attention_mask}
    except Exception as exc:
        logger.debug("tokenizer encode failed for %s: %s", model_key, exc)
        return None


def pad_inputs_for_session(
    session,
    encoded: dict[str, np.ndarray],
) -> dict[str, np.ndarray]:
    """Pad/truncate encoded tensors to match ONNX session input shapes."""
    feeds: dict[str, np.ndarray] = {}
    for inp in session.get_inputs():
        name = inp.name
        shape = inp.shape
        if name in encoded:
            arr = encoded[name]
        elif name == "input_ids" and "input_ids" in encoded:
            arr = encoded["input_ids"]
        elif name in ("attention_mask", "token_type_ids") and "attention_mask" in encoded:
            arr = encoded["attention_mask"]
        else:
            continue

        target_len = shape[1] if len(shape) > 1 and isinstance(shape[1], int) else arr.shape[1]
        if arr.shape[1] < target_len:
            pad_width = ((0, 0), (0, target_len - arr.shape[1]))
            fill = 0 if "mask" not in name else 0
            arr = np.pad(arr, pad_width, constant_values=fill)
        elif arr.shape[1] > target_len:
            arr = arr[:, :target_len]
        feeds[name] = arr.astype(np.int64)
    if not feeds and "input_ids" in encoded:
        feeds[session.get_inputs()[0].name] = encoded["input_ids"]
    return feeds
