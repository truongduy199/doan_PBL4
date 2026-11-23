"""OCR NumPy nhận trực tiếp vùng biển số dạng ảnh OpenCV BGR (không đọc lại file)."""
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from .decoder import decode_plate_characters
from .mlp_numpy import NumpyMLP
from .segment import segment_characters


_SMALL_PLATE_MAX_WIDTH = 150


@dataclass(frozen=True)
class OCRResult:
    raw_text: str
    text: str
    char_count: int


class NumpyPlateOCR:
    """Nạp bộ trọng số OCR một lần, tái sử dụng cho nhiều biển số."""

    def __init__(self, weights_path: str | Path):
        path = Path(weights_path)
        if not path.is_file():
            raise FileNotFoundError(f"Không tìm thấy trọng số OCR: {path}")
        self.model = NumpyMLP()
        self.model.load_weights(str(path))

    def recognize_bgr(self, plate_bgr: np.ndarray) -> OCRResult:
        """Nhận HxWx3, uint8, thứ tự kênh BGR; không đổi sang RGB."""
        if (not isinstance(plate_bgr, np.ndarray)
                or plate_bgr.ndim != 3
                or plate_bgr.shape[2] != 3
                or plate_bgr.dtype != np.uint8
                or plate_bgr.size == 0):
            raise ValueError("Ảnh crop OCR phải là NumPy uint8 HxWx3 ở định dạng BGR")

        # Phóng to biển nhỏ trước khi lọc và tách ký tự.
        if plate_bgr.shape[1] <= _SMALL_PLATE_MAX_WIDTH:
            plate_bgr = cv2.resize(plate_bgr, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        char_items, _threshold_image = segment_characters(plate_bgr)
        if not char_items:
            return OCRResult(raw_text="", text="", char_count=0)

        batch = np.asarray(
            [character.flatten().astype(np.float32) / 255.0
             for character, _char_box in char_items],
            dtype=np.float32,
        )
        probs = self.model.forward(batch)
        # Giữ nguyên bộ giải mã và các luật biển số Việt Nam từ main(1).py.
        raw_text, final_text = decode_plate_characters(char_items, probs)
        return OCRResult(raw_text=raw_text, text=final_text, char_count=len(char_items))
