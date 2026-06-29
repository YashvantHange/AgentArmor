"""Hash-based embedder (bootstrap) — replaced by BGE ONNX when downloaded."""

from __future__ import annotations

import hashlib
import math
import struct
from typing import Protocol


class Embedder(Protocol):
    def embed(self, text: str) -> list[float]:
        ...


class HashEmbedder:
    """Deterministic 384-dim embedding without external models."""

    EMBEDDER_VERSION = "hash-v1"

    def __init__(self, dim: int = 384) -> None:
        self.dim = dim

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        tokens = text.lower().split()
        if not tokens:
            return vec
        for token in tokens:
            digest = hashlib.sha256(token.encode()).digest()
            for i in range(0, min(len(digest), self.dim), 4):
                idx = struct.unpack(">I", digest[i : i + 4])[0] % self.dim
                vec[idx] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


def get_embedder(model_dir=None) -> Embedder:
    from agentarmor.detection.l3_semantic.onnx_embedder import BGEOnnxEmbedder
    from agentarmor.detection.models.manager import get_model_manager
    from agentarmor.detection.models.tokenizer_utils import (
        has_tokenizer_bundle,
        warn_missing_tokenizer,
    )

    manager = get_model_manager(model_dir)
    if manager.has_onnx_embedder():
        if not has_tokenizer_bundle(manager.model_dir, "bge_onnx"):
            warn_missing_tokenizer("bge_onnx")
        else:
            try:
                return BGEOnnxEmbedder(manager.path("bge_onnx"), manager.model_dir)
            except Exception:
                pass
    return HashEmbedder()
