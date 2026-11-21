"""Face Template Normalizer & Multi-Frame Aggregator (Section I.5 & IV.2)."""
from __future__ import annotations

from typing import Sequence
import numpy as np


class FaceTemplateNormalizer:
    """
    Validates 512-D finite embeddings, L2-normalizes each sample e_i,
    and aggregates t = normalize((e_1 + ... + e_n) / n).
    Never substitutes zero vectors on failure.
    """

    @staticmethod
    def l2_normalize(embedding: np.ndarray, min_norm: float = 1e-6) -> np.ndarray:
        vec = np.asarray(embedding, dtype=np.float32).reshape(-1)
        if vec.shape != (512,) or not np.all(np.isfinite(vec)):
            raise ValueError("Vector khuôn mặt phải có đúng 512 phần tử hữu hạn (float32).")
        norm = float(np.linalg.norm(vec))
        if norm < min_norm:
            raise ValueError("Norm của vector khuôn mặt quá nhỏ hoặc bằng 0.")
        return (vec / norm).astype(np.float32)

    @classmethod
    def build_template(cls, embeddings: Sequence[np.ndarray], min_norm: float = 1e-6) -> np.ndarray:
        if not embeddings:
            raise ValueError("Không có embedding hợp lệ để tổng hợp template.")
        normalized_samples = [cls.l2_normalize(e, min_norm=min_norm) for e in embeddings]
        mean_vec = np.mean(np.stack(normalized_samples, axis=0), axis=0)
        return cls.l2_normalize(mean_vec, min_norm=min_norm)
