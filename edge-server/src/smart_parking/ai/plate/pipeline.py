"""License Plate Pipeline integrating `modules/license_plate_yolo_numpy` (Section II & IV.1)."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from smart_parking.ai.plate.normalizer import PlateNormalizer
from smart_parking.ai.plate.validator import PlateValidator

# Ensure `modules/license_plate_yolo_numpy` in repo root is importable
_REPO_ROOT = Path(__file__).resolve().parents[5]
_LP_MODULE_DIR = _REPO_ROOT / "modules" / "license_plate_yolo_numpy"
if _LP_MODULE_DIR.is_dir() and str(_LP_MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(_LP_MODULE_DIR))


@dataclass(frozen=True)
class PlateRecognitionOutcome:
    ok: bool
    reason_code: str
    message: str
    raw_text: str
    normalized_plate: str
    display_plate: str
    detector_confidence: Optional[float]
    ocr_confidence: Optional[float]
    bbox: Optional[Tuple[int, int, int, int]]
    detector_version: str
    ocr_version: str
    latency_ms: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "reason_code": self.reason_code,
            "message": self.message,
            "raw_text": self.raw_text,
            "normalized_plate": self.normalized_plate,
            "display_plate": self.display_plate,
            "detector_confidence": self.detector_confidence,
            "ocr_confidence": self.ocr_confidence,
            "bbox": list(self.bbox) if self.bbox else None,
            "detector_version": self.detector_version,
            "ocr_version": self.ocr_version,
            "latency_ms": round(self.latency_ms, 2),
        }


class PlatePipeline:
    """
    Wraps `LicensePlateReader` (YOLO detector + NumPy MLP OCR):
    - Enforces single clear plate candidate inside gate ROI (rejects multiple ambiguous plates per Section II.5).
    - Normalizes and validates Vietnamese license plate format without forcing near-matches.
    - Supports multi-frame voting across a burst of frames from ESP32-S3 OV5640.
    - Never opens barrier servos directly.
    """

    def __init__(
        self,
        reader: Any = None,
        conf: float = 0.25,
        iou: float = 0.45,
        detector_version: str = "yolo-plate-best-v1",
        ocr_version: str = "numpy-mlp-coco-v1",
        lazy_init: bool = True,
        detector_imgsz: int = 1280,
    ) -> None:
        self._reader = reader
        self.conf = conf
        self.iou = iou
        self.detector_version = detector_version
        self.ocr_version = ocr_version
        self.detector_imgsz = detector_imgsz
        if not lazy_init and self._reader is None:
            self._ensure_reader()

    def _ensure_reader(self) -> Any:
        if self._reader is not None:
            return self._reader
        from license_plate_yolo_numpy import LicensePlateReader  # type: ignore

        self._reader = LicensePlateReader(conf=self.conf, iou=self.iou, detector_imgsz=self.detector_imgsz)
        return self._reader

    @staticmethod
    def crop_roi(frame_bgr: np.ndarray, roi: Optional[Tuple[int, int, int, int]]) -> np.ndarray:
        if roi is None:
            return frame_bgr
        h, w = frame_bgr.shape[:2]
        x1, y1, x2, y2 = roi
        x1 = max(0, min(w, int(x1)))
        y1 = max(0, min(h, int(y1)))
        x2 = max(0, min(w, int(x2)))
        y2 = max(0, min(h, int(y2)))
        if x2 <= x1 or y2 <= y1:
            return frame_bgr
        return frame_bgr[y1:y2, x1:x2].copy()

    def process_frame(
        self,
        frame_bgr: np.ndarray,
        *,
        roi: Optional[Tuple[int, int, int, int]] = None,
    ) -> PlateRecognitionOutcome:
        started = time.perf_counter()
        if frame_bgr is None or not isinstance(frame_bgr, np.ndarray) or frame_bgr.ndim != 3 or frame_bgr.size == 0:
            return PlateRecognitionOutcome(
                ok=False,
                reason_code="INVALID_PLATE_IMAGE",
                message="Ảnh biển số rỗng hoặc sai định dạng BGR.",
                raw_text="",
                normalized_plate="",
                display_plate="",
                detector_confidence=None,
                ocr_confidence=None,
                bbox=None,
                detector_version=self.detector_version,
                ocr_version=self.ocr_version,
                latency_ms=(time.perf_counter() - started) * 1000.0,
            )

        target = self.crop_roi(frame_bgr, roi)
        try:
            reader = self._ensure_reader()
            results = reader.predict(target)
        except Exception as exc:
            return PlateRecognitionOutcome(
                ok=False,
                reason_code="PLATE_INFERENCE_ERROR",
                message=f"Lỗi suy luận YOLO/OCR biển số: {exc}",
                raw_text="",
                normalized_plate="",
                display_plate="",
                detector_confidence=None,
                ocr_confidence=None,
                bbox=None,
                detector_version=self.detector_version,
                ocr_version=self.ocr_version,
                latency_ms=(time.perf_counter() - started) * 1000.0,
            )

        if not results:
            return PlateRecognitionOutcome(
                ok=False,
                reason_code="NO_PLATE_DETECTED",
                message="Không tìm thấy vùng biển số trong ROI.",
                raw_text="",
                normalized_plate="",
                display_plate="",
                detector_confidence=None,
                ocr_confidence=None,
                bbox=None,
                detector_version=self.detector_version,
                ocr_version=self.ocr_version,
                latency_ms=(time.perf_counter() - started) * 1000.0,
            )

        # Section II.5: Reject ambiguous multiple plates in the same gate ROI
        if len(results) > 1:
            return PlateRecognitionOutcome(
                ok=False,
                reason_code="MULTIPLE_PLATES_IN_ROI",
                message=f"Phát hiện {len(results)} biển số trong cùng vùng nhận diện; yêu cầu kiểm tra thủ công.",
                raw_text="",
                normalized_plate="",
                display_plate="",
                detector_confidence=None,
                ocr_confidence=None,
                bbox=None,
                detector_version=self.detector_version,
                ocr_version=self.ocr_version,
                latency_ms=(time.perf_counter() - started) * 1000.0,
            )

        candidate = results[0]
        raw_text = getattr(candidate.ocr, "raw_text", "") or ""
        decoded_text = getattr(candidate.ocr, "text", "") or ""
        det_conf = round(float(candidate.confidence), 4)

        if not decoded_text:
            return PlateRecognitionOutcome(
                ok=False,
                reason_code="OCR_EMPTY_TEXT",
                message="Phát hiện vùng biển số nhưng OCR không tách được chuỗi ký tự.",
                raw_text=raw_text,
                normalized_plate="",
                display_plate="",
                detector_confidence=det_conf,
                ocr_confidence=None,
                bbox=tuple(candidate.bbox),
                detector_version=self.detector_version,
                ocr_version=self.ocr_version,
                latency_ms=(time.perf_counter() - started) * 1000.0,
            )

        try:
            norm_plate = PlateNormalizer.normalize(decoded_text)
        except ValueError as exc:
            return PlateRecognitionOutcome(
                ok=False,
                reason_code="INVALID_PLATE_FORMAT",
                message=str(exc),
                raw_text=raw_text,
                normalized_plate="",
                display_plate="",
                detector_confidence=det_conf,
                ocr_confidence=None,
                bbox=tuple(candidate.bbox),
                detector_version=self.detector_version,
                ocr_version=self.ocr_version,
                latency_ms=(time.perf_counter() - started) * 1000.0,
            )

        if not PlateValidator.is_valid_vietnamese_plate(norm_plate):
            return PlateRecognitionOutcome(
                ok=False,
                reason_code="INVALID_PLATE_FORMAT",
                message=f"Chuỗi OCR '{norm_plate}' không khớp định dạng biển số Việt Nam.",
                raw_text=raw_text,
                normalized_plate=norm_plate,
                display_plate=PlateNormalizer.format_display(norm_plate),
                detector_confidence=det_conf,
                ocr_confidence=None,
                bbox=tuple(candidate.bbox),
                detector_version=self.detector_version,
                ocr_version=self.ocr_version,
                latency_ms=(time.perf_counter() - started) * 1000.0,
            )

        return PlateRecognitionOutcome(
            ok=True,
            reason_code="OK",
            message="Đọc biển số thành công.",
            raw_text=raw_text,
            normalized_plate=norm_plate,
            display_plate=PlateNormalizer.format_display(norm_plate),
            detector_confidence=det_conf,
            ocr_confidence=det_conf,
            bbox=tuple(candidate.bbox),
            detector_version=self.detector_version,
            ocr_version=self.ocr_version,
            latency_ms=(time.perf_counter() - started) * 1000.0,
        )

    def process_frames(
        self,
        frames_bgr: Sequence[np.ndarray],
        *,
        roi: Optional[Tuple[int, int, int, int]] = None,
    ) -> PlateRecognitionOutcome:
        """Multi-frame voting across a burst of frames for the same gate event (Section II.5)."""
        if not frames_bgr:
            return PlateRecognitionOutcome(
                ok=False,
                reason_code="INVALID_PLATE_IMAGE",
                message="Không có frame biển số nào để xử lý.",
                raw_text="",
                normalized_plate="",
                display_plate="",
                detector_confidence=None,
                ocr_confidence=None,
                bbox=None,
                detector_version=self.detector_version,
                ocr_version=self.ocr_version,
                latency_ms=0.0,
            )

        valid_outcomes: List[PlateRecognitionOutcome] = []
        last_failure: Optional[PlateRecognitionOutcome] = None
        for frame in frames_bgr:
            out = self.process_frame(frame, roi=roi)
            if out.ok:
                valid_outcomes.append(out)
            else:
                last_failure = out

        if not valid_outcomes:
            assert last_failure is not None
            return last_failure

        counts = Counter(o.normalized_plate for o in valid_outcomes)
        most_common = counts.most_common()
        if len(most_common) > 1 and most_common[0][1] == most_common[1][1]:
            return PlateRecognitionOutcome(
                ok=False,
                reason_code="PLATE_VOTING_CONFLICT",
                message="Kết quả OCR giữa các frame mâu thuẫn nhau; chuyển quản trị viên kiểm tra.",
                raw_text=valid_outcomes[0].raw_text,
                normalized_plate="",
                display_plate="",
                detector_confidence=valid_outcomes[0].detector_confidence,
                ocr_confidence=None,
                bbox=valid_outcomes[0].bbox,
                detector_version=self.detector_version,
                ocr_version=self.ocr_version,
                latency_ms=sum(o.latency_ms for o in valid_outcomes),
            )

        winner_plate = most_common[0][0]
        if len(frames_bgr) >= 3 and most_common[0][1] < 2:
            first = valid_outcomes[0]
            from dataclasses import replace
            return replace(first, ok=False, reason_code="PLATE_INSUFFICIENT_CONSENSUS",
                           message="Chưa có ít nhất hai ảnh cùng đọc đúng một biển số.",
                           normalized_plate="", display_plate="", ocr_confidence=None)
        for o in valid_outcomes:
            if o.normalized_plate == winner_plate:
                return o
        return valid_outcomes[0]

    def process(self, frame: np.ndarray) -> PlateRecognitionOutcome:
        return self.process_frame(frame)
