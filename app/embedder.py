"""One ONNX embedder shared by retrieval and cache.

PyTorch sentence-transformers loads twice and exceeds Render's 512 MB free limit.
"""
from __future__ import annotations

from typing import List

import numpy as np

from app.config import EMBEDDING_MODEL


class SharedEmbedder:
    def __init__(self, model_name: str = EMBEDDING_MODEL) -> None:
        self.model_name = model_name
        self._model = None

    def initialize(self) -> None:
        if self._model is not None:
            return
        from fastembed import TextEmbedding

        self._model = TextEmbedding(model_name=self.model_name)

    def encode(self, texts: List[str]) -> np.ndarray:
        self.initialize()
        assert self._model is not None
        vectors = [np.asarray(v, dtype=np.float32) for v in self._model.embed(texts)]
        if not vectors:
            return np.zeros((0, 384), dtype=np.float32)
        mat = np.vstack(vectors)
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        return mat / np.maximum(norms, 1e-9)
