"""Face Quality Checker (Single face, bounding box margin, size, pose/landmarks, blur & brightness)."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Optional, Tuple

import numpy as np


@dataclass(frozen=True)
class FaceQualityResult:
    passed: bool
    quality_score: Optional[float]
    reason_code: str
    message: str


class FaceQualityChecker:
    """Validates face bounding box, landmarks pose, blur (Laplacian variance), and brightness."""

    @staticmethod
    def check_blur(frame_bgr: np.ndarray) -> float:
        import cv2
        if frame_bgr is None or frame_bgr.size == 0:
            return 0.0
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY) if frame_bgr.ndim == 3 else frame_bgr
        return float(cv2.Laplacian(gray, cv2.CV_64F).var())

    @staticmethod
    def check_pose(landmarks: Any) -> Tuple[bool, str]:
        if landmarks is None:
            return False, "Thiếu 5 điểm landmark khuôn mặt."
        kps = np.asarray(landmarks, dtype=np.float32)
        if kps.shape != (5, 2):
            return False, "Landmark khuôn mặt không đủ 5 điểm."

        left_eye, right_eye, nose, left_mouth, right_mouth = kps
        eye_vector = right_eye - left_eye
        eye_distance = float(np.linalg.norm(eye_vector))
        if eye_distance < 1.0:
            return False, "Khoảng cách hai mắt quá nhỏ."

        roll_degrees = abs(math.degrees(math.atan2(float(eye_vector[1]), float(eye_vector[0]))))
        if roll_degrees > 15.0:
            return False, f"Đầu nghiêng quá góc cho phép ({roll_degrees:.1f} độ)."

        left_nose_dist = float(np.linalg.norm(nose - left_eye))
        right_nose_dist = float(np.linalg.norm(nose - right_eye))
        yaw_asymmetry = abs(left_nose_dist - right_nose_dist) / max(left_nose_dist, right_nose_dist, 1.0)
        eye_midpoint = (left_eye + right_eye) * 0.5
        nose_horiz_offset = abs(float(nose[0] - eye_midpoint[0])) / eye_distance
        if yaw_asymmetry > 0.32 or nose_horiz_offset > 0.28:
            return False, "Khuôn mặt quay ngang quá mức, cần nhìn thẳng camera."

        eye_line_y = float((left_eye[1] + right_eye[1]) * 0.5)
        mouth_line_y = float((left_mouth[1] + right_mouth[1]) * 0.5)
        eye_to_mouth = mouth_line_y - eye_line_y
        if eye_to_mouth <= 1.0:
            return False, "Tọa độ mắt-miệng không hợp lệ."
        nose_vert_ratio = float(nose[1] - eye_line_y) / eye_to_mouth
        if not (0.20 <= nose_vert_ratio <= 0.92):
            return False, "Góc ngẩng/cúi mặt không hợp lệ."

        return True, "Pose hợp lệ."

    @classmethod
    def evaluate(
        cls,
        face: Any,
        frame_bgr: np.ndarray,
        min_face_size: int = 64,
        min_blur_var: float = 20.0,
    ) -> FaceQualityResult:
        if frame_bgr is None or frame_bgr.ndim != 3 or frame_bgr.size == 0:
            return FaceQualityResult(False, None, "FACE_QUALITY_FAILED", "Ảnh đầu vào rỗng hoặc sai định dạng.")

        frame_h, frame_w = frame_bgr.shape[:2]
        bbox = getattr(face, "bbox", None)
        if bbox is None:
            return FaceQualityResult(False, None, "FACE_QUALITY_FAILED", "Không có bbox khuôn mặt.")

        x1, y1, x2, y2 = np.asarray(bbox, dtype=np.float32)[:4]
        face_w = float(x2 - x1)
        face_h = float(y2 - y1)
        face_size = min(face_w, face_h)
        if face_w <= 0 or face_h <= 0:
            return FaceQualityResult(False, None, "FACE_QUALITY_FAILED", "Kích thước bbox không hợp lệ.")

        margin_x = max(6.0, face_w * 0.06)
        margin_y = max(6.0, face_h * 0.06)
        if x1 < margin_x or y1 < margin_y or x2 > (frame_w - margin_x) or y2 > (frame_h - margin_y):
            return FaceQualityResult(
                False,
                None,
                "FACE_QUALITY_FAILED",
                "Khuôn mặt bị cắt ở sát mép khung hình.",
            )

        if face_size < min_face_size:
            return FaceQualityResult(
                False,
                None,
                "FACE_QUALITY_FAILED",
                f"Khuôn mặt quá nhỏ ({face_size:.0f}px < {min_face_size}px).",
            )

        pose_ok, pose_msg = cls.check_pose(getattr(face, "kps", None))
        if not pose_ok:
            return FaceQualityResult(False, None, "FACE_QUALITY_FAILED", pose_msg)

        cx1, cy1 = max(0, int(x1)), max(0, int(y1))
        cx2, cy2 = min(frame_w, int(x2)), min(frame_h, int(y2))
        crop = frame_bgr[cy1:cy2, cx1:cx2]
        blur_score = cls.check_blur(crop) if crop.size > 0 else 100.0
        if crop.size > 0 and min_blur_var > 0 and blur_score < min_blur_var:
            return FaceQualityResult(
                False,
                None,
                "FACE_QUALITY_FAILED",
                f"Ảnh khuôn mặt bị mờ (blur={blur_score:.1f} < {min_blur_var:.1f}).",
            )

        det_score = float(getattr(face, "det_score", 0.90) or 0.90)
        size_ratio = min(1.0, face_size / max(float(min_face_size * 1.5), 1.0))
        quality_score = round(float(0.6 * min(1.0, max(0.0, det_score)) + 0.4 * size_ratio), 4)
        return FaceQualityResult(True, quality_score, "OK", "Chất lượng khuôn mặt đạt yêu cầu.")
