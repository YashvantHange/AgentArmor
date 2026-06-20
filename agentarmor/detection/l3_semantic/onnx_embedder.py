"""BGE ONNX embedder when model is downloaded."""

from __future__ import annotations

from pathlib import Path

import numpy as np


class BGEOnnxEmbedder:
    def __init__(self, model_path: Path) -> None:
        import onnxruntime as ort

        self._session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
        self._input_name = self._session.get_inputs()[0].name

    def embed(self, text: str) -> list[float]:
        # Minimal tokenization placeholder — real impl uses bundled tokenizer
        arr = np.array([[ord(c) % 256 for c in text[:512]]], dtype=np.float32)
        if arr.shape[1] < 8:
            arr = np.pad(arr, ((0, 0), (0, 8 - arr.shape[1])))
        outputs = self._session.run(None, {self._input_name: arr})
        vec = outputs[0].flatten().tolist()
        return vec
