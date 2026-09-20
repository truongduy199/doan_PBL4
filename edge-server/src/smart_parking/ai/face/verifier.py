"""Face Verifier (Cosine Similarity)."""
import numpy as np

class FaceVerifier:
    def __init__(self, t_accept: float = 0.65, t_reject: float = 0.45):
        self.t_accept = t_accept
        self.t_reject = t_reject

    def verify(self, emb1: np.ndarray, emb2: np.ndarray) -> tuple[str, float]:
        sim = float(np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2)))
        if sim >= self.t_accept:
            return "ACCEPT", sim
        elif sim < self.t_reject:
            return "REJECT", sim
        else:
            return "REVIEW_REQUIRED", sim