"""1:1 Face Verifier with Metadata Compatibility & Dual Thresholds (Section I.7 & IV.8)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple
import numpy as np

from smart_parking.ai.face.template import FaceTemplateNormalizer


@dataclass(frozen=True)
class FaceVerificationOutcome:
    decision: str          # "ACCEPT", "REJECT", or "REVIEW_REQUIRED"
    similarity: Optional[float]
    reason_code: str
    t_accept: float
    t_reject: float


class FaceVerifier:
    """
    Compares two L2-normalized 512-D templates using cosine similarity s = dot(t_ref, t_current):
    - Checks model_id and model_version compatibility first (returns REVIEW_REQUIRED / MODEL_MISMATCH on mismatch).
    - s >= T_accept -> ACCEPT
    - s <  T_reject -> REJECT (FACE_MISMATCH)
    - T_reject <= s < T_accept -> REVIEW_REQUIRED (FACE_REVIEW_REQUIRED)
    """

    def __init__(self, t_accept: float = 0.65, t_reject: float = 0.45) -> None:
        if t_reject > t_accept:
            raise ValueError("Ngưỡng T_reject không được lớn hơn T_accept.")
        self.t_accept = float(t_accept)
        self.t_reject = float(t_reject)

    def verify(self, emb1: np.ndarray, emb2: np.ndarray) -> Tuple[str, float]:
        v1 = FaceTemplateNormalizer.l2_normalize(emb1)
        v2 = FaceTemplateNormalizer.l2_normalize(emb2)
        sim = float(np.dot(v1, v2))
        if sim >= self.t_accept:
            return "ACCEPT", sim
        elif sim < self.t_reject:
            return "REJECT", sim
        else:
            return "REVIEW_REQUIRED", sim

    def verify_with_metadata(
        self,
        reference_embedding: Optional[np.ndarray],
        candidate_embedding: Optional[np.ndarray],
        ref_model_id: Optional[str] = None,
        cand_model_id: Optional[str] = None,
        ref_model_version: Optional[str] = None,
        cand_model_version: Optional[str] = None,
    ) -> FaceVerificationOutcome:
        if reference_embedding is None or candidate_embedding is None:
            return FaceVerificationOutcome(
                decision="REVIEW_REQUIRED",
                similarity=None,
                reason_code="FACE_TEMPLATE_MISSING",
                t_accept=self.t_accept,
                t_reject=self.t_reject,
            )

        if ref_model_id and cand_model_id and ref_model_id != cand_model_id:
            return FaceVerificationOutcome(
                decision="REVIEW_REQUIRED",
                similarity=None,
                reason_code="MODEL_MISMATCH",
                t_accept=self.t_accept,
                t_reject=self.t_reject,
            )

        if ref_model_version and cand_model_version and ref_model_version != cand_model_version:
            return FaceVerificationOutcome(
                decision="REVIEW_REQUIRED",
                similarity=None,
                reason_code="MODEL_MISMATCH",
                t_accept=self.t_accept,
                t_reject=self.t_reject,
            )

        try:
            decision, sim = self.verify(reference_embedding, candidate_embedding)
        except ValueError:
            return FaceVerificationOutcome(
                decision="REVIEW_REQUIRED",
                similarity=None,
                reason_code="FACE_INFERENCE_ERROR",
                t_accept=self.t_accept,
                t_reject=self.t_reject,
            )

        reason = (
            "FACE_MATCH_ACCEPTED"
            if decision == "ACCEPT"
            else ("FACE_MISMATCH" if decision == "REJECT" else "FACE_REVIEW_REQUIRED")
        )
        return FaceVerificationOutcome(
            decision=decision,
            similarity=round(sim, 4),
            reason_code=reason,
            t_accept=self.t_accept,
            t_reject=self.t_reject,
        )
