"""Tương thích với cách import pipeline từ bản mã nguồn trước."""

from license_plate_yolo_numpy.pipeline import (
    DEFAULT_OCR_WEIGHTS,
    DEFAULT_YOLO_WEIGHTS,
    LicensePlateReader,
    OCRResult,
    PlateResult,
    read_image_bgr,
    save_annotated,
)

__all__ = [
    "DEFAULT_OCR_WEIGHTS",
    "DEFAULT_YOLO_WEIGHTS",
    "LicensePlateReader",
    "OCRResult",
    "PlateResult",
    "read_image_bgr",
    "save_annotated",
]
