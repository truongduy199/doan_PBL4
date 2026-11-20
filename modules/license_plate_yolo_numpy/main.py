"""Tương thích với lệnh `python main.py` từ thư mục mã nguồn."""

from license_plate_yolo_numpy.cli import build_parser, main

__all__ = ["build_parser", "main"]

if __name__ == "__main__":
    raise SystemExit(main())
