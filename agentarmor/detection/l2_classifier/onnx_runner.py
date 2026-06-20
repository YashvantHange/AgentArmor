"""DeBERTa-v3 ONNX security classifier."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from agentarmor.detection.l2_classifier.fallback import L2_CLASSES, L2Result, classify_fallback


@dataclass
class L2OnnxResult(L2Result):
    engine: str = "onnx"


def classify(text: str, model_dir=None) -> L2Result:
    from agentarmor.detection.models.manager import get_model_manager

    manager = get_model_manager(model_dir)
    if not manager.has_onnx_classifier():
        return classify_fallback(text)

    try:
        return _classify_onnx(text, manager.path("deberta_onnx"))
    except Exception:
        result = classify_fallback(text)
        result.engine = "fallback-onnx-error"
        return result


def _classify_onnx(text: str, model_path: Path) -> L2OnnxResult:
    import time

    import onnxruntime as ort

    start = time.perf_counter()
    session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
    input_name = session.get_inputs()[0].name

    # Char-level placeholder features until tokenizer bundle ships with model
    arr = np.array([[ord(c) % 512 for c in text[:256]]], dtype=np.int64)
    if arr.shape[1] < 16:
        arr = np.pad(arr, ((0, 0), (0, 16 - arr.shape[1])))

    outputs = session.run(None, {input_name: arr})
    logits = outputs[0].flatten()[: len(L2_CLASSES)]
    exp = np.exp(logits - np.max(logits))
    probs = exp / exp.sum()
    scores = {cls: float(probs[i]) for i, cls in enumerate(L2_CLASSES)}
    top_class = max(scores, key=scores.get)  # type: ignore[arg-type]
    latency_ms = (time.perf_counter() - start) * 1000
    return L2OnnxResult(
        scores=scores,
        max_score=scores[top_class],
        top_class=top_class,
        latency_ms=latency_ms,
        engine="onnx",
    )
