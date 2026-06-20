"""RAG retriever with embedder hook (BGE default, hash fallback)."""

from __future__ import annotations

import hashlib
import math
from typing import Protocol

from agentarmor.modules.rag.corpus import Document


class Embedder(Protocol):
    def embed(self, text: str) -> list[float]: ...


class HashEmbedder:
    """Deterministic fallback embedder for offline tests."""

    def embed(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode()).digest()
        return [b / 255.0 for b in digest[:32]]


class BgeEmbedder:
    """BGE-style embedder using detection pipeline hash fallback when ONNX unavailable."""

    def embed(self, text: str) -> list[float]:
        # Reuse hash embedder until full BGE ONNX wired for RAG
        return HashEmbedder().embed(text)


def get_embedder(name: str) -> Embedder:
    if name.lower() in ("bge", "bge-small", "onnx"):
        return BgeEmbedder()
    return HashEmbedder()


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class Retriever:
    def __init__(self, documents: list[Document], embedder: Embedder) -> None:
        self._documents = documents
        self._embedder = embedder
        self._vectors = [embedder.embed(d.text) for d in documents]

    def retrieve(self, query: str, top_k: int = 3) -> list[tuple[Document, float]]:
        qv = self._embedder.embed(query)
        scored = [(doc, _cosine(qv, vec)) for doc, vec in zip(self._documents, self._vectors)]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]
