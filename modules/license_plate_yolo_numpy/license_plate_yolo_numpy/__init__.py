"""API nhận diện biển số xe từ ảnh OpenCV."""

from .ocr_numpy import OCRResult
from .pipeline import LicensePlateReader, PlateResult, read_image_bgr, save_annotated

__all__ = [
    "LicensePlateReader",
    "OCRResult",
    "PlateResult",
    "read_image_bgr",
    "save_annotated",
]
