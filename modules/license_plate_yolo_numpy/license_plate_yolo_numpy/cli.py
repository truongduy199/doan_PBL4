"""CLI: license-plate-reader --image <đường_dẫn_ảnh>."""
import argparse
import sys
from pathlib import Path

from .pipeline import (
    DEFAULT_OCR_WEIGHTS, DEFAULT_YOLO_WEIGHTS,
    LicensePlateReader, read_image_bgr, save_annotated,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="YOLO phát hiện biển số, OCR NumPy đọc ký tự trên crop BGR"
    )
    parser.add_argument("--image", required=True, type=Path,
                        help="Ảnh gốc (có thể chứa nhiều biển số)")
    parser.add_argument("--yolo-weights", type=Path, default=DEFAULT_YOLO_WEIGHTS,
                        help="Trọng số YOLO, mặc định dùng best.pt đi kèm gói")
    parser.add_argument("--ocr-weights", type=Path, default=DEFAULT_OCR_WEIGHTS,
                        help="Trọng số OCR, mặc định dùng ocr_coco_weights.npz đi kèm gói")
    parser.add_argument("--conf", type=float, default=0.25,
                        help="Ngưỡng YOLO confidence (mặc định: 0.25)")
    parser.add_argument("--iou", type=float, default=0.45,
                        help="Ngưỡng YOLO NMS IoU (mặc định: 0.45)")
    parser.add_argument("--save", type=Path, default=None,
                        help="Tùy chọn lưu ảnh đã vẽ bbox, ví dụ results/output.jpg")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        image_bgr = read_image_bgr(args.image)
        reader = LicensePlateReader(
            yolo_weights=args.yolo_weights,
            ocr_weights=args.ocr_weights,
            conf=args.conf,
            iou=args.iou,
        )
        plates = reader.predict(image_bgr)
        print(f"Ảnh: {args.image}")
        print(f"Số biển số phát hiện: {len(plates)}")
        for index, plate in enumerate(plates, start=1):
            x1, y1, x2, y2 = plate.bbox
            print(f"Biển số #{index}:")
            print(f"  Bounding box (x1,y1,x2,y2): ({x1}, {y1}, {x2}, {y2})")
            print(f"  YOLO confidence: {plate.confidence:.4f}")
            print(f"  OCR: {plate.ocr.text or '(không đọc được ký tự)'}")
            print(f"  OCR thô: {plate.ocr.raw_text or '(trống)'}")
            print(f"  Số ký tự tách được: {plate.ocr.char_count}")
        if args.save is not None:
            save_annotated(image_bgr, plates, args.save)
            print(f"Đã lưu ảnh kết quả: {args.save}")
        return 0
    except (FileNotFoundError, ValueError, RuntimeError, OSError) as exc:
        print(f"Lỗi: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
