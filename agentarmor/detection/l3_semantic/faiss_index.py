"""Build and query FAISS exploit similarity index."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from agentarmor.detection.l3_semantic.embedder import get_embedder


@dataclass
class L3Result:
    score: float
    matches: list[str]
    latency_ms: float = 0.0
    engine: str = "faiss"


def ensure_faiss_index(phrases_path: Path, index_path: Path) -> None:
    if index_path.exists():
        return
    phrases = json.loads(phrases_path.read_text(encoding="utf-8"))
    embedder = get_embedder(phrases_path.parent)
    vectors = np.array([embedder.embed(p) for p in phrases], dtype=np.float32)
    try:
        import faiss

        dim = vectors.shape[1]
        index = faiss.IndexFlatIP(dim)
        faiss.normalize_L2(vectors)
        index.add(vectors)
        faiss.write_index(index, str(index_path))
    except ImportError:
        # Store raw vectors for numpy fallback search
        np.save(str(index_path) + ".npy", vectors)
        index_path.with_suffix(".phrases.json").write_text(json.dumps(phrases), encoding="utf-8")


def search(text: str, model_dir=None, threshold: float = 0.82) -> L3Result:
    import time

    from agentarmor.detection.models.manager import get_model_manager

    start = time.perf_counter()
    manager = get_model_manager(model_dir)
    manager.ensure_bootstrap_models()

    phrases_path = manager.exploit_phrases_path()
    index_path = manager.faiss_index_path()
    phrases = json.loads(phrases_path.read_text(encoding="utf-8"))
    embedder = get_embedder(model_dir)
    query = np.array([embedder.embed(text)], dtype=np.float32)

    best_score = 0.0
    best_phrase = ""

    try:
        import faiss

        if index_path.exists():
            index = faiss.read_index(str(index_path))
            faiss.normalize_L2(query)
            scores, indices = index.search(query, k=3)
            for score, idx in zip(scores[0], indices[0]):
                if idx < 0:
                    continue
                if score > best_score:
                    best_score = float(score)
                    best_phrase = phrases[int(idx)]
    except ImportError:
        npy = str(index_path) + ".npy"
        if Path(npy).exists():
            vectors = np.load(npy)
            q = query[0]
            q_norm = np.linalg.norm(q) or 1.0
            for i, vec in enumerate(vectors):
                v_norm = np.linalg.norm(vec) or 1.0
                sim = float(np.dot(q, vec) / (q_norm * v_norm))
                if sim > best_score:
                    best_score = sim
                    best_phrase = phrases[i]

    score = best_score if best_score >= threshold else best_score * 0.5
    latency_ms = (time.perf_counter() - start) * 1000
    matches = [best_phrase] if best_phrase and best_score >= threshold * 0.9 else []
    return L3Result(score=min(score, 1.0), matches=matches, latency_ms=latency_ms)
