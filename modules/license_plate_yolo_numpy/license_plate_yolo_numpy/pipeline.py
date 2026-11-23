"""Phát hiện YOLO trên ảnh gốc, crop BGR, đưa thẳng sang OCR NumPy."""
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from .ocr_numpy import NumpyPlateOCR, OCRResult


WEIGHTS_DIR = Path(__file__).resolve().parent / "weights"
DEFAULT_YOLO_WEIGHTS = WEIGHTS_DIR / "best.pt"
DEFAULT_OCR_WEIGHTS = WEIGHTS_DIR / "ocr_coco_weights.npz"


@dataclass(frozen=True)
class PlateResult:
    bbox: tuple[int, int, int, int]  # x1,y1,x2,y2 theo tọa độ ảnh gốc
    confidence: float
    ocr: OCRResult


class LicensePlateReader:
    """Hai model được khởi tạo một lần trong constructor, KHÔNG tạo lại mỗi bbox."""

    def __init__(
        self,
        yolo_weights: str | Path = DEFAULT_YOLO_WEIGHTS,
        ocr_weights: str | Path = DEFAULT_OCR_WEIGHTS,
        conf: float = 0.25,
        iou: float = 0.45,
        *,
        detector=None,
        ocr=None,
        detector_imgsz: int | None = None,
    ):
        if not 0 < conf <= 1:
            raise ValueError("--conf phải nằm trong (0, 1]")
        if not 0 < iou <= 1:
            raise ValueError("--iou phải nằm trong (0, 1]")
        self.conf = conf
        self.iou = iou
        if detector_imgsz is not None and (detector_imgsz < 320 or detector_imgsz > 1920 or detector_imgsz % 32):
            raise ValueError("detector_imgsz phải là bội số 32 trong khoảng 320..1920")
        self.detector_imgsz = detector_imgsz

        if detector is None:
            path = Path(yolo_weights)
            if not path.is_file():
                raise FileNotFoundError(f"Không tìm thấy trọng số YOLO: {path}")
            try:
                from ultralytics import YOLO
            except ImportError as exc:
                raise RuntimeError(
                    "Chưa cài ultralytics. Chạy: python -m pip install ultralytics"
                ) from exc
            self.detector = YOLO(str(path))  # nạp YOLO duy nhất 1 lần
        else:
            self.detector = detector

        self.ocr = ocr if ocr is not None else NumpyPlateOCR(ocr_weights)

    def predict(self, image_bgr: np.ndarray) -> list[PlateResult]:
        if (not isinstance(image_bgr, np.ndarray)
                or image_bgr.ndim != 3 or image_bgr.shape[2] != 3
                or image_bgr.dtype != np.uint8 or image_bgr.size == 0):
            raise ValueError("Ảnh đầu vào phải là NumPy uint8 HxWx3 định dạng BGR")
        height, width = image_bgr.shape[:2]
        options = {"imgsz": self.detector_imgsz} if self.detector_imgsz is not None else {}
        detections = self.detector.predict(source=image_bgr, conf=self.conf, iou=self.iou, verbose=False, **options)
        if not detections:
            return []
        boxes = detections[0].boxes
        if boxes is None or len(boxes) == 0:
            return []

        candidates: list[tuple[tuple[int, int, int, int], float]] = []
        for box in boxes:
            # YOLO -> tensor, chuyển sang CPU trước khi lấy tọa độ.
            coords = box.xyxy[0].cpu().numpy()
            if not np.all(np.isfinite(coords)):
                continue
            x1 = int(np.clip(np.floor(coords[0]), 0, width))
            y1 = int(np.clip(np.floor(coords[1]), 0, height))
            x2 = int(np.clip(np.ceil(coords[2]), 0, width))
            y2 = int(np.clip(np.ceil(coords[3]), 0, height))
            if x2 <= x1 or y2 <= y1:
                continue
            confidence = float(box.conf[0].item())
            candidates.append(((x1, y1, x2, y2), confidence))

        # Xử lý theo thứ tự trên xuống dưới, trái sang phải.
        candidates.sort(key=lambda item: (item[0][1], item[0][0]))
        results = []
        for (x1, y1, x2, y2), confidence in candidates:
            crop_bgr = image_bgr[y1:y2, x1:x2].copy()
            # Không ghi ra file / không đổi màu: NumPy BGR -> segment_characters.
            recognized = self.ocr.recognize_bgr(crop_bgr)
            results.append(
                PlateResult(bbox=(x1, y1, x2, y2), confidence=confidence, ocr=recognized)
            )
        return results


def read_image_bgr(path: str | Path) -> np.ndarray:
    """Đọc được cả đường dẫn có dấu tiếng Việt trên Windows."""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Không tìm thấy ảnh: {p}")
    encoded = np.fromfile(str(p), dtype=np.uint8)
    decoded = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    if decoded is None:
        raise ValueError(f"Không giải mã được ảnh: {p}")
    return decoded


def save_annotated(image_bgr: np.ndarray, plates: list[PlateResult], output: str | Path) -> None:
    out = image_bgr.copy()
    for index, plate in enumerate(plates, start=1):
        x1, y1, x2, y2 = plate.bbox
        cv2.rectangle(out, (x1, y1), (x2, y2), (0, 255, 0), 2)
        label = f"#{index} {plate.ocr.text or 'NO_OCR'}"
        cv2.putText(out, label, (x1, max(15, y1 - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    suffix = destination.suffix.lower()
    if suffix not in ('.jpg', '.jpeg', '.png', '.bmp'):
        raise ValueError("--save cần đuôi .jpg, .jpeg, .png hoặc .bmp")
    ok, buf = cv2.imencode(suffix, out)
    if not ok:
        raise OSError(f"Không thể mã hóa ảnh kết quả: {destination}")
    buf.tofile(str(destination))
