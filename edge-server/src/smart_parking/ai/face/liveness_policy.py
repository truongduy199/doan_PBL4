"""Face Liveness Policy (Fail-Closed Anti-Spoofing per Section I.8 & T20)."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Optional

from smart_parking.domain.enums import LivenessStatus


@dataclass(frozen=True)
class LivenessCheckResult:
    is_valid_live: bool
    liveness_status: str
    liveness_score: Optional[float]
    reason_code: str
    message: str


class FaceLivenessPolicy:
    """
    Evaluates InsightFace addon `liveness` output in fail-closed mode:
    - Live gate scans (IN/OUT) MUST achieve `liveness_status == 'Passed'` and `live_score >= threshold`.
    - Missing addon result, input_rejected, error, or score < threshold NEVER auto-approves (`T20`).
    - Offline internal template imports explicitly record `liveness_status = 'Not_used'` and `liveness_score = None`.
    """

    @staticmethod
    def evaluate(score: float, threshold: float = 0.80) -> bool:
        if score is None or not math.isfinite(float(score)):
            return False
        return float(score) >= threshold

    @classmethod
    def evaluate_face_object(
        cls,
        face: Any,
        threshold: float = 0.80,
        require_liveness: bool = True,
    ) -> LivenessCheckResult:
        if not require_liveness:
            return LivenessCheckResult(
                is_valid_live=True,
                liveness_status=LivenessStatus.NOT_USED.value,
                liveness_score=None,
                reason_code="LIVENESS_NOT_USED_OFFLINE_IMPORT",
                message="Mẫu nhập nội bộ không chạy live anti-spoofing (Not_used / score NULL).",
            )

        result = getattr(face, "liveness", None)
        if result is None:
            return LivenessCheckResult(
                is_valid_live=False,
                liveness_status=LivenessStatus.UNAVAILABLE.value,
                liveness_score=None,
                reason_code="LIVENESS_UNAVAILABLE",
                message="Thiếu kết quả từ addon liveness (LIVENESS_UNAVAILABLE).",
            )

        status = getattr(result, "status", None)
        if status == "input_rejected":
            return LivenessCheckResult(
                is_valid_live=False,
                liveness_status=LivenessStatus.ERROR.value,
                liveness_score=None,
                reason_code="LIVENESS_INPUT_REJECTED",
                message="Khuôn mặt không nằm trọn trong khung kiểm tra liveness.",
            )
        if status != "ok":
            return LivenessCheckResult(
                is_valid_live=False,
                liveness_status=LivenessStatus.ERROR.value,
                liveness_score=None,
                reason_code="LIVENESS_ERROR",
                message=f"Trạng thái liveness không hợp lệ: {status}.",
            )

        raw_score = getattr(result, "live_score", None)
        try:
            live_score = float(raw_score)
        except (TypeError, ValueError):
            return LivenessCheckResult(
                is_valid_live=False,
                liveness_status=LivenessStatus.ERROR.value,
                liveness_score=None,
                reason_code="LIVENESS_ERROR",
                message="Điểm liveness_score không phải số thực hợp lệ.",
            )

        if not math.isfinite(live_score) or not (0.0 <= live_score <= 1.0):
            return LivenessCheckResult(
                is_valid_live=False,
                liveness_status=LivenessStatus.ERROR.value,
                liveness_score=None,
                reason_code="LIVENESS_ERROR",
                message="Điểm liveness_score nằm ngoài miền [0, 1].",
            )

        is_live = getattr(result, "is_live", None)
        if is_live is not True or live_score < threshold:
            return LivenessCheckResult(
                is_valid_live=False,
                liveness_status=LivenessStatus.FAILED.value,
                liveness_score=round(live_score, 4),
                reason_code="LIVENESS_FAILED",
                message=f"Phát hiện dấu hiệu giả mạo ảnh/màn hình (score={live_score:.2f} < {threshold:.2f}).",
            )

        return LivenessCheckResult(
            is_valid_live=True,
            liveness_status=LivenessStatus.PASSED.value,
            liveness_score=round(live_score, 4),
            reason_code="LIVENESS_PASSED",
            message=f"Liveness đạt ({live_score:.2f}).",
        )
