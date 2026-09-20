"""Face Template Normalizer."""
import numpy as np

class FaceTemplateNormalizer:
    @staticmethod
    def l2_normalize(embedding: np.ndarray) -> np.ndarray:
        norm = np.linalg.norm(embedding)
        return embedding / norm if norm > 0 else embedding