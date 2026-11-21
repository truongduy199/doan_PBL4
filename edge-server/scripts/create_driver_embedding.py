"""CLI Tool to Export 512-D L2-Normalized Driver Face Embedding JSON for Demo Seeding (Section IV.4 & VII.2).

Usage:
    # 1. Tạo từ ảnh mẫu tài xế (mặc định ghi liveness_status="Not_used", liveness_score=null đúng chính sách nhập nội bộ):
    python edge-server/scripts/create_driver_embedding.py --image path/to/driver.jpg --output driver_embedding.json

    # 2. Sau đó nạp vào MySQL bằng script của Việt:
    python edge-server/scripts/seed_demo_data.py --plate 43A12345 --embedding-file driver_embedding.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import cv2
import numpy as np

EDGE_SERVER_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = EDGE_SERVER_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from smart_parking.ai.face.insightface_adapter import InsightFaceAdapter
from smart_parking.ai.face.pipeline import FacePipeline
from smart_parking.config.constants import (
    DEFAULT_FACE_CONFIG_VERSION,
    DEFAULT_FACE_MODEL_ID,
    DEFAULT_FACE_MODEL_VERSION,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Trích xuất vector 512-D Buffalo-L chuẩn hóa L2 ra file JSON để nạp user_face_templates."
    )
    parser.add_argument(
        "--image",
        type=Path,
        nargs="+",
        required=True,
        help="Một hoặc nhiều đường dẫn ảnh mẫu khuôn mặt tài xế.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Đường dẫn file JSON đầu ra (ví dụ: driver_embedding.json).",
    )
    parser.add_argument(
        "--model-root",
        type=Path,
        default=EDGE_SERVER_DIR / "models" / "insightface",
        help="Thư mục chứa model InsightFace buffalo_l.",
    )
    parser.add_argument(
        "--require-liveness",
        action="store_true",
        help="Nếu bật, chạy cả addon liveness. Mặc định tắt cho ảnh mẫu nhập nội bộ (ghi Not_used/null).",
    )
    return parser.parse_args()


def read_image_bgr(path: Path) -> np.ndarray:
    if not path.is_file():
        raise FileNotFoundError(f"Không tìm thấy file ảnh: {path}")
    raw = np.fromfile(str(path), dtype=np.uint8)
    img = cv2.imdecode(raw, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"Không giải mã được file ảnh: {path}")
    return img


def main() -> int:
    args = parse_args()
    frames = [read_image_bgr(p) for p in args.image]

    adapter = InsightFaceAdapter(
        model_root=args.model_root,
        model_pack=DEFAULT_FACE_MODEL_ID,
        liveness_enabled=args.require_liveness,
    )
    if not adapter.initialize():
        print("Lỗi: Không khởi tạo được InsightFace Buffalo-L.", file=sys.stderr)
        return 2

    pipeline = FacePipeline(
        adapter=adapter,
        model_id=DEFAULT_FACE_MODEL_ID,
        model_version=DEFAULT_FACE_MODEL_VERSION,
        config_version=DEFAULT_FACE_CONFIG_VERSION,
    )
    res = pipeline.process_frames(frames, require_liveness=args.require_liveness, min_valid_samples=1)
    if not res.ok or res.embedding is None:
        print(f"Lỗi trích xuất mẫu khuôn mặt ({res.reason_code}): {res.message}", file=sys.stderr)
        return 1

    payload = {
        "embedding": [round(float(x), 8) for x in res.embedding.tolist()],
        "model_id": res.model_id,
        "model_version": res.model_version,
        "config_version": res.config_version,
        "quality_score": res.quality_score,
        "liveness_status": res.liveness_status,
        "liveness_score": res.liveness_score,
        "source_policy": "live_liveness_verified" if args.require_liveness else "controlled_offline_import",
        "valid_sample_count": res.valid_sample_count,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Đã xuất mẫu khuôn mặt 512-D chuẩn hóa L2 ra: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
